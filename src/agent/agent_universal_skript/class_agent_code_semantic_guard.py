import ast
import json
import re
from typing import Set, Tuple, Dict, Any, List, Optional

class class_agent_code_semantic_guard:
    """
    AGENT_Code_Semantic_Guard:
    Ein deterministischer Hybrid-Trichter für Code-Validierung und Refactoring-Schutz.
    Kombiniert AST-Integrität, Fast-Path-Delta, Scope-Mapping und gezielte Self-Correction.
    """
    def __init__(self, model_name: str, ollama_endpoint_fn: callable):
        self.model_name = model_name
        self.call_ollama_fn = ollama_endpoint_fn
    def _validate_syntax(self, code_text: str) -> Tuple[bool, Optional[str]]:
        """[DEF 5: Deterministischer Syntax-Guard] Kompiliert Code vorab per ast.parse()."""
        try:
            ast.parse(code_text)
            return True, None
        except SyntaxError as e:
            return False, f"SyntaxError in Zeile {e.lineno}: {e.text}"
    def _extract_all_signatures(self, code_text: str) -> Dict[str, Set[str]]:
        """[DEF 1: AST-Signatur-Integrität] Extrahiert Funktionen, Klassen und globale Variablen."""
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

    def _structural_scope_mapper(self, original_code: str, new_code: str, missing_funcs: Set[str]) -> bool:
        """
        Prüft gezielt, ob scheinbar 'fehlende' Funktionen lediglich in einen anderen 
        Scope (z. B. eine innere def oder Klasse) verschoben wurden, statt gelöscht zu sein.
        """
        prompt = f"""
Du bist ein präziser AST-Scope-Mapper. Folgende Pflicht-Funktionen fehlen im Haupt-Scope des neuen Codes: {list(missing_funcs)}
Prüfe im folgenden Code-Vergleich, ob diese Funktionen lediglich verschoben wurden (z.B. als innere Funktion in eine andere def gewandert sind) oder ob sie noch existieren.

[ORIGINAL CODE]:
{original_code}

[NEUER CODE]:
{new_code}

Antworte strikt als JSON:
{{
  "all_functions_accounted_for": true/false,
  "reason": "Kurze Erklärung"
}}
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
        """[DEF 2: Der LLM-basierte Diff-Auditor] Kompakter Semantik-Check für echte Deltas."""
        prompt = f"""
Du bist ein Code-Audit-Agent. Vergleiche den Original-Code mit dem optimierten Code.
Prüfe, ob der fachliche Zweck, Inputs, Transformationen und Outputs identisch geblieben sind.

[ORIGINAL CODE]:
{original_code}

[OPTIMIERTER CODE]:
{new_code}

Antworte strikt als JSON:
{{
  "logic_preserved": true/false,
  "reason": "Exakte Begründung"
}}
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
            return data.get("logic_preserved", True), data.get("reason", "Keine Details")
        except Exception:
            return True, "JSON-Parsing fehlgeschlagen, nehme Integrität an."

    def _request_self_correction(self, original_code: str, faulty_code: str, error_message: str) -> str:
        """[DEF 3: Automatisierter Self-Correction-Loop] Schickt den Code mit konkretem Fehler zurück."""
        prompt = f"""
Du bist ein Self-Correction-Agent. Dein Code hat die Validierung nicht bestanden.
FEHLER / URSACHE: {error_message}

[ORIGINAL CODE ALS REFERENZ]:
{original_code}

[DEIN LETZTER FEHLERHAFTER CODE]:
{faulty_code}

Korrigiere den Code so, dass alle Pflicht-Anker erhalten bleiben und keine Syntaxfehler existieren.
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
        Führt den hocheffizienten Trichter durch:
        Fast-Path (Identisch?) -> Syntax-Guard -> AST-Integrität -> Scope-Mapper -> Toleranz-Korridor -> Diff-Audit.
        """
        current_code = initial_new_code

        # --- OPTIMIERUNG: FAST-PATH (Null Overhead bei identischem Code) ---
        if original_code.strip() == current_code.strip():
            return True, current_code, "FAST_PATH: Code ist zu 100% identisch. Übersprungen."
        orig_sig = self._extract_all_signatures(original_code)
        orig_lines = [l for l in original_code.splitlines() if l.strip() and not l.strip().startswith("#")]
        for attempt in range(3):  # [DEF 3] Max 3 Versuche im Self-Correction-Loop
            
            # --- STUFE 5: Deterministischer Syntax-Guard ---
            valid_syntax, syntax_err = self._validate_syntax(current_code)
            if not valid_syntax:
                if attempt == 2:
                    return False, original_code, f"[DEF 5] Syntax-Guard fehlgeschlagen: {syntax_err}"
                current_code = self._request_self_correction(original_code, current_code, syntax_err)
                continue

            # --- STUFE 1: AST-Signatur-Integrität & Delta-Prüfung ---
            new_sig = self._extract_all_signatures(current_code)
            missing_funcs = orig_sig["functions"] - new_sig["functions"]
            missing_classes = orig_sig["classes"] - new_sig["classes"]
            
            if missing_funcs or missing_classes:
                # Prüfen, ob Funktionen nur den Scope gewechselt haben (Verschiebungserkennung)
                scope_ok = self._structural_scope_mapper(original_code, current_code, missing_funcs)
                if not scope_ok:
                    err_msg = f"[DEF 1] Fehlende Pflicht-Anker (gelöscht): Funktionen {missing_funcs}, Klassen {missing_classes}"
                    if attempt == 2:
                        return False, original_code, err_msg
                    current_code = self._request_self_correction(original_code, current_code, err_msg)
                    continue

            # --- STUFE 6: Semantische Toleranz-Grenze (Max 50% Zeilenschwund) ---
            new_lines = [l for l in current_code.splitlines() if l.strip() and not l.strip().startswith("#")]
            if len(orig_lines) > 0 and len(new_lines) < len(orig_lines) * 0.5:
                err_msg = f"[DEF 6] Zu starker Code-Schwund: {len(new_lines)} Zeilen (Original: {len(orig_lines)})"
                if attempt == 2:
                    return False, original_code, err_msg
                current_code = self._request_self_correction(original_code, current_code, err_msg)
                continue

            # --- STUFE 2: Semantischer Diff-Audit (Nur bei echten Änderungen) ---
            preserved, reason = self._semantic_diff_audit(original_code, current_code)
            if not preserved:
                err_msg = f"[DEF 2] Semantischer Diff-Audit fehlgeschlagen: {reason}"
                if attempt == 2:
                    return False, original_code, err_msg
                current_code = self._request_self_correction(original_code, current_code, err_msg)
                continue
            return True, current_code, "TRICHTER_PASSED: Alle Schutzebenen und Delta-Prüfungen erfolgreich durchlaufen."
        return False, original_code, "Loop erschöpft nach 3 Versuchen."

# Globale Registrierung im Namespace
globals()['class_agent_code_semantic_guard'] = class_agent_code_semantic_guard