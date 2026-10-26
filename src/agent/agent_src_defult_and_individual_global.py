import datetime as _dt
import json
import logging
import platform
import re
import sys
import threading
import time
import ast
from pathlib import Path
from collections import Counter
from typing import Dict, List, Tuple

# Optionaler psutil-Import für präzise RAM-Erkennung
try:
    import psutil
except ImportError:
    psutil = None

# Automatischer Bootstrap und Registrierung aller universellen Werkzeuge
try:
    from agent_universal_skript.auto_bootstrap_and_register_agent_tools import auto_bootstrap_and_register_agent_tools
    auto_bootstrap_and_register_agent_tools()
except ImportError:
    pass

# Zentrale globale Aliase mit sicherer Fallback-Logik direkt nach Bootstrap
logger = globals().get('class_logger_audit_execution')
ollama_manager = globals().get('class_tool_ollama_service_manager')
notebook_engine = globals().get('class_agent_notebook_scientific_engine')
stochastic_pre_guard = globals().get('class_code_py_stochastic_pre_guard')
semantic_guard = globals().get('class_agent_code_py_semantic_guard')
semantic_project_globalizer = globals().get('class_agent_code_py_semantic_project_central_globalizer')
dependency_analyzer = globals().get('class_code_py_dependency_analyzer')
format_tool = globals().get('class_code_py_iso_iec_25010_format_tool')
sandbox_verifier = globals().get('class_agent_sub_verifier')
spinner = globals().get('class_tool_resource_aware_spinner')

# Zentraler Import des BertLayer / Structural Classifiers aus dem Tool-Ordner
bert_layer_classifier = globals().get('class_code_py_bert_structural_classifier')

# Workflow-individuelle Laufzeit-Konfiguration für den Ist-Zustand
if "_GLOBAL_RUNTIME_CONFIG" not in globals():
    globals()["_GLOBAL_RUNTIME_CONFIG"] = {}

def Globale_exist(defaults_table: dict):
    """
    Prüft, ob Parameter bereits im globalen RAM existieren.
    Existieren sie: Werden sie beibehalten (Schutz des Live-Ist-Zustands).
    Existieren sie nicht: Werden die Defaults einmalig geladen.
    """
    runtime_config = globals()["_GLOBAL_RUNTIME_CONFIG"]
    for key, default_value in defaults_table.items():
        if key not in runtime_config:
            runtime_config[key] = default_value

# Hartcodierte Grundeinstellungen des Workflows & LAYA-Spezifikationen
_WORKFLOW_DEFAULT_CONFIG = {
    "OLLAMA_URL": "http://localhost:11434",
    "MODEL": "hermes",
    "DIR_SRC": "src",
    "SPINNER_INTERVAL": 2,
    "TIMEOUT_OLLAMA_SEC": 1800,
    "LAYA_AGENT_MAX_TOKENS": 4096,
    "LAYA_AGENT_CPU_LIMIT": 2,
    "LAYA_AGENT_CLOCK_SEC": 0.5,
    "LAYA_AUTO_INSTALLER_MODE": True
}

Globale_exist(_WORKFLOW_DEFAULT_CONFIG)


class class_laya_behavioral_specification_engine:
    """
    LAYA Sub-Model: Autonome Offline-Logik- & Spezifikations-Engine für Agenten.
    Definiert individuelle Ressourcengrenzen und steuert das agentenspezifische Verhalten.
    """
    def __init__(self, agent_config: dict = None):
        self.config = agent_config or globals()["_GLOBAL_RUNTIME_CONFIG"]
        self.max_tokens = self.config.get("LAYA_AGENT_MAX_TOKENS", 4096)
        self.cpu_limit = self.config.get("LAYA_AGENT_CPU_LIMIT", 2)
        self.clock_sec = self.config.get("LAYA_AGENT_CLOCK_SEC", 0.5)

    def enforce_minimum_specifications(self, target_params: dict) -> dict:
        """
        Erzwingt agentenspezifische Mindestwerte, sofern keine individuellen Vorgaben existieren.
        """
        validated = target_params.copy()
        validated.setdefault("max_tokens", self.max_tokens)
        validated.setdefault("cpu_limit", self.cpu_limit)
        validated.setdefault("clock_sec", self.clock_sec)
        return validated


