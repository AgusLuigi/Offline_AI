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
    def get_project_root(cls, start_path: Path = None) -> Path:
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

globals()['coreInfrastructure'] = coreInfrastructure