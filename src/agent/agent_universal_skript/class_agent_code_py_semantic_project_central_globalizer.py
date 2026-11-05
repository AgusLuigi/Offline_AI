"""
Modul: class_agent_code_py_semantic_project_central_globalizer
Bezeichnung: Zentrale SSOT-Globalisierungs- und Fusions-Engine
Inhaltlicher Schwerpunkt:
Erkennung redundanter Funktionsdefinitionen und transaktionale Zusammenführung
(Zwei zu Eins) in zentrale Master-Werkzeuge unter Wahrung der AST-Integrität.
"""

from __future__ import annotations
import ast
import re
import sys
from pathlib import Path
from typing import Tuple, List, Optional

# Globale Bindings
logger = globals().get("class_logger_audit_execution")
core_infra = globals().get("class_tool_core_infrastructure")
ollama_manager = globals().get("class_tool_ollama_service_manager")


class class_agent_code_py_semantic_project_central_globalizer:
    """
    Zentralisierungs-Engine zur Eliminierung von Code-Fragmentierung.
    Fusioniert redundante Funktionen transaktional in Master-Module.
    """

    _cfg = globals().setdefault("_AGENT_CONFIG", {})
    MODEL: str = _cfg.setdefault("MODEL", "codestral")
    OLLAMA_HOST: str = _cfg.setdefault("OLLAMA_HOST", "http://127.0.0.1:11434")

    def __init__(self, src_path: Path = None):
        print("[class_agent_code_py_semantic_project_central_globalizer] Starte Arbeit: __init__ wird jetzt ausgeführt.")
        if src_path:
            self.src_path = Path(src_path)
        else:
            infra = globals().get("class_tool_core_infrastructure")
            root = infra.get_project_root() if infra and hasattr(infra, "get_project_root") else Path.cwd()
            self.src_path = root / "src"
        if not hasattr(self, "src_path") or self.src_path is None:
            print("[class_agent_code_py_semantic_project_central_globalizer] FEHLER: __init__ hat die Aufgabe nicht erfüllt. Grund: src_path konnte nicht gesetzt werden.")
            return
        print("[class_agent_code_py_semantic_project_central_globalizer] Erfolg: __init__ erfolgreich beendet.")

    def detect_target_domain(self, file_path: Path, func_name: str) -> Tuple[str, str]:
        """Ermittelt die Ziel-Domäne und das Master-Tool für die Zusammenführung."""
        print(f"[class_agent_code_py_semantic_project_central_globalizer] Starte Arbeit: detect_target_domain wird jetzt ausgeführt. (Parameter: {func_name})")
        path_str = str(file_path.resolve()).lower()
        func_lower = func_name.lower()

        if "agent" in path_str or any(k in func_lower for k in ["sql", "query", "prompt", "llm", "ollama"]):
            result = ("AGENT_CORE", "class_tool_sql_reader")
        elif "docker" in path_str or "docker" in func_lower:
            result = ("APP_DOCKER", "docker_app_core")
        elif "install" in path_str or "install" in func_lower:
            result = ("APP_INSTALLER", "install_app_core")
        elif "security" in path_str or "protect" in func_lower:
            result = ("APP_SECURITY", "security_app_core")
        else:
            result = ("INDIVIDUAL_PRODUCT", "main_app_core")

        if result is None:
            print("[class_agent_code_py_semantic_project_central_globalizer] FEHLER: detect_target_domain hat die Aufgabe nicht erfüllt. Grund: Kein Ergebnis ermittelt.")
            return ("INDIVIDUAL_PRODUCT", "main_app_core")
        print("[class_agent_code_py_semantic_project_central_globalizer] Erfolg: detect_target_domain erfolgreich beendet.")
        return result

    def execute_quality_merge(self, target_agent_path: Path, duplicate_element_name: str) -> bool:
        """Fusioniert eine lokale Funktion in das zentrale Master-Tool."""
        print(f"[class_agent_code_py_semantic_project_central_globalizer] Starte Arbeit: execute_quality_merge wird jetzt ausgeführt. (Parameter: {duplicate_element_name})")
        domain_type, target_tool = self.detect_target_domain(target_agent_path, duplicate_element_name)
        matches = list(self.src_path.rglob(f"{target_tool}.py"))
        if not matches:
            print(f"[class_agent_code_py_semantic_project_central_globalizer] FEHLER: Master-Tool '{target_tool}.py' nicht gefunden.")
            return False

        central_tool_path = matches[0]
        try:
            orig_local_code = target_agent_path.read_text(encoding="utf-8", errors="replace")
            orig_central_code = central_tool_path.read_text(encoding="utf-8", errors="replace")

            ast.parse(orig_local_code)
            ast.parse(orig_central_code)

            local_ast = ast.parse(orig_local_code)
            extracted_func = ""
            for node in ast.walk(local_ast):
                if isinstance(node, ast.FunctionDef) and node.name == duplicate_element_name:
                    extracted_func = ast.unparse(node)
                    break

            if not extracted_func:
                print(f"[class_agent_code_py_semantic_project_central_globalizer] FEHLER: Funktion '{duplicate_element_name}' im lokalen AST nicht gefunden.")
                return False

            mgr = globals().get("class_tool_ollama_service_manager")
            if not mgr:
                print("[class_agent_code_py_semantic_project_central_globalizer] FEHLER: Ollama Manager nicht verfügbar.")
                return False

            prompt = f"""Merge the function '{duplicate_element_name}' into '{target_tool}.py'.
Combine capabilities without losing logic or parameters.

[FUNCTION TO MERGE]:
{extracted_func}

[TARGET FILE CONTENT]:
{orig_central_code[:3000]}

Return the FULL updated file inside a ```python block.
"""
            res = mgr.generate(prompt=prompt, model=self.MODEL, ollama_host=self.OLLAMA_HOST)
            if not res or res.get("status") != "SUCCESS":
                print(f"[class_agent_code_py_semantic_project_central_globalizer] FEHLER: LLM Generierung fehlgeschlagen.")
                return False

            blocks = re.findall(r"```(?:python|py)?\s*(.*?)\s*```", res.get("content", ""), re.DOTALL)
            if not blocks:
                print(f"[class_agent_code_py_semantic_project_central_globalizer] FEHLER: Keine Codeblöcke im LLM-Ergebnis.")
                return False

            new_central_code = blocks[0].strip()

            class FunctionPurger(ast.NodeTransformer):
                def visit_FunctionDef(self, node_in):
                    return None if node_in.name == duplicate_element_name else node_in

            clean_ast = FunctionPurger().visit(ast.parse(orig_local_code))
            ast.fix_missing_locations(clean_ast)
            new_local_code = ast.unparse(clean_ast)

            parsed_central = ast.parse(new_central_code)
            parsed_local = ast.parse(new_local_code)

            has_merged = any(isinstance(n, ast.FunctionDef) and n.name == duplicate_element_name for n in ast.walk(parsed_central))
            if not has_merged:
                print(f"[class_agent_code_py_semantic_project_central_globalizer] FEHLER: Funktion fehlt im Master-Code.")
                return False

            central_tool_path.write_text(new_central_code, encoding="utf-8")
            target_agent_path.write_text(new_local_code, encoding="utf-8")
            result = True
            if result is False or result is None:
                print("[class_agent_code_py_semantic_project_central_globalizer] FEHLER: execute_quality_merge hat die Aufgabe nicht erfüllt. Grund: Fusion fehlgeschlagen.")
                return False
            print("[class_agent_code_py_semantic_project_central_globalizer] Erfolg: execute_quality_merge erfolgreich beendet.")
            return result

        except Exception as e:
            print(f"[class_agent_code_py_semantic_project_central_globalizer] FEHLER: Unerwarteter Fusionsfehler: {e}")
            return False

    @classmethod
    def run_central_globalizer(cls, target_agent_path: Path, duplicate_element_name: str) -> dict:
        """
        Zentrale Ausführungsfunktion: Bündelt die Analyse der Zieldomäne und
        die Ausführung der Qualitätstransaktion.
        """
        print(f"[class_agent_code_py_semantic_project_central_globalizer] Starte Arbeit: run_central_globalizer wird jetzt ausgeführt.")
        try:
            globalizer = cls()
            domain, target_tool = globalizer.detect_target_domain(target_agent_path, duplicate_element_name)
            success = globalizer.execute_quality_merge(target_agent_path, duplicate_element_name)
            result = {
                "success": success,
                "domain": domain,
                "target_tool": target_tool,
                "function": duplicate_element_name
            }
            if result is None:
                print("[class_agent_code_py_semantic_project_central_globalizer] FEHLER: run_central_globalizer hat die Aufgabe nicht erfüllt. Grund: Kein Ergebnis zurückgegeben.")
                return None
            print("[class_agent_code_py_semantic_project_central_globalizer] Erfolg: run_central_globalizer erfolgreich beendet.")
            return result
        except Exception as e:
            print(f"[class_agent_code_py_semantic_project_central_globalizer] FEHLER: In run_central_globalizer: {e}")
            return None
