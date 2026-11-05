"""
Modul: class_code_py_stochastic_pre_guard
Bezeichnung: Präventiver Code-Vorbereinigungs- und Stabilitäts-Guard
Inhaltlicher Schwerpunkt:
Behebung typischer Vor-Parsing-Fehler wie abgeschnittene Zeilen, übermäßige Leerzeilen,
mehrzeilige Funktionsköpfe, fehlerhafte Scope-Einrückungen und unvollständige Main-Guards.
"""

from __future__ import annotations
import ast
import re
import sys
from pathlib import Path

# Globale Bindings
logger = globals().get("class_logger_audit_execution")
auto_import_framework = globals().get("class_code_py_auto_import_framework")


class class_code_py_stochastic_pre_guard:
    """
    Präventiver Vorfilter für Quellcode vor der formalen AST-Verarbeitung.
    Bereinigt strukturelle Anomalien, die durch Modellgenerierung entstehen können.
    """

    _cfg = globals().setdefault("_AGENT_CONFIG", {})
    MAX_BLANK_LINES: int = _cfg.setdefault("MAX_BLANK_LINES", 2)

    @classmethod
    def global_stochastic_pre_guard(cls, code_text: str) -> str:
        """Hauptmethode: Bereinigt und stabilisiert fehlerhafte Code-Strukturen."""
        print("[class_code_py_stochastic_pre_guard] Starte Arbeit: global_stochastic_pre_guard wird jetzt ausgeführt.")
        if not code_text:
            print("[class_code_py_stochastic_pre_guard] FEHLER: global_stochastic_pre_guard hat die Aufgabe nicht erfüllt. Grund: Leerer Code-Text übergeben.")
            return code_text

        try:
            # 1. Troncierte / unvollständige Zeilen isolieren
            lines = code_text.splitlines()
            sanitized = []
            for line in lines:
                s = line.strip()
                if re.search(r"=\s*[\w\.]+import$", s) or (s.endswith(".") and not s.endswith("...")):
                    sanitized.append(f"{line}  # [PRE_GUARD]: Zeile isoliert")
                else:
                    sanitized.append(line)
            code_text = "\n".join(sanitized)

            # 2. Leerzeilen normalisieren
            code_text = re.sub(r"\n\s*\n\s*\n+", "\n\n", code_text)

            # 3. Mehrzeilige Funktionssignaturen komprimieren
            code_text = re.sub(r"(def\s+\w+)\s*\n\s*\((.*?)\):", r"\1(\2):", code_text, flags=re.DOTALL)

            # 4. Einrückung nach except / with korrigieren
            lines = code_text.splitlines()
            fixed_lines = []
            i = 0
            while i < len(lines):
                curr = lines[i]
                sc = curr.strip()
                fixed_lines.append(curr)
                if sc.endswith("except:") or (sc.startswith("except ") and sc.endswith(":")) or (sc.startswith("with ") and sc.endswith(":")):
                    if i + 1 < len(lines):
                        nxt = lines[i + 1]
                        ns = nxt.strip()
                        if "=" in ns and not ns.startswith("#") and not nxt.startswith("    "):
                            fixed_lines.append(f"    {nxt.lstrip()}")
                            i += 1
                i += 1
            code_text = "\n".join(fixed_lines)

            # 5. Main-Guard stabilisieren
            if "if __name__ == '__main__':" in code_text or 'if __name__ == "__main__":' in code_text:
                code_text = re.sub(
                    r"if\s+__name__\s*==\s*['\"]__main__['\"]:\s*(?:\n\s*)+pass",
                    "if __name__ == '__main__':\n    pass",
                    code_text
                )

            # 6. Import-Reparatur anbinden
            framework = globals().get("class_code_py_auto_import_framework")
            if framework and hasattr(framework, "repair_code_imports"):
                code_text = framework.repair_code_imports(code_text)

            if not code_text:
                print("[class_code_py_stochastic_pre_guard] FEHLER: global_stochastic_pre_guard hat die Aufgabe nicht erfüllt. Grund: Ergebnis ist leer.")
                return ""
            print("[class_code_py_stochastic_pre_guard] Erfolg: global_stochastic_pre_guard erfolgreich beendet.")
            return code_text

        except Exception as e:
            print(f"[class_code_py_stochastic_pre_guard] FEHLER: global_stochastic_pre_guard hat die Aufgabe nicht erfüllt. Grund: {e}")
            return code_text

    @classmethod
    def run_stochastic_guard(cls, code_text: str) -> dict:
        """
        Zentrale Ausführungsfunktion: Bereinigt den Code präventiv und prüft,
        ob dieser anschließend erfolgreich als AST geparst werden kann.
        """
        print("[class_code_py_stochastic_pre_guard] Starte Arbeit: run_stochastic_guard wird jetzt ausgeführt.")
        try:
            cleaned = cls.global_stochastic_pre_guard(code_text)
            parsed = False
            try:
                ast.parse(cleaned)
                parsed = True
            except SyntaxError as se:
                print(f"[class_code_py_stochastic_pre_guard] FEHLER: run_stochastic_guard hat die Aufgabe nicht erfüllt. Grund: Parsing fehlgeschlagen: {se}")

            result = {
                "success":        parsed,
                "sanitized_code": cleaned,
                "modified":       cleaned != code_text
            }
            if result is None:
                print("[class_code_py_stochastic_pre_guard] FEHLER: run_stochastic_guard hat die Aufgabe nicht erfüllt. Grund: Kein Ergebnis erzeugt.")
                return {"success": False}
            print("[class_code_py_stochastic_pre_guard] Erfolg: run_stochastic_guard erfolgreich beendet.")
            return result
        except Exception as e:
            print(f"[class_code_py_stochastic_pre_guard] FEHLER: run_stochastic_guard hat die Aufgabe nicht erfüllt. Grund: {e}")
            return {"success": False, "error": str(e)}