def build_dynamic_project_taxonomy(all_keys: list, all_values: list) -> dict:
    """
    STOCHASTISCH-MECHANISCHE PROJEKT-ANALYSE & SCORING:
    Analysiert Vorkommen, Häufigkeiten und Sinnhaftigkeit von Pfaden und Ordnerbezeichnungen
    im src/-Ordner, um sie auf einen globalen Standard zu vereinheitlichen.
    """
    mapping = {}
    suffix_dir_count = sum(1 for k in all_keys if k.endswith("_DIR") and k != "DIR")
    prefix_dir_count = sum(1 for k in all_keys if k.startswith("DIR_") and k != "DIR")
    target_is_prefix = prefix_dir_count >= suffix_dir_count

    for k, v in zip(all_keys, all_values):
        val_str = str(v).lower()
        is_path_like = isinstance(v, str) and ('/' in val_str or '\\' in val_str or any(val_str.endswith(ext) for ext in ['.db', '.json', '.txt', '.py', '.log', '.csv']))
        is_dir_like = isinstance(v, str) and not is_path_like and val_str in ['src', 'config', 'data', 'logs', 'models', 'knowledge', 'notebooks', 'cache', 'output', 'assets', 'Knowledge', 'Config']

        clean_base = k
        for token in ['_DIR', 'DIR_', '_PATH', 'PATH_', '_CONFIG', 'CONFIG_', '_FOLDER', 'FOLDER_']:
            clean_base = clean_base.replace(token, '')
        clean_base = re.sub(r'[^a-zA-Z0-9_]', '_', clean_base).strip('_').upper()

        if is_dir_like or 'DIR' in k.upper() or 'FOLDER' in k.upper():
            mapping[k] = f"DIR_{clean_base}" if target_is_prefix else f"{clean_base}_DIR"
        elif is_path_like or 'PATH' in k.upper() or 'FILE' in k.upper():
            mapping[k] = f"PATH_{clean_base}"
        elif 'URL' in k.upper() or 'HOST' in k.upper() or val_str.startswith(('http://', 'https://')):
            mapping[k] = f"URL_{clean_base}" if 'URL' in k.upper() else f"HOST_{clean_base}"
        else:
            mapping[k] = clean_base
    return mapping


class class_variable_renamer(ast.NodeTransformer):
    """
    AST-Transformer zur skriptweiten Ersetzung alter Variablennamen 
    durch die normalisierten globalen Begriffe (NameError-Schutz).
    """
    def __init__(self, rename_map: dict):
        self.rename_map = rename_map

    def visit_Name(self, node):
        if node.id in self.rename_map:
            node.id = self.rename_map[node.id]
        return self.generic_visit(node)


