"""setup.py — Offline Coding Agent Setup (Windows)"""

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


def run(cmd, check=True, visible=False):
    """
    Führt einen Befehl aus.
    visible=True  → Output wird direkt im Terminal angezeigt (z. B. Download-Fortschritt).
    visible=False → Output wird gecaptured und als stdout zurückgegeben.
    """
    if visible:
        result = subprocess.run(cmd, shell=True, text=True, encoding="utf-8", errors="replace")
        if check and result.returncode != 0:
            print(f"  ✗ Fehler bei: {cmd}")
            sys.exit(1)
        return result
    else:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if check and result.returncode != 0:
            print(f"  ✗ Fehler: {result.stderr.strip()}")
            sys.exit(1)
        return result

def check(cmd):
    """Prüft, ob ein Befehl existiert / erfolgreich ist."""
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace").returncode == 0   

MIN_RAM_TIERS = [8, 12, 16, 24, 32, 48, 64, 80, 128]

AVAILABLE_MODELS = [
    # CODE
    {"id": "qwen3-coder-next",  "label": "Qwen3 Coder Next (80B)",  "desc": "Top Coding – 58,7% SWE-bench, 256K Kontext",
     "size_gb": 45.0, "min_ram": 48, "forge": True,  "tags": ["code", "system"]},
    {"id": "qwen3.8:27b",       "label": "Qwen3.8 (27B)",           "desc": "Bestes Allround-Coding, Image-Input",
     "size_gb": 18.0, "min_ram": 24, "forge": False, "tags": ["code", "vision"]},
    {"id": "qwen3.6:27b",       "label": "Qwen3.6 (27B)",           "desc": "Agentic Coding, MTP (schneller)",
     "size_gb": 17.0, "min_ram": 24, "forge": True,  "tags": ["code", "system"]},
    {"id": "qwen3-coder:30b",   "label": "Qwen3 Coder (30B)",       "desc": "High-End Coding & Software-Architektur",
     "size_gb": 22.4, "min_ram": 24, "forge": True,  "tags": ["code", "system"]},
    {"id": "qwen3:32b",         "label": "Qwen3 (32B)",             "desc": "Coding + Reasoning (Thinking-Mode)",
     "size_gb": 20.0, "min_ram": 24, "forge": False, "tags": ["code", "logik"]},
    {"id": "devstral:24b",      "label": "Devstral Small 2 (24B)",  "desc": "Agentic Multi-File-Edits, 46,8% SWE-bench",
     "size_gb": 14.0, "min_ram": 16, "forge": False, "tags": ["code", "system"]},
    {"id": "gpt-oss:20b",       "label": "GPT-OSS (20B)",           "desc": "OpenAI Open-Weight, Tool-Use + Reasoning",
     "size_gb": 14.0, "min_ram": 16, "forge": False, "tags": ["code", "system", "logik"]},
    {"id": "gemma4:26b-a4b",    "label": "Gemma 4 (26B A4B)",       "desc": "Schnellstes Coding (MoE, ~136 tok/s)",
     "size_gb": 16.0, "min_ram": 16, "forge": False, "tags": ["code", "vision"]},
    {"id": "glm-4.7-flash",     "label": "GLM-4.7-Flash",           "desc": "198K Kontext, MIT-Lizenz, MCP + Tool-Use",
     "size_gb": 19.0, "min_ram": 24, "forge": False, "tags": ["code", "system"]},

    # LOGIK / REASONIN
    {"id": "qwen3.5:122b",      "label": "Qwen3.5 (122B-A10B)",     "desc": "MoE 10B aktiv – schnell + starkes Reasoning",
     "size_gb": 73.0, "min_ram": 80, "forge": False, "tags": ["logik", "planung"]},
    {"id": "deepseek-r1:70b",   "label": "DeepSeek R1 (70B)",       "desc": "Bestes Reasoning – Chain-of-Thought, Mathe, Logik",
     "size_gb": 43.0, "min_ram": 48, "forge": False, "tags": ["logik"]},
    {"id": "qwen2.5:72b",       "label": "Qwen 2.5 (72B)",          "desc": "Top Reasoning + Multilingual (DE/EN)",
     "size_gb": 47.0, "min_ram": 48, "forge": False, "tags": ["logik", "planung"]},
    {"id": "deepseek-r1:32b",   "label": "DeepSeek R1 (32B)",       "desc": "Starkes Reasoning – schneller als 70B",
     "size_gb": 20.0, "min_ram": 24, "forge": False, "tags": ["logik"]},
    {"id": "deepseek-r1:8b",    "label": "DeepSeek R1 (8B)",        "desc": "Logik & Reasoning (sparsam)",
     "size_gb": 6.5,  "min_ram": 8,  "forge": False, "tags": ["logik"]},

    # ALLROUNDER / PLANUNG
    {"id": "qwen3:30b",         "label": "Qwen3 (30B)",             "desc": "Königsklasse – logisches Denken, Planung, Jarvis",
     "size_gb": 22.0, "min_ram": 24, "forge": False, "tags": ["allrounder", "planung", "system"]},
    {"id": "qwen3:14b",         "label": "Qwen3 (14B)",             "desc": "Starker Allrounder",
     "size_gb": 11.2, "min_ram": 16, "forge": False, "tags": ["allrounder", "planung"]},
    {"id": "gemma4:31b",        "label": "Gemma 4 (31B)",           "desc": "Kreatives Schreiben, RP, Architektur-Design",
     "size_gb": 20.0, "min_ram": 24, "forge": False, "tags": ["kreativ", "planung"]},

    # VISION / VIDEO
    {"id": "qwen3-vl:8b",       "label": "Qwen3-VL (8B)",           "desc": "Video + Bild-Verständnis, OCR, UI-Analyse",
     "size_gb": 6.2,  "min_ram": 8,  "forge": False, "tags": ["vision"]},
    {"id": "gemma4:e4b",        "label": "Gemma 4 (E4B)",           "desc": "Vision + Text, MMMU 52,6%, läuft auf 8 GB",
     "size_gb": 7.0,  "min_ram": 8,  "forge": False, "tags": ["vision", "smalltalk"]},
    {"id": "minicpm-v",         "label": "MiniCPM-V (8B)",          "desc": "Multi-Image + Video-Understanding",
     "size_gb": 6.0,  "min_ram": 8,  "forge": False, "tags": ["vision"]},
    {"id": "llama4:scout",      "label": "Llama 4 Scout (109B MoE)","desc": "17B aktiv, 10M Kontext, Video-Frames",
     "size_gb": 62.0, "min_ram": 64, "forge": False, "tags": ["vision", "allrounder"]},
    {"id": "moondream",         "label": "Moondream (1.8B)",        "desc": "Ultrakompakt – Vision auf jedem Gerät",
     "size_gb": 1.7,  "min_ram": 4,  "forge": False, "tags": ["vision", "smalltalk"]},

    # AUTOCOMPLETE / IDE
    {"id": "codestral:22b",     "label": "Codestral (22B)",         "desc": "FIM 94,1%, HumanEval 88,4% – IDE Tab-Completion",
     "size_gb": 14.0, "min_ram": 16, "forge": False, "tags": ["autocomplete", "code"]},

    # SMALLTALK / LEICHTGEWICHT
    {"id": "gemma3:4b",         "label": "Gemma 3 (4B)",            "desc": "Leichtgewicht / schnelle Basis",
     "size_gb": 3.2,  "min_ram": 8,  "forge": False, "tags": ["smalltalk"]},
]

