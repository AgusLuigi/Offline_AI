import sys
import logging
from pathlib import Path

# 1. Hauptverzeichnis zum Python-Pfad hinzufügen
sys.path.append(str(Path(__file__).resolve().parent))

# 2. Auto-Bootstrap & Registrierung aller ausgelagerten Klassen aus agent_universal_skript
from agent_universal_skript.auto_bootstrap_and_register_agents import auto_bootstrap_and_register_agents
auto_bootstrap_and_register_agents()

# Auslagerungen importieren (alle Standards sind in den jeweiligen Klassen definiert)
from agent_universal_skript.class_coreInfrastructure import coreInfrastructure
from agent_universal_skript.class_sql_reader import class_sql_reader
from agent_universal_skript.class_spinner import ResourceAwareSpinner
from agent_universal_skript.class_subAgentVerifier import SubAgentVerifier
from agent_universal_skript.class_evolve_loop_test import EvolveLoopTest
from agent_universal_skript.class_ollama_manager import OllamaManager

# Konfiguration des Loggers
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)


class MetaCoderSQLPipeline(class_sql_reader):
    """
    Zentrale Verklemmungs-Pipeline ('meta_coder_sql').
    
    Architektur-Prinzipien:
    1. Alle Klassen sind in 'agent_universal_skript' ausgelagert.
    2. Hier findet ausschließlich die Verklemmung der Module statt.
    3. Alle Globalen sind standardmäßig in den Klassen definiert. Werden hier keine
       Änderungen übergeben, greifen automatisch die Klassen-Standards.
    4. Alle Phasen werden sequentiell aus der SQL-Datenbank (meta_agent_start)
       abgerufen und zeilenweise ausgeführt, bis die Antwort für den Benutzer feststeht.
    """

    def __init__(self, db_filename: str = None, model_name: str = None, 
                 ollama_host: str = None, require_ollama: bool = True):
        # Initialisierung über geerbte class_sql_reader-Klasse
        super().__init__(db_filename=db_filename)

        # Globale Parameter: Standards der Klasse nutzen, falls nicht explizit überschrieben
        if model_name:
            self.MODEL_LLM = model_name
        if ollama_host:
            self.OLLAMA_HOST = ollama_host

        self.model_name = self.MODEL_LLM
        self.ollama_host = self.OLLAMA_HOST
        self.require_ollama = require_ollama

        # Verklemmung der Sub-Systeme
        self.evolution_loop = EvolveLoopTest(registry_db_path=self.db_filename)
        self.spinner = ResourceAwareSpinner(
            agent_name=self.AGENT_NAME,
            min_ram_mb=self.MIN_RAM_MB,
            max_cpu_threshold=self.CPU_WARNING_THRESHOLD,
            spinner_interval=self.SPINNER_INTERVAL
        )

        # Autonome Hintergrund-Verbindung zu Ollama prüfen/starten
        if self.require_ollama:
            OllamaManager.ensure_ollama_running(self.ollama_host)
            client = OllamaManager.get_client(self.ollama_host)
            if client:
                resolved = OllamaManager.resolve_model(self.model_name, self.ollama_host)
                print(f"[INFO] Ollama-Client aktiv: {self.ollama_host} | Modell: {resolved}")
            else:
                print(f"[WARNUNG] Ollama nicht direkt erreichbar. System nutzt Fallback-Wissensmodus.")

    def run_query(self, user_input: str) -> dict:
        """
        Führt eine Benutzeranfrage streng nach der SQL-Datenbank aus (Regel 5):
        Phasen aus 'meta_agent_start' sequentiell abrufen und zeilenweise ausführen.
        Liefert am Schluss die Antwort für den Benutzer.
        """
        def spinner_starter(agent_label):
            import threading
            spinner = ResourceAwareSpinner(
                agent_name=agent_label,
                min_ram_mb=self.MIN_RAM_MB,
                max_cpu_threshold=self.CPU_WARNING_THRESHOLD,
                spinner_interval=self.SPINNER_INTERVAL
            )
            stop_evt = threading.Event()
            th = threading.Thread(target=spinner.run, args=(stop_evt, True))
            th.start()
            return stop_evt, th

        return self.execute_query_with_db_phases(
            raw_query=user_input,
            model_name=self.model_name,
            ollama_host=self.ollama_host,
            spinner_thread_starter=spinner_starter
        )


