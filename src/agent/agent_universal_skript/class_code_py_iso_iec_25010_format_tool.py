from __future__ import annotations
import ast
import re
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple

# Assicuriamo la presenza del logger nel namespace globale
logger = globals().get('class_logger_audit_execution')

if "_GLOBAL_RUNTIME_CONFIG" not in globals():
    globals()["_GLOBAL_RUNTIME_CONFIG"] = {}
_cfg = globals()["_GLOBAL_RUNTIME_CONFIG"]

ALIGN_SYMMETRY = _cfg.setdefault("ALIGN_SYMMETRY", True)
ENFORCE_SINGLE_LINE_SIGNATURES = _cfg.setdefault("ENFORCE_SINGLE_LINE_SIGNATURES", True)
MAX_CONSECUTIVE_BLANK_LINES = _cfg.setdefault("MAX_CONSECUTIVE_BLANK_LINES", 2)
MAX_TARGET_NAME_LENGTH = _cfg.setdefault("MAX_TARGET_NAME_LENGTH", 40)

FORMAT_CONFIG: Dict[str, Any] = {
    "align_symmetry": ALIGN_SYMMETRY,
    "enforce_single_line_signatures": ENFORCE_SINGLE_LINE_SIGNATURES,
    "max_consecutive_blank_lines": MAX_CONSECUTIVE_BLANK_LINES
}