# TAG-BESCHREIBUNG (für UI / Auswahl)
TAG_LABELS = {
    "code":         "Code",
    "logik":        "Logik / Reasoning",
    "allrounder":   "Allrounder",
    "planung":      "Planung / Architektur",
    "system":       "System / Automatisierung",
    "vision":       "Vision / Video",
    "kreativ":      "Kreativ / RP",
    "autocomplete": "Autocomplete / IDE",
    "smalltalk":    "Smalltalk",
}

OLLAMA_MODEL_DEFAULT = "qwen3.6:27b"

def get_installed_models() -> list:
    """
    Liest die lokal vorhandenen Ollama-Modelle über 'ollama list' aus.
    Liefert eine Liste kleiner, lower-case Modellnamen (z. B. ['qwen3-coder:30b']).
    """
    result = run("ollama list", check=False)
    installed = []
    for line in result.stdout.splitlines():
        parts = line.strip().split()
        if not parts or parts[0].lower() == "name":
            continue
        installed.append(parts[0].lower())
    return installed


def get_model_status(model_id: str, installed_models: list) -> str:
    """
    Ermittelt den zentralen Anzeigestatus eines Modells:
      - '[local]'    -> Modell ist bereits lokal vorhanden (via 'ollama list' erkannt).
      - '[download]' -> Modell ist in der Offline-Bibliothek gelistet und kann via 'ollama pull' geladen werden.
      - '[online]'   -> Modell ist online bzw. im Katalog verfügbar, lokal nicht vorhanden.
    """
    if not model_id or not isinstance(model_id, str):
        return "[online]"
    clean = model_id.strip().lower()
    base = clean.split(":")[0].strip()
    for m in installed_models or []:
        if str(m).strip().lower().split(":")[0].strip() == base:
            return "[local]"
    for m in AVAILABLE_MODELS:
        mid = str(m.get("id") or "").strip().lower()
        if mid.split(":")[0].strip() == base:
            return "[download]"
    return "[online]"


