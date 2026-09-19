import ast
import subprocess
import sys
import tempfile
from pathlib import Path

# Hauptverzeichnis zum Python-Pfad hinzufügen
sys.path.append(str(Path(__file__).resolve().parent))

# Funktion importieren und direkt ausführen
from agent_universal_skript.auto_bootstrap_and_register_agents import auto_bootstrap_and_register_agents
auto_bootstrap_and_register_agents()

class SubAgentVerifier(coreInfrastructure):
    """
    Closed-Loop Code Execution & Security Sandbox Verifier.
    Nutzt ausschließlich die zentrale CoreInfrastructure (Vererbung), 
    um Redundanzen zu vermeiden und gemeinsame Verbesserungen zu garantieren.
    """
    
    FORBIDDEN_MODULES = {"subprocess", "shutil", "socket", "ctypes", "pickle", "multiprocessing"}
    FORBIDDEN_FUNCTIONS = {"eval", "exec", "__import__", "compile", "open"}

    @staticmethod
    def extract_code_blocks(text: str) -> list[str]:
        """Extrahiert alle Python-Codeblöcke aus einer Textantwort."""
        blocks = []
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
        return blocks

    @classmethod
    def _static_security_check(cls, code_snippet: str) -> tuple[bool, str]:
        """Führt eine statische AST-Analyse durch, um schädliche Befehle vorab abzufangen."""
        try:
            tree = ast.parse(code_snippet)
        except SyntaxError as e:
            return False, f"Syntaxfehler im Code: {e}"

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    base_name = alias.name.split('.')[0]
                    if base_name in cls.FORBIDDEN_MODULES:
                        return False, f"Sicherheitsverletzung: Das Modul '{base_name}' ist im Sandkasten untersagt."
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split('.')[0] in cls.FORBIDDEN_MODULES:
                    return False, f"Sicherheitsverletzung: Das Modul '{node.module}' ist im Sandkasten untersagt."
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in cls.FORBIDDEN_FUNCTIONS:
                        return False, f"Sicherheitsverletzung: Die Funktion '{node.func.id}()' ist untersagt."
                        
        return True, "AST-Check bestanden."

    @classmethod
    def verify_code_in_sandbox(cls, code_snippet: str, project_root: Path = None, timeout_sec: int = 15) -> tuple[bool, str]:
        """
        Führt das Code-Snippet in einem separaten Python-Subprozess im Sandbox-Verzeichnis aus.
        Greift direkt auf die zentrale get_project_root()-Methode der CoreInfrastructure zurück.
        """
        # 1. Nutzung der zentralen, vererbten Infrastruktur-Logik
        if project_root is None:
            project_root = cls.get_project_root()

        # 2. Statische AST-Sicherheitsprüfung
        is_safe, security_msg = cls._static_security_check(code_snippet)
        if not is_safe:
            return False, f"[SECURITY BLOCK] {security_msg}"

        sandbox_dir = project_root / "scratch"
        sandbox_dir.mkdir(parents=True, exist_ok=True)
        
        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".py", mode="w", encoding="utf-8", dir=str(sandbox_dir), delete=False) as f:
                f.write(code_snippet)
                temp_file = Path(f.name)

            res = subprocess.run(
                [sys.executable, str(temp_file)],
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                cwd=str(sandbox_dir)  # Ausführung isoliert im scratch-Ordner
            )
            
            success = (res.returncode == 0)
            max_output_length = 4000
            raw_output = res.stdout.strip() if success else (res.stderr.strip() or res.stdout.strip())
            
            if len(raw_output) > max_output_length:
                output = raw_output[:max_output_length] + "\n... [Output aus Sicherheitsgründen abgeschnitten]"
            else:
                output = raw_output
                
            return success, output

        except subprocess.TimeoutExpired:
            return False, f"Sandbox execution timeout ({timeout_sec}s exceeded - mögliche Endlosschleife)."
        except Exception as err:
            return False, f"Sandbox execution error: {err}"
        finally:
            if temp_file and temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass

# Globale Registrierung im Namespace
globals()['SubAgentVerifier'] = SubAgentVerifier