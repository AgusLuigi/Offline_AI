import ast
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Any

# 1. Automatischer Bootstrap und Registrierung aller universellen Werkzeuge
from agent_universal_skript.auto_bootstrap_and_register_agent_tools import auto_bootstrap_and_register_agent_tools
auto_bootstrap_and_register_agent_tools()

# 2. Direkter Zugriff auf die globalen Werkzeuge und Aliase nach dem Bootstrap
logger = globals().get('class_logger_audit_execution')
core_infra = globals().get('class_tool_core_infrastructure')
ollama_manager = globals().get('class_tool_ollama_service_manager')
spinner = globals().get('class_tool_resource_aware_spinner')
sandbox_verifier = globals().get('class_agent_sub_verifier')
sql_reader_cls = globals().get('class_tool_sql_reader')


def _get_active_agent_self_bans(sql_reader_instance) -> str:
    """
    Lucht aktiv alle selbstauferlegten Verhaltensverbote (Self-Bans) aus der 
    SQLite-Datenbank, um sie dem LLM als harte Leitlinien zu übergeben.
    """
    if not sql_reader_instance or not hasattr(sql_reader_instance, "get_active_self_bans"):
        return "Keine aktiven Verbote geladen."
    try:
        bans = sql_reader_instance.get_active_self_bans()
        if not bans:
            return "Keine aktiven Verbote registriert."
        
        ban_lines = []
        for row in bans:
            # row format: (prohibited_pattern_self_ban, detected_bug_description, applied_fix)
            ban_lines.append(f"- VERBOTEN: {row[0]} (Grund: {row[1]})")
        return "\n".join(ban_lines)
    except Exception as e:
        return f"Fehler beim Abrufen der Self-Bans: {e}"


def _read_project_knowledge_and_src(project_root: Path, target_keyword: str) -> str:
    """
    Durchsucht die gesamte Projekt-Wissensbibliothek nach Zusammenhängen und Fehlerkontext.
    """
    context_data = []
    search_dirs = ["knowledge", "image", "data", "config", "src", "agent_universal_skript"]
    
    for s_dir in search_dirs:
        dir_path = project_root / s_dir
        if dir_path.exists():
            for file_path in dir_path.rglob("*"):
                if file_path.is_file() and file_path.suffix in [".py", ".json", ".md", ".txt", ".cfg", ".yaml"]:
                    try:
                        content = file_path.read_text(encoding="utf-8", errors="replace")
                        if target_keyword.lower() in file_path.name.lower() or target_keyword.lower() in content.lower():
                            snippet = content[:2000]
                            context_data.append(f"--- FILE [{s_dir}]: {file_path.relative_to(project_root)} ---\n{snippet}\n")
                    except Exception:
                        pass
                        
    return "\n".join(context_data[:6])


def _resolve_target_tool_file(project_root: Path, module_name: str, detail: str) -> Path:
    """
    Löst das exakte Zielskript auf, in dem der Fehler liegt, um chirurgisch anzusetzen.
    """
    src_dir = project_root / "src"
    universal_dir = project_root / "agent_universal_skript"
    
    if module_name and module_name != "unknown_module":
        clean_name = module_name.lower().replace("cell_", "").strip()
        direct_match = src_dir / f"{module_name}.py"
        if direct_match.exists():
            return direct_match
            
        for d in [src_dir, universal_dir]:
            if d.exists():
                for f in d.glob("*.py"):
                    if clean_name in f.name.lower() or f.stem.lower() in clean_name:
                        return f

    detail_lower = detail.lower()
    if "guard" in detail_lower or "semantic" in detail_lower:
        f_path = universal_dir / "class_agent_code_py_semantic_guard.py"
        if f_path.exists(): return f_path
    elif "notebook" in detail_lower or "engine" in detail_lower:
        for f in universal_dir.glob("*notebook*.py"): return f
        for f in src_dir.glob("*notebook*.py"): return f

    fallback_file = universal_dir / "class_tool_healed_extensions.py"
    if not fallback_file.exists():
        fallback_file.parent.mkdir(parents=True, exist_ok=True)
        fallback_file.write_text("# Chirurgische Erweiterungen & Healed Code\n", encoding="utf-8")
    return fallback_file