def build_model_entries(installed_models: list) -> list:
    """
    Baut die vollständige, einheitliche Modell-Auswahlliste:
      1. ALLE lokal vorhandenen Modelle (Status '[local]') – inklusive solcher Modelle,
         die nicht in der statischen Offline-Bibliothek (AVAILABLE_MODELS) stehen
         (z. B. selbst geladene Custom-Modelle).
      2. Alle verfügbaren Offline-Modelle (Status '[download]', falls lokal nicht vorhanden;
         Status '[local]', falls bereits lokal vorhanden).
    So werden nicht nur 'mögliche' Modelle, sondern auch die 'vorhandenen' Modelle angezeigt.
    """
    installed = [str(m).strip().lower() for m in (installed_models or []) if m and str(m).strip()]
    entries = []
    seen_ids = set()
    pool_lookup = {}
    # Lookup: Modellname (ohne Tag) -> Bibliotheks-Metadaten
    for m in AVAILABLE_MODELS:
        mid = str(m.get("id") or "").strip().lower()
        pool_lookup[mid.split(":")[0].strip()] = m


    def add_entry(model_id: str, label: str, desc: str, size_gb, status: str, installed_flag: bool, from_pool: bool) -> None:
        clean_id = str(model_id).strip().lower()
        if clean_id in seen_ids:
            return
        seen_ids.add(clean_id)
        entries.append({
            "id": clean_id,
            "label": label,
            "desc": desc,
            "size_gb": size_gb,
            "status": status,
            "installed": installed_flag,
            "from_pool": from_pool,
        })
    # 1) Alle lokal vorhandenen Modelle anzeigen
    for name in sorted(set(installed)):
        meta = pool_lookup.get(name.split(":")[0].strip())
        if meta:
            add_entry(
                name,
                str(meta.get("label") or name),
                str(meta.get("desc") or "Lokal vorhanden"),
                meta.get("size_gb"),
                "[local]",
                True,
                False,
            )
        else:
            add_entry(name, name, "Lokal vorhanden", None, "[local]", True, False)
    for m in AVAILABLE_MODELS:
        mid = str(m.get("id") or "").strip().lower()
        base = mid.split(":")[0].strip()
        is_local = any(str(i).split(":")[0].strip() == base for i in installed)
        if is_local:
            continue
        add_entry(
            mid,
            str(m.get("label") or mid),
            str(m.get("desc") or ""),
            m.get("size_gb"),
            "[download]",
            False,
            True,
        )
    return entries


