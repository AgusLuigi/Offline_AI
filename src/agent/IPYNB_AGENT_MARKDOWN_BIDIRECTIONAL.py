import json
import os
import sys
import platform
import ctypes
import subprocess
import hashlib
from pathlib import Path
from typing import List, Optional, Set, Dict
import requests

# Optionaler psutil-Import für RAM-Erkennung
try:
    import psutil
except ImportError:
    psutil = None

# Konfiguration für lokales Ollama
OLLAMA_URL = "http://localhost:11434"

# Globale Konstanten für die Projekterkennung
DIR_SRC = "src"
DIR_CONFIG = "config"
DIR_NOTEBOOKS = "notebooks"
MAX_ROOT_SEARCH_DEPTH = 5

def get_active_model() -> str:
    """Prüft die Ollama-Modelle und wählt ein für den VRAM passendes Modell aus (überspringt DeepSeek-Giant)."""
    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        if response.status_code == 200:
            models = response.json().get("models", [])
            if not models:
                print("[WARNUNG] Keine Modelle in Ollama gefunden!")
                return "hermes"
            
            model_names = [m.get("name") for m in models]
            print(f"[OLLAMA] Verfügbare Modelle: {model_names}")
            
            # Filtere zu große Modelle heraus (z.B. DeepSeek 671B)
            valid_models = [m for m in model_names if "671b" not in m.lower() and "deepseek-v3" not in m.lower()]
            
            if not valid_models:
                print("[WARNUNG] Keine passenden kleinen Modelle gefunden. Verwende Fallback.")
                return model_names[0]
            
            # Suche zuerst nach einem Hermes-Modell in den gültigen Modellen
            for name in valid_models:
                if "hermes" in name.lower():
                    print(f"[OLLAMA] Modell automatisch erkannt: {name}")
                    return name
            
            fallback = valid_models[0]
            print(f"[OLLAMA] Verwende passendes lokales Modell: {fallback}")
            return fallback
    except Exception as e:
        print(f"[WARNUNG] Konnte Ollama-Modelle nicht abrufen ({e}).")
    
    return "hermes"

