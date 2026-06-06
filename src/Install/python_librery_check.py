import os
import json
import sys
import logging

# ==============================================================================
# GLOBALE PFADE GEZIELT ÜBER 'Offline_AI' LADEN
# ==============================================================================
def load_global_paths() -> dict:
    """
    Ermittelt das Stammverzeichnis über den festen Anker 'Offline_AI'
    und lädt die dort hinterlegten globalen Pfad-Begriffe.
    """
    # Startpunkt: Wo wird das Skript gerade ausgeführt
    current_path = os.path.abspath(os.getcwd())
    path_parts = current_path.split(os.sep)
    
    # Suchen den Ordner 'Offline_AI' im aktuellen Pfad
    if "Offline_AI" in path_parts:
        ai_index = path_parts.index("Offline_AI")
        root_path = os.sep.join(path_parts[:ai_index + 1])
        
        # Falls os.sep am Anfang verloren ging
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
                
    # Fallback: Falls 'Offline_AI' im Pfad nicht direkt gefunden wurde, nach oben suchen
    current = current_path
    while True:
        parent = os.path.dirname(current)
        if os.path.basename(current) == "Offline_AI":
            potential_config = os.path.join(current, "config", "project_paths.json")
            if os.path.exists(potential_config):
                with open(potential_config, "r", encoding="utf-8") as f:
                    return json.load(f)
        if current == parent: # Root erreicht
            break
        current = parent
    
    print("Fehler: 'Offline_AI' oder 'project_paths.json' wurde nicht gefunden.")
    print("Bitte stelle sicher, dass du dich innerhalb des Projekts befindest.")
    sys.exit(1)

# Lade die vordefinierten, globalen Pfade
PATHS = load_global_paths()

# ==============================================================================
# LOGGING KONFIGURATION
# ==============================================================================
logger = logging.getLogger("LibraryChecker")
logger.setLevel(logging.INFO)
if logger.hasHandlers():
    logger.handlers.clear()

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Schreibt in den globalen logs-Ordner aus der Konfiguration
log_dir = PATHS.get("logs", os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs"))
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "app.log")

file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

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
        
        # Speichert die Datei im globalen Config-Ordner aus der Konfiguration
        config_dir = PATHS.get("config", os.path.join(os.path.dirname(os.path.abspath(__file__)), "config"))
        os.makedirs(config_dir, exist_ok=True)
        output_json = os.path.join(config_dir, "python_library_config.json")
        
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(installed_packages_list, f, indent=4, ensure_ascii=False)
            
        logger.info(f"Erfolgreich! Gespeichert in: {output_json}")
        
    except Exception as e:
        logger.error(f"Fehler aufgetreten: {e}", exc_info=True)

if __name__ == "__main__":
    check_and_save_libraries()