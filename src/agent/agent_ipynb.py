import datetime as _dt
import json
import logging
import platform
import re
import sys
import threading
import time
from pathlib import Path
from typing import Dict, List, Tuple
from urllib import request as urllib_request

# Optionaler psutil-Import für präzise RAM-Erkennung
try:
    import psutil
except ImportError:
    psutil = None

# 1. Funktion importieren und direkt ausführen (Auto-Bootstrap & globale Registrierung)
from agent_universal_skript.auto_bootstrap_and_register_agent_tools import auto_bootstrap_and_register_agent_tools
auto_bootstrap_and_register_agent_tools()

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
SPINNER_INTERVAL = 2
TIMEOUT_OLLAMA_SEC = 1800
MAX_TORKENS = -1 # Offenes ende Nach modell


class class_resource_aware_spinner:
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
    """Zero-Dependency Ollama-Kommunikation mit integriertem class_resource_aware_spinner und erhöhtem Timeout (120s)."""
    url = f"{OLLAMA_URL}{endpoint}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib_request.Request(url, data=data, headers={"Content-Type": "application/json"})

    spinner = class_resource_aware_spinner(agent_name=agent_title, min_ram_mb=MIN_RAM_MB, max_cpu_threshold=MAX_CPU_THRESHOLD, spinner_interval=SPINNER_INTERVAL)
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

def global_stochastic_pre_guard(code_text: str) -> str:
    """
    Globaler stochastischer Vorverarbeitungs-Guard:
    Behebt typische Agenten-Fehler (unnötige Leerzeilen, Signatur-Umbrüche,
    verwaiste pass-Blöcke im Einstiegspunkt) deterministisch vor jeder Verarbeitung.
    """
    if not code_text:
        return code_text 
    # 0. Vorab-Check auf abgeschnittene Codezeilen / unvollständige Imports (Bug #22)
    lines = code_text.splitlines()
    sanitized_lines = []
    for line in lines:
        stripped = line.strip()
        if re.search(r'=\s*[\w\.]+import$', stripped) or (stripped.endswith('.') and not stripped.endswith('...')):
            sanitized_lines.append(f"{line}  # [INLINE_REPAIR_FAIL]: Abgeschnittene Codezeile bereinigt")
        else:
            sanitized_lines.append(line)
    code_text = "\n".join(sanitized_lines)
    # 1. Unnötige mehrfache Leerzeilen normalisieren (maximal 2 Leerzeilen zulassen) (Bug #7)
    code_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', code_text)
    # 2. Unmotiviert umgebrochene Funktionssignaturen (def name \n (...) :) in eine Zeile ziehen (Bug #17)
    code_text = re.sub(r'(def\s+\w+)\s*\n\s*\((.*?)\):', r'\1(\2):', code_text, flags=re.DOTALL) 
    # 3. Verwaiste pass-Blöcke im Main-Guard durch sicheren Fallback ersetzen (Bugs #18 & #19)
    if "if __name__ == '__main__':" in code_text or "if __name__ == \"__main__\":" in code_text:
        code_text = re.sub(
            r"if\s+__name__\s*==\s*['\"]__main__['\"]:\s*(?:\n\s*)+pass",
            "if __name__ == '__main__':\n    # Stochastischer Guard: Fallback-Initialisierung\n    try:\n        if 'OllamaServiceManager' in globals():\n            OllamaServiceManager().start_service()\n    except Exception as e:\n        print(f'[Guard Error]: {e}')",
            code_text
        )
    return code_text


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
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": MAX_TORKENS}
        }
    success, resp_data = call_ollama("/api/generate", payload, agent_title="Reverse-Engineer-CODE_to_MD")

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
    payload = {
        "model": model_name,
        "prompt": prompt, 
        "stream": False,
        "options": {"num_predict": MAX_TORKENS}
        }

    success, resp_data = call_ollama("/api/generate", payload, agent_title="Code-Harden")

    if not success:
        return False, resp_data.get('error', 'Unbekannt')
    return True, resp_data.get("response", "Keine Antwort.")

