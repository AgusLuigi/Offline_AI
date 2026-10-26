import ast
import subprocess
import sys
import tempfile
from pathlib import Path

# Assicuriamo che il percorso principale sia indicizzato nel sistema
sys.path.append(str(Path(__file__).resolve().parent))

# Bootstrap automatico dell'infrastruttura condivisa
from agent_universal_skript.auto_bootstrap_and_register_agent_tools import auto_bootstrap_and_register_agent_tools
auto_bootstrap_and_register_agent_tools()

logger = globals().get('class_logger_audit_execution')
core_infra = globals().get('class_tool_core_infrastructure')

FORBIDDEN_MODULES = {"subprocess", "shutil", "socket", "ctypes", "pickle", "multiprocessing"}
FORBIDDEN_FUNCTIONS = {"eval", "exec", "__import__", "compile", "open"}
SANDBOX_TIMEOUT = 15
MAX_SANDBOX_OUTPUT_LENGTH = 4000

class class_agent_sub_verifier(core_infra if core_infra else object):
    """
    Sandbox di verifica e validazione del codice a circuito chiuso.
    Implementa controlli statici di sicurezza (AST) e test di esecuzione 
    in sub-processi isolati per impedire regressioni fatali nel codice sorgente.
    """
    
    FORBIDDEN_MODULES = FORBIDDEN_MODULES
    FORBIDDEN_FUNCTIONS = FORBIDDEN_FUNCTIONS
    SANDBOX_TIMEOUT = SANDBOX_TIMEOUT
    MAX_SANDBOX_OUTPUT_LENGTH = MAX_SANDBOX_OUTPUT_LENGTH

    @staticmethod
    def extract_code_blocks(text: str) -> list[str]:
        """Estrae in modo pulito i blocchi di codice Python racchiusi nei tag markdown della LLM."""
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
        """Ispeziona l'AST del frammento di codice per intercettare chiamate o moduli malevoli/vietati."""
        try:
            tree = ast.parse(code_snippet)
        except SyntaxError as e:
            return False, f"SyntaxError nel frammento analizzato: {e}"

        for node in ast.walk(tree):
            # Controllo importazioni standard (es: import subprocess)
            if isinstance(node, ast.Import):
                for alias in node.names:
                    base_name = alias.name.split('.')[0]
                    if base_name in cls.FORBIDDEN_MODULES:
                        return False, f"[SECURITY ATTACK] Modulo non autorizzato nell'ambiente protetto: '{base_name}'."
            
            # Controllo importazioni parziali (es: from subprocess import Popen)
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split('.')[0] in cls.FORBIDDEN_MODULES:
                    return False, f"[SECURITY ATTACK] Modulo non autorizzato nell'ambiente protetto: '{node.module}'."
            
            # Controllo built-in pericolosi (es: eval())
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in cls.FORBIDDEN_FUNCTIONS:
                        return False, f"[SECURITY ATTACK] Funzione incorporata interdetta nella sandbox: '{node.func.id}()'."
                        
        return True, "Analisi AST statica superata con successo."

    @classmethod
    def verify_code_in_sandbox(cls, code_snippet: str, project_root: Path = None, timeout_sec: int = None) -> tuple[bool, str]:
        """Esegue transazionalmente il codice in un sub-processo Python confinato nella cartella scratch."""
        if timeout_sec is None:
            timeout_sec = cls.SANDBOX_TIMEOUT

        # Utilizzo dell'architettura ereditata per determinare la root del repository
        if project_root is None:
            project_root = cls.get_project_root() if hasattr(cls, "get_project_root") else Path.cwd()

        # Fase 1: Blocco di sicurezza preventivo via AST
        is_safe, security_msg = cls._static_security_check(code_snippet)
        if not is_safe:
            return False, f"[SANDBOX GUARDED] {security_msg}"

        # Configurazione della directory isolata (Scratchpad)
        sandbox_dir = project_root / "scratch"
        sandbox_dir.mkdir(parents=True, exist_ok=True)
        
        temp_file = None
        try:
            # Creazione atomica del file temporaneo da validare
            with tempfile.NamedTemporaryFile(suffix=".py", mode="w", encoding="utf-8", dir=str(sandbox_dir), delete=False) as f:
                f.write(code_snippet)
                temp_file = Path(f.name)

            # Fase 3: Esecuzione isolata nel sub-processo protetto
            res = subprocess.run(
                [sys.executable, str(temp_file)],
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                cwd=str(sandbox_dir)
            )
            
            success = (res.returncode == 0)
            raw_output = res.stdout.strip() if success else (res.stderr.strip() or res.stdout.strip())
            
            # Fase 5: Taglio controllato dell'output per scongiurare buffer overflow
            if len(raw_output) > cls.MAX_SANDBOX_OUTPUT_LENGTH:
                output = raw_output[:cls.MAX_SANDBOX_OUTPUT_LENGTH] + "\n... [Output troncato per motivi di sicurezza e overflow]"
            else:
                output = raw_output
                
            return success, output

        except subprocess.TimeoutExpired:
            return False, f"[SANDBOX TIMEOUT] Tempo limite di esecuzione superato ({timeout_sec}s). Sospetta presenza di ciclo infinito."
        except Exception as err:
            return False, f"[SANDBOX EXCEPTION] Errore critico durante l'istanziamento del processo: {err}"
        finally:
            # Pulizia deterministica immediata del file di test temporaneo
            if temp_file and temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass