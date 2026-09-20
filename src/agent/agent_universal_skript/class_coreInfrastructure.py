import os
import sqlite3
from pathlib import Path

class coreInfrastructure:
    """
    Zentrale Basis-Infrastruktur für alle zukünftigen Agenten und Tools.
    Ermittelt das Projekt-Hauptverzeichnis rein dynamisch über das Auffinden des 'PROJECT_POINT'-Ordners.
    """
    PROJECT_POINT = "src"

    @classmethod
    def get_project_root(cls, start_path: PROJECT_POINT) -> Path:
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
                # Prüfen, ob der Ordner selbst den Namen von PROJECT_POINT hat
                if parent.name.lower() == cls.PROJECT_POINT.lower():
                    return parent.parent
                
                # Prüfen, ob der Ordner ein PROJECT_POINT-Unterverzeichnis enthält
                if (parent / cls.PROJECT_POINT).is_dir():
                    return parent
                    
        except Exception as e:
            print(f"[KRITISCHER FEHLER] Konnte Ankerpunkt nicht finden: {e}")

        # Letzter Fallback, falls kein PROJECT_POINT im ganzen Baum existiert
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
            f"[KRITISCHER FEHLER] Die Datei '{filename}' wurde ausgehend vom Root '{base_root}' "
            f"im gesamten Projektverzeichnis nicht gefunden!"
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
        Öffnet eine robuste Verbindung zu einer beliebigen, übergebenen SQLite-Datenbank.
        Der konkrete Dateiname wird dynamisch vom jeweiligen Agenten vorgegeben.
        """
        db_path = cls.get_file_path(filename)
        posix_path = db_path.resolve().as_posix()
        uri_path = f"file:///{posix_path}?mode=rw" if posix_path.startswith("/") else f"file:{posix_path}?mode=rw"
        try:
            conn = sqlite3.connect(uri_path, uri=True)
        except sqlite3.OperationalError:
            conn = sqlite3.connect(str(db_path))
        return conn

    def _get_relevant_tips(self, task_description: str) -> str:
        """Lädt kontextbezogene Richtlinien und Knoten aus dem Routing Tree."""
        domain = self._detect_domain(task_description)
        tips = (" [SYSTEM CORE MEMORY: KNOWLEDGE AGENT ROUTING TREE]")

        with self.get_db_connection() as conn:
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

        if len(tips) <= 3:
            return f"No prior routing tree nodes recorded for domain [{domain}]."
        return "\n".join(tips)

    @staticmethod
    def load_optional_ollama_checker() -> bool:
        """Prüft optional, ob Ollama erreichbar ist."""
        global _OLLAMA_VERIFIED_CACHE
        if _OLLAMA_VERIFIED_CACHE:
            return True
        try:
            client = Client()
            client.list()
            _OLLAMA_VERIFIED_CACHE = True
            return True
        except Exception as e:
            print(f"[OLLAMA WARNUNG] Konnte keine Verbindung zu Ollama herstellen: {e}")
            return False

globals()['coreInfrastructure'] = coreInfrastructure