def prompt_model_selection(default_model: str = OLLAMA_MODEL_DEFAULT) -> list:
    """
    Interaktive Modell-Auswahl, bevor das Offline-Modell geladen wird.
    Zeigt ALLE lokal vorhandenen Modelle sowie alle verfügbaren Offline-Modelle an –
    jeweils mit Status:
      [local]    -> Modell ist bereits lokal vorhanden
      [download] -> Modell ist ladbar (verfügbar) und kann via 'ollama pull' geladen werden
      [online]   -> Modell ist online bzw. im Katalog verfügbar, lokal nicht vorhanden
    Der Nutzer kann eine Nummer aus der Liste wählen ([1] ... [n]), einen eigenen
    Modellnamen eingeben oder Enter drücken (Default).
    """
    print("\n[5/6] Modell-Auswahl (Mehrfachauswahl mit Komma möglich):")
    installed_models = get_installed_models()
    entries = build_model_entries(installed_models)
    for idx, e in enumerate(entries, start=1):
        size_txt = f" ({e.get('size_gb')} GB)" if e.get("size_gb") else ""
        source_txt = " [library]" if e.get("from_pool") else ""
        print(f"  [{idx}] {e['status']} {e['label']} – {e['desc']}{size_txt}{source_txt}")
    choice = input(
        f"  → Modell(e) auswählen [1-{len(entries)}, z.B. 3 oder 24,26,12,25], eigene Eingabe oder Enter für Standard '{default_model}': "
    ).strip().lower()
    selected_models = []
    if not choice:
        selected_models = [default_model]
        print(f"  ✓ Gewählt (Standard): '{default_model}'")
    else:
        parts = [p.strip() for p in choice.replace(";", ",").split(",") if p.strip()]
        for part in parts:
            if part.isdigit():
                val = int(part)
                if 1 <= val <= len(entries):
                    m_id = entries[val - 1]["id"]
                    if m_id not in selected_models:
                        selected_models.append(m_id)
            else:
                cleaned = "".join(c for c in part if c.isalnum() or c in "._-:/")
                cleaned = cleaned.strip("._-")
                if cleaned and cleaned not in selected_models:
                    selected_models.append(cleaned)
        if not selected_models:
            selected_models = [default_model]
            print(f"  ⚠ Keine gültige Auswahl erkannt. Verwende Standard: '{default_model}'")
        else:
            print(f"  ✓ Gewählte Modelle: {selected_models}")
    return selected_models


def prompt_model_cleanup():
    """
    [5/6b] Modell-Verwaltung / Bereinigung:
    Erlaubt das gezielte Löschen von lokal nicht mehr benötigten Modellen via 'ollama rm'.
    Der Nutzer kann einzelne Nummern (z.B. '3'), mehrere durch Komma getrennte Nummern (z.B. '1,2,3') 
    oder Enter zum Überspringen eingeben.
    """
    print("\n[5/6b] Lokale Modell-Bereinigung (Optionale Speicherplatz-Freigabe):")
    installed_models = get_installed_models()
    if not installed_models:
        print("  → Keine lokalen Modelle gefunden, die gelöscht werden könnten.")
        return
    entries = build_model_entries(installed_models)
    # Filtere nur die heraus, die tatsächlich lokal vorhanden sind ([local])
    local_entries = [e for e in entries if e["status"] == "[local]"]
    if not local_entries:
        print("  → Keine lokalen Modelle vorhanden.")
        return
    print("  Aktuell lokal installierte Modelle:")
    for idx, e in enumerate(local_entries, start=1):
        size_txt = f" ({e.get('size_gb')} GB)" if e.get("size_gb") else ""
        print(f"  [{idx}] {e['id']}{size_txt} – {e['desc']}")
    choice = input(
        "  → Möchtest du Modelle löschen? Gib Nummern ein (z.B. 3 oder 1,2) oder Enter zum Überspringen: "
    ).strip()
    if not choice:
        print("  → Übersprungen. Keine Modelle gelöscht.")
        return
    indices_to_delete = []
    for part in choice.replace(";", ",").split(","):
        part = part.strip()
        if part.isdigit():
            val = int(part)
            if 1 <= val <= len(local_entries):
                indices_to_delete.append(val - 1)
    for idx in sorted(set(indices_to_delete), reverse=True):
        model_to_rm = local_entries[idx]["id"]
        print(f"  → Lösche lokales Modell '{model_to_rm}' via ollama rm...")
        run(f'ollama rm "{model_to_rm}"', check=False)
        print(f"  ✓ Modell '{model_to_rm}' wurde entfernt.")