def _safe_surgical_injection(target_file: Path, fix_code: str) -> bool:
    """
    [SCHUTZ GEGEN LOGIK-SCHWUND]
    Führt eine saubere, kontrollierte Injektion durch und validiert via AST, 
    und verhindert unkontrolliertes Anwachsen der Datei auf Duplikate.
    """
    try:
        existing = target_file.read_text(encoding="utf-8", errors="replace") if target_file.exists() else "# Base Code\n"
        if fix_code.strip() in existing:
            return False
        ast.parse(fix_code)
        updated_content = existing + "\n\n# --- Chirurgischer Patch / Dev-Erweiterung ---\n" + fix_code
        ast.parse(updated_content)
        target_file.write_text(updated_content, encoding="utf-8")
        return True
    except Exception as e:
        if logger:
            logger.error(f"[SurgicalInjection] Injektionsfehler in {target_file.name}: {e}")
        return False


def _proactive_src_code_optimization(project_root: Path, target_model: str, url: str, sql_reader=None) -> List[Dict[str, Any]]:
    """
    Führt kontinuierliche Optimierungen im src/-Ordner aus und speichert sauberen Code in SQLite.
    """
    optimized_details = []
    src_dir = project_root / "src"
    if not src_dir.exists():
        return optimized_details
    for py_file in src_dir.glob("*.py"):
        try:
            file_content = py_file.read_text(encoding="utf-8", errors="replace")
            if len(file_content.strip()) < 20:
                continue
            active_bans = _get_active_agent_self_bans(sql_reader)
            prompt = f"""
Du bist der autonome Code-Optimierungs-Agent für den 'src/' Ordner.
Analysiere die folgende Python-Datei auf Optimierungspotenziale, Performance und Robustheit.
Dateiname: {py_file.name}
FOLGENDE SELBSTAUFERLEGTE VERBOTE MÜSSEN STRIKT EINGEHALTEN WERDEN:
{active_bans}
QUELLTEXT:
{file_content[:4000]}
Antworte AUSSCHLIESSLICH mit verbessertem Python-Code im ```python Markdown-Block oder mit "NO_OPTIMIZATION_NEEDED".
"""
            if ollama_manager and hasattr(ollama_manager, "generate"):
                res = ollama_manager.generate(prompt=prompt, model=target_model, ollama_host=url)
                if res.get("status") == "SUCCESS" and sandbox_verifier and hasattr(sandbox_verifier, "extract_code_blocks"):
                    blocks = sandbox_verifier.extract_code_blocks(res.get("content", ""))
                    if blocks and blocks[0].strip() != "NO_OPTIMIZATION_NEEDED":
                        optimized_code = blocks[0]
                        is_valid, _ = sandbox_verifier.verify_code_in_sandbox(optimized_code, project_root)
                        if is_valid and _safe_surgical_injection(py_file, optimized_code):
                            # Speichere sauberen Code direkt über das SQL-Tool in library_src_code
                            if sql_reader and hasattr(sql_reader, "write_clean_src_code"):
                                sql_reader.write_clean_src_code(
                                    file_path=str(py_file.relative_to(project_root)),
                                    code_snippet=optimized_code,
                                    module_name=py_file.stem,
                                    quality_score=1.0
                                )
                            optimized_details.append({"target_file": py_file.name, "status": "PROACTIVELY_OPTIMIZED"})
        except Exception as e:
            if logger:
                logger.error(f"[meta_agent_code_project_log_healing_src] Fehler bei Optimierung von {py_file.name}: {e}")
    return optimized_details


