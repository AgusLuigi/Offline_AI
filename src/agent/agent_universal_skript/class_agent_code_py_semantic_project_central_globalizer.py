import ast
import re
from pathlib import Path
from typing import Tuple, List

# Versuche den globalen Ollama-Manager zu laden
ollama_manager = globals().get('class_tool_ollama_service_manager')
logger = globals().get('class_logger_audit_execution')

class class_agent_code_py_semantic_project_central_globalizer:
    """
    Zentrale SSOT-Zentralisierungs- und Globalisierungs-Engine.
    Erkennt identische Definitionen (DEFs) und fusioniert sie nach Produktbereichen.
    Erweitert um ein transaktionales 5-Stufen-Sicherheitsnetz gegen Code-Zerstörung.
    - Agenten-Werkzeuge landen im 'agent_universal_skript' / 'class_tool_sql_reader'.
    - Eigenständige Anwendungen (Docker, Installer, Security) bleiben isoliert in ihrer App.
    """
    def __init__(self, src_path: Path):
        self.src_path = src_path

    def detect_target_domain(self, file_path: Path, func_name: str) -> Tuple[str, str]:
        """Ermittelt anhand des Pfads und Namens die korrekte Domäne für die Globalisierung."""
        path_str = str(file_path.resolve()).lower()
        func_lower = func_name.lower()

        if "agent" in path_str or any(k in func_lower for k in ["sql", "query", "prompt", "llm", "ollama"]):
            return "AGENT_CORE", "class_tool_sql_reader"

        if "docker" in path_str or "docker" in func_lower:
            return "APP_DOCKER", "docker_app_core"
        if "install" in path_str or "install" in func_lower:
            return "APP_INSTALLER", "install_app_core"
        if "security" in path_str or "protect" in func_lower:
            return "APP_SECURITY", "security_app_core"

        return "INDIVIDUAL_PRODUCT", "main_app_core"

    def execute_quality_merge(self, target_agent_path: Path, duplicate_element_name: str) -> bool:
        """
        Fusioniert zwei identische Funktionen zu einer Master-Version (Zwei zu Eins).
        Nutzt ein transaktionales Backup- und AST-Validierungsverfahren.
        """
        # STUFE 1: IST-ZUSTAND ERMITTELN & IN-MEMORY SNAPSHOT
        domain_type, target_tool = self.detect_target_domain(target_agent_path, duplicate_element_name)
        matches = list(self.src_path.rglob(f"{target_tool}.py"))
        if not matches:
            return False
        
        central_tool_path = matches[0]
        
        # Sicherung des Ist-Zustands im RAM für Rollback-Fähigkeit
        orig_local_code = target_agent_path.read_text(encoding="utf-8", errors="replace")
        orig_central_code = central_tool_path.read_text(encoding="utf-8", errors="replace")

        try:
            # Vorabprüfung der syntaktischen Integrität des Ist-Zustands
            ast.parse(orig_local_code)
            ast.parse(orig_central_code)
            
            local_ast = ast.parse(orig_local_code)
            extracted_func = ""
            for node in ast.walk(local_ast):
                if isinstance(node, ast.FunctionDef) and node.name == duplicate_element_name:
                    extracted_func = ast.unparse(node)
                    break

            if not extracted_func:
                return False

            # STUFE 2 & 3: PLANUNG & AUSFÜHRUNG (CORRETTO ALLINEAMENTO)
            if not ollama_manager:
                if logger: 
                    logger.warning("Ollama Manager nicht im globalen Workspace registriert.", module="Globalizer")
                return False

            prompt = f"""You are an advanced software architect. Your goal is to eliminate code fragmentation.
We need to merge a function named '{duplicate_element_name}' into its rightful home: '{target_tool}.py' ({domain_type}).

[NEW LOGIC TO INTEGRATE]:
{extracted_func}

[CURRENT CONTENT OF TARGET FILE]:
{orig_central_code}

CRITICAL INSTRUCTIONS:
1. Merge the implementations. If one has extra options or better quality, combine them without data loss.
2. Return the COMPLETE updated Python file content inside python markdown blocks. No text.
"""
            res = ollama_manager.generate(prompt=prompt, model="codestral", ollama_host="http://localhost:11434")
            if not res or res.get("status") != "SUCCESS":
                return False
            blocks = re.findall(r"```(?:python|py)?\s*(.*?)\s*```", res.get("content", ""), re.DOTALL)
            if not blocks:
                return False
            new_central_code = blocks[0].strip()
            # Lokale Bereinigung beim Agenten via AST vorbereiten
            class FunctionPurger(ast.NodeTransformer):
                def visit_FunctionDef(self, node_in):
                    if node_in.name == duplicate_element_name:
                        return None
                    return node_in

            # ALLINEATO ESTERNAMENTE ALLA CLASSE INTERNA: Flusso operativo principale
            clean_ast = FunctionPurger().visit(ast.parse(orig_local_code))
            ast.fix_missing_locations(clean_ast)
            new_local_code = ast.unparse(clean_ast)

            # Transaktionales Schreiben in temporäre Schatten-Dateien (.tmp)
            tmp_central_path = central_tool_path.with_suffix(".py.tmp")
            tmp_local_path = target_agent_path.with_suffix(".py.tmp")

            tmp_central_path.write_text(new_central_code, encoding="utf-8")
            tmp_local_path.write_text(new_local_code, encoding="utf-8")

            # STUFE 4 & 5: VERIFIKATION (HAT DIE AUSFÜHRUNG RICHTIG GEGRIFFEN?)
            try:
                # Syntaktische Prüfung der Modifikationen
                parsed_tmp_central = ast.parse(new_central_code)
                parsed_tmp_local = ast.parse(new_local_code)

                # Semantische Prüfung: Befindet sich die Funktion im Master?
                has_merged_func = any(isinstance(n, ast.FunctionDef) and n.name == duplicate_element_name for n in ast.walk(parsed_tmp_central))
                # Semantische Prüfung: Ist die Funktion lokal gelöscht?
                is_purged_locally = not any(isinstance(n, ast.FunctionDef) and n.name == duplicate_element_name for n in ast.walk(parsed_tmp_local))

                if not has_merged_func:
                    raise ValueError("Das LLM hat die Funktion im Master-Tool weggelassen (Code-Schwund).")
                if not is_purged_locally:
                    raise ValueError("Die lokale Funktion konnte im AST nicht sauber entfernt werden.")

                # Wenn alle Schranken fehlerfrei passiert wurden: Atomarer Austausch
                tmp_central_path.replace(central_tool_path)
                tmp_local_path.replace(target_agent_path)
        
                if logger: 
                    logger.write_log("Repair", "OK", module=target_agent_path.name, detail=f"Zwei-zu-Eins Fusion für {duplicate_element_name} erfolgreich validiert.")
                return True

            except (SyntaxError, ValueError) as verification_error:
                # Rollback-Sicherung: Tmp-Dateien verwerfen, Quellcode bleibt unberührt
                if tmp_central_path.exists(): tmp_central_path.unlink()
                if tmp_local_path.exists(): tmp_local_path.unlink()
                if logger: 
                    logger.error(f"Sicherheits-Abweisung beim Mergen von '{duplicate_element_name}': {verification_error}", module="Globalizer")
                return False

        except Exception as global_error:
            if logger: 
                logger.critical(f"Kritischer Systemfehler bei Globalisierung: {global_error}", module="Globalizer")
            return False
