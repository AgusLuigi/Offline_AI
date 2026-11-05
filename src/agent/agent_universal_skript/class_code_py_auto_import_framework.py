"""
Modul: class_code_py_auto_import_framework
Bezeichnung: Automatisiertes Import- und Typisierungs-Framework
Inhaltlicher Schwerpunkt:
Automatisches Erkennen und Heilen von fehlenden Typisierungs-Importen (typing),
Korrektur von Standardbibliothek-Fehlzuordnungen und Behebung veralteter API-Importpfade via AST und Regex.
"""

from __future__ import annotations
import ast
import re
import sys
from pathlib import Path
from typing import Set, Dict, List, Tuple, Any, Optional

# Globale Bindings
logger = globals().get("class_logger_audit_execution")


class class_code_py_auto_import_framework:
    """
    Automatisiertes Import-Framework für Python-Quellcode.
    Analysiert AST und Importzeilen, um NameErrors und fehlerhafte Modulimporte zuverlässig zu beheben.
    """

    _cfg = globals().setdefault("_AGENT_CONFIG", {})
    TYPING_NAMES: Set[str] = _cfg.setdefault("TYPING_NAMES", {
        "Callable", "Optional", "Union", "Dict", "List", "Tuple", "Set",
        "Any", "Mapping", "Iterable", "Sequence", "Iterator", "Generator",
        "TypeVar", "Generic", "cast", "overload", "Literal", "Final"
    })

    STDLIB_REDIRECTS: Dict[str, Tuple[str, str]] = _cfg.setdefault("STDLIB_REDIRECTS", {
        "Path": ("pathlib", "from pathlib import Path"),
        "datetime": ("datetime", "import datetime"),
        "date": ("datetime", "from datetime import date"),
        "time": ("time", "import time"),
        "re": ("re", "import re"),
        "json": ("json", "import json"),
        "os": ("os", "import os"),
        "sys": ("sys", "import sys"),
    })

    PACKAGE_ALIAS_MAPPING: Dict[str, str] = _cfg.setdefault("PACKAGE_ALIAS_MAPPING", {
        "hf_hub": "huggingface_hub",
        "huggingface": "huggingface_hub",
        "sklearn": "sklearn",
        "cv2": "cv2",
        "PIL": "PIL",
    })

    API_REPLACEMENTS: List[Tuple[str, str]] = _cfg.setdefault("API_REPLACEMENTS", [
        (r"from\s+IPython\.display\s+import\s+([^\n]*\bwidgets\b[^\n]*)", "import ipywidgets as widgets"),
        (r"from\s+IPython\.display\s+import\s+([^\n]*\bIntProgress\b[^\n]*)", "from ipywidgets import IntProgress"),
        (r"from\s+llama_cpp\s+import\s+Client\b", "from llama_cpp import Llama as Client"),
        (r"import\s+llama_cpp\.Client\b", "from llama_cpp import Llama as Client"),
    ])

    @classmethod
    def repair_code_imports(cls, code_text: str) -> str:
        """Hauptmethode: Wendet alle strukturellen Importkorrekturen auf den Quellcode an."""
        print("[class_code_py_auto_import_framework] Starte Arbeit: repair_code_imports wird jetzt ausgeführt.")
        if not code_text or not code_text.strip():
            print("[class_code_py_auto_import_framework] Erfolg: repair_code_imports erfolgreich beendet. (Leerer Eingabetext, unveränderter Rückgabewert)")
            return code_text

        try:
            code_text = cls._fix_api_and_submodule_imports(code_text)
            code_text = cls._fix_package_names(code_text)
            code_text = cls._fix_typing_vs_stdlib(code_text)
            code_text = cls._inject_missing_typing(code_text)

            if not code_text:
                print("[class_code_py_auto_import_framework] FEHLER: repair_code_imports hat die Aufgabe nicht erfüllt. Grund: Ergebnis ist leer nach Verarbeitung.")
                return ""

            print(f"[class_code_py_auto_import_framework] Erfolg: repair_code_imports erfolgreich beendet.")
            return code_text
        except Exception as e:
            print(f"[class_code_py_auto_import_framework] FEHLER: repair_code_imports hat die Aufgabe nicht erfüllt. Grund: Importkorrektur fehlgeschlagen: {e}")
            return code_text

    @classmethod
    def _fix_api_and_submodule_imports(cls, code_text: str) -> str:
        """Ersetzt veraltete Modul- und API-Aufrufe direkt an den Import-Stellen."""
        print("[class_code_py_auto_import_framework] Starte Arbeit: _fix_api_and_submodule_imports wird jetzt ausgeführt.")
        try:
            tree = ast.parse(code_text)
            modified = False

            class ImportReplacer(ast.NodeTransformer):
                def visit_ImportFrom(self, node_in):
                    nonlocal modified
                    if node_in.module == "llama_cpp":
                        for alias in node_in.names:
                            if alias.name == "Client":
                                alias.name = "Llama"
                                alias.asname = "Client"
                                modified = True
                    return node_in

            new_tree = ImportReplacer().visit(tree)
            if modified:
                ast.fix_missing_locations(new_tree)
                result = ast.unparse(new_tree)
                print(f"[class_code_py_auto_import_framework] Erfolg: _fix_api_and_submodule_imports erfolgreich beendet. (AST-Ersetzung aktiv)")
                return result
        except Exception:
            pass

        lines = code_text.splitlines()
        for idx, line in enumerate(lines):
            if line.strip().startswith(("import ", "from ")):
                for pattern, replacement in cls.API_REPLACEMENTS:
                    lines[idx] = re.sub(pattern, replacement, line)

        result = "\n".join(lines)

        if not result and code_text:
            print("[class_code_py_auto_import_framework] FEHLER: _fix_api_and_submodule_imports hat die Aufgabe nicht erfüllt. Grund: Ergebnis ist leer.")
            return code_text

        print(f"[class_code_py_auto_import_framework] Erfolg: _fix_api_and_submodule_imports erfolgreich beendet.")
        return result

    @classmethod
    def _fix_package_names(cls, code_text: str) -> str:
        """Korrigiert fehlerhafte Paketnamen auf bekannte Aliase."""
        print("[class_code_py_auto_import_framework] Starte Arbeit: _fix_package_names wird jetzt ausgeführt.")
        lines = code_text.splitlines()
        for idx, line in enumerate(lines):
            if line.strip().startswith(("import ", "from ")):
                for wrong_name, correct_name in cls.PACKAGE_ALIAS_MAPPING.items():
                    if wrong_name != correct_name:
                        lines[idx] = re.sub(rf"\bimport\s+{wrong_name}\b", f"import {correct_name}", lines[idx])
                        lines[idx] = re.sub(rf"\bfrom\s+{wrong_name}\b", f"from {correct_name}", lines[idx])

        result = "\n".join(lines)

        if not result and code_text:
            print("[class_code_py_auto_import_framework] FEHLER: _fix_package_names hat die Aufgabe nicht erfüllt. Grund: Ergebnis ist leer.")
            return code_text

        print(f"[class_code_py_auto_import_framework] Erfolg: _fix_package_names erfolgreich beendet.")
        return result

    @classmethod
    def _fix_typing_vs_stdlib(cls, code_text: str) -> str:
        """Trennt Standardbibliothek-Klassen von Typing-Importen."""
        print("[class_code_py_auto_import_framework] Starte Arbeit: _fix_typing_vs_stdlib wird jetzt ausgeführt.")
        def replace_typing_line(match: re.Match) -> str:
            imports_str = match.group(1)
            imported_items = [item.strip() for item in imports_str.split(",") if item.strip()]
            retained_typing = []
            stdlib_injections = set()

            for item in imported_items:
                base_name = item.split(" as ")[0].strip()
                if base_name in cls.STDLIB_REDIRECTS:
                    _, injection = cls.STDLIB_REDIRECTS[base_name]
                    stdlib_injections.add(injection)
                else:
                    retained_typing.append(item)

            result_lines = []
            if retained_typing:
                result_lines.append(f"from typing import {', '.join(retained_typing)}")
            for inj in sorted(stdlib_injections):
                result_lines.append(inj)
            return "\n".join(result_lines)

        result = re.sub(r"^from\s+typing\s+import\s+([^\n]+)", replace_typing_line, code_text, flags=re.MULTILINE)

        if not result and code_text:
            print("[class_code_py_auto_import_framework] FEHLER: _fix_typing_vs_stdlib hat die Aufgabe nicht erfüllt. Grund: Ergebnis ist leer.")
            return code_text

        print(f"[class_code_py_auto_import_framework] Erfolg: _fix_typing_vs_stdlib erfolgreich beendet.")
        return result

    @classmethod
    def _inject_missing_typing(cls, code_text: str) -> str:
        """Ermittelt ungebundene Typnamen via AST und ergänzt den typing-Import."""
        print("[class_code_py_auto_import_framework] Starte Arbeit: _inject_missing_typing wird jetzt ausgeführt.")
        try:
            tree = ast.parse(code_text)
        except Exception as e:
            print(f"[class_code_py_auto_import_framework] FEHLER: _inject_missing_typing hat die Aufgabe nicht erfüllt. Grund: AST Parsing fehlgeschlagen: {e}")
            return code_text

        defined_or_imported: Set[str] = set()
        used_names: Set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    defined_or_imported.add(alias.asname or alias.name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                defined_or_imported.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and isinstance(target.ctx, ast.Store):
                        defined_or_imported.add(target.id)

        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                if node.id in cls.TYPING_NAMES:
                    used_names.add(node.id)

        missing_types = sorted(list((used_names & cls.TYPING_NAMES) - defined_or_imported))
        if not missing_types:
            print(f"[class_code_py_auto_import_framework] Erfolg: _inject_missing_typing erfolgreich beendet. (Keine fehlenden Typen)")
            return code_text

        injection_line = f"from typing import {', '.join(missing_types)}"
        if "from typing import" in code_text:
            def merge_typing(match: re.Match) -> str:
                current_items = [x.strip() for x in match.group(1).split(",") if x.strip()]
                all_items = sorted(list(set(current_items + missing_types)))
                return f"from typing import {', '.join(all_items)}"
            result = re.sub(r"^from\s+typing\s+import\s+([^\n]+)", merge_typing, code_text, count=1, flags=re.MULTILINE)
        else:
            lines = code_text.splitlines()
            insert_idx = 0
            for idx, line in enumerate(lines):
                if line.startswith("from __future__") or line.startswith("#"):
                    insert_idx = idx + 1
                else:
                    break
            lines.insert(insert_idx, injection_line)
            result = "\n".join(lines)

        if not result and code_text:
            print("[class_code_py_auto_import_framework] FEHLER: _inject_missing_typing hat die Aufgabe nicht erfüllt. Grund: Ergebnis ist leer.")
            return code_text

        print(f"[class_code_py_auto_import_framework] Erfolg: _inject_missing_typing erfolgreich beendet. ({len(missing_types)} Typen injiziert)")
        return result

    @classmethod
    def run_import_framework(cls, code_text: str) -> dict:
        """
        Zentrale Ausführungsfunktion: Führt die vollständige Importbereinigung durch
        und validiert das Endergebnis via AST.
        """
        print("[class_code_py_auto_import_framework] Starte Arbeit: run_import_framework wird jetzt ausgeführt.")
        try:
            repaired_code = cls.repair_code_imports(code_text)
            is_valid = True
            error_msg = None
            try:
                ast.parse(repaired_code)
            except SyntaxError as se:
                is_valid = False
                error_msg = str(se)
                print(f"[class_code_py_auto_import_framework] FEHLER: run_import_framework hat die Aufgabe nicht erfüllt. Grund: Nach Reparatur ungültiger AST: {se}")

            result = {
                "success": is_valid,
                "repaired_code": repaired_code,
                "error": error_msg,
                "modified": repaired_code != code_text
            }

            if result is None:
                print("[class_code_py_auto_import_framework] FEHLER: run_import_framework hat die Aufgabe nicht erfüllt. Grund: Kein Ergebnis-Dictionary erzeugt.")
                return None

            print(f"[class_code_py_auto_import_framework] Erfolg: run_import_framework erfolgreich beendet. (valid={is_valid}, modified={result['modified']})")
            return result
        except Exception as e:
            print(f"[class_code_py_auto_import_framework] FEHLER: run_import_framework hat die Aufgabe nicht erfüllt. Grund: {e}")
            return None
