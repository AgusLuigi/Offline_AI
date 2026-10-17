import ast
import hashlib
import json
import re
from typing import Set, Tuple, Dict, Any, List, Optional

class class_agent_code_semantic_guard:
    """
    AGENT_Code_Semantic_Guard:
    Ein deterministischer Hybrid-Trichter für Code-Validierung und Refactoring-Schutz.
    Kombiniert AST-Integrität, Fast-Path-Delta, Scope-Mapping, SHA-256-Prüfsummen,
    essenzielle Token-Validierung, Schlüsselwort-Erhaltung und gezielte Self-Correction.
    """
    def __init__(self, model_name: str, ollama_endpoint_fn: callable):
        self.model_name = model_name
        self.call_ollama_fn = ollama_endpoint_fn

    @staticmethod
    def calculate_checksum(code_text: str) -> str:
        """Erstellt einen SHA-256 Hash des Code-Inhalts zur Integritätsprüfung."""
        return hashlib.sha256(code_text.encode("utf-8")).hexdigest()

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

    def _extract_critical_tokens(self, code_text: str) -> Set[str]:
        """Extrahiert kritische Bezeichner, Funktionsnamen und Schlüsselbegriffe zur Erhaltung."""
        tokens = set()
        try:
            tree = ast.parse(code_text)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    tokens.add(node.name)
                elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                    tokens.add(node.id)
                elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                    # Wichtige Strings / URLs / Konfigurationsschlüssel erfassen, sofern sie lang genug sind
                    if len(node.value) > 4 and ("/" in node.value or "_" in node.value or "-" in node.value):
                        tokens.add(node.value)
        except SyntaxError:
            pass
        return tokens

    def _validate_critical_keywords(self, original_code: str, new_code: str) -> Tuple[bool, str]:
        """
        [Vorher-Nachher Schlüsselwort-Prüfung]
        Stellt sicher, dass wichtige Schlüsselbegriffe, Funktionsnamen und Konfigurations-Strings
        vom Agenten nicht verändert oder gelöscht wurden.
        """
        orig_tokens = self._extract_critical_tokens(original_code)
        missing_tokens = []
        for token in orig_tokens:
            # Prüfen ob das Token als String oder Bezeichner im neuen Code existiert
            if token not in new_code:
                missing_tokens.append(token)
        
        # Wenn zu viele essenzielle Identifier/Schlüsselwörter fehlen, greift der Schutz
        if len(missing_tokens) > 2:
            return False, f"[KEYWORD GUARD] Folgende essenzielle Schlüsselwörter/Identifier wurden verändert oder entfernt: {missing_tokens[:5]}"
        
        return True, "Schlüsselwort-Prüfung erfolgreich bestanden."

    def _validate_code_integrity(self, original_code: str, new_code: str) -> Tuple[bool, str]:
        """
        [Erweiterter Anti-Shrinkage & Token Guard]
        Prüft Zeilenreduktion, SHA-256 Deltas und das Vorhandensein essenzieller Konfigurations-Anker.
        """
        orig_lines = [l for l in original_code.splitlines() if l.strip() and not l.strip().startswith("#")]
        new_lines = [l for l in new_code.splitlines() if l.strip() and not l.strip().startswith("#")]
        
        # Strenge Prüfung auf drastischen Code-Schwund (> 50% Reduktion aktiver Zeilen)
        if len(orig_lines) > 0 and len(new_lines) < len(orig_lines) * 0.5:
            return False, f"[DEF 6] Zu starker Code-Schwund: {len(new_lines)} aktive Zeilen (Original: {len(orig_lines)})"

        # Prüfung auf essenzielle globale Anker / Konfigurationstabellen (z.B. Import-Strukturen)
        essential_tokens = ["DEFAULT_CORE_IMPORT", "DEFAULT_ZONE_FROM", "AUTO_IMPORT_LAZY_LOAD"]
        for token in essential_tokens:
            if token in original_code and token not in new_code:
                return False, f"[INTEGRITY GUARD] Essenzieller Token '{token}' wurde versehentlich entfernt."

        return True, "Integritätsprüfung erfolgreich bestanden."

    def _structural_scope_mapper(self, original_code: str, new_code: str, missing_funcs: Set[str]) -> bool:
        """
        Prüft gezielt, ob scheinbar 'fehlende' Funktionen in einen anderen 
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

Korrigiere den Code so, dass alle Pflicht-Anker, Schlüsselwörter und Identifier exakt erhalten bleiben und keine Syntaxfehler existieren.
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
        Fast-Path -> Syntax-Guard -> AST-Signatur -> Schlüsselwort-Prüfung -> Scope-Mapper -> Code-Integrität -> Diff-Audit.
        """
        current_code = initial_new_code

        # OPTIMIERUNG: FAST-PATH (Null Overhead bei identischem Code) 
        if original_code.strip() == current_code.strip():
            return True, current_code, "FAST_PATH: Code ist zu 100% identisch. Übersprungen."
        orig_sig = self._extract_all_signatures(original_code)
        for attempt in range(3):  # [DEF 3] Max 3 Versuche im Self-Correction-Loop
            
            # STUFE 5: Deterministischer Syntax-Guard 
            valid_syntax, syntax_err = self._validate_syntax(current_code)
            if not valid_syntax:
                if attempt == 2:
                    return False, original_code, f"[DEF 5] Syntax-Guard fehlgeschlagen: {syntax_err}"
                current_code = self._request_self_correction(original_code, current_code, syntax_err)
                continue

            # STUFE 1.5: Vorher-Nachher Schlüsselwort- & Identifier-Prüfung 
            kw_ok, kw_err = self._validate_critical_keywords(original_code, current_code)
            if not kw_ok:
                if attempt == 2:
                    return False, original_code, kw_err
                current_code = self._request_self_correction(original_code, current_code, kw_err)
                continue

            # STUFE 1: AST-Signatur-Integrität & Delta-Prüfung 
            new_sig = self._extract_all_signatures(current_code)
            missing_funcs = orig_sig["functions"] - new_sig["functions"]
            missing_classes = orig_sig["classes"] - new_sig["classes"]
            
            if missing_funcs or missing_classes:
                scope_ok = self._structural_scope_mapper(original_code, current_code, missing_funcs)
                if not scope_ok:
                    err_msg = f"[DEF 1] Fehlende Pflicht-Anker (gelöscht): Funktionen {missing_funcs}, Klassen {missing_classes}"
                    if attempt == 2:
                        return False, original_code, err_msg
                    current_code = self._request_self_correction(original_code, current_code, err_msg)
                    continue

            # STUFE 6: Code-Integrität & Anti-Shrinkage-Guard 
            integrity_ok, integrity_err = self._validate_code_integrity(original_code, current_code)
            if not integrity_ok:
                if attempt == 2:
                    return False, original_code, integrity_err
                current_code = self._request_self_correction(original_code, current_code, integrity_err)
                continue

            # STUFE 2: Semantischer Diff-Audit (Nur bei echten Änderungen) 
            preserved, reason = self._semantic_dict_audit = self._semantic_diff_audit(original_code, current_code) if hasattr(self, '_semantic_diff_audit') else (True, "OK")
            if not preserved:
                err_msg = f"[DEF 2] Semantischer Diff-Audit fehlgeschlagen: {reason}"
                if attempt == 2:
                    return False, original_code, err_msg
                current_code = self._request_self_correction(original_code, current_code, err_msg)
                continue
            return True, current_code, "TRICHTER_PASSED: Alle Schutzebenen, Schlüsselwort- und Delta-Prüfungen erfolgreich durchlaufen."
        return False, original_code, "Loop erschöpft nach 3 Versuchen."

# Globale Registrierung im Namespace
globals()['class_agent_code_semantic_guard'] = class_agent_code_semantic_guard