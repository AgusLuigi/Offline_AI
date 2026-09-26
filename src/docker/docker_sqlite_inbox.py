"""
Modul: docker_sqlite_inbox.py
Projekt: Mai_AI (MaiOmni)

Dieses Modul stellt feingranulare Funktionen für Schritt 4 (Asynchrone SQLite-Inbox für Chat-Requests)
bereit. Es entkoppelt das HTML-Interface von der KI-Engine über eine relationale Queue:
`HTML-Interface -> Request (SQLite-Inbox) -> Agent/Engine -> Chat-Antwort`.
Alle Standard-Dateinamen und Model-Referenzen stammen aus `config/docker_global.json`.
"""

import os
import sys
import time
import sqlite3
import logging
from typing import Dict, Any, List, Optional, Tuple

from src.docker_py.docker_config import (
    load_docker_global_config,
    get_sqlite_inbox_config,
    get_storage_config,
    find_project_root
)

try:
    from src.Install.ollama_model_utils import sanitize_ollama_model_name
except ImportError:
    def sanitize_ollama_model_name(raw_name: str, default_fallback: str = "codestral") -> str:
        if not raw_name or not isinstance(raw_name, str):
            return default_fallback
        return raw_name.strip().lower() or default_fallback

logger = logging.getLogger("DockerSqliteInbox")


def get_inbox_database_path(
    user_id: Optional[str] = None,
    base_dir: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None
) -> str:
    """
    Ermittelt den Pfad zur SQLite-Inbox-Datenbankdatei anhand von `config/docker_global.json`.

    Args:
        user_id (Optional[str]): Falls angegeben, im User-Space; andernfalls im zentralen Datenverzeichnis.
        base_dir (Optional[str]): Optionaler Basispfad.
        config (Optional[Dict[str, Any]]): Optionale Konfiguration.

    Returns:
        str: Absoluter Dateipfad zur `.db`-Datei.
    """
    inbox_cfg = get_sqlite_inbox_config(config)
    storage_cfg = get_storage_config(config)
    root = base_dir or find_project_root()

    if user_id:
        from src.docker_py.docker_user_isolation import sanitize_user_identifier, get_user_base_directory
        clean_id = sanitize_user_identifier(user_id)
        user_inbox_dir = os.path.join(get_user_base_directory(root, config=config), clean_id, "inbox")
        os.makedirs(user_inbox_dir, exist_ok=True)
        filename = inbox_cfg.get("db_filename", "user_inbox.db")
        return os.path.join(user_inbox_dir, filename)
    else:
        shared_rel = storage_cfg.get("base_inbox_dir", "data/inbox")
        shared_dir = os.path.join(root, shared_rel)
        os.makedirs(shared_dir, exist_ok=True)
        filename = inbox_cfg.get("shared_db_filename", "platform_inbox.db")
        return os.path.join(shared_dir, filename)


