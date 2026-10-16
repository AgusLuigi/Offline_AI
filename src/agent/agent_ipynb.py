import json
import os
import sys
import platform
import ctypes
import subprocess
import hashlib
import ast
import re
import time
import threading
from pathlib import Path
from typing import List, Optional, Set, Dict, Tuple
from urllib import request as urllib_request

# Optionaler psutil-Import für präzise RAM-Erkennung
try:
    import psutil
except ImportError:
    psutil = None

# GLOBALE KONFIGURATION & STEUERUNGS-PARAMETER
OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "hermes"
STATE_FILE = ".agent_state.json"
CACHE_FILE = ".agent_cell_cache.json"

# Projekt-Struktur Anker
DIR_SRC = "src"
DIR_CONFIG = "config"
DIR_NOTEBOOKS = "notebooks"
MAX_ROOT_SEARCH_DEPTH = 5

# System- & Spinner-Grenzwerte
MAX_CPU_THRESHOLD = 90.0
MIN_RAM_MB = 2000
SPINNER_INTERVAL = 1
TIMEOUT_OLLAMA_SEC = 120


class ResourceAwareSpinner:
    """
    Kapselt den visuellen Terminal-Spinner inklusive Live-Ressourcenüberwachung (CPU/RAM).
    Läuft fehlertolerant im Hintergrund-Thread, ohne den Hauptprozess zu blockieren.
    Alle Schwellenwerte sind über Klassenattribute oder __init__-Parameter konfigurierbar.
    """
    def __init__(self, agent_name: str = "Agent",
                 min_ram_mb: int = None,
                 max_cpu_threshold: float = None,
                 spinner_interval: float = None):
        self.agent_name = agent_name
        self.has_psutil = self._check_psutil()
        # Individuelle Überschreibung der Klassenattribute pro Instanz
        if min_ram_mb is not None:
            self.MIN_RAM_MB = min_ram_mb
        if max_cpu_threshold is not None:
            self.MAX_CPU_THRESHOLD = max_cpu_threshold
        if spinner_interval is not None:
            self.SPINNER_INTERVAL = spinner_interval

    @staticmethod
    def _check_psutil() -> bool:
        try:
            import psutil
            return True
        except ImportError:
            return False

    def _get_system_metrics(self) -> str:
        """Sammelt ressourcenschonend CPU- und RAM-Werte für die Live-Anzeige."""
        if not self.has_psutil:
            return ""
        try:
            import psutil
            ram_avail = psutil.virtual_memory().available / (1024**3)
            cpu_usage = psutil.cpu_percent(interval=None)

            # Automatisches Aufräumen, falls der RAM unter das Limit fällt
            if ram_avail < (self.MIN_RAM_MB / 1024):
                gc.collect()
                return f"⚠️ RAM kritisch ({ram_avail:.2f}GB) | GC aktiv"

            if cpu_usage > self.MAX_CPU_THRESHOLD:
                return f"🔥 CPU Last hoch ({cpu_usage:.0f}%)"

            return f"RAM frei: {ram_avail:.1f}GB | CPU: {cpu_usage:.0f}%"
        except Exception:
            return ""

    def run(self, stop_event: threading.Event, is_de: bool = True):
        """
        Startet die Endlos-Visualisierung im Terminal, bis das `stop_event` gesetzt wird.
        """
        chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        base_msg = f"[{self.agent_name}] Arbeitet..." if is_de else f"[{self.agent_name}] Processing..."
        idx = 0
        
        try:
            while not stop_event.is_set():
                metrics = self._get_system_metrics()
                metric_str = f" | {metrics}" if metrics else ""
                
                output_line = f"\r{base_msg} {chars[idx % len(chars)]}{metric_str}   "
                sys.stdout.write(output_line)
                sys.stdout.flush()
                
                idx += 1
                time.sleep(self.SPINNER_INTERVAL)
        except Exception:
            pass  # Verhindert jeglichen Crash des Hauptprogramms durch Darstellungsfehler
        finally:
            # Zeile nach Beendigung sauber im Terminal bereinigen
            sys.stdout.write('\r' + ' ' * 100 + '\r')
            sys.stdout.flush()