def run_sync():
    # 1. Logger initialisieren (setzt die Log-Datei beim Start einmalig frisch auf per mode='w')
    logger = globals().get('class_agent_logger').initialize_logger()
    pc_id = platform.node() or "LocalAgent"
    globals().get('class_agent_logger').write_log(pc_id, globals().get('class_agent_logger').LOG_PHASE_SESSION, globals().get('class_agent_logger').LOG_EVENT_SESSION_START, 
                        detail="Agent-Workflow gestartet") 
    steps_performed = []
    root = globals().get('class_agent_notebook_scientific_engine')._detect_project_root()
    steps_performed.append(f"Stochastische Projekterkennung verifiziert (Root: {root})") 
    globals().get('class_agent_logger').write_log(pc_id, globals().get('class_agent_logger').LOG_PHASE_SESSION, globals().get('class_agent_logger').LOG_EVENT_STEP_ACTION, 
                        module="ProjectRoot", detail=str(root))
    project_map = globals().get('class_agent_notebook_scientific_engine').generate_project_map(root)
    hw = globals().get('class_agent_notebook_scientific_engine').get_hardware_information()
    hw_hash = globals().get('class_agent_notebook_scientific_engine').compute_hw_hash(hw)
    steps_performed.append(f"Hardware-Analyse aktiv ({hw['GPU_TOTAL_VRAM']} GB VRAM, Hash: {hw_hash})") 
    globals().get('class_agent_logger').write_log(pc_id, globals().get('class_agent_logger').LOG_PHASE_HARDWARE, globals().get('class_agent_logger').LOG_EVENT_HW_KNOWN, 
                        detail=f"VRAM: {hw['GPU_TOTAL_VRAM']}GB, Cores: {hw['CORE']}, Hash: {hw_hash}")
    print(f"Projekt-Root gesichert: {root}")
    print(f"[HW-SYSTEM] Plattform: {hw['PLATFORM']} | CPU Cores: {hw['CORE']} | VRAM: {hw['GPU_TOTAL_VRAM']} GB | Hash: {hw_hash}")
    print(f"[HW-DETAILS] GPU-Liste: {hw['GPU_DETAILS']} | CPU Flags: {hw['CPU_FLAGS']}") 
    model_name = get_active_model()
    steps_performed.append(f"LLM aktiviert: '{model_name}'") 
    globals().get('class_agent_logger').write_log(pc_id, globals().get('class_agent_logger').LOG_PHASE_SESSION, globals().get('class_agent_logger').LOG_EVENT_STEP_ACTION, 
                        module="LLMSelection", detail=model_name)
    target_ipynb = globals().get('class_agent_notebook_scientific_engine').find_target_notebook(root)
    steps_performed.append(f"Ziel-Notebook geladen: {target_ipynb.name}") 
    globals().get('class_agent_logger').write_log(pc_id, globals().get('class_agent_logger').LOG_PHASE_AGENT, globals().get('class_agent_logger').LOG_EVENT_STEP_ACTION, 
                        module="NotebookLoader", detail=target_ipynb.name)
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
            raw_code_content = "".join(cell.get("source", []))
            current_code = global_stochastic_pre_guard(raw_code_content)
            if not current_code.strip():
                modified_cells.append(cell)
                continue 
            # Secret & Security Scan
            sec_warnings = globals().get('class_agent_notebook_scientific_engine').scan_for_secrets_and_security(current_code)
            if sec_warnings:
                security_warnings_count += len(sec_warnings)
                print(f"[SECURITY-WARNUNG Zelle {index}]: {sec_warnings}")
                globals().get('class_agent_logger').write_log(pc_id, globals().get('class_agent_logger').LOG_PHASE_FILTER, globals().get('class_agent_logger').LOG_EVENT_BANNED, 
                                     module=f"Cell_{index}", detail=str(sec_warnings)) 
            outputs = cell.get("outputs", [])
            if len(outputs) > 5:
                bloated_outputs_count += 1 
            total_cells_checked += 1
            print(f"\n Untersuchung Code-Zelle {index}") 
            if not last_markdown or not last_markdown.strip():
                print("[INVESTIGATIV-MODUS] Keine Dokumentation. Führe Tiefen-Reverse-Engineering durch...")
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
                    globals().get('class_agent_logger').write_log(pc_id, globals().get('class_agent_logger').LOG_PHASE_AGENT, globals().get('class_agent_logger').LOG_EVENT_STEP_ACTION, 
                                         module=f"Cell_{index}", detail="Reverse-Engineering erfolgreich")
                else:
                    errors_encountered.append({"cell": index, "error": rev_result})
                    globals().get('class_agent_logger').write_log(pc_id, globals().get('class_agent_logger').LOG_PHASE_REPAIR, globals().get('class_agent_logger').LOG_EVENT_RETRY_EXHAUSTED, 
                                         module=f"Cell_{index}", detail=rev_result)
            else:
                success, sync_result = investigative_harden_and_sync(last_markdown, current_code, model_name)
                if success:
                    print(sync_result)
                    cleaned_response = globals().get('class_agent_notebook_scientific_engine').deterministic_harness_fix(sync_result)
                    extracted_code = globals().get('class_agent_notebook_scientific_engine').extract_code_block_from_llm(cleaned_response)
                    guard = globals()['class_agent_code_semantic_guard'](model_name=model_name, ollama_endpoint_fn=call_ollama)
                    valid, final_code, msg = guard.evaluate_and_repair(current_code, extracted_code) 
                    if not valid:
                        anti_shrinkage_violations += 1
                        consecutive_failures += 1
                        if consecutive_failures >= 3:
                            print(f"[LOOP DETECTION] Zu viele Fehler in Folge bei Zelle {index}. Breche Optimierung ab.")
                            globals().get('class_agent_logger').write_log(pc_id, globals().get('class_agent_logger').LOG_PHASE_REPAIR, globals().get('class_agent_logger').LOG_EVENT_INLINE_REPAIR_FAIL, 
                                                 module=f"Cell_{index}", detail="Loop-Detection ausgelöst")
                        cell["source"] = [line + "\n" for line in current_code.splitlines()]
                        globals().get('class_agent_logger').write_log(pc_id, globals().get('class_agent_logger').LOG_PHASE_REPAIR, globals().get('class_agent_logger').LOG_EVENT_INLINE_REPAIR_FAIL, 
                                             module=f"Cell_{index}", detail=msg)
                    else:
                        consecutive_failures = 0
                        analyzer_cls = globals().get('class_agent_code_dependency_analyzer')
                        if analyzer_cls:
                            analyzer = analyzer_cls()
                            dep_report = analyzer.analyze_deep_dependencies(final_code)
                            if dep_report.get("dead_code_count", 0) > 0:
                                print(f"[DEPENDENCY ANALYZER] {dep_report['dead_code_count']} tote Code-Leichen in Zelle {index} erkannt.")
                        formatter_cls = globals().get('class_agent_code_py_iso_iec_25010_pep8_format_tool')
                        if formatter_cls:
                            formatter = formatter_cls()
                            fmt_success, formatted_code, fmt_msg = formatter.format_code(final_code)
                            if fmt_success:
                                final_code = formatted_code
                                print(f"[FORMATTER] Zelle {index} erfolgreich nach ISO/IEC 25010 / PEP 8 formatiert.")
                        cell["source"] = [line + "\n" for line in final_code.splitlines()]
                        globals().get('class_agent_logger').write_log(pc_id, globals().get('class_agent_logger').LOG_PHASE_REPAIR, globals().get('class_agent_logger').LOG_EVENT_INLINE_REPAIR_OK, 
                                             module=f"Cell_{index}", detail=f"Guard, Analyzer & Formatter erfolgreich: {msg}")
                else:
                    errors_encountered.append({"cell": index, "error": sync_result})
                    globals().get('class_agent_logger').write_log(pc_id, globals().get('class_agent_logger').LOG_PHASE_REPAIR, globals().get('class_agent_logger').LOG_EVENT_INLINE_REPAIR_FAIL, 
                                         module=f"Cell_{index}", detail=sync_result)
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
                globals().get('class_agent_logger').write_log(pc_id, globals().get('class_agent_logger').LOG_PHASE_SESSION, globals().get('class_agent_logger').LOG_EVENT_STEP_ACTION, 
                                     module="RoundTrip", detail="Notebook erfolgreich gespeichert")
            except Exception as e:
                print(f"\n[FEHLER beim Speichern]: {e}")
                globals().get('class_agent_logger').write_log(pc_id, globals().get('class_agent_logger').LOG_PHASE_SESSION, globals().get('class_agent_logger').LOG_EVENT_INSTALL_FAIL, 
                                     module="RoundTrip", detail=str(e))
        else:
            print("\n[ABBRUCH] Aufgrund von Guard-Verstößen oder Code-Verlust wurde kein automatisches Überschreiben durchgeführt.")
            globals().get('class_agent_logger').write_log(pc_id, globals().get('class_agent_logger').LOG_PHASE_FILTER, globals().get('class_agent_logger').LOG_EVENT_BANNED, 
                                 module="RoundTrip", detail="Guard-Verstöße verhinderten Speicherung")
    else:
        print("\n[ABBRUCH] Vom Nutzer durch Bestätigungsabfrage abgebrochen.")
        globals().get('class_agent_logger').write_log(pc_id, globals().get('class_agent_logger').LOG_PHASE_SESSION, globals().get('class_agent_logger').LOG_EVENT_STEP_ACTION, 
                             module="RoundTrip", detail="Vom Nutzer abgebrochen")
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

#python src/agent/agent_ipynb.py