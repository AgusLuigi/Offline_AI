import logging
import sqlite3
import sys
import threading
from pathlib import Path

# 1. Hauptverzeichnis zum Python-Pfad hinzufügen
sys.path.append(str(Path(__file__).resolve().parent))

# 2. Funktion importieren und direkt ausführen (Auto-Bootstrap & globale Registrierung)
from agent_universal_skript.auto_bootstrap_and_register_agents import auto_bootstrap_and_register_agents
auto_bootstrap_and_register_agents()

# Konfiguration des Loggers
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# 3. Globale Einstellungen & Konstanten
PROJECT_POINT = "src"
DB_FILENAME = "Knowledge_Agent_Routing_tree.db"
_OLLAMA_VERIFIED_CACHE = False
OLLAMA_CHECKER_FILENAME = "__ollama_running.py"
MODEL_LLM = "mixtral:instruct"

class MetaCoderSQLPipeline(class_sql_reader):
    """
    Zentrale Verklemmungs-Pipeline ('metacoder.sql v2').
    Verlinkt Core-Infrastruktur, SQL-Reader, Sandbox-Verifier,
    Evolutions-Schleife und Terminal-Spinner zu einem autonomen Agenten-System.
    """
    def __init__(self, db_filename: str = DB_FILENAME, start_path: str = PROJECT_POINT):
        super().__init__()
        # Initialisierung der vererbten Core-Infrastruktur und Bestimmung des Projekt-Roots
        self.root_path = Path(coreInfrastructure.get_project_root(start_path))
        # Universelle und absolute Pfadfindung für die Datenbank im Projektverzeichnis
        # Nutzt get_file_path für absolute Sicherheit im Verzeichnisbaum
        try:
            self.db_filename = str(coreInfrastructure.get_file_path(db_filename))
        except FileNotFoundError:
            # Fallback, falls die DB physisch noch gar nicht im Baum existiert
            self.db_filename = str(self.root_path / db_filename)
        # Initialisierung des Evolutions-Loops mit dem absolut aufgelösten Datenbank-Pfad
        self.evolution_loop = EvolveLoopTest(registry_db_path=self.db_filename)
        # Ressourcen-Spinner für visuelles Feedback initialisieren
        self.spinner = ResourceAwareSpinner(agent_name="MetaCoder-Agent")

    def get_db_connection(self):
        """Stellt eine sichere Verbindung zur globalen Knowledge-Datenbank her."""
        conn = sqlite3.connect(self.db_filename)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_core_tables(self):
        """Garantiert die physische Existenz aller Kern-Tabellen vor Pipeline-Start."""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                # Erstellt die kritische Cache-Tabelle 'user_query', falls sie fehlt
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_query (
                        node_id TEXT PRIMARY KEY,
                        task_description TEXT,
                        domain TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        status TEXT
                    );
                """)
                conn.commit()
            except sqlite3.Error as e:
                print(f"[GEGENKONTROLLE FEHLER] Konnte Tabellenstrukturen nicht härten: {e}")

    def verify_environment(self) -> bool:
        """
        Prüft die Existenz der globalen Datenbank, initialisiert die Tabellenstrukturen 
        und verifiziert die Tool-Schnittstellen.
        """
        db_path = Path(self.db_filename)
        if not db_path.exists():
            print(f"[METABASE] Erstelle neue SQLite-Registry unter: {db_path.resolve()}")
            # Verzeichnis erstellen, falls es fehlt
            db_path.parent.mkdir(parents=True, exist_ok=True)
        # Erst die Standard-Tabellen erzwingen, um Abstürze im SQL-Reader zu verhindern
        self._ensure_core_tables()
        # Initialisierung der Tabellen in der Existenz-Datenbank via EvolveLoop
        if hasattr(self.evolution_loop, "init_database_tables"):
            try:
                self.evolution_loop.init_database_tables()
                print(f"[METABASE] Tabellenstrukturen in '{self.db_filename}' erfolgreich verifiziert/angelegt.")
            except Exception as e:
                print(f"[METABASE FEHLER] Konnte Tabellen nicht initialisieren: {e}")  
        print("[METAKODER] Umgebung erfolgreich verifiziert. Alle erweiterten Tools verbunden.")
        return True

    def run_pipeline(self, task_description: str, target_notebook: str = None) -> dict:
        """
        Führt die Haupt-Pipeline aus:
        1. Cache-Prüfung oder Abfrage-Registrierung via SQL Reader.
        2. Visuelle Begleitung mit dem ResourceAwareSpinner.
        3. Ausführung im Closed-Loop (EvolveLoopTest + SubAgentVerifier).
        4. Protokollierung der Ergebnisse mit exaktem DB-Zeitstempel.
        """
        # Vorab-Verifikation der Tabellen-Integrität vor jedem Run
        self._ensure_core_tables()
        stop_event = threading.Event()
        spinner_thread = threading.Thread(target=self.spinner.run, args=(stop_event, True))
        spinner_thread.start()
        codes = []  # Vorab definieren, damit es im finally/store-Bereich sicher greift
        node_id = None
        try:
            # 1. Blueprint-System anfahren
            try:
                self.initialize_blueprint_system(task_description)
            except Exception as e:
                print(f"[GEGENKONTROLLE FEHLER] Blueprint-System übersprungen: {e}")
            # 2. Cache abfragen / Eintrag vorbereiten
            try:
                cached_check = self.get_cached_or_create_query(task_description)
                if cached_check and cached_check.get("cache_hit"):
                    print(f"\n[CACHE HIT] Anfrage im Cache gefunden (Node-ID: {cached_check.get('node_id')}).")
                    return cached_check
                node_id = cached_check.get("node_id") if cached_check else None
            except Exception as e:
                print(f"[GEGENKONTROLLE FEHLER] Cache-Abfrage fehlgeschlagen: {e}")
            # Falls kein Reader die Node-ID generiert hat, bauen wir die ID deterministisch vorab
            if not node_id:
                current_time = datetime.datetime.now().strftime("%H%M%S")
                unique_suffix = str(random.randint(100000, 999999))
                node_id = f"STEP_{current_time}_{unique_suffix}"
                print(f"[PIPELINE-FIX] Generiere autonome Pipeline-ID: {node_id}")

            def execution_runner(payload):
                nonlocal codes
                codes = SubAgentVerifier.extract_code_blocks(payload.get("task", ""))
                if codes:
                    success, output = SubAgentVerifier.verify_code_in_sandbox(codes[0])
                    if not success:
                        raise RuntimeError(f"Sandbox-Fehler: {output}")
                    return output
                return "Kein ausführbarer Code-Block gefunden, logische Ausführung erfolgreich."
            # 3. Evolutionsschleife starten
            evolution_result = self.evolution_loop.test_and_evolve_loop(
                specialization="MetaCoder SQL Automated Pipeline",
                task_description=task_description,
                base_filename=target_notebook or "metacoder_run",
                max_generations=3,
                execution_func=execution_runner
            )
            final_status = evolution_result.get("status")
            final_message = evolution_result.get("message") or evolution_result.get("result", "")
            snippet_to_store = codes[0] if codes else ""
            # 4. Ergebnisse mit gesicherter Node-ID zurückspeichern
            try:
                self.store_query_result(node_id=node_id, answer=str(final_message), snippet=snippet_to_store)
            except Exception as e:
                print(f"[GEGENKONTROLLE FEHLER] store_query_result abgebrochen: {e}")
            try:
                # Reicht die node_id an den Zeitstempel-Logger weiter
                self.log_save_query_run_to_db_timestamp(
                    task_description=task_description,
                    error_msg="" if final_status == "SUCCESS" else str(evolution_result.get("last_error")),
                    solution_code=str(final_message),
                    node_id=node_id  # Verhindert den Zeitstempel-Abbruch im Folge-Protokoll
                )
            except Exception as e:
                print(f"[GEGENKONTROLLE FEHLER] Zeitstempel-Verankerung fehlgeschlagen: {e}")
            return evolution_result
        except Exception as e:
            print(f"\n[KRITISCHER PIPELINE-FEHLER] {e}")
            return {"status": "FAILED", "error": str(e)}
        finally:
            stop_event.set()
            spinner_thread.join()

# 4. AUSFÜHRUNG & INTERAKTIVER MODUS
if __name__ == "__main__":
    print("--- Starte MetaCoder SQL Verklemmungs-Pipeline (v2) ---")
    
    pipeline = MetaCoderSQLPipeline()
    
    # Umgebung und Tabellen prüfen
    if not pipeline.verify_environment():
        logging.warning("Umgebung konnte nicht vollständig verifiziert werden. Fahre fort...")

    # Kernel-Modul-Check über coreInfrastructure
    kernel_check = coreInfrastructure.scan_kernel_modules(["psutil", "sqlite3"])
    logging.info(f"[KERNEL MODULE SCAN] Status: {kernel_check}")

    print("\n======================================================================")
    print(" [INTELLIGENTER CHAT-MODUS] Verbunden mit SQLite-Langzeitgedächtnis")
    print(" Befehle: 'exit' zum Beenden")

    while True:
        try:
            user_input = input("\nDu: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit"]:
                print("\nAgent: Bis zum nächsten Mal!")
                break

            # Pipeline mit der Benutzereingabe ausführen
            result = pipeline.run_pipeline(user_input)

            print(f"\nMetaCoder-Agent [Status: {result.get('status')}]:")
            print(result.get("message") or result.get("result") or result.get("error"))
            print("-" * 70)

        except KeyboardInterrupt:
            print("\n\nAgent: Sitzung durch Benutzer abgebrochen.")
            break
        except Exception as e:
            logging.error(f"[FEHLER IM AGENTEN-LOOP] Konnte Anfrage nicht verarbeiten: {e}")
            
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