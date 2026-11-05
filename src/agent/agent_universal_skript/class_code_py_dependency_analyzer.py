"""
Modul: class_code_py_dependency_analyzer
Bezeichnung: Tiefer AST-Abhängigkeits- und Struktur-Auditor
Inhaltlicher Schwerpunkt:
Erkennung von totem Code, duplizierten Funktionsimplementierungen (MD5-Hash-Vergleich),
zeitlichen Sequenzierungsfehlern (Aufruf vor Deklaration) und redundanten UI-Definitionen.
"""

from __future__ import annotations
import ast
import hashlib
import sys
from pathlib import Path
from typing import Optional, Dict, List, Set, Tuple, Any

# Globale Bindings
logger = globals().get("class_logger_audit_execution")
core_infra = globals().get("class_tool_core_infrastructure")


class class_code_py_dependency_analyzer:
    """
    Analysiert Abhängigkeiten und Code-Strukturen per AST.
    Identifiziert ungenutzte Blöcke, Duplikate und logische Ablaufbrüche.
    """

    _cfg = globals().setdefault("_AGENT_CONFIG", {})
    IGNORED_BUILTINS: Set[str] = _cfg.setdefault("IGNORED_BUILTINS", {
        "print", "len", "str", "int", "dict", "set", "list", "range",
        "isinstance", "getattr", "globals"
    })
    UI_KEYWORDS: List[str] = _cfg.setdefault("UI_KEYWORDS", [
        "VBox", "HBox", "AppLayout", "GridBox", "Tab", "Accordion", "display"
    ])

    def __init__(self, src_path: Path = None):
        print("[class_code_py_dependency_analyzer] Starte Arbeit: __init__ wird jetzt ausgeführt.")
        if src_path:
            self.path_src = Path(src_path)
        else:
            infra = globals().get("class_tool_core_infrastructure")
            root = infra.get_project_root() if infra and hasattr(infra, "get_project_root") else Path.cwd()
            self.path_src = root / "src"

        if self.path_src is None:
            print("[class_code_py_dependency_analyzer] FEHLER: __init__ hat die Aufgabe nicht erfüllt. Grund: path_src konnte nicht gesetzt werden.")
            return

        print(f"[class_code_py_dependency_analyzer] Erfolg: __init__ erfolgreich beendet. (path_src={self.path_src})")

    @staticmethod
    def _calculate_function_hash(node: ast.FunctionDef) -> str:
        """Erzeugt einen normalisierten MD5-Hash des Funktionskörpers zur Erkennung identischer Logik."""
        print(f"[class_code_py_dependency_analyzer] Starte Arbeit: _calculate_function_hash wird jetzt ausgeführt. (Parameter: node.name={node.name})")
        try:
            code_segment = ast.unparse(node)
            normalized = "".join(code_segment.split())
            result = hashlib.md5(normalized.encode("utf-8")).hexdigest()

            if not result:
                print(f"[class_code_py_dependency_analyzer] FEHLER: _calculate_function_hash hat die Aufgabe nicht erfüllt. Grund: Leerer Hash für '{node.name}'")
                return ""

            print(f"[class_code_py_dependency_analyzer] Erfolg: _calculate_function_hash erfolgreich beendet. (hash={result[:8]}...)")
            return result
        except Exception as e:
            print(f"[class_code_py_dependency_analyzer] FEHLER: _calculate_function_hash hat die Aufgabe nicht erfüllt. Grund: Hash-Berechnung fehlgeschlagen: {e}")
            return ""

    def _scan_for_global_tool_duplicate(self, element_name: str) -> bool:
        """Prüft, ob eine Funktion bereits in einem anderen Modul im Quellverzeichnis existiert."""
        print(f"[class_code_py_dependency_analyzer] Starte Arbeit: _scan_for_global_tool_duplicate wird jetzt ausgeführt. (Parameter: element_name={element_name})")
        if not self.path_src.exists():
            print(f"[class_code_py_dependency_analyzer] Erfolg: _scan_for_global_tool_duplicate erfolgreich beendet. (Quellpfad existiert nicht, False)")
            return False
        try:
            for py_file in self.path_src.rglob("*.py"):
                content = py_file.read_text(encoding="utf-8", errors="ignore")
                if element_name in content:
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef) and node.name == element_name:
                            print(f"[class_code_py_dependency_analyzer] Erfolg: _scan_for_global_tool_duplicate erfolgreich beendet. (Duplikat gefunden: {element_name})")
                            return True
        except Exception as e:
            print(f"[class_code_py_dependency_analyzer] FEHLER: _scan_for_global_tool_duplicate hat die Aufgabe nicht erfüllt. Grund: Scan fehlgeschlagen: {e}")

        print(f"[class_code_py_dependency_analyzer] Erfolg: _scan_for_global_tool_duplicate erfolgreich beendet. (Kein Duplikat gefunden)")
        return False

    def analyze_deep_dependencies(self, code_text: str) -> Dict[str, Any]:
        """Führt eine vollständige semantische Abhängigkeitsanalyse für den übergebenen Code durch."""
        print("[class_code_py_dependency_analyzer] Starte Arbeit: analyze_deep_dependencies wird jetzt ausgeführt.")
        defined_functions: Dict[str, int] = {}
        defined_classes: Dict[str, int] = {}
        function_hashes: Dict[str, List[str]] = {}
        called_names: Set[str] = set()
        global_vars: Set[str] = set()
        call_sequence: List[Tuple[str, int]] = []

        try:
            tree = ast.parse(code_text)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    defined_functions[node.name] = node.lineno
                    f_hash = self._calculate_function_hash(node)
                    if f_hash:
                        function_hashes.setdefault(f_hash, []).append(node.name)
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
            print(f"[class_code_py_dependency_analyzer] FEHLER: analyze_deep_dependencies hat die Aufgabe nicht erfüllt. Grund: SyntaxError im Quelltext: {e}")
            return {"status": "ERROR", "error": str(e)}

        all_definitions = set(defined_functions.keys()) | set(defined_classes.keys())
        active_calls = called_names | self.IGNORED_BUILTINS
        dead_elements = all_definitions - active_calls

        dead_code_report = []
        for elem in dead_elements:
            lineno = defined_functions.get(elem) or defined_classes.get(elem, 0)
            if self._scan_for_global_tool_duplicate(elem):
                category = "GLOBAL_DUPLICATE_POTENTIAL_MERGE"
                reason = "In geteilten globalen Modulen vorhanden."
            elif elem.startswith("_") or elem.startswith("test_"):
                category = "POTENTIAL_HOOK_OR_HELPER"
                reason = "Privater Hook oder Hilfsmethode."
            elif elem in ["setUp", "tearDown", "__init__", "main"]:
                category = "LIFECYCLE_OR_ENTRY"
                reason = "Lifecycle-Methode."
            else:
                category = "TRUE_DEAD_CODE"
                reason = "Nicht referenziert im Codefluss."

            dead_code_report.append({
                "name": elem,
                "line": lineno,
                "category": category,
                "reason": reason
            })

        duplicate_warnings = [
            {"duplicate_functions": names, "issue": "Spiegelbildliche Code-Duplikation"}
            for f_hash, names in function_hashes.items() if len(names) > 1
        ]

        sequencing_warnings = [
            {"element": name, "called_at": c_line, "defined_at": defined_functions[name]}
            for name, c_line in call_sequence
            if name in defined_functions and defined_functions[name] > c_line
        ]

        ui_duplications = []
        for kw in self.UI_KEYWORDS:
            occurrences = [lineno for name, lineno in call_sequence if name == kw]
            if len(occurrences) > 1:
                ui_duplications.append({"ui_element": kw, "lines": occurrences})

        result = {
            "status": "SUCCESS",
            "total_definitions": len(all_definitions),
            "dead_code_count": len(dead_code_report),
            "dead_code_details": dead_code_report,
            "duplicate_code_warnings": duplicate_warnings,
            "duplicate_ui_warnings": ui_duplications,
            "sequencing_warnings": sequencing_warnings,
            "isolated_components": list(dead_elements)
        }

        if result is None:
            print("[class_code_py_dependency_analyzer] FEHLER: analyze_deep_dependencies hat die Aufgabe nicht erfüllt. Grund: Kein Ergebnis-Dictionary erzeugt.")
            return {"status": "ERROR", "error": "Unbekannter Fehler"}

        print(f"[class_code_py_dependency_analyzer] Erfolg: analyze_deep_dependencies erfolgreich beendet. ({len(all_definitions)} Definitionen, {len(dead_code_report)} tote Elemente)")
        return result

    @classmethod
    def run_dependency_analyzer(cls, code_text: str, src_path: Path = None) -> dict:
        """
        Zentrale Ausführungsfunktion: Führt die vollständige Abhängigkeits- und Qualitätsprüfung
        durch und fasst alle Warnungen und Metriken zusammen.
        """
        print("[class_code_py_dependency_analyzer] Starte Arbeit: run_dependency_analyzer wird jetzt ausgeführt.")
        try:
            analyzer = cls(src_path=src_path)
            report = analyzer.analyze_deep_dependencies(code_text)

            if report is None or report.get("status") == "ERROR":
                print(f"[class_code_py_dependency_analyzer] FEHLER: run_dependency_analyzer hat die Aufgabe nicht erfüllt. Grund: Analysebericht fehlerhaft: {report}")
                return report

            print(f"[class_code_py_dependency_analyzer] Erfolg: run_dependency_analyzer erfolgreich beendet.")
            return report
        except Exception as e:
            print(f"[class_code_py_dependency_analyzer] FEHLER: run_dependency_analyzer hat die Aufgabe nicht erfüllt. Grund: {e}")
            return None
