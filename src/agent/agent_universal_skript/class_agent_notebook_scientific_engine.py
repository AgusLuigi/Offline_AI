from __future__ import annotations
import ast
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Set, Tuple

# Sincronizzazione con il logger centrale dell'infrastruttura
logger = globals().get('class_logger_audit_execution')
core_infra = globals().get('class_tool_core_infrastructure')

if "_GLOBAL_RUNTIME_CONFIG" not in globals():
    globals()["_GLOBAL_RUNTIME_CONFIG"] = {}
_cfg = globals()["_GLOBAL_RUNTIME_CONFIG"]

DIR_CONFIG = _cfg.setdefault("DIR_CONFIG", "config")
DIR_NOTEBOOKS = _cfg.setdefault("DIR_NOTEBOOKS", "notebooks")
DIR_SRC = _cfg.setdefault("DIR_SRC", "src")
MAX_ROOT_SEARCH_DEPTH = _cfg.setdefault("MAX_ROOT_SEARCH_DEPTH", 5)

ANTI_SHRINKAGE_RATIO = _cfg.setdefault("ANTI_SHRINKAGE_RATIO", 0.7)
MAX_PREDICT_TOKENS = _cfg.setdefault("MAX_PREDICT_TOKENS", -1)
STOCHASTIC_TIMEOUT_SEC = _cfg.setdefault("STOCHASTIC_TIMEOUT_SEC", 3)

