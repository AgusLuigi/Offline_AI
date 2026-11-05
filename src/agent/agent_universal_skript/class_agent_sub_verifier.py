"""
Modul: class_agent_sub_verifier
Bezeichnung: Sandbox- und Code-Verifikationswerkzeug
Inhaltlicher Schwerpunkt:
Extraktion von Python-Codeblöcken aus Markdown, statische AST-Sicherheitsanalyse
und isolierte Probe-Ausführung von Codefragmenten im Subprozess.
"""

import ast
import subprocess
import sys
import tempfile
from pathlib import Path

# Globale Bindings
logger     = globals().get("class_logger_audit_execution")
core_infra = globals().get("class_tool_core_infrastructure")


class class_agent_sub_verifier:
    """
    Werkzeug zur Verifikation und Validierung von generiertem Code.
    Führt statische AST-Prüfungen durch und validiert Codeausführung in einer isolierten Umgebung.
    """

    _cfg = globals().setdefault("_AGENT_CONFIG", {})
    FORBIDDEN_MODULES: set         = _cfg.setdefault("FORBIDDEN_MODULES",         {"subprocess", "shutil", "socket", "ctypes", "pickle", "multiprocessing"})
    FORBIDDEN_FUNCTIONS: set       = _cfg.setdefault("FORBIDDEN_FUNCTIONS",       {"eval", "exec", "__import__", "compile", "open"})
    SANDBOX_TIMEOUT: int           = _cfg.setdefault("SANDBOX_TIMEOUT",           15)
    MAX_SANDBOX_OUTPUT_LENGTH: int = _cfg.setdefault("MAX_SANDBOX_OUTPUT_LENGTH", 4000)

    @staticmethod
    def extract_code_blocks(text: str) -> list:
        """Extrahiert saubere Python-Codeblöcke aus Markdown-Text."""
        print("[class_agent_sub_verifier] Starte Arbeit: extract_code_blocks wird jetzt ausgeführt.")
        blocks = []
        if not text:
            print("[class_agent_sub_verifier] FEHLER: extract_code_blocks hat die Aufgabe nicht erfüllt. Grund: Leerer Text übergeben.")
            return blocks
        if "```python" in text:
            parts = text.split("```python")
            for p in parts[1:]:
                if "```" in p:
                    code = p.split("```")[0].strip()
                    if code:
                        blocks.append(code)
        elif "```" in text:
            parts = text.split("```")
            for i in range(1, len(parts), 2):
                code = parts[i].strip()
                if code and not any(code.startswith(tag) for tag in ["markdown", "sql", "bash", "json", "yaml"]):
                    blocks.append(code)
        print("[class_agent_sub_verifier] Erfolg: extract_code_blocks erfolgreich beendet.")
        return blocks

    @classmethod
    def _static_security_check(cls, code_snippet: str) -> tuple:
        """Prüft den AST auf unerlaubte Modulimporte oder gefährliche Aufrufe."""
        print("[class_agent_sub_verifier] Starte Arbeit: _static_security_check wird jetzt ausgeführt.")
        try:
            tree = ast.parse(code_snippet)
        except SyntaxError as e:
            print(f"[class_agent_sub_verifier] FEHLER: _static_security_check hat die Aufgabe nicht erfüllt. Grund: Syntaxfehler: {e}")
            return False, f"SyntaxError: {e}"

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    base_name = alias.name.split(".")[0]
                    if base_name in cls.FORBIDDEN_MODULES:
                        print(f"[class_agent_sub_verifier] FEHLER: _static_security_check hat die Aufgabe nicht erfüllt. Grund: Nicht autorisiertes Modul: '{base_name}'")
                        return False, f"Nicht autorisiertes Modul: '{base_name}'"
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split(".")[0] in cls.FORBIDDEN_MODULES:
                    print(f"[class_agent_sub_verifier] FEHLER: _static_security_check hat die Aufgabe nicht erfüllt. Grund: Nicht autorisiertes Modul: '{node.module}'")
                    return False, f"Nicht autorisiertes Modul: '{node.module}'"
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in cls.FORBIDDEN_FUNCTIONS:
                    print(f"[class_agent_sub_verifier] FEHLER: _static_security_check hat die Aufgabe nicht erfüllt. Grund: Verbotene Funktion: '{node.func.id}()'")
                    return False, f"Verbotene Funktion aufgerufen: '{node.func.id}()'"

        result = True, "AST-Analyse erfolgreich bestanden."
        print("[class_agent_sub_verifier] Erfolg: _static_security_check erfolgreich beendet.")
        return result

    @classmethod
    def verify_code_in_sandbox(cls, code_snippet: str, project_root: Path = None, timeout_sec: int = None) -> tuple:
        """Führt den Code zur Probe in einem temporären Subprozess aus."""
        print("[class_agent_sub_verifier] Starte Arbeit: verify_code_in_sandbox wird jetzt ausgeführt.")
        timeout_sec = timeout_sec or cls.SANDBOX_TIMEOUT

        if project_root is None:
            infra = globals().get("class_tool_core_infrastructure")
            project_root = infra.get_project_root() if infra and hasattr(infra, "get_project_root") else Path.cwd()

        is_safe, msg = cls._static_security_check(code_snippet)
        if not is_safe:
            print(f"[class_agent_sub_verifier] FEHLER: verify_code_in_sandbox hat die Aufgabe nicht erfüllt. Grund: Sicherheitsprüfung fehlgeschlagen: {msg}")
            return False, f"[SECURITY_GUARD] {msg}"

        temp_dir  = project_root / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_file = None

        try:
            with tempfile.NamedTemporaryFile(suffix=".py", mode="w", encoding="utf-8", dir=str(temp_dir), delete=False) as f:
                f.write(code_snippet)
                temp_file = Path(f.name)

            res = subprocess.run(
                [sys.executable, str(temp_file)],
                capture_output=True, text=True,
                timeout=timeout_sec, cwd=str(temp_dir)
            )

            success    = (res.returncode == 0)
            raw_output = res.stdout.strip() if success else (res.stderr.strip() or res.stdout.strip())
            output     = raw_output[:cls.MAX_SANDBOX_OUTPUT_LENGTH] + "\n... [Output gekürzt]" if len(raw_output) > cls.MAX_SANDBOX_OUTPUT_LENGTH else raw_output

            if not success:
                print(f"[class_agent_sub_verifier] FEHLER: verify_code_in_sandbox hat die Aufgabe nicht erfüllt. Grund: Exitcode {res.returncode}: {output}")
                return False, output

            print("[class_agent_sub_verifier] Erfolg: verify_code_in_sandbox erfolgreich beendet.")
            return True, output

        except subprocess.TimeoutExpired:
            print(f"[class_agent_sub_verifier] FEHLER: verify_code_in_sandbox hat die Aufgabe nicht erfüllt. Grund: Timeout nach {timeout_sec}s.")
            return False, f"[TIMEOUT] Zeitlimit ({timeout_sec}s) überschritten."
        except Exception as e:
            print(f"[class_agent_sub_verifier] FEHLER: verify_code_in_sandbox hat die Aufgabe nicht erfüllt. Grund: {e}")
            return False, f"[EXCEPTION] {e}"
        finally:
            if temp_file and temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass

    @classmethod
    def run_sub_verifier(cls, raw_llm_response: str, project_root: Path = None) -> dict:
        """
        Zentrale Ausführungsfunktion: Extrahiert Codeblöcke aus einer LLM-Antwort,
        prüft deren Sicherheit und testet die Ausführung im Subprozess.
        """
        print("[class_agent_sub_verifier] Starte Arbeit: run_sub_verifier wird jetzt ausgeführt.")
        try:
            blocks = cls.extract_code_blocks(raw_llm_response)
            if not blocks:
                print("[class_agent_sub_verifier] FEHLER: run_sub_verifier hat die Aufgabe nicht erfüllt. Grund: Keine Codeblöcke im Text gefunden.")
                return {"valid": False, "error": "Keine Codeblöcke gefunden", "code": None}

            code_to_verify = blocks[0]
            success, output = cls.verify_code_in_sandbox(code_to_verify, project_root=project_root)
            result = {
                "valid":       success,
                "code":        code_to_verify,
                "output":      output,
                "block_count": len(blocks)
            }
            if result is None:
                print("[class_agent_sub_verifier] FEHLER: run_sub_verifier hat die Aufgabe nicht erfüllt. Grund: Kein Ergebnis erzeugt.")
                return {"valid": False}
            print("[class_agent_sub_verifier] Erfolg: run_sub_verifier erfolgreich beendet.")
            return result
        except Exception as e:
            print(f"[class_agent_sub_verifier] FEHLER: run_sub_verifier hat die Aufgabe nicht erfüllt. Grund: {e}")
            return {"valid": False, "error": str(e)}
