import os
import sqlite3
import sys
from pathlib import Path

# 1. Hauptverzeichnis zum Python-Pfad hinzufügen
sys.path.append(str(Path(__file__).resolve().parent))

# 2. Auto-Bootstrap & globale Registrierung
from agent_universal_skript.auto_bootstrap_and_register_agent_tools import auto_bootstrap_and_register_agent_tools
auto_bootstrap_and_register_agent_tools()

# 3. Zentrale globale Aliase mit sicherer Fallback-Logik (Defaults) direkt nach Bootstrap
logger = globals().get('class_logger_audit_execution')

# GLOBALE STANDARD-KONFIGURATION
PROJECT_POINT = "src"


class class_tool_core_infrastructure:
    """
    Zentrale Basis-Infrastruktur für alle zukünftigen Agenten und Tools.
    Ermittelt das Projekt-Hauptverzeichnis rein dynamisch über das Auffinden des 'PROJECT_POINT'-Ordners.
    Keine agenten-spezifischen Begriffe oder Domains — rein technische Infrastruktur.
    """

    # Ollama-Verifizierungsstatus als Klassenattribut (statt global)
    _ollama_verified = False

    @classmethod
    def get_project_root(cls, start_path=None) -> Path:
        """
        Sucht heuristisch im Verzeichnisbaum nach oben, bis ein Projekt-Root
        (definiert durch das Vorhandensein eines 'PROJECT_POINT'-Ordners) gefunden wird.
        """
        if start_path is None:
            file_path = Path(__file__).resolve()
        else:
            file_path = Path(start_path).resolve()

        current = file_path if file_path.is_dir() else file_path.parent
        try:
            for parent in [current] + list(current.parents):
                if parent.name.lower() == cls.PROJECT_POINT.lower():
                    return parent.parent
                if (parent / cls.PROJECT_POINT).is_dir():
                    return parent
        except Exception as e:
            print(f"[KRITISCHER FEHLER] Konnte Ankerpunkt nicht finden: {e}")
        return current
    
    @classmethod
    def get_file_path(cls, filename: str) -> Path:
        """
        Sucht universell nach einer beliebigen Datei im Projektverzeichnis,
        ausgehend vom automatischen Projekt-Root, und bricht bei Nichtfinden ab.
        """
        base_root = cls.get_project_root()
        fn_lower = filename.lower()

        for path in base_root.rglob("*"):
            if path.is_file() and path.name.lower() == fn_lower:
                return path

        raise FileNotFoundError(
            f"[KRITISCHER FEHLER] Die Datei '{filename}' wurde ausgehend vom Root '{base_root}' nicht gefunden!"
        )
    
    @staticmethod
    def scan_kernel_modules(required_modules: list) -> dict:
        """Prüft die Verfügbarkeit von Python-Modulen und Systemressourcen."""
        status = {}
        for mod in required_modules:
            try:
                __import__(mod)
                status[mod] = "active"
            except ImportError:
                status[mod] = "missing"
        return status

    @classmethod
    def get_db_connection(cls, filename: str) -> sqlite3.Connection:
        """
        Öffnet eine robuste Verbindung zur übergebenen SQLite-Datenbank.
        Erfordert expliziten Dateinamen — kein Hardcoded-Default.
        """
        db_path = cls.get_file_path(filename)
        posix_path = db_path.resolve().as_posix()
        uri_path = f"file:///{posix_path}?mode=rw" if posix_path.startswith("/") else f"file:{posix_path}?mode=rw"
        try:
            conn = sqlite3.connect(uri_path, uri=True)
        except sqlite3.OperationalError:
            conn = sqlite3.connect(str(db_path))
        return conn

    @classmethod
    def load_optional_ollama_checker(cls) -> bool:
        """Prüft optional, ob Ollama erreichbar ist (mit Guard-Import)."""
        if cls._ollama_verified:
            return True
        try:
            from ollama import Client
            client = Client()
            client.list()
            cls._ollama_verified = True
            return True
        except ImportError:
            print("[OLLAMA WARNUNG] Das Paket 'ollama' ist nicht installiert.")
            return False
        except Exception as e:
            print(f"[OLLAMA WARNUNG] Konnte keine Verbindung zu Ollama herstellen: {e}")
            return False