class NotebookAgentSync:
    
    @staticmethod
    def _detect_project_root() -> Path:
        """Stochastische Projekterkennung via CWD & __file__.
        Erkennt src/, config/ und .git/ als Marker; exakter letzter Ordnername = Anker."""
        start_paths: List[Path] = [Path.cwd()]
        try:
            f = globals().get("__file__")
            if f:
                start_paths.append(Path(f).resolve().parent)
        except Exception:
            pass
        for start in start_paths:
            d = start.resolve()
            if d.name == DIR_NOTEBOOKS and (d.parent / DIR_SRC).is_dir():
                return d.parent
            if d.name == DIR_SRC:
                return d.parent
            for _ in range(MAX_ROOT_SEARCH_DEPTH):
                if (d / DIR_SRC).is_dir() or (d / DIR_CONFIG).is_dir() or (d / ".git").is_dir():
                    return d
                if d.name == DIR_SRC:
                    return d.parent
                if d.parent == d:
                    break
                d = d.parent
        return Path.cwd().parent if Path.cwd().name == DIR_NOTEBOOKS else Path.cwd()

    @classmethod
    def find_target_notebook(cls, project_root: Path) -> Path:
        """Sucht sicher nach passenden .ipynb-Dateien im Projektordner und
        wählt dasjenige aus, das dem Projektkontext am nächsten ist."""
        notebooks = list(project_root.rglob("*.ipynb"))
        
        # Ignoriere Checkpoints
        notebooks = [nb for nb in notebooks if ".ipynb_checkpoints" not in str(nb)]
        
        if not notebooks:
            raise FileNotFoundError(f"Keine .ipynb Dateien im Projektpfad '{project_root}' gefunden!")
        
        if len(notebooks) == 1:
            print(f"-> Eindeutiges Notebook gefunden: {notebooks[0]}")
            return notebooks[0]
        
        print("\nMehrere Notebooks im Projekt gefunden:")
        for i, nb in enumerate(notebooks):
            print(f"  [{i}] {nb.relative_to(project_root)}")
            
        choice = input("Wähle die Nummer des Notebooks, das bearbeitet werden soll: ")
        try:
            return notebooks[int(choice)]
        except (ValueError, IndexError):
            print("Ungültige Wahl, nehme das erste gefundene Notebook.")
            return notebooks[0]

    # ==========================================
    # CHAPTER 4: HARDWARE INFORMATION
    # ==========================================
    @staticmethod
    def _detect_cpu_flags() -> Set[str]:
        """Proaktive Erkennung unterstuetzter Instruction-Sets, plattformabhaengig."""
        flags: Set[str] = set()
        sys_name = platform.system()
        if sys_name == "Linux":
            try:
                with open("/proc/cpuinfo") as fh:
                    tokens = set(
                        next((l for l in fh.read().lower().splitlines() if l.startswith("flags")), "")
                        .split(":", 1)[-1].split()
                    )
                for tok, tag in [("avx", "AVX"), ("avx2", "AVX2"), ("avx512f", "AVX512"),
                                 ("fma", "FMA"), ("bmi2", "BMI2")]:
                    if tok in tokens: flags.add(tag)
                if "sse4_1" in tokens or "sse4_2" in tokens: flags.add("SSE4")
            except Exception:
                pass
        elif sys_name == "Windows":
            try:
                k32 = ctypes.windll.kernel32
                for feat_id, tag in [(17, "AVX"), (40, "AVX2"), (41, "AVX512")]:
                    if k32.IsProcessorFeaturePresent(feat_id): flags.add(tag)
            except Exception:
                pass
        elif sys_name == "Darwin":
            try:
                out = subprocess.run(
                    ["sysctl", "-n", "machdep.cpu.features", "machdep.cpu.leaf7_features"],
                    capture_output=True, text=True, timeout=3,
                ).stdout.upper()
                for substr, tag in [("AVX2", "AVX2"), (" AVX ", "AVX"), (" AVX1.0 ", "AVX"),
                                    ("FMA", "FMA"), ("BMI2", "BMI2"), ("SSE4.1", "SSE4"), ("SSE4.2", "SSE4")]:
                    if substr in f" {out} ": flags.add(tag)
            except Exception:
                pass
        return flags

    @staticmethod
    def _detect_gpu_ram() -> Dict:
        """Erfasst alle Nvidia-GPUs mit Namen und VRAM."""
        gpu_list: List[Dict] = []
        total = 0.0
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=3,
            )
            if out.returncode == 0:
                for line in filter(None, out.stdout.strip().splitlines()):
                    parts = line.strip().split(",")
                    if len(parts) == 2:
                        try: vram = round(float(parts[1].strip()) / 1024, 1)
                        except ValueError: vram = 0.0
                        gpu_list.append({"name": parts[0].strip(), "vram_gb": vram})
                        total += vram
        except Exception:
            pass
        return {"count": len(gpu_list), "total_vram": round(total, 1), "details": gpu_list}

    @classmethod
    def get_hardware_information(cls) -> Dict:
        """Collects CPU, RAM (via psutil), GPU, and platform info."""
        gpu_info = cls._detect_gpu_ram()
        try:
            ram_gb = round(psutil.virtual_memory().total / 1024**3, 1) if psutil else 0.0
        except Exception:
            ram_gb = 0.0
        return {
            "CORE": os.cpu_count() or 0, "RAM": ram_gb,
            "GPU_COUNT": gpu_info["count"], "GPU_TOTAL_VRAM": gpu_info["total_vram"],
            "GPU_DETAILS": gpu_info["details"], "PLATFORM": platform.system(),
            "OS_BITNESS": "64bit" if sys.maxsize > 2**32 else "32bit",
            "CPU_ARCH": platform.machine(), "CPU_FLAGS": cls._detect_cpu_flags(),
        }

    @staticmethod
    def compute_hw_hash(hw_info: Dict) -> str:
        """HW_HASH-Basis: OHNE MAC/RAM/GPU_RAM."""
        basis = f"{hw_info['CPU_ARCH']}|{hw_info['PLATFORM']}|{hw_info['OS_BITNESS']}|{hw_info['CORE']}"
        return hashlib.sha1(basis.encode()).hexdigest()[:8]

