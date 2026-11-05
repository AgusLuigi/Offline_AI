"""
Modul: class_agent_code_py_semantic_guard
Bezeichnung: Geschlossener semantischer Validierungs- und Integritätstrichter (Closed-Loop Guard)
Inhaltlicher Schwerpunkt:
Verhinderung von Code-Schwund, Verlust kritischer Tabellen/Registries, Zerstörung von
globalen Namespaces oder syntaktischen Brüchen bei automatisierten Refactorings und Patches.
"""

from __future__ import annotations
import ast
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from typing import Set, Tuple, Dict, Any, List, Optional, Callable

# Globale Bindings
logger = globals().get("class_logger_audit_execution")
core_infra = globals().get("class_tool_core_infrastructure")
ollama_manager = globals().get("class_tool_ollama_service_manager")


class class_agent_code_py_semantic_guard:
    """
    Validierungstrichter und Schutzschild gegen destruktive Code-Modifikationen.
    Kombiniert AST-Integritätsprüfungen, Anti-Shrinkage-Schwellenwerte und optionale LLM-Korrekturschleifen.
    """

    _cfg = globals().setdefault("_GLOBAL_RUNTIME_CONFIG", {})

    HEALING_SLEEP_INTERVAL_SEC: float = _cfg.setdefault("HEALING_SLEEP_INTERVAL_SEC", 1.0)
    MAX_RETRIES_EVALUATE: int = _cfg.setdefault("MAX_RETRIES_EVALUATE", 3)
    MAX_RETRIES_GUARD_EXECUTION: int = _cfg.setdefault("MAX_RETRIES_GUARD_EXECUTION", 3)
    MAX_KEYWORD_LOSS_COUNT: int = _cfg.setdefault("MAX_KEYWORD_LOSS_COUNT", 2)
    MIN_TOKEN_LENGTH_FOR_EXTRACTION: int = _cfg.setdefault("MIN_TOKEN_LENGTH_FOR_EXTRACTION", 4)
    SHRINKAGE_THRESHOLD_RATIO: float = _cfg.setdefault("SHRINKAGE_THRESHOLD_RATIO", 0.5)

    CRITICAL_WHITELIST_PATTERNS: Set[str] = _cfg.setdefault("CRITICAL_WHITELIST_PATTERNS", {
        "INLINE_REPAIR_FAIL",
        "OllamaServiceManager",
        "hardware_fallback",
        "start_service",
        "stochastic_self_heal"
    })

    ESSENTIAL_INTEGRITY_TOKENS: List[str] = _cfg.setdefault("ESSENTIAL_INTEGRITY_TOKENS", [
        "AUTO_IMPORT_LAZY_LOAD",
        "CORE_IMPORT",
        "ZONE_FROM"
    ])

    def __init__(self, model_name: str = "codestral", ollama_endpoint_fn: Callable = None):
        print(f"[class_agent_code_py_semantic_guard] Starte Arbeit: __init__ wird jetzt ausgeführt. (Parameter: {model_name})")
        self.model_name = model_name
        self.call_ollama_fn = ollama_endpoint_fn or self._default_ollama_call
        if not self.model_name or not self.call_ollama_fn:
            print("[class_agent_code_py_semantic_guard] FEHLER: __init__ hat die Aufgabe nicht erfüllt. Grund: Kern-Attribute nicht gesetzt.")
        else:
            print("[class_agent_code_py_semantic_guard] Erfolg: __init__ erfolgreich beendet.")

    def _default_ollama_call(self, endpoint: str, payload: dict, agent_title: str = "SemanticGuard") -> Tuple[bool, dict]:
        """Standard-Aufruf über den globalen Ollama-Manager."""
        print("[class_agent_code_py_semantic_guard] Starte Arbeit: _default_ollama_call wird jetzt ausgeführt.")
        mgr = globals().get("class_tool_ollama_service_manager")
        if mgr and hasattr(mgr, "call_ollama"):
            result = mgr.call_ollama(endpoint=endpoint, payload=payload, agent_title=agent_title)
        else:
            result = (False, {"error": "Ollama Service Manager nicht verfügbar"})
        print("[class_agent_code_py_semantic_guard] Erfolg: _default_ollama_call erfolgreich beendet.")
        return result

    @staticmethod
    def calculate_checksum(code_text: str) -> str:
        """Erzeugt eine deterministische SHA-256 Prüfsumme des Quelltextes."""
        print("[class_agent_code_py_semantic_guard] Starte Arbeit: calculate_checksum wird jetzt ausgeführt.")
        result = hashlib.sha256(code_text.encode("utf-8")).hexdigest()
        if not result or not isinstance(result, str):
            print("[class_agent_code_py_semantic_guard] FEHLER: calculate_checksum hat die Aufgabe nicht erfüllt. Grund: Leere Prüfsumme.")
            return ""
        print("[class_agent_code_py_semantic_guard] Erfolg: calculate_checksum erfolgreich beendet.")
        return result

    def _validate_syntax(self, code_text: str) -> Tuple[bool, Optional[str]]:
        """Validiert die syntaktische Korrektheit des Quellcodes über den Python AST."""
        print("[class_agent_code_py_semantic_guard] Starte Arbeit: _validate_syntax wird jetzt ausgeführt.")
        try:
            ast.parse(code_text)
            print("[class_agent_code_py_semantic_guard] Erfolg: _validate_syntax erfolgreich beendet.")
            return True, None
        except SyntaxError as e:
            print(f"[class_agent_code_py_semantic_guard] FEHLER: Syntaxfehler: {e}")
            return False, f"SyntaxError in Zeile {e.lineno}: {e.msg}"

    def _stochastic_namespace_pollution_detector(self, original_code: str, new_code: str) -> Tuple[bool, str]:
        """Prüft auf zirkuläre Zuweisungen oder unzulässige Überschreibung globaler Konstanten."""
        print("[class_agent_code_py_semantic_guard] Starte Arbeit: _stochastic_namespace_pollution_detector wird jetzt ausgeführt.")
        try:
            tree = ast.parse(new_code)
        except SyntaxError:
            print("[class_agent_code_py_semantic_guard] Erfolg: _stochastic_namespace_pollution_detector erfolgreich beendet.")
            return True, "Syntaxfehler wird in anderer Stufe behandelt."

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        try:
                            val_str = ast.unparse(node.value)
                        except Exception:
                            val_str = ""
                        if f'"{target.id}"' in val_str and target.id in val_str and "setdefault" in val_str:
                            print(f"[class_agent_code_py_semantic_guard] FEHLER: Zirkuläre Zuweisung bei '{target.id}'")
                            return False, f"Zirkuläre Zuweisung bei '{target.id}'"

        orig_globals = set()
        try:
            orig_tree = ast.parse(original_code)
            for node in ast.walk(orig_tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id.isupper():
                            orig_globals.add(target.id)
        except Exception:
            pass

        inside_class = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                inside_class = True
            elif inside_class and isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in orig_globals:
                        print(f"[class_agent_code_py_semantic_guard] FEHLER: Globale Konstante '{target.id}' in Klasse korrumpiert")
                        return False, f"Globale Konstante '{target.id}' in Klasse korrumpiert"

        result = (True, "Namespace-Integrität bestätigt.")
        print("[class_agent_code_py_semantic_guard] Erfolg: _stochastic_namespace_pollution_detector erfolgreich beendet.")
        return result

    def _stochastic_table_and_structure_loss_detector(self, original_code: str, new_code: str) -> Tuple[bool, str]:
        """Verhindert den unbeabsichtigten Verlust kritischer Registries, Tabellen oder Mappings."""
        print("[class_agent_code_py_semantic_guard] Starte Arbeit: _stochastic_table_and_structure_loss_detector wird jetzt ausgeführt.")
        try:
            orig_tree = ast.parse(original_code)
            new_tree = ast.parse(new_code)
        except SyntaxError:
            print("[class_agent_code_py_semantic_guard] Erfolg: _stochastic_table_and_structure_loss_detector erfolgreich beendet.")
            return True, "Syntaxfehler wird in anderer Stufe behandelt."

        orig_collections = {}
        for node in ast.walk(orig_tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.isupper():
                        if isinstance(node.value, (ast.Set, ast.List, ast.Tuple, ast.Dict)):
                            orig_collections[target.id] = ast.unparse(node.value)

        new_collections = {}
        for node in ast.walk(new_tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.isupper():
                        if isinstance(node.value, (ast.Set, ast.List, ast.Tuple, ast.Dict)):
                            new_collections[target.id] = ast.unparse(node.value)

        for col_name, orig_val in orig_collections.items():
            if any(k in col_name for k in ["TABLE", "MAPPING", "REGISTRY"]):
                if col_name not in new_collections:
                    print(f"[class_agent_code_py_semantic_guard] FEHLER: Kritisches Register '{col_name}' fehlt")
                    return False, f"Kritisches Register '{col_name}' wurde entfernt"
                if len(new_collections[col_name]) < len(orig_val) * 0.4:
                    print(f"[class_agent_code_py_semantic_guard] FEHLER: Anomale Kontraktion von '{col_name}'")
                    return False, f"Register '{col_name}' hat über 60% Daten verloren"

        result = (True, "Tabellen- und Strukturintegrität validiert.")
        print("[class_agent_code_py_semantic_guard] Erfolg: _stochastic_table_and_structure_loss_detector erfolgreich beendet.")
        return result

    def _stochastic_ssot_alias_detector(self, code_text: str) -> Tuple[bool, str]:
        """Erkennt unzulässige Alias-Ketten zwischen globalen Variablen."""
        print("[class_agent_code_py_semantic_guard] Starte Arbeit: _stochastic_ssot_alias_detector wird jetzt ausgeführt.")
        try:
            tree = ast.parse(code_text)
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and isinstance(node.value, ast.Name):
                            if target.id.isupper() and node.value.id.isupper():
                                print(f"[class_agent_code_py_semantic_guard] FEHLER: SSOT-Verletzung '{target.id} = {node.value.id}'")
                                return False, f"SSOT-Alias-Verletzung: '{target.id} = {node.value.id}'"
        except SyntaxError:
            pass
        result = (True, "SSOT-Integrität validiert.")
        print("[class_agent_code_py_semantic_guard] Erfolg: _stochastic_ssot_alias_detector erfolgreich beendet.")
        return result

    def _validate_ast_injection_safety(self, code_text: str) -> Tuple[bool, Optional[str]]:
        """Überprüft Einrückungen unter except- und with-Blöcken auf syntaktische Vollständigkeit."""
        print("[class_agent_code_py_semantic_guard] Starte Arbeit: _validate_ast_injection_safety wird jetzt ausgeführt.")
        lines = code_text.splitlines()
        for idx, line in enumerate(lines):
            s = line.strip()
            if s.endswith("except:") or (s.startswith("except ") and s.endswith(":")) or (s.startswith("with ") and s.endswith(":")):
                if idx + 1 < len(lines):
                    next_line = lines[idx + 1].strip()
                    if "=" in next_line and not next_line.startswith("#") and not lines[idx + 1].startswith("    "):
                        print(f"[class_agent_code_py_semantic_guard] FEHLER: Fehlende Einrückung in Zeile {idx + 2}")
                        return False, f"Fehlende Einrückung in Zeile {idx + 2}"
        print("[class_agent_code_py_semantic_guard] Erfolg: _validate_ast_injection_safety erfolgreich beendet.")
        return True, None

    def _extract_all_signatures(self, code_text: str) -> Dict[str, Set[str]]:
        """Extrahiert alle Funktions-, Klassen- und Konstantennamen."""
        print("[class_agent_code_py_semantic_guard] Starte Arbeit: _extract_all_signatures wird jetzt ausgeführt.")
        sigs = {"functions": set(), "classes": set(), "globals": set()}
        try:
            tree = ast.parse(code_text)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    sigs["functions"].add(node.name)
                elif isinstance(node, ast.ClassDef):
                    sigs["classes"].add(node.name)
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            sigs["globals"].add(target.id)
        except SyntaxError:
            pass
        result = sigs
        if result is None:
            print("[class_agent_code_py_semantic_guard] FEHLER: _extract_all_signatures hat die Aufgabe nicht erfüllt. Grund: Kein Ergebnis.")
            return {"functions": set(), "classes": set(), "globals": set()}
        print("[class_agent_code_py_semantic_guard] Erfolg: _extract_all_signatures erfolgreich beendet.")
        return result

    def _validate_critical_keywords(self, original_code: str, new_code: str) -> Tuple[bool, str]:
        """Prüft, ob essenzielle Schlüsselwörter und Whitelist-Tokens erhalten blieben."""
        print("[class_agent_code_py_semantic_guard] Starte Arbeit: _validate_critical_keywords wird jetzt ausgeführt.")
        for pattern in self.CRITICAL_WHITELIST_PATTERNS:
            if pattern in original_code and pattern not in new_code:
                print(f"[class_agent_code_py_semantic_guard] FEHLER: Whitelist-Token '{pattern}' fehlt")
                return False, f"Kritisches Token '{pattern}' entfernt."

        for token in self.ESSENTIAL_INTEGRITY_TOKENS:
            if token in original_code and token not in new_code:
                print(f"[class_agent_code_py_semantic_guard] FEHLER: Integritäts-Token '{token}' fehlt")
                return False, f"Integritäts-Token '{token}' entfernt."

        result = (True, "Schlüsselwort-Prüfung erfolgreich.")
        print("[class_agent_code_py_semantic_guard] Erfolg: _validate_critical_keywords erfolgreich beendet.")
        return result

    def _validate_code_integrity(self, original_code: str, new_code: str) -> Tuple[bool, str]:
        """Verhindert drastischen Code-Schwund (Anti-Shrinkage)."""
        print("[class_agent_code_py_semantic_guard] Starte Arbeit: _validate_code_integrity wird jetzt ausgeführt.")
        orig_lines = [l for l in original_code.splitlines() if l.strip() and not l.strip().startswith("#")]
        new_lines = [l for l in new_code.splitlines() if l.strip() and not l.strip().startswith("#")]

        if len(orig_lines) > 0 and len(new_lines) < len(orig_lines) * self.SHRINKAGE_THRESHOLD_RATIO:
            print(f"[class_agent_code_py_semantic_guard] FEHLER: Zu starker Code-Schwund ({len(new_lines)}/{len(orig_lines)} Zeilen)")
            return False, f"Zu starker Code-Schwund: {len(new_lines)} von {len(orig_lines)} Zeilen erhalten."

        result = (True, "Code-Integrität validiert.")
        print("[class_agent_code_py_semantic_guard] Erfolg: _validate_code_integrity erfolgreich beendet.")
        return result

    def _request_self_correction(self, original_code: str, faulty_code: str, error_message: str) -> str:
        """Fordert das LLM auf, den abgelehnten Patch unter Berücksichtigung des Fehlers zu reparieren."""
        print("[class_agent_code_py_semantic_guard] Starte Arbeit: _request_self_correction wird jetzt ausgeführt.")
        prompt = f"""Dein Code hat die Validierung nicht bestanden.
FEHLER: {error_message}

[ORIGINAL]:
{original_code[:3000]}

[FEHLERHAFTER CODE]:
{faulty_code[:3000]}

Korrigiere den Code, stelle sicher, dass keine Tabellen, Strukturen oder Funktionen verloren gehen.
Antworte NUR mit dem vollständigen Python-Code im ```python Markdown-Block.
"""
        success, resp = self.call_ollama_fn("/api/generate", {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False
        }, agent_title="SemanticGuard-Repair")

        if success:
            match = re.search(r"```python\s*(.*?)\s*```", resp.get("response", ""), re.DOTALL)
            if match:
                result = match.group(1).strip()
                print("[class_agent_code_py_semantic_guard] Erfolg: _request_self_correction erfolgreich beendet.")
                return result
        print("[class_agent_code_py_semantic_guard] Erfolg: _request_self_correction erfolgreich beendet.")
        return faulty_code

    def evaluate_and_repair(self, original_code: str, initial_new_code: str) -> Tuple[bool, str, str]:
        """Führt den geschlossenen Validierungs- und Reparaturtrichter durch."""
        print("[class_agent_code_py_semantic_guard] Starte Arbeit: evaluate_and_repair wird jetzt ausgeführt.")
        current_code = initial_new_code[0] if isinstance(initial_new_code, list) else str(initial_new_code)
        orig_code = original_code[0] if isinstance(original_code, list) else str(original_code)

        if orig_code.strip() == current_code.strip():
            print("[class_agent_code_py_semantic_guard] Erfolg: evaluate_and_repair erfolgreich beendet.")
            return True, current_code, "FAST_PATH: Identisch."

        for attempt in range(self.MAX_RETRIES_EVALUATE):
            valid_syntax, syntax_err = self._validate_syntax(current_code)
            if not valid_syntax:
                if attempt == self.MAX_RETRIES_EVALUATE - 1:
                    return False, orig_code, f"Syntax-Fehler: {syntax_err}"
                current_code = self._request_self_correction(orig_code, current_code, syntax_err)
                continue

            struct_ok, struct_err = self._stochastic_table_and_structure_loss_detector(orig_code, current_code)
            if not struct_ok:
                if attempt == self.MAX_RETRIES_EVALUATE - 1:
                    return False, orig_code, struct_err
                current_code = self._request_self_correction(orig_code, current_code, struct_err)
                continue

            ns_ok, ns_err = self._stochastic_namespace_pollution_detector(orig_code, current_code)
            if not ns_ok:
                if attempt == self.MAX_RETRIES_EVALUATE - 1:
                    return False, orig_code, ns_err
                current_code = self._request_self_correction(orig_code, current_code, ns_err)
                continue

            ssot_ok, ssot_err = self._stochastic_ssot_alias_detector(current_code)
            if not ssot_ok:
                if attempt == self.MAX_RETRIES_EVALUATE - 1:
                    return False, orig_code, ssot_err
                current_code = self._request_self_correction(orig_code, current_code, ssot_err)
                continue

            inj_ok, inj_err = self._validate_ast_injection_safety(current_code)
            if not inj_ok:
                if attempt == self.MAX_RETRIES_EVALUATE - 1:
                    return False, orig_code, inj_err
                current_code = self._request_self_correction(orig_code, current_code, inj_err)
                continue

            kw_ok, kw_err = self._validate_critical_keywords(orig_code, current_code)
            if not kw_ok:
                if attempt == self.MAX_RETRIES_EVALUATE - 1:
                    return False, orig_code, kw_err
                current_code = self._request_self_correction(orig_code, current_code, kw_err)
                continue

            int_ok, int_err = self._validate_code_integrity(orig_code, current_code)
            if not int_ok:
                if attempt == self.MAX_RETRIES_EVALUATE - 1:
                    return False, orig_code, int_err
                current_code = self._request_self_correction(orig_code, current_code, int_err)
                continue

            print("[class_agent_code_py_semantic_guard] Erfolg: evaluate_and_repair erfolgreich beendet.")
            return True, current_code, "Validierung erfolgreich bestanden."

        return False, orig_code, f"Validierung nach {self.MAX_RETRIES_EVALUATE} Versuchen erschöpft."

    def trigger_meta_healing(self, agent_name: str, error_context: str) -> bool:
        """Löst den Meta-Agenten zur Fehlerbehebung bei Laufzeitfehlern aus."""
        print(f"[class_agent_code_py_semantic_guard] Starte Arbeit: trigger_meta_healing wird jetzt ausgeführt. (Parameter: {agent_name})")
        try:
            import importlib
            healing_module = importlib.import_module("meta_agent_code_project_log_healing_src")
            if hasattr(healing_module, "run_sync"):
                result = healing_module.run_sync(
                    target_failed_agent=agent_name,
                    error_context=error_context
                )
                if result.get("status") == "SUCCESS" and result.get("patches_applied", 0) > 0:
                    print("[class_agent_code_py_semantic_guard] Erfolg: trigger_meta_healing erfolgreich beendet.")
                    return True
        except Exception as e:
            print(f"[class_agent_code_py_semantic_guard] FEHLER: Meta-Healing fehlgeschlagen: {e}")
        print("[class_agent_code_py_semantic_guard] FEHLER: trigger_meta_healing hat die Aufgabe nicht erfüllt. Grund: Heilung nicht erfolgreich.")
        return False

    def guard_agent_execution(self, agent_callable: Callable, agent_name: str, *args, **kwargs) -> Any:
        """Überwacht die Ausführung eines Agenten und startet bei Fehler Meta-Healing."""
        print(f"[class_agent_code_py_semantic_guard] Starte Arbeit: guard_agent_execution wird jetzt ausgeführt. (Parameter: {agent_name})")
        for attempt in range(1, self.MAX_RETRIES_GUARD_EXECUTION + 1):
            try:
                result = agent_callable(*args, **kwargs)
                print("[class_agent_code_py_semantic_guard] Erfolg: guard_agent_execution erfolgreich beendet.")
                return result
            except Exception as e:
                print(f"[class_agent_code_py_semantic_guard] FEHLER: Ausnahme in '{agent_name}': {e}")
                healed = self.trigger_meta_healing(agent_name, str(e))
                if healed:
                    time.sleep(self.HEALING_SLEEP_INTERVAL_SEC)
                    continue
                raise e
        return None

    @classmethod
    def run_semantic_guard(cls, original_code: str, new_code: str, model_name: str = "codestral") -> dict:
        """
        Zentrale Ausführungsfunktion: Führt die vollständige semantische Validierung
        und bei Bedarf die Reparatur des neuen Codes durch.
        """
        print("[class_agent_code_py_semantic_guard] Starte Arbeit: run_semantic_guard wird jetzt ausgeführt.")
        try:
            guard = cls(model_name=model_name)
            success, code_out, message = guard.evaluate_and_repair(original_code, new_code)
            result = {
                "success": success,
                "code": code_out,
                "message": message,
                "checksum": cls.calculate_checksum(code_out)
            }
        except Exception as e:
            print(f"[class_agent_code_py_semantic_guard] FEHLER: In run_semantic_guard: {e}")
            return None
        if result is None:
            print("[class_agent_code_py_semantic_guard] FEHLER: run_semantic_guard hat die Aufgabe nicht erfüllt. Grund: Kein Ergebnis.")
            return None
        print("[class_tool_ollama_service_manager] Erfolg: run_semantic_guard erfolgreich beendet.")
        return result
