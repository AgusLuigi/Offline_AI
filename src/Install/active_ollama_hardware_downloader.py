import os
import json
import sys
import subprocess
import importlib
import re

def get_project_root() -> str:
    """
    Ermittelt das Stammverzeichnis über den festen Anker 'Offline_AI'.
    Verhindert das Ausbrechen aus der Projektstruktur.
    """
    if "__file__" in globals():
        current_path = os.path.abspath(os.path.dirname(__file__))
    else:
        current_path = os.path.abspath(os.getcwd())
    
    path_parts = current_path.split(os.sep)
    if "Offline_AI" in path_parts:
        ki_index = path_parts.index("Offline_AI")
        if os.name == 'nt':
            root_path = path_parts[0] + os.sep + os.path.join(*path_parts[1:ki_index + 1])
        else:
            root_path = os.sep + os.path.join(*path_parts[:ki_index + 1])
        return os.path.abspath(root_path)

    while current_path != os.path.dirname(current_path):
        if os.path.basename(current_path) == "Offline_AI":
            return current_path
        current_path = os.path.dirname(current_path)
    return os.path.abspath(os.getcwd())

# ==============================================================================
# 1. INITIALISIERE CONFIG UND LOGGING ZUERST (Schutz vor Logikschwand)
# ==============================================================================
PROJECT_ROOT = get_project_root()
config_paths_json = os.path.join(PROJECT_ROOT, "config", "project_paths.json")

if not os.path.exists(config_paths_json):
    print(f"Fehler: '{config_paths_json}' fehlt. Bitte zuerst initialize_project.py ausführen.")
    sys.exit(1)

with open(config_paths_json, "r", encoding="utf-8") as f:
    PATHS = json.load(f)

# Zentrales Logging sauber initialisieren (Verhindert Duplikate im Notebook)
import logging
logger = logging.getLogger("HardwareOllamaDownloader")
logger.setLevel(logging.INFO)
logger.handlers.clear()  # Alte Handler entfernen vor Neu-Registrierung
logger.propagate = False

formatter = logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s')

file_handler = logging.FileHandler(os.path.join(PATHS["logs"], "app.log"), encoding="utf-8")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# ==============================================================================
# 2. SELBSTHEILUNGS-LOGIK (Notebook-Sicher via importlib-Reload)
# ==============================================================================
try:
    import urllib.request
    import psutil
    import ollama
    from ollama import Client  # Schutz vor Download-Abbrüchen durch Timeout-Steuerung
