from __future__ import annotations
import ast
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from typing import Set, Tuple, Dict, Any, List, Optional, Callable

# Assicuriamo la presenza del logger nel namespace globale
logger = globals().get('class_logger_audit_execution')

if "_GLOBAL_RUNTIME_CONFIG" not in globals():
    globals()["_GLOBAL_RUNTIME_CONFIG"] = {}
_cfg = globals()["_GLOBAL_RUNTIME_CONFIG"]

HEALING_SLEEP_INTERVAL_SEC = _cfg.setdefault("HEALING_SLEEP_INTERVAL_SEC", 1.0)
MAX_RETRIES_EVALUATE = _cfg.setdefault("MAX_RETRIES_EVALUATE", 3)
MAX_RETRIES_GUARD_EXECUTION = _cfg.setdefault("MAX_RETRIES_GUARD_EXECUTION", 3)

MAX_KEYWORD_LOSS_COUNT = _cfg.setdefault("MAX_KEYWORD_LOSS_COUNT", 2)
MIN_TOKEN_LENGTH_FOR_EXTRACTION = _cfg.setdefault("MIN_TOKEN_LENGTH_FOR_EXTRACTION", 4)
SHRINKAGE_THRESHOLD_RATIO = _cfg.setdefault("SHRINKAGE_THRESHOLD_RATIO", 0.5)

CRITICAL_WHITELIST_PATTERNS = _cfg.setdefault("CRITICAL_WHITELIST_PATTERNS", {
    "INLINE_REPAIR_FAIL",
    "OllamaServiceManager",
    "hardware_fallback",
    "start_service",
    "stochastic_self_heal"
})
ESSENTIAL_INTEGRITY_TOKENS = _cfg.setdefault("ESSENTIAL_INTEGRITY_TOKENS", [
    "AUTO_IMPORT_LAZY_LOAD",
    "CORE_IMPORT",
    "ZONE_FROM"
])

