import os
import sqlite3
from pathlib import Path


class coreInfrastructure:
    """
    Zentrale Basis-Infrastruktur für alle zukünftigen Agenten und Tools.
    Ermittelt das Projekt-Hauptverzeichnis rein dynamisch über das Auffinden des 'PROJECT_POINT'-Ordners.
    Keine agenten-spezifischen Begriffe oder Domains — rein technische Infrastruktur.
    """
    PROJECT_POINT = "src"

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

    def _detect_domain(self, task_description: str) -> str:
        """Hilfsmethode zur Erkennung der SQL-Tabelle basierend auf der Aufgabe."""
        # Fallback falls die Methode im Original fehlte
        return "app_standards"

    def _get_relevant_tips(self, task_description: str) -> str:
        """Lädt kontextbezogene Richtlinien und Knoten aus dem Routing Tree."""
        domain = self._detect_domain(task_description)
        
        # FIX 1: Als Liste initialisieren, damit .append() funktioniert
        tips = ["[SYSTEM CORE MEMORY: KNOWLEDGE AGENT ROUTING TREE]"]

        # FIX 2: Standard-Datenbanknamen übergeben, damit kein TypeError geworfen wird
        with self.get_db_connection("app_standards.db") as conn:
            cursor = conn.cursor()

            try:
                cursor.execute("SELECT directive_key, explanation_for_agent FROM agent_system_manifest LIMIT 5")
                manifest_rows = cursor.fetchall()
            except sqlite3.OperationalError:
                manifest_rows = []

            try:
                words = [w for w in task_description.lower().split() if len(w) > 3]
                domain_rows = []
                if words:
                    placeholders = " OR ".join(["topic_title LIKE ? OR topic_specification LIKE ? OR agent_instruction LIKE ?"] * len(words))
                    params = []
                    for w in words:
                        pattern = f"%{w}%"
                        params.extend([pattern, pattern, pattern])
                    cursor.execute(
                        f"SELECT node_id, topic_title, agent_instruction, example_code_snippet FROM {domain} "
                        f"WHERE is_active = 1 AND ({placeholders}) ORDER BY success_weight DESC LIMIT 3",
                        params
                    )
                    domain_rows = cursor.fetchall()

                if not domain_rows:
                    cursor.execute(
                        f"SELECT node_id, topic_title, agent_instruction, example_code_snippet FROM {domain} "
                        f"WHERE is_active = 1 ORDER BY success_weight DESC LIMIT 3"
                    )
                    domain_rows = cursor.fetchall()
            except sqlite3.OperationalError:
                domain_rows = []

            try:
                cursor.execute(
                    "SELECT node_id, topic_title, agent_instruction FROM pre_execution_blueprint_generator "
                    "WHERE is_active = 1 ORDER BY node_id ASC LIMIT 5"
                )
                blueprints = cursor.fetchall()
            except sqlite3.OperationalError:
                blueprints = []

        if manifest_rows:
            tips.append("\n--- Agent System Manifest & Core Directives ---")
            for key, exp in manifest_rows:
                tips.append(f"• [{key}]: {exp}")

        if domain_rows:
            tips.append(f"\n--- Relevant Nodes from Domain [{domain}] ---")
            for node_id, title, instruction, snippet in domain_rows:
                tips.append(f"• Node [{node_id}] {title}: {instruction}")
                if snippet and snippet.strip() and not snippet.startswith("# FX_"):
                    tips.append(f"  Code Snippet: {snippet.strip()[:150]}...")

        if blueprints:
            tips.append("\n--- Mandatory Pre-Execution Blueprints ---")
            for node_id, title, instruction in blueprints:
                tips.append(f"• Step [{node_id}] {title}: {instruction}")

        if len(tips) <= 5:
            return f"No prior routing tree nodes recorded for domain [{domain}]."
        return "\n".join(tips)


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

globals()['coreInfrastructure'] = coreInfrastructure