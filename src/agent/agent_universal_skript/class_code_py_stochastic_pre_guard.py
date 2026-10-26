from __future__ import annotations
import re
import sys
from pathlib import Path

# Assicuriamo la presenza del logger e del framework nel namespace globale
logger = globals().get('class_logger_audit_execution')
auto_import_framework = globals().get('class_code_py_auto_import_framework')

class class_code_py_stochastic_pre_guard:
    """
    Guardiano preventivo stochastico-deterministico per il codice.
    Risolve anomalie tipiche introdotte dagli agenti prima del parsing formale,
    inclusi blocchi troncati, disallineamenti di blocchi condizionali o eccezioni,
    e firme di funzioni disarticolate su più righe.
    """

    @staticmethod
    def global_stochastic_pre_guard(code_text: str) -> str:
        if not code_text:
            return code_text
            
        # 1. Fase 1: Identificazione e sanificazione di righe di codice troncate (Bug #22)
        lines = code_text.splitlines()
        sanitized_lines = []
        for line in lines:
            stripped = line.strip()
            # Intercetta espressioni orfane interrotte o costrutti terminanti con punti sospetti
            if re.search(r'=\s*[\w\.]+import$', stripped) or (stripped.endswith('.') and not stripped.endswith('...')):
                sanitized_lines.append(f"{line}  # [INLINE_REPAIR_FAIL]: Riga troncata rilevata e isolata preventivamente")
            else:
                sanitized_lines.append(line)
        code_text = "\n".join(sanitized_lines)

        # 2. Fase 3: Riorganizzazione delle righe vuote consecutive (Massimo 2 consentite) (Bug #7)
        code_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', code_text)
        
        # 3. Fase 4: Compressione delle firme di funzione spezzate su più righe (Bug #17)
        code_text = re.sub(r'(def\s+\w+)\s*\n\s*\((.*?)\):', r'\1(\2):', code_text, flags=re.DOTALL)
        
        # 4. Fase 5: Correzione dell'indentazione difettosa post-eccezione o contestuale
        lines = code_text.splitlines()
        final_lines = []
        i = 0
        while i < len(lines):
            current_line = lines[i]
            stripped_curr = current_line.strip()
            final_lines.append(current_line)
            
            # Controlla se la riga introduce uno scope protetto (except o with)
            if stripped_curr.endswith("except:") or (stripped_curr.startswith("except ") and stripped_curr.endswith(":")) or (stripped_curr.startswith("with ") and stripped_curr.endswith(":")):
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    next_stripped = next_line.strip()
                    # Rileva se la linea successiva contiene una logica operativa (es. assegnazione) ma manca di indentazione
                    if "=" in next_stripped and not next_stripped.startswith("#") and not next_line.startswith("    "):
                        indentation = "    " + next_line.lstrip()
                        final_lines.append(f"{indentation}  # [STOCHASTIC_PRE_GUARD]: Correzione automatica dell'indentazione dello scope")
                        i += 1
            i += 1
        
        code_text = "\n".join(final_lines)

        # 5. Stabilizzazione del Main Guard orfano con inizializzazioni sicure di ripiego (Bug #18 & #19)
        if "if __name__ == '__main__':" in code_text or "if __name__ == \"__main__\":" in code_text:
            code_text = re.sub(
                r"if\s+__name__\s*==\s*['\"]__main__['\"]:\s*(?:\n\s*)+pass",
                "if __name__ == '__main__':\n    # Guardiano Stochastico: Inizializzazione sicura di fallback\n    try:\n        if 'class_tool_ollama_service_manager' in globals():\n            globals()['class_tool_ollama_service_manager'].ensure_ollama_running()\n    except Exception as e:\n        print(f'[Guard Error]: {e}')",
                code_text
            )

        # 6. Risoluzione dei Typings orfani tramite attivazione del framework dedicato (Bug #1, #2, #3, #4, #5, #11)
        import_framework = globals().get('class_code_py_auto_import_framework')
        if not import_framework:
            try:
                from agent_universal_skript.class_code_py_auto_import_framework import class_code_py_auto_import_framework as import_framework
            except Exception:
                pass
        if import_framework:
            code_text = import_framework.repair_code_imports(code_text)

        return code_text