def call_ollama(endpoint: str, payload: dict, agent_title: str = "Ollama") -> Tuple[bool, dict]:
    """Zero-Dependency Ollama-Kommunikation mit integriertem ResourceAwareSpinner und erhöhtem Timeout (120s)."""
    url = f"{OLLAMA_URL}{endpoint}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib_request.Request(url, data=data, headers={"Content-Type": "application/json"})

    spinner = ResourceAwareSpinner(agent_name=agent_title, min_ram_mb=MIN_RAM_MB, max_cpu_threshold=MAX_CPU_THRESHOLD, spinner_interval=SPINNER_INTERVAL)
    stop_event = threading.Event()
    spinner_thread = threading.Thread(target=spinner.run, args=(stop_event, True))
    spinner_thread.start()

    try:
        with urllib_request.urlopen(req, timeout=TIMEOUT_OLLAMA_SEC) as response:
            if response.status == 200:
                res_data = json.loads(response.read().decode("utf-8"))
                return True, res_data
    except urllib_request.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode("utf-8"))
            return False, {"error": err_body.get("error", str(e))}
        except Exception:
            return False, {"error": f"HTTP Error {e.code}: {e.reason}"}
    except Exception as e:
        return False, {"error": str(e)}
    finally:
        stop_event.set()
        spinner_thread.join()
    return False, {"error": "Unbekannter Fehler"}

def get_active_model() -> str:
    """Ermittelt das optimale lokale LLM über die Ollama-API, prüft die Registry robust und greift auf lokal verfügbare Fallbacks zurück."""
    url = f"{OLLAMA_URL}/api/tags"
    try:
        req = urllib_request.Request(url, headers={"Content-Type": "application/json"})
        with urllib_request.urlopen(req, timeout=3) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                models = data.get("models", [])
                if models:
                    model_names = [m.get("name") for m in models if isinstance(m, dict) and "name" in m]
                    print(f"[OLLAMA] Verfügbare Modelle in der Registry: {model_names}")
                    valid_models = [m for m in model_names if "671b" not in m.lower() and "deepseek-v3" not in m.lower()]
                    if not valid_models:
                        valid_models = model_names
                    for name in valid_models:
                        if "hermes" in name.lower() or "qwen" in name.lower():
                            print(f"[OLLAMA] Agenten-Modell automatisch erkannt: {name}")
                            return name
                    print(f"[OLLAMA] Verwende lokal verfügbares Modell: {valid_models[0]}")
                    return valid_models[0]
    except Exception as e:
        print(f"[OLLAMA-WARNUNG] Konnte Modell-Registry nicht abrufen ({e}).")
    return DEFAULT_MODEL