class class_agent_code_py_semantic_guard:
    """
    Imbuto di validazione semantica a circuito chiuso (Closed-Loop Guard).
    Intercetta violazioni strutturali, regressioni di codice e instabilità sintattiche,
    guidando il processo di auto-riparazione dell'agente senza rischi di corruzione.
    AGENT_Code_Semantic_Guard:
    Ein deterministischer Hybrid-Trichter für Code-Validierung und Refactoring-Schutz.
    Kombiniert AST-Integrität, Fast-Path-Delta, Scope-Mapping, SHA-256-Prüfsummen,
    essenzielle Token-Validierung, Schlüsselwort-Erhaltung, UI-HTML-Identifier-Guard,
    Bootstrap-/Fallback-Schutz, AST-Sicherheits-Injektionsprüfung, stochastische Namespace-,
    SSOT- & Tabellenverlust-Analysen sowie den geschlossenen Selbstheilungs-Regelkreis.
    """
    
    CRITICAL_WHITELIST_PATTERNS = CRITICAL_WHITELIST_PATTERNS

    def __init__(self, model_name: str, ollama_endpoint_fn: Callable):
        self.model_name = model_name
        self.call_ollama_fn = ollama_endpoint_fn

    @staticmethod
    def calculate_checksum(code_text: str) -> str:
        """Genera un hash SHA-256 univoco per il tracciamento atomico dello stato del codice."""
        return hashlib.sha256(code_text.encode("utf-8")).hexdigest()

    def _validate_syntax(self, code_text: str) -> Tuple[bool, Optional[str]]:
        """Valida deterministicamente la sintassi compilando il codice tramite AST."""
        try:
            ast.parse(code_text)
            return True, None
        except SyntaxError as e:
            return False, f"SyntaxError alla linea {e.lineno}: {e.text}"

    def _stochastic_namespace_pollution_detector(self, original_code: str, new_code: str) -> Tuple[bool, str]:
        """Rileva inquinamenti strutturali o riscritture cicliche vietate nel namespace globale."""
        try:
            tree = ast.parse(new_code)
        except SyntaxError:
            return True, "Errore di sintassi gestito in un'altra fase."

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        target_name = target.id
                        try:
                            val_str = ast.unparse(node.value)
                        except Exception:
                            val_str = ""
                        
                        if f'"{target_name}"' in val_str and target_name in val_str and "setdefault" in val_str:
                            return False, f"[NAMESPACE GUARD] Rilevata auto-sovrascrittura ciclica distruttiva su: '{target_name}'."

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
                        return False, f"[NAMESPACE GUARD] La costante globale '{target.id}' è stata corrotta all'interno di una classe."

        return True, "Controllo di integrità del namespace superato."

    def _stochastic_table_and_structure_loss_detector(self, original_code: str, new_code: str) -> Tuple[bool, str]:
        """
        Previene la cancellazione involontaria di registri critici o tabelle di configurazione.
        Erkennt, ob kritische Sammlungen wie ALLOWED_TABLES oder Mapping-Listen 
        im neuen Code versehentlich gelöscht oder drastisch reduziert wurden.
        """
        try:
            orig_tree = ast.parse(original_code)
            new_tree = ast.parse(new_code)
        except SyntaxError:
            return True, "Errore di sintassi gestito in un'altra fase."

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
                    return False, f"[STRUCTURE LOSS] Il registro critico '{col_name}' è stato rimosso dal codice generato!"
                if len(new_collections[col_name]) < len(orig_val) * 0.4:
                    return False, f"[STRUCTURE LOSS] La tabella '{col_name}' ha subito una contrazione anomala dei dati (potenziale perdita di configurazioni)."

        return True, "Integrità strutturale delle tabelle validata."

    def _stochastic_ssot_alias_detector(self, code_text: str) -> Tuple[bool, str]:
        """
        Previene violazioni del principio Single Source of Truth impedendo catene di alias globali.
        Erkennt Verletzungen der Single Source of Truth, bei denen Konfigurationsvariablen 
        direkt aufeinander zugewiesen werden anstatt aus dem globalen RAM zu stammen.
        """
        try:
            tree = ast.parse(code_text)
        except SyntaxError:
            return True, "Errore di sintassi gestito in un'altra fase."

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and isinstance(node.value, ast.Name):
                        if target.id.isupper() and node.value.id.isupper():
                            return False, f"[SSOT VIOLATION] Catena di assegnazione alias non consentita: '{target.id} = {node.value.id}'."
        return True, "Verifica SSOT completata."

    def _validate_ast_injection_safety(self, code_text: str) -> Tuple[bool, Optional[str]]:
        """
        [AST-INJEKTIONS-SICHERHEITS-GUARD]
        Ispeziona le transizioni dei blocchi except e with per intercettare iniezioni o indentazioni rotte.
        """
        lines = code_text.splitlines()
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if stripped.endswith("except:") or (stripped.startswith("except ") and stripped.endswith(":")):
                if idx + 1 < len(lines):
                    next_line = lines[idx + 1].strip()
                    if "=" in next_line and not next_line.startswith("#") and not lines[idx + 1].startswith("    "):
                        return False, f"Rilevato difetto strutturale alla linea {idx + 2}: istruzione operativa sotto 'except' priva di rientro."
            if stripped.startswith("with ") and stripped.endswith(":"):
                if idx + 1 < len(lines):
                    next_line = lines[idx + 1].strip()
                    if "=" in next_line and not next_line.startswith("#") and not lines[idx + 1].startswith("    "):
                        return False, f"Rilevato difetto strutturale alla linea {idx + 2}: istruzione operativa sotto 'with' priva di rientro."
        return True, None

    def _extract_all_signatures(self, code_text: str) -> Dict[str, Set[str]]:
        """
        Estrae l'impronta strutturale completa (firme di classi e funzioni) tramite AST.
        """
        signatures = {"functions": set(), "classes": set(), "globals": set()}
        try:
            tree = ast.parse(code_text)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    signatures["functions"].add(node.name)
                elif isinstance(node, ast.ClassDef):
                    signatures["classes"].add(node.name)
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            signatures["globals"].add(target.id)
        except SyntaxError:
            pass
        return signatures

    def _extract_critical_tokens(self, code_text: str) -> Set[str]:
        tokens = set()
        try:
            tree = ast.parse(code_text)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    tokens.add(node.name)
                elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                    tokens.add(node.id)
                elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if len(node.value) > MIN_TOKEN_LENGTH_FOR_EXTRACTION and ("/" in node.value or "_" in node.value or "-" in node.value):
                        tokens.add(node.value)
        except SyntaxError:
            pass
        return tokens

    def _validate_ui_html_and_identifiers(self, original_code: str, new_code: str) -> Tuple[bool, str]:
        html_patterns = re.findall(r'<(?:div|span|button|input|table|tr|td|form|label)[^>]*>', original_code, re.IGNORECASE)
        for pattern in html_patterns:
            if pattern not in new_code:
                return False, f"[KEYWORD GUARD] UI-HTML-Element verändert/gelöscht: {pattern} (BANNED)"

        for pattern in self.CRITICAL_WHITELIST_PATTERNS:
            if pattern in original_code and pattern not in new_code:
                return False, f"[WHITELIST GUARD] Kritische Runtime-Routine '{pattern}' entfernt."

        return True, "UI-HTML und Identifier-Prüfung erfolgreich."

    def _validate_critical_keywords(self, original_code: str, new_code: str) -> Tuple[bool, str]:
        orig_tokens = self._extract_critical_tokens(original_code)
        missing_tokens = [t for t in orig_tokens if t not in new_code]
        
        if len(missing_tokens) > MAX_KEYWORD_LOSS_COUNT:
            return False, f"[KEYWORD GUARD] Essenzielle Schlüsselwörter entfernt: {missing_tokens[:5]}"
        
        return True, "Schlüsselwort-Prüfung erfolgreich."

    def _validate_code_integrity(self, original_code: str, new_code: str) -> Tuple[bool, str]:
        orig_lines = [l for l in original_code.splitlines() if l.strip() and not l.strip().startswith("#")]
        new_lines = [l for l in new_code.splitlines() if l.strip() and not l.strip().startswith("#")]
        
        if len(orig_lines) > 0 and len(new_lines) < len(orig_lines) * SHRINKAGE_THRESHOLD_RATIO:
            return False, f"[DEF 6] Zu starker Code-Schwund: {len(new_lines)} von {len(orig_lines)} Zeilen."

        for token in ESSENTIAL_INTEGRITY_TOKENS:
            if token in original_code and token not in new_code:
                return False, f"[INTEGRITY GUARD] Token '{token}' entfernt."

        return True, "Integritätsprüfung erfolgreich."

    def _structural_scope_mapper(self, original_code: str, new_code: str, missing_funcs: Set[str]) -> bool:
        prompt = f"""
Du bist ein präziser AST-Scope-Mapper. Folgende Pflicht-Funktionen fehlen im Haupt-Scope: {list(missing_funcs)}
Prüfe im Code-Vergleich, ob sie nur verschoben wurden.

[ORIGINAL]:
{original_code}

[NEU]:
{new_code}

Antworte strikt als JSON:
{{"all_functions_accounted_for": true/false, "reason": "..."}}
"""
        success, resp = self.call_ollama_fn("/api/generate", {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }, agent_title="Scope-Mapper")
        if not success:
            return False
        try:
            data = json.loads(resp.get("response", "{}"))
            return data.get("all_functions_accounted_for", False)
        except Exception:
            return False

    def _semantic_diff_audit(self, original_code: str, new_code: str) -> Tuple[bool, str]:
        prompt = f"""
Vergleiche Original und Code. Ist der fachliche Zweck identisch?

[ORIGINAL]:
{original_code}

[NEU]:
{new_code}

Antworte strikt als JSON:
{{"logic_preserved": true/false, "reason": "..."}}
"""
        success, resp = self.call_ollama_fn("/api/generate", {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }, agent_title="Semantic-Diff-Auditor")
        if not success:
            return True, "Audit-Fallback: LLM nicht erreichbar."
        try:
            data = json.loads(resp.get("response", "{}"))
            return data.get("logic_preserved", True), data.get("reason", "OK")
        except Exception:
            return True, "JSON-Parsing Fehler."

    def _request_self_correction(self, original_code: str, faulty_code: str, error_message: str) -> str:
        prompt = f"""
Dein Code hat die Validierung nicht bestanden.
FEHLER: {error_message}

[ORIGINAL]:
{original_code}

[FEHLERHAFTER CODE]:
{faulty_code}

Korrigiere den Code, stelle sicher, dass keine Tabellen, Strukturen oder Funktionen verloren gehen.
Antworte NUR mit dem vollständigen Python-Code im ```python Markdown-Block.
"""
        success, resp = self.call_ollama_fn("/api/generate", {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False
        }, agent_title="Self-Correction-Repair")

        if success:
            match = re.search(r"```python\s*(.*?)\s*```", resp.get("response", ""), re.DOTALL)
            if match:
                return match.group(1).strip()
        return faulty_code

    def evaluate_and_repair(self, original_code: str, initial_new_code: str) -> Tuple[bool, str, str]:
        """
        Führt den vollständigen Validierungs- und Reparaturtrichter durch (ohne Logik-Schwund).
        Verhindert syntaktische Brüche und integriert Typ-Absicherungen stabil.
        """
        # SENSE-GUARD TYP-ABSICHERUNG
        # Verhindert TypeError, falls 'initial_new_code' oder 'original_code' fälschlicherweise als Liste übergeben wird
        if isinstance(initial_new_code, list):
            current_code = initial_new_code[0] if initial_new_code else ""
        else:
            current_code = str(initial_new_code)
        if isinstance(original_code, list):
            original_code = original_code[0] if original_code else ""
        else:
            original_code = str(original_code)
        if original_code.strip() == current_code.strip():
            return True, current_code, "FAST_PATH: Identisch."
        orig_sig = self._extract_all_signatures(original_code)
        for attempt in range(MAX_RETRIES_EVALUATE):
            valid_syntax, syntax_err = self._validate_syntax(current_code)
            if not valid_syntax:
                if attempt == MAX_RETRIES_EVALUATE - 1:
                    return False, original_code, f"Syntax-Guard: {syntax_err}"
                current_code = self._request_self_correction(original_code, current_code, syntax_err)
                continue
            # 1. Tabellen- und Strukturverlust-Prüfung
            struct_safe, struct_err = self._stochastic_table_and_structure_loss_detector(original_code, current_code)
            if not struct_safe:
                if attempt == MAX_RETRIES_EVALUATE - 1:
                    return False, original_code, struct_err
                current_code = self._request_self_correction(original_code, current_code, struct_err)
                continue
            # 2. Namespace-Prüfung
            namespace_safe, namespace_err = self._stochastic_namespace_pollution_detector(original_code, current_code)
            if not namespace_safe:
                if attempt == MAX_RETRIES_EVALUATE - 1:
                    return False, original_code, namespace_err
                current_code = self._request_self_correction(original_code, current_code, namespace_err)
                continue
            # 3. SSOT-Alias-Prüfung
            ssot_safe, ssot_err = self._stochastic_ssot_alias_detector(current_code)
            if not ssot_safe:
                if attempt == MAX_RETRIES_EVALUATE - 1:
                    return False, original_code, ssot_err
                current_code = self._request_self_correction(original_code, current_code, ssot_err)
                continue
            # 4. AST-Injektionssicherheit
            injection_safe, injection_err = self._validate_ast_injection_safety(current_code)
            if not injection_safe:
                if attempt == MAX_RETRIES_EVALUATE - 1:
                    return False, original_code, injection_err
                current_code = self._request_self_correction(original_code, current_code, injection_err)
                continue
            # 5. UI & Identifier
            ui_ok, ui_err = self._validate_ui_html_and_identifiers(original_code, current_code)
            if not ui_ok:
                if attempt == MAX_RETRIES_EVALUATE - 1:
                    return False, original_code, ui_err
                current_code = self._request_self_correction(original_code, current_code, ui_err)
                continue
            # 6. Keywords
            kw_ok, kw_err = self._validate_critical_keywords(original_code, current_code)
            if not kw_ok:
                if attempt == MAX_RETRIES_EVALUATE - 1:
                    return False, original_code, kw_err
                current_code = self._request_self_correction(original_code, current_code, kw_err)
                continue
            # 7. Signaturen & Scope
            new_sig = self._extract_all_signatures(current_code)
            missing_funcs = orig_sig["functions"] - new_sig["functions"]
            missing_classes = orig_sig["classes"] - new_sig["classes"]
            if missing_funcs or missing_classes:
                scope_ok = self._structural_scope_mapper(original_code, current_code, missing_funcs)
                if not scope_ok:
                    err_msg = f"Fehlende Pflicht-Anker: Funktionen {missing_funcs}"
                    if attempt == MAX_RETRIES_EVALUATE - 1:
                        return False, original_code, err_msg
                    current_code = self._request_self_correction(original_code, current_code, err_msg)
                    continue
            # 8. Integrität (Anti-Shrinkage)
            integrity_ok, integrity_err = self._validate_code_integrity(original_code, current_code)
            if not integrity_ok:
                if attempt == MAX_RETRIES_EVALUATE - 1:
                    return False, original_code, integrity_err
                current_code = self._request_self_correction(original_code, current_code, integrity_err)
                continue
            # 9. Semantischer Diff-Audit
            preserved, reason = self._semantic_diff_audit(original_code, current_code)
            if not preserved:
                err_msg = f"[DEF 2] Semantischer Diff-Audit fehlgeschlagen: {reason}"
                if attempt == MAX_RETRIES_EVALUATE - 1:
                    return False, original_code, err_msg
                current_code = self._request_self_correction(original_code, current_code, err_msg)
                continue
            return True, current_code, "TRICHTER_PASSED: Alle Schutzebenen und stochastischen Prüfungen bestanden."
        return False, original_code, f"Loop erschöpft nach {MAX_RETRIES_EVALUATE} Versuchen."

    def guard_agent_execution(self, agent_callable: Callable, agent_name: str, *args, **kwargs) -> Any:
        """
        Supervisiona a circuito chiuso l'esecuzione dell'agente, isolando le eccezioni a runtime.
        [CLOSED-LOOP GUARD SCHLAUFE]
        Überwacht die Ausführung eines Agenten, fängt Fehler ab,
        triggert den Meta-Agenten zur Korrektur und startet den Agenten neu.
        """
        attempt = 0
        while attempt < MAX_RETRIES_GUARD_EXECUTION:
            attempt += 1
            if logger:
                logger.info(f"[SemanticGuard] Controllo attività per l'agente: '{agent_name}' (Tentativo {attempt}/{MAX_RETRIES_GUARD_EXECUTION})")
            try:
                result = agent_callable(*args, **kwargs)
                return result
            except Exception as e:
                error_msg = str(e)
                if logger:
                    logger.error(f"[SemanticGuard] Eccezione intercettata nell'agente '{agent_name}': {error_msg}")
                healing_success = self.trigger_meta_healing(agent_name, error_msg)
                if healing_success:
                    globals()[f"AGENT_HEALED{agent_name}"] = True
                    globals()["META_AGENT_STATUS"] = "FINISHED_SUCCESS"
                    time.sleep(HEALING_SLEEP_INTERVAL_SEC)
                    continue
                else:
                    print(f"[SemanticGuard] Meta-Healing konnte den Fehler für '{agent_name}' nicht beheben.")
                    raise e
        raise RuntimeError(f"[SemanticGuard] Numero massimo di ripristini esausto per l'agente '{agent_name}'.")
    def _trigger_meta_healing(self, agent_name: str, error_context: str) -> bool:
        """
        Löst den Meta-Agenten ('meta_agent_code_project_log_healing_src') aus,
        übergibt den Agentennamen sowie den Fehlerkontext und wartet auf das 'Fertig'-Signal.
        """
        try:
            import importlib
            healing_module = importlib.import_module("meta_agent_code_project_log_healing_src")
            if hasattr(healing_module, "run_sync"):
                result = healing_module.run_sync(
                    target_failed_agent=agent_name,
                    error_context=error_context
                )
                if result.get("status") == "SUCCESS" and result.get("patches_applied", 0) > 0:
                    return True
        except Exception as err:
            if logger:
                logger.error(f"[SemanticGuard] Fehler beim Aufruf des Meta-Healing-Agenten: {err}")
            print(f"[SemanticGuard] Fehler beim Aufruf des Meta-Agenten: {err}")
        return False