"""
Modul: class_tool_core_infrastructure
Bezeichnung: Zentrale Basis-Infrastruktur für Agenten und Werkzeuge
Inhaltlicher Schwerpunkt:
Ermittlung des Projekt-Root-Verzeichnisses, globale Dateipfadauflösung,
manipulationssichere Knowledge-Datenbankpfad-Auflösung, Kernel-Modul-Prüfung
und Bereitstellung robuster SQLite-Datenbankverbindungen.
"""

import os
import sqlite3
import sys
from pathlib import Path
from typing import Optional, List, Dict

# Globale Bindings
logger = globals().get("class_logger_audit_execution")


class class_tool_core_infrastructure:
    """
    Zentrale Basis-Infrastruktur für alle Agenten und Werkzeuge.
    Stellt Pfadfindungs-, Datei-, Modul- und Datenbankdienste agenten-agnostisch bereit.
    """

    _cfg = globals().setdefault("_AGENT_CONFIG", {})
    PROJECT_POINT: str = _cfg.setdefault("PROJECT_POINT", "src")
    _ollama_verified: bool = False

    @classmethod
    def get_project_root(cls, start_path=None) -> Path:
        """Ermittelt heuristisch das Projekt-Wurzelverzeichnis über das Verzeichnis PROJECT_POINT."""
        print("[class_tool_core_infrastructure] Starte Arbeit: get_project_root wird jetzt ausgeführt.")
        try:
            file_path = Path(start_path).resolve() if start_path else Path(__file__).resolve()
            current = file_path if file_path.is_dir() else file_path.parent
            for parent in [current] + list(current.parents):
                if parent.name.lower() == cls.PROJECT_POINT.lower():
                    result = parent.parent
                    print("[class_tool_core_infrastructure] Erfolg: get_project_root erfolgreich beendet.")
                    return result
                if (parent / cls.PROJECT_POINT).is_dir():
                    result = parent
                    print("[class_tool_core_infrastructure] Erfolg: get_project_root erfolgreich beendet.")
                    return result
            result = current
            print("[class_tool_core_infrastructure] Erfolg: get_project_root erfolgreich beendet.")
            return result
        except Exception as e:
            print(f"[class_tool_core_infrastructure] FEHLER: Konnte Ankerpunkt nicht finden: {e}")
            return Path.cwd()

    @classmethod
    def get_database_path(cls, filename: str = None) -> Path:
        """
        Löst den absoluten, manipulationssicheren Pfad zur Knowledge-Datenbank auf.
        Prüft definierte kanonische Pfade in 'knowledge/' und verhindert verwaiste DBs in Quellcode-Ordnern.
        """
        print(f"[class_tool_core_infrastructure] Starte Arbeit: get_database_path wird jetzt ausgeführt. (Parameter: {filename})")
        root = cls.get_project_root()
        target_name = (filename or "agent_hierarchical_routing_tree_sql.db").replace("\\", "/")

        # 1. Direkter absoluter Pfad
        if Path(target_name).is_absolute() and Path(target_name).exists():
            print(f"[class_tool_core_infrastructure] Erfolg: get_database_path erfolgreich beendet. (Absolut: {target_name})")
            return Path(target_name)

        # 2. Kanonische Wissensdatenbank-Pfade prüfen
        base_name = Path(target_name).name.lower()
        candidates = [
            root / target_name,
            root / "knowledge" / "agent_hierarchical_routing_tree_sql.db",
            root / "knowledge" / "knowledge_agent_hierarchical_routing_tree_sql" / "knowledge_agent_routing_tree.db",
            root / "Knowledge" / "agent_hierarchical_routing_tree_sql.db",
            root / "knowledge" / "meta_coder_base" / "meta_coder_base_issue_solution.db" if "meta_coder_base" in base_name else None,
        ]

        if "routing_tree" in base_name or "knowledge" in base_name or "sql" in base_name:
            candidates.insert(0, root / "knowledge" / "agent_hierarchical_routing_tree_sql.db")
            candidates.insert(1, root / "knowledge" / "knowledge_agent_hierarchical_routing_tree_sql" / "knowledge_agent_routing_tree.db")

        for c in filter(None, candidates):
            if c.is_file() and c.exists() and c.stat().st_size > 0:
                print(f"[class_tool_core_infrastructure] Erfolg: get_database_path erfolgreich beendet. (Gefunden: {c})")
                return c

        # 3. Rekursive Suche im knowledge/-Verzeichnis
        knowledge_dir = root / "knowledge"
        if knowledge_dir.exists():
            for p in knowledge_dir.rglob("*.db"):
                if p.is_file() and (p.name.lower() == base_name or "routing_tree" in p.name.lower()):
                    print(f"[class_tool_core_infrastructure] Erfolg: get_database_path erfolgreich beendet. (Knowledge-Scan: {p})")
                    return p

        # 4. Fallback über get_file_path
        res = cls.get_file_path(Path(target_name).name)
        if res and res.is_file():
            print(f"[class_tool_core_infrastructure] Erfolg: get_database_path erfolgreich beendet. (Gefunden: {res})")
            return res

        # 5. Geordneter Fallback im knowledge-Ordner anlegen (niemals im Quellcode-Ordner!)
        fallback = root / "knowledge" / "agent_hierarchical_routing_tree_sql.db"
        fallback.parent.mkdir(parents=True, exist_ok=True)
        print(f"[class_tool_core_infrastructure] Erfolg: get_database_path erfolgreich beendet. (Kanonischer Pfad: {fallback})")
        return fallback

    @classmethod
    def get_file_path(cls, filename: str) -> Path:
        """Sucht fehlertolerant und manipulationssicher nach einer Datei ausgehend vom Projekt-Root."""
        print(f"[class_tool_core_infrastructure] Starte Arbeit: get_file_path wird jetzt ausgeführt. (Parameter: {filename})")
        try:
            target_path = Path(filename)
            if target_path.is_absolute() and target_path.exists():
                print("[class_tool_core_infrastructure] Erfolg: get_file_path erfolgreich beendet. (Direkter Pfad)")
                return target_path

            base_root = cls.get_project_root()
            direct = base_root / filename
            if direct.exists() and direct.is_file():
                print("[class_tool_core_infrastructure] Erfolg: get_file_path erfolgreich beendet. (Relativ zum Root)")
                return direct

            # Wissensdatenbank-Spezialbehandlung
            fn_lower = target_path.name.lower()
            if fn_lower.endswith(".db"):
                if "routing_tree" in fn_lower or "knowledge" in fn_lower or "sql" in fn_lower:
                    return cls.get_database_path(filename)

            # Rekursive Suche
            for path in base_root.rglob("*"):
                if path.is_file() and path.name.lower() == fn_lower:
                    print(f"[class_tool_core_infrastructure] Erfolg: get_file_path erfolgreich beendet. (Gefunden: {path})")
                    return path

            print(f"[class_tool_core_infrastructure] FEHLER: get_file_path hat die Aufgabe nicht erfüllt. Grund: Datei '{filename}' nicht gefunden.")
            return None
        except Exception as e:
            print(f"[class_tool_core_infrastructure] FEHLER: get_file_path hat die Aufgabe nicht erfüllt. Grund: {e}")
            return None

    @staticmethod
    def scan_kernel_modules(required_modules: list) -> dict:
        """Prüft die Verfügbarkeit angeforderter Python-Module."""
        print("[class_tool_core_infrastructure] Starte Arbeit: scan_kernel_modules wird jetzt ausgeführt.")
        status = {}
        for mod in required_modules:
            try:
                __import__(mod)
                status[mod] = "active"
            except ImportError:
                status[mod] = "missing"
        result = status
        if result is None:
            print("[class_tool_core_infrastructure] FEHLER: scan_kernel_modules hat die Aufgabe nicht erfüllt. Grund: Rückgabe ist None")
            return {}
        print("[class_tool_core_infrastructure] Erfolg: scan_kernel_modules erfolgreich beendet.")
        return result

    @classmethod
    def get_db_connection(cls, filename: str = None) -> sqlite3.Connection:
        """Öffnet eine sichere Verbindung zu einer SQLite-Datenbank im Projekt."""
        print(f"[class_tool_core_infrastructure] Starte Arbeit: get_db_connection wird jetzt ausgeführt. (Parameter: {filename})")
        try:
            db_path = cls.get_database_path(filename) if (filename and filename.endswith(".db")) else (cls.get_file_path(filename) if filename else cls.get_database_path())
            if not db_path:
                print(f"[class_tool_core_infrastructure] FEHLER: get_db_connection hat die Aufgabe nicht erfüllt. Grund: Datenbankdatei '{filename}' existiert nicht.")
                return None
            posix_path = db_path.resolve().as_posix()
            uri_path = f"file:///{posix_path}?mode=rw" if posix_path.startswith("/") else f"file:{posix_path}?mode=rw"
            try:
                conn = sqlite3.connect(uri_path, uri=True)
            except sqlite3.OperationalError:
                conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            print(f"[class_tool_core_infrastructure] Erfolg: get_db_connection erfolgreich beendet. (Verbunden mit: {db_path})")
            return conn
        except Exception as e:
            print(f"[class_tool_core_infrastructure] FEHLER: get_db_connection hat die Aufgabe nicht erfüllt. Grund: {e}")
            return None

    @classmethod
    def load_optional_ollama_checker(cls) -> bool:
        """Prüft, ob der Ollama-Dienst lokal erreichbar ist."""
        print("[class_tool_core_infrastructure] Starte Arbeit: load_optional_ollama_checker wird jetzt ausgeführt.")
        if cls._ollama_verified:
            print("[class_tool_core_infrastructure] Erfolg: load_optional_ollama_checker erfolgreich beendet.")
            return True
        try:
            from ollama import Client
            client = Client()
            client.list()
            cls._ollama_verified = True
            print("[class_tool_core_infrastructure] Erfolg: load_optional_ollama_checker erfolgreich beendet.")
            return True
        except ImportError:
            print("[class_tool_core_infrastructure] FEHLER: Paket 'ollama' ist nicht installiert.")
            return False
        except Exception as e:
            print(f"[class_tool_core_infrastructure] FEHLER: Keine Verbindung zu Ollama: {e}")
            return False

    @classmethod
    def run_core_infrastructure(cls, required_modules: list = None, db_filename: str = None) -> dict:
        """
        Zentrale Ausführungsfunktion: Koordiniert und initialisiert die Basisinfrastruktur
        (Root-Ermittlung, Kernel-Modul-Check und optionale DB-Verbindung).
        """
        print("[class_tool_core_infrastructure] Starte Arbeit: run_core_infrastructure wird jetzt ausgeführt.")
        try:
            root = cls.get_project_root()
            module_status = cls.scan_kernel_modules(required_modules or ["sqlite3", "os", "sys"])
            db_conn = cls.get_db_connection(db_filename) if db_filename else None
            result = {
                "project_root": root,
                "module_status": module_status,
                "db_connected": db_conn is not None,
                "db_connection": db_conn
            }
            if result is None:
                print("[class_tool_core_infrastructure] FEHLER: run_core_infrastructure hat die Aufgabe nicht erfüllt. Grund: Rückgabe ist None")
                return {}
            print("[class_tool_core_infrastructure] Erfolg: run_core_infrastructure erfolgreich beendet.")
            return result
        except Exception as e:
            print(f"[class_tool_core_infrastructure] FEHLER: In run_core_infrastructure: {e}")
            return None
