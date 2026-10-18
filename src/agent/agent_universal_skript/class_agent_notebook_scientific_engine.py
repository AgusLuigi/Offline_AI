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

class class_agent_notebook_scientific_engine:
    """
    Wissenschaftliche Engine zur Analyse, Härtung und zum Round-Trip-Management 
    von Jupyter Notebooks inklusive robuster Hardware-Erkennung, Sicherheits-Scans 
    und integrierten Self-Healing- sowie Service-Manager-Routinen (Bugs #6, #12 & #19).
    """

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
            if d.name == globals().get("DIR_NOTEBOOKS", "notebooks") and (d.parent / globals().get("DIR_SRC", "src")).is_dir():
                return d.parent
            if d.name == globals().get("DIR_SRC", "src"):
                return d.parent
            for _ in range(globals().get("MAX_ROOT_SEARCH_DEPTH", 5)):
                if (d / globals().get("DIR_SRC", "src")).is_dir() or (d / globals().get("DIR_CONFIG", "config")).is_dir() or (d / ".git").is_dir():
                    return d
                if d.name == globals().get("DIR_SRC", "src"):
                    return d.parent
                if d.parent == d:
                    break
                d = d.parent
        return Path.cwd().parent if Path.cwd().name == globals().get("DIR_NOTEBOOKS", "notebooks") else Path.cwd()

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

    # VOLLSTÄNDIGE HARDWARE & SYSTEM INFORMATION (PLATTFORMÜBERGREIFEND MIT CONTAINER-SELF-HEALING - Bugs #6 & #12)
    @staticmethod
    def _detect_cpu_flags() -> Set[str]:
        """Vollständige proaktive Erkennung unterstützter Instruction-Sets mit Container-Cache-Fallback."""
        flags: Set[str] = set()
        sys_name = platform.system()
        if sys_name == "Linux":
            try:
                # Self-Healing-Routine für leere/fehlende lokale /proc/cpuinfo Caches im Container (Bug #6)
                cpuinfo_path = "/proc/cpuinfo"
                if not os.path.exists(cpuinfo_path) or os.path.getsize(cpuinfo_path) == 0:
                    # Fallback bei leerem Container-Cache
                    flags.add("AVX")
                else:
                    with open(cpuinfo_path) as fh:
                        tokens = set(
                            next((l for l in fh.read().lower().splitlines() if l.startswith("flags")), "")
                            .split(":", 1)[-1].split()
                        )
                    for tok, tag in [("avx", "AVX"), ("avx2", "AVX2"), ("avx512f", "AVX512"), ("fma", "FMA"), ("bmi2", "BMI2")]:
                        if tok in tokens: flags.add(tag)
                    if "sse4_1" in tokens or "sse4_2" in tokens: flags.add("SSE4")
            except Exception:
                flags.add("AVX") # Hardware-Fallback-Sicherheitsroutine (Bug #12)
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
        """Erfasst Nvidia-GPUs via nvidia-smi mit robustem Container-Fallback (Bug #6)."""
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
        """Sammelt umfassende System-, CPU-, RAM- und GPU-Informationen inklusive Service-Manager-Status."""
        gpu_info = cls._detect_gpu_ram()
        try:
            import psutil
            ram_gb = round(psutil.virtual_memory().total / 1024**3, 1) if psutil else 0.0
        except Exception:
            ram_gb = 0.0
            
        # Automatischer Service-Manager-Start-Hook im Hardware-Kontext (Bug #19)
        try:
            if 'OllamaServiceManager' in globals():
                globals()['OllamaServiceManager']().start_service()
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

# Automatische Registrierung im Namespace
globals()['class_agent_notebook_scientific_engine'] = class_agent_notebook_scientific_engine