class NotebookAgentScientificEngine:
    
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

    @staticmethod
    def generate_project_map(project_root: Path) -> str:
        """Erstellt eine kompakte Projektstruktur-Übersicht (Project Map) für den LLM-Kontext."""
        lines = []
        count = 0
        for path in project_root.rglob("*"):
            if ".ipynb_checkpoints" in str(path) or ".git" in str(path):
                continue
            if path.is_file():
                rel = path.relative_to(project_root)
                lines.append(f"file: {rel}")
                count += 1
                if count >= 80:
                    lines.append("... (weitere Dateien ausgeblendet)")
                    break
        return "\n".join(lines)

    @classmethod
    def find_target_notebook(cls, project_root: Path) -> Path:
        """Sucht sicher nach passenden .ipynb-Dateien im Projektordner."""
        notebooks = list(project_root.rglob("*.ipynb"))
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

    # VOLLSTÄNDIGE HARDWARE & SYSTEM INFORMATION (PLATTFORMÜBERGREIFEND)
    @staticmethod
    def _detect_cpu_flags() -> Set[str]:
        """
        Vollständige proaktive Erkennung unterstützter Instruction-Sets für Linux, Windows und macOS.
        Plattformübergreifender Parser für Befehlssätze.
        """
        flags: Set[str] = set()
        sys_name = platform.system()
        if sys_name == "Linux":
            try:
                with open("/proc/cpuinfo") as fh:
                    tokens = set(
                        next((l for l in fh.read().lower().splitlines() if l.startswith("flags")), "")
                        .split(":", 1)[-1].split()
                    )
                for tok, tag in [("avx", "AVX"), ("avx2", "AVX2"), ("avx512f", "AVX512"), ("fma", "FMA"), ("bmi2", "BMI2")]:
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
        """Erfasst Nvidia-GPUs via nvidia-smi."""
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
        """Sammelt umfassende System-, CPU-, RAM- und GPU-Informationen."""
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
        """Erzeugt einen eindeutigen Hardware-Hash (OHNE volatile Werte wie RAM/VRAM)."""
        basis = f"{hw_info['CPU_ARCH']}|{hw_info['PLATFORM']}|{hw_info['CORE']}"
        return hashlib.sha1(basis.encode()).hexdigest()[:8]

    @staticmethod
    def extract_code_block_from_llm(llm_response: str) -> str:
        """Extrahiert exakt den Python-Code aus Markdown-Codeblöcken der LLM-Antwort."""
        match = re.search(r"```python\s*(.*?)\s*```", llm_response, re.DOTALL)
        if match:
            return match.group(1).strip()
        return llm_response.strip()

    @staticmethod
    def extract_section_from_llm(llm_response: str, section_header: str) -> str:
        """Extrahiert spezifische Abschnitte aus strukturierten LLM-Antworten."""
        pattern = rf"###\s*{section_header}\s*\n(.*?)(?=\n###|\Z)"
        match = re.search(pattern, llm_response, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return ""

    @staticmethod
    def scan_for_secrets_and_security(code_text: str) -> List[str]:
        warnings = []
        patterns = [
            (r"api[_-]?key\s*=\s*['\"].*?['\"]", "Möglicher hartcodierter API-Key entdeckt!"),
            (r"password\s*=\s*['\"].*?['\"]", "Möglicher hartcodierter Passwort-String entdeckt!"),
            (r"secret\s*=\s*['\"].*?['\"]", "Möglicher hartcodierter Secret-String entdeckt!"),
            (r"\beval\s*\(", "Unsichere Verwendung von eval() detektiert!")
        ]
        for pat, msg in patterns:
            if re.search(pat, code_text, re.IGNORECASE):
                warnings.append(msg)
        return warnings

    @classmethod
    def deterministic_harness_fix(cls, raw_response: str) -> str:
        """Deterministic Harness: Fängt Formatierungsfehler kleiner Modelle ab und korrigiert sie."""
        if "```python" not in raw_response and "def " in raw_response:
            raw_response = f"### Korrigierter Code via Deterministic Harness\n```python\n{raw_response}\n```"
        return raw_response

    @classmethod
    def validate_code_anti_shrinkage(cls, original_code: str, llm_response: str) -> Tuple[bool, str, str]:
        """Prüft strikt programmatisch, ob der vom LLM generierte Code geschrumpft ist oder Syntaxfehler hat."""
        cleaned_response = cls.deterministic_harness_fix(llm_response)
        new_code = cls.extract_code_block_from_llm(cleaned_response)
        orig_lines = [l.strip() for l in original_code.splitlines() if l.strip() and not l.strip().startswith("#")]
        new_lines = [l.strip() for l in new_code.splitlines() if l.strip() and not l.strip().startswith("#")]
        if len(new_lines) < len(orig_lines) * 0.7:
            return False, f"Code-Schrumpfung erkannt! Original: {len(orig_lines)}, Neu: {len(new_lines)}", new_code
        try:
            ast.parse(new_code)
        except SyntaxError as e:
            return False, f"Syntaxfehler im generierten Code: {e}", new_code   
        return True, "Anti-Shrinkage & AST-Prüfung erfolgreich.", new_code


def investigative_reverse_engineer(code_text: str, project_map: str, model_name: str) -> Tuple[bool, str]:
    prompt = f"""
Du bist ein leitender wissenschaftlicher Forschungs- und Software-Architekt.
Für den folgenden Quellcode existiert keine Dokumentation. Erstelle einen absolut investigativen, wissenschaftlich fundierten Markdown-Dokumentationsblock.
Analysiere diesen Code-Block im Kontext des Projekts:

[PROJEKT-STRUKTUR]:
{project_map}

[QUELLCODE ZUR WISSENSCHAFTLICHEN ANALYSE]:
{code_text}

Strukturiere deine Analyse strikt in folgenden wissenschaftlichen Abschnitten:
### 1. Theoretischer Hintergrund & Fachlicher Zweck:
[Fundierte Beschreibung der wissenschaftlichen / architektonischen Intention und des Geschäftswerts.]

### 2. Algorithmic Flow & Datenfluss-Architektur:
[Präzise Beschreibung der mathematischen oder logischen Reihenfolge, Ein- und Ausgänge.]

### 3. Technische Kontrakte & Typisierung:
[Erforderliche Datentypen, Bibliotheken, NumPy/Pandas-Strukturen oder API-Schnittstellen.]

### 4. Edge Cases, Risiken & Performance-Betrachtungen:
[Analyse von Speicherkomplexität, VRAM/RAM-Auslastung, Laufzeitkomplexität (Big-O) und potenziellen Fehlern.]
[Präzise Beschreibung der mathematischen oder logischen Reihenfolge, Ein- und Ausgänge.]
"""
    payload = {"model": model_name, "prompt": prompt, "stream": False}
    success, resp_data = call_ollama("/api/generate", payload, agent_title="Reverse-Engineer")

    if not success:
        return False, resp_data.get('error', 'Unbekannt')
    return True, resp_data.get("response", "Keine Antwort.")

def investigative_harden_and_sync(markdown_text: str, code_text: str, model_name: str) -> Tuple[bool, str]:
    """Führt einen strengen wissenschaftlichen Abgleich durch und härtet den Code ohne Code-Schwund."""
    prompt = f"""
Du bist ein kompromissloser Senior Code Auditor und Software-Härtungs-Agent. Härte den Code ohne Logikverlust (kein Code-Shrinkage). Füge Type Hints und Docstrings hinzu.
STRIKTE REGEL: Reduziere, kürze oder lösche NIEMALS bestehende Code-Logik! Der Code muss vollständig erhalten bleiben.

[(Markdown)]:
{markdown_text}

[BESTEHENDER CODE (Zu härten und zu synchronisieren)]:
{code_text}

Führe folgende Aufgaben aus:
1. Gleiche die Logik des Codes mit dem Blueprint ab.Entspricht der Code dem Markdown-Blueprint?
2. Wurden manuelle Ergänzungen vorgenommen? Bewerte deren Qualität und Zweck ("Warum").
3. Gibt es Verbesserungspotenziale hinsichtlich Performance, Sicherheit oder Best Practices?
4. Härte den Code: Füge Python Type Hints, strukturierte Docstrings und defensive Try-Except-Fehlerbehandlung hinzu.
5. Stelle sicher, dass KEIN Code-Schwund (Code-Shrinkage) stattfindet.

Antworte strikt in diesem Format:
### Analyse Investigative Analyse der Logik & Abweichungen:
[Detaillierte Analyse]

### Härtungs-Notizen:
[Erklärungen zu Type Hints, Robustheit und Best Practices]

### Vollständiger Code Synchronisierter & Optimierter gehärteter Code (Ohne Code-Verlust!):
```python
[Der vollständige Python-Code in einem ausführbaren Block]
Aktualisierter Markdown-Blueprint:
[Erweiterter Beschreibungstext]
"""
    payload = {"model": model_name, "prompt": prompt, "stream": False}
    success, resp_data = call_ollama("/api/generate", payload, agent_title="Code-Harden")

    if not success:
        return False, resp_data.get('error', 'Unbekannt')
    return True, resp_data.get("response", "Keine Antwort.")

def run_sync():
    steps_performed = []
    root = NotebookAgentScientificEngine._detect_project_root()
    steps_performed.append(f"Stochastische Projekterkennung verifiziert (Root: {root})")
    project_map = NotebookAgentScientificEngine.generate_project_map(root)
    hw = NotebookAgentScientificEngine.get_hardware_information()
    hw_hash = NotebookAgentScientificEngine.compute_hw_hash(hw)
    steps_performed.append(f"Hardware-Analyse aktiv ({hw['GPU_TOTAL_VRAM']} GB VRAM, Hash: {hw_hash})")
    print(f"Projekt-Root gesichert: {root}")
    print(f"[HW-SYSTEM] Plattform: {hw['PLATFORM']} | CPU Cores: {hw['CORE']} | VRAM: {hw['GPU_TOTAL_VRAM']} GB | Hash: {hw_hash}")
    print(f"[HW-DETAILS] GPU-Liste: {hw['GPU_DETAILS']} | CPU Flags: {hw['CPU_FLAGS']}")
    model_name = get_active_model()
    steps_performed.append(f"LLM aktiviert: '{model_name}'")
    target_ipynb = NotebookAgentScientificEngine.find_target_notebook(root)
    steps_performed.append(f"Ziel-Notebook geladen: {target_ipynb.name}")
    print(f"\n[AGENT] Starte Analyse für '{target_ipynb.name}' mit Modell '{model_name}'...\n" + "="*50)
    with open(target_ipynb, 'r', encoding='utf-8') as f:
        nb_data = json.load(f)
    cells = nb_data.get("cells", [])
    last_markdown = None
    total_cells_checked = 0
    reverse_engineered_count = 0
    anti_shrinkage_violations = 0
    bloated_outputs_count = 0
    security_warnings_count = 0
    errors_encountered = []
    modified_cells = []
    consecutive_failures = 0
    for index, cell in enumerate(cells):
        cell_type = cell.get("cell_type")
        if cell_type == "markdown":
            last_markdown = "".join(cell.get("source", []))
            modified_cells.append(cell)
        elif cell_type == "code":
            current_code = "".join(cell.get("source", []))
            if not current_code.strip():
                modified_cells.append(cell)
                continue
            # Secret & Security Scan 
            sec_warnings = NotebookAgentScientificEngine.scan_for_secrets_and_security(current_code)
            if sec_warnings:
                security_warnings_count += len(sec_warnings)
                print(f"[SECURITY-WARNUNG Zelle {index}]: {sec_warnings}") 
            outputs = cell.get("outputs", [])
            if len(outputs) > 5:
                bloated_outputs_count += 1 
            total_cells_checked += 1
            print(f"\n Untersuchung Code-Zelle {index}") 
            if not last_markdown or not last_markdown.strip():
                print(f"[INVESTIGATIV-MODUS] Keine Dokumentation. Führe Tiefen-Reverse-Engineering durch...")
                reverse_engineered_count += 1
                success, rev_result = investigative_reverse_engineer(current_code, project_map, model_name)
                if success:
                    print("\n[Markdown-Bericht]:")
                    print(rev_result)
                    new_md_cell = {
                        "cell_type": "markdown",
                        "metadata": {},
                        "source": [line + "\n" for line in rev_result.splitlines()]
                    }
                    modified_cells.append(new_md_cell)
                else:
                    errors_encountered.append({"cell": index, "error": rev_result})
            else:
                success, sync_result = investigative_harden_and_sync(last_markdown, current_code, model_name)
                if success:
                    print(sync_result)
                    valid, msg, extracted_code = NotebookAgentScientificEngine.validate_code_anti_shrinkage(current_code, sync_result)
                    if not valid:
                        anti_shrinkage_violations += 1
                        consecutive_failures += 1
                        if consecutive_failures >= 3:
                            print(f"[LOOP DETECTION] Zu viele Fehler in Folge bei Zelle {index}. Breche Optimierung ab.")
                        cell["source"] = [line + "\n" for line in current_code.splitlines()]
                    else:
                        consecutive_failures = 0
                        cell["source"] = [line + "\n" for line in extracted_code.splitlines()]
                else:
                    errors_encountered.append({"cell": index, "error": sync_result})
            modified_cells.append(cell)
            last_markdown = None
        else:
            modified_cells.append(cell)
    proceed = input("\n[KONTROLLE] Härtungen in das Notebook schreiben? [Y/n]: ").strip().lower()
    if proceed in ["", "y", "yes"]:
        if anti_shrinkage_violations == 0:
            nb_data["cells"] = modified_cells
            backup_path = target_ipynb.with_suffix(".ipynb.bak")
            try:
                with open(backup_path, "w", encoding="utf-8") as bf:
                    json.dump(nb_data, bf, indent=2, ensure_ascii=False)
                with open(target_ipynb, "w", encoding="utf-8") as tf:
                    json.dump(nb_data, tf, indent=2, ensure_ascii=False)
                print(f"\n[ROUND-TRIP] Notebook erfolgreich aktualisiert und gespeichert (Backup erstellt unter {backup_path.name})!")
            except Exception as e:
                print(f"\n[FEHLER beim Speichern]: {e}")
        else:
            print("\n[ABBRUCH] Aufgrund von Anti-Shrinkage-Verstößen (Code-Verlust) wurde kein automatisches Überschreiben durchgeführt.")
    else:
        print("\n[ABBRUCH] Vom Nutzer durch Bestätigungsabfrage abgebrochen.")
    steps_performed.append(f"Investigativer Audit abgeschlossen: {total_cells_checked} Zellen geprüft ({reverse_engineered_count} dokumentiert)")

    print("\n" + "="*10)
    print("ABSCHLUSSBERICHT & AUDIT-PROTOKOLL")
    print("="*10)

    print("\n[1] ZUSAMMENFASSUNG DER ERBRACHTEN SCHRITTE:")
    for i, step in enumerate(steps_performed, 1):
        print(f"  {i}. {step}")
        
    print("\n[2] METRIKEN & QUALITÄTSKONTROLLE:")
    print(f" • Ziel-Notebook:              {target_ipynb.name}")
    print(f" • Aktives LLM:                {model_name}")
    print(f" • Analysierte Code-Zellen:    {total_cells_checked}")
    print(f" • Dokumentations-Ergänzungen: {reverse_engineered_count} (Investigativ erstellt)")
    print(f" • Bloated Outputs:            {bloated_outputs_count} (Zellen mit hoher Output-Last)")
    print(f" • Security Warnungen:         {security_warnings_count} (Secrets / unsichere Patterns)")
    print(f" • Anti-Shrinkage-Verstöße:    {anti_shrinkage_violations} (Code-Verlust-Schutz)")
    print(f" • Aufgetretene Fehler:        {len(errors_encountered)}")

    if errors_encountered:
        print("\n[3] KRITISCHE PROBLEME:")
        for err in errors_encountered:
            print(f"  • Zelle {err['cell']}: {err['error']}")
    else:
        print("\n[3] STATUS: Notebook-Workflow erfolgreich ausgeführt und verifiziert!")
        
    print("="*10)


if __name__ == "__main__":
    run_sync()

#python src/agent/IPYNB_AGENT_MARKDOWN_BIDIRECTIONAL.py