def run_secure_agent_pipeline(file_path: Path, raw_generated_code: str) -> Tuple[bool, str]:
    """
    INTEGRAZIONE DELLA NUOVA PIPELINE NELLO SCRIPT PRINCIPALE:
    Orchestratore transazionale a 5 stadi. Esegue controlli preventivi stocastici,
    formattazione ISO, analisi profonda delle dipendenze e verifica in Sandbox isolata
    prima di effettuare qualsiasi commit atomico su disco, preservando la logica esistente.
    """
    original_code = file_path.read_text(encoding="utf-8", errors="replace")

    # Stadio 2: Pulizia stocastica e indentazione automatica (except/with)
    if stochastic_pre_guard:
        working_code = stochastic_pre_guard.global_stochastic_pre_guard(raw_generated_code)
    else:
        working_code = raw_generated_code

    # Stadio 3: Formattazione estetica e allineamento simmetrico delle assegnazioni
    if format_tool:
        formatter = format_tool()
        success_fmt, formatted_code, fmt_msg = formatter.format_code(working_code)
        if not success_fmt:
            return False, f"Format Tool respinto: {fmt_msg}"
        working_code = formatted_code

    # Stadio 4: Audit AST delle dipendenze e controllo inversione temporale delle chiamate
    if dependency_analyzer:
        analyzer = dependency_analyzer()
        audit_report = analyzer.analyze_deep_dependencies(working_code)
        if audit_report.get("status") == "ERROR":
            return False, f"Errore analisi dipendenze: {audit_report.get('error')}"
        if audit_report.get("sequencing_warnings"):
            return False, "Errore di sequenza lineare delle chiamate rilevato nell'AST."

    # Stadio 5: Esecuzione in Sandbox isolata (scratch/) per intercettare crash o eccezioni a runtime
    if sandbox_verifier:
        success_sandbox, sandbox_msg = sandbox_verifier.verify_code_in_sandbox(working_code)
        if not success_sandbox:
            return False, f"Violazione di runtime in Sandbox: {sandbox_msg}"

    # Validazione finale sull'imbuto semantico protetto (Anti-Shrinkage e conservazione logica)
    if semantic_guard and 'project_semantic_guard' in globals():
        guard_success, final_code, guard_msg = globals()['project_semantic_guard'].evaluate_and_repair(original_code, working_code)
        if not guard_success:
            return False, f"Barriera semantica finale infranta: {guard_msg}"
        working_code = final_code

    # Commit Atomico transazionale su disco
    try:
        tmp_file = file_path.with_suffix(".py.committed.tmp")
        tmp_file.write_text(working_code, encoding="utf-8")
        tmp_file.replace(file_path)
        return True, "Pipeline completata con successo. Logica preservata e codice integrato."
    except Exception as e:
        return False, f"Errore OS durante il commit finale: {e}"


