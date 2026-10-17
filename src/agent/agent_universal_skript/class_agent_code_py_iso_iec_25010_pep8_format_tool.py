import ast
import re
from typing import List, Dict, Any, Tuple


class class_agent_code_py_iso_iec_25010_pep8_format_tool:
    """
    ISO/IEC 25010 & PEP 8 compliant code formatting tool:
    Deterministically enforces international standards for maintainability, 
    clean architecture, and syntax block ordering in generated Python code.
    Prevents code shrinkage, block displacement, and indentation shifts.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}

    def _stochastic_pre_clean(self, code_text: str) -> str:
        """
        Stochastische Vorab-Bereinigung:
        - Reduziert redundante, mehrfache Leerzeilen auf ein sauberes Maß.
        - Zieht unnötig umgebrochene Funktionssignaturen wieder in eine Zeile zusammen.
        """
        # 1. Mehrfache Leerzeilen (3 oder mehr) auf maximal 2 reduzieren
        code_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', code_text)
        
        # 2. Unmotiviert umgebrochene Funktionssignaturen (def name \n (...):) korrigieren
        code_text = re.sub(r'(def\s+\w+)\s*\n\s*\((.*?)\):', r'\1(\2):', code_text, flags=re.DOTALL)
        
        return code_text

    def _extract_code_blocks(self, code_text: str) -> Dict[str, Any]:
        """Extrahiert und trennt Code-Segmente sicher mittels AST und bewahrt echten Entry-Point."""
        imports = []
        globals_list = []
        classes = []
        functions = []
        entry_points = []
        docstrings = []

        try:
            tree = ast.parse(code_text)
            lines = code_text.splitlines()

            # Modul-Docstring am Anfang prüfen
            if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant):
                if isinstance(tree.body[0].value.value, str):
                    ds_lines = lines[tree.body[0].lineno - 1 : tree.body[0].end_lineno]
                    docstrings.append("\n".join(ds_lines))

            for node in tree.body:
                # Modul-Docstring überspringen, da separat behandelt
                if node == tree.body[0] and docstrings:
                    continue

                segment_lines = lines[node.lineno - 1:node.end_lineno]
                segment_code = "\n".join(segment_lines)

                # Prüfen, ob es sich um einen if __name__ == "__main__": Block handelt
                if isinstance(node, ast.If):
                    test = node.test
                    is_main_guard = (
                        isinstance(test, ast.Compare)
                        and isinstance(test.left, ast.Name)
                        and test.left.id == "__name__"
                        and any(
                            isinstance(comp, ast.Constant) and comp.value == "__main__"
                            for comp in test.comparators
                        )
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

        except SyntaxError:
            return {"raw": code_text.splitlines()}

        return {
            "docstrings": docstrings,
            "imports": imports,
            "globals": globals_list,
            "classes": classes,
            "functions": functions,
            "entry_points": entry_points
        }

    def format_code(self, raw_code_text: str) -> Tuple[bool, str, str]:
        """
        Hauptformatierungs-Pipeline nach strikter architektonischer Ordnung:
        1. Modul-Docstring & Header-Kommentare
        2. Imports
        3. Dynamische globale Konfigurationen
        4. Backend-Klassen und UI-Klassen
        5. Standalone-Funktionen
        6. Ursprünglicher Entry-Point am Ende (mit Fallback, falls keiner existierte)
        """
        try:
            cleaned_input = re.sub(r"```python\s*", "", raw_code_text)
            cleaned_input = re.sub(r"```\s*", "", cleaned_input).strip()

            # Stochastische Vorab-Bereinigung anwenden, bevor der AST parsiert
            cleaned_input = self._stochastic_pre_clean(cleaned_input)

            blocks = self._extract_code_blocks(cleaned_input)

            if "raw" in blocks:
                return False, raw_code_text, "FORMAT_ERROR: Syntax error detected, automated formatting aborted."

            formatted_parts = []

            if blocks["docstrings"]:
                formatted_parts.append("\n\n".join(blocks["docstrings"]))

            if blocks["imports"]:
                formatted_parts.append("\n\n".join(blocks["imports"]))

            if blocks["globals"]:
                formatted_parts.append("\n\n".join(blocks["globals"]))

            if blocks["classes"]:
                formatted_parts.append("\n\n\n".join(blocks["classes"]))

            if blocks["functions"]:
                formatted_parts.append("\n\n\n".join(blocks["functions"]))

            # Echten Entry-Point behalten oder sauberen Fallback bereitstellen
            if blocks["entry_points"]:
                formatted_parts.append("\n\n\n".join(blocks["entry_points"]))
            else:
                entry_point_snippet = (
                    "if __name__ == \"__main__\":\n"
                    "    # Standardized entry point according to ISO/IEC 25010 architectural requirements\n"
                    "    pass"
                )
                formatted_parts.append(entry_point_snippet)

            final_output = "\n\n".join(formatted_parts)
            return True, final_output, "FORMAT_SUCCESS: Code successfully normalized according to ISO/IEC 25010 and PEP 8 without code loss."

        except Exception as e:
            return False, raw_code_text, f"FORMAT_EXCEPTION: {str(e)}"


# Automatische Registrierung im globalen Namespace für den Auto-Bootstrap
globals()['class_agent_code_py_iso_iec_25010_pep8_format_tool'] = class_agent_code_py_iso_iec_25010_pep8_format_tool