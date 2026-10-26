import datetime
import random
import sqlite3
import sys
import threading
from pathlib import Path

# 1. Hauptverzeichnis zum Python-Pfad hinzufügen
sys.path.append(str(Path(__file__).resolve().parent))

# 2. Auto-Bootstrap & globale Registrierung aller universellen Werkzeuge
from agent_universal_skript.auto_bootstrap_and_register_agent_tools import auto_bootstrap_and_register_agent_tools
auto_bootstrap_and_register_agent_tools()

# 3. Zentrale globale Aliase mit sicherer Fallback-Logik (Defaults) direkt nach Bootstrap
logger = globals().get('class_logger_audit_execution')
core_infra = globals().get('class_tool_core_infrastructure')
ollama_manager = globals().get('class_tool_ollama_service_manager')
spinner_tool = globals().get('class_tool_resource_aware_spinner')
sql_reader = globals().get('class_tool_sql_reader')
sub_verifier = globals().get('class_agent_sub_verifier')
evolve_loop = globals().get('class_container_evolve_loop_test')

# Initialisierung des zentralen Loggers
if logger:
    logger.initialize_logger()


# GLOBALE KONFIGURATION — Mechanische Steuerung der LLM-Intensität und Grenzwerte
PROJECT_POINT = "src"
DB_FILENAME = "Knowledge_Agent_Routing_tree.db"
OLLAMA_CHECKER_FILENAME = "__ollama_running.py"

MODEL_LLM = "codestral"
OLLAMA_HOST = "http://127.0.0.1:11434"
AGENT_NAME = "MetaCoder-Agent"

MAX_EVOLUTION_GENERATIONS = 3
MAX_USER_QUERY_ID_RANGE = (3, 999)
EVOLUTION_RETRY_DELAY_SEC = 1

TASK_DESCRIPTION_MAX_LEN = 200
CODE_SNIPPET_PREVIEW_LEN = 150
QUERY_TITLE_MAX_LEN = 35
MAX_SANDBOX_OUTPUT_LENGTH = 4000
SANDBOX_TIMEOUT = 15
PROMPT_MAX_LEN = 500

TFIDF_SIMILARITY_THRESHOLD = 0.15
FEEDBACK_WEIGHT_INCREMENT = 0.2
MAX_BLUEPRINT_STEPS = 5
MAX_DOMAIN_NODES = 3
MAX_MANIFEST_ENTRIES = 5
CPU_WARNING_THRESHOLD = 90.0
MIN_RAM_MB = 2000
SPINNER_INTERVAL = 1.0

DOMAIN_KEYWORDS = {
    "meta_admin_repair_registry": [
        "repair", "fix", "notfall", "error", "fehler", "crash", "fx_chain", "kette"
    ],
    "meta_admin_bootstrap_registry": [
        "admin", "taboo", "bootstrap", "security", "protect", "schutz"
    ],
    "system_resources": [
        "resource", "hardware", "cpu", "ram", "psutil", "speicher", "leistung"
    ],
    "toolkit_library_registry": [
        "tool", "toolkit", "api", "scan", "module", "kernel"
    ],
    "pre_execution_blueprint_generator": [
        "plan", "blueprint", "route", "tree", "schritt", "workflow"
    ],
    "library_registry": [
        "library", "bibliothek", "fähigkeit", "capability", "wissen"
    ]
}

ALLOWED_TABLES_EXCLUDE = {
    "user_query",
    "table_issue_data_time_stamp_run_protocol_for_query",
    "meta_admin_repair_registry",
    "meta_admin_bootstrap_registry",
    "system_resources",
    "toolkit_library_registry",
    "pre_execution_blueprint_generator",
    "library_registry",
    "meta_agent_start",
    "agent_system_manifest",
    "index_chat_user_query"
}
FALLBACK_DOMAIN = "library_registry"
REQUIRED_KERNEL_MODULES = ["psutil", "sqlite3"]


