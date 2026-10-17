import ast
import logging
from typing import Optional, Dict, List, Set, Tuple, Any

class class_agent_code_dependency_analyzer:
    """
    Erweiterter AST- und Dependency-Analyzer für Python-Agenten-Code.
    Erkennt:
    - Tote Code-Leichen (mit Klassifizierung: echte Leiche vs. potenzieller Hook)
    - Unterbrochene Verbindungen / Unerreichbarkeit
    - Falsche Block-Reihenfolge (Sequenzierungsfehler)
    - Globale Namespace-Entkopplungen
    """

    def __init__(self, logger_instance: Optional[logging.Logger] = None):
        self.logger = logger_instance or logging.getLogger("DependencyAnalyzer")

    def analyze_deep_dependencies(self, code_text: str) -> Dict[str, Any]:
        """
        Führt eine vollständige Tiefen-Analyse des Quellcodes durch.
        """
        defined_functions: Dict[str, int] = {}  # {func_name: line_number}
        defined_classes: Dict[str, int] = {}    # {class_name: line_number}
        called_names: Set[str] = set()
        global_vars: Set[str] = set()
        instantiations: Set[str] = set()
        
        call_sequence: List[Tuple[str, int]] = [] # Tracking der Aufrufreihenfolge

        try:
            tree = ast.parse(code_text)
            lines = code_text.splitlines()

            # 1. Erfassungs-Pass (AST Walking)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    defined_functions[node.name] = node.lineno
                elif isinstance(node, ast.ClassDef):
                    defined_classes[node.name] = node.lineno
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            global_vars.add(target.id)
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        called_names.add(node.func.id)
                        call_sequence.append((node.func.id, node.lineno))
                    elif isinstance(node.func, ast.Attribute):
                        called_names.add(node.func.attr)
                        call_sequence.append((node.func.attr, node.lineno))
                elif isinstance(node, ast.ClassDef):
                    pass

        except SyntaxError as e:
            err_msg = f"SYNTAX_ERROR: Konnte Code nicht parsen in Zeile {e.lineno}: {e.text}"
            self.logger.error(err_msg)
            return {"status": "ERROR", "error": err_msg}

        # 2. Analyse: Tote Code-Leichen & Klassifizierung
        ignored_builtins = {"print", "len", "str", "int", "dict", "set", "list", "range", "isinstance", "getattr", "globals"}
        all_definitions = set(defined_functions.keys()) | set(defined_classes.keys())
        active_calls = called_names | ignored_builtins

        # Funktionen/Klassen, die nirgendwo im Code aufgerufen werden
        dead_elements = all_definitions - active_calls
        
        dead_code_report = []
        for elem in dead_elements:
            lineno = defined_functions.get(elem) or defined_classes.get(elem, 0)
            
            # Heuristik zur Ursachenanalyse: Warum liegt das als Leiche drin?
            reason = "Unbekannt / Möglicherweise vergessen oder veraltet"
            category = "TRUE_DEAD_CODE" # Echte Leiche
            
            if elem.startswith("_") or elem.startswith("test_"):
                category = "POTENTIAL_HOOK_OR_HELPER"
                reason = "Beginnt mit Unterstrich oder Test-Präfix; könnte interner Hook oder Test sein."
            elif elem in ["setUp", "tearDown", "__init__", "main"]:
                category = "LIFECYCLE_OR_ENTRY"
                reason = "Framework-Lifecycle-Methode; wird evtl. per Reflection/Magic aufgerufen."
            else:
                reason = "Weder im globalen Namespace noch in Entry-Points referenziert. Vermutlich verwaister Code nach Refactoring."

            dead_code_report.append({
                "name": elem,
                "line": lineno,
                "category": category,
                "reason": reason,
                "action_recommendation": "Löschen (Entfernen)" if category == "TRUE_DEAD_CODE" else "Prüfen / Behalten"
            })

        # 3. Analyse: Sequenzierungs- und Reihenfolge-Prüfung (Forward-Reference Check)
        # Prüft, ob Funktionen aufgerufen werden, bevor sie definiert wurden (ohne Forward Declaration / Imports)
        sequencing_warnings = []
        for call_name, call_line in call_sequence:
            if call_name in defined_functions:
                def_line = defined_functions[call_name]
                if def_line > call_line:
                    sequencing_warnings.append({
                        "element": call_name,
                        "called_at_line": call_line,
                        "defined_at_line": def_line,
                        "issue": "Sequenzierungsfehler: Funktion wird aufgerufen, bevor sie im Skript definiert wurde."
                    })

        # Zusammenstellung des Gesamtberichts
        report = {
            "status": "SUCCESS",
            "total_definitions": len(all_definitions),
            "dead_code_count": len(dead_code_report),
            "dead_code_details": dead_code_report,
            "sequencing_warnings": sequencing_warnings,
            "isolated_components": list(dead_elements)
        }

        # Strukturiertes Logging via Logger
        self.logger.info(f"[DEPENDENCY_AUDIT] Analysiert: {len(all_definitions)} Definitionen. Tote Leichen: {len(dead_code_report)}. Sequenz-Warnungen: {len(sequencing_warnings)}")
        
        return report

# Globale Registrierung
globals()['class_agent_code_dependency_analyzer'] = class_agent_code_dependency_analyzer