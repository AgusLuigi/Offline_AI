from __future__ import annotations
import ast
import re
import sys
from pathlib import Path
from typing import Set, Dict, List, Tuple, Any, Optional

# Assicuriamo la presenza del logger nel namespace globale
logger = globals().get('class_logger_audit_execution')

TYPING_NAMES: Set[str] = {
    "Callable", "Optional", "Union", "Dict", "List", "Tuple", "Set",
    "Any", "Mapping", "Iterable", "Sequence", "Iterator", "Generator",
    "TypeVar", "Generic", "cast", "overload", "Literal", "Final"
}

class class_code_py_auto_import_framework:
    """
    Framework automatizzato stochastico-deterministico per la risoluzione degli import.
    Previene NameError e import errati indotti dai refactoring degli agenti senza
    danneggiare le stringhe letterali o la logica interna del codice sorgente.
    Automatisiertes, stochastisch-deterministisches Import-Framework.
    Analysiert Python-Quellcode per AST und Regex, um häufige Agenten-Importfehler vollautomatisch zu beheben:
    - Bug #1: NameError bei fehlenden Typisierungs-Imports (Callable, Optional, Union, Dict, List, Tuple, Any, Set, Mapping, Iterable)
    - Bug #2: Falsche Importe durch API-Änderungen (z.B. llama_cpp.Client -> llama_cpp.Llama / ollama.Client)
    - Bug #3: Abweichungen zwischen Paket- und Repository-Namen (z.B. hf_hub -> huggingface_hub, sklearn -> scikit-learn)
    - Bug #4: Vermischung von IPython.display und ipywidgets (z.B. from IPython.display import widgets -> import ipywidgets as widgets)
    - Bug #5: Falscher Importort zwischen Standardbibliothek und typing (z.B. Path from typing -> from pathlib import Path)
    - Bug #11: Modulare, global wiederverwendbare Kapselung
    """

    TYPING_NAMES: Set[str] = TYPING_NAMES

    STDLIB_REDIRECTS: Dict[str, Tuple[str, str]] = {
        "Path": ("pathlib", "from pathlib import Path"),
        "datetime": ("datetime", "import datetime"),
        "date": ("datetime", "from datetime import date"),
        "time": ("time", "import time"),
        "re": ("re", "import re"),
        "json": ("json", "import json"),
        "os": ("os", "import os"),
        "sys": ("sys", "import sys"),
    }

    PACKAGE_ALIAS_MAPPING: Dict[str, str] = {
        "hf_hub": "huggingface_hub",
        "huggingface": "huggingface_hub",
        "sklearn": "sklearn",
        "cv2": "cv2",
        "PIL": "PIL",
    }

    API_REPLACEMENTS: List[Tuple[str, str]] = [
        (r"from\s+IPython\.display\s+import\s+([^\n]*\bwidgets\b[^\n]*)", "import ipywidgets as widgets"),
        (r"from\s+IPython\.display\s+import\s+([^\n]*\bIntProgress\b[^\n]*)", "from ipywidgets import IntProgress"),
        (r"from\s+llama_cpp\s+import\s+Client\b", "from llama_cpp import Llama as Client"),
        (r"import\s+llama_cpp\.Client\b", "from llama_cpp import Llama as Client"),
    ]

    @classmethod
    def repair_code_imports(cls, code_text: str) -> str:
        """
        Punto di ingresso primario: applica le correzioni strutturali agli import
        garantendo l'integrità del codice sorgente analizzato.
        """
        if not code_text or not code_text.strip():
            return code_text

        # 1. Correzione delle API e dei sottomoduli tramite AST/Regex controllata (Fase 3)
        code_text = cls._fix_api_and_submodule_imports(code_text)

        # 2. Correzione dei nomi dei pacchetti (Fase 4)
        code_text = cls._fix_package_names(code_text)

        # 3. Separazione sicura tra standard library e typing (Fase 4)
        code_text = cls._fix_typing_vs_stdlib(code_text)

        # 4. Iniezione deterministica dei tipi mancanti tramite analisi AST dei nodi orfani (Fase 5)
        code_text = cls._inject_missing_typing(code_text)

        return code_text

    @classmethod
    def _fix_api_and_submodule_imports(cls, code_text: str) -> str:
        """Sostituisce gli import deprecati agendo esclusivamente sulle righe di import effettive."""
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
                return ast.unparse(new_tree)
        except Exception:
            pass

        # Fallback controllato riga per riga per evitare match globali su stringhe di testo
        lines = code_text.splitlines()
        for idx, line in enumerate(lines):
            if line.strip().startswith(("import ", "from ")):
                for pattern, replacement in cls.API_REPLACEMENTS:
                    lines[idx] = re.sub(pattern, replacement, line)
        return "\n".join(lines)

    @classmethod
    def _fix_package_names(cls, code_text: str) -> str:
        """Mappa i nomi dei pacchetti errati limitando l'azione ai token isolati di importazione."""
        lines = code_text.splitlines()
        for idx, line in enumerate(lines):
            if line.strip().startswith(("import ", "from ")):
                for wrong_name, correct_name in cls.PACKAGE_ALIAS_MAPPING.items():
                    if wrong_name == correct_name:
                        continue
                    lines[idx] = re.sub(rf"\bimport\s+{wrong_name}\b", f"import {correct_name}", lines[idx])
                    lines[idx] = re.sub(rf"\bfrom\s+{wrong_name}\b", f"from {correct_name}", lines[idx])
        return "\n".join(lines)

    @classmethod
    def _fix_typing_vs_stdlib(cls, code_text: str) -> str:
        """
        Evita la contaminazione di typing reindirizzando oggetti della StdLib nei loro moduli nativi.
        Beispiel: 'from typing import Path, List' -> 'from typing import List\nfrom pathlib import Path'
        """
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

        return re.sub(r"^from\s+typing\s+import\s+([^\n]+)", replace_typing_line, code_text, flags=re.MULTILINE)

    @classmethod
    def _inject_missing_typing(cls, code_text: str) -> str:
        """Rileva tramite AST l'uso di Typings non dichiarati e li inietta in modo pulito."""
        try:
            tree = ast.parse(code_text)
        except Exception:
            return code_text

        defined_or_imported_names: Set[str] = set()
        used_names: Set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    defined_or_imported_names.add(alias.asname or alias.name)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    defined_or_imported_names.add(alias.asname or alias.name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                defined_or_imported_names.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and isinstance(target.ctx, ast.Store):
                        defined_or_imported_names.add(target.id)

        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                if node.id in cls.TYPING_NAMES:
                    used_names.add(node.id)

        missing_types = sorted(list((used_names & cls.TYPING_NAMES) - defined_or_imported_names))
        if not missing_types:
            return code_text

        injection_line = f"from typing import {', '.join(missing_types)}"

        if "from typing import" in code_text:
            def merge_typing(match: re.Match) -> str:
                current_items = [x.strip() for x in match.group(1).split(",") if x.strip()]
                all_items = sorted(list(set(current_items + missing_types)))
                return f"from typing import {', '.join(all_items)}"
            return re.sub(r"^from\s+typing\s+import\s+([^\n]+)", merge_typing, code_text, count=1, flags=re.MULTILINE)
        else:
            lines = code_text.splitlines()
            insert_idx = 0
            for idx, line in enumerate(lines):
                if line.startswith("from __future__") or line.startswith("#"):
                    insert_idx = idx + 1
                else:
                    break
            lines.insert(insert_idx, injection_line)
            return "\n".join(lines)