except ImportError as e:
    missing_module = str(e).split("'")[-2] if "'" in str(e) else str(e)
    logger.warning(f"Fehlende Abhängigkeit erkannt: Das Paket '{missing_module}' ist nicht bereit.")
    logger.info("Starte automatische Hintergrund-Installation via pip...")
    
    try:
        print(f"\n[AUTO-REPARATUR] Installiere fehlende Module im Hintergrund...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "ollama", "psutil"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if result.returncode == 0:
            logger.info("Abhängigkeiten erfolgreich nachinstalliert. Erneuter Import-Versuch...")
            import urllib.request
            psutil = importlib.import_module('psutil')
            ollama = importlib.import_module('ollama')
            from ollama import Client
            print("[AUTO-REPARATUR] Module erfolgreich im RAM registriert.\n")
        else:
            logger.error(f"Pip-Installationsfehler (Returncode {result.returncode}): {result.stderr}")
            print(f"\n[FEHLER] Automatische Installation fehlgeschlagen.\nDetails: {result.stderr}")
            sys.exit(1)
            
    except Exception as install_error:
        logger.error(f"Kritischer Systemfehler bei der Paketreparatur: {install_error}", exc_info=True)
        sys.exit(1)

# ==============================================================================
# LIVE-MODELLDATEN UND HARDWARE-ABGLEICH
# ==============================================================================
def fetch_online_model_library() -> list:
    """
    Lädt die tagesaktuelle, verifizierte Liste der Ollama-Modelle herunter.
    Sichert verschachtelte JSON-Objekte strukturell ab.
    """
    print("[INFO] Stelle Verbindung zum zentralen Open-Source-Repository her...")
    logger.info("Rufe aktuelle Modell-Bibliothek aus dem Internet ab...")
    
    url = "https://raw.githubusercontent.com/chrizzo84/OllamaScraper/refs/heads/main/out/ollama_models.json"
    
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            print("[INFO] Modell-Metadaten erfolgreich empfangen.")
            data = json.loads(response.read().decode("utf-8"))
            
            if isinstance(data, dict):
                for key in ["models", "library", "available_models"]:
                    if key in data and isinstance(data[key], list):
                        return data[key]
                return [data]
                
            return data if isinstance(data, list) else []
    except Exception as e:
        logger.warning(f"Online-Abruf fehlgeschlagen ({e}). Nutze integrierten Hardware-Sicherheits-Fallback.")
        print("[HINWEIS] Online-Bibliothek nicht erreichbar. Fallback-Modellmatrix geladen.")
        return [
            {"name": "gemma3:4b", "size_gb": 3.2, "description": "Gemma 3 Leichtgewicht"},
            {"name": "deepseek-r1:8b", "size_gb": 6.5, "description": "DeepSeek R1 Logik/Reasoning"},
            {"name": "qwen3:14b", "size_gb": 11.2, "description": "Qwen 3 Starker Allrounder"},
            {"name": "qwen3-coder:30b", "size_gb": 22.4, "description": "High-End Coding für Software-Architektur"},
            {"name": "qwen3:30b", "size_gb": 22.0, "description": "Königsklasse für logisches Denken / Jarvis"}
        ]

def analyze_system_and_select_model(models: list):
    """
    Prüft die tatsächliche Hardware-Leistung des Geräts und filtert 
    vollautomatisch das mathematisch stabilste Modell heraus.
    Validiert Namen via RegEx gegen Text-Metadaten und Dokumentations-Fragmente.
    """
    print("[INFO] Starte Hardware-Leistungs-Check...")
    total_ram_gb = round(psutil.virtual_memory().total / (1024**3), 2)
    safe_ram_budget = round(total_ram_gb * 0.70, 1)
    
    logger.info(f"Geräte-Leistungs-Check: {total_ram_gb} GB RAM erkannt.")
    logger.info(f"Berechnete maximale Obergrenze für Modellgröße: {safe_ram_budget} GB.")

    # RegEx für offizielle Ollama-Namen (z.B. "llama3", "phi3:medium", "deepseek-r1:8b")
    ollama_name_pattern = re.compile(r"^[a-zA-Z0-9.\-_]+(:[a-zA-Z0-9.\-_]+)?$")

    valid_models = []
    for m in models:
        if isinstance(m, str):
            model_name = m.strip()
            size = None
            description = "Lokales LLM-Modell (Direkt-Link)"
        elif isinstance(m, dict):
            model_name = str(m.get("name", "unbekannt")).strip()
            size = m.get("size_gb") or m.get("size", 0) / (1024**3) if isinstance(m.get("size"), (int, float)) else None
            description = m.get("description", m.get("blurb", "Lokales LLM-Modell"))
        else:
            continue
        
        # 1. Stufe: Metadaten-Schutz über Wortindikatoren und Dokumentationsanker
        name_lower = model_name.lower()
        metadata_blacklist = [
            "scraped", "updated", "timestamp", "unbekannt", 
            "reference", "readme", "license", "manifest", "note"
        ]
        if any(indicator in name_lower for indicator in metadata_blacklist):
            continue

        # 2. Stufe: Strikter Syntax-Check (Filtert Beschreibungen und Freitexte im Namensfeld heraus)
        if not ollama_name_pattern.match(model_name):
            continue

        if not size:
            if "32b" in name_lower or "30b" in name_lower: size = 22.0
            elif "14b" in name_lower: size = 11.0
            elif "8b" in name_lower or "9b" in name_lower: size = 6.5
            elif "3b" in name_lower or "4b" in name_lower: size = 3.5
            else: size = 4.0
            
        if size <= safe_ram_budget:
            valid_models.append({
                "name": model_name,
                "size_gb": round(size, 1),
                "desc": description
            })

    valid_models = sorted(valid_models, key=lambda x: x["size_gb"], reverse=True)
    return total_ram_gb, safe_ram_budget, valid_models

# ==============================================================================
# DOWNLOAD AUSFÜHRUNG
# ==============================================================================
def smart_hardware_downloader():
    logger.info("=== Start der automatisisierten Ollama-Hardware-Analyse ===")
    
    raw_models = fetch_online_model_library()
    total_ram, safe_budget, fit_models = analyze_system_and_select_model(raw_models)
    
    if not fit_models:
        logger.error("Fehler: Kein gültiges Modell passt in die Hardware-Spezifikationen dieses Geräts.")
        print("[ABBRUCH] Hardware reicht für die verfügbaren Modelle nicht aus.")
        return

    perfect_match = fit_models[0]
    
    print("\n" + "="*80)
    print(f" SYSTEM-ANALYSE REPRODUZIERT:")
    print(f" -> VERFÜGGBARER ARBEITSSPEICHER : {total_ram} GB RAM")
    print(f" -> MAXIMALES SCHUTZ-BUDGET     : {safe_budget} GB")
    print(f" -> GEWÄHLTES KI-OPTIMUM        : {perfect_match['name']} ({perfect_match['size_gb']} GB)")
    print("="*80)
    print(f" Einsatzbereich: {perfect_match['desc']}")
    print("="*80 + "\n")
    
    print(f"[AUTOMATION] Starte direkten Download für Core-Modell: '{perfect_match['name']}'")
    logger.info(f"Starte automatisisierten Download für: '{perfect_match['name']}'")
    print("Bitte stelle sicher, dass die Ollama-App im Hintergrund läuft.\n")

    try:
        # Client mit verlässlichem Timeout initialisieren, um Verbindungsabbrüche abzufangen
        client = Client(timeout=3600.0)
        
        current_digest = None
        for progress in client.pull(model=perfect_match['name'], stream=True):
            status = progress.get('status', '')
            completed = progress.get('completed')
            
            total = progress.get('total')
            digest = progress.get('digest', '')
            
            if digest != current_digest and digest:
                print(f"\nÜbertrage Daten-Layer [{digest[:12]}]...")
                current_digest = digest
                
            if isinstance(total, int) and isinstance(completed, int) and total > 0:
                percent = (completed / total) * 100
                sys.stdout.write(f"\rFortschritt: {percent:.2f}% ({completed // (1024**2)}MB / {total // (1024**2)}MB) | Status: {status}")
                sys.stdout.flush()
            else:
                sys.stdout.write(f"\rStatus: {status}")
                sys.stdout.flush()

        print("\n")
        logger.info(f"Erfolgreich! '{perfect_match['name']}' wurde hardwarekonform installiert.")
        
        active_config = os.path.join(PATHS["config"], "active_model_config.json")
        with open(active_config, "w", encoding="utf-8") as f:
            json.dump({
                "model_name": perfect_match['name'],
                "allocated_size_gb": perfect_match['size_gb'],
                "detected_ram_gb": total_ram
            }, f, indent=4, ensure_ascii=False)
            
        logger.info(f"Aktiver System-Status gesichert in: {active_config}")
        print("--- Prozess fehlerfrei beendet. Dein Jarvis-Kern steht! ---")

    except Exception as e:
        logger.error(f"Kritischer Fehler beim Pull-Vorgang: {e}", exc_info=True)
        print(f"\n[FEHLER] Verbindung zu Ollama abgebrochen. Details: {e}")
        print("Bitte stelle sicher, dass die Ollama-App gestartet ist.")
        sys.exit(1)

if __name__ == "__main__":
    smart_hardware_downloader()