def boot_latest_metacoder(require_ollama: bool = True) -> MetaCoderSQLPipeline:
    """Erstellt und bootet die MetaCoder-Pipeline mit Database-Driven DNA."""
    pipeline = MetaCoderSQLPipeline(require_ollama=require_ollama)
    try:
        pipeline.bootstrap_from_database()
    except Exception as e:
        print(f"[BOOT WARNUNG] Bootstrap-DNA konnte nicht geladen werden: {e}")
    return pipeline


def query_meta_coder_sql(notebook_path: str, instruction: str):
    """Schnittstelle für Jupyter-Notebooks: Startet den MetaCoder für ein spezifisches Notebook."""
    metacoder = boot_latest_metacoder()
    task = f"Target Notebook: {notebook_path}\nInstruction: {instruction}"
    return metacoder.run_query(task)


if __name__ == "__main__":
    print(f"--- Starte {class_sql_reader.AGENT_NAME} SQL Verklemmungs-Pipeline (v2+V1) ---")
    
    pipeline = boot_latest_metacoder(require_ollama=True)
    pipeline.verify_environment()

    # Kernel-Modul-Scan
    kernel_check = coreInfrastructure.scan_kernel_modules(pipeline.REQUIRED_KERNEL_MODULES)
    logging.info(f"[KERNEL MODULE SCAN] Status: {kernel_check}")

    print(f" [INTELLIGENTER CHAT-MODUS] Verbunden mit SQLite-Langzeitgedächtnis")
    print(f" {pipeline.AGENT_NAME} nutzt aktiv den Knowledge Agent Routing Tree.")
    print(" Befehle: '!positiv' / '!negativ' für Feedback | 'exit' zum Beenden")

    last_query_node_id = None
    while True:
        try:
            user_input = input("\nDu: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit"]:
                print("\nAgent: Bis zum nächsten Mal!")
                break

            # Feedback-Befehle behandeln
            if user_input.lower().startswith("!feedback") or user_input.lower() in ["!positiv", "!negativ"]:
                if not last_query_node_id:
                    print("--> [FEEDBACK] Bisher wurde noch keine Anfrage ausgeführt, die bewertet werden könnte.")
                    continue
                is_pos = "positiv" in user_input.lower()
                comment = user_input.split(" ", 1)[1] if " " in user_input else ("Positives Feedback" if is_pos else "Negatives Feedback")
                fb_res = pipeline.record_feedback(last_query_node_id, is_positive=is_pos, comment=comment)
                print(f"--> [FEEDBACK REGISTRIERT] Node '{last_query_node_id}' bewertet: {fb_res}")
                continue

            # Sequentielle Phasen-Ausführung aus der SQL-Datenbank (Regel 5)
            result = pipeline.run_query(user_input)
            last_query_node_id = result.get("node_id")

            # Rückmeldung / Antwort für den Benutzer anzeigen
            answer = result.get("answer", "")
            domain = result.get("domain", "Allgemein")
            cache_tag = "SQL-Cache | " if result.get("cache_hit") else ""

            print(f"\n{pipeline.AGENT_NAME} [Domain: {cache_tag}{domain} | DB aktiv | Node {last_query_node_id or '-'}]:")
            print(answer)
            print("-" * 70)

            # Auto-Persistenz bei Schlüsselwörtern
            if "verewige" in user_input.lower() or "speichere in sql" in user_input.lower():
                pipeline.persist_new_capability(
                    capability_name="Autonomous_Capability",
                    code_snippet=answer[:pipeline.PROMPT_MAX_LEN],
                    description=user_input
                )
                print("\n[SYSTEM-INFO] Die Fähigkeit wurde physisch in die SQLite-Tabelle 'library_registry' geschrieben!")

        except KeyboardInterrupt:
            print("\n\nAgent: Sitzung durch Benutzer abgebrochen.")
            break
        except Exception as e:
            logging.error(f"[FEHLER IM AGENTEN-LOOP] Konnte Anfrage nicht verarbeiten: {e}")