def analyze_cell_with_ollama(markdown_text, code_text, model_name):
    """Sendet Markdown und den aktuellen Code an Ollama/Hermes zur Synchronisation."""
    prompt = f"""
Du bist ein präziser Code-Synchronisations-Agent. 
Deine Aufgabe ist es, einen Jupyter-Notebook-Abschnitt zu analysieren.

[MARKDOWN (Soll-Beschreibung / Blueprint)]:
{markdown_text}

[AKTUELLER CODE (Inklusive manueller Ergänzungen des Benutzers)]:
{code_text}

Analysiere folgendes:
1. Vergleiche das Markdown mit dem aktuellen Code.
2. Erkenne, ob der Benutzer manuellen Code hinzugefügt oder modifiziert hat.
3. Erkläre kurz den Zweck dieser manuellen Änderungen ("Warum").
4. Generiere den synchronisierten, erweiterten Code sowie ggf. den Vorschlag für das Markdown.

Antworte strukturiert in folgendem Format:
### Analyse der manuellen Änderungen:
[Deine Erklärung]

### Synchronisierter Code:
[Der optimierte/erweiterte Code]

### Vorschlag für Markdown-Ergänzung:
[Ergänzung für den Text]
"""

    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False
    }

    try:
        response = requests.post(f"{OLLAMA_URL}/api/generate", json=payload)
        if response.status_code != 200:
            return f"Ollama API Fehler (Status {response.status_code}): {response.text}"
        return response.json().get("response", "Keine Antwort vom Modell erhalten.")
    except Exception as e:
        return f"Verbindungsfehler zu Ollama: {e}"

def run_sync():
    root = NotebookAgentSync._detect_project_root()
    print(f"Projekt-Root sicher erkannt: {root}")
    
    # Hardware-Check ausgeben
    hw = NotebookAgentSync.get_hardware_information()
    hw_hash = NotebookAgentSync.compute_hw_hash(hw)
    print(f"[HW-INFO] Plattform: {hw['PLATFORM']} ({hw['OS_BITNESS']}), CPU Cores: {hw['CORE']}, RAM: {hw['RAM']} GB")
    print(f"[HW-INFO] GPU(s): {hw['GPU_COUNT']} erkannt, Gesamt-VRAM: {hw['GPU_TOTAL_VRAM']} GB, Details: {hw['GPU_DETAILS']}")
    print(f"[HW-INFO] Hardware Hash: {hw_hash}")
    
    # Ermittle das aktive Modell dynamisch
    model_name = get_active_model()
    
    target_ipynb = NotebookAgentSync.find_target_notebook(root)
    print(f"Starte Verarbeitung für: {target_ipynb.name}")
    
    with open(target_ipynb, 'r', encoding='utf-8') as f:
        nb_data = json.load(f)
        
    cells = nb_data.get("cells", [])
    last_markdown = ""
    
    for index, cell in enumerate(cells):
        if cell.get("cell_type") == "markdown":
            last_markdown = "".join(cell.get("source", []))
        elif cell.get("cell_type") == "code" and last_markdown:
            current_code = "".join(cell.get("source", []))
            
            print(f"\n=== Prüfe Zelle {index} ===")
            result = analyze_cell_with_ollama(last_markdown, current_code, model_name)
            print(result)
            print("-"*50)

if __name__ == "__main__":
    run_sync()
    
#python src/agent/IPYNB_AGENT_MARKDOWN_BIDIRECTIONAL.py