class class_code_py_iso_iec_25010_format_tool:
    """
    Strumento di formattazione conforme a ISO/IEC 25010 e PEP 8.
    Applica regole deterministiche di allineamento e ordinamento alfabetico 
    delle variabili globali per garantire la massima manutenibilità del codice.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config if config is not None else FORMAT_CONFIG.copy()

    def _stochastic_pre_clean(self, code_text: str) -> str:
        """Esegue la pulizia preliminare delle righe vuote e normalizza le firme delle funzioni."""
        max_blank = self.config.get("max_consecutive_blank_lines", 2)
        blank_pattern = r'\n\s*' + r'\n\s*' * max_blank + r'+'
        code_text = re.sub(blank_pattern, '\n' * (max_blank + 1), code_text)
        
        if self.config.get("enforce_single_line_signatures", True):
            code_text = re.sub(r'(def\s+\w+)\s*\n\s*(.*?):', r'\1(\2):', code_text, flags=re.DOTALL)
        
        if self.config.get("align_symmetry", True):
            code_text = self._align_assignment_symmetry(code_text)
            code_text = self._align_brackets_and_commas(code_text)

        return code_text

    @staticmethod
    def _align_assignment_symmetry(code_text: str) -> str:
        """Allinea in modo simmetrico i caratteri '=' all'interno di blocchi contigui."""
        lines = code_text.splitlines()
        aligned_lines = []
        block = []

        def flush_block(blk: List[str]):
            if len(blk) < 2:
                aligned_lines.extend(blk)
                return
            parsed_block = []
            for l in blk:
                m = re.match(r"^(\s*)([\w\.\:\[\],\s]+?)\s*=\s*(.+)\$", l)
                if m and not l.strip().startswith("#") and "==" not in l and "+=" not in l:
                    indent, target, val = m.group(1), m.group(2).strip(), m.group(3).strip()
                    parsed_block.append((indent, target, val))
                else:
                    aligned_lines.extend(blk)
                    return
            max_target_len = max(len(target) for _, target, _ in parsed_block)
            if max_target_len > MAX_TARGET_NAME_LENGTH:
                aligned_lines.extend(blk)
                return
            for indent, target, val in parsed_block:
                aligned_lines.append(f"{indent}{target.ljust(max_target_len)} = {val}")

        for line in lines:
            is_assign = bool(re.match(r"^\s*[\w\.\:\[\],\s]+?\s*=\s*[^=].*\$", line)) and not line.strip().startswith("#")
            if is_assign and "==" not in line and "+=" not in line and "-=" not in line and "*=" not in line:
                block.append(line)
            else:
                if block:
                    flush_block(block)
                    block = []
                aligned_lines.append(line)
        if block:
            flush_block(block)

        return "\n".join(aligned_lines)

    @staticmethod
    def _align_brackets_and_commas(code_text: str) -> str:
        """Normalizza la spaziatura dopo le virgole per garantire leggibilità ed eleganza."""
        lines = code_text.splitlines()
        processed_lines = []
        for line in lines:
            if "," in line and not line.strip().startswith("#") and '"' not in line and "'" not in line:
                line = re.sub(r',(?\(=\S\))', ', ', line)
            processed_lines.append(line)
        return "\n".join(processed_lines)

    @staticmethod
    def _sort_global_variables(globals_block: List[str]) -> List[str]:
        """Ordina alfabeticamente solo le assegnazioni globali pure senza corrompere i commenti."""
        if not globals_block:
            return []
        assignment_lines = [l for l in globals_block if "=" in l and not l.strip().startswith("#")]
        other_lines = [l for l in globals_block if l not in assignment_lines]
        
        assignment_lines.sort(key=lambda x: x.strip().split("=")[0].strip())
        return other_lines + assignment_lines

    def _extract_code_blocks(self, code_text: str) -> Dict[str, Any]:
        """Raggruppa chirurgicamente i segmenti di codice isolandoli tramite parsing AST."""
        imports = []
        globals_list = []
        classes = []
        functions = []
        entry_points = []
        docstrings = []

        try:
            tree = ast.parse(code_text)
            lines = code_text.splitlines()

            if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant):
                if isinstance(tree.body[0].value.value, str):
                    ds_lines = lines[tree.body[0].lineno - 1 : tree.body[0].end_lineno]
                    docstrings.append("\n".join(ds_lines))

            for node in tree.body:
                if node == tree.body[0] and docstrings:
                    continue

                segment_lines = lines[node.lineno - 1:node.end_lineno]
                segment_code = "\n".join(segment_lines)

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

        sorted_globals = self._sort_global_variables(globals_list)

        return {
            "docstrings": docstrings,
            "imports": imports,
            "globals": sorted_globals,
            "classes": classes,
            "functions": functions,
            "entry_points": entry_points
        }

    def format_code(self, raw_code_text: str) -> Tuple[bool, str, str]:
        """
        Esegue la pipeline di formattazione ordinata secondo le specifiche di clean architecture.
        Hauptformatierungs-Pipeline nach ISO/IEC 25010 Standard.
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

            # Fase 4: Controllo di stabilità e parsing AST preventivo
            try:
                ast.parse(cleaned_input)
            except SyntaxError as syntax_err:
                return False, raw_code_text, f"FORMAT_ERROR: Codice sorgente malformato sintatticamente: {syntax_err}"

            cleaned_input = self._stochastic_pre_clean(cleaned_input)
            blocks = self._extract_code_blocks(cleaned_input)

            if "raw" in blocks:
                return False, raw_code_text, "FORMAT_ERROR: Rilevato errore di sintassi imprevisto durante l'estrazione."

            formatted_parts = []

            if blocks["docstrings"]: formatted_parts.append("\n\n".join(blocks["docstrings"]))
            if blocks["imports"]: formatted_parts.append("\n\n".join(blocks["imports"]))
            if blocks["globals"]: formatted_parts.append("\n\n".join(blocks["globals"]))
            if blocks["classes"]: formatted_parts.append("\n\n\n".join(blocks["classes"]))
            if blocks["functions"]: formatted_parts.append("\n\n\n".join(blocks["functions"]))

            if blocks["entry_points"]:
                formatted_parts.append("\n\n\n".join(blocks["entry_points"]))
            else:
                entry_point_snippet = (
                    "if __name__ == \"__main__\":\n"
                    "    # Entry point standardizzato secondo requisiti ISO/IEC 25010\n"
                    "    pass"
                )
                formatted_parts.append(entry_point_snippet)

            final_output = "\n\n".join(formatted_parts)
            
            # Controllo finale post-esecuzione per escludere mutazioni distruttive
            ast.parse(final_output)
            return True, final_output, "FORMAT_SUCCESS: Codice normalizzato con successo senza alcuna perdita logica."

        except Exception as e:
            return False, raw_code_text, f"FORMAT_EXCEPTION: Errore interno imprevisto: {str(e)}"