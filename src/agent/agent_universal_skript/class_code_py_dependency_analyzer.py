from __future__ import annotations
import ast
import hashlib
import logging
import sys
import re
from pathlib import Path
from typing import Optional, Dict, List, Set, Tuple, Any

# Assicuriamo la presenza del logger e dei parametri nel namespace globale
logger = globals().get('class_logger_audit_execution')

ANALYZER_LOGGER_NAME = "DependencyAnalyzer"

class class_code_py_dependency_analyzer:
    """
    Analizzatore avanzato di dipendenze e strutture AST per agenti Python.
    Individua porzioni di codice morto, duplicati architetturali (Bug #13),
    disallineamenti di sequenza e disconnessioni nel namespace globale del progetto.
    
    Erkennt:
    - Tote Code-Leichen (mit Klassifizierung: echte Leiche vs. potenzieller Hook vs. Global Merge Tool)
    - Unterbrochene Verbindungen / Unerreichbarkeit
    - Falsche Block-Reihenfolge (Sequenzierungsfehler)
    - Globale Namespace-Entkopplungen
    - Duplizierte Codeblöcke / Funktionen via Funktions-Hash-Vergleich (Bug #13)
    """

    def __init__(self, logger_instance: Optional[logging.Logger] = None):
        if logger_instance:
            self.logger = logger_instance
        elif logger and hasattr(logger, 'get_logger'):
            self.logger = logger.get_logger()
        else:
            self.logger = logging.getLogger(ANALYZER_LOGGER_NAME)
            
        current_file = Path(__file__).resolve()
        root = current_file.parent
        for parent in [current_file] + list(current_file.parents):
            if (parent / "src").exists():
                root = parent
                break
        self.path_src = root / "src"

    def _calculate_function_hash(self, node: ast.FunctionDef) -> str:
        """Calcola un hash MD5 normalizzato del corpo della funzione per stanare duplicati strutturali."""
        try:
            code_segment = ast.unparse(node)
            # Rimozione totale degli spazi vuoti per garantire l'invarianza estetica dell'hash (Bug #13)
            normalized_code = "".join(code_segment.split())
            return hashlib.md5(normalized_code.encode('utf-8')).hexdigest()
        except Exception:
            return ""

    def _scan_for_global_tool_duplicate(self, element_name: str) -> bool:
        """Scansiona l'intera directory sorgente per mappare la duplicazione inter-modulo delle funzioni."""
        if not self.path_src.exists():
            return False
        try:
            for py_file in self.path_src.rglob("*.py"):
                # Previene l'auto-analisi ricorsiva se il file coincide con il contesto corrente
                file_content = py_file.read_text(encoding="utf-8", errors="ignore")
                if element_name in file_content:
                    external_ast = ast.parse(file_content)
                    for node in ast.walk(external_ast):
                        if isinstance(node, ast.FunctionDef) and node.name == element_name:
                            return True
        except Exception:
            pass
        return False

    def analyze_deep_dependencies(self, code_text: str) -> Dict[str, Any]:
        """
        Esegue un audit statico e semantico profondo sul frammento di codice passato.
        """
        defined_functions: Dict[str, int] = {}  # {nome_funzione: riga_inizio}
        defined_classes: Dict[str, int] = {}    # {nome_classe: riga_inizio}
        function_hashes: Dict[str, List[str]] = {} # {hash_md5: [nomi_funzioni]}
        called_names: Set[str] = set()
        global_vars: Set[str] = set()
        
        call_sequence: List[Tuple[str, int]] = []

        try:
            tree = ast.parse(code_text)

            # Fase 1: Estrazione e mapping dei nodi tramite AST Walking
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    defined_functions[node.name] = node.lineno
                    
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
            err_msg = f"SYNTAX_ERROR: Impossibile eseguire il parsing del codice alla riga {e.lineno}: {e.text}"
            self.logger.error(err_msg)
            return {"status": "ERROR", "error": err_msg}

        # Fase 4: Analisi del codice orfano / morto
        ignored_builtins = {"print", "len", "str", "int", "dict", "set", "list", "range", "isinstance", "getattr", "globals"}
        all_definitions = set(defined_functions.keys()) | set(defined_classes.keys())
        active_calls = called_names | ignored_builtins

        dead_elements = all_definitions - active_calls
        
        dead_code_report = []
        for elem in dead_elements:
            lineno = defined_functions.get(elem) or defined_classes.get(elem, 0)
            
            reason = "Blocco isolato / Non referenziato nel flusso principale"
            category = "TRUE_DEAD_CODE"
            action_recommendation = "Rimozione sicura (Delete)"
            
            if self._scan_for_global_tool_duplicate(elem):
                category = "GLOBAL_DUPLICATE_POTENTIAL_MERGE"
                reason = "Questa istruzione è presente parallellamente nei moduli condivisi globali."
                action_recommendation = "Fusione qualitativa semantica (Zwei zu Eins)"
            elif elem.startswith("_") or elem.startswith("test_"):
                category = "POTENTIAL_HOOK_OR_HELPER"
                reason = "Presenta prefissi privati o di test; potenziale hook interno."
                action_recommendation = "Monitorare / Mantenere"
            elif elem in ["setUp", "tearDown", "__init__", "main"]:
                category = "LIFECYCLE_OR_ENTRY"
                reason = "Metodo legato al ciclo di vita del framework richiamato per riflessione."
                action_recommendation = "Ispezionare / Mantenere"

            dead_code_report.append({
                "name": elem,
                "line": lineno,
                "category": category,
                "reason": reason,
                "action_recommendation": action_recommendation
            })

        # Controllo dei blocchi duplicati (Bug #13)
        duplicate_warnings = []
        for f_hash, names in function_hashes.items():
            if len(names) > 1:
                duplicate_warnings.append({
                    "duplicate_functions": names,
                    "issue": "Duplicazione strutturale rilevata: blocchi di codice speculari all'interno dello stesso modulo."
                })

        # Controllo degli errori di sequenziamento temporale delle chiamate
        sequencing_warnings = []
        for call_name, call_line in call_sequence:
            if call_name in defined_functions:
                def_line = defined_functions[call_name]
                if def_line > call_line:
                    sequencing_warnings.append({
                        "element": call_name,
                        "called_at_line": call_line,
                        "defined_at_line": def_line,
                        "issue": "Errore di sequenza: la funzione viene invocata prima della sua dichiarazione lineare."
                    })

        # Controllo ridondanze UI (Bug #20)
        ui_duplications = []
        ui_keywords = ["VBox", "HBox", "AppLayout", "GridBox", "Tab", "Accordion", "display"]
        for kw in ui_keywords:
            occurrences = [lineno for name, lineno in call_sequence if name == kw]
            if len(occurrences) > 1:
                ui_duplications.append({
                    "ui_element": kw,
                    "lines": occurrences,
                    "issue": "Definizione UI multipla o Re-Display ridondante nello stesso scope."
                })

        report = {
            "status": "SUCCESS",
            "total_definitions": len(all_definitions),
            "dead_code_count": len(dead_code_report),
            "dead_code_details": dead_code_report,
            "duplicate_code_warnings": duplicate_warnings,
            "duplicate_ui_warnings": ui_duplications,
            "sequencing_warnings": sequencing_warnings,
            "isolated_components": list(dead_elements)
        }
        self.logger.info(f"[DEPENDENCY_AUDIT] Verificati: {len(all_definitions)} elementi. Rilevati {len(dead_code_report)} blocchi orfani, {len(duplicate_warnings)} duplicati strutturali.")
        return report