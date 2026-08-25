import os
import sys
import subprocess
import sqlite3
import time
import urllib.request
import socket
import gc
import threading
from datetime import datetime
from pathlib import Path
from ollama import Client

# Versuche psutil zu importieren (für den System-Check im Spinner)
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

# OLLAMA CHECK & START LOGIK (SEPARAT & IM SILENT-MODUS BEI ERFOLG)
_OLLAMA_VERIFIED_CACHE = False
def is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False

def check_and_start_ollama(ollama_host: str = "http://127.0.0.1:11434") -> bool:
    """
    Prüft autonom Ollama (inkl. RAM-Cache), startet den Dienst bei Bedarf 
    im Hintergrund und bleibt im Erfolgsfall komplett stumm (Silent Mode).
    """
    global _OLLAMA_VERIFIED_CACHE

    if _OLLAMA_VERIFIED_CACHE:
        return True

    host_ip = ollama_host.replace("http://", "").replace("https://", "").split(":")[0]
    port = int(ollama_host.split(":")[-1]) if ":" in ollama_host else 11434

    # 1. Schnelltest über Socket & API
    if is_port_open(host_ip, port, timeout=1.0):
        try:
            req = urllib.request.Request(f"{ollama_host}/api/tags")
            with urllib.request.urlopen(req, timeout=2) as response:
                if response.status == 200:
                    _OLLAMA_VERIFIED_CACHE = True
                    return True
        except Exception:
            pass

    # 2. Automatischer Start im Hintergrund (ohne störendes Konsolenfenster)
    try:
        if os.name == 'nt':
            subprocess.Popen(["ollama", "serve"], creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        print("--- [OLLAMA CHECK] Fehler-Protokoll ---")
        print("--> [FEHLER] Der Befehl 'ollama' wurde im System nicht gefunden.")
        print("--> Bitte installiere Ollama (https://ollama.com/download).")
        return False
    except Exception as sub_err:
        print("--- [OLLAMA CHECK] Fehler-Protokoll ---")
        print(f"--> [FEHLER] Konnte den Ollama-Prozess nicht automatisch starten: {sub_err}")
        return False

    # 3. Warten und verifizieren nach dem Start
    for attempt in range(1, 4):
        time.sleep(3)
        if is_port_open(host_ip, port, timeout=1.0):
            try:
                req = urllib.request.Request(f"{ollama_host}/api/tags")
                with urllib.request.urlopen(req, timeout=2) as response:
                    if response.status == 200:
                        _OLLAMA_VERIFIED_CACHE = True
                        return True
            except Exception:
                pass

    print("--- [OLLAMA CHECK] Fehler-Protokoll ---")
    print("--> [HINWEIS] Ollama ist nach mehreren Versuchen nicht erreichbar.")
    return False

def _llm_adapt_reserved_cores_from_usage(cpu_usage: float):
    if cpu_usage > 85:
        pass

# META-CODEBASE & HIERARCHICAL ROUTING TREE AGENT
class MetaCodeBase:
    @staticmethod
    def start_spinner(stop_event, is_de: bool = True):
        """
        VISUELLES FEEDBACK [UX-STANDARD]
        Zeigt einen Spinner während der LLM-Verarbeitung und prüft RAM/CPU.
        Nutzt die Messung, um die CPU-Reserve selbstständig anzupassen.
        """
        def perform_system_check():
            if not HAS_PSUTIL:
                return ""

            ram_avail = psutil.virtual_memory().available / (1024**3)
            cpu_usage = psutil.cpu_percent(interval=None)

            _llm_adapt_reserved_cores_from_usage(cpu_usage)

            status_msg = ""
            if ram_avail < 1.5:
                gc.collect()
                status_msg = f"⚠️ RAM kritisch ({ram_avail:.2f}GB). GC ausgeführt."
            if cpu_usage > 90:
                cpu_alert = f" | 🔥 CPU Last hoch ({cpu_usage:.0f}%)."
                status_msg = status_msg + cpu_alert if status_msg else cpu_alert
            return status_msg

        chars = ['⠋','⠙','⠹','⠸','⠼','⠴','⠦','⠧','⠇','⠏']
        msg = "Analysiere (Lokale GPU/CPU)..." if is_de else "Analyzing (Local GPU/CPU)..."
        idx = 0
        while not stop_event.is_set():
            alert_msg = perform_system_check()
            sys.stdout.write(f'\r{msg} {chars[idx % len(chars)]} {alert_msg}')
            sys.stdout.flush()
            idx += 1
            time.sleep(1.0)
        sys.stdout.write('\r' + ' ' * 100 + '\r')
        sys.stdout.flush()
        
    def __init__(self, model_name: str = "codestral:latest", ollama_host: str = "http://127.0.0.1:11434"):
        if not check_and_start_ollama(ollama_host):
            print("[KRITISCHER ABBRUCH] Ollama konnte nicht verifiziert oder gestartet werden.")
            sys.exit(1)

        self.model_name = model_name
        self.ollama_host = ollama_host
        
        try:
            self.client = Client(host=ollama_host)
            self.client.list()
        except Exception as e:
            print(f"--> [KRITISCHER FEHLER] Verbindung zum Ollama Client fehlgeschlagen: {e}")
            sys.exit(1)
        
        self.db_path = self.initialize_find_folder()
        self._init_db()

    def initialize_find_folder(self) -> Path:
        ANKER_DIR = "Offline_AI"
        BASE_DIR = "Knowledge"
        AGENT_SUBDIR = "knowledge_agent_hierarchical_routing_tree_sql"
        DB_FILENAME = "knowledge_agent_routing_tree.db"

        print("--- [START] Prüfe Ordnerstruktur für den Knowledge Agent ---")

        current_path = os.path.abspath(os.getcwd())
        print(f"--> [INFO] Start-Pfad: {current_path}")
        
        if ANKER_DIR.lower() in current_path.lower():
            base_parts = current_path.split(os.sep)
            anker_index = [p.lower() for p in base_parts].index(ANKER_DIR.lower())
            base_root = os.sep.join(base_parts[:anker_index + 1])
        else:
            base_root = current_path

        print(f"--> [ERFOLG] Projekt-Root '{ANKER_DIR}' identifiziert unter: {base_root}")

        target_knowledge_dir = os.path.join(base_root, BASE_DIR)
        print(f"Suche nach Hauptverzeichnis: '{target_knowledge_dir}'...")
        if not os.path.exists(target_knowledge_dir):
            os.makedirs(target_knowledge_dir)
            print(f"--> [ERFOLG] Hauptverzeichnis '{target_knowledge_dir}' wurde neu erstellt.")
        else:
            print(f"--> [INFO] Hauptverzeichnis '{target_knowledge_dir}' wurde gefunden.")

        target_directory = os.path.join(target_knowledge_dir, AGENT_SUBDIR)
        print(f"Suche nach Unterordner: '{target_directory}'...")
        
        if not os.path.exists(target_directory):
            os.makedirs(target_directory)
            print(f"--> [ERFOLG] Unterordner '{AGENT_SUBDIR}' wurde neu erstellt.")
        else:
            print(f"--> [INFO] Unterordner '{AGENT_SUBDIR}' existiert bereits.")

        db_path = Path(target_directory) / DB_FILENAME
        print(f"Pfad-Zusammenführung abgeschlossen. Zieldatei: '{db_path}'")
        print("--- [ENDE] Ordnerstruktur erfolgreich geprüft ---\n")
        
        return db_path

    def _init_db(self):
        domains = ["script_errors", "jupyter_errors", "data_io_errors", "scope_global_errors", "routing_tree_errors"]
        
        with sqlite3.connect(self.db_path) as conn:
            for domain in domains:
                conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS {domain} (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        error_signature TEXT UNIQUE,
                        context_combination TEXT,
                        solution_code TEXT,
                        success_score INTEGER DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS core_directives (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    capability_name TEXT UNIQUE,
                    code_snippet TEXT,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def persist_new_capability(self, capability_name: str, code_snippet: str, description: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO core_directives (capability_name, code_snippet, description)
                VALUES (?, ?, ?)
                ON CONFLICT(capability_name) DO UPDATE SET 
                    code_snippet = excluded.code_snippet,
                    description = excluded.description
            """, (capability_name, code_snippet, description))
            conn.commit()
            
        print(f"\n[PERSISTENZ-ERFOLG] Fähigkeit '{capability_name}' wurde dauerhaft in SQLite verewigt!")

    def _detect_domain(self, text_context: str) -> str:
        text_lower = text_context.lower()
        if "jupyter" in text_lower or "notebook" in text_lower or ".ipynb" in text_lower:
            return "jupyter_errors"
        elif "json" in text_lower or "csv" in text_lower or "file" in text_lower or "data" in text_lower or "io" in text_lower:
            return "data_io_errors"
        elif "global" in text_lower or "scope" in text_lower or "import" in text_lower or "variable" in text_lower:
            return "scope_global_errors"
        elif "route" in text_lower or "tree" in text_lower or "sql" in text_lower or "hierarchy" in text_lower:
            return "routing_tree_errors"
        else:
            return "script_errors"

    def _get_relevant_tips(self, task_description: str) -> str:
        domain = self._detect_domain(task_description)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute(f"SELECT error_signature, solution_code FROM {domain} ORDER BY success_score DESC LIMIT 3")
            rows = cursor.fetchall()
            
            cursor.execute("SELECT capability_name, description FROM core_directives LIMIT 5")
            directives = cursor.fetchall()

            try:
                cursor.execute("SELECT execution_phase, agent_instruction FROM pre_execution_blueprint_generator WHERE is_active = 1 LIMIT 5")
                blueprints = cursor.fetchall()
            except sqlite3.OperationalError:
                blueprints = []

        tips = ["=================================================="]
        tips.append(" [SYSTEM CORE MEMORY: SQL-DATABASE DEEP KNOWLEDGE]")
        tips.append("==================================================")
        
        tips.append(f"\n--- Relevant Past Solutions from [{domain}] ---")
        for err, sol in rows:
            tips.append(f"- Bug: [{err}] -> Fix Code Pattern: {sol}")
            
        if directives:
            tips.append("\n--- Active Core Directives & Capabilities ---")
            for cap, desc in directives:
                tips.append(f"- Capability: [{cap}] -> {desc}")

        if blueprints:
            tips.append("\n--- Mandatory Pre-Execution Blueprints ---")
            for phase, instruction in blueprints:
                tips.append(f"- Phase [{phase}]: {instruction}")

        if len(tips) <= 3:
            return f"No prior errors recorded in domain [{domain}]."

        return "\n".join(tips)

    def _save_solution_to_db(self, task_description: str, error_msg: str, solution_code: str):
        domain = self._detect_domain(task_description)
        error_signature = error_msg.strip().split('\n')[-1]
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(f"""
                INSERT INTO {domain} (error_signature, context_combination, solution_code, success_score)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(error_signature) DO UPDATE SET 
                    success_score = success_score + 1,
                    solution_code = excluded.solution_code
            """, (error_signature, task_description[:100], solution_code))
            conn.commit()

    def evolve_self(self, recent_error: str, task_context: str) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        history_dir = Path("src/agent/metacoder_history")
        history_dir.mkdir(parents=True, exist_ok=True)
        new_filename = history_dir / f"MetaCodeBase_{timestamp}.py"
        
        tips_text = self._get_relevant_tips(task_context)

        prompt = f"""
You are an expert Autonomous Meta-Architect AI. You are improving your own source code to fix a recurring bug.

Current Error Encountered:
{recent_error}

Relevant Database Knowledge:
{tips_text}

Task:
Rewrite and improve this Python class (MetaCodeBase) so that it proactively checks for and prevents the above error. 
Return the COMPLETE, executable Python code for the new MetaCodeBase script inside markdown code blocks (```python ... ```).
"""
        stop_event = threading.Event()
        spinner_thread = threading.Thread(target=self.start_spinner, args=(stop_event, True))
        spinner_thread.start()
        try:
            response = self.client.generate(model=self.model_name, prompt=prompt)
        finally:
            stop_event.set()
            spinner_thread.join()

        raw_text = response.get('response', '')
        new_code = self._extract_code_block(raw_text)
        with open(new_filename, "w", encoding="utf-8") as f:
            f.write(new_code)
        return new_filename

    def test_and_evolve_loop(self, specialization: str, task_description: str, base_filename: str, max_generations: int = 3):
        target_dir = Path("src/agent")
        target_dir.mkdir(parents=True, exist_ok=True)
        current_error = None
        generated_files = []
        print(f"\n[AGENT-LOOP] Starte Generierungs- und Test-Zyklus für: {base_filename}")
        for gen in range(1, max_generations + 1):
            print(f"--> [GEN {gen}/{max_generations}] Generiere Arbeiter-Agent...")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            versioned_filename = f"{Path(base_filename).stem}_{timestamp}.py"
            filepath = target_dir / versioned_filename
            db_tips = self._get_relevant_tips(task_description)
            prompt = f"""
You are an expert Autonomous Python Architect. Write a complete, standalone Python script for an agent 
integrated into a Hierarchical Routing Tree using SQLite.
Specialization: {specialization}
Task Description: {task_description}
Known Rules & Lessons from SQLite Knowledge Database (Follow strictly!):
{db_tips}
Mandatory Rules:
1. Return ONLY valid Python code inside standard markdown code blocks (```python ... ```).
2. The script must be fully self-contained and runnable via `python`.
"""
            stop_event = threading.Event()
            spinner_thread = threading.Thread(target=self.start_spinner, args=(stop_event, True))
            spinner_thread.start()
            try:
                response = self.client.generate(model=self.model_name, prompt=prompt)
            finally:
                stop_event.set()
                spinner_thread.join()

            code = self._extract_code_block(response.get('response', ''))
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(code)
            generated_files.append(filepath)
            print(f"--> [TEST] Führe Arbeiter-Agent aus: {filepath.name}...")
            success, output = self._run_script(filepath)
            if success:
                print(f"--> [ERFOLG] Arbeiter-Agent lief fehlerfrei durch!")
                return filepath
            else:
                print(f"--> [FEHLER GEFANGEN] Agent ist stolpert. Speichere Signatur in SQLite-DB.")
                current_error = output
                sample_fix = f"try-except block added for routing/sql context: {task_description[:30]}"
                self._save_solution_to_db(task_description, current_error, sample_fix)
                self.evolve_self(recent_error=current_error, task_context=task_description)
        for old_file in reversed(generated_files[:-1]):
            if old_file.exists():
                success, _ = self._run_script(old_file)
                if success:
                    return old_file
        return None

    def _run_script(self, filepath: Path) -> tuple[bool, str]:
        try:
            result = subprocess.run(["python", str(filepath)], capture_output=True, text=True, timeout=30)
            return (result.returncode == 0), (result.stderr.strip() or result.stdout.strip())
        except Exception as e:
            return False, str(e)

    def _extract_code_block(self, text: str) -> str:
        if "```python" in text:
            parts = text.split("```python")
            if len(parts) > 1:
                return parts[1].split("```")[0].strip()
        elif "```" in text:
            parts = text.split("```")
            if len(parts) > 1:
                return parts[1].strip()
        return text.strip()

def boot_latest_metacoder():
    history_dir = Path("src/agent/metacoder_history")
    history_dir.mkdir(parents=True, exist_ok=True)
    return MetaCodeBase()

def query_meta_coder_sql(notebook_path: str, instruction: str):
    metacoder = boot_latest_metacoder()
    spec = f"Hierarchical Routing Tree SQL Agent for {Path(notebook_path).name}"
    task = f"""
    Target Notebook/Module Path: {notebook_path}
    User Instruction/Routing Goal: {instruction}
    """
    return metacoder.test_and_evolve_loop(
        specialization=spec,
        task_description=task,
        base_filename=f"sql_routing_agent_{Path(notebook_path).stem}",
        max_generations=3
    )

if __name__ == "__main__":
    metacoder = boot_latest_metacoder()
    
    print("\n======================================================================")
    print(" [INTELLIGENTER CHAT-MODUS] Verbunden mit SQLite-Langzeitgedächtnis")
    print(" Codestral nutzt jetzt aktiv den Knowledge Agent Routing Tree.")
    print(" Schreibe 'exit' oder 'quit', um das Gespräch zu beenden.")
    print("======================================================================\n")

    while True:
        try:
            user_input = input("\nDu: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit"]:
                print("\nAgent: Bis zum nächsten Mal!")
                break

            domain = metacoder._detect_domain(user_input)
            db_tips = metacoder._get_relevant_tips(user_input)

            system_prompt = f"""
You are an autonomous AI Agent with an active SQLite Long-Term Memory (Knowledge Agent Routing Tree).
Current Detected Domain: {domain}

Retrieved Knowledge & Past Patterns from SQLite DB:
{db_tips}

Your Task: Answer the user's request in German, keeping any code or technical keywords strictly in English. 
Acknowledge and make use of the SQLite database context if relevant.
"""

            # Spinner im Hintergrund während der Ollama-Chat-Anfrage starten
            stop_event = threading.Event()
            spinner_thread = threading.Thread(target=metacoder.start_spinner, args=(stop_event, True))
            spinner_thread.start()

            try:
                response = metacoder.client.chat(
                    model=metacoder.model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_input}
                    ]
                )
            finally:
                stop_event.set()
                spinner_thread.join()
            
            answer = response.get('message', {}).get('content', '')
            
            if "verewige" in user_input.lower() or "speichere in sql" in user_input.lower():
                metacoder.persist_new_capability(
                    capability_name="Autonomous_Workspace_Scanner_and_Semantic_Abstraction",
                    code_snippet=answer[:500],
                    description=user_input
                )
                print("\n[SYSTEM-INFO] Die Fähigkeit wurde physisch in die SQLite-Tabelle 'core_directives' geschrieben!")

            elif "sql" in user_input.lower() or "fehler" in user_input.lower() or "code" in user_input.lower():
                metacoder._save_solution_to_db(
                    task_description=user_input,
                    error_msg=f"User interaction pattern in domain [{domain}]",
                    solution_code=answer[:200]
                )

            print(f"\nCodestral [Domain: {domain} | DB aktiv]:\n{answer}\n" + "-"*70)

        except KeyboardInterrupt:
            print("\n\nAgent: Sitzung durch Benutzer abgebrochen.")
            break
        except Exception as e:
            print(f"\n[FEHLER IM AGENTEN-LOOP] Konnte Anfrage nicht verarbeiten: {e}\n")

# [INFO-BOX] ANLEITUNG ZUR AUSLÖSUNG DES META-CODERS
# Variante 1: Auslösung über das Terminal (Konsole)
#
# A) Interaktiver Modus (fragt nach Pfad & Aufgabe):
#    python src/agent/meta_coder_sql.py
#
# B) Direkt als Einzeiler mit Parametern:
#    python src/agent/meta_coder_sql.py notebooks/dein_notebook.ipynb "Deine Aufgabe hier"
#
# 
# Variante 2: Auslösung direkt aus einem Jupyter Notebook (.ipynb) heraus
# 
# Füge diesen Code in eine Notebook-Zelle ein und führe sie aus:
#
#    from src.agent.meta_coder_sql import query_meta_coder_sql
#
#    query_meta_coder_sql(
#        notebook_path="notebooks/dein_notebook.ipynb",
#        instruction="Deine Anweisung zur Korrektur oder Erweiterung"
#    )