def run_config(src_dir: str = None, model: str = None, spinner_interval: float = None) -> dict:
    runtime_cfg = globals()["_GLOBAL_RUNTIME_CONFIG"]
    effective_src_dir = src_dir or runtime_cfg.get("DIR_SRC", "src")
    src_path = Path(effective_src_dir)
    laya_engine = class_laya_behavioral_specification_engine(runtime_cfg)
    
    structural_classifier = None
    if bert_layer_classifier:
        structural_classifier = bert_layer_classifier(
            max_tokens=runtime_cfg.get("LAYA_AGENT_MAX_TOKENS", 4096)
        )

    project_globalizer = None
    if semantic_project_globalizer:
        project_globalizer = semantic_project_globalizer(src_path=src_path)

    if logger:
        logger.initialize_logger()
    pc_id = platform.node() or "LocalWorkflowAgent"

    def log_action(phase, event, module="ConfigGlobalizer", detail=""):
        if logger:
            logger.write_log(pc_id, phase, event, module=module, detail=detail)
            if event in [logger.LOG_EVENT_STEP_ACTION, logger.LOG_EVENT_SESSION_START]:
                logger.info(detail, module=module)
            elif event == logger.LOG_EVENT_BANNED:
                logger.warning(detail, module=module)
            elif event in [logger.LOG_EVENT_INLINE_REPAIR_FAIL, logger.LOG_EVENT_RETRY_EXHAUSTED]:
                logger.error(detail, module=module)
        else:
            print(f"[{module}] {detail}")

    log_action(
        logger.LOG_PHASE_SESSION if logger else "Session",
        logger.LOG_EVENT_SESSION_START if logger else "Start",
        detail="Globalisierungs-Workflow mit BertLayer-Struktur-Klassifizierung und AST-Rewriting gestartet"
    )

    steps_performed = []

    if not src_path.exists():
        log_action("Error", "Fail", detail=f"Zielordner {src_path} nicht gefunden.")
        return {"status": "FAILED", "error": f"Pfad {src_path} existiert nicht."}

    steps_performed.append(f"Arbeitsbereich verifiziert: {src_path.resolve()}")

    py_files = list(src_path.rglob("*.py"))
    total_files = len(py_files)

    raw_extracted_keys_per_file = {}
    file_parsed_data = {}
    all_project_keys = []
    all_project_values = []
    file_contents_map = {}

    for file_path in py_files:
        if "agent_src_defult_and_individual_global" in file_path.name or "agent_ipynb" in file_path.name:
            continue
        try:
            raw_content = file_path.read_text(encoding="utf-8", errors="replace")
            
            cleaned_lines = []
            for line in raw_content.splitlines():
                if re.match(r'^\s*#\s*[-=]{3,}', line) or re.match(r'^\s*[-=]{3,}', line):
                    continue
                cleaned_lines.append(line)
            content = "\n".join(cleaned_lines)
            file_contents_map[file_path] = content

            tree = ast.parse(content)
            extracted = {}
            functions_to_merge = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id.isupper():
                            try:
                                code_repr = ast.unparse(node.value) if hasattr(ast, "unparse") else str(node.value)
                                extracted[target.id] = code_repr
                                all_project_keys.append(target.id)
                                all_project_values.append(code_repr)
                            except Exception:
                                pass
                elif isinstance(node, ast.FunctionDef):
                    functions_to_merge.append(node.name)
            
            # 3. NEU: Ausführung des Quality-Merges für gefundene Funktionen
            if 'project_globalizer' in locals() and project_globalizer:
                for func_name in functions_to_merge:
                    try:
                        # Startet den Merge-Prozess (Zwei zu Eins) in der Master-Komponente
                        success = project_globalizer.execute_quality_merge(file_path, func_name)
                        if success and logger:
                            logger.info(
                                f"Funktion '{func_name}' erfolgreich in Master-Domäne fusioniert und lokal bereinigt.",
                                module=file_path.name
                            )
                    except Exception:
                        pass
                content = file_path.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(content)
            raw_extracted_keys_per_file[file_path] = extracted
            file_parsed_data[file_path] = {
                "content": content,
                "tree": tree,
                "has_classes": any(isinstance(node, ast.ClassDef) for node in ast.walk(tree))
            }
        except Exception as e:
            pass

    if structural_classifier:
        cluster_mapping = structural_classifier.evaluate_code_similarity_and_grouping(file_contents_map)
        steps_performed.append(f"BertLayer Classifier hat {len(cluster_mapping)} Dateien analysiert und gruppiert.")

    project_taxonomy_map = build_dynamic_project_taxonomy(all_project_keys, all_project_values)

    file_semantic_maps = {}
    config_value_counters = {}
    key_position_sums = {}
    key_position_counts = {}

    for file_path, extracted in raw_extracted_keys_per_file.items():
        file_map = {}
        norm_extracted = {}
        for k, v_repr in extracted.items():
            norm_k = project_taxonomy_map.get(k, k)
            file_map[k] = norm_k
            norm_extracted[norm_k] = v_repr
            
            if norm_k not in config_value_counters:
                config_value_counters[norm_k] = Counter()
            config_value_counters[norm_k][v_repr] += 1

        file_semantic_maps[file_path] = file_map

        for idx, norm_k in enumerate(norm_extracted.keys()):
            key_position_sums[norm_k] = key_position_sums.get(norm_k, 0) + idx
            key_position_counts[norm_k] = key_position_counts.get(norm_k, 0) + 1

        file_parsed_data[file_path]["extracted"] = norm_extracted

    unified_global_consensus = {}
    for k, counter in config_value_counters.items():
        most_common_repr = counter.most_common(1)[0][0]
        unified_global_consensus[k] = most_common_repr

    consensus_order_rank = {}
    for k, total_pos in key_position_sums.items():
        consensus_order_rank[k] = total_pos / key_position_counts[k]

    steps_performed.append(f"Stochastische Projekt-Taxonomie & Scoring angewendet. {len(unified_global_consensus)} Parameter harmonisiert.")
    
    modified_tools = 0
    modified_workflows = 0
    errors_encountered = []

    for file_path, data in file_parsed_data.items():
        try:
            content = data["content"]
            has_classes = data["has_classes"]
            
            is_workflow_script = not has_classes or ("def run_config" in content or "if __name__" in content and not has_classes)
            
            has_double_assignments = bool(re.search(r'^\s*([A-Z0-9_]+)\s*=\s*\1\s*$', content, re.MULTILINE))
            if "_cfg.setdefault" in content and not has_double_assignments and "_WORKFLOW_CONFIG_TABLE" in content:
                continue
            if not data["extracted"]:
                continue

            file_old_to_new = file_semantic_maps.get(file_path, {})

            sorted_extracted_items = sorted(
                data["extracted"].items(),
                key=lambda item: (
                    0 if item[0].startswith("DIR_") else (1 if item[0].startswith("PATH_") else 2),
                    consensus_order_rank.get(item[0], 999)
                )
            )

            if "meta_coder" in file_path.name.lower():
                sorted_extracted_items = [item for item in sorted_extracted_items if item[0] not in ["ALLOWED_TABLES", "DOMAIN"]]

            tool_specs = laya_engine.enforce_minimum_specifications({
                "file": file_path.name,
                "items_count": len(sorted_extracted_items)
            })

            # Generazione del blocco di codice normalizzato ed elaborazione degli alias
            if is_workflow_script:
                clean_extracted_items = [item for item in sorted_extracted_items if not (item[1].strip().isupper() and item[1].strip() in [x[0] for x in sorted_extracted_items])]
                config_entries = ",\n    ".join([f'"{k}": {unified_global_consensus.get(k, v)}' for k, v in clean_extracted_items])
                
                local_aliases = []
                for k, v in clean_extracted_items:
                    consensus_val = unified_global_consensus.get(k, v)
                    if isinstance(consensus_val, str) and ("os." in consensus_val or "re." in consensus_val or "get_project_root" in consensus_val):
                        local_aliases.append(f'{k} = _runtime_cfg.get("{k}", {consensus_val})')
                    else:
                        local_aliases.append(f'{k} = _runtime_cfg.get("{k}", {repr(consensus_val) if not consensus_val.startswith("(") and not consensus_val.startswith("{") else consensus_val})')
                local_aliases_str = "\n".join(local_aliases)

                boilerplate = f'''
# Zentral harmonisierte Workflow-Laufzeit-Konfiguration (SSOT-konform)
if "_GLOBAL_RUNTIME_CONFIG" not in globals():
    globals()["_GLOBAL_RUNTIME_CONFIG"] = {{}}
def Globale_exist(defaults_table: dict):
    runtime_config = globals()["_GLOBAL_RUNTIME_CONFIG"]
    for key, default_value in defaults_table.items():
        if key not in runtime_config:
            runtime_config[key] = default_value
_WORKFLOW_CONFIG_TABLE = {{
    {config_entries}
}}
Globale_exist(_WORKFLOW_CONFIG_TABLE)
# Lokale Namespace-Aliase als direkte Anbindung an den globalen RAM (Single Source of Truth)
_runtime_cfg = globals()["_GLOBAL_RUNTIME_CONFIG"]
{local_aliases_str}
'''
                tree = ast.parse(content)
                transformed_tree = class_variable_renamer(file_old_to_new).visit(tree)
                ast.fix_missing_locations(transformed_tree)
                transformed_code = ast.unparse(transformed_tree)
                lines = transformed_code.splitlines()
                filtered_lines = [line for line in lines if not (any(line.strip().startswith(f"{new_k} =") for new_k in file_old_to_new.values()) and not line.strip().startswith(("if ", "def ")))]
                insert_idx = 0
                for i, line in enumerate(filtered_lines):
                    if line.startswith("import ") or line.startswith("from "):
                        insert_idx = i + 1
                filtered_lines.insert(insert_idx, boilerplate)
                new_code = "\n".join(filtered_lines)
                modified_workflows += 1
            else:
                tree = ast.parse(content)
                transformed_tree = class_variable_renamer(file_old_to_new).visit(tree)
                ast.fix_missing_locations(transformed_tree)
                transformed_code = ast.unparse(transformed_tree)if hasattr(ast, "unparse") else content
                einzeiler_lines = [
                '    # Globalen Runtime-RAM im Namespace sicherstellen',
                '    if "_GLOBAL_RUNTIME_CONFIG" not in globals():',
                '        globals()["_GLOBAL_RUNTIME_CONFIG"] = {}',
                f'    # LAYA Agenten-Mindestwerte & Ressourcen: Max Tokens: {tool_specs["max_tokens"]}, CPU: {tool_specs["cpu_limit"]}',
                '    _cfg = globals()["_GLOBAL_RUNTIME_CONFIG"]',
                '    # Klassentinterne Standards mit Fallback-Schutz'
                ]
                for k, v in sorted_extracted_items:
                    consensus_expr = unified_global_consensus.get(k, v)
                    if consensus_expr.strip() == k or f'"{k}"' in consensus_expr and k in consensus_expr:
                        continue
                    einzeiler_lines.append(f'    {k} = _cfg.setdefault("{k}", {consensus_expr})')
                boilerplate = "\n".join(einzeiler_lines) + "\n"
                class_match = re.search(r'(class\s+\w+.*?):', transformed_code)
                if class_match:
                    class_def_end = transformed_code.find(':', class_match.start()) + 1
                    docstring_match = re.search(r'(""".*?"""|\'\'\'.*?\'\'\')', transformed_code[class_def_end:], re.DOTALL)
                    insert_pos = class_def_end + docstring_match.end() if docstring_match else class_def_end
                    if transformed_code[insert_pos:insert_pos+50].strip().startswith(("except", "with")):
                        next_newline = transformed_code.find('\n', insert_pos)
                        if next_newline != -1: insert_pos = next_newline + 1
                    code_with_class_config = transformed_code[:insert_pos] + "\n" + boilerplate + transformed_code[insert_pos:]
                else:
                    code_with_class_config = boilerplate + "\n" + transformed_code
                cleaned_lines = []
                inside_class = False
                for line in code_with_class_config.splitlines():
                    if line.strip().startswith("class "): inside_class = True
                    if not inside_class and any(line.strip().startswith(f"{new_k} =") for new_k in file_old_to_new.values()): continue
                    if re.match(r'^\s*([A-Z0-9_]+)\s*=\s*\1\s*$', line.strip()): continue
                    cleaned_lines.append(line)
                new_code = "\n".join(cleaned_lines)
                modified_tools += 1

            success_pipeline, msg_pipeline = run_secure_agent_pipeline(file_path, new_code)
            if success_pipeline:
               log_action("Repair", "OK", module=file_path.name, detail=msg_pipeline)
            else:
                errors_encountered.append({"file": file_path.name, "error": msg_pipeline})
                log_action("Repair", "Fail", module=file_path.name, detail=msg_pipeline)
        except Exception as e:
            errors_encountered.append({"file": file_path.name, "error": str(e)})
            log_action("Repair",
            "Fail",
            module=file_path.name,
            detail=f"Fehler: {str(e)}"
            )
    steps_performed.append(f"Refactoring abgeschlossen: {modified_tools} Tool-Klassen, {modified_workflows} Workflows harmonisiert.")
    print("ABSCHLUSSBERICHT: VOLLSTÄNDIGE HARMONISIERUNG & AST-SICHERUNG")
    print("\n[1] ZUSAMMENFASSUNG DER SCHRITTE:")
    for i, step in enumerate(steps_performed, 1):
        print(f"  {i}. {step}")
    print("\n[2] METRIKEN:")
    print(f" • Gescannte Dateien gesamt:    {total_files}")
    print(f" • Harmonisierte Tool-Klassen:  {modified_tools}")
    print(f" • Harmonisierte Workflows:     {modified_workflows}")
    print(f" • Aufgetretene Fehler:         {len(errors_encountered)}")
    return {
        "status": "SUCCESS",
        "scanned": total_files,
        "tools_modified": modified_tools,
        "workflows_modified": modified_workflows,
        "errors": errors_encountered
    }
globals()['run_config'] = run_config
if __name__ == "__main__":
    run_config()