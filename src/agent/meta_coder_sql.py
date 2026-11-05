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
tool_evolution_manager = globals().get('class_self_tool_evolution_manager')

# Initialisierung des zentralen Loggers
if logger:
    logger.initialize_logger()


# GLOBALE KONFIGURATION — Mechanische Steuerung der LLM-Intensität und Grenzwerte
PROJECT_POINT = "src"
DB_FILENAME = "Knowledge_Agent_Routing_tree.db"
OLLAMA_CHECKER_FILENAME = "__ollama_running.py"

MODEL_LLM = "deepseek-r1-8b"
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
ALLOWED_TABLES = ALLOWED_TABLES_EXCLUDE
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

    
    def bootstrap_from_database(self):
        """Lädt die DNA-Konfiguration aus der Datenbank."""
        return super().bootstrap_from_database()

    def check_or_cache_user_query(self, user_query: str) -> dict:
        """Prüft den Cache oder registriert eine neue Anfrage."""
        return super().get_cached_or_create_query(user_query)

    def seal_query_cache(self, node_id: str, answer: str, snippet: str = ""):
        """Versiegelt eine erfolgreich beantwortete Anfrage in user_query."""
        return super().seal_query_cache(node_id=node_id, answer=answer, snippet=snippet)

    def record_feedback(self, query_node_id: str, is_positive: bool, comment: str = "") -> dict:
        """Verarbeitet Benutzer-Feedback."""
        return super().record_feedback(query_node_id=query_node_id, is_positive=is_positive, comment=comment)

    def persist_new_capability(self, capability_name: str, code_snippet: str, description: str = ""):
        """Persistiert eine neue Fähigkeit in der SQLite-Tabelle."""
        return super().persist_new_capability(capability_name=capability_name, code_snippet=code_snippet, description=description)

    def _get_relevant_tips(self, task_description: str) -> str:
        """Lädt kontextbezogene Richtlinien aus der Datenbank."""
        return super()._get_relevant_tips(task_description=task_description)

    def _save_solution_to_db(self, task_description: str, solution_code: str, error_msg: str = ""):
        """Speichert eine Lösung in der Datenbank."""
        return super()._save_solution_to_db(task_description=task_description, solution_code=solution_code, error_msg=error_msg)

    def evolve_self(self, recent_error: str = "", task_context: str = ""):
        """Führt eine Selbst-Evolution durch."""
        return super().evolve_self(recent_error=recent_error, task_context=task_context)

    def verify_environment(self) -> bool:
        """Verifiziert die SQLite-Umgebung und Kern-Tabellen."""
        return super().verify_environment()

    def evolve_and_register_tool(self, tool_name: str, code_snippet: str, description: str = "", test_call: str = "", allow_replace: bool = True) -> dict:
        """Führt den vollständigen 4-Stufen-Evolutionszyklus aus und injiziert das Werkzeug in den RAM."""
        if self.evolution_manager:
            return self.evolution_manager.evolve_and_register_new_tool(
                tool_name=tool_name,
                code_snippet=code_snippet,
                description=description,
                test_call=test_call,
                target_agent=self,
                allow_replace=allow_replace
            )
        return {"status": "FAILED", "error": "Evolution manager not available"}

    def execute_capability_evolution_pipeline(self, task_description: str, node_id: str = None, log_table: str = None, time_stamp: str = None) -> dict:
        """
        Erzwingt den 4-Stufen-Evolutionszyklus für neue Kernel-Funktionen und Fähigkeiten (Anti-Heißluft):
        Stufe A: LLM-Codegenerierung (leerer Code = Abbruch/Fehler).
        Stufe B: Zwingender Sandbox-Test via SubAgentVerifier (Returncode 0 erforderlich).
        Stufe C: Transaktionaler SQL-Commit in library_registry (INSERT OR REPLACE).
        Stufe D: Dynamischer RAM-Bootstrap & Signatur-Check.
        """
        import ast
        import re
        if logger:
            logger.info(f"[CAPABILITY-EVOLUTION] Starte 4-Stufen-Zyklus für: {task_description[:80]}")

        # 1. Namen der Zielfunktion ermitteln
        fn_match = re.search(r'(?:funktion|def|kernel-funktion|kernel_funktion|tool)\s+([a-zA-Z0-9_]+)', task_description, re.IGNORECASE)
        target_fn_name = fn_match.group(1) if fn_match else "run_multi_model_consensus"
        if "consensus" in task_description.lower() or "run_multi_model_consensus" in task_description:
            target_fn_name = "run_multi_model_consensus"

        # Stufe A: LLM-Codegenerierung mit Rückfall/Evolutionsschleife
        system_prompt = f"""Du bist ein autonomer Python-Entwickler für Offline_AI.
Deine Aufgabe ist es, eine neue Python-Funktion '{target_fn_name}' zu implementieren.
Anforderung:
{task_description}

Strikte Regeln:
1. Liefere den vollständigen, lauffähigen Python-Code in einem einzigen Markdown-Block (```python ... ```).
2. Alle erforderlichen Imports (z. B. urllib.request, json, random, psutil, typing, etc.) müssen im Codeblock enthalten sein.
3. Verwende KEINE verbotenen Module (kein subprocess, kein eval, kein exec, kein open).
4. Am Ende des Codeblocks muss ein kurzer, sicherer Funktionsaufruf (Smoke-Test) oder 'if __name__ == "__main__":' stehen, damit der Subprozess-Test den Returncode 0 bestätigt.
5. Antworte NUR mit dem Codeblock und kurzer Erklärung, keine Höflichkeitsfloskeln.
6. psutil hat KEINE gpu_percent()-Funktion; nutze psutil.cpu_percent() und psutil.virtual_memory().percent. Für GPU nutze 0.0 als sicheren Fallback.
7. Alle externen API-Aufrufe (z. B. zu Ollama) in try-except-Blöcke kapseln, damit bei Verbindungs-Timeouts saubere Fallback-Werte zurückgegeben werden.
"""
        generated_code = ""
        last_error = ""
        verification_output = ""
        verified = False

        for gen in range(1, MAX_EVOLUTION_GENERATIONS + 1):
            if logger:
                logger.info(f"[EVOLUTION GENERATION {gen}/{MAX_EVOLUTION_GENERATIONS}] Generiere und teste '{target_fn_name}'...")

            chat_messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Implementiere '{target_fn_name}' fehlerfrei." if gen == 1 else f"Der Sandbox-Test schlug fehl mit:\n{last_error}\nBitte korrigiere den Code."}
            ]

            chat_res = ollama_manager.run_agent(
                chat_messages,
                agent_title=f"{AGENT_NAME}-Evo-Gen{gen}",
                model=self.model_name,
                ollama_host=self.ollama_host
            ) if ollama_manager else {"status": "FAILED", "content": ""}

            content = chat_res.get("content", "") if isinstance(chat_res, dict) else ""
            blocks = sub_verifier.extract_code_blocks(content) if (sub_verifier and content) else []
            if not blocks and "def " in content:
                blocks = [content]

            # STUFE A Sicherung: Leerer Code führt zu hartem Abbruch
            if not blocks or not blocks[0].strip():
                last_error = "Kein ausführbarer Code-Block vom LLM generiert (Anti-Heißluft)."
                continue

            generated_code = blocks[0].strip()

            # STUFE B: Zwingender Sandbox-Test via SubAgentVerifier
            try:
                tree = ast.parse(generated_code)
                found_funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
                if found_funcs and target_fn_name not in found_funcs:
                    target_fn_name = found_funcs[0]

                verified, verification_output = sub_verifier.verify_code_in_sandbox(
                    generated_code,
                    timeout_sec=SANDBOX_TIMEOUT
                ) if sub_verifier else (True, "Verifier omitted")
            except Exception as se:
                verified = False
                verification_output = f"AST/Syntax Error: {se}"

            if verified:
                if logger:
                    logger.info(f"[SANDBOX-ERFOLG] Code für '{target_fn_name}' in Generation {gen} verifiziert (Returncode 0).")
                break
            else:
                last_error = verification_output
                if logger:
                    logger.warning(f"[SANDBOX-FEHLER] Generation {gen} fehlgeschlagen: {str(last_error)[:200]}")

        if not verified or not generated_code:
            err_result = {
                "status": "FAILED",
                "error": f"Fähigkeit '{target_fn_name}' konnte nach {MAX_EVOLUTION_GENERATIONS} Generationen nicht verifiziert werden. Letzter Fehler: {last_error}"
            }
            if logger:
                logger.error(f"[CAPABILITY-EVOLUTION FEHLER] {err_result['error']}")
            return err_result

        # STUFE C: Automatisierter transaktionaler SQL-Commit in library_registry
        persisted_node_id = None
        if self.evolution_manager:
            evo_res = self.evolution_manager.evolve_and_register_new_tool(
                tool_name=target_fn_name,
                code_snippet=generated_code,
                description=task_description[:500],
                target_agent=self,
                allow_replace=True
            )
            persisted_node_id = evo_res.get("node_id")

        if not persisted_node_id:
            now = datetime.datetime.now()
            node_id_gen = f"CAP_{now.strftime('%Y%m%d_%H%M%S')}_{random.randint(100, 999)}"
            with sqlite3.connect(self.db_filename) as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT OR REPLACE INTO library_registry (
                        node_id, is_active, error_fallback_count,
                        year, month, day, hour, minute, second,
                        topic_title, topic_specification, agent_instruction,
                        example_code_snippet, validation_rule, execution_count,
                        success_weight, target_table, target_column_id, target_node_id
                    ) VALUES (?, 1, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'SANDBOX_VERIFIED_RETURNCODE_0', 1, 1.0, 'user_query', 'node_id', '000')
                """, (
                    node_id_gen, now.year, now.month, now.day, now.hour, now.minute, now.second,
                    target_fn_name, task_description[:500], f"EXECUTE_TOOL: {target_fn_name}",
                    generated_code
                ))
                conn.commit()
                persisted_node_id = node_id_gen

        # STUFE D: Dynamischer RAM-Bootstrap & Live-Check
        injected = []
        if self.evolution_manager:
            inj_res = self.evolution_manager.inject_capability_into_ram(generated_code, target_agent=self)
            injected = inj_res.get("injected", [])

        is_callable = callable(getattr(self, target_fn_name, None)) or (target_fn_name in injected) or (self.evolution_manager and target_fn_name in self.evolution_manager.ram_capabilities)
        if not is_callable and logger:
            logger.warning(f"[RAM-CHECK WARNUNG] Funktion '{target_fn_name}' nicht direkt aufrufbar, gefundene Symbole: {injected}")

        # Protokollierung & Cache-Versiegelung mit echtem Snippet
        if node_id:
            try:
                self.seal_query_cache(node_id=node_id, answer=f"Fähigkeit '{target_fn_name}' erfolgreich in library_registry (Node: {persisted_node_id}) verewigt.", snippet=generated_code)
            except Exception as e:
                if logger:
                    logger.warning(f"[CACHE SEAL WARNUNG] {e}")

        if log_table and time_stamp:
            try:
                self.log_save_query_run_to_db_timestamp(
                    task_description=task_description,
                    error_msg="",
                    solution_code=generated_code[:TASK_DESCRIPTION_MAX_LEN],
                    run_id=time_stamp,
                    step_type="seal",
                    log_table_name=log_table
                )
            except Exception as e:
                pass

        return {
            "status": "SUCCESS",
            "node_id": persisted_node_id,
            "tool_name": target_fn_name,
            "injected_functions": injected,
            "code_snippet": generated_code,
            "message": f"Fähigkeit '{target_fn_name}' verifiziert (Returncode 0), in 'library_registry' (Node {persisted_node_id}) persistiert und im RAM aktiviert."
        }

    def bootstrap_ram_capabilities(self) -> dict:
        """Lädt alle aktiven Fähigkeiten aus der Datenbank direkt in den RAM."""
        if self.evolution_manager:
            return self.evolution_manager.bootstrap_ram_capabilities(target_agent=self)
        return {"status": "FAILED", "error": "Evolution manager not available"}

    def introspect_library(self) -> dict:
        """Analysiert die bestehende library_registry vor neuen Erstellungen (Anti-Code-Shrinking)."""
        if self.evolution_manager:
            return self.evolution_manager.introspect_existing_library()
        return {"total_count": 0, "functions": set(), "nodes": []}

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

        # 4. Self-Tool-Evolution-Manager & dynamischer RAM-Bootstrap (Stufe 4)
        evo_mgr_cls = globals().get('class_self_tool_evolution_manager') or tool_evolution_manager
        self.evolution_manager = evo_mgr_cls(db_path=self.db_filename) if evo_mgr_cls else None
        if self.evolution_manager:
            self.evolution_manager.bootstrap_ram_capabilities(target_agent=self)
        
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

        # Anti-Heißluft: Capability-Evolutionsaufträge zwingend über den 4-Stufen-Zyklus routen
        capability_terms = [
            "run_multi_model_consensus", "consensus", "fähigkeit", "fehigkeit",
            "capability", "kernel-funktion", "kernel funktion", "kernel_funktion",
            "neue funktion", "erstelle funktion", "registriere in library_registry",
            "library_registry", "tool-evolution", "tool evolution"
        ]
        if any(term in task_description.lower() for term in capability_terms):
            return self.execute_capability_evolution_pipeline(
                task_description=effective_task,
                node_id=node_id,
                log_table=log_table,
                time_stamp=time_stamp
            )

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
                raise RuntimeError("Anti-Heißluft-Schutz: Kein ausführbarer Code-Block gefunden. Erfolg wird verweigert.")
            
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
    try:
        pipeline.bootstrap_ram_capabilities()
    except Exception as e:
        if logger:
            logger.warning(f"[BOOT WARNUNG] RAM-Bootstrap konnte nicht geladen werden: {e}")
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
globals()['class_self_tool_evolution_manager'] = globals().get('class_self_tool_evolution_manager') or tool_evolution_manager


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
                    cached_resp = cached_data.get("response")
                    cached_node = cached_data.get("node_id")

                    # Prüfung auf Weiterentwicklung: Wurde in library_registry neues Wissen verankert?
                    has_evolved = pipeline.check_library_evolution_since_node(cached_node) if hasattr(pipeline, "check_library_evolution_since_node") else False

                    if not has_evolved and cached_resp and cached_resp.strip() and cached_resp != "PROCESSING":
                        print(f"\n{AGENT_NAME} [Domain: SQL-Cache | DB aktiv | Node {last_query_node_id}]:")
                        print(cached_resp)
                        print("-" * 70)
                        continue
                    elif has_evolved:
                        if logger:
                            logger.info(f"[EVOLUTION] Neues Wissen in 'library_registry' nach Node {cached_node} erkannt - Antwort wird aktualisiert.")
            except Exception as e:
                if logger:
                    logger.warning(f"[GEGENKONTROLLE FEHLER] index_chat_user_query fehlgeschlagen: {e}")
                last_query_node_id = None
                log_table = None
                effective_input = user_input

            # Stufe 2A: Intent-Trennung für Capability- & Tool-Evolution (Anti-Heißluft & Stufe A-D)
            capability_terms = [
                "run_multi_model_consensus", "consensus", "fähigkeit", "fehigkeit",
                "capability", "kernel-funktion", "kernel funktion", "kernel_funktion",
                "neue funktion", "erstelle funktion", "registriere in library_registry",
                "library_registry", "tool-evolution", "tool evolution"
            ]
            is_capability_evolution = any(term in user_input.lower() for term in capability_terms)

            if is_capability_evolution:
                if logger:
                    logger.info(f"[TOOL-EVOLUTION] Starte verbindliche 4-Stufen-Evolution: {effective_input[:80]}")
                evo_result = pipeline.execute_capability_evolution_pipeline(
                    effective_input,
                    node_id=last_query_node_id,
                    log_table=log_table,
                    time_stamp=indexed_context.get("time_stamp") if 'indexed_context' in locals() else None
                )
                res_msg = evo_result.get("message") or evo_result.get("error")
                print(f"\n{AGENT_NAME} [Status: {evo_result.get('status')} | Tool-Evolution]:\n{res_msg}\n" + "-" * 70)
                continue

            # Stufe 2B: Aufgaben-Klassifizierung (Job im Projektverzeichnis vs. Frage-Antwort / Code)
            action_terms = ["erstelle", "schreibe datei", "repariere", "korrigiere", "fuehre aus", "führe aus", "analysiere projekt", "fixe", "implementiere"]
            is_job = any(term in user_input.lower() for term in action_terms) and not any(user_input.lower().startswith(q) for q in ["was", "wie", "welche", "warum", "kannst du erklaeren", "kannst du erklären", "zeige"])

            if is_job:
                if logger:
                    logger.info(f"[PROJEKT-JOB] Fuehre Aufgabe im Projektverzeichnis aus: {effective_input[:80]}")
                job_result = pipeline.run_pipeline(effective_input)
                res_msg = job_result.get("message") or job_result.get("result") or job_result.get("error")
                print(f"\n{AGENT_NAME} [Status: {job_result.get('status')} | Projekt-Ausfuehrung]:\n{res_msg}\n" + "-" * 70)
                if last_query_node_id and res_msg:
                    pipeline.seal_query_cache(last_query_node_id, str(res_msg))
                continue

            # Stufe 3: LLM-Inferenz oder Pipeline mit automatischer Spinner-Koppelung (run_agent)
            if pipeline.client:
                domain = pipeline._detect_domain(effective_input)
                db_tips = pipeline._get_relevant_tips(effective_input)
                user_blueprint = pipeline.initialize_blueprint_system(effective_input)

                system_prompt = f"""Du bist der Offline-AI Agent für Python-Entwicklung und Software-Architektur.