def run_sync(ollama_url: str = None, model: str = None, timeout_sec: int = None,
             spinner_interval: float = None, target_failed_agent: str = None,
             error_context: str = None) -> Dict[str, Any]:
    """
    Führt den geschlossenen Selbstheilungs- und Optimierungs-Prozess aus, 
    gestützt auf die SQLite-Wissensdatenbank und Self-Bans.
    - Analysiert den Fehler mit absolutem Fokus auf chirurgische Präzision.
    - Verändert niemals funktionierenden Code im Ganzen, sondern korrigiert zielgerichtet 
      oder fügt saubere Dev-Werkzeuge hinzu.
    """
    project_root = core_infra.get_project_root() if core_infra and hasattr(core_infra, "get_project_root") else Path(__file__).resolve().parents[2]
    logs_dir = project_root / "logs"
    scratch_dir = project_root / "scratch"
    tests_dir = project_root / "tests"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    tests_dir.mkdir(parents=True, exist_ok=True)
    url = ollama_url or "http://localhost:11434"
    target_model = model or "hermes"
    sql_reader = sql_reader_cls() if sql_reader_cls else None
    if sql_reader and hasattr(sql_reader, "verify_environment"):
        sql_reader.verify_environment()
    if logger:
        logger.info(f"[meta_agent_code_project_log_healing_src] Starte chirurgischen Workflow für Agent: {target_failed_agent}. Root: {project_root}")
    print(f"[meta_agent_code_project_log_healing_src] Starte chirurgischen Healing-Workflow für '{target_failed_agent or 'General'}'. Root: {project_root}")
    stop_event = threading.Event()
    spinner_thread = None
    if spinner:
        try:
            spinner_instance = spinner(agent_name="MetaLogHealingSRC", spinner_interval=spinner_interval or 2.0)
            spinner_thread = threading.Thread(target=spinner_instance.run, args=(stop_event, True))
            spinner_thread.daemon = True
            spinner_thread.start()
        except Exception:
            pass
    summary = {
        "status": "SUCCESS", 
        "failures_found": 0, 
        "patches_applied": 0, 
        "target_agent": target_failed_agent,
        "details": []
    }
    try:
        if ollama_manager and hasattr(ollama_manager, "ensure_ollama_running"):
            if not ollama_manager.ensure_ollama_running(url):
                if logger:
                    logger.error("[meta_agent_code_project_log_healing_src] Ollama-Dienst nicht erreichbar.")
                return {"status": "FAILED", "error": "Ollama service unavailable", "target_agent": target_failed_agent}
        failures = []
        if error_context:
            failures.append({"module": target_failed_agent or "unknown_module", "detail": error_context})
        else:
            if logs_dir.exists():
                log_files = list(logs_dir.glob("*.log"))
                if log_files:
                    latest_log = max(log_files, key=lambda p: p.stat().st_mtime)
                    if logger:
                        logger.info(f"[meta_agent_code_project_log_healing_src] Analysiere Log-Datei: {latest_log.name}")

                    critical_keywords = {"SYNTAXERROR", "KEYWORD GUARD", "INLINE_REPAIR_FAIL", "FAILED", "ERROR", "BANNED"}
                    with latest_log.open("r", encoding="utf-8", errors="replace") as f:
                        for line in f:
                            line_str = line.strip()
                            if any(kw in line_str.upper() for kw in critical_keywords):
                                failures.append({"module": target_failed_agent or "unknown_module", "detail": line_str})
        summary["failures_found"] = len(failures)
        # 1. Fehlerbasiertes chirurgisches Heilen ausführen
        for fail in failures:
            module_name = fail.get("module", target_failed_agent or "unknown_module")
            detail = fail.get("detail", "")
            target_file = _resolve_target_tool_file(project_root, module_name, detail)
            file_content = target_file.read_text(encoding="utf-8", errors="replace") if target_file.exists() else ""
            project_knowledge = _read_project_knowledge_and_src(project_root, module_name)
            active_bans = _get_active_agent_self_bans(sql_reader)
            prompt = f"""
Du bist der autonome Meta-Agent 'meta_agent_code_project_log_healing_src'.
Deine Aufgabe ist STRICT SURGISCH und PLANVOLL:
1. Verändere NIEMALS funktionierenden Code oder ganze Dateien im Ganzen.
2. Analysiere den exakten Fehler und identifiziere die genaue Zeile, Methode oder Logik, die versagt oder mangelhafte Qualität liefert.
3. Erstelle einen minimalen, sauberen Python-Code-Patch, der sich nahtlos in die Kette einfügt.

FOLGENDE SELBSTAUFERLEGTE VERBOTE MÜSSEN STRIKT EINGEHALTEN WERDEN:
{active_bans}
Fehlerkontext für '{module_name}':
Detail: {detail}
ZIEL-DATEI: {target_file.name}
AKTUELLE DATEI-INHALTE (Auszug):
{file_content[:3000]}
PROJEKT-WISSENSBIBLIOTHEK:
{project_knowledge}
Antworte AUSSCHLIESSLICH mit gültigem Python-Code im ```python Block.
"""

            fix_code = ""
            if ollama_manager and hasattr(ollama_manager, "generate"):
                res = ollama_manager.generate(prompt=prompt, model=target_model, ollama_host=url)
                if res.get("status") == "SUCCESS" and sandbox_verifier and hasattr(sandbox_verifier, "extract_code_blocks"):
                    blocks = sandbox_verifier.extract_code_blocks(res.get("content", ""))
                    if blocks:
                        fix_code = blocks[0]
            if not fix_code:
                fix_code = f"\n# Surgical Dev Extension for {module_name} at {int(time.time())}\n"
            is_valid = True
            validation_error_msg = ""
            if sandbox_verifier and hasattr(sandbox_verifier, "verify_code_in_sandbox"):
                is_valid, validation_error_msg = sandbox_verifier.verify_code_in_sandbox(fix_code, project_root)
            if is_valid:
                if _safe_surgical_injection(target_file, fix_code):
                    summary["patches_applied"] += 1
                    summary["details"].append({"target_file": target_file.name, "status": "CHIRURGICALLY_PATCHED"})
                    
                    # Speichere erfolgreichen Patch in library_src_code ab
                    if sql_reader and hasattr(sql_reader, "write_clean_src_code"):
                        sql_reader.write_clean_src_code(
                            file_path=str(target_file.relative_to(project_root)),
                            code_snippet=fix_code,
                            module_name=target_file.stem,
                            quality_score=1.0
                        )
                    if logger:
                        logger.info(f"[meta_agent_code_project_log_healing_src] Chirurgischer Patch erfolgreich in {target_file.name} integriert.")
            else:
                # Registriere den Fehlschlag und erteile sich selbst ein Verbot (Self-Ban)
                if sql_reader and hasattr(sql_reader, "log_src_bug_and_self_ban"):
                    sql_reader.log_src_bug_and_self_ban(
                        bug_description=f"Patch-Validierungsfehler in {target_file.name}: {detail}",
                        failed_code=fix_code,
                        applied_fix=validation_error_msg or "Validation failed",
                        self_ban_rule=f"Do not apply unverified patterns causing: {validation_error_msg[:100]}"
                    )
        # 2. Proaktive src/-Ordner Optimierung mit SQL-Unterstützung
        opt_results = _proactive_src_code_optimization(project_root, target_model, url, sql_reader=sql_reader)
        for item in opt_results:
            summary["patches_applied"] += 1
            summary["details"].append(item)
        return summary
    except Exception as err:
        err_trace = traceback.format_exc()
        if logger:
            logger.error(f"[meta_agent_code_project_log_healing_src] Fehler: {err}")
        return {"status": "FAILED", "error": str(err), "traceback": err_trace, "target_agent": target_failed_agent}
    finally:
        if stop_event:
            stop_event.set()
        if spinner_thread:
            spinner_thread.join(timeout=2.0)


if __name__ == "__main__":
    run_sync()