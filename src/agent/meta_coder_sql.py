import os
import sys
import subprocess
import sqlite3
import time
import gc
import threading
from datetime import datetime
from pathlib import Path
from ollama import Client

# Globale Einstellungen
_OLLAMA_VERIFIED_CACHE = False

# Globale Einstellungen (Variablennamen wie gewünscht beibehalten/angepasst)
ANKER_DIR = "Offline_AI"
BASE_DIR = "Knowledge"
SUBFOLDER = "Knowledge_Agent_Hierarchical_Routing_Tree_SQL"
DB_FILENAME = "Knowledge_Agent_Routing_tree.db"
OLLAMA_CHECKER_FILENAME = "__ollama_running.py"

class ResourceAwareSpinner:
    """
    Kapselt den visuellen Terminal-Spinner inklusive Live-Ressourcenüberwachung (CPU/RAM).
    Läuft fehlertolerant im Hintergrund-Thread, ohne den Hauptprozess zu blockieren.
    """
    # Globale Schutz- und Mindesteinstellungen für den Agenten
    MIN_RAM_MB = 2000          # Mindestens 2 GB RAM-Sicherheitspuffer
    MAX_CPU_THRESHOLD = 90.0   # Warnschwelle bei CPU-Auslastung
    SPINNER_INTERVAL = 1.0     # Taktung der Aktualisierung in Sekunden

    def __init__(self, agent_name: str = "Codestral-Agent"):
        self.agent_name = agent_name
        self.has_psutil = self._check_psutil()

    @staticmethod
    def _check_psutil() -> bool:
        try:
            import psutil
            return True
        except ImportError:
            return False

    def _get_system_metrics(self) -> str:
        """Sammelt ressourcenschonend CPU- und RAM-Werte für die Live-Anzeige."""
        if not self.has_psutil:
            return ""
        
        try:
            import psutil
            ram_avail = psutil.virtual_memory().available / (1024**3)
            cpu_usage = psutil.cpu_percent(interval=None)

            # Automatisches Aufräumen, falls der RAM unter das Limit fällt
            if ram_avail < (self.MIN_RAM_MB / 1024):
                gc.collect()
                return f"⚠️ RAM kritisch ({ram_avail:.2f}GB) | GC aktiv"

            if cpu_usage > self.MAX_CPU_THRESHOLD:
                return f"🔥 CPU Last hoch ({cpu_usage:.0f}%)"

            return f"RAM frei: {ram_avail:.1f}GB | CPU: {cpu_usage:.0f}%"
        except Exception:
            return ""

    def run(self, stop_event: threading.Event, is_de: bool = True):
        """
        Startet die Endlos-Visualisierung im Terminal, bis das `stop_event` gesetzt wird.
        """
        chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        base_msg = f"[{self.agent_name}] Arbeitet..." if is_de else f"[{self.agent_name}] Processing..."
        idx = 0
        
        try:
            while not stop_event.is_set():
                metrics = self._get_system_metrics()
                metric_str = f" | {metrics}" if metrics else ""
                
                output_line = f"\r{base_msg} {chars[idx % len(chars)]}{metric_str}   "
                sys.stdout.write(output_line)
                sys.stdout.flush()
                
                idx += 1
                time.sleep(self.SPINNER_INTERVAL)
        except Exception:
            pass  # Verhindert jeglichen Crash des Hauptprogramms durch Darstellungsfehler
        finally:
            # Zeile nach Beendigung sauber im Terminal bereinigen
            sys.stdout.write('\r' + ' ' * 100 + '\r')
            sys.stdout.flush()

