import os
import json
import sys
import logging

# ==============================================================================
# GLOBALE PFADE GEZIELT ÜBER 'Offline_KI' LADEN
# ==============================================================================
def load_global_paths() -> dict:
    """
    Ermittelt das Stammverzeichnis über den festen Anker 'Offline_KI'
    und lädt die dort hinterlegten globalen Pfad-Begriffe.
    """
    # Startpunkt: Wo wird das Skript gerade ausgeführt (getcwd verhindert Notebook-Abstürze)
    current_path = os.path.abspath(os.getcwd())
    path_parts = current_path.split(os.sep)
    
    # Suchen den Ordner 'Offline_KI' im aktuellen Pfad
    if "Offline_KI" in path_parts:
        ki_index = path_parts.index("Offline_KI")
        root_path = os.sep.join(path_parts[:ki_index + 1])
        
        # Falls os.sep am Anfang verloren ging (Unix/macOS/Linux-Systeme)
        if current_path.startswith(os.sep) and not root_path.startswith(os.sep):
            root_path = os.sep + root_path
            
        potential_config = os.path.join(root_path, "config", "project_paths.json")
        
        if os.path.exists(potential_config):
            try:
                with open(potential_config, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Fehler beim Lesen der project_paths.json: {e}")
                sys.exit(1)
                
    # Fallback: Falls 'Offline_KI' im aktuellen Pfad-String nicht direkt auftaucht,
    # wandern wir traditionell nach oben, um den Ordner zu finden
    current = current_path
    while current != os.path.dirname(current):
        if os.path.basename(current) == "Offline_KI":
            potential_config = os.path.join(current, "config", "project_paths.json")
            if os.path.exists(potential_config):
                with open(potential_config, "r", encoding="utf-8") as f:
                    return json.load(f)
        current = os.path.dirname(current)
    
    print("Fehler: 'Offline_KI' oder 'project_paths.json' wurde nicht gefunden.")
    print("Bitte führe zuerst die 'initialize_project.py' im Hauptverzeichnis aus.")
    sys.exit(1)

# Lade die vordefinierten, globalen Pfade
# Jetzt sind die Begriffe PATHS["logs"] und PATHS["config"] absolut sicher geladen
PATHS = load_global_paths()

# ==============================================================================
# LOGGING KONFIGURATION (Nutzt jetzt IMMER den korrekten globalen logs-Ordner)
# ==============================================================================
logger = logging.getLogger("LibraryChecker")
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Schreibt garantiert und ausschließlich in den globalen logs-Ordner von Offline_KI
log_file = os.path.join(PATHS["logs"], "app.log")
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Zeigt es wie gewohnt in der Konsole / im Notebook an
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# ==============================================================================
# CORE FUNKTION
# ==============================================================================
def check_and_save_libraries():
    logger.info("Analysiere installierte Python-Bibliotheken...")
    
    try:
        import importlib.metadata as metadata
        installed_packages = metadata.distributions()
        
        installed_packages_list = sorted([
            {"library": dist.metadata["Name"].lower(), "version": dist.version}
            for dist in installed_packages if "Name" in dist.metadata
        ], key=lambda x: x["library"])
        
        # Speichert die Datei GARANTIERT im richtigen globalen Config-Ordner
        output_json = os.path.join(PATHS["config"], "python_library_config.json")
        
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(installed_packages_list, f, indent=4, ensure_ascii=False)
            
        logger.info(f"Erfolgreich! Gespeichert in: {output_json}")
        
    except Exception as e:
        logger.error(f"Fehler aufgetreten: {e}", exc_info=True)

if __name__ == "__main__":
    check_and_save_libraries()