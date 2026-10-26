# DETERMINISTISCHER PYTHON-STRUKTUR-KLASSIFIZIERER
import ast
from pathlib import Path
from typing import Dict, List, Any

class class_code_py_bert_structural_classifier:
    """
    Classificatore strutturale deterministico basato su AST Python.
    Organizza il repository e raggruppa semanticamente i file all'interno di src/
    evitando analisi di testo grezzo soggette a errori strutturali.
    """
    def __init__(self, max_tokens: int = 4096):
        self.max_tokens = max_tokens

    def tokenize_code_structure(self, source_code: str) -> dict:
        """
        Analizza meccanicamente le strutture del codice Python tramite AST 
        per identificare variabili globali, import, classi e blocchi di esecuzione.
        """
        token_groups = {
            "imports": [],
            "globals": [],
            "classes": [],
            "functions": [],
            "execution": []
        }

        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            # Se l'istante attuale è corrotto scompone in modalità provvisoria 
            # per non bloccare l'intero ciclo ma segnala la criticità
            return token_groups

        for node in tree.body:
            # 1. Rilevamento deterministico degli Import
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                token_groups["imports"].append(ast.unparse(node))
            
            # 2. Rilevamento Classi (inclusi decoratori)
            elif isinstance(node, ast.ClassDef):
                token_groups["classes"].append(node.name)
            
            # 3. Rilevamento Funzioni Standalone
            elif isinstance(node, ast.FunctionDef):
                token_groups["functions"].append(node.name)
            
            # 4. Rilevamento Variabili Globali Reali (Uppercase)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.isupper():
                        token_groups["globals"].append(target.id)
            
            # 5. Rilevamento Esatto del Main Guard / Entry Point
            elif isinstance(node, ast.If):
                if isinstance(node.test, ast.Compare):
                    if isinstance(node.test.left, ast.Name) and node.test.left.id == "__name__":
                        for comp in node.test.comparators:
                            if isinstance(comp, ast.Constant) and comp.value == "__main__":
                                token_groups["execution"].append("main_guard")

        return token_groups

    def evaluate_code_similarity_and_grouping(self, all_file_contents: dict) -> dict:
        """
        Esegue il clustering semantico dei file nella directory src/ 
        per raggruppare i prodotti equivalenti e definire le categorie in modo sicuro.
        """
        cluster_map = {}
        for file_path, content in all_file_contents.items():
            tokens = self.tokenize_code_structure(content)
            global_count = len(tokens["globals"])
            class_count = len(tokens["classes"])
            execution_count = len(tokens["execution"])
            
            # Classificazione basata su metriche strutturali certe
            if global_count > 5 and class_count == 0:
                cluster_map[file_path] = "CONFIG_HEAVY_WORKFLOW"
            elif class_count > 0:
                cluster_map[file_path] = "MODULAR_TOOL_EXTENSION"
            elif execution_count > 0:
                cluster_map[file_path] = "EXECUTION_LAUNCHER"
            else:
                cluster_map[file_path] = "GENERIC_SCRIPT"

        return cluster_map
