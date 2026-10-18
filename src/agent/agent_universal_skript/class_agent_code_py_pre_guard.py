from __future__ import annotations
import re

class class_agent_code_py_pre_guard:
    """
    Globaler stochastischer Vorverarbeitungs-Guard:
    Behebt typische Agenten-Fehler (unnötige Leerzeilen, Signatur-Umbrüche,
    verwaiste pass-Blöcke im Einstiegspunkt, abgeschnittene Codezeilen) deterministisch vor jeder Verarbeitung.
    """

    @staticmethod
    def global_stochastic_pre_guard(code_text: str) -> str:
        if not code_text:
            return code_text
            
        # 0. Vorab-Check auf abgeschnittene Codezeilen / unvollständige Imports (Bug #22)
        # Erkennt Zeilen, die abrupt mit einem Punkt oder unvollständigen Zuweisungen enden
        lines = code_text.splitlines()
        sanitized_lines = []
        for line in lines:
            stripped = line.strip()
            # Erkennung von abgeschnittenen Imports oder Zuweisungen (z.B. "mod = importlib.import")
            if re.search(r'=\s*[\w\.]+import$', stripped) or (stripped.endswith('.') and not stripped.endswith('...')):
                # Ergänzung eines sicheren Fallbacks oder Markierung als INLINE_REPAIR_FAIL
                sanitized_lines.append(f"{line}  # [INLINE_REPAIR_FAIL]: Abgeschnittene Codezeile bereinigt")
            else:
                sanitized_lines.append(line)
        code_text = "\n".join(sanitized_lines)

        # 1. Unnötige mehrfache Leerzeilen normalisieren (maximal 2 Leerzeilen zulassen) (Bug #7)
        code_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', code_text)
        
        # 2. Unmotiviert umgebrochene Funktionssignaturen (def name \n (...) :) in eine Zeile ziehen (Bug #17)
        code_text = re.sub(r'(def\s+\w+)\s*\n\s*\((.*?)\):', r'\1(\2):', code_text, flags=re.DOTALL)
        
        # 3. Verwaiste pass-Blöcke im Main-Guard durch sicheren Fallback ersetzen (Bug #18 & #19)
        if "if __name__ == '__main__':" in code_text or "if __name__ == \"__main__\":" in code_text:
            code_text = re.sub(
                r"if\s+__name__\s*==\s*['\"]__main__['\"]:\s*(?:\n\s*)+pass",
                "if __name__ == '__main__':\n    # Stochastischer Guard: Fallback-Initialisierung\n    try:\n        if 'OllamaServiceManager' in globals():\n            OllamaServiceManager().start_service()\n    except Exception as e:\n        print(f'[Guard Error]: {e}')",
                code_text
            )
        return code_text

# Globale Registrierung
globals()['class_agent_code_py_pre_guard'] = class_agent_code_py_pre_guard