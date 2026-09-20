import os
import sqlite3
from pathlib import Path

class coreInfrastructure:
    """
    Zentrale Basis-Infrastruktur für alle zukünftigen Agenten und Tools.
    Ermittelt das Projekt-Hauptverzeichnis rein dynamisch über das Auffinden des 'src'-Ordners.
    """
    
    BASE_DIR = "Knowledge"
    SUBFOLDER = "Knowledge_Agent_Hierarchical_Routing_Tree_SQL"
    DB_FILENAME = "Knowledge_Agent_Routing_tree.db"

    @staticmethod
    def get_project_root(start_path: Path = None) -> Path:
        """
        Sucht stochastisch im Verzeichnisbaum nach oben, bis ein 'src'-Ordner 
        gefunden wird. Der Ordner direkt darüber ist das automatische Projekt-Root.
        """
        if start_path is None:
            file_path = Path(__file__).resolve()
        else:
            file_path = Path(start_path).resolve()

        current = file_path if file_path.is_dir() else file_path.parent

        # Kaskadierende Aufwärtssuche nach dem 'src'-Verzeichnis
        for parent in [current] + list(current.parents):
            # Fall 1: Der aktuelle Elternordner enthält ein 'src'-Unterverzeichnis -> das ist unser Root
            if (parent / "src").is_dir():
                return parent
            # Fall 2: Wir stehen selbst direkt im 'src'-Ordner -> der Ordner darüber ist das Root
            if parent.name.lower() == "src":
                return parent.parent

        # Fallback auf das aktuelle Verzeichnis, falls nirgendwo ein 'src' existiert
        return current

    @classmethod
    def project_find_data(cls, filename: str) -> Path:
        """Sucht eine Datei ausgehend vom dynamisch erkannten Projekt-Root in allen Unterordnern abwärts."""
        base_root = cls.get_project_root()
        fn_lower = filename.lower()
        for path in base_root.rglob("*"):
            if path.is_file() and path.name.lower() == fn_lower:
                return path
        return None

    @classmethod
    def get_database_path(cls) -> Path:
        """Gibt den Pfad zur SQLite-Wissensdatenbank zurück."""
        base_root = cls.get_project_root()
        candidate = base_root / cls.BASE_DIR / cls.SUBFOLDER / cls.DB_FILENAME
        if candidate.is_file():
            return candidate

        found = cls.project_find_data(cls.DB_FILENAME)
        if found and found.is_file():
            return found

        raise FileNotFoundError(
            f"[KRITISCHER FEHLER] Die SQLite-Datenbank '{cls.DB_FILENAME}' wurde ausgehend vom Root '{base_root}' nicht gefunden!"
        )

    @classmethod
    def get_db_connection(cls) -> sqlite3.Connection:
        """Öffnet eine robuste Verbindung zur SQLite-Datenbank."""
        db_path = cls.get_database_path()
        posix_path = db_path.resolve().as_posix()
        uri_path = f"file:///{posix_path}?mode=rw" if posix_path.startswith("/") else f"file:{posix_path}?mode=rw"
        try:
            conn = sqlite3.connect(uri_path, uri=True)
        except sqlite3.OperationalError:
            conn = sqlite3.connect(str(db_path))
        return conn

globals()['coreInfrastructure'] = coreInfrastructure