class class_agent_notebook_scientific_engine:
    """
    Engine scientifico avanzato per l'analisi e l'hardenizzazione dei Jupyter Notebook.
    Gestisce la mappatura del repository, il monitoraggio delle risorse hardware 
    e l'applicazione deterministica delle soglie Anti-Shrinkage a tutela del codice.
    """

    @staticmethod
    def _detect_project_root() -> Path:
        """Determina la radice del progetto analizzando la struttura delle directory."""
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
        """Genera un riepilogo compatto della struttura dei file per l'allineamento dei modelli."""
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
        """Individua in modo sicuro e isolato i Notebook target presenti nell'area di lavoro."""
        notebooks = list(project_root.rglob("*.ipynb"))
        notebooks = [nb for nb in notebooks if ".ipynb_checkpoints" not in str(nb)]
        if not notebooks:
            raise FileNotFoundError(f"Nessun file con estensione .ipynb rilevato nel percorso: '{project_root}'")
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
            print("Scelta non valida o vuota. Selezione automatica del primo Notebook disponibile.")
            return notebooks[0]

    @staticmethod
    def _detect_cpu_flags() -> Set[str]:
        """Esegue una scansione dei flag di istruzione supportati dalla CPU con logiche di fallback."""
        flags: Set[str] = set()
        sys_name = platform.system()
        if sys_name == "Linux":
            try:
                cpuinfo_path = "/proc/cpuinfo"
                if not os.path.exists(cpuinfo_path) or os.path.getsize(cpuinfo_path) == 0:
                    flags.add("AVX")
                else:
                    with open(cpuinfo_path) as fh:
                        lines = fh.read().lower().splitlines()
                        flags_line = next((l for l in lines if l.startswith("flags")), "")
                        tokens = set(flags_line.split(":", 1)[-1].split())
                    for tok, tag in [("avx", "AVX"), ("avx2", "AVX2"), ("avx512f", "AVX512"), ("fma", "FMA"), ("bmi2", "BMI2")]:
                        if tok in tokens: flags.add(tag)
                    if "sse4_1" in tokens or "sse4_2" in tokens: flags.add("SSE4")
            except Exception:
                flags.add("AVX")
        elif sys_name == "Windows":
            try:
                import ctypes
                k32 = ctypes.windll.kernel32
                for feat_id, tag in [(17, "AVX"), (40, "AVX2"), (41, "AVX512")]:
                    if k32.IsProcessorFeaturePresent(feat_id): flags.add(tag)
            except Exception:
                pass
        elif sys_name == "Darwin":
            try:
                out = subprocess.run(
                    ["sysctl", "-n", "machdep.cpu.features", "machdep.cpu.leaf7_features"],
                    capture_output=True, text=True, timeout=STOCHASTIC_TIMEOUT_SEC,
                ).stdout.upper()
                for substr, tag in [("AVX2", "AVX2"), (" AVX ", "AVX"), (" AVX1.0 ", "AVX"),
                                    ("FMA", "FMA"), ("BMI2", "BMI2"), ("SSE4.1", "SSE4"), ("SSE4.2", "SSE4")]:
                    if substr in f" {out} ": flags.add(tag)
            except Exception:
                pass
        return flags

    @staticmethod
    def _detect_gpu_ram() -> Dict:
        """Interroga l'infrastruttura NVIDIA catturando in modo sicuro eventuali timeout o driver assenti."""
        gpu_list: List[Dict] = []
        total = 0.0
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=STOCHASTIC_TIMEOUT_SEC,
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
        """Mappa l'hardware di calcolo isolando la telemetria da potenziali stalli software."""
        gpu_info = cls._detect_gpu_ram()
        try:
            import psutil
            ram_gb = round(psutil.virtual_memory().total / 1024**3, 1) if psutil else 0.0
        except Exception:
            ram_gb = 0.0
            
        try:
            if 'class_tool_ollama_service_manager' in globals():
                globals()['class_tool_ollama_service_manager'].ensure_ollama_running()
        except Exception:
            pass

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
        """Isola il codice Python dai tag markdown scartando i flussi di testo adiacenti."""
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
        """Scansiona staticamente il testo alla ricerca di credenziali o pattern insicuri."""
        warnings = []
        patterns = [
            (r"api[_-]?key\s*=\s*['\"].*?['\"]", "Rilevata potenziale chiave API cablata staticamente."),
            (r"password\s*=\s*['\"].*?['\"]", "Rilevata potenziale password cablata staticamente."),
            (r"secret\s*=\s*['\"].*?['\"]", "Rilevato potenziale token segreto cablato staticamente."),
            (r"\beval\s*\(", "Rilevato uso insicuro dell'istruzione nativa eval().")
        ]
        for pat, msg in patterns:
            if re.search(pat, code_text, re.IGNORECASE):
                warnings.append(msg)
        return warnings

    @classmethod
    def deterministic_harness_fix(cls, raw_response: str) -> str:
        """Normalizza risposte malformate prive di blocchi markdown formali."""
        if "```python" not in raw_response and "def " in raw_response:
            raw_response = f"### Korrigierter Code via Deterministic Harness\n```python\n{raw_response}\n```"
        return raw_response

    @classmethod
    def validate_code_anti_shrinkage(cls, original_code: str, llm_response: str) -> Tuple[bool, str, str]:
        """Prüft strikt programmatisch gemäß Agent-Pack-Tabelle, ob der Code geschrumpft ist."""
        cleaned_response = cls.deterministic_harness_fix(llm_response)
        new_code = cls.extract_code_block_from_llm(cleaned_response)
        orig_lines = [l.strip() for l in original_code.splitlines() if l.strip() and not l.strip().startswith("#")]
        new_lines = [l.strip() for l in new_code.splitlines() if l.strip() and not l.strip().startswith("#")]
        
        threshold = ANTI_SHRINKAGE_RATIO
        if len(new_lines) < len(orig_lines) * threshold:
            return False, f"Code-Schrumpfung erkannt! Original: {len(orig_lines)}, Neu: {len(new_lines)} (Grenze: {threshold})", new_code
        try:
            ast.parse(new_code)
        except SyntaxError as e:
            return False, f"Syntaxfehler im generierten Code: {e}", new_code   
        return True, "Anti-Shrinkage & AST-Prüfung erfolgreich bestanden.", new_code

    @classmethod
    def investigative_reverse_engineer(cls, code_text: str, project_map: str, model_name: str,
                                         call_ollama_fn=None) -> Tuple[bool, str]:
        """
        Wissenschaftliches Deep-Reverse-Engineering für undokumentierte Codeblöcke.
        Erzeugt einen strukturierten Markdown-Dokumentationsblock.
        """
        prompt = f"""Du bist ein leitender wissenschaftlicher Forschungs- und Software-Architekt.
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
"""
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": MAX_PREDICT_TOKENS}
        }
        if call_ollama_fn is None:
            mgr = globals().get('class_tool_ollama_service_manager')
            if mgr:
                call_ollama_fn = mgr.call_ollama
            else:
                return False, "Kein Ollama-Service-Manager verfügbar"

        success, resp_data = call_ollama_fn("/api/generate", payload, agent_title="Reverse-Engineer-CODE_to_MD")
        if not success:
            return False, resp_data.get('error', 'Unbekannter Fehler beim Reverse-Engineering')
        return True, resp_data.get("response", "Keine Antwort erhalten.")

    @classmethod
    def investigative_harden_and_sync(cls, markdown_text: str, code_text: str, model_name: str,
                                         call_ollama_fn=None) -> Tuple[bool, str]:
        """
        Führt einen strengen wissenschaftlichen Abgleich durch, validiert per Anti-Shrinkage und härtet den Code ohne Code-Schwund.
        """
        prompt = f"""Du bist ein kompromissloser Senior Code Auditor und Software-Härtungs-Agent. Härte den Code ohne Logikverlust (kein Code-Shrinkage). Füge Type Hints und Docstrings hinzu.
STRIKTE REGEL: Reduziere, kürze oder lösche NIEMALS bestehende Code-Logik! Der Code muss vollständig erhalten bleiben.

[(Markdown)]:
{markdown_text}

[BESTEHENDER CODE (Zu härten und zu synchronisieren)]:
{code_text}

Führe folgende Aufgaben aus:
1. Gleiche die Logik des Codes mit dem Blueprint ab. Entspricht der Code dem Markdown-Blueprint?
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
```
Aktualisierter Markdown-Blueprint:
[Erweiterter Beschreibungstext]
"""
        payload = {
            "model": model_name,
            "prompt": prompt, 
            "stream": False,
            "options": {"num_predict": -1}
        }
        if call_ollama_fn is None:
            mgr = globals().get('class_tool_ollama_service_manager')
            if mgr:
                call_ollama_fn = mgr.call_ollama
            else:
                return False, "Kein Ollama-Service-Manager verfügbar"

        success, resp_data = call_ollama_fn("/api/generate", payload, agent_title="Code-Harden")
        if not success:
            return False, resp_data.get('error', 'Unbekannter Fehler bei der Code-Härtung')
        raw_resp = resp_data.get("response", "Keine Antwort erhalten.")
        section_code = cls.extract_section_from_llm(raw_resp, "Vollständiger Code")
        if not section_code:
            section_code = cls.extract_code_block_from_llm(raw_resp)
        is_valid, validation_msg, _ = cls.validate_code_anti_shrinkage(code_text, section_code)
        if not is_valid:
            return False, f"[Anti-Shrinkage Abweisung]: {validation_msg}"
        return True, raw_resp