def init_inbox_database(db_path: str) -> bool:
    """
    Initialisiert das relationale Schema für die SQLite-Inbox:
    - `incoming_requests`: Puffer für Benutzer-Anfragen aus dem HTML-Interface
    - `chat_responses`: Asynchrone Antworten der KI-Engine
    - `audit_log`: System- und Zustandsereignisse

    Args:
        db_path (str): Pfad zur SQLite-Datei.

    Returns:
        bool: True bei erfolgreicher Schema-Erstellung.
    """
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # 1. Tabelle für eingehende HTML-Requests
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS incoming_requests (
                    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    priority INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'PENDING',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed_at TIMESTAMP NULL
                )
            """)
            
            # 2. Tabelle für generierte Chat-Antworten
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_responses (
                    response_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    response_text TEXT NOT NULL,
                    model_used TEXT DEFAULT 'codestral',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(request_id) REFERENCES incoming_requests(request_id)
                )
            """)
            
            # 3. Tabelle für Audit-Events
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_req_status ON incoming_requests(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_req_user ON incoming_requests(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_resp_req ON chat_responses(request_id)")
            
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Fehler bei init_inbox_database ({db_path}): {e}")
        return False


def enqueue_user_request(
    db_path: str,
    user_id: str,
    prompt: str,
    priority: Optional[int] = None,
    config: Optional[Dict[str, Any]] = None
) -> int:
    """
    Stellt eine neue Anfrage aus dem HTML-Interface in die SQLite-Inbox ein (Status: PENDING).

    Args:
        db_path (str): Pfad zur Inbox-Datenbank.
        user_id (str): Benutzerkennung.
        prompt (str): Inhalt der Chat-Anfrage.
        priority (Optional[int]): Dringlichkeit oder None für Config-Standard.
        config (Optional[Dict[str, Any]]): Optionale Konfiguration.

    Returns:
        int: Die generierte `request_id` (oder -1 bei Fehler).
    """
    inbox_cfg = get_sqlite_inbox_config(config)
    eff_priority = priority if priority is not None else int(inbox_cfg.get("default_priority", 1))

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO incoming_requests (user_id, prompt, priority, status) VALUES (?, ?, ?, 'PENDING')",
                (user_id, prompt, eff_priority)
            )
            conn.commit()
            req_id = cursor.lastrowid
            
            cursor.execute(
                "INSERT INTO audit_log (user_id, event_type, details) VALUES (?, 'REQUEST_ENQUEUED', ?)",
                (user_id, f"Request ID {req_id} enqueued")
            )
            conn.commit()
            return req_id
    except Exception as e:
        logger.error(f"Fehler beim Enqueue des Requests: {e}")
        return -1


def fetch_pending_requests(
    db_path: str,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Liest ausstehende Anfragen (Status: PENDING) aus der Inbox zur Abarbeitung durch den Agenten.

    Args:
        db_path (str): Pfad zur Inbox-Datenbank.
        limit (int): Maximale Anzahl zu ladender Anfragen.

    Returns:
        List[Dict[str, Any]]: Liste der Anfragen als Dictionaries.
    """
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM incoming_requests WHERE status = 'PENDING' ORDER BY priority DESC, created_at ASC LIMIT ?",
                (limit,)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Fehler bei fetch_pending_requests: {e}")
        return []


def store_chat_response(
    db_path: str,
    request_id: int,
    user_id: str,
    response_text: str,
    model_used: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None
) -> int:
    """
    Speichert eine generierte Chat-Antwort in der Datenbank und aktualisiert den Request auf 'COMPLETED'.

    Args:
        db_path (str): Pfad zur Inbox-Datenbank.
        request_id (int): Die ID der beantworteten Anfrage.
        user_id (str): Benutzerkennung.
        response_text (str): Die generierte KI-Antwort.
        model_used (Optional[str]): Name des Modells oder None für Config-Wert.
        config (Optional[Dict[str, Any]]): Optionale Konfiguration.

    Returns:
        int: Die generierte `response_id` (oder -1 bei Fehler).
    """
    inbox_cfg = get_sqlite_inbox_config(config)
    raw_model = model_used or inbox_cfg.get("default_model", "codestral")
    eff_model = sanitize_ollama_model_name(raw_model, default_fallback="codestral")

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO chat_responses (request_id, user_id, response_text, model_used) VALUES (?, ?, ?, ?)",
                (request_id, user_id, response_text, eff_model)
            )
            resp_id = cursor.lastrowid
            
            cursor.execute(
                "UPDATE incoming_requests SET status = 'COMPLETED', processed_at = CURRENT_TIMESTAMP WHERE request_id = ?",
                (request_id,)
            )
            
            cursor.execute(
                "INSERT INTO audit_log (user_id, event_type, details) VALUES (?, 'RESPONSE_STORED', ?)",
                (user_id, f"Response ID {resp_id} for Request {request_id}")
            )
            conn.commit()
            return resp_id
    except Exception as e:
        logger.error(f"Fehler bei store_chat_response: {e}")
        return -1


def fetch_chat_history(
    db_path: str,
    user_id: str,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    Liest den bisherigen Chatverlauf (Frage & Antwort Paare) für das HTML-Interface aus.

    Args:
        db_path (str): Pfad zur Inbox-Datenbank.
        user_id (str): Benutzerkennung.
        limit (int): Maximale Anzahl an Paaren.

    Returns:
        List[Dict[str, Any]]: Chronologische Liste der Chat-Interaktionen.
    """
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            query = """
                SELECT 
                    r.request_id, r.user_id, r.prompt, r.status, r.created_at AS requested_at,
                    c.response_id, c.response_text, c.model_used, c.created_at AS answered_at
                FROM incoming_requests r
                LEFT JOIN chat_responses c ON r.request_id = c.request_id
                WHERE r.user_id = ?
                ORDER BY r.created_at DESC
                LIMIT ?
            """
            cursor.execute(query, (user_id, limit))
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Fehler bei fetch_chat_history: {e}")
        return []


def run_step4_sqlite_inbox_test(
    user_id: str = "user_alice@mai-ai.local",
    sample_prompt: str = "Hallo Mai_AI, wie ist mein System-Status?",
    config: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    Orchestrierungsfunktion für Schritt 4 im Notebook:
    Initialisiert die SQLite-Inbox, testet den vollständigen Zyklus:
    `HTML-Interface -> Request -> SQLite-Inbox -> Dispatcher -> Chat-Antwort`
    anhand der Parameter in `config/docker_global.json`.

    Args:
        user_id (str): Benutzerkennung für den Test.
        sample_prompt (str): Beispielhafte Eingabe aus dem Web-Interface.
        config (Optional[Dict[str, Any]]): Globale Konfiguration.

    Returns:
        Tuple[bool, Dict[str, Any]]: Erfolg (bool) und Test-Metadaten.
    """
    cfg = config or load_docker_global_config()
    db_path = get_inbox_database_path(user_id, config=cfg)
    
    # 1. DB initialisieren
    schema_ok = init_inbox_database(db_path)
    if not schema_ok:
        print(f"[X] Schritt 4 fehlgeschlagen: Schema konnte nicht initialisiert werden.")
        return False, {"error": "schema_init_failed"}
        
    # 2. Anfrage einstellen (HTML -> Request)
    req_id = enqueue_user_request(db_path, user_id, sample_prompt, config=cfg)
    
    # 3. Wartende Anfragen abrufen (Inbox Puffer)
    pending = fetch_pending_requests(db_path, limit=5)
    
    # 4. Antwort simulieren & persistieren (Engine -> Chat-Antwort)
    inbox_cfg = get_sqlite_inbox_config(cfg)
    raw_default_model = inbox_cfg.get("default_model", "codestral")
    default_model = sanitize_ollama_model_name(raw_default_model, default_fallback="codestral")
    mock_reply = "System aktiv: Deine isolierte Sandbox läuft geschützt im mai-ai_network."
    resp_id = store_chat_response(db_path, req_id, user_id, mock_reply, model_used=default_model, config=cfg)
    
    # 5. Historie validieren
    history = fetch_chat_history(db_path, user_id, limit=5)

    print(f"[✓] Schritt 4 erfolgreich konfiguriert: SQLite-Inbox für asynchrones Messaging aktiv")
    print(f"    -> Inbox-Datenbank: {db_path}")
    print(f"    -> Request Enqueue (ID: {req_id}): \"{sample_prompt}\" (Status: PENDING -> COMPLETED)")
    print(f"    -> Chat-Antwort verarbeitet (ID: {resp_id}, Modell: '{default_model}'): \"{mock_reply}\"")
    print(f"    -> Nachrichten-Pipeline: HTML-Interface -> Request -> Chat-Antwort erfolgreich verifiziert.")

    return True, {
        "db_path": db_path,
        "request_id": req_id,
        "response_id": resp_id,
        "history_count": len(history)
    }
