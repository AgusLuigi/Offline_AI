"""
Modul: class_agent_notebook_scientific_engine
Bezeichnung: Wissenschaftliche Analyse- und Härtungs-Engine für Jupyter Notebooks
Inhaltlicher Schwerpunkt:
Hardware-Erkennung (CPU-Flags, GPU-VRAM), statische Sicherheits- und Secret-Scans,
Anti-Shrinkage-Validierung, wissenschaftliches Deep-Reverse-Engineering und Code-Härtung.
"""

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
from typing import List, Dict, Set, Tuple, Optional, Any

# Globale Bindings
logger = globals().get("class_logger_audit_execution")
core_infra = globals().get("class_tool_core_infrastructure")
ollama_manager = globals().get("class_tool_ollama_service_manager")


class class_agent_notebook_scientific_engine:
    """
    Wissenschaftliche Engine zur Analyse, Härtung und Validierung von Jupyter Notebooks.
    Koppelt Hardware-Telemetrie mit deterministischer Anti-Shrinkage-Codevalidierung.
    """

    _cfg = globals().setdefault("_AGENT_CONFIG", {})
    DIR_NOTEBOOKS: str = _cfg.setdefault("DIR_NOTEBOOKS", "notebooks")
    DIR_SRC: str = _cfg.setdefault("DIR_SRC", "src")
    ANTI_SHRINKAGE_RATIO: float = _cfg.setdefault("ANTI_SHRINKAGE_RATIO", 0.7)
    MAX_PREDICT_TOKENS: int = _cfg.setdefault("MAX_PREDICT_TOKENS", -1)
    STOCHASTIC_TIMEOUT_SEC: int = _cfg.setdefault("STOCHASTIC_TIMEOUT_SEC", 3)

    @classmethod
    def get_project_root(cls) -> Path:
        """Ermittelt das Projekt-Root-Verzeichnis."""
        print("[class_agent_notebook_scientific_engine] Starte Arbeit: get_project_root wird jetzt ausgeführt.")
        infra = globals().get("class_tool_core_infrastructure")
        if infra and hasattr(infra, "get_project_root"):
            result = infra.get_project_root()
            print("[class_agent_notebook_scientific_engine] Erfolg: get_project_root erfolgreich beendet.")
            return result
        result = Path.cwd()
        print("[class_agent_notebook_scientific_engine] Erfolg: get_project_root erfolgreich beendet.")
        return result

    @classmethod
    def generate_project_map(cls, project_root: Path = None) -> str:
        """Erstellt eine kompakte Übersicht der Projektdateien."""
        print("[class_agent_notebook_scientific_engine] Starte Arbeit: generate_project_map wird jetzt ausgeführt.")
        root = project_root or cls.get_project_root()
        lines = []
        count = 0
        for path in root.rglob("*"):
            if ".ipynb_checkpoints" in str(path) or ".git" in str(path):
                continue
            if path.is_file():
                rel = path.relative_to(root)
                lines.append(f"file: {rel}")
                count += 1
                if count >= 80:
                    lines.append("... (weitere Dateien ausgeblendet)")
                    break
        result = "\n".join(lines)
        if not result or not isinstance(result, str):
            print("[class_agent_notebook_scientific_engine] FEHLER: generate_project_map hat die Aufgabe nicht erfüllt. Grund: Kein Ergebnis zurückgegeben.")
            return ""
        print("[class_agent_notebook_scientific_engine] Erfolg: generate_project_map erfolgreich beendet.")
        return result

    @classmethod
    def find_target_notebook(cls, project_root: Path = None) -> Optional[Path]:
        """Findet das primäre Ziel-Notebook im Projekt ohne interaktive Blockade."""
        print("[class_agent_notebook_scientific_engine] Starte Arbeit: find_target_notebook wird jetzt ausgeführt.")
        root = project_root or cls.get_project_root()
        notebooks = [nb for nb in root.rglob("*.ipynb") if ".ipynb_checkpoints" not in str(nb)]
        if not notebooks:
            print("[class_agent_notebook_scientific_engine] FEHLER: Kein Notebook gefunden.")
            return None
        result = notebooks[0]
        print("[class_agent_notebook_scientific_engine] Erfolg: find_target_notebook erfolgreich beendet.")
        return result

    @classmethod
    def _detect_cpu_flags(cls) -> Set[str]:
        """Ermittelt die unterstützten CPU-Instruktionsflags."""
        print("[class_agent_notebook_scientific_engine] Starte Arbeit: _detect_cpu_flags wird jetzt ausgeführt.")
        flags: Set[str] = set()
        sys_name = platform.system()
        try:
            if sys_name == "Windows":
                import ctypes
                k32 = ctypes.windll.kernel32
                for feat_id, tag in [(17, "AVX"), (40, "AVX2"), (41, "AVX512")]:
                    if k32.IsProcessorFeaturePresent(feat_id):
                        flags.add(tag)
            elif sys_name == "Linux" and os.path.exists("/proc/cpuinfo"):
                with open("/proc/cpuinfo") as fh:
                    lines = fh.read().lower().splitlines()
                    flags_line = next((l for l in lines if l.startswith("flags")), "")
                    tokens = set(flags_line.split(":", 1)[-1].split())
                for tok, tag in [("avx", "AVX"), ("avx2", "AVX2"), ("avx512f", "AVX512"), ("fma", "FMA")]:
                    if tok in tokens:
                        flags.add(tag)
        except Exception as e:
            print(f"[class_agent_notebook_scientific_engine] FEHLER: CPU-Flag-Scan fehlgeschlagen: {e}")
        result = flags
        if result is None:
            print("[class_agent_notebook_scientific_engine] FEHLER: _detect_cpu_flags hat die Aufgabe nicht erfüllt. Grund: Kein Ergebnis zurückgegeben.")
            return set()
        print("[class_agent_notebook_scientific_engine] Erfolg: _detect_cpu_flags erfolgreich beendet.")
        return result

    @classmethod
    def _detect_gpu_ram(cls) -> Dict:
        """Liest die NVIDIA GPU-Telemetrie fehlertolerant aus."""
        print("[class_agent_notebook_scientific_engine] Starte Arbeit: _detect_gpu_ram wird jetzt ausgeführt.")
        gpu_list = []
        total = 0.0
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=cls.STOCHASTIC_TIMEOUT_SEC
            )
            if out.returncode == 0:
                for line in filter(None, out.stdout.strip().splitlines()):
                    parts = line.strip().split(",")
                    if len(parts) == 2:
                        vram = round(float(parts[1].strip()) / 1024, 1)
                        gpu_list.append({"name": parts[0].strip(), "vram_gb": vram})
                        total += vram
        except Exception:
            pass
        result = {"count": len(gpu_list), "total_vram": round(total, 1), "details": gpu_list}
        if result is None:
            print("[class_agent_notebook_scientific_engine] FEHLER: _detect_gpu_ram hat die Aufgabe nicht erfüllt. Grund: Kein Ergebnis zurückgegeben.")
            return {}
        print("[class_agent_notebook_scientific_engine] Erfolg: _detect_gpu_ram erfolgreich beendet.")
        return result

    @classmethod
    def get_hardware_information(cls) -> Dict:
        """Erfasst Hardwaredaten für Inferenzabschätzungen."""
        print("[class_agent_notebook_scientific_engine] Starte Arbeit: get_hardware_information wird jetzt ausgeführt.")
        gpu_info = cls._detect_gpu_ram()
        ram_gb = 0.0
        try:
            import psutil
            ram_gb = round(psutil.virtual_memory().total / (1024 ** 3), 1)
        except Exception:
            pass

        result = {
            "CORE": os.cpu_count() or 0,
            "RAM": ram_gb,
            "GPU_COUNT": gpu_info["count"],
            "GPU_TOTAL_VRAM": gpu_info["total_vram"],
            "GPU_DETAILS": gpu_info["details"],
            "PLATFORM": platform.system(),
            "CPU_ARCH": platform.machine(),
            "CPU_FLAGS": cls._detect_cpu_flags(),
        }
        if result is None:
            print("[class_agent_notebook_scientific_engine] FEHLER: get_hardware_information hat die Aufgabe nicht erfüllt. Grund: Kein Ergebnis zurückgegeben.")
            return {}
        print("[class_agent_notebook_scientific_engine] Erfolg: get_hardware_information erfolgreich beendet.")
        return result

    @staticmethod
    def compute_hw_hash(hw_info: Dict) -> str:
        """Erzeugt einen eindeutigen Hardware-Hash (OHNE volatile Werte wie RAM/VRAM)."""
        print("[class_agent_notebook_scientific_engine] Starte Arbeit: compute_hw_hash wird jetzt ausgeführt.")
        basis = f"{hw_info.get('CPU_ARCH', '')}|{hw_info.get('PLATFORM', '')}|{hw_info.get('CORE', '')}"
        result = hashlib.sha1(basis.encode()).hexdigest()[:8]
        if not result:
            print("[class_agent_notebook_scientific_engine] FEHLER: compute_hw_hash hat die Aufgabe nicht erfüllt. Grund: Leerer Hash erzeugt.")
            return "hw_hash"
        print(f"[class_agent_notebook_scientific_engine] Erfolg: compute_hw_hash erfolgreich beendet. (Hash={result})")
        return result

    @classmethod
    def deterministic_harness_fix(cls, raw_response: str) -> str:
        """Normalisiert unformatierte Antworten ohne formale Markdown-Blöcke."""
        print("[class_agent_notebook_scientific_engine] Starte Arbeit: deterministic_harness_fix wird jetzt ausgeführt.")
        result = raw_response
        if "```python" not in raw_response and "def " in raw_response:
            result = f"### Korrigierter Code via Deterministic Harness\n```python\n{raw_response}\n```"
        print("[class_agent_notebook_scientific_engine] Erfolg: deterministic_harness_fix erfolgreich beendet.")
        return result

    @staticmethod
    def extract_code_block_from_llm(llm_response: str) -> str:
        """Extrahiert sauberen Python-Code aus Markdown-Codeblöcken."""
        print("[class_agent_notebook_scientific_engine] Starte Arbeit: extract_code_block_from_llm wird jetzt ausgeführt.")
        match = re.search(r"```(?:python)?\s*(.*?)\s*```", llm_response, re.DOTALL)
        result = match.group(1).strip() if match else llm_response.strip()
        if not result or not isinstance(result, str):
            print("[class_agent_notebook_scientific_engine] FEHLER: extract_code_block_from_llm hat die Aufgabe nicht erfüllt. Grund: Kein gültiger Code-String zurückgegeben.")
            return ""
        print("[class_agent_notebook_scientific_engine] Erfolg: extract_code_block_from_llm erfolgreich beendet.")
        return result

    @staticmethod
    def extract_section_from_llm(llm_response: str, section_header: str) -> str:
        """Extrahiert einen strukturierten Abschnitt aus der Antwort."""
        print(f"[class_agent_notebook_scientific_engine] Starte Arbeit: extract_section_from_llm wird jetzt ausgeführt. (Parameter: {section_header})")
        pattern = rf"###\s*{section_header}\s*\n(.*?)(?=\n###|\Z)"
        match = re.search(pattern, llm_response, re.DOTALL | re.IGNORECASE)
        result = match.group(1).strip() if match else ""
        if not isinstance(result, str):
            print("[class_agent_notebook_scientific_engine] FEHLER: extract_section_from_llm hat die Aufgabe nicht erfüllt. Grund: Kein String zurückgegeben.")
            return ""
        print("[class_agent_notebook_scientific_engine] Erfolg: extract_section_from_llm erfolgreich beendet.")
        return result

    @staticmethod
    def scan_for_secrets_and_security(code_text: str) -> List[str]:
        """Prüft Code statisch auf versehentlich eingebettete Schlüssel oder gefährliche Befehle."""
        print("[class_agent_notebook_scientific_engine] Starte Arbeit: scan_for_secrets_and_security wird jetzt ausgeführt.")
        warnings = []
        patterns = [
            (r"api[_-]?key\s*=\s*['\"].*?['\"]", "Potenzieller API-Key hartkodiert"),
            (r"password\s*=\s*['\"].*?['\"]", "Potenzielles Passwort hartkodiert"),
            (r"\beval\s*\(", "Unsichere Verwendung von eval()"),
        ]
        for pat, msg in patterns:
            if re.search(pat, code_text, re.IGNORECASE):
                warnings.append(msg)
        result = warnings
        if result is None:
            print("[class_agent_notebook_scientific_engine] FEHLER: scan_for_secrets_and_security hat die Aufgabe nicht erfüllt. Grund: Kein Ergebnis zurückgegeben.")
            return []
        print("[class_agent_notebook_scientific_engine] Erfolg: scan_for_secrets_and_security erfolgreich beendet.")
        return result

    @classmethod
    def validate_code_anti_shrinkage(cls, original_code: str, llm_response: str) -> Tuple[bool, str, str]:
        """Validiert, dass durch die Modifikation kein Code-Schwund entstanden ist."""
        print("[class_agent_notebook_scientific_engine] Starte Arbeit: validate_code_anti_shrinkage wird jetzt ausgeführt.")
        new_code = cls.extract_code_block_from_llm(llm_response)
        orig_lines = [l.strip() for l in original_code.splitlines() if l.strip() and not l.strip().startswith("#")]
        new_lines = [l.strip() for l in new_code.splitlines() if l.strip() and not l.strip().startswith("#")]

        if len(orig_lines) > 0 and len(new_lines) < len(orig_lines) * cls.ANTI_SHRINKAGE_RATIO:
            print(f"[class_agent_notebook_scientific_engine] FEHLER: Code-Schwund ({len(new_lines)}/{len(orig_lines)} Zeilen)")
            return False, "Code-Schrumpfung erkannt!", new_code

        try:
            ast.parse(new_code)
        except SyntaxError as e:
            print(f"[class_agent_notebook_scientific_engine] FEHLER: Syntaxfehler: {e}")
            return False, f"Syntaxfehler: {e}", new_code

        result = (True, "Validierung erfolgreich", new_code)
        if result is None:
            print("[class_agent_notebook_scientific_engine] FEHLER: validate_code_anti_shrinkage hat die Aufgabe nicht erfüllt. Grund: Kein Ergebnis zurückgegeben.")
            return (False, "Kein Ergebnis", "")
        print("[class_agent_notebook_scientific_engine] Erfolg: validate_code_anti_shrinkage erfolgreich beendet.")
        return result

    @classmethod
    def investigative_reverse_engineer(cls, code_text: str, project_map: str, model_name: str,
                                       call_ollama_fn=None) -> Tuple[bool, str]:
        """
        Wissenschaftliches Deep-Reverse-Engineering für undokumentierte Codeblöcke.
        Erzeugt einen strukturierten Markdown-Dokumentationsblock.
        """
        print(f"[class_agent_notebook_scientific_engine] Starte Arbeit: investigative_reverse_engineer wird jetzt ausgeführt. (Modell={model_name})")
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
            "options": {"num_predict": cls.MAX_PREDICT_TOKENS}
        }
        if call_ollama_fn is None:
            mgr = globals().get("class_tool_ollama_service_manager")
            if mgr and hasattr(mgr, "call_ollama"):
                call_ollama_fn = mgr.call_ollama
            else:
                print("[class_agent_notebook_scientific_engine] FEHLER: investigative_reverse_engineer hat die Aufgabe nicht erfüllt. Grund: Kein Ollama-Service-Manager verfügbar.")
                return False, "Kein Ollama-Service-Manager verfügbar"

        success, resp_data = call_ollama_fn("/api/generate", payload, agent_title="Reverse-Engineer-CODE_to_MD")
        if not success:
            err_msg = resp_data.get("error", "Unbekannter Fehler beim Reverse-Engineering") if isinstance(resp_data, dict) else str(resp_data)
            print(f"[class_agent_notebook_scientific_engine] FEHLER: investigative_reverse_engineer hat die Aufgabe nicht erfüllt. Grund: {err_msg}")
            return False, err_msg

        result_text = resp_data.get("response", "Keine Antwort erhalten.") if isinstance(resp_data, dict) else str(resp_data)
        print("[class_agent_notebook_scientific_engine] Erfolg: investigative_reverse_engineer erfolgreich beendet.")
        return True, result_text

    @classmethod
    def investigative_harden_and_sync(cls, markdown_text: str, code_text: str, model_name: str,
                                       call_ollama_fn=None) -> Tuple[bool, str]:
        """
        Führt einen strengen wissenschaftlichen Abgleich durch, validiert per Anti-Shrinkage und härtet den Code ohne Code-Schwund.
        """
        print(f"[class_agent_notebook_scientific_engine] Starte Arbeit: investigative_harden_and_sync wird jetzt ausgeführt. (Modell={model_name})")
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
            "options": {"num_predict": cls.MAX_PREDICT_TOKENS}
        }
        if call_ollama_fn is None:
            mgr = globals().get("class_tool_ollama_service_manager")
            if mgr and hasattr(mgr, "call_ollama"):
                call_ollama_fn = mgr.call_ollama
            else:
                print("[class_agent_notebook_scientific_engine] FEHLER: investigative_harden_and_sync hat die Aufgabe nicht erfüllt. Grund: Kein Ollama-Service-Manager verfügbar.")
                return False, "Kein Ollama-Service-Manager verfügbar"

        success, resp_data = call_ollama_fn("/api/generate", payload, agent_title="Code-Harden")
        if not success:
            err_msg = resp_data.get("error", "Unbekannter Fehler bei der Code-Härtung") if isinstance(resp_data, dict) else str(resp_data)
            print(f"[class_agent_notebook_scientific_engine] FEHLER: investigative_harden_and_sync hat die Aufgabe nicht erfüllt. Grund: {err_msg}")
            return False, err_msg

        raw_resp = resp_data.get("response", "Keine Antwort erhalten.") if isinstance(resp_data, dict) else str(resp_data)
        section_code = cls.extract_section_from_llm(raw_resp, "Vollständiger Code")
        if not section_code:
            section_code = cls.extract_code_block_from_llm(raw_resp)

        is_valid, validation_msg, _ = cls.validate_code_anti_shrinkage(code_text, section_code)
        if not is_valid:
            print(f"[class_agent_notebook_scientific_engine] FEHLER: investigative_harden_and_sync hat die Aufgabe nicht erfüllt. Grund: [Anti-Shrinkage Abweisung]: {validation_msg}")
            return False, f"[Anti-Shrinkage Abweisung]: {validation_msg}"

        print("[class_agent_notebook_scientific_engine] Erfolg: investigative_harden_and_sync erfolgreich beendet.")
        return True, raw_resp

    @classmethod
    def run_notebook_engine(cls, notebook_path: Path = None) -> dict:
        """
        Zentrale Ausführungsfunktion: Bündelt die Suche nach dem Notebook,
        die Hardware-Erfassung und die Projektstruktur-Übersicht.
        """
        print("[class_agent_notebook_scientific_engine] Starte Arbeit: run_notebook_engine wird jetzt ausgeführt.")
        try:
            target_nb = Path(notebook_path) if notebook_path else cls.find_target_notebook()
            hw = cls.get_hardware_information()
            pmap = cls.generate_project_map()
            result = {
                "target_notebook": target_nb,
                "hardware": hw,
                "project_map_length": len(pmap),
                "ready": target_nb is not None
            }
            if result is None:
                print("[class_agent_notebook_scientific_engine] FEHLER: run_notebook_engine hat die Aufgabe nicht erfüllt. Grund: Kein Ergebnis zurückgegeben.")
                return None
            print("[class_agent_notebook_scientific_engine] Erfolg: run_notebook_engine erfolgreich beendet.")
            return result
        except Exception as e:
            print(f"[class_agent_notebook_scientific_engine] FEHLER: In run_notebook_engine: {e}")
            return None