class MetaCoderSQLPipeline(sql_reader if sql_reader else object):
    """
    Zentrale Verklemmungs-Pipeline ('metacoder.sql v2+V1').
    Verbindet class_tool_core_infrastructure, class_tool_sql_reader, class_agent_sub_verifier,
    class_container_evolve_loop_test und class_tool_resource_aware_spinner zu einem autonomen Agenten-System.
    
    Erbt sämtliche Wissens- und SQL-Logiken direkt aus der Single Source of Truth class_tool_sql_reader:
    - Database-Driven DNA Bootstrap
    - Autonomer User-Query-Cache (Zero-Compute)
    - Benutzer-Feedback mit dynamischer Gewichtsanpassung
    - Knoten-Deaktivierung & Rerouting mit FX_CHAIN
    - Persistenz neuer Fähigkeiten in library_registry
    - Kontextbezogene SQLite-Knowledge-Tips
    - Selbst-Evolution via LLM
    """

    ALLOWED_TABLES = ALLOWED_TABLES_EXCLUDE
    DOMAIN = FALLBACK_DOMAIN
    DOMAIN_KEYWORDS = DOMAIN_KEYWORDS
    TFIDF_SIMILARITY_THRESHOLD = TFIDF_SIMILARITY_THRESHOLD
    TASK_DESCRIPTION_MAX_LEN = TASK_DESCRIPTION_MAX_LEN
    CODE_SNIPPET_PREVIEW_LEN = CODE_SNIPPET_PREVIEW_LEN
    QUERY_TITLE_MAX_LEN = QUERY_TITLE_MAX_LEN
    MAX_BLUEPRINT_STEPS = MAX_BLUEPRINT_STEPS
    MAX_DOMAIN_NODES = MAX_DOMAIN_NODES
    MAX_MANIFEST_ENTRIES = MAX_MANIFEST_ENTRIES

    def __init__(self, db_filename: str = DB_FILENAME, start_path: str = PROJECT_POINT,
                 model_name: str = MODEL_LLM, ollama_host: str = OLLAMA_HOST,
                 require_ollama: bool = True):
        super().__init__(db_filename=db_filename)
        
        # Bestimmung des Projekt-Roots über die vererbte Infrastruktur
        self.root_path = Path(self.get_project_root(start_path))
        
        # Absolute Pfadfindung für die Datenbank
        try:
            self.db_filename = str(self.get_file_path(db_filename))
        except FileNotFoundError:
            self.db_filename = str(self.root_path / db_filename)
        
        # Initialisierung des Container-Evolutions-Loops
        self.evolution_loop = evolve_loop(registry_db_path=self.db_filename) if evolve_loop else None
        if self.evolution_loop:
            self.evolution_loop.EVOLUTION_RETRY_DELAY_SEC = EVOLUTION_RETRY_DELAY_SEC
        
        # Ressourcen-Spinner initialisieren
        self.spinner = spinner_tool(
            agent_name=AGENT_NAME,
            min_ram_mb=MIN_RAM_MB,
            max_cpu_threshold=CPU_WARNING_THRESHOLD,
            spinner_interval=SPINNER_INTERVAL
        ) if spinner_tool else None

        self.model_name = model_name
        self.ollama_host = ollama_host
        self.client = None
        
        if require_ollama and ollama_manager:
            if ollama_manager.ensure_ollama_running(ollama_host):
                self.client = ollama_manager.get_client(ollama_host)
                if logger:
                    logger.info(f"[INFO] Ollama-Dienst verbunden: {ollama_host} | Modell: {model_name}")
            else:
                if logger:
                    logger.warning(f"[WARNUNG] Ollama-Dienst unter {ollama_host} nicht erreichbar. LLM-Funktionen eingeschränkt.")

    def run_pipeline(self, task_description: str, target_notebook: str = None) -> dict:
        """
        Führt die Haupt-Pipeline aus:
        1. Cache-Prüfung oder Abfrage-Registrierung via SQL Reader.
        2. Visuelle Begleitung durch die zentrale run_agent-Methode des Ollama Service Managers.
        3. Ausführung im Closed-Loop (EvolveLoopTest + class_agent_sub_verifier).
        4. Protokollierung der Ergebnisse mit exaktem DB-Zeitstempel.
        """
        self._ensure_core_tables()
        codes = []
        node_id = None

        # 0. Kognitive Erfassung & Token-Schärfung via index_chat_user_query
        indexed_query = self.index_chat_user_query(task_description)
        if indexed_query.get("cache_hit"):
            cached_data = indexed_query.get("cached_check", {})
            cached_data["status"] = "SUCCESS"
            if logger:
                logger.info(f"\n[CACHE HIT] Anfrage im Cache gefunden (Node-ID: {indexed_query.get('node_id')}).")
            return cached_data

        effective_task = indexed_query.get("sharpened_query") or task_description
        node_id = indexed_query.get("node_id")
        log_table = indexed_query.get("log_table_name")
        time_stamp = indexed_query.get("time_stamp")

        def _execute_pipeline_core():
            nonlocal node_id, codes
            # 1. Blueprint-System anfahren
            try:
                self.initialize_blueprint_system(effective_task)
            except Exception as e:
                if logger:
                    logger.warning(f"[GEGENKONTROLLE FEHLER] Blueprint-System übersprungen: {e}")  
            
            # Falls kein Reader die Node-ID generiert hat
            if not node_id:
                current_time = datetime.datetime.now().strftime("%H%M%S")
                unique_suffix = str(random.randint(100000, 999999))
                node_id = f"STEP_{current_time}_{unique_suffix}"
                if logger:
                    logger.info(f"[PIPELINE-FIX] Generiere autonome Pipeline-ID: {node_id}")
            
            # 2. Sandbox-Ausführungsumgebung
            def execution_runner(payload):
                nonlocal codes
                codes = sub_verifier.extract_code_blocks(payload.get("task", "")) if sub_verifier else []
                if codes:
                    code_to_test = codes[0] if isinstance(codes, list) else codes
                    success, output = sub_verifier.verify_code_in_sandbox(
                        code_to_test,
                        timeout_sec=SANDBOX_TIMEOUT
                    ) if sub_verifier else (True, "Verifier omitted")
                    if not success:
                        raise RuntimeError(f"Sandbox-Fehler: {output}")
                    return output
                return "Kein ausführbarer Code-Block gefunden, logische Ausführung erfolgreich."
            
            # 3. Evolutionsschleife starten
            if self.evolution_loop:
                evolution_result = self.evolution_loop.test_and_evolve_loop(
                    specialization=f"{AGENT_NAME} Automated Pipeline",
                    task_description=effective_task,
                    base_filename=target_notebook or "metacoder_run",
                    max_generations=MAX_EVOLUTION_GENERATIONS,
                    execution_func=execution_runner
                )
            else:
                evolution_result = {"status": "SUCCESS", "message": "Evolution loop omitted"}

            final_status = evolution_result.get("status")
            final_message = evolution_result.get("message") or evolution_result.get("result", "")
            snippet_to_store = codes if codes else ""
            
            # 4. Ergebnisse im Cache versiegeln
            try:
                self.store_query_result(node_id=node_id, answer=str(final_message), snippet=str(snippet_to_store))
            except Exception as e:
                if logger:
                    logger.warning(f"[GEGENKONTROLLE FEHLER] store_query_result abgebrochen: {e}")
            
            # 5. Zeitstempel-Protokollierung in dynamische Log-Tabelle log_{time}
            try:
                self.log_save_query_run_to_db_timestamp(
                    task_description=effective_task,
                    error_msg="" if final_status == "SUCCESS" else str(evolution_result.get("last_error")),
                    solution_code=str(final_message),
                    run_id=time_stamp,
                    step_type="seal",
                    log_table_name=log_table
                )
            except Exception as e:
                if logger:
                    logger.warning(f"[GEGENKONTROLLE FEHLER] Zeitstempel-Verankerung fehlgeschlagen: {e}")
            
            # 6. Bei Fehler: Selbst-Evolution auslösen
            if final_status != "SUCCESS":
                try:
                    self.evolve_self(
                        recent_error=str(evolution_result.get("last_error", "")),
                        task_context=task_description
                    )
                except Exception as e:
                    if logger:
                        logger.error(f"[EVOLUTION FEHLER] Selbst-Evolution fehlgeschlagen: {e}")
            
            return evolution_result

        # Ausführung über die zentrale run_agent-Methode mit automatischem Spinner
        try:
            if ollama_manager:
                return ollama_manager.run_agent(_execute_pipeline_core, agent_title=AGENT_NAME)
            return _execute_pipeline_core()
        except Exception as e:
            if logger:
                logger.error(f"\n[KRITISCHER PIPELINE-FEHLER] {e}")
            return {"status": "FAILED", "error": str(e)}


