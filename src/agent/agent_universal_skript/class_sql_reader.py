import os
import sqlite3
from datetime import datetime
from pathlib import Path


class class_sql_reader:
    """
    Universeller SQL-Reader für den Knowledge Agent Routing Tree.
    Alle konfigurierbaren Parameter sind als Klassenattribute definiert,
    damit Agenten sie per Unterklasse oder Instanz überschreiben können.
    Keine fixen Agent-Namen, Domains oder Tabellen im Code-Body.
    """
    # KONFIGURIERBARE KLASSENATTRIBUTE (überschreibbar durch Agenten)
    # Erlaubte Tabellen für SQL-Operationen
    ALLOWED_TABLES = {
        "user_query",
        "table_issue_data_time_stamp_run_protocol_for_query"
    }

    # Fallback-Domain bei unbekannter Klassifizierung
    DEFAULT_DOMAIN = "python_domain"

    # Domain-Keyword-Mapping für die heuristische Erkennung
    DOMAIN_KEYWORDS = {
        "sql_domain": ["sql", "database", "query", "sqlite", "postgres", "select", "insert", "update", "table"],
        "infrastructure_domain": ["docker", "container", "traefik", "ollama", "deployment", "server", "network"],
        "fehlererkennung": ["bug", "fix", "error", "exception", "debugging", "crash", "stacktrace", "failure"],
        "logische_anfrage": ["bedingung", "logik", "berechnen", "vergleichen", "auswerten", "algorithmus", "verständnis"],
        "python_domain": ["python", "script", "code", "function", "variables", "data", "science"]
    }

    # Schwellenwert für TF-IDF Ähnlichkeitsanalyse
    TFIDF_SIMILARITY_THRESHOLD = 0.15

    # Ob fehlende Dependencies automatisch installiert werden sollen
    AUTO_INSTALL_DEPENDENCIES = True

    # Text-Limits
    TASK_DESCRIPTION_MAX_LEN = 200
    CODE_SNIPPET_PREVIEW_LEN = 150
    QUERY_TITLE_MAX_LEN = 35

    # Blueprint/Manifest-Limits
    MAX_BLUEPRINT_STEPS = 5
    MAX_DOMAIN_NODES = 3
    MAX_MANIFEST_ENTRIES = 5

    # METHODEN
    @staticmethod
    def initialize_blueprint_system(user_input: str) -> dict:
        """
        Initialisiert das Blueprint-System für die Anforderung mit integrierter Gegenkontrolle.
        Meldet jeden Fehler sofort und bricht kontrolliert ab.
        """
        try:
            if not user_input or not isinstance(user_input, str) or not user_input.strip():
                raise ValueError("Die Benutzereingabe für das Blueprint-System ist leer oder ungültig.")
            print(f"[BLUEPRINT] Initialisiere Blueprint-System für Anfrage...")
            return {"status": "INITIALIZED", "query": user_input.strip()}
            
        except Exception as e:
            error_message = f"[FEHLER IN initialize_blueprint_system] Konnte das System nicht initialisieren: {str(e)}"
            print(error_message)
            return {
                "status": "FAILED",
                "query": user_input,
                "error": error_message
            }

    def get_cached_or_create_query(self, raw_query: str) -> dict:
        """Prüft den Cache oder registriert eine neue Anfrage mit detaillierter Gegenkontrolle."""
        if not raw_query or not isinstance(raw_query, str):
            print("[GEGENKONTROLLE FEHLER] Ungültige oder leere raw_query übergeben.")
            return {"cache_hit": False, "status": "FAILED", "error": "Ungültige Eingabe"}
        cleaned_query = raw_query.strip().lower()
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # SCHRITT 1: Cache-Abfrage in der bestehenden Tabelle
                try:
                    cursor.execute("""
                        SELECT node_id, topic_title, topic_specification, agent_instruction, example_code_snippet, validation_rule
                        FROM user_query
                        WHERE TRIM(LOWER(topic_specification)) = ? AND is_active = 1
                        ORDER BY node_id DESC LIMIT 1
                    """, (cleaned_query,))
                    cached = cursor.fetchone()
                except sqlite3.Error as db_err:
                    print(f"[GEGENKONTROLLE FEHLER] SELECT-Abfrage auf Tabelle 'user_query' fehlgeschlagen: {db_err}")
                    raise
                
                # SCHRITT 2: Cache-Treffer verarbeiten
                if cached and cached[3] and cached[3] != "PROCESSING" and cached[5] == "COMPLETED_CACHE_READY":
                    try:
                        cursor.execute("UPDATE user_query SET execution_count = execution_count + 1 WHERE node_id = ?", (cached[0],))
                        conn.commit()
                    except sqlite3.Error as db_err:
                        print(f"[GEGENKONTROLLE FEHLER] UPDATE des execution_count für Node {cached[0]} fehlgeschlagen: {db_err}")
                        raise
                    return {
                        "cache_hit": True,
                        "node_id": cached[0],
                        "title": cached[1],
                        "query": cached[2],
                        "response": cached[3],
                        "snippet": cached[4]
                    }
                
                # SCHRITT 3: Bestehende IDs auslesen für neuen Node
                try:
                    cursor.execute("SELECT node_id FROM user_query")
                    existing_ids = {int(row[0]) for row in cursor.fetchall() if row[0].isdigit()}
                except sqlite3.Error as db_err:
                    print(f"[GEGENKONTROLLE FEHLER] Auslesen der node_ids aus 'user_query' fehlgeschlagen: {db_err}")
                    raise
                next_id_num = next((c for c in range(3, 999) if c not in existing_ids), 998)
                next_node_id = f"{next_id_num:03d}"
                
                # SCHRITT 4: Neuen Routing-Knoten einfügen
                try:
                    self._insert_routing_node(
                        conn=conn,
                        table_name="user_query",
                        node_id=next_node_id,
                        topic_title=f"USER QUERY: {raw_query[:self.QUERY_TITLE_MAX_LEN]}",
                        topic_specification=raw_query,
                        agent_instruction="PROCESSING",
                        example_code_snippet="",
                        validation_rule="PENDING_EXECUTION",
                        target_table="pre_execution_blueprint_generator"
                    )
                except Exception as ins_err:
                    print(f"[GEGENKONTROLLE FEHLER] Einfügen des Routing-Knotens ({next_node_id}) fehlgeschlagen: {ins_err}")
                    raise
                return {
                    "cache_hit": False,
                    "node_id": next_node_id,
                    "query": raw_query,
                    "status": "PENDING_EXECUTION"
                }
        except Exception as e:
            error_message = f"[KRITISCHER ABBRUCH IN get_cached_or_create_query]: {str(e)}"
            print(error_message)
            return {
                "cache_hit": False,
                "status": "FAILED",
                "error": error_message
            }

    def store_query_result(self, node_id: str, answer: str, snippet: str = ""):
        """Versiegelt eine erfolgreich beantwortete Anfrage im Cache mit integrierter Gegenkontrolle."""
        if not node_id:
            print("[GEGENKONTROLLE FEHLER] store_query_result aufgerufen ohne gültige node_id.")
            return
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE user_query
                    SET agent_instruction = ?,
                        example_code_snippet = ?,
                        validation_rule = 'COMPLETED_CACHE_READY',
                        is_active = 1
                    WHERE node_id = ?
                """, (answer, snippet, node_id))
                if cursor.rowcount == 0:
                    print(f"[GEGENKONTROLLE WARNUNG] Keine Zeile mit node_id '{node_id}' in 'user_query' gefunden, die aktualisiert werden konnte.")
                conn.commit()
                print(f"[SQL-CACHE] Anfrage mit node_id '{node_id}' erfolgreich im Cache versiegelt.")
        except sqlite3.Error as db_err:
            print(f"[GEGENKONTROLLE FEHLER] Datenbankfehler beim Versiegeln des Cache-Ergebnisses für node_id '{node_id}': {db_err}")
        except Exception as e:
            print(f"[KRITISCHER FEHLER IN store_query_result] Unerwarteter Fehler: {str(e)}")

    # LOG & PROTOCOL
    def log_save_query_run_to_db_timestamp(self, task_description: str, error_msg: str, solution_code: str, run_id: str = None):
        """
        Protokolliert Mikroschritte und holt den verbindlichen Zeitstempel direkt aus der Datenbank; 
        steuert die fortlaufende Append-Protokollierung und Crash-Wiederherstellung.
        """
        try:
            domain = self._detect_domain(task_description)
        except Exception as e:
            print(f"[GEGENKONTROLLE FEHLER] Domain-Erkennung fehlgeschlagen: {e}")
            domain = self.DEFAULT_DOMAIN

        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                # 1. Zeitstempel-Ermittlung aus der Datenbank absichern
                try:
                    if not run_id:
                        cursor.execute("""
                            SELECT year, month, day, hour, minute, second 
                            FROM user_query 
                            WHERE is_active = 1 
                            ORDER BY year DESC, month DESC, day DESC, hour DESC, minute DESC, second DESC 
                            LIMIT 1
                        """)
                        db_time = cursor.fetchone()
                        if db_time and all(db_time):
                            year, month, day, hour, minute, second = db_time
                            run_id = f"{year:04d}{month:02d}{day:02d}_{hour:02d}{minute:02d}{second:02d}"
                        else:
                            now = datetime.now()
                            year, month, day, hour, minute, second = now.year, now.month, now.day, now.hour, now.minute, now.second
                            run_id = now.strftime('%Y%m%d_%H%M%S')
                    else:
                        dt = datetime.strptime(run_id, '%Y%m%d_%H%M%S')
                        year, month, day, hour, minute, second = dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second
                except Exception as time_err:
                    print(f"[GEGENKONTROLLE FEHLER] Konnte Zeitstempel oder Run-ID nicht verarbeiten: {time_err}")
                    now = datetime.now()
                    year, month, day, hour, minute, second = now.year, now.month, now.day, now.hour, now.minute, now.second
                    run_id = now.strftime('%Y%m%d_%H%M%S')
                # Dynamischer Tabellenname
                dynamic_table_name = f"run_protocol_{run_id}"
                node_id = f"STEP_{hour:02d}{minute:02d}{second:02d}_{datetime.now().strftime('%f')}"
                
                # 2. Crash-Wiederherstellung & Status-Prüfung absichern
                try:
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (dynamic_table_name,))
                    table_already_exists = cursor.fetchone() is not None
                    if table_already_exists:
                        print(f"[RECOVERY] Tabelle '{dynamic_table_name}' existiert bereits. Setze fort mit echtem DB-Zeitstempel.")
                except sqlite3.Error as sqlite_err:
                    print(f"[GEGENKONTROLLE FEHLER] Überprüfung der Existenz von Tabelle '{dynamic_table_name}' fehlgeschlagen: {sqlite_err}")
                    raise

                # 3. Dynamische Tabelle erstellen absichern
                try:
                    cursor.execute(f"""
                        CREATE TABLE IF NOT EXISTS {dynamic_table_name} (
                            node_id TEXT PRIMARY KEY,
                            is_active INTEGER DEFAULT 1,
                            error_fallback_count INTEGER DEFAULT 0,
                            year INTEGER, month INTEGER, day INTEGER, hour INTEGER, minute INTEGER, second INTEGER,
                            topic_title TEXT,
                            topic_specification TEXT,
                            agent_instruction TEXT,
                            example_code_snippet TEXT,
                            validation_rule TEXT,
                            execution_count INTEGER DEFAULT 0,
                            success_weight REAL DEFAULT 1.0,
                            target_table TEXT,
                            target_column_id TEXT,
                            target_node_id TEXT
                        )
                    """)
                    conn.commit()
                except sqlite3.Error as sqlite_err:
                    print(f"[GEGENKONTROLLE FEHLER] Erstellen der dynamischen Tabelle '{dynamic_table_name}' fehlgeschlagen: {sqlite_err}")
                    raise

                # 4. Mikroschritt schreiben absichern
                max_len = self.TASK_DESCRIPTION_MAX_LEN
                step_title = f"Step in [{domain}]"
                if table_already_exists:
                    step_title += " (Resumed)"
                try:
                    self._insert_routing_node(
                        conn=conn,
                        table_name=dynamic_table_name,
                        node_id=node_id,
                        topic_title=step_title,
                        topic_specification=task_description[:max_len],
                        agent_instruction=error_msg.strip().split('\n')[-1][:max_len] if error_msg else "RUN_STEP_SUCCESS",
                        example_code_snippet=solution_code,
                        validation_rule="step_logged == TRUE",
                        target_table=domain
                    )
                except Exception as insert_err:
                    print(f"[GEGENKONTROLLE FEHLER] Einfügen des Routing-Knotens in '{dynamic_table_name}' fehlgeschlagen: {insert_err}")
                    raise

                # 5. Exakte Zeitstempel-Werte in den Datensatz schreiben absichern
                try:
                    cursor.execute(f"""
                        UPDATE {dynamic_table_name}
                        SET year = ?, month = ?, day = ?, hour = ?, minute = ?, second = ?
                        WHERE node_id = ?
                    """, (year, month, day, hour, minute, second, node_id))
                    conn.commit()
                except sqlite3.Error as sqlite_err:
                    print(f"[GEGENKONTROLLE FEHLER] Aktualisieren der Zeitstempel-Daten in '{dynamic_table_name}' fehlgeschlagen: {sqlite_err}")
                    raise
            print(f"[SQL-KNOWLEDGE] Protokollschritt mit DB-Zeitstempel in '{dynamic_table_name}' verankert.")
        except Exception as e:
            print(f"[KRITISCHER ABBRUCH IN log_save_query_run_to_db_timestamp]: {str(e)}")

    def _detect_domain(self, task_description: str) -> str:
        """
        Erkennt anhand einer zentralen Definition (Heuristik & optionalem TF-IDF) die relevante Zieltabelle/Domain.
        Nutzt konfigurierbare Klassenattribute DOMAIN_KEYWORDS, TFIDF_SIMILARITY_THRESHOLD, DEFAULT_DOMAIN.
        """
        import importlib.util

        if not task_description or not isinstance(task_description, str) or not task_description.strip():
            print(f"[GEGENKONTROLLE WARNUNG] task_description ist leer oder ungültig. Fallback auf '{self.DEFAULT_DOMAIN}'.")
            return self.DEFAULT_DOMAIN

        try:
            desc_lower = task_description.lower()
            
            # STUFE 1: Fast-Path Heuristik aus konfigurierbarem Domain-Mapping
            for domain, keywords in self.DOMAIN_KEYWORDS.items():
                if any(kw in desc_lower for kw in keywords[:5]):
                    return domain

            # STUFE 2: Optionale stochastische Vektor-Analyse (nur wenn sklearn verfügbar)
            sklearn_available = importlib.util.find_spec("sklearn") is not None
            numpy_available = importlib.util.find_spec("numpy") is not None

            if sklearn_available and numpy_available:
                try:
                    from sklearn.feature_extraction.text import TfidfVectorizer
                    from sklearn.metrics.pairwise import cosine_similarity
                    import numpy as np
                    domain_corpus = {domain: " ".join(words) for domain, words in self.DOMAIN_KEYWORDS.items()}
                    domain_keys = list(domain_corpus.keys())
                    
                    vectorizer = TfidfVectorizer()
                    tfidf_matrix = vectorizer.fit_transform(list(domain_corpus.values()))
                    task_vector = vectorizer.transform([task_description])
                    cosine_sim = cosine_similarity(task_vector, tfidf_matrix).flatten()
                    total_sim = np.sum(cosine_sim)
                    if total_sim > 0:
                        probabilities = cosine_sim / total_sim
                        best_idx = np.argmax(probabilities)
                        if probabilities[best_idx] >= self.TFIDF_SIMILARITY_THRESHOLD:
                            return domain_keys[best_idx]
                except Exception:
                    pass  # TF-IDF optional — bei Fehler einfach Fallback nutzen
            # STUFE 3: Standard-Fallback
            return self.DEFAULT_DOMAIN
        except Exception as e:
            print(f"[GEGENKONTROLLE FEHLER IN _detect_domain]: Unerwarteter Fehler bei der Domain-Erkennung: {str(e)}")
            return self.DEFAULT_DOMAIN

    def fetch_records(self, table_name: str, active_only: bool = True):
        """
        Liest alle Datensätze aus der angegebenen Tabelle aus mit integrierter Gegenkontrolle.
        """
        # Gegenkontrolle 1: Registry-Prüfung (erlaubt auch dynamische run_protocol Tabellen)
        if table_name not in self.ALLOWED_TABLES and not table_name.startswith("run_protocol_"):
            error_msg = f"Tabelle '{table_name}' ist nicht in der Registry zugelassen."
            print(f"[GEGENKONTROLLE FEHLER] {error_msg}")
            raise ValueError(error_msg)
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
                if not cursor.fetchone():
                    print(f"[GEGENKONTROLLE FEHLER] Tabelle '{table_name}' existiert physisch nicht in der Datenbank. Zugriff abgebrochen.")
                    return []
                if active_only:
                    query = f"SELECT * FROM {table_name} WHERE is_active = 1 ORDER BY year DESC, month DESC, day DESC, hour DESC, minute DESC, second DESC"
                else:
                    query = f"SELECT * FROM {table_name} ORDER BY year DESC, month DESC, day DESC, hour DESC, minute DESC, second DESC"
                cursor.execute(query)
                if not cursor.description:
                    print(f"[GEGENKONTROLLE WARNUNG] Abfrage auf Tabelle '{table_name}' lieferte keine Spaltenbeschreibungen.")
                    return []
                    
                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()
                result = [dict(zip(columns, row)) for row in rows]
                print(f"[SQL-SUCCESS] {len(result)} Datensätze erfolgreich aus '{table_name}' ausgelesen.")
                return result
                
        except sqlite3.Error as db_err:
            print(f"[GEGENKONTROLLE FEHLER] Datenbankfehler beim Auslesen der Tabelle '{table_name}': {db_err}")
            return []
        except Exception as e:
            print(f"[KRITISCHER ABBRUCH IN fetch_records]: {str(e)}")
            return []

    def fetch_single_node(self, table_name: str, node_id: str):
        """
        Liest einen spezifischen Knoten anhand seiner node_id aus.
        """
        if table_name not in self.ALLOWED_TABLES and not table_name.startswith("run_protocol_"):
            error_msg = f"Tabelle '{table_name}' ist unzulässig."
            print(f"[GEGENKONTROLLE FEHLER] {error_msg}")
            raise ValueError(error_msg)

        if not node_id:
            print("[GEGENKONTROLLE FEHLER] fetch_single_node aufgerufen ohne gültige node_id.")
            return None

        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
                if not cursor.fetchone():
                    print(f"[GEGENKONTROLLE FEHLER] Tabelle '{table_name}' existiert physisch nicht in der Datenbank.")
                    return None
                cursor.execute(f"SELECT * FROM {table_name} WHERE node_id = ?", (node_id,))
                row = cursor.fetchone()
                
                if row:
                    if not cursor.description:
                        print(f"[GEGENKONTROLLE WARNUNG] Abfrage auf Tabelle '{table_name}' lieferte keine Spaltenbeschreibungen.")
                        return None
                        
                    columns = [description[0] for description in cursor.description]
                    return dict(zip(columns, row))
                
                print(f"[GEGENKONTROLLE HINWEIS] Kein Datensatz mit node_id '{node_id}' in Tabelle '{table_name}' gefunden.")
                return None
                
        except sqlite3.Error as db_err:
            print(f"[GEGENKONTROLLE FEHLER] Datenbankfehler beim Auslesen von node_id '{node_id}' aus '{table_name}': {db_err}")
            return None
        except Exception as e:
            print(f"[KRITISCHER ABBRUCH IN fetch_single_node]: {str(e)}")
            return None

    def _insert_routing_node(self, conn, table_name: str, node_id: str, 
                               topic_title: str = "", topic_specification: str = "", 
                               agent_instruction: str = "", example_code_snippet: str = "", 
                               validation_rule: str = "", target_table: str = "", 
                               target_node_id: str = "000", **kwargs):
        """
        Fügt einen neuen Knoten minimal, performant und dynamisch anhand des Live-Schemas ein.
        integrierter Gegenkontrolle und Fehlerabsicherung.
        """
        if not conn:
            print("[GEGENKONTROLLE FEHLER] Keine gültige Datenbankverbindung (conn) an _insert_routing_node übergeben.")
            raise ValueError("Ungültige Datenbankverbindung")

        if not table_name or not node_id:
            error_msg = f"table_name ('{table_name}') oder node_id ('{node_id}') fehlt."
            print(f"[GEGENKONTROLLE FEHLER] {error_msg}")
            raise ValueError(error_msg)

        try:
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({table_name})")
            actual_columns = {row[1] for row in cursor.fetchall()}
            
            if not actual_columns:
                error_msg = f"Tabelle '{table_name}' existiert physisch nicht oder ist leer."
                print(f"[GEGENKONTROLLE FEHLER] {error_msg}")
                raise ValueError(error_msg)

            now = datetime.now()
            
            payload = {
                "node_id": node_id,
                "is_active": 1,
                "error_fallback_count": 0,
                "year": now.year, "month": now.month, "day": now.day,
                "hour": now.hour, "minute": now.minute, "second": now.second,
                "topic_title": topic_title,
                "topic_specification": topic_specification,
                "agent_instruction": agent_instruction,
                "example_code_snippet": example_code_snippet,
                "validation_rule": validation_rule,
                "execution_count": 1,
                "success_weight": 1.0,
                "target_table": target_table,
                "target_column_id": "node_id",
                "target_node_id": target_node_id,
                **kwargs
            }
            
            # Dynamischer Abgleich: Nur Spalten verwenden, die die Live-Tabelle aktuell besitzt
            filtered_data = {k: v for k, v in payload.items() if k in actual_columns}
            
            cols = ", ".join(filtered_data.keys())
            placeholders = ", ".join(["?"] * len(filtered_data))
            
            cursor.execute(
                f"INSERT OR REPLACE INTO {table_name} ({cols}) VALUES ({placeholders})", 
                list(filtered_data.values())
            )
            conn.commit()
            print(f"[SQL-SUCCESS] Knoten '{node_id}' erfolgreich in Tabelle '{table_name}' verankert.")

        except sqlite3.Error as sqlite_err:
            print(f"[GEGENKONTROLLE FEHLER] SQLite-Fehler beim Insert in Tabelle '{table_name}' (node_id: {node_id}): {sqlite_err}")
            raise
        except Exception as e:
            print(f"[KRITISCHER ABBRUCH IN _insert_routing_node]: {str(e)}")
            raise

    def deactivate_and_reroute(self, table_name: str, node_id: str, failure_reason: str) -> dict:
        """
        Deaktiviert fehlerhafte Knoten und leitet auf Alternativpfade um.
        """
        if table_name not in self.ALLOWED_TABLES and not table_name.startswith("run_protocol_"):
            error_msg = f"Tabelle '{table_name}' ist unzulässig für Rerouting."
            print(f"[GEGENKONTROLLE FEHLER] {error_msg}")
            raise ValueError(error_msg)

        if not node_id:
            print("[GEGENKONTROLLE FEHLER] deactivate_and_reroute aufgerufen ohne gültige node_id.")
            return {
                "deactivated_node": "UNKNOWN",
                "table_name": table_name,
                "reason": failure_reason,
                "alternative_available": False,
                "next_node": "000",
                "next_target": "FX_CHAIN"
            }

        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
                if not cursor.fetchone():
                    print(f"[GEGENKONTROLLE FEHLER] Tabelle '{table_name}' existiert physisch nicht in der Datenbank.")
                    raise ValueError(f"Tabelle '{table_name}' nicht gefunden.")

                cursor.execute(f"""
                    UPDATE {table_name}
                    SET is_active = 0, error_fallback_count = error_fallback_count + 1
                    WHERE node_id = ?
                """, (node_id,))
                
                if cursor.rowcount == 0:
                    print(f"[GEGENKONTROLLE WARNUNG] Node '{node_id}' in Tabelle '{table_name}' konnte nicht deaktiviert werden (nicht gefunden).")
                
                cursor.execute(f"""
                    SELECT node_id, topic_title, target_table, target_node_id
                    FROM {table_name}
                    WHERE is_active = 1 AND node_id != ?
                    ORDER BY success_weight DESC LIMIT 1
                """, (node_id,))
                alt_row = cursor.fetchone()
                
                conn.commit()
                print(f"[SQL-SUCCESS] Node '{node_id}' in '{table_name}' deaktiviert. Grund: {failure_reason}")
                
                return {
                    "deactivated_node": node_id,
                    "table_name": table_name,
                    "reason": failure_reason,
                    "alternative_available": alt_row is not None,
                    "next_node": alt_row[0] if alt_row else "000",
                    "next_target": alt_row[2] if alt_row and alt_row[2] else "FX_CHAIN"
                }

        except sqlite3.Error as db_err:
            print(f"[GEGENKONTROLLE FEHLER] Datenbankfehler beim Rerouting für node_id '{node_id}' in '{table_name}': {db_err}")
            return {
                "deactivated_node": node_id,
                "table_name": table_name,
                "reason": f"DB_ERROR: {str(db_err)}",
                "alternative_available": False,
                "next_node": "000",
                "next_target": "FX_CHAIN"
            }
        except Exception as e:
            print(f"[KRITISCHER ABBRUCH IN deactivate_and_reroute]: {str(e)}")
            return {
                "deactivated_node": node_id,
                "table_name": table_name,
                "reason": f"CRITICAL_ERROR: {str(e)}",
                "alternative_available": False,
                "next_node": "000",
                "next_target": "FX_CHAIN"
            }