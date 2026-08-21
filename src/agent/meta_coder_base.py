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
        self.base_dir = Path(".")
        self.history_dir = self.base_dir / "src" / "agent" / "metacoder_history"
        self.history_dir.mkdir(parents=True, exist_ok=True)
        
        # SQLite Wissensdatenbank-Setup im vorgegebenen Ordner: knowledge/meta_coder_base/
        self.knowledge_dir = self.base_dir / "knowledge" / "meta_coder_base"
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.knowledge_dir / "meta_coder_base_issue_solution.db"
        
        self._init_db()
        print(f"[META-BASE] Initialisiert. SQLite-Wissensdatenbank aktiv unter: {self.db_path}")

    def _init_db(self):
        """Erstellt spezialisierte Tabellen für verschiedene Fehler-Domains (Jupyter, Data IO, Scope, Scripts)."""
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
        """Ermittelt anhand von Schlüsselwörtern, in welcher Fehler-Domain (Tabelle) gesucht/gespeichert werden muss."""
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
        """Holt passgenaue Tipps und Lösungs-Snippets nur aus der relevanten Domain-Tabelle."""
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
        """Speichert den spezifischen Fehler und Code-Fix in der passenden Domain-Tabelle."""
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
        print(f"[KNOWLEDGE] Neuer Fix erfolgreich in Tabelle '{domain}' gespeichert.")

    def evolve_self(self, recent_error: str, task_context: str) -> Path:
        """Schreibt eine neue, verbesserte Version von sich selbst mit aktuellem Zeitstempel."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        new_filename = self.history_dir / f"MetaCodeBase_{timestamp}.py"
        
        print(f"\n[EVOLUTION] Erstelle verbesserte MetaCodeBase-Version: {new_filename.name}...")

        current_code_path = Path(__file__)
        current_code = current_code_path.read_text(encoding="utf-8") if current_code_path.exists() else "# Base Code"

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
Do not lose core functions like test_and_evolve_loop, SQLite database handling, or self-execution logic.
"""

        response = self.client.generate(model=self.model_name, prompt=prompt)
        raw_text = response.get('response', '')
        new_code = self._extract_code_block(raw_text)

        with open(new_filename, "w", encoding="utf-8") as f:
            f.write(new_code)
            
        print(f"[EVOLUTION] Neue Version erfolgreich gespeichert unter: {new_filename}")
        return new_filename

    def test_and_evolve_loop(self, specialization: str, task_description: str, base_filename: str, max_generations: int = 3):
        """
        Steuert den Erstellungsprozess mit Fallback-Kette (Rollback bei Fehlschlag) 
        und zieht kontextbezogenes Wissen aus der SQLite-Datenbank.
        """
        target_dir = Path("src/agent")
        target_dir.mkdir(parents=True, exist_ok=True)
        
        current_error = None
        generated_files = []

        for gen in range(1, max_generations + 1):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            versioned_filename = f"{Path(base_filename).stem}_{timestamp}.py"
            filepath = target_dir / versioned_filename

            print(f"\n[META-CODER] Generiere Arbeiter-Agent (Gen {gen}): {versioned_filename}...")

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
3. Include internal validation checks to verify its own success before terminating.
"""

            response = self.client.generate(model=self.model_name, prompt=prompt)
            code = self._extract_code_block(response.get('response', ''))

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(code)

            generated_files.append(filepath)

            print(f"--- Führe Test aus für {filepath.name} ---")
            success, output = self._run_script(filepath)

            if success:
                print(f"\n[✓] Agent '{filepath.name}' erfolgreich verifiziert!")
                return filepath
            else:
                print(f"\n[!] Fehler in Agent entdeckt: {output}")
                current_error = output
                
                sample_fix = f"try-except block added for context: {task_description[:30]}"
                self._save_solution_to_db(task_description, current_error, sample_fix)
                
                self.evolve_self(recent_error=current_error, task_context=task_description)

        print(f"\n[ROLLBACK] Alle {max_generations} Generationen fehlgeschlagen. Gehe in der Historie zurück...")
        for old_file in reversed(generated_files[:-1]):
            if old_file.exists():
                print(f"Prüfe älteren, stabilen Stand: {old_file.name}")
                success, _ = self._run_script(old_file)
                if success:
                    print(f"[✓] Fallback erfolgreich auf: {old_file.name}")
                    return old_file

        print(f"[X] Kritischer Fehler: Kein stabiler Agent auffindbar.")
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

# --- AUTOMATISCHER START-CHECK ---
def boot_latest_metacoder():
    history_dir = Path("src/agent/metacoder_history")
    history_dir.mkdir(parents=True, exist_ok=True)
    
    versions = sorted(history_dir.glob("MetaCodeBase_*.py"))
    if versions:
        latest_version = versions[-1]
        print(f"[BOOT] Neueste selbst-evolverte MetaCodeBase im Ordner gefunden: {latest_version.name}")
    
    return MetaCodeBase()

# --- SCHNITTSTELLE FÜR JUPYTER-NOTEBOOKS (.ipynb) ---
def query_meta_coder_base(notebook_path: str, instruction: str):
    """
    Funktion, die direkt aus einer Jupyter Notebook Zelle aufgerufen werden kann:
    query_meta_coder_base("notebooks/mein_skript.ipynb", "Behebe den Fehler in Zelle 3")
    """
    metacoder = boot_latest_metacoder()
    spec = f"Jupyter Notebook Agent for {Path(notebook_path).name}"
    task = f"""
    Target Jupyter Notebook Path: {notebook_path}
    User Instruction: {instruction}
    
    Instructions for the Agent:
    1. Parse and load the target Jupyter Notebook (.ipynb).
    2. Analyze the code cells and perform the requested correction or implementation.
    3. Save the modified notebook back safely.
    4. Validate that the notebook JSON remains healthy and fully formatted.
    """
    print(f"\n[NOTEBOOK-BRIDGE] Starte Agenten-Loop für Notebook: {notebook_path}")
    return metacoder.test_and_evolve_loop(
        specialization=spec,
        task_description=task,
        base_filename=f"nb_agent_{Path(notebook_path).stem}",
        max_generations=3
    )

# --- CLI / TERMIN MODUS & START ---
if __name__ == "__main__":
    metacoder = boot_latest_metacoder()
    
    # Prüfen, ob Argumente im Terminal übergeben wurden
    if len(sys.argv) > 2:
        nb_path = sys.argv[1]
        user_task = sys.argv[2]
        print(f"[CLI-MODE] Starte mit Argumenten -> Notebook: {nb_path} | Task: {user_task}")
        query_meta_coder_base(nb_path, user_task)
    else:
        # Interaktiver Fall im Terminal
        print("\n==================================================")
        print(" [META-CODER] Interaktiver Terminal-Modus aktiv ")
        print("==================================================")
        choice = input("Möchtest du ein Jupyter-Notebook korrigieren lassen? (j/n): ").strip().lower()
        
        if choice == 'j':
            nb_path = input("Pfad zum Jupyter-Notebook (z. B. notebooks/test.ipynb): ").strip()
            user_task = input("Was soll der Agent tun/korrigieren?: ").strip()
            query_meta_coder_base(nb_path, user_task)
        else:
            # Standard-Test (Fallback, falls nichts angegeben wurde)
            spec = "Ollama Environment Inspector"
            task = """
            Create a Python script that connects to the local Ollama instance, lists local models,
            and ensures no timeout occurs. Exit with code 0 on success.
            """
            metacoder.test_and_evolve_loop(
                specialization=spec,
                task_description=task,
                base_filename="ollama_inspector",
                max_generations=3
            )

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
#    from src.agent.meta_coder_base import query_meta_coder_base
#
#    query_meta_coder_base(
#        notebook_path="notebooks/dein_notebook.ipynb",
#        instruction="Deine Anweisung zur Korrektur oder Erweiterung"
#    )