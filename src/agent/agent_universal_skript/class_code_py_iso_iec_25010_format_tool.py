"""
Modul: class_code_py_iso_iec_25010_format_tool
Bezeichnung: ISO/IEC 25010 & PEP 8 Code-Formatierungswerkzeug
Inhaltlicher Schwerpunkt:
Deterministische Normalisierung von Python-Quellcode durch lineare Gliederung
(Docstrings, Imports, globale Zuweisungen, Klassen, Funktionen, Entry-Point)
sowie Standardisierung von Leerzeilen, Zuweisungssymmetrie und Interpunktion.
"""

from __future__ import annotations
import ast
import re
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple

# Globale Bindings
logger = globals().get("class_logger_audit_execution")


class class_code_py_iso_iec_25010_format_tool:
    """
    Formatierungswerkzeug zur Herstellung von Softwarequalität nach ISO/IEC 25010 und PEP 8.
    Strukturiert Quellcodedateien architektonisch sauber und deterministisch.
    """

    _cfg = globals().setdefault("_AGENT_CONFIG", {})
    ALIGN_SYMMETRY: bool = _cfg.setdefault("ALIGN_SYMMETRY", True)
    ENFORCE_SINGLE_LINE_SIGNATURES: bool = _cfg.setdefault("ENFORCE_SINGLE_LINE_SIGNATURES", True)
    MAX_CONSECUTIVE_BLANK_LINES: int = _cfg.setdefault("MAX_CONSECUTIVE_BLANK_LINES", 2)
    MAX_TARGET_NAME_LENGTH: int = _cfg.setdefault("MAX_TARGET_NAME_LENGTH", 40)

    def __init__(self, config: Dict[str, Any] = None):
        print("[class_code_py_iso_iec_25010_format_tool] Starte Arbeit: __init__ wird jetzt ausgeführt.")
        cfg = config or {}
        self.align_symmetry = cfg.get("align_symmetry", self.ALIGN_SYMMETRY)
        self.enforce_single_line_signatures = cfg.get("enforce_single_line_signatures", self.ENFORCE_SINGLE_LINE_SIGNATURES)
        self.max_consecutive_blank_lines = cfg.get("max_consecutive_blank_lines", self.MAX_CONSECUTIVE_BLANK_LINES)
        self.max_target_name_length = cfg.get("max_target_name_length", self.MAX_TARGET_NAME_LENGTH)

        print(f"[class_code_py_iso_iec_25010_format_tool] Erfolg: __init__ erfolgreich beendet.")

    def _stochastic_pre_clean(self, code_text: str) -> str:
        """Bereinigt überschüssige Leerzeilen und komprimiert Funktionssignaturen."""
        print("[class_code_py_iso_iec_25010_format_tool] Starte Arbeit: _stochastic_pre_clean wird jetzt ausgeführt.")
        blank_pattern = r"\n\s*" + r"\n\s*" * self.max_consecutive_blank_lines + r"+"
        code_text = re.sub(blank_pattern, "\n" * (self.max_consecutive_blank_lines + 1), code_text)

        if self.enforce_single_line_signatures:
            code_text = re.sub(r"(def\s+\w+)\s*\n\s*(.*?):", r"\1(\2):", code_text, flags=re.DOTALL)

        if self.align_symmetry:
            code_text = self._align_assignment_symmetry(code_text)
            code_text = self._align_brackets_and_commas(code_text)

        if not code_text:
            print("[class_code_py_iso_iec_25010_format_tool] FEHLER: _stochastic_pre_clean hat die Aufgabe nicht erfüllt. Grund: Ergebnis ist leer.")
            return ""

        print(f"[class_code_py_iso_iec_25010_format_tool] Erfolg: _stochastic_pre_clean erfolgreich beendet.")
        return code_text

    def _align_assignment_symmetry(self, code_text: str) -> str:
        """Richtet Zuweisungsoperatoren in zusammenhängenden Blöcken symmetrisch aus."""
        print("[class_code_py_iso_iec_25010_format_tool] Starte Arbeit: _align_assignment_symmetry wird jetzt ausgeführt.")
        lines = code_text.splitlines()
        aligned_lines = []
        block = []

        def flush_block(blk: List[str]):
            if len(blk) < 2:
                aligned_lines.extend(blk)
                return
            parsed_block = []
            for l in blk:
                m = re.match(r"^(\s*)([\w\.\:\[\],\s]+?)\s*=\s*(.+)$", l)
                if m and not l.strip().startswith("#") and "==" not in l and "+=" not in l:
                    indent, target, val = m.group(1), m.group(2).strip(), m.group(3).strip()
                    parsed_block.append((indent, target, val))
                else:
                    aligned_lines.extend(blk)
                    return
            max_target_len = max(len(target) for _, target, _ in parsed_block)
            if max_target_len > self.max_target_name_length:
                aligned_lines.extend(blk)
                return
            for indent, target, val in parsed_block:
                aligned_lines.append(f"{indent}{target.ljust(max_target_len)} = {val}")

        for line in lines:
            is_assign = bool(re.match(r"^\s*[\w\.\:\[\],\s]+?\s*=\s*[^=].*$", line)) and not line.strip().startswith("#")
            if is_assign and "==" not in line and "+=" not in line and "-=" not in line and "*=" not in line:
                block.append(line)
            else:
                if block:
                    flush_block(block)
                    block = []
                aligned_lines.append(line)
        if block:
            flush_block(block)

        result = "\n".join(aligned_lines)

        if not result and code_text:
            print("[class_code_py_iso_iec_25010_format_tool] FEHLER: _align_assignment_symmetry hat die Aufgabe nicht erfüllt. Grund: Ergebnis ist leer, obwohl Eingabe vorhanden.")
            return code_text

        print(f"[class_code_py_iso_iec_25010_format_tool] Erfolg: _align_assignment_symmetry erfolgreich beendet.")
        return result

    @staticmethod
    def _align_brackets_and_commas(code_text: str) -> str:
        """Setzt deterministisch ein Leerzeichen nach jedem Komma außerhalb von Strings."""
        print("[class_code_py_iso_iec_25010_format_tool] Starte Arbeit: _align_brackets_and_commas wird jetzt ausgeführt.")
        lines = code_text.splitlines()
        processed_lines = []
        for line in lines:
            if "," in line and not line.strip().startswith("#") and '"' not in line and "'" not in line:
                line = re.sub(r",(?=\S)", ", ", line)
            processed_lines.append(line)

        result = "\n".join(processed_lines)

        if not result and code_text:
            print("[class_code_py_iso_iec_25010_format_tool] FEHLER: _align_brackets_and_commas hat die Aufgabe nicht erfüllt. Grund: Ergebnis ist leer.")
            return code_text

        print(f"[class_code_py_iso_iec_25010_format_tool] Erfolg: _align_brackets_and_commas erfolgreich beendet.")
        return result

    @staticmethod
    def _sort_global_variables(globals_block: List[str]) -> List[str]:
        """Sortiert Zuweisungen auf Modulebene alphabetisch nach Bezeichner."""
        print("[class_code_py_iso_iec_25010_format_tool] Starte Arbeit: _sort_global_variables wird jetzt ausgeführt.")
        if not globals_block:
            print("[class_code_py_iso_iec_25010_format_tool] Erfolg: _sort_global_variables erfolgreich beendet. (Leerer Block, nichts zu sortieren)")
            return []
        assignment_lines = [l for l in globals_block if "=" in l and not l.strip().startswith("#")]
        other_lines = [l for l in globals_block if l not in assignment_lines]
        assignment_lines.sort(key=lambda x: x.strip().split("=")[0].strip())
        result = other_lines + assignment_lines

        print(f"[class_code_py_iso_iec_25010_format_tool] Erfolg: _sort_global_variables erfolgreich beendet. ({len(result)} Zeilen sortiert)")
        return result

    def _extract_code_blocks(self, code_text: str) -> Dict[str, Any]:
        """Gliedert Python-Code per AST-Knoten in strukturelle Abschnitte."""
        print("[class_code_py_iso_iec_25010_format_tool] Starte Arbeit: _extract_code_blocks wird jetzt ausgeführt.")
        imports, globals_list, classes, functions, entry_points, docstrings = [], [], [], [], [], []

        try:
            tree = ast.parse(code_text)
            lines = code_text.splitlines()

            if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant):
                if isinstance(tree.body[0].value.value, str):
                    ds_lines = lines[tree.body[0].lineno - 1: tree.body[0].end_lineno]
                    docstrings.append("\n".join(ds_lines))

            for node in tree.body:
                if node == tree.body[0] and docstrings:
                    continue

                segment_lines = lines[node.lineno - 1: node.end_lineno]
                segment_code = "\n".join(segment_lines)

                if isinstance(node, ast.If):
                    test = node.test
                    is_main_guard = (
                        isinstance(test, ast.Compare)
                        and isinstance(test.left, ast.Name)
                        and test.left.id == "__name__"
                        and any(isinstance(c, ast.Constant) and c.value == "__main__" for c in test.comparators)
                    )
                    if is_main_guard:
                        entry_points.append(segment_code)
                        continue

                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    imports.append(segment_code)
                elif isinstance(node, ast.ClassDef):
                    classes.append(segment_code)
                elif isinstance(node, ast.FunctionDef):
                    functions.append(segment_code)
                else:
                    globals_list.append(segment_code)

        except SyntaxError as e:
            print(f"[class_code_py_iso_iec_25010_format_tool] FEHLER: _extract_code_blocks hat die Aufgabe nicht erfüllt. Grund: SyntaxError beim Zerlegen: {e}")
            return {"raw": code_text.splitlines()}

        sorted_globals = self._sort_global_variables(globals_list)
        result = {
            "docstrings": docstrings,
            "imports": imports,
            "globals": sorted_globals,
            "classes": classes,
            "functions": functions,
            "entry_points": entry_points
        }

        if result is None:
            print("[class_code_py_iso_iec_25010_format_tool] FEHLER: _extract_code_blocks hat die Aufgabe nicht erfüllt. Grund: Ergebnis-Dictionary ist None.")
            return {"raw": code_text.splitlines()}

        print(f"[class_code_py_iso_iec_25010_format_tool] Erfolg: _extract_code_blocks erfolgreich beendet. ({len(imports)} Imports, {len(classes)} Klassen)")
        return result

    def format_code(self, raw_code_text: str) -> Tuple[bool, str, str]:
        """Führt die geordnete Formatierungs-Pipeline nach ISO/IEC 25010 aus."""
        print("[class_code_py_iso_iec_25010_format_tool] Starte Arbeit: format_code wird jetzt ausgeführt.")
        try:
            cleaned_input = re.sub(r"```python\s*", "", raw_code_text)
            cleaned_input = re.sub(r"```\s*", "", cleaned_input).strip()

            try:
                ast.parse(cleaned_input)
            except SyntaxError as syntax_err:
                print(f"[class_code_py_iso_iec_25010_format_tool] FEHLER: format_code hat die Aufgabe nicht erfüllt. Grund: Syntax ungültig: {syntax_err}")
                return False, raw_code_text, f"Syntaxfehler im Quelltext: {syntax_err}"

            cleaned_input = self._stochastic_pre_clean(cleaned_input)
            blocks = self._extract_code_blocks(cleaned_input)

            if "raw" in blocks:
                print("[class_code_py_iso_iec_25010_format_tool] FEHLER: format_code hat die Aufgabe nicht erfüllt. Grund: Blockextraktion fehlgeschlagen.")
                return False, raw_code_text, "Fehler bei der Blockextraktion."

            formatted_parts = []
            if blocks["docstrings"]: formatted_parts.append("\n\n".join(blocks["docstrings"]))
            if blocks["imports"]: formatted_parts.append("\n\n".join(blocks["imports"]))
            if blocks["globals"]: formatted_parts.append("\n\n".join(blocks["globals"]))
            if blocks["classes"]: formatted_parts.append("\n\n\n".join(blocks["classes"]))
            if blocks["functions"]: formatted_parts.append("\n\n\n".join(blocks["functions"]))

            if blocks["entry_points"]:
                formatted_parts.append("\n\n\n".join(blocks["entry_points"]))
            else:
                entry_point_snippet = "if __name__ == \"__main__\":\n    pass"
                formatted_parts.append(entry_point_snippet)

            final_output = "\n\n".join(formatted_parts)
            ast.parse(final_output)

            print(f"[class_code_py_iso_iec_25010_format_tool] Erfolg: format_code erfolgreich beendet.")
            return True, final_output, "Formatierung erfolgreich abgeschlossen."

        except Exception as e:
            print(f"[class_code_py_iso_iec_25010_format_tool] FEHLER: format_code hat die Aufgabe nicht erfüllt. Grund: Unerwarteter Fehler: {e}")
            return False, raw_code_text, str(e)

    @classmethod
    def run_iso_format_tool(cls, code_text: str) -> dict:
        """
        Zentrale Ausführungsfunktion: Bündelt die Instanziierung und Formatierung
        eines Code-Fragments und liefert das validierte Ergebnis zurück.
        """
        print("[class_code_py_iso_iec_25010_format_tool] Starte Arbeit: run_iso_format_tool wird jetzt ausgeführt.")
        try:
            formatter = cls()
            success, formatted_code, msg = formatter.format_code(code_text)
            result = {
                "success": success,
                "formatted_code": formatted_code,
                "message": msg
            }

            if result is None:
                print("[class_code_py_iso_iec_25010_format_tool] FEHLER: run_iso_format_tool hat die Aufgabe nicht erfüllt. Grund: Kein Ergebnis-Dictionary erzeugt.")
                return None

            if not result["success"]:
                print(f"[class_code_py_iso_iec_25010_format_tool] FEHLER: run_iso_format_tool hat die Aufgabe nicht erfüllt. Grund: {result['message']}")
                return result

            print(f"[class_code_py_iso_iec_25010_format_tool] Erfolg: run_iso_format_tool erfolgreich beendet.")
            return result
        except Exception as e:
            print(f"[class_code_py_iso_iec_25010_format_tool] FEHLER: run_iso_format_tool hat die Aufgabe nicht erfüllt. Grund: {e}")
            return None