def boot_latest_metacoder(require_ollama: bool = True) -> MetaCoderSQLPipeline:
    """Erstellt und bootet die neueste MetaCoder-Instanz mit Database-Driven DNA."""
    pipeline = MetaCoderSQLPipeline(require_ollama=require_ollama)
    try:
        pipeline.bootstrap_from_database()
    except Exception as e:
        if logger:
            logger.warning(f"[BOOT WARNUNG] Bootstrap-DNA konnte nicht geladen werden: {e}")
    return pipeline


def query_meta_coder_sql(notebook_path: str, instruction: str):
    """Schnittstelle für Jupyter-Notebooks: Startet den MetaCoder für ein spezifisches Notebook."""
    metacoder = boot_latest_metacoder()
    spec = f"Hierarchical Routing Tree SQL Agent for {Path(notebook_path).name}"
    task = f"""
    Target Notebook/Module Path: {notebook_path}
    User Instruction/Routing Goal: {instruction}
    """
    return metacoder.run_pipeline(task_description=task, target_notebook=f"sql_routing_agent_{Path(notebook_path).stem}")


# Globale Registrierung im Namespace
globals()['MetaCoderSQLPipeline'] = MetaCoderSQLPipeline
globals()['boot_latest_metacoder'] = boot_latest_metacoder
globals()['query_meta_coder_sql'] = query_meta_coder_sql


