import os
import sys
import subprocess
import glob
import sqlite3
from datetime import datetime
from pathlib import Path
from ollama import Client

class MetaCodeBase:
    def __init__(self, model_name: str = "codestral:latest", ollama_host: str = "http://127.0.0.1:11434"):
        self.model_name = model_name
        self.client = Client(host=ollama_host)
        
        # Initialisierung über die geforderte Ordnerstruktur-Logik
        self.db_path = self.initialize_find_folder()
        
        self._init_db()
        print(f"[META-BASE] Initialisiert. SQLite-Wissensdatenbank aktiv unter: {self.db_path}")

    def initialize_find_folder(self) -> Path:
        """
        Prüft, ob die notwendige Ordnerstruktur für den Knowledge Agent im Projekt vorhanden ist,
        und gibt bei jedem Teilschritt ein klares Status-Print in der Konsole aus.
        """
        ANKER_DIR = "Offline_AI"
        BASE_DIR = "Knowledge"
        AGENT_SUBDIR = "knowledge_agent_hierarchical_routing_tree_sql"
        DB_FILENAME = "knowledge_agent_routing_tree.db"

        print("--- [START] Prüfe Ordnerstruktur für den Knowledge Agent ---")

        current_path = os.path.abspath(os.getcwd())
        print(f"--> [INFO] Start-Pfad des Notebooks: {current_path}")
        
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
        print("--- [ENDE] Ordnerstruktur erfolgreich geprüft ---")
        
        return db_path

    def _init_db(self):
        """Erstellt spezialisierte Fehler-Domains."""
        domains = ["script_errors", "jupyter_errors", "data_io_errors", "scope_global_errors"]
        
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
            conn.commit()

    def _detect_domain(self, text_context: str) -> str:
        text_lower = text_context.lower()
        if "jupyter" in text_lower or "notebook" in text_lower or ".ipynb" in text_lower:
            return "jupyter_errors"
        elif "json" in text_lower or "csv" in text_lower or "file" in text_lower or "data" in text_lower or "io" in text_lower:
            return "data_io_errors"
        elif "global" in text_lower or "scope" in text_lower or "import" in text_lower or "variable" in text_lower:
            return "scope_global_errors"
        else:
            return "script_errors"

    def _get_relevant_tips(self, task_description: str) -> str:
        domain = self._detect_domain(task_description)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT error_signature, solution_code FROM {domain} ORDER BY success_score DESC LIMIT 3")
            rows = cursor.fetchall()

        if not rows:
            return f"No prior errors recorded in domain [{domain}]."

        tips = [f"--- Relevant Past Solutions from [{domain}] ---"]
        for err, sol in rows:
            tips.append(f"- Bug: [{err}] -> Fix Code Pattern: {sol}")
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
        history_dir = self.base_dir / "src" / "agent" / "metacoder_history"
        history_dir.mkdir(parents=True, exist_ok=True)
        new_filename = history_dir / f"MetaCodeBase_{timestamp}.py"
        
        current_code_path = Path(__file__)
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

        response = self.client.generate(model=self.model_name, prompt=prompt)
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

        for gen in range(1, max_generations + 1):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            versioned_filename = f"{Path(base_filename).stem}_{timestamp}.py"
            filepath = target_dir / versioned_filename

            db_tips = self._get_relevant_tips(task_description)

            prompt = f"""
You are an expert Autonomous Python Architect. Write a complete, standalone Python script for an agent.

Specialization: {specialization}
Task Description: {task_description}

Known Rules & Lessons from SQLite Knowledge Database (Follow strictly!):
{db_tips}

Mandatory Rules:
1. Return ONLY valid Python code inside standard markdown code blocks (```python ... ```).
2. The script must be fully self-contained and runnable via `python`.
"""

            response = self.client.generate(model=self.model_name, prompt=prompt)
            code = self._extract_code_block(response.get('response', ''))

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(code)

            generated_files.append(filepath)

            success, output = self._run_script(filepath)

            if success:
                return filepath
            else:
                current_error = output
                sample_fix = f"try-except block added for context: {task_description[:30]}"
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
    spec = f"Jupyter Notebook Agent for {Path(notebook_path).name}"
    task = f"""
    Target Jupyter Notebook Path: {notebook_path}
    User Instruction: {instruction}
    """
    return metacoder.test_and_evolve_loop(
        specialization=spec,
        task_description=task,
        base_filename=f"nb_agent_{Path(notebook_path).stem}",
        max_generations=3
    )

if __name__ == "__main__":
    metacoder = boot_latest_metacoder()
    
    # [INFO-BOX] ANLEITUNG ZUR AUSLÖSUNG DES META-CODERS
    # Variante 1: Auslösung über das Terminal (Konsole)
    #
    # A) Interaktiver Modus (fragt nach Pfad & Aufgabe):
    #    python src/agent/meta_coder_base.py
    #
    # B) Direkt als Einzeiler mit Parametern:
    #    python src/agent/meta_coder_base.py notebooks/dein_notebook.ipynb "Deine Aufgabe hier"
    #
    # 
    # Variante 2: Auslösung direkt aus einem Jupyter Notebook (.ipynb) heraus
    # 
    # Füge diesen Code in eine Notebook-Zelle ein und führe sie aus:
    #
    #    from src.agent.meta_coder_base import query_meta_coder_sql
    #
    #    query_meta_coder_sql(
    #        notebook_path="notebooks/dein_notebook.ipynb",
    #        instruction="Deine Anweisung zur Korrektur oder Erweiterung"
    #    )