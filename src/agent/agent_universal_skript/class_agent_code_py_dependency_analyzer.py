from __future__ import annotations
import ast
import hashlib
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
    - Duplizierte Codeblöcke / Funktionen via Funktions-Hash-Vergleich (Bug #13)
    """

    def __init__(self, logger_instance: Optional[logging.Logger] = None):
        self.logger = logger_instance or logging.getLogger("DependencyAnalyzer")

    def _calculate_function_hash(self, node: ast.FunctionDef) -> str:
        """Berechnet einen MD5-Hash des Funktionsinhalts zur Duplizier-Erkennung (Bug #13)."""
        try:
            code_segment = ast.unparse(node)
            # Whitespace normalisieren für verlässlichen Hash-Vergleich
            normalized_code = "".join(code_segment.split())
            return hashlib.md5(normalized_code.encode('utf-8')).hexdigest()
        except Exception:
            return ""

    def analyze_deep_dependencies(self, code_text: str) -> Dict[str, Any]:
        """
        Führt eine vollständige Tiefen-Analyse des Quellcodes inklusive Duplikat- und Sequenz-Prüfung durch.
        """
        defined_functions: Dict[str, int] = {}  # {func_name: line_number}
        defined_classes: Dict[str, int] = {}    # {class_name: line_number}
        function_hashes: Dict[str, List[str]] = {} # {hash: [func_names]}
        called_names: Set[str] = set()
        global_vars: Set[str] = set()
        
        call_sequence: List[Tuple[str, int]] = [] # Tracking der Aufrufreihenfolge

        try:
            tree = ast.parse(code_text)

            # 1. Erfassungs-Pass (AST Walking)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    defined_functions[node.name] = node.lineno
                    
                    # Duplikat-Erkennung via Funktions-Hash vorbereiten (Bug #13)
                    func_hash = self._calculate_function_hash(node)
                    if func_hash:
                        if func_hash not in function_hashes:
                            function_hashes[func_hash] = []
                        function_hashes[func_hash].append(node.name)

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

        except SyntaxError as e:
            err_msg = f"SYNTAX_ERROR: Konnte Code nicht parsen in Zeile {e.lineno}: {e.text}"
            self.logger.error(err_msg)
            return {"status": "ERROR", "error": err_msg}

        # 2. Analyse: Tote Code-Leichen & Klassifizierung
        ignored_builtins = {"print", "len", "str", "int", "dict", "set", "list", "range", "isinstance", "getattr", "globals"}
        all_definitions = set(defined_functions.keys()) | set(defined_classes.keys())
        active_calls = called_names | ignored_builtins

        dead_elements = all_definitions - active_calls
        
        dead_code_report = []
        for elem in dead_elements:
            lineno = defined_functions.get(elem) or defined_classes.get(elem, 0)
            
            reason = "Unbekannt / Möglicherweise vergessen oder veraltet"
            category = "TRUE_DEAD_CODE"
            
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

        # 3. Analyse: Duplizierte Codeblöcke / Funktionen (Bug #13)
        duplicate_warnings = []
        for f_hash, names in function_hashes.items():
            if len(names) > 1:
                duplicate_warnings.append({
                    "duplicate_functions": names,
                    "issue": "Duplizierung von Codeblöcken: Mehrfaches Auftreten identischer Funktionsstrukturen im Skript."
                })

        # 4. Analyse: Sequenzierungs- und Reihenfolge-Prüfung
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

        report = {
            "status": "SUCCESS",
            "total_definitions": len(all_definitions),
            "dead_code_count": len(dead_code_report),
            "dead_code_details": dead_code_report,
            "duplicate_code_warnings": duplicate_warnings,
            "sequencing_warnings": sequencing_warnings,
            "isolated_components": list(dead_elements)
        }
        self.logger.info(f"[DEPENDENCY_AUDIT] Analysiert: {len(all_definitions)} Definitionen. Tote Leichen: {len(dead_code_report)}. Duplikate: {len(duplicate_warnings)}. Sequenz-Warnungen: {len(sequencing_warnings)}") 
        return report


# Globale Registrierung
globals()['class_agent_code_dependency_analyzer'] = class_agent_code_dependency_analyzer