def main():
    print("  Offline Coding Agent Setup")
    print("\n[1/6] Prüfe Python...")
    print(f"  ✓ Python {sys.version.split()[0]}")
    print("\n[2/6] Prüfe PyTorch...")
    if check('python -c "import torch"'):
        ver = run('python -c "import torch; print(torch.__version__)"').stdout.strip()
        print(f"  ✓ PyTorch {ver} ist installiert.")
    else:
        print("  → Installiere PyTorch...")
        if check("nvidia-smi"):
            print("  → NVIDIA GPU erkannt, CUDA-Variante...")
            run('pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126', check=False)
        else:
            print("  → Keine NVIDIA GPU, CPU-Variante...")
            run('pip install torch torchvision torchaudio', check=False)
        print("  ✓ PyTorch installiert.")
    print("\n[3/6] Prüfe Ollama...")
    if check("ollama --version"):
        print("  ✓ Ollama ist installiert.")
    else:
        print("  → Installiere Ollama...")
        run("winget install Ollama.Ollama", check=False)
        print("  ✓ Ollama installiert.")
        print("  ⚠ Neustart des Terminals nötig.")
        input("  Enter drücken nach Neustart...")
    print("\n[4/6] Prüfe Ollama-Dienst...")
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3)
        print("  ✓ Ollama läuft bereits.")
    except Exception:
        print("  → Starte Ollama...")
        subprocess.Popen("ollama serve", shell=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(5)
        try:
            urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3)
            print("  ✓ Ollama läuft.")
        except Exception:
            print("  ⚠ Ollama startet nicht. Starte manuell: ollama serve")
            sys.exit(1)
    print("\n[5/6] Prüfe Modelle...")
    SELECTED_MODELS = prompt_model_selection()
    prompt_model_cleanup()
    installed_models = get_installed_models()
    if OLLAMA_MODEL_DEFAULT not in SELECTED_MODELS:
        SELECTED_MODELS.insert(0, OLLAMA_MODEL_DEFAULT)
    for model in SELECTED_MODELS:
        if get_model_status(model, installed_models) != "[local]":
            print(f"  → Lade Modell '{model}' (kann je nach Größe dauern)...")
            run(f'ollama pull "{model}"', check=False, visible=True)
            print(f"  ✓ Modell '{model}' geladen.")
            installed_models = get_installed_models()
        else:
            print(f"  ✓ Modell '{model}' ist bereits lokal vorhanden.")
    PRIMARY_MODEL = SELECTED_MODELS[0]
    print("\n[6/6] Prüfe OpenCode...")
    if check("opencode --version"):
        print("  ✓ OpenCode ist installiert.")
    else:
        if not check("npm --version"):
            print("  → npm nicht gefunden. Installiere Node.js...")
            run("winget install OpenJS.NodeJS.LTS", check=False)
            nodejs_dir = os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "nodejs")
            os.environ["PATH"] = nodejs_dir + os.pathsep + os.environ.get("PATH", "")
            time.sleep(2)
            if not check("npm --version"):
                print("  ⚠ Node.js installiert, aber npm nicht im PATH.")
                print("  → Terminal NEU öffnen und Skript erneut ausführen.")
                sys.exit(0)
            print("  ✓ Node.js installiert.")
        print("  → Installiere OpenCode...")
        npm_global = os.path.join(os.environ.get("APPDATA", ""), "npm")
        nodejs_dir = os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "nodejs")
        os.environ["PATH"] = npm_global + os.pathsep + nodejs_dir + os.pathsep + os.environ.get("PATH", "")
        result = run("npm install -g opencode-ai", check=False)
        if result.returncode != 0:
            print("  → npm-Installation fehlgeschlagen. Versuche Binary-Download...")
            run('powershell -ExecutionPolicy Bypass -Command "irm https://opencode.ai/install.ps1 | iex"', check=False)
        if check("opencode --version"):
            print("  ✓ OpenCode installiert.")
        else:
            print("  ⚠ OpenCode nicht im PATH. Terminal neu öffnen und erneut ausführen.")
            sys.exit(0)   
    config_dir = Path.home() / ".config" / "opencode"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "opencode.json"
    if not config_file.exists():
        models_dict = {}
        for m in SELECTED_MODELS:
            model_meta = next((item for item in AVAILABLE_MODELS if item["id"] == m), None)
            model_display_name = model_meta["label"] if model_meta else m
            models_dict[m] = {"name": model_display_name, "tools": True}
        config = {
            "provider": {
                "ollama": {
                    "npm": "@ai-sdk/openai-compatible",
                    "name": "Ollama (local)",
                    "options": {"baseURL": "http://localhost:11434/v1"},
                    "models": models_dict
                }
            }
        }
        config_file.write_text(json.dumps(config, indent=2))
        print(f"\n  ✓ Config geschrieben: {config_file}")
    print("  ✓ Setup fertig!")
    print(f"\n  Starte mit: opencode --model ollama/{PRIMARY_MODEL}\n")
    ans = input("Soll ich OpenCode jetzt starten? [J/n]: ")
    if ans.lower() != "n":
        npm_global = os.path.join(os.environ.get("APPDATA", ""), "npm")
        nodejs_dir = os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "nodejs")
        os.environ["PATH"] = npm_global + os.pathsep + nodejs_dir + os.pathsep + os.environ.get("PATH", "")
        os.system("opencode")

if __name__ == "__main__":
    main()   