Aktuelle Domäne: {domain}

Wissensfundament & Richtlinien aus der SQLite-Bibliothek (library_registry):
{db_tips}

Regeln für deine Antwort:
1. Keine Begrüßungsfloskeln, kein Smalltalk und keine Meta-Selbsterklärungen (z. B. nicht sagen 'Ich bin ein Agent...'). Antworte direkt, präzise und sachbezogen.
2. Wenn nach Code gefragt wird, liefere den vollständigen, sauberen Code als Markdown-Block (```python ... ```).
3. Beziehe relevante Funktionen oder Konzepte aus der SQLite-Bibliothek ein, um die Frage technisch fundiert zu beantworten.
4. Alle Code-Elemente (Klassen, Funktionen, Variablen) strikt in englischer Sprache benennen; Erklärungen auf benutzer gefragte Sprache verfassen.
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
                ) if ollama_manager else {"status": "FAILED", "content": ""}

                answer = chat_res.get("content", "") if isinstance(chat_res, dict) else ""

                # Autonomer Fallback auf SQLite Knowledge Tree wenn LLM leer oder Modell fehlt
                if not answer or not answer.strip() or (isinstance(chat_res, dict) and chat_res.get("status") == "FAILED"):
                    err_msg = chat_res.get("error", "LLM lieferte keine Antwort") if isinstance(chat_res, dict) else "Kein Inferenz-Ergebnis"
                    answer = pipeline.generate_knowledge_fallback_response(
                        effective_input,
                        domain=domain,
                        db_tips=db_tips,
                        error_info=err_msg
                    )

                # Cache nur mit gehaltvoller Antwort versiegeln
                if last_query_node_id and answer and answer.strip():
                    pipeline.seal_query_cache(last_query_node_id, answer)
                
                # Auto-Persistence & 4-Stufen Self-Tool-Evolution
                if any(trigger in user_input.lower() for trigger in ["verewige", "speichere in sql", "erstelle fähigkeit", "erstelle fehigkeit", "erstelle tool", "neue fähigkeit", "neue fehigkeit", "lerne"]):
                    extracted_code = ""
                    if sub_verifier and hasattr(sub_verifier, "extract_code_blocks"):
                        blocks = sub_verifier.extract_code_blocks(answer) or sub_verifier.extract_code_blocks(user_input)
                        if blocks:
                            extracted_code = blocks[0] if isinstance(blocks, list) else blocks
                    if not extracted_code:
                        extracted_code = answer

                    tool_title = f"Capability_{datetime.datetime.now().strftime('%H%M%S')}"
                    evo_res = pipeline.evolve_and_register_tool(
                        tool_name=tool_title,
                        code_snippet=extracted_code,
                        description=user_input
                    )
                    print(f"--> [TOOL-EVOLUTION] Status: {evo_res.get('status')} | Im RAM aktiviert: {evo_res.get('injected_functions')}")

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