# META-CODEBASE & HIERARCHICAL ROUTING TREE AGENT
class MetaCodeBase:
    """
    Ein autonomer Agent, der sich selbst weiterentwickelt, indem er Fehler erkennt, Lösungen
    in einer SQLite-Datenbank speichert und sich iterativ verbessert.
    """
    @staticmethod
    def get_project_root() -> Path:
        """
        Ermittelt den zentralen Ankerpunkt ('Offline_AI') als Basis-Root-Verzeichnis.
        """
        try:
            # 1. Ausgehend von dieser Datei nach oben suchen
            file_path = Path(__file__).resolve()
            for parent in [file_path] + list(file_path.parents):
                if parent.name.lower() == ANKER_DIR.lower():
                    return parent

            # 2. Ausgehend vom aktuellen Arbeitsverzeichnis suchen
            current_path = Path(os.path.abspath(os.getcwd()))
            if ANKER_DIR.lower() in [p.lower() for p in current_path.parts]:
                base_parts = list(current_path.parts)
                anker_index = [p.lower() for p in base_parts].index(ANKER_DIR.lower())
                base_root = Path(*base_parts[:anker_index + 1])
                if current_path.drive and not base_root.drive:
                    base_root = Path(current_path.drive) / base_root
                return base_root
            return current_path
        except Exception as e:
            print(f"[KRITISCHER FEHLER] Konnte Ankerpunkt nicht finden: {e}")
            return Path(os.getcwd())

    @staticmethod
    def project_find_data(filename: str) -> Path:
        """
        Universal-Funktion 1: Sucht den Dateipfad ausgehend vom Ankerpunkt 
        in allen Unterordnern abwärts (case-insensitive).
        """
        base_root = MetaCodeBase.get_project_root()
        fn_lower = filename.lower()
        for path in base_root.rglob("*"):
            if path.is_file() and path.name.lower() == fn_lower:
                return path
        return None

    @staticmethod
    def get_database_path() -> Path:
        """
        Gibt ausschließlich den Pfad zur existierenden SQLite-Datenbank Knowledge_Agent_Routing_tree.db zurück.
        Erstellt unter keinen Umständen eine neue oder leere Datenbank.
        """
        base_root = MetaCodeBase.get_project_root()

        # 1. Direkter Pfad (auch bei Case-Variationen auf verschiedenen Systemen)
        candidate = base_root / BASE_DIR / SUBFOLDER / DB_FILENAME
        if candidate.is_file():
            return candidate

        # 2. Case-insensitive Suche in Knowledge-Ordnern
        for k_name in ["Knowledge", "knowledge"]:
            k_dir = base_root / k_name
            if k_dir.is_dir():
                for p in k_dir.rglob("*.db"):
                    if p.name.lower() == DB_FILENAME.lower():
                        return p

        # 3. Projektweite Suche als Fallback
        found = MetaCodeBase.project_find_data(DB_FILENAME)
        if found and found.is_file():
            return found

        raise FileNotFoundError(
            f"[KRITISCHER FEHLER] Die existierende SQLite-Datenbank '{DB_FILENAME}' wurde unter dem Pfad "
            f"'{candidate}' nicht gefunden! Es darf keine neue Datenbank erstellt werden."
        )

    @staticmethod
    def get_db_connection() -> sqlite3.Connection:
        """
        Öffnet eine schreib-/lesbare Verbindung zur existierenden Datenbank.
        Verhindert durch vorherige Existenzprüfung und mode=rw, dass SQLite eine neue Datei erstellt.
        """
        db_path = MetaCodeBase.get_database_path()
        if not db_path.is_file():
            raise FileNotFoundError(f"[KRITISCHER FEHLER] Datenbankdatei existiert nicht: {db_path}")

        posix_path = db_path.resolve().as_posix()
        uri_path = f"file:///{posix_path}?mode=rw" if posix_path.startswith("/") else f"file:{posix_path}?mode=rw"
        try:
            conn = sqlite3.connect(uri_path, uri=True)
        except sqlite3.OperationalError:
            conn = sqlite3.connect(str(db_path))
        return conn

    @staticmethod
    def project_create_folder(subfolder: str, filename: str) -> Path:
        """
        Gibt den Pfad zu einer Datei zurück. Falls es sich um die Datenbank handelt,
        wird strikt die existierende Datenbank Knowledge_Agent_Routing_tree.db zurückgegeben.
        """
        if filename.lower() == DB_FILENAME.lower():
            return MetaCodeBase.get_database_path()

        base_root = MetaCodeBase.get_project_root()
        target_dir = base_root / BASE_DIR / subfolder
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir / filename

    @staticmethod
    def load_optional_ollama_checker() -> bool:
        """
        Startet die '__ollama_running.py' Datei, um die Ollama-Umgebung zu prüfen und zu verifizieren.
        """
        global _OLLAMA_VERIFIED_CACHE
        import importlib.machinery, types
        
        # Nutzt die universelle Projektsuche statt eines festen Pfads
        runner_path = MetaCodeBase.project_find_data("__ollama_running.py")
        
        if runner_path and runner_path.is_file():
            try:
                loader = importlib.machinery.SourceFileLoader("__ollama_running", str(runner_path))
                mod = types.ModuleType(loader.name)
                loader.exec_module(mod)
                
                # Führt die Prüf- und Start-Logik direkt aus und wertet das Ergebnis aus
                if hasattr(mod, "check_and_start_ollama"):
                    success = mod.check_and_start_ollama()
                    _OLLAMA_VERIFIED_CACHE = success
                    return success
                else:
                    return False
            except Exception as e:
                print(f"[FEHLER] Fehler beim Ausführen von '__ollama_running.py': {e}")
                return False
        else:
            print(f"[FEHLER] Datei '__ollama_running.py' wurde im Projektverzeichnis nicht gefunden.")
            return False

    def __init__(self, model_name: str = "codestral:latest", ollama_host: str = "http://127.0.0.1:11434"):
        global _OLLAMA_VERIFIED_CACHE
        if not _OLLAMA_VERIFIED_CACHE:
            print(f"[KRITISCHER ABBRUCH] Ollama ist nicht verifiziert (_OLLAMA_VERIFIED_CACHE = False).")
            sys.exit(1)

        self.model_name = model_name
        self.ollama_host = ollama_host
        
        try:
            self.client = Client(host=ollama_host)
            self.client.list()
        except Exception as e:
            print(f"--> [KRITISCHER FEHLER] Verbindung zum Ollama Client unter {ollama_host} fehlgeschlagen: {e}")
            sys.exit(1)
        
        # Sicherstellen, dass ausschließlich die existierende Routing-Tree-Datenbank verwendet wird
        self.db_path = self.get_database_path()
        print(f"[INFO] Verbunden mit existierender SQLite-Datenbank: '{self.db_path}'")
    
    @staticmethod
    def scan_kernel_modules(module_list: list) -> dict:
        """Scans available Python modules in the kernel."""
        import importlib.util
        results = {}
        for mod in module_list:
            exists = importlib.util.find_spec(mod) is not None
            results[mod] = "active" if exists else "inactive"
        return results

    @staticmethod
    def initialize_blueprint_system(raw_query: str) -> dict:
        """Initializes the planning core for the raw user query and checks SQL table context."""
        cleaned_query = raw_query.strip().lower()
        
        # Qualitätsprüfung / SQL-Integration der Mikroverhalten
        blueprint = {
            "status": "initialized",
            "query": cleaned_query,
            "micro_steps": MetaCodeBase._fetch_micro_behaviors_from_db(cleaned_query)
        }
        return blueprint

    @staticmethod
    def _fetch_micro_behaviors_from_db(query: str) -> list:
        """
        Liest aktive Blueprint-Schritte aus der existierenden Tabelle
        'pre_execution_blueprint_generator' der Knowledge_Agent_Routing_tree.db.
        """
        steps = []
        try:
            with MetaCodeBase.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT node_id, topic_title, agent_instruction 
                    FROM pre_execution_blueprint_generator 
                    WHERE is_active = 1 
                    ORDER BY node_id ASC
                """)
                rows = cursor.fetchall()
                for node_id, title, instruction in rows:
                    steps.append(f"[{node_id}] {title}: {instruction}")
        except Exception as e:
            steps = [f"sql_error_fallback: {str(e)}"]
            
        return steps
    
    @staticmethod
    def _insert_routing_node(
        conn: sqlite3.Connection,
        table_name: str,
        node_id: str,
        topic_title: str,
        topic_specification: str,
        agent_instruction: str,
        example_code_snippet: str = "",
        validation_rule: str = "validated",
        target_table: str = "",
        target_column_id: str = "node_id",
        target_node_id: str = ""
    ):
        """
        Fügt einen Knoten konform zum Standard-Schema des Knowledge Agent Routing Trees ein.
        """
        now = datetime.now()
        conn.execute(f"""
            INSERT INTO {table_name} (
                node_id, is_active, error_fallback_count,
                year, month, day, hour, minute, second,
                topic_title, topic_specification, agent_instruction,
                example_code_snippet, validation_rule, execution_count,
                success_weight, target_table, target_column_id, target_node_id
            ) VALUES (?, 1, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1.0, ?, ?, ?)
            ON CONFLICT(node_id) DO UPDATE SET
                topic_title = excluded.topic_title,
                topic_specification = excluded.topic_specification,
                agent_instruction = excluded.agent_instruction,
                example_code_snippet = excluded.example_code_snippet,
                execution_count = execution_count + 1
        """, (
            node_id,
            now.year, now.month, now.day, now.hour, now.minute, now.second,
            topic_title, topic_specification, agent_instruction,
            example_code_snippet, validation_rule,
            target_table, target_column_id, target_node_id
        ))
        conn.commit()

    def persist_new_capability(self, capability_name: str, code_snippet: str, description: str):
        """
        Persistiert eine neue Fähigkeit dauerhaft in der 'library_registry' Tabelle des Routing Trees.
        """
        node_id = f"CAP_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        with self.get_db_connection() as conn:
            self._insert_routing_node(
                conn=conn,
                table_name="library_registry",
                node_id=node_id,
                topic_title=capability_name,
                topic_specification=description,
                agent_instruction=f"EXECUTE_CAPABILITY: {capability_name}",
                example_code_snippet=code_snippet,
                validation_rule="capability_persisted == TRUE"
            )
        print(f"\n[PERSISTENZ-ERFOLG] Fähigkeit '{capability_name}' wurde dauerhaft in SQLite ('library_registry') verewigt!")

    def _detect_domain(self, text_context: str) -> str:
        """
        Ermittelt anhand von Schlüsselwörtern, in welcher Tabelle des Routing Trees
        gesucht oder referenziert werden soll.
        """
        text_lower = text_context.lower()
        if any(k in text_lower for k in ["repair", "fix", "notfall", "error", "fehler", "crash", "fx_chain", "kette"]):
            return "meta_admin_repair_registry"
        elif any(k in text_lower for k in ["admin", "taboo", "bootstrap", "security", "protect", "schutz"]):
            return "meta_admin_bootstrap_registry"
        elif any(k in text_lower for k in ["resource", "hardware", "cpu", "ram", "psutil", "speicher", "leistung"]):
            return "system_resources"
        elif any(k in text_lower for k in ["tool", "toolkit", "api", "scan", "module", "kernel"]):
            return "toolkit_library_registry"
        elif any(k in text_lower for k in ["plan", "blueprint", "route", "tree", "schritt", "workflow"]):
            return "pre_execution_blueprint_generator"
        else:
            return "library_registry"

    def _get_relevant_tips(self, task_description: str) -> str:
        """
        Lädt kontextbezogene Richtlinien, Blueprint-Schritte und Knoten aus der
        existierenden Knowledge_Agent_Routing_tree.db.
        """
        domain = self._detect_domain(task_description)
        tips = ["=================================================="]
        tips.append(" [SYSTEM CORE MEMORY: KNOWLEDGE AGENT ROUTING TREE]")
        tips.append("==================================================")

        with self.get_db_connection() as conn:
            cursor = conn.cursor()

            # 1. System-Manifest & Core-Direktiven laden
            try:
                cursor.execute("SELECT directive_key, explanation_for_agent FROM agent_system_manifest LIMIT 5")
                manifest_rows = cursor.fetchall()
            except sqlite3.OperationalError:
                manifest_rows = []

            # 2. Relevante Knoten aus der erkannten Domain-Tabelle laden
            try:
                words = [w for w in task_description.lower().split() if len(w) > 3]
                domain_rows = []
                if words:
                    placeholders = " OR ".join(["topic_title LIKE ? OR topic_specification LIKE ? OR agent_instruction LIKE ?"] * len(words))
                    params = []
                    for w in words:
                        pattern = f"%{w}%"
                        params.extend([pattern, pattern, pattern])
                    cursor.execute(
                        f"SELECT node_id, topic_title, agent_instruction, example_code_snippet FROM {domain} "
                        f"WHERE is_active = 1 AND ({placeholders}) ORDER BY success_weight DESC LIMIT 3",
                        params
                    )
                    domain_rows = cursor.fetchall()

                if not domain_rows:
                    cursor.execute(
                        f"SELECT node_id, topic_title, agent_instruction, example_code_snippet FROM {domain} "
                        f"WHERE is_active = 1 ORDER BY success_weight DESC LIMIT 3"
                    )
                    domain_rows = cursor.fetchall()
            except sqlite3.OperationalError:
                domain_rows = []

            # 3. Aktive Blueprint-Schritte laden
            try:
                cursor.execute(
                    "SELECT node_id, topic_title, agent_instruction FROM pre_execution_blueprint_generator "
                    "WHERE is_active = 1 ORDER BY node_id ASC LIMIT 5"
                )
                blueprints = cursor.fetchall()
            except sqlite3.OperationalError:
                blueprints = []

        if manifest_rows:
            tips.append("\n--- Agent System Manifest & Core Directives ---")
            for key, exp in manifest_rows:
                tips.append(f"• [{key}]: {exp}")

        if domain_rows:
            tips.append(f"\n--- Relevant Nodes from Domain [{domain}] ---")
            for node_id, title, instruction, snippet in domain_rows:
                tips.append(f"• Node [{node_id}] {title}: {instruction}")
                if snippet and snippet.strip() and not snippet.startswith("# FX_"):
                    tips.append(f"  Code Snippet: {snippet.strip()[:150]}...")

        if blueprints:
            tips.append("\n--- Mandatory Pre-Execution Blueprints ---")
            for node_id, title, instruction in blueprints:
                tips.append(f"• Step [{node_id}] {title}: {instruction}")

        if len(tips) <= 3:
            return f"No prior routing tree nodes recorded for domain [{domain}]."
        return "\n".join(tips)

    def _save_solution_to_db(self, task_description: str, error_msg: str, solution_code: str):
        """
        Protokolliert Interaktionsmuster und Lösungen in der Tabelle
        'table_issue_data_time_stamp_run_protocol_for_query' des Routing Trees.
        """
        domain = self._detect_domain(task_description)
        node_id = f"LOG_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        with self.get_db_connection() as conn:
            self._insert_routing_node(
                conn=conn,
                table_name="table_issue_data_time_stamp_run_protocol_for_query",
                node_id=node_id,
                topic_title=f"Pattern in [{domain}]",
                topic_specification=task_description[:200],
                agent_instruction=error_msg.strip().split('\n')[-1][:200],
                example_code_snippet=solution_code,
                validation_rule="protocol_logged == TRUE",
                target_table=domain
            )
        print(f"[SQL-KNOWLEDGE] Eintrag erfolgreich in 'table_issue_data_time_stamp_run_protocol_for_query' protokolliert.")

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
        spinner = ResourceAwareSpinner(agent_name="MetaCoder-Evolution")
        stop_event = threading.Event()
        spinner_thread = threading.Thread(target=spinner.run, args=(stop_event, True))
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
        try:
            import psutil
            if psutil.cpu_percent(interval=None) > 90.0:
                print("--> [WARNUNG] Hohe CPU-Auslastung vor dem Start erkannt!")
        except ImportError:
            pass

        db_steps = []
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT node_id, topic_title, agent_instruction 
                    FROM pre_execution_blueprint_generator 
                    WHERE is_active = 1
                    ORDER BY node_id ASC
                """)
                db_steps = cursor.fetchall()
        except sqlite3.OperationalError:
            db_steps = []

        if db_steps:
            print(f"--> [SQL-KNOWLEDGE] {len(db_steps)} aktive Blueprint-Schritte aus SQLite geladen:")
            for node_id, title, instruction in db_steps:
                print(f"    • Schritt [{node_id}]: {title}")
        else:
            print("--> [SQL-KNOWLEDGE] Keine spezifischen Schritte gefunden. Nutze allgemeine DB-Tips als Wissensbasis.")

        target_dir = Path("src/agent")
        target_dir.mkdir(parents=True, exist_ok=True)
        current_error = None
        generated_files = []
        print(f"\n[AGENT-LOOP] Starte ressourcensparenden Generierungs- und Test-Zyklus für: {base_filename}")
        
        for gen in range(1, max_generations + 1):
            print(f"--> [GEN {gen}/{max_generations}] Generiere Arbeiter-Agent mit SQLite-Mikroverhalten...")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            versioned_filename = f"{Path(base_filename).stem}_{timestamp}.py"
            filepath = target_dir / versioned_filename
            
            if db_steps:
                behavior_sequence = "\n".join([f"Step [{node_id}] {title}: {instruction}" for node_id, title, instruction in db_steps])
            else:
                behavior_sequence = self._get_relevant_tips(task_description)
            
            prompt = f"""
You are an expert Autonomous Python Architect. Write a complete, standalone Python script for a lightweight worker agent.
The agent must execute its logic strictly step-by-step based on the dynamic SQLite Knowledge sequence provided below.

Specialization: {specialization}
Task Description: {task_description}

Dynamic SQLite Micro-Behavior Sequence (Execute strictly line by line, ensure state persistence):
{behavior_sequence}

Mandatory Rules:
1. Return ONLY valid Python code inside standard markdown code blocks (```python ... ```).
2. The script must be fully self-contained, lightweight, resource-efficient, and runnable via `python`.
3. Every single execution step must report its progress and log its state back to the SQLite database to remain crash-safe.
"""
            spinner = ResourceAwareSpinner(agent_name=f"Worker-Gen-{gen}")
            stop_event = threading.Event()
            spinner_thread = threading.Thread(target=spinner.run, args=(stop_event, True))
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
                print(f"--> [ERFOLG] Arbeiter-Agent hat alle Mikroschritte fehlerfrei abgearbeitet!")
                return filepath
            else:
                print(f"--> [FEHLER GEFANGEN] Agent ist in einem Mikroschritt gestolpert. Speichere Signatur in SQLite-DB.")
                current_error = output
                sample_fix = f"Resilient step-by-step error handling added for: {task_description[:30]}"
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
    # 1. Sicherstellen, dass ausschließlich die existierende Datenbank verwendet wird
    database_path = MetaCodeBase.get_database_path()
    print(f"[BOOT] Exklusive SQLite-Datenbank erfolgreich geladen: '{database_path}'")
    
    # 2. Optionalen Ollama-Checker ausführen (gibt nur im Fehlerfall Meldungen aus)
    if not MetaCodeBase.load_optional_ollama_checker():
        exit(1)

    # 3. Metacoder booten und Start-Routine durchführen
    metacoder = boot_latest_metacoder()
    
    # Kernel-Modul-Check beim Start
    kernel_check = MetaCodeBase.scan_kernel_modules(["psutil", "sqlite3", "ollama"])
    print(f"\n[KERNEL MODULE SCAN] Status: {kernel_check}")

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

            # Initialisiere Blueprint-Logik für jede Benutzereingabe
            user_blueprint = MetaCodeBase.initialize_blueprint_system(user_input)

            domain = metacoder._detect_domain(user_input)
            db_tips = metacoder._get_relevant_tips(user_input)

            system_prompt = f"""
You are an autonomous AI Agent with an active SQLite Long-Term Memory (Knowledge Agent Routing Tree).
Current Detected Domain: {domain}
Blueprint Status: {user_blueprint['status']}

Retrieved Knowledge & Past Patterns from SQLite DB:
{db_tips}

Your Task: Answer the user's request in German, keeping any code or technical keywords strictly in English. 
Acknowledge and make use of the SQLite database context if relevant.
"""
            # Korrekte Instanziierung des ResourceAwareSpinners im Hintergrund
            spinner = ResourceAwareSpinner(agent_name="Codestral-Chat")
            stop_event = threading.Event()
            spinner_thread = threading.Thread(target=spinner.run, args=(stop_event, True))
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
                print("\n[SYSTEM-INFO] Die Fähigkeit wurde physisch in die SQLite-Tabelle 'library_registry' geschrieben!")

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
#    hallo
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