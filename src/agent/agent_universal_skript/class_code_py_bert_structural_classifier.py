"""
Modul: class_code_py_bert_structural_classifier
Bezeichnung: Deterministischer Python-Struktur-Klassifizierer
Inhaltlicher Schwerpunkt:
AST-basierte Zerlegung und Klassifizierung von Python-Dateien in semantische Kategorien
(CONFIG_HEAVY_WORKFLOW, MODULAR_TOOL_EXTENSION, EXECUTION_LAUNCHER, GENERIC_SCRIPT).
"""

import ast
import sys
from pathlib import Path
from typing import Dict, List, Any

# Globale Bindings
logger = globals().get("class_logger_audit_execution")


class class_code_py_bert_structural_classifier:
    """
    Klassifiziert Python-Dateien deterministisch anhand ihrer AST-Strukturmerkmale.
    Vermeidet fehleranfällige Text-Regex-Scans durch exakte Syntaxbaum-Analyse.
    """

    _cfg = globals().setdefault("_AGENT_CONFIG", {})
    GLOBAL_COUNT_THRESHOLD: int = _cfg.setdefault("GLOBAL_COUNT_THRESHOLD", 5)

    def __init__(self, max_tokens: int = 4096):
        print("[class_code_py_bert_structural_classifier] Starte Arbeit: __init__ wird jetzt ausgeführt.")
        self.max_tokens = max_tokens

        if self.max_tokens is None or not isinstance(self.max_tokens, int):
            print("[class_code_py_bert_structural_classifier] FEHLER: __init__ hat die Aufgabe nicht erfüllt. Grund: max_tokens ist kein gültiger Integer.")
            return

        print(f"[class_code_py_bert_structural_classifier] Erfolg: __init__ erfolgreich beendet. (max_tokens={self.max_tokens})")

    def tokenize_code_structure(self, source_code: str) -> dict:
        """Extrahiert strukturelle Merkmale (Imports, Globals, Klassen, Funktionen, Main) per AST."""
        print("[class_code_py_bert_structural_classifier] Starte Arbeit: tokenize_code_structure wird jetzt ausgeführt.")
        token_groups = {
            "imports": [],
            "globals": [],
            "classes": [],
            "functions": [],
            "execution": []
        }

        try:
            tree = ast.parse(source_code)
        except SyntaxError as e:
            print(f"[class_code_py_bert_structural_classifier] FEHLER: tokenize_code_structure hat die Aufgabe nicht erfüllt. Grund: SyntaxError im Quelltext: {e}")
            return token_groups

        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                token_groups["imports"].append(ast.unparse(node))
            elif isinstance(node, ast.ClassDef):
                token_groups["classes"].append(node.name)
            elif isinstance(node, ast.FunctionDef):
                token_groups["functions"].append(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.isupper():
                        token_groups["globals"].append(target.id)
            elif isinstance(node, ast.If):
                if isinstance(node.test, ast.Compare):
                    if isinstance(node.test.left, ast.Name) and node.test.left.id == "__name__":
                        for comp in node.test.comparators:
                            if isinstance(comp, ast.Constant) and comp.value == "__main__":
                                token_groups["execution"].append("main_guard")

        if token_groups is None:
            print("[class_code_py_bert_structural_classifier] FEHLER: tokenize_code_structure hat die Aufgabe nicht erfüllt. Grund: token_groups ist None.")
            return {}

        print(f"[class_code_py_bert_structural_classifier] Erfolg: tokenize_code_structure erfolgreich beendet. ({len(token_groups['imports'])} Imports, {len(token_groups['classes'])} Klassen)")
        return token_groups

    def evaluate_code_similarity_and_grouping(self, all_file_contents: dict) -> dict:
        """Klassifiziert mehrere Dateien anhand ihrer extrahierten Strukturmerkmale."""
        print(f"[class_code_py_bert_structural_classifier] Starte Arbeit: evaluate_code_similarity_and_grouping wird jetzt ausgeführt. (Parameter: {len(all_file_contents)} Dateien)")
        cluster_map = {}
        for file_path, content in all_file_contents.items():
            tokens = self.tokenize_code_structure(content)
            global_count = len(tokens["globals"])
            class_count = len(tokens["classes"])
            execution_count = len(tokens["execution"])

            if global_count > self.GLOBAL_COUNT_THRESHOLD and class_count == 0:
                cluster_map[file_path] = "CONFIG_HEAVY_WORKFLOW"
            elif class_count > 0:
                cluster_map[file_path] = "MODULAR_TOOL_EXTENSION"
            elif execution_count > 0:
                cluster_map[file_path] = "EXECUTION_LAUNCHER"
            else:
                cluster_map[file_path] = "GENERIC_SCRIPT"

        if cluster_map is None:
            print("[class_code_py_bert_structural_classifier] FEHLER: evaluate_code_similarity_and_grouping hat die Aufgabe nicht erfüllt. Grund: cluster_map ist None.")
            return {}

        print(f"[class_code_py_bert_structural_classifier] Erfolg: evaluate_code_similarity_and_grouping erfolgreich beendet. ({len(cluster_map)} Dateien klassifiziert)")
        return cluster_map

    @classmethod
    def run_bert_classifier(cls, file_contents: dict) -> dict:
        """
        Zentrale Ausführungsfunktion: Führt die Tokenisierung und Klassifikation
        für eine Sammlung von Dateien aus und fasst die Ergebnisse zusammen.
        """
        print("[class_code_py_bert_structural_classifier] Starte Arbeit: run_bert_classifier wird jetzt ausgeführt.")
        try:
            classifier = cls()
            classification = classifier.evaluate_code_similarity_and_grouping(file_contents)
            result = {
                "success": True,
                "classifications": classification,
                "file_count": len(file_contents)
            }

            if result is None:
                print("[class_code_py_bert_structural_classifier] FEHLER: run_bert_classifier hat die Aufgabe nicht erfüllt. Grund: Kein Ergebnis-Dictionary erzeugt.")
                return None

            print(f"[class_code_py_bert_structural_classifier] Erfolg: run_bert_classifier erfolgreich beendet. ({result['file_count']} Dateien verarbeitet)")
            return result
        except Exception as e:
            print(f"[class_code_py_bert_structural_classifier] FEHLER: run_bert_classifier hat die Aufgabe nicht erfüllt. Grund: {e}")
            return None