if __name__ == "__main__":
    if logger:
        logger.info(f"--- Starte {AGENT_NAME} SQL Verklemmungs-Pipeline (v2+V1) ---")
    
    pipeline = boot_latest_metacoder(require_ollama=True)
    
    # Umgebung und Tabellen prüfen
    if not pipeline.verify_environment() and logger:
        logger.warning("Umgebung konnte nicht vollständig verifiziert werden. Fahre fort...")

    # Kernel-Modul-Check
    if core_infra:
        kernel_check = core_infra.scan_kernel_modules(REQUIRED_KERNEL_MODULES)
        if logger:
            logger.info(f"[KERNEL MODULE SCAN] Status: {kernel_check}")

    print(f" [INTELLIGENTER CHAT-MODUS] Verbunden mit SQLite-Langzeitgedächtnis")
    print(f" {AGENT_NAME} nutzt aktiv den Knowledge Agent Routing Tree.")
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

            # Stufe 1: Kognitive Erfassung, Bereinigung & Token-Schärfung (index_chat_user_query)
            try:
                indexed_context = pipeline.index_chat_user_query(user_input)
                last_query_node_id = indexed_context.get("node_id")
                log_table = indexed_context.get("log_table_name")
                effective_input = indexed_context.get("sharpened_query") or user_input

                if indexed_context.get("cache_hit"):
                    cached_data = indexed_context.get("cached_check", {})
                    print(f"\n{AGENT_NAME} [Domain: SQL-Cache | DB aktiv | Node {last_query_node_id}]:")
                    print(cached_data.get("response"))
                    print("-" * 70)
                    continue
            except Exception as e:
                if logger:
                    logger.warning(f"[GEGENKONTROLLE FEHLER] index_chat_user_query fehlgeschlagen: {e}")
                last_query_node_id = None
                log_table = None
                effective_input = user_input

            # Stufe 2: LLM-Inferenz oder Pipeline mit automatischer Spinner-Koppelung (run_agent)
            if pipeline.client:
                domain = pipeline._detect_domain(effective_input)
                db_tips = pipeline._get_relevant_tips(effective_input)
                user_blueprint = pipeline.initialize_blueprint_system(effective_input)

                system_prompt = f"""
You are an autonomous AI Agent with an active SQLite Long-Term Memory (Knowledge Agent Routing Tree).
Current Detected Domain: {domain}
Blueprint Status: {user_blueprint['status']}

Retrieved Knowledge & Past Patterns from SQLite DB:
{db_tips}

Your Task: Answer the user's request in German, keeping any code or technical keywords strictly in English. 
Acknowledge and make use of the SQLite database context if relevant.
"""
                chat_messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": effective_input}
                ]

                # Zentraler Agenten-Aufruf via run_agent mit automatischem Spinner
                chat_res = ollama_manager.run_agent(
                    chat_messages,
                    agent_title=f"{AGENT_NAME}-Chat",
                    model=pipeline.model_name,
                    ollama_host=pipeline.ollama_host
                ) if ollama_manager else {"content": ""}

                answer = chat_res.get("content", "")

                # Cache versiegeln
                if last_query_node_id:
                    pipeline.seal_query_cache(last_query_node_id, answer)
                
                # Auto-Persistence
                if "verewige" in user_input.lower() or "speichere in sql" in user_input.lower():
                    pipeline.persist_new_capability(
                        capability_name="Autonomous_Capability",
                        code_snippet=answer[:PROMPT_MAX_LEN],
                        description=user_input
                    )
                    if logger:
                        logger.info("\n[SYSTEM-INFO] Die Fähigkeit wurde physisch in die SQLite-Tabelle 'library_registry' geschrieben!")

                elif "sql" in user_input.lower() or "fehler" in user_input.lower() or "code" in user_input.lower():
                    pipeline.log_save_query_run_to_db_timestamp(
                        task_description=effective_input,
                        error_msg=f"User interaction pattern in domain [{domain}]",
                        solution_code=answer[:TASK_DESCRIPTION_MAX_LEN],
                        run_id=indexed_context.get("time_stamp") if 'indexed_context' in locals() else None,
                        step_type="checkpoint",
                        log_table_name=log_table
                    )

                print(f"\n{AGENT_NAME} [Domain: {domain} | DB aktiv]:\n{answer}\n" + "-" * 70)
            else:
                result = pipeline.run_pipeline(effective_input)
                print(f"\n{AGENT_NAME} [Status: {result.get('status')}]:")
                print(result.get("message") or result.get("result") or result.get("error"))
                print("-" * 70)

        except KeyboardInterrupt:
            print("\n\nAgent: Sitzung durch Benutzer abgebrochen.")
            break
        except Exception as e:
            if logger:
                logger.error(f"[FEHLER IM AGENTEN-LOOP] Konnte Anfrage nicht verarbeiten: {e}")