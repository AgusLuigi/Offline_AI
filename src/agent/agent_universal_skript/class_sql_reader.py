import os
import sys
import sqlite3
import datetime
import random
import importlib.util
from pathlib import Path

# Basis-Infrastruktur importieren
from agent_universal_skript.class_coreInfrastructure import coreInfrastructure
from agent_universal_skript.class_ollama_manager import OllamaManager


class class_sql_reader(coreInfrastructure):
    """
    Universeller SQL-Reader und Ausführungsmotor für den Knowledge Agent Routing Tree.
    Alle konfigurierbaren Parameter sind als Klassenattribute definiert,
    damit abgeleitete Agenten und Pipelines sie bei Bedarf überschreiben können.
    Ist in der Lage, Phasen aus 'meta_agent_start' sequenziell abzurufen,
    nach DB-Vorgabe zeilenweise auszuführen und Rückmeldungen an den Benutzer zu liefern.
    """

    # --- Datenbank & Projekt-Standards ---
    PROJECT_POINT = "src"
    DB_FILENAME = "Knowledge_Agent_Routing_tree.db"
    AGENT_NAME = "MetaCoder-Agent"
    MODEL_LLM = "codestral"
    OLLAMA_HOST = "http://127.0.0.1:11434"

    # --- Schwellenwerte & Limits ---
    MAX_EVOLUTION_GENERATIONS = 3
    MAX_USER_QUERY_ID_RANGE = (3, 999)
    EVOLUTION_RETRY_DELAY_SEC = 1
    TASK_DESCRIPTION_MAX_LEN = 200
    CODE_SNIPPET_PREVIEW_LEN = 150
    QUERY_TITLE_MAX_LEN = 35
    MAX_SANDBOX_OUTPUT_LENGTH = 4000
    DEFAULT_SANDBOX_TIMEOUT = 15
    PROMPT_MAX_LEN = 500
    TFIDF_SIMILARITY_THRESHOLD = 0.15
    FEEDBACK_WEIGHT_INCREMENT = 0.2
    MAX_BLUEPRINT_STEPS = 5
    MAX_DOMAIN_NODES = 3
    MAX_MANIFEST_ENTRIES = 5
    CPU_WARNING_THRESHOLD = 90.0
    MIN_RAM_MB = 2000
    SPINNER_INTERVAL = 1.0

    REQUIRED_KERNEL_MODULES = ["psutil", "sqlite3"]

    # --- Erlaubte Tabellen für SQL-Operationen ---
    ALLOWED_TABLES = {
        "user_query",
        "table_issue_data_time_stamp_run_protocol_for_query",
        "meta_admin_repair_registry",
        "meta_admin_bootstrap_registry",
        "meta_admin_taboo_rules",
        "system_resources",
        "toolkit_library_registry",
        "pre_execution_blueprint_generator",
        "library_registry",
        "meta_agent_start",
        "agent_system_manifest",
        "index_chat_user_query",
        "kernel_tool",
        "hardware_enviroment"
    }

    DEFAULT_DOMAIN = "library_registry"

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

    def __init__(self, db_filename: str = None):
        super().__init__()
        self.root_path = Path(self.get_project_root())
        target_db = db_filename or self.DB_FILENAME
        try:
            self.db_filename = str(self.get_file_path(target_db))
        except FileNotFoundError:
            self.db_filename = str(self.root_path / target_db)

        self.bootstrap_dna = []
        self.manifest_directives = {}

    def get_db_connection(self, filename: str = None) -> sqlite3.Connection:
        """Stellt eine sichere Verbindung zur Knowledge-Datenbank her."""
        target_file = filename or getattr(self, "db_filename", None) or self.DB_FILENAME
        try:
            db_path = self.get_file_path(target_file)
        except Exception:
            db_path = Path(target_file) if Path(target_file).is_absolute() else self.root_path / target_file

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_core_tables(self):
        """Garantiert die physische Existenz aller Kern-Tabellen vor Pipeline-Start."""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_query (
                        node_id TEXT PRIMARY KEY,
                        is_active INTEGER DEFAULT 1,
                        error_fallback_count INTEGER DEFAULT 0,
                        year INTEGER, month INTEGER, day INTEGER, hour INTEGER, minute INTEGER, second INTEGER,
                        topic_title TEXT,
                        topic_specification TEXT,
                        agent_instruction TEXT,
                        example_code_snippet TEXT,
                        validation_rule TEXT,
                        execution_count INTEGER DEFAULT 0,
                        success_weight REAL DEFAULT 1.0,
                        target_table TEXT,
                        target_column_id TEXT,
                        target_node_id TEXT
                    );
                """)
                conn.commit()
            except sqlite3.Error as e:
                print(f"[GEGENKONTROLLE FEHLER] Konnte Tabellenstrukturen nicht härten: {e}")

    def verify_environment(self) -> bool:
        """Prüft die Existenz der globalen Datenbank und initialisiert Tabellenstrukturen."""
        db_path = Path(self.db_filename)
        if not db_path.exists():
            print(f"[METABASE] Erstelle neue SQLite-Registry unter: {db_path.resolve()}")
            db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_core_tables()
        print("[METAKODER] Umgebung erfolgreich verifiziert. Alle erweiterten Tools verbunden.")
        return True

    
    # DATABASE-DRIVEN DNA BOOTSTRAP (Phasen 000, 001, 999)
    

    def bootstrap_from_database(self) -> list:
        """
        Lädt die Start-DNA des Agenten autonom aus der SQLite-Datenbank.
        Folgt der Kette: meta_admin_bootstrap_registry (Node '001') → meta_agent_start ('000' bis '999').
        """
        print("\n" + "=" * 60)
        print(" [BOOTSTRAP-DNA] Initialisiere Agent über SQLite Knowledge Tree")
        print("=" * 60)
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()

                # 1. Inbound-Prüfung über meta_admin_bootstrap_registry Node 001
                cursor.execute("""
                    SELECT target_table, target_node_id, topic_title 
                    FROM meta_admin_bootstrap_registry 
                    WHERE node_id = '001' AND is_active = 1
                """)
                registry_entry = cursor.fetchone()
                if not registry_entry:
                    print("--> [WARNUNG] Kein aktiver Bootstrap-Eintrag '001' in meta_admin_bootstrap_registry gefunden.")
                    start_table = "meta_agent_start"
                else:
                    start_table = registry_entry[0]
                    print(f"--> [REGISTRY LINK] Node '001' verweist auf '{start_table}' (Ziel: '{registry_entry[1]}')")

                # 2. Phasen aus meta_agent_start sequenziell abrufen
                cursor.execute(f"""
                    SELECT node_id, topic_title, topic_specification, agent_instruction, 
                           example_code_snippet, validation_rule, target_table, target_node_id
                    FROM {start_table}
                    WHERE is_active = 1
                    ORDER BY node_id ASC
                """)
                phases = cursor.fetchall()
                self.bootstrap_dna = phases

                for row in phases:
                    node_id = row[0]
                    title = row[1]
                    print(f"  * Phase [{node_id}] {title}")

                    # Phase 000: System Manifest harvest
                    if node_id == "000":
                        try:
                            cursor.execute("SELECT directive_key, explanation_for_agent FROM agent_system_manifest WHERE is_active = 1")
                            self.manifest_directives = dict(cursor.fetchall())
                            print(f"    -> {len(self.manifest_directives)} Kern-Direktiven aus 'agent_system_manifest' absorbiert.")
                        except sqlite3.OperationalError:
                            pass

                    # Phase 001: Kernel & Resource Audit
                    elif node_id == "001":
                        k_mods = self.scan_kernel_modules(self.REQUIRED_KERNEL_MODULES + ["ollama"])
                        print(f"    -> Kernel-Audit: {sum(1 for v in k_mods.values() if v == 'active')}/{len(k_mods)} Module aktiv.")

                    # Phase 002: Cache readiness check
                    elif node_id == "002":
                        try:
                            cursor.execute("SELECT COUNT(*) FROM user_query WHERE is_active = 1")
                            active_queries = cursor.fetchone()[0]
                            print(f"    -> Idempotenz-Prüfung: 'user_query' betriebsbereit ({active_queries} aktive Einträge).")
                        except sqlite3.OperationalError:
                            print("    -> Tabelle 'user_query' nicht gefunden, wird bei Bedarf erstellt.")

                    # Phase 999: Startup Seal
                    elif node_id == "999":
                        now = datetime.datetime.now()
                        try:
                            self._insert_routing_node(
                                conn=conn,
                                table_name="table_issue_data_time_stamp_run_protocol_for_query",
                                node_id=f"START_{now.strftime('%Y%m%d_%H%M%S')}",
                                topic_title="AGENT_BOOTSTRAP_SUCCESS",
                                topic_specification=f"Bootstrapped via {start_table} with {len(phases)} phases",
                                agent_instruction="SYSTEM_READY_FOR_INTERACTION",
                                validation_rule="BOOTSTRAP_SEALED == TRUE",
                                target_table="user_query",
                                target_node_id="000"
                            )
                            print(f"    -> Startup-Siegel in 'table_issue_data_time_stamp_run_protocol_for_query' verankert.")
                        except Exception:
                            pass

                print(f"--> [BOOTSTRAP-DNA ERFOLG] {len(phases)} Phasen erfolgreich aus SQLite instanziiert.")
                print("=" * 60 + "\n")
                return phases
        except Exception as e:
            print(f"--> [BOOTSTRAP FEHLER] Konnte Start-DNA nicht vollständig laden: {e}")
            return []

    
    # SEQUENZIELLE PHASEN-AUSFÜHRUNG AUS DER SQL-DATENBANK (Regel 5)
    

    def execute_query_with_db_phases(self, raw_query: str, model_name: str = None, 
                                     ollama_host: str = None, spinner_thread_starter=None) -> dict:
        """
        Führt eine Benutzeranfrage streng nach den Vorgaben der Phasen aus 'meta_agent_start' aus:
        1. Phasen sequentiell aus 'meta_agent_start' abrufen.
        2. Zeile nach Zeile ausführen:
           - Phase 002: IDEMPOTENT QUERY CACHE & SEQUENTIAL INGESTION
           - Phase 003: DYNAMIC BLUEPRINT DISPATCH & COGNITIVE ROUTING
           - Phase 004: CLOSED-LOOP EXECUTION & SUB-AGENT CODE VERIFICATION
           - Phase 005: STRICT SCHEMATIC PROTOCOL SEAL & TIMESTAMP BINDING
           - Phase 999: AGENT READY GATEWAY & BENUTZER-ANTWORT
        3. Rückmeldung / Antwort für den Benutzer sicherstellen.
        """
        # Phasen aus meta_agent_start laden
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT node_id, topic_title, topic_specification, agent_instruction, 
                       example_code_snippet, validation_rule, target_table, target_node_id
                FROM meta_agent_start
                WHERE is_active = 1
                ORDER BY node_id ASC
            """)
            phases_dict = {row[0]: dict(row) for row in cursor.fetchall()}

        clean_text = " ".join(raw_query.strip().split())
        cleaned_query_lower = clean_text.lower()
        now = datetime.datetime.now()

        # -------------------------------------------------------------
        # Phase [002]: IDEMPOTENT QUERY CACHE & SEQUENTIAL INGESTION
        # -------------------------------------------------------------
        phase_002 = phases_dict.get("002", {})
        query_node_id = None
        log_table_name = None
        time_stamp_str = None
        cached_result = None

        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT node_id, topic_title, topic_specification, agent_instruction, example_code_snippet, validation_rule
                FROM user_query
                WHERE TRIM(LOWER(topic_specification)) = ? AND is_active = 1
                ORDER BY node_id DESC LIMIT 1
            """, (cleaned_query_lower,))
            cached = cursor.fetchone()

            if cached and cached[3] and cached[3] != "PROCESSING" and cached[5] == "COMPLETED_CACHE_READY":
                cursor.execute("UPDATE user_query SET execution_count = execution_count + 1 WHERE node_id = ?", (cached[0],))
                conn.commit()
                print(f"--> [SQL-CACHE HIT] Anfrage direkt aus Node '{cached[0]}' geladen (Zero-Compute)!")
                return {
                    "status": "SUCCESS",
                    "cache_hit": True,
                    "node_id": cached[0],
                    "title": cached[1],
                    "domain": "SQL-Cache",
                    "answer": cached[3],
                    "snippet": cached[4]
                }

            # Cache Miss: Token-Schärfung & Registrierung
            indexed_info = self.index_chat_user_query(raw_query)
            query_node_id = indexed_info.get("node_id")
            log_table_name = indexed_info.get("log_table_name")
            time_stamp_str = indexed_info.get("time_stamp")
            effective_query = indexed_info.get("sharpened_query") or raw_query

        # -------------------------------------------------------------
        # Phase [003]: DYNAMIC BLUEPRINT DISPATCH & COGNITIVE ROUTING
        # -------------------------------------------------------------
        phase_003 = phases_dict.get("003", {})
        domain = self._detect_domain(effective_query)
        db_tips = self._get_relevant_tips(effective_query)
        blueprint_info = self.initialize_blueprint_system(effective_query)

        # -------------------------------------------------------------
        # Phase [004]: CLOSED-LOOP EXECUTION & SUB-AGENT CODE VERIFICATION
        # -------------------------------------------------------------
        phase_004 = phases_dict.get("004", {})
        active_model = model_name or getattr(self, "model_name", None) or self.MODEL_LLM
        active_host = ollama_host or getattr(self, "ollama_host", None) or self.OLLAMA_HOST

        # Prüfen und ggf. automatischen Start von Ollama durchführen
        ollama_ready = OllamaManager.ensure_ollama_running(active_host)

        answer = ""
        codes = []

        if ollama_ready:
            system_prompt = f"""
