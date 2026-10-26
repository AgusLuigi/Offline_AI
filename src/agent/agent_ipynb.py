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

# Optionaler psutil-Import für präzise RAM-Erkennung
try:
    import psutil
except ImportError:
    psutil = None

# 1. Automatischer Bootstrap und Registrierung aller universellen Werkzeuge
from agent_universal_skript.auto_bootstrap_and_register_agent_tools import auto_bootstrap_and_register_agent_tools
auto_bootstrap_and_register_agent_tools()

# 2. Zentrale globale Aliase mit sicherer Fallback-Logik (Defaults) direkt nach Bootstrap
logger = globals().get('class_logger_audit_execution')
ollama_manager = globals().get('class_tool_ollama_service_manager')
notebook_engine = globals().get('class_agent_notebook_scientific_engine')
stochastic_pre_guard = globals().get('class_code_py_stochastic_pre_guard')
semantic_guard = globals().get('class_agent_code_py_semantic_guard')
dependency_analyzer = globals().get('class_code_py_dependency_analyzer')
format_tool = globals().get('class_code_py_iso_iec_25010_format_tool')
spinner = globals().get('class_tool_resource_aware_spinner')

# GLOBALE KONFIGURATION & STEUERUNGS-PARAMETER (Fallback-Defaults)
OLLAMA_URL = "http://localhost:11434"
MODEL = "hermes"
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
MAX_TORKENS = -1  # Offenes Ende nach Modell