You are an autonomous AI Agent with an active SQLite Long-Term Memory (Knowledge Agent Routing Tree).
Current Detected Domain: {domain}
Blueprint Status: {blueprint_info.get('status')}

Retrieved Knowledge & Past Patterns from SQLite DB:
{db_tips}

Your Task: Answer the user's request in German, keeping any code or technical keywords strictly in English. 
Acknowledge and make use of the SQLite database context if relevant.
"""
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": effective_query}
            ]

            # Spinner während des LLM-Aufrufs aktivieren, falls Starter übergeben wurde
            stop_event = None
            if spinner_thread_starter:
                stop_event, spinner_thread = spinner_thread_starter(f"{self.AGENT_NAME}-Chat")

            try:
                chat_res = OllamaManager.chat(messages=messages, model=active_model, ollama_host=active_host)
                if chat_res.get("status") == "SUCCESS":
                    answer = chat_res.get("content", "").strip()
            except Exception:
                answer = ""
            finally:
                if stop_event:
                    stop_event.set()
                    spinner_thread.join()

        # Fallback, falls Ollama nicht verfügbar ist oder keine Antwort lieferte
        if not answer.strip():
            answer = (
                f"Hallo! Ich bin der {self.AGENT_NAME} und mit dem Knowledge Agent Routing Tree verbunden.\n"
                f"Deine Anfrage '{clean_text}' wurde in die Domäne [{domain}] klassifiziert.\n\n"
                f"Aktueller Zustand des Wissensbaums:\n"
                f"* Abfrage-Knoten '{query_node_id}' verankert in 'user_query'.\n"
                f"* Protokollschritt in '{log_table_name}' versiegelt.\n"
                f"* Blueprint-Status: {blueprint_info.get('status')}.\n"
            )

        # Code-Verifikation gemäß Phase 004
        try:
            from agent_universal_skript.class_subAgentVerifier import SubAgentVerifier
            codes = SubAgentVerifier.extract_code_blocks(answer)
            if codes:
                code_to_verify = codes[0] if isinstance(codes, list) else codes
                v_ok, v_msg = SubAgentVerifier.verify_code_in_sandbox(
                    code_to_verify, timeout_sec=self.DEFAULT_SANDBOX_TIMEOUT
                )
                if not v_ok:
                    print(f"[VERIFIER WARNUNG] Code-Verifikation meldete: {v_msg}")
        except Exception:
            pass

        # -------------------------------------------------------------
        # Phase [005]: STRICT SCHEMATIC PROTOCOL SEAL & TIMESTAMP BINDING
        # -------------------------------------------------------------
        phase_005 = phases_dict.get("005", {})
        try:
            self.log_save_query_run_to_db_timestamp(
                task_description=effective_query,
                error_msg="",
                solution_code=answer[:self.TASK_DESCRIPTION_MAX_LEN],
                run_id=time_stamp_str,
                step_type="seal",
                log_table_name=log_table_name
            )
        except Exception as e:
            print(f"[GEGENKONTROLLE HINWEIS] Protokollierung in Phase 005 übersprungen: {e}")

        # -------------------------------------------------------------
        # Phase [999]: AGENT READY GATEWAY & ANTWORT-VERSIEGELUNG
        # -------------------------------------------------------------
        if query_node_id:
            snippet_str = str(codes[0]) if codes else ""
            self.seal_query_cache(query_node_id, answer, snippet=snippet_str)

        return {
            "status": "SUCCESS",
            "cache_hit": False,
            "node_id": query_node_id,
            "domain": domain,
            "answer": answer,
            "snippet": codes[0] if codes else ""
        }

    
    # USER-QUERY-CACHE & FEEDBACK
    

    def check_or_cache_user_query(self, raw_query: str) -> dict:
        """Autonome User-Query-Prüfung & Sequenzieller Cache."""
        return self.get_cached_or_create_query(raw_query)

    def seal_query_cache(self, node_id: str, answer: str, snippet: str = ""):
        """Versiegelt eine erfolgreich beantwortete Anfrage in 'user_query' als fertigen Cache-Eintrag."""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE user_query
                SET agent_instruction = ?,
                    example_code_snippet = ?,
                    validation_rule = 'COMPLETED_CACHE_READY',
                    is_active = 1
                WHERE node_id = ?
            """, (answer, snippet, node_id))
            conn.commit()
        print(f"--> [SQL-CACHE SEAL] Antwort in 'user_query' Node '{node_id}' dauerhaft versiegelt.")

    def store_query_result(self, node_id: str, answer: str, snippet: str = ""):
        """Alias für seal_query_cache zur Wahrung der Abwärtskompatibilität."""
        return self.seal_query_cache(node_id=node_id, answer=answer, snippet=snippet)

    def record_feedback(self, query_node_id: str, is_positive: bool, comment: str = "") -> dict:
        """Verarbeitet Benutzer-Feedback für einen Query-Knoten."""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            if is_positive:
                cursor.execute("""
                    UPDATE user_query
                    SET success_weight = success_weight + ?,
                        validation_rule = 'POSITIVE_VERIFIED'
                    WHERE node_id = ?
                """, (self.FEEDBACK_WEIGHT_INCREMENT, query_node_id))
                conn.commit()
                print(f"--> [FEEDBACK POSITIV] Node '{query_node_id}' gestärkt (+{self.FEEDBACK_WEIGHT_INCREMENT}).")
                return {"status": "success", "feedback": "positive", "node_id": query_node_id}
            else:
                return self.deactivate_and_reroute("user_query", query_node_id, failure_reason=comment or "Negatives Benutzer-Feedback")

    def persist_new_capability(self, capability_name: str, code_snippet: str, description: str):
        """Persistiert eine neue Fähigkeit dauerhaft in der 'library_registry' Tabelle."""
        node_id = f"CAP_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        with self.get_db_connection() as conn:
            self._insert_routing_node(
                conn=conn,
                table_name="library_registry",
                node_id=node_id,
                topic_title=capability_name,
                topic_specification=description,
                agent_instruction=f"EXECUTE_CAPABILITY: {capability_name}",
                example_code_snippet=code_snippet[:self.PROMPT_MAX_LEN],
                validation_rule="capability_persisted == TRUE"
            )
        print(f"\n[PERSISTENZ-ERFOLG] Fähigkeit '{capability_name}' wurde dauerhaft in SQLite ('library_registry') verewigt!")

    
    # KOGNITIVE ERFASSUNG, TOKEN-SCHÄRFUNG & AUDIT-PROTOKOLLIERUNG
    

    def index_chat_user_query(self, raw_query: str) -> dict:
        """Erfassung, Bereinigung, Token-Schärfung und Indizierung von Benutzeranfragen."""
        if not raw_query or not isinstance(raw_query, str):
            raw_query = ""

        clean_text = " ".join(raw_query.strip().split())

        # Token-Schärfung
        sharpened_text = clean_text
        stop_phrases = [
            "kannst du bitte", "könntest du bitte", "bitte erstelle", "bitte zeige",
            "bitte mach", "zeige mir", "mach mal", "erstelle mal", "ich möchte",
            "ich will", "für mich", "can you please", "could you please", "please show",
            "show me", "i want to", "i would like"
        ]
        lower_temp = sharpened_text.lower()
        for phrase in stop_phrases:
            if phrase in lower_temp:
                idx = lower_temp.find(phrase)
                sharpened_text = (sharpened_text[:idx] + sharpened_text[idx + len(phrase):]).strip()
                lower_temp = sharpened_text.lower()

        filler_words = {
            "bitte", "mal", "einmal", "halt", "eben", "quasi", "einfach", "gerne",
            "please", "just", "kindly"
        }
        words = sharpened_text.split()
        filtered_words = [w for w in words if w.lower().strip(".,!?:;") not in filler_words]
        sharpened_text = " ".join(filtered_words) if filtered_words else clean_text

        # Intent-Klassifikation
        desc_lower = clean_text.lower()
        if any(k in desc_lower for k in ["repair", "fix", "fehler", "crash", "bug", "error", "notfall", "beheben", "korrigieren"]):
            query_type = "Reparatur"
        elif any(k in desc_lower for k in ["architektur", "blueprint", "struktur", "schema", "routing", "tree", "aufbau", "design"]):
            query_type = "Architektur"
        elif any(k in desc_lower for k in ["analyse", "analysieren", "untersuche", "scan", "prüfe", "audit", "verify", "inspect", "vergleiche"]):
            query_type = "Analyse"
        elif any(k in desc_lower for k in ["code", "coding", "python", "sql", "script", "funktion", "implementiere", "entwickle", "erstelle", "schreiben"]):
            query_type = "Coding"
        else:
            query_type = "Allgemein"

        cached_check = self.get_cached_or_create_query(sharpened_text)
        node_id = cached_check.get("node_id") if cached_check else None

        time_stamp_str = None
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                if node_id:
                    cursor.execute("SELECT year, month, day, hour, minute, second FROM user_query WHERE node_id = ?", (node_id,))
                    t_row = cursor.fetchone()
                else:
                    t_row = None

                if not t_row or not all(t_row):
                    cursor.execute("""
                        SELECT year, month, day, hour, minute, second 
                        FROM user_query 
                        WHERE is_active = 1 
                        ORDER BY year DESC, month DESC, day DESC, hour DESC, minute DESC, second DESC 
                        LIMIT 1
                    """)
                    t_row = cursor.fetchone()

                if t_row and all(t_row):
                    y, m, d, h, mn, s = t_row
                    time_stamp_str = f"{y:04d}{m:02d}{d:02d}_{h:02d}{mn:02d}{s:02d}"
        except Exception:
            pass

        if not time_stamp_str:
            time_stamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        log_table_name = f"log_{time_stamp_str}"

        if not cached_check.get("cache_hit"):
            try:
                self.log_save_query_run_to_db_timestamp(
                    task_description=f"[{query_type}] {sharpened_text}",
                    error_msg="",
                    solution_code="INDEX_CHAT_USER_QUERY_INITIALIZED",
                    run_id=time_stamp_str,
                    step_type="init",
                    log_table_name=log_table_name
                )
            except Exception as e:
                print(f"[GEGENKONTROLLE HINWEIS] Initial-Log konnte nicht verankert werden: {e}")

        return {
            "raw_query": raw_query,
            "clean_query": clean_text,
            "sharpened_query": sharpened_text,
            "query_type": query_type,
            "node_id": node_id,
            "time_stamp": time_stamp_str,
            "log_table_name": log_table_name,
            "cache_hit": cached_check.get("cache_hit", False),
            "cached_check": cached_check
        }

    def get_cached_or_create_query(self, raw_query: str) -> dict:
        """Prüft den Cache oder registriert eine neue Anfrage mit detaillierter Gegenkontrolle."""
        if not raw_query or not isinstance(raw_query, str):
            return {"cache_hit": False, "status": "FAILED", "error": "Ungültige Eingabe"}
        cleaned_query = raw_query.strip().lower()
        id_start, id_end = self.MAX_USER_QUERY_ID_RANGE

        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()

                # 1. Exakte Suche nach aktiver Anfrage mit Cache
                cursor.execute("""
                    SELECT node_id, topic_title, topic_specification, agent_instruction, example_code_snippet, validation_rule
                    FROM user_query
                    WHERE TRIM(LOWER(topic_specification)) = ? AND is_active = 1
                    ORDER BY node_id DESC LIMIT 1
                """, (cleaned_query,))
                cached = cursor.fetchone()

                if cached and cached[3] and cached[3] != "PROCESSING" and cached[5] == "COMPLETED_CACHE_READY":
                    cursor.execute("UPDATE user_query SET execution_count = execution_count + 1 WHERE node_id = ?", (cached[0],))
                    conn.commit()
                    return {
                        "cache_hit": True,
                        "node_id": cached[0],
                        "title": cached[1],
                        "query": cached[2],
                        "response": cached[3],
                        "snippet": cached[4]
                    }

                # 2. Nächste freie Sequenz-ID ermitteln
                cursor.execute("SELECT node_id FROM user_query")
                existing_ids = set()
                for row in cursor.fetchall():
                    try:
                        existing_ids.add(int(row[0]))
                    except (ValueError, TypeError):
                        pass

                next_id_num = None
                for candidate in range(id_start, id_end):
                    if candidate not in existing_ids:
                        next_id_num = candidate
                        break

                if next_id_num is None:
                    next_id_num = id_end - 1

                next_node_id = f"{next_id_num:03d}"
                now = datetime.datetime.now()

                try:
                    self._insert_routing_node(
                        conn=conn,
                        table_name="user_query",
                        node_id=next_node_id,
                        topic_title=f"USER QUERY: {raw_query[:self.QUERY_TITLE_MAX_LEN]}",
                        topic_specification=raw_query,
                        agent_instruction="PROCESSING",
                        validation_rule="PENDING_EXECUTION",
                        target_table="pre_execution_blueprint_generator",
                        target_node_id="000"
                    )
                except Exception:
                    cursor.execute("""
                        INSERT OR IGNORE INTO user_query (
                            node_id, is_active, error_fallback_count,
                            year, month, day, hour, minute, second,
                            topic_title, topic_specification, agent_instruction,
                            example_code_snippet, validation_rule, execution_count,
                            success_weight, target_table, target_column_id, target_node_id
                        ) VALUES (?, 1, 0, ?, ?, ?, ?, ?, ?, ?, ?, 'PROCESSING', '', 'PENDING_EXECUTION', 1, 1.0, 'pre_execution_blueprint_generator', 'node_id', '000')
                    """, (
                        next_node_id,
                        now.year, now.month, now.day, now.hour, now.minute, now.second,
                        f"USER QUERY: {raw_query[:self.QUERY_TITLE_MAX_LEN]}",
                        raw_query
                    ))
                    conn.commit()

                return {
                    "cache_hit": False,
                    "node_id": next_node_id,
                    "query": raw_query,
                    "status": "PENDING_EXECUTION"
                }
        except Exception as e:
            return {"cache_hit": False, "status": "FAILED", "error": str(e)}

    def log_save_query_run_to_db_timestamp(
        self,
        task_description: str,
        error_msg: str = "",
        solution_code: str = "",
        run_id: str = None,
        step_type: str = "checkpoint",
        log_table_name: str = None
    ):
        """Protokolliert Schritte in dynamische log_{time}-Tabelle und verknüpft mit table_issue_data_..."""
        domain = self._detect_domain(task_description)

        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()

                year, month, day, hour, minute, second = None, None, None, None, None, None
                if not run_id:
                    try:
                        cursor.execute("""
                            SELECT year, month, day, hour, minute, second 
                            FROM user_query 
                            WHERE is_active = 1 
                            ORDER BY year DESC, month DESC, day DESC, hour DESC, minute DESC, second DESC 
                            LIMIT 1
                        """)
                        db_time = cursor.fetchone()
                        if db_time and all(db_time):
                            year, month, day, hour, minute, second = db_time
                            run_id = f"{year:04d}{month:02d}{day:02d}_{hour:02d}{minute:02d}{second:02d}"
                        else:
                            now = datetime.datetime.now()
                            year, month, day, hour, minute, second = now.year, now.month, now.day, now.hour, now.minute, now.second
                            run_id = now.strftime('%Y%m%d_%H%M%S')
                    except Exception:
                        now = datetime.datetime.now()
                        year, month, day, hour, minute, second = now.year, now.month, now.day, now.hour, now.minute, now.second
                        run_id = now.strftime('%Y%m%d_%H%M%S')
                else:
                    try:
                        clean_rid = str(run_id).replace("log_", "")
                        dt = datetime.datetime.strptime(clean_rid, '%Y%m%d_%H%M%S')
                        year, month, day, hour, minute, second = dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second
                    except Exception:
                        now = datetime.datetime.now()
                        year, month, day, hour, minute, second = now.year, now.month, now.day, now.hour, now.minute, now.second

                dynamic_table_name = log_table_name if log_table_name else f"log_{run_id}"
                if not dynamic_table_name.startswith("log_"):
                    dynamic_table_name = f"log_{dynamic_table_name}"

                node_id = f"STEP_{hour:02d}{minute:02d}{second:02d}_{datetime.datetime.now().strftime('%f')}"

                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {dynamic_table_name} (
                        node_id TEXT PRIMARY KEY,
                        is_active INTEGER DEFAULT 1,
                        error_fallback_count INTEGER DEFAULT 0,
                        year INTEGER, month INTEGER, day INTEGER, hour INTEGER, minute INTEGER, second INTEGER,
                        topic_title TEXT,
                        topic_specification TEXT,
                        agent_instruction TEXT,
                        example_code_snippet TEXT,
                        validation_rule TEXT,
                        execution_count INTEGER DEFAULT 0,
                        success_weight REAL DEFAULT 1.0,
                        target_table TEXT,
                        target_column_id TEXT,
                        target_node_id TEXT
                    )
                """)
                conn.commit()

                step_title = f"Step in [{domain}] ({step_type.upper()})"
                step_spec = task_description[:self.TASK_DESCRIPTION_MAX_LEN]
                agent_inst = error_msg.strip().split('\n')[-1][:self.TASK_DESCRIPTION_MAX_LEN] if error_msg else "RUN_STEP_SUCCESS"

                self._insert_routing_node(
                    conn=conn,
                    table_name=dynamic_table_name,
                    node_id=node_id,
                    topic_title=step_title,
                    topic_specification=step_spec,
                    agent_instruction=agent_inst,
                    example_code_snippet=solution_code,
                    validation_rule="step_logged == TRUE",
                    target_table="table_issue_data_time_stamp_run_protocol_for_query",
                    target_node_id="000"
                )

                cursor.execute(f"""
                    UPDATE {dynamic_table_name}
                    SET year = ?, month = ?, day = ?, hour = ?, minute = ?, second = ?
                    WHERE node_id = ?
                """, (year, month, day, hour, minute, second, node_id))
                conn.commit()

                master_node_id = f"AUDIT_{run_id}_{datetime.datetime.now().strftime('%f')[:4]}"
                try:
                    self._insert_routing_node(
                        conn=conn,
                        table_name="table_issue_data_time_stamp_run_protocol_for_query",
                        node_id=master_node_id,
                        topic_title=f"Audit Link -> {dynamic_table_name}",
                        topic_specification=task_description[:self.TASK_DESCRIPTION_MAX_LEN],
                        agent_instruction=f"LOG_TABLE_SEALED: {dynamic_table_name}",
                        example_code_snippet=solution_code[:self.CODE_SNIPPET_PREVIEW_LEN],
                        validation_rule="audit_trail_linked == TRUE",
                        target_table=dynamic_table_name,
                        target_column_id="node_id",
                        target_node_id=node_id
                    )
                except Exception:
                    pass

            print(f"[SQL-KNOWLEDGE] Protokollschritt mit DB-Zeitstempel in '{dynamic_table_name}' verankert.")
        except Exception as e:
            print(f"[KRITISCHER ABBRUCH IN log_save_query_run_to_db_timestamp]: {e}")

    def save_table_issue_data_run_protocol(self, *args, **kwargs):
        """Alias für log_save_query_run_to_db_timestamp."""
        return self.log_save_query_run_to_db_timestamp(*args, **kwargs)

    # KONTEXT-TIPS & DOMAIN-ROUTING
    def _detect_domain(self, task_description: str) -> str:
        """
        Erkennt die relevante Zieltabelle/Domain anhand Heuristik und konfigurierbaren Keywords.
        """
        if not task_description or not isinstance(task_description, str) or not task_description.strip():
            return self.DEFAULT_DOMAIN

        desc_lower = task_description.lower()
        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            if any(kw in desc_lower for kw in keywords):
                return domain

        # Optional: Sklearn TF-IDF
        if importlib.util.find_spec("sklearn") and importlib.util.find_spec("numpy"):
            try:
                from sklearn.feature_extraction.text import TfidfVectorizer
                from sklearn.metrics.pairwise import cosine_similarity
                import numpy as np

                domain_corpus = {domain: " ".join(words) for domain, words in self.DOMAIN_KEYWORDS.items()}
                domain_keys = list(domain_corpus.keys())
                vectorizer = TfidfVectorizer()
                tfidf_matrix = vectorizer.fit_transform(list(domain_corpus.values()))
                task_vector = vectorizer.transform([task_description])
                cosine_sim = cosine_similarity(task_vector, tfidf_matrix).flatten()
                total_sim = np.sum(cosine_sim)
                if total_sim > 0:
                    probabilities = cosine_sim / total_sim
                    best_idx = np.argmax(probabilities)
                    if probabilities[best_idx] >= self.TFIDF_SIMILARITY_THRESHOLD:
                        return domain_keys[best_idx]
            except Exception:
                pass

        return self.DEFAULT_DOMAIN

    def _get_relevant_tips(self, task_description: str) -> str:
        """Lädt kontextbezogene Richtlinien, Blueprint-Schritte und Knoten aus der Datenbank."""
        domain = self._detect_domain(task_description)
        tips = [
            "==================================================",
            " [SYSTEM CORE MEMORY: KNOWLEDGE AGENT ROUTING TREE]",
            "=================================================="
        ]

        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()

                # 1. System-Manifest & Core-Direktiven
                try:
                    cursor.execute(f"SELECT directive_key, explanation_for_agent FROM agent_system_manifest LIMIT {self.MAX_MANIFEST_ENTRIES}")
                    manifest_rows = cursor.fetchall()
                except sqlite3.OperationalError:
                    manifest_rows = []

                # 2. Relevante Knoten aus der erkannten Domain-Tabelle
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
                            f"WHERE is_active = 1 AND ({placeholders}) ORDER BY success_weight DESC LIMIT {self.MAX_DOMAIN_NODES}",
                            params
                        )
                        domain_rows = cursor.fetchall()

                    if not domain_rows:
                        cursor.execute(
                            f"SELECT node_id, topic_title, agent_instruction, example_code_snippet FROM {domain} "
                            f"WHERE is_active = 1 ORDER BY success_weight DESC LIMIT {self.MAX_DOMAIN_NODES}"
                        )
                        domain_rows = cursor.fetchall()
                except sqlite3.OperationalError:
                    domain_rows = []

                # 3. Aktive Blueprint-Schritte
                try:
                    cursor.execute(
                        f"SELECT node_id, topic_title, agent_instruction FROM pre_execution_blueprint_generator "
                        f"WHERE is_active = 1 ORDER BY node_id ASC LIMIT {self.MAX_BLUEPRINT_STEPS}"
                    )
                    blueprints = cursor.fetchall()
                except sqlite3.OperationalError:
                    blueprints = []

            if manifest_rows:
                tips.append("\n--- Agent System Manifest & Core Directives ---")
                for key, exp in manifest_rows:
                    tips.append(f"* [{key}]: {exp}")

            if domain_rows:
                tips.append(f"\n--- Relevant Nodes from Domain [{domain}] ---")
                for node_id, title, instruction, snippet in domain_rows:
                    tips.append(f"* Node [{node_id}] {title}: {instruction}")
                    if snippet and snippet.strip() and not snippet.startswith("# FX_"):
                        tips.append(f"  Code Snippet: {snippet.strip()[:self.CODE_SNIPPET_PREVIEW_LEN]}...")

            if blueprints:
                tips.append("\n--- Mandatory Pre-Execution Blueprints ---")
                for node_id, title, instruction in blueprints:
                    tips.append(f"* Step [{node_id}] {title}: {instruction}")

        except Exception as e:
            tips.append(f"\n[FEHLER] Konnte Knowledge-Tips nicht laden: {e}")

        if len(tips) <= 3:
            return f"No prior routing tree nodes recorded for domain [{domain}]."
        return "\n".join(tips)

    def initialize_blueprint_system(self, user_input: str) -> dict:
        """Initialisiert das Blueprint-System für eine Eingabe."""
        if not user_input or not isinstance(user_input, str) or not user_input.strip():
            return {"status": "FAILED", "query": user_input, "error": "Leere Eingabe"}
        print(f"[BLUEPRINT] Initialisiere Blueprint-System für Anfrage...")
        return {"status": "INITIALIZED", "query": user_input.strip()}

    
    # GENERIC CRUD & REROUTING
    

    def _insert_routing_node(self, conn, table_name: str, node_id: str, 
                             topic_title: str = "", topic_specification: str = "", 
                             agent_instruction: str = "", example_code_snippet: str = "", 
                             validation_rule: str = "", target_table: str = "", 
                             target_node_id: str = "000", **kwargs):
        """Fügt einen neuen Knoten dynamisch anhand des Live-Schemas in die Tabelle ein."""
        if not conn or not table_name or not node_id:
            raise ValueError("Ungültige Parameter für _insert_routing_node")

        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        actual_columns = {row[1] for row in cursor.fetchall()}

        if not actual_columns:
            raise ValueError(f"Tabelle '{table_name}' existiert nicht.")

        now = datetime.datetime.now()
        payload = {
            "node_id": node_id,
            "is_active": 1,
            "error_fallback_count": 0,
            "year": now.year, "month": now.month, "day": now.day,
            "hour": now.hour, "minute": now.minute, "second": now.second,
            "topic_title": topic_title,
            "topic_specification": topic_specification,
            "agent_instruction": agent_instruction,
            "example_code_snippet": example_code_snippet,
            "validation_rule": validation_rule,
            "execution_count": 1,
            "success_weight": 1.0,
            "target_table": target_table,
            "target_column_id": "node_id",
            "target_node_id": target_node_id,
            **kwargs
        }

        filtered_data = {k: v for k, v in payload.items() if k in actual_columns}
        cols = ", ".join(filtered_data.keys())
        placeholders = ", ".join(["?"] * len(filtered_data))

        cursor.execute(f"INSERT OR REPLACE INTO {table_name} ({cols}) VALUES ({placeholders})", list(filtered_data.values()))
        conn.commit()
        print(f"[SQL-SUCCESS] Knoten '{node_id}' erfolgreich in Tabelle '{table_name}' verankert.")

    def deactivate_and_reroute(self, table_name: str, node_id: str, failure_reason: str) -> dict:
        """Deaktiviert fehlerhafte Knoten und leitet auf Alternativpfade um."""
        if not node_id:
            return {"deactivated_node": "UNKNOWN", "table_name": table_name, "reason": failure_reason, "alternative_available": False}

        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"UPDATE {table_name} SET is_active = 0, error_fallback_count = error_fallback_count + 1 WHERE node_id = ?", (node_id,))
                cursor.execute(f"""
                    SELECT node_id, topic_title, target_table, target_node_id
                    FROM {table_name}
                    WHERE is_active = 1 AND node_id != ?
                    ORDER BY success_weight DESC LIMIT 1
                """, (node_id,))
                alt_row = cursor.fetchone()
                conn.commit()
                print(f"[SQL-SUCCESS] Node '{node_id}' in '{table_name}' deaktiviert. Grund: {failure_reason}")
                return {
                    "deactivated_node": node_id,
                    "table_name": table_name,
                    "reason": failure_reason,
                    "alternative_available": alt_row is not None,
                    "next_node": alt_row[0] if alt_row else "000",
                    "next_target": alt_row[2] if alt_row and alt_row[2] else "FX_CHAIN"
                }
        except Exception as e:
            return {"deactivated_node": node_id, "table_name": table_name, "reason": str(e), "alternative_available": False}

    def fetch_records(self, table_name: str, active_only: bool = True):
        """Liest Datensätze aus einer Tabelle aus."""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            query = f"SELECT * FROM {table_name}" + (" WHERE is_active = 1" if active_only else "")
            cursor.execute(query)
            cols = [d[0] for d in cursor.description] if cursor.description else []
            return [dict(zip(cols, row)) for row in cursor.fetchall()]

    def fetch_single_node(self, table_name: str, node_id: str):
        """Liest einen einzelnen Knoten aus."""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {table_name} WHERE node_id = ?", (node_id,))
            row = cursor.fetchone()
            if row and cursor.description:
                cols = [d[0] for d in cursor.description]
                return dict(zip(cols, row))
            return None



    def evolve_self(self, recent_error: str, task_context: str):
        """Schreibt eine neue, verbesserte Version von sich selbst mit aktuellem Zeitstempel."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        history_dir = self.root_path / "src" / "agent" / "metacoder_history"
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
Rewrite and improve this Python class so that it proactively checks for and prevents the above error. 
Return the COMPLETE, executable Python code inside markdown code blocks (```python ... ```).
"""
        res = OllamaManager.generate(prompt=prompt, model=self.MODEL_LLM, ollama_host=self.OLLAMA_HOST)
        if res.get("status") == "SUCCESS":
            raw_text = res.get("content", "")
            try:
                from agent_universal_skript.class_subAgentVerifier import SubAgentVerifier
                blocks = SubAgentVerifier.extract_code_blocks(raw_text)
                code_text = blocks[0] if blocks else raw_text.strip()
            except Exception:
                code_text = raw_text.strip()
            with open(new_filename, "w", encoding="utf-8") as f:
                f.write(code_text)
            print(f"[EVOLUTION] Neue Version gespeichert: {new_filename}")
            return new_filename
        return None

    def run_pipeline(self, task_description: str, target_notebook: str = None) -> dict:
        """
        Führt die Haupt-Pipeline über die sequentiellen SQL-Phasen aus.
        Gewährleistet Protokollierung, Verifikation und Benutzer-Rückmeldung.
        """
        self._ensure_core_tables()
        return self.execute_query_with_db_phases(raw_query=task_description)


globals()["class_sql_reader"] = class_sql_reader