def run_sync(ollama_url: str = None, model: str = None, timeout_sec: int = None,
             spinner_interval: float = None):
    """
    Führt den investigativen Härtungs-, Dokumentations- und Synchronisations-Workflow
    für Jupyter-Notebooks aus. Nutzt die zentralen globalen Aliase und koppelt
    Agenten-Aufrufe mit dem integrierten Spinner des Ollama Service Managers.
    Parameter können beim Aufruf individuell überschrieben werden oder fallen
    auf die globalen Standardwerte (Defaults) am Skriptanfang zurück.
    """
    effective_ollama_url = ollama_url or OLLAMA_URL
    effective_default_model = model or MODEL
    effective_timeout = timeout_sec if timeout_sec is not None else TIMEOUT_OLLAMA_SEC
    effective_spinner_interval = spinner_interval if spinner_interval is not None else SPINNER_INTERVAL

    # 1. Zentralen Audit-Logger initialisieren
    if logger:
        logger.initialize_logger()
    pc_id = platform.node() or "LocalAgent"
    
    def log_action(phase, event, module="Agent", detail=""):
        if logger:
            logger.write_log(pc_id, phase, event, module=module, detail=detail)
            if event == logger.LOG_EVENT_STEP_ACTION or event == logger.LOG_EVENT_SESSION_START:
                logger.info(detail, module=module)
            elif event == logger.LOG_EVENT_BANNED:
                logger.warning(detail, module=module)
            elif event == logger.LOG_EVENT_INLINE_REPAIR_FAIL or event == logger.LOG_EVENT_RETRY_EXHAUSTED:
                logger.error(detail, module=module)
        else:
            print(f"[{module}] {detail}")

    log_action(
        logger.LOG_PHASE_SESSION if logger else "Session",
        logger.LOG_EVENT_SESSION_START if logger else "Start",
        detail="Agent-Workflow gestartet"
    )

    steps_performed = []

    # 2. Projekt-Root und Hardware über die zentrale Engine ermitteln
    root = notebook_engine._detect_project_root() if notebook_engine else Path.cwd()
    steps_performed.append(f"Stochastische Projekterkennung verifiziert (Root: {root})")
    log_action(
        logger.LOG_PHASE_SESSION if logger else "Session",
        logger.LOG_EVENT_STEP_ACTION if logger else "Step",
        module="ProjectRoot",
        detail=str(root)
    )

    project_map = notebook_engine.generate_project_map(root) if notebook_engine else ""
    hw = notebook_engine.get_hardware_information() if notebook_engine else {"GPU_TOTAL_VRAM": 0, "CORE": 4, "PLATFORM": platform.system(), "GPU_DETAILS": [], "CPU_FLAGS": []}
    hw_hash = notebook_engine.compute_hw_hash(hw) if notebook_engine else "default_hw_hash"
    steps_performed.append(f"Hardware-Analyse aktiv ({hw.get('GPU_TOTAL_VRAM', 0)} GB VRAM, Hash: {hw_hash})")
    
    if logger:
        logger.write_log(
            pc_id,
            logger.LOG_PHASE_HARDWARE,
            logger.LOG_EVENT_HW_KNOWN,
            detail=f"VRAM: {hw.get('GPU_TOTAL_VRAM', 0)}GB, Cores: {hw.get('CORE', 1)}, Hash: {hw_hash}"
        )
        logger.info(f"Projekt-Root gesichert: {root}")
        logger.info(f"[HW-SYSTEM] Plattform: {hw.get('PLATFORM')} | CPU Cores: {hw.get('CORE')} | VRAM: {hw.get('GPU_TOTAL_VRAM')} GB | Hash: {hw_hash}")
        logger.info(f"[HW-DETAILS] GPU-Liste: {hw.get('GPU_DETAILS')} | CPU Flags: {hw.get('CPU_FLAGS')}")

    # 3. Aktives LLM über den zentralen Ollama Service Manager auflösen
    model_name = ollama_manager.get_active_model(
        fallback_default=effective_default_model,
        ollama_host=effective_ollama_url
    ) if ollama_manager else effective_default_model

    steps_performed.append(f"LLM aktiviert: '{model_name}'")
    log_action(
        logger.LOG_PHASE_SESSION if logger else "Session",
        logger.LOG_EVENT_STEP_ACTION if logger else "Step",
        module="LLMSelection",
        detail=model_name
    )

    # 4. Ziel-Notebook lokalisieren und einlesen
    target_ipynb = notebook_engine.find_target_notebook(root) if notebook_engine else None
    if not target_ipynb:
        raise FileNotFoundError("Kein Ziel-Notebook gefunden.")

    steps_performed.append(f"Ziel-Notebook geladen: {target_ipynb.name}")
    log_action(
        logger.LOG_PHASE_AGENT if logger else "Agent",
        logger.LOG_EVENT_STEP_ACTION if logger else "Step",
        module="NotebookLoader",
        detail=target_ipynb.name
    )

    if logger:
        logger.info(f"\n[AGENT] Starte Analyse für '{target_ipynb.name}' mit Modell '{model_name}'...\n" + "=" * 50)

    with open(target_ipynb, "r", encoding="utf-8") as f:
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

    # 5. Zellen iterieren, prüfen und mit standardmäßigem Spinner über run_agent härten
    for index, cell in enumerate(cells):
        cell_type = cell.get("cell_type")
        if cell_type == "markdown":
            last_markdown = "".join(cell.get("source", []))
            modified_cells.append(cell)
        elif cell_type == "code":
            raw_code_content = "".join(cell.get("source", []))
            current_code = stochastic_pre_guard.global_stochastic_pre_guard(raw_code_content) if stochastic_pre_guard else raw_code_content
            if not current_code.strip():
                modified_cells.append(cell)
                continue

            # Secret & Security Scan
            sec_warnings = notebook_engine.scan_for_secrets_and_security(current_code) if notebook_engine else []
            if sec_warnings:
                security_warnings_count += len(sec_warnings)
                if logger:
                    logger.warning(f"[SECURITY-WARNUNG Zelle {index}]: {sec_warnings}")
                    logger.write_log(
                        pc_id,
                        logger.LOG_PHASE_FILTER,
                        logger.LOG_EVENT_BANNED,
                        module=f"Cell_{index}",
                        detail=str(sec_warnings)
                    )

            outputs = cell.get("outputs", [])
            if len(outputs) > 5:
                bloated_outputs_count += 1

            total_cells_checked += 1
            if logger:
                logger.info(f"\nUntersuchung Code-Zelle {index}")

            # Fall A: Keine Dokumentation vorhanden -> Tiefen-Reverse-Engineering mit run_agent
            if not last_markdown or not last_markdown.strip():
                if logger:
                    logger.info("[INVESTIGATIV-MODUS] Keine Dokumentation. Führe Tiefen-Reverse-Engineering durch...")
                reverse_engineered_count += 1
                
                # Zentriert über ollama_manager.run_agent gekoppelt mit automatischem Spinner
                success, rev_result = ollama_manager.run_agent(
                    lambda: notebook_engine.investigative_reverse_engineer(
                        current_code,
                        project_map,
                        model_name,
                        call_ollama_fn=ollama_manager.call_ollama
                    ),
                    agent_title="Reverse-Engineer",
                    spinner_interval=effective_spinner_interval
                ) if ollama_manager and notebook_engine else (False, "Engine nicht initialisiert")

                if success:
                    if logger:
                        logger.info("\n[Markdown-Bericht]:")
                        logger.info(rev_result)
                    new_md_cell = {
                        "cell_type": "markdown",
                        "metadata": {},
                        "source": [line + "\n" for line in rev_result.splitlines()]
                    }
                    modified_cells.append(new_md_cell)
                    if logger:
                        logger.write_log(
                            pc_id,
                            logger.LOG_PHASE_AGENT,
                            logger.LOG_EVENT_STEP_ACTION,
                            module=f"Cell_{index}",
                            detail="Reverse-Engineering erfolgreich"
                        )
                else:
                    errors_encountered.append({"cell": index, "error": rev_result})
                    if logger:
                        logger.write_log(
                            pc_id,
                            logger.LOG_PHASE_REPAIR,
                            logger.LOG_EVENT_RETRY_EXHAUSTED,
                            module=f"Cell_{index}",
                            detail=rev_result
                        )
            # Fall B: Dokumentation vorhanden -> Code-Härtung und Synchronisation mit run_agent
            else:
                success, sync_result = ollama_manager.run_agent(
                    lambda: notebook_engine.investigative_harden_and_sync(
                        last_markdown,
                        current_code,
                        model_name,
                        call_ollama_fn=ollama_manager.call_ollama
                    ),
                    agent_title="Code-Harden",
                    spinner_interval=effective_spinner_interval
                ) if ollama_manager and notebook_engine else (False, "Engine nicht initialisiert")

                if success:
                    if logger:
                        logger.info(sync_result)
                    cleaned_response = notebook_engine.deterministic_harness_fix(sync_result)
                    extracted_code = notebook_engine.extract_code_block_from_llm(cleaned_response)

                    # Semantischer Guard gegen Code-Shrinkage & Syntaxfehler
                    guard_instance = semantic_guard(
                        model_name=model_name,
                        ollama_endpoint_fn=ollama_manager.call_ollama
                    ) if semantic_guard else None

                    valid, final_code, msg = guard_instance.evaluate_and_repair(current_code, extracted_code) if guard_instance else (True, extracted_code, "Guard skipped")

                    if not valid:
                        anti_shrinkage_violations += 1
                        consecutive_failures += 1
                        if consecutive_failures >= 3:
                            if logger:
                                logger.warning(f"[LOOP DETECTION] Zu viele Fehler in Folge bei Zelle {index}. Breche Optimierung ab.")
                                logger.write_log(
                                    pc_id,
                                    logger.LOG_PHASE_REPAIR,
                                    logger.LOG_EVENT_INLINE_REPAIR_FAIL,
                                    module=f"Cell_{index}",
                                    detail="Loop-Detection ausgelöst"
                                )
                        cell["source"] = [line + "\n" for line in current_code.splitlines()]
                        if logger:
                            logger.write_log(
                                pc_id,
                                logger.LOG_PHASE_REPAIR,
                                logger.LOG_EVENT_INLINE_REPAIR_FAIL,
                                module=f"Cell_{index}",
                                detail=msg
                            )
                    else:
                        consecutive_failures = 0
                        # Dependency-Analyse (Dead Code & UI Warnungen)
                        if dependency_analyzer:
                            analyzer = dependency_analyzer()
                            dep_report = analyzer.analyze_deep_dependencies(final_code)
                            if dep_report.get("dead_code_count", 0) > 0 and logger:
                                logger.warning(f"[DEPENDENCY ANALYZER] {dep_report['dead_code_count']} tote Code-Leichen in Zelle {index} erkannt.")
                            if dep_report.get("duplicate_ui_warnings") and logger:
                                for ui_w in dep_report["duplicate_ui_warnings"]:
                                    logger.warning(f"[UI CHECK Zelle {index}] {ui_w}")

                        # ISO/IEC 25010 & PEP 8 Formatierung
                        if format_tool:
                            formatter = format_tool()
                            fmt_success, formatted_code, fmt_msg = formatter.format_code(final_code)
                            if fmt_success:
                                final_code = formatted_code
                                if logger:
                                    logger.info(f"[FORMATTER] Zelle {index} erfolgreich nach ISO/IEC 25010 / PEP 8 formatiert.")

                        cell["source"] = [line + "\n" for line in final_code.splitlines()]
                        if logger:
                            logger.write_log(
                                pc_id,
                                logger.LOG_PHASE_REPAIR,
                                logger.LOG_EVENT_INLINE_REPAIR_OK,
                                module=f"Cell_{index}",
                                detail=f"Guard, Analyzer & Formatter erfolgreich: {msg}"
                            )
                else:
                    errors_encountered.append({"cell": index, "error": sync_result})
                    if logger:
                        logger.write_log(
                            pc_id,
                            logger.LOG_PHASE_REPAIR,
                            logger.LOG_EVENT_INLINE_REPAIR_FAIL,
                            module=f"Cell_{index}",
                            detail=sync_result
                        )
            modified_cells.append(cell)
            last_markdown = None
        else:
            modified_cells.append(cell)

    # 6. Benutzer-Bestätigung und Round-Trip-Schreiben
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
                if logger:
                    logger.info(f"\n[ROUND-TRIP] Notebook erfolgreich aktualisiert und gespeichert (Backup erstellt unter {backup_path.name})!")
                    logger.write_log(
                        pc_id,
                        logger.LOG_PHASE_SESSION,
                        logger.LOG_EVENT_STEP_ACTION,
                        module="RoundTrip",
                        detail="Notebook erfolgreich gespeichert"
                    )
            except Exception as e:
                if logger:
                    logger.error(f"\n[FEHLER beim Speichern]: {e}")
                    logger.write_log(
                        pc_id,
                        logger.LOG_PHASE_SESSION,
                        logger.LOG_EVENT_INSTALL_FAIL,
                        module="RoundTrip",
                        detail=str(e)
                    )
        else:
            if logger:
                logger.warning("\n[ABBRUCH] Aufgrund von Guard-Verstößen oder Code-Verlust wurde kein automatisches Überschreiben durchgeführt.")
                logger.write_log(
                    pc_id,
                    logger.LOG_PHASE_FILTER,
                    logger.LOG_EVENT_BANNED,
                    module="RoundTrip",
                    detail="Guard-Verstöße verhinderten Speicherung"
                )
    else:
        if logger:
            logger.info("\n[ABBRUCH] Vom Nutzer durch Bestätigungsabfrage abgebrochen.")
            logger.write_log(
                pc_id,
                logger.LOG_PHASE_SESSION,
                logger.LOG_EVENT_STEP_ACTION,
                module="RoundTrip",
                detail="Vom Nutzer abgebrochen"
            )

    # 7. Abschlussbericht
    steps_performed.append(f"Investigativer Audit abgeschlossen: {total_cells_checked} Zellen geprüft ({reverse_engineered_count} dokumentiert)")
    print("\n" + "=" * 50)
    print("ABSCHLUSSBERICHT & AUDIT-PROTOKOLL")
    print("=" * 50)
    print("\n[1] ZUSAMMENFASSUNG DER ERBRACHTEN SCHRITTE:")
    print(f"  1. {steps_performed[0]}")
    for i, step in enumerate(steps_performed[1:], 2):
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
    print("=" * 50)


# Globale Registrierung im Namespace
globals()['run_sync'] = run_sync

if __name__ == "__main__":
    guard = semantic_guard(model_name=MODEL,ollama_endpoint_fn=ollama_manager.call_ollama if ollama_manager else None)
    guard.guard_agent_execution(agent_callable=run_sync,agent_name="agent_ipynb")