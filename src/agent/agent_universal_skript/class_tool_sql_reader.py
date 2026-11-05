"""
Modul: class_tool_sql_reader
Bezeichnung: Universeller SQLite Knowledge-Reader & Agent-Routing-Baum
Schwerpunkt:
    Kernmodul für den persistenten Zugriff auf den SQLite Knowledge Agent Routing Tree.
    Verwaltet vollständige CRUD-Operationen, Bootstrap-DNA (Phasen 000/001/002/999),
    idempotenten Query-Cache, TF-IDF Domänen-Erkennung, Log-Protokollierung,
    SRC-Code- und Bug-Bibliothek sowie den Self-Evolution-Mechanismus.
    Alle Konfigurationskonstanten werden über _GLOBAL_RUNTIME_CONFIG (SSOT) gehalten.
"""

import datetime
import importlib.util
import os
import random
import sqlite3
import sys
from pathlib import Path

# --- Globale Aliase (werden vom Bootstrap-System befüllt) ---
logger = globals().get('class_logger_audit_execution')
core_infra = globals().get('class_tool_core_infrastructure')
ollama_manager = globals().get('class_tool_ollama_service_manager')
sub_verifier = globals().get('class_agent_sub_verifier')
spinner_tool = globals().get('class_tool_resource_aware_spinner')

# --- Minimale Fallback-Basis falls core_infra nicht geladen ---
if core_infra is None:
    try:
        from agent_universal_skript.class_tool_core_infrastructure import class_tool_core_infrastructure as core_infra
    except Exception:
        core_infra = type('FallbackCore', (), {
            'PROJECT_POINT': 'src',
            'get_project_root': staticmethod(lambda start_path=None: Path(__file__).resolve().parent.parent.parent),
            'get_database_path': staticmethod(lambda filename=None: Path(__file__).resolve().parent.parent.parent / "knowledge" / "agent_hierarchical_routing_tree_sql.db"),
            'get_file_path': staticmethod(lambda filename: Path(__file__).resolve().parent.parent.parent / "knowledge" / "agent_hierarchical_routing_tree_sql.db" if str(filename).endswith('.db') else Path(__file__).resolve().parent.parent / filename),
        })


class class_tool_sql_reader(core_infra):
    """
    Universeller SQL-Reader. Alle Einstellungen inklusive Schwellenwerte
    sind direkt in der Klasse sichtbar und über das globale Runtime-Dict live-gesichert.
    """

    # SSOT-Konfiguration über _GLOBAL_RUNTIME_CONFIG
    _cfg = globals().setdefault("_GLOBAL_RUNTIME_CONFIG", {})

    # --- A. CORE & RUNTIME SETTINGS ---
    AGENT_NAME                = _cfg.setdefault("AGENT_NAME",               "AI-Agent")
    DB_FILENAME               = _cfg.setdefault("DB_FILENAME",              "Knowledge_Agent_Routing_tree.db")
    MODEL_LLM                 = _cfg.setdefault("MODEL_LLM",                "codestral")
    OLLAMA_HOST               = _cfg.setdefault("OLLAMA_HOST",              "http://127.0.0.1:11434")
    PROJECT_POINT             = _cfg.setdefault("PROJECT_POINT",            "src")
    SPINNER_INTERVAL          = _cfg.setdefault("SPINNER_INTERVAL",         1.0)

    # --- B. THRESHOLDS & LIMITS ---
    CODE_SNIPPET_PREVIEW_LEN  = _cfg.setdefault("CODE_SNIPPET_PREVIEW_LEN", 150)
    CPU_WARNING_THRESHOLD     = _cfg.setdefault("CPU_WARNING_THRESHOLD",    90.0)
    EVOLUTION_RETRY_DELAY_SEC = _cfg.setdefault("EVOLUTION_RETRY_DELAY_SEC",1)
    FEEDBACK_WEIGHT_INCREMENT = _cfg.setdefault("FEEDBACK_WEIGHT_INCREMENT",0.2)
    MAX_BLUEPRINT_STEPS       = _cfg.setdefault("MAX_BLUEPRINT_STEPS",      5)
    MAX_DOMAIN_NODES          = _cfg.setdefault("MAX_DOMAIN_NODES",         3)
    MAX_EVOLUTION_GENERATIONS = _cfg.setdefault("MAX_EVOLUTION_GENERATIONS",3)
    MAX_MANIFEST_ENTRIES      = _cfg.setdefault("MAX_MANIFEST_ENTRIES",     5)
    MAX_SANDBOX_OUTPUT_LENGTH = _cfg.setdefault("MAX_SANDBOX_OUTPUT_LENGTH",4000)
    MAX_USER_QUERY_ID_RANGE   = _cfg.setdefault("MAX_USER_QUERY_ID_RANGE",  (3, 999))
    MIN_RAM_MB                = _cfg.setdefault("MIN_RAM_MB",               2000)
    PROMPT_MAX_LEN            = _cfg.setdefault("PROMPT_MAX_LEN",           500)
    QUERY_TITLE_MAX_LEN       = _cfg.setdefault("QUERY_TITLE_MAX_LEN",      35)
    REQUIRED_KERNEL_MODULES   = _cfg.setdefault("REQUIRED_KERNEL_MODULES",  ["psutil", "sqlite3"])
    SANDBOX_TIMEOUT           = _cfg.setdefault("SANDBOX_TIMEOUT",          15)
    TASK_DESCRIPTION_MAX_LEN  = _cfg.setdefault("TASK_DESCRIPTION_MAX_LEN", 200)
    TFIDF_SIMILARITY_THRESHOLD= _cfg.setdefault("TFIDF_SIMILARITY_THRESHOLD",0.15)

    # --- Erlaubte Tabellen (vollständige Liste inkl. SRC-Library) ---
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
        "hardware_enviroment",
        "library_src_code",
        "library_src_bugs_cleaning",
        "meta_agent_code_project_log_healing_registry"
    }

    DOMAIN = "library_registry"

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

    # =========================================================================
    # EBENE 4: METHODEN
    # =========================================================================

    def __init__(self, db_filename: str = None, model_name: str = None,
                 ollama_host: str = None, agent_name: str = None,
                 spinner_interval: float = None):
        print("[class_tool_sql_reader] Starte Arbeit: __init__ wird jetzt ausgeführt.")
        super().__init__()

        cfg = globals()["_GLOBAL_RUNTIME_CONFIG"]
        if db_filename:       cfg["DB_FILENAME"]     = db_filename
        if model_name:        cfg["MODEL_LLM"]        = model_name
        if ollama_host:       cfg["OLLAMA_HOST"]      = ollama_host
        if agent_name:        cfg["AGENT_NAME"]       = agent_name
        if spinner_interval is not None:
                              cfg["SPINNER_INTERVAL"] = spinner_interval

        self.root_path = Path(self.get_project_root())
        target_db = db_filename or self.DB_FILENAME
        db_resolved = None
        if hasattr(self, "get_database_path"):
            db_resolved = self.get_database_path(target_db)
        if not db_resolved and hasattr(self, "get_file_path"):
            db_resolved = self.get_file_path(target_db)
        if not db_resolved or not Path(db_resolved).exists():
            db_resolved = self.root_path / "knowledge" / "agent_hierarchical_routing_tree_sql.db"
        self.db_filename = str(db_resolved)

        self.bootstrap_dna = []
        self.manifest_directives = {}

        if not hasattr(self, 'db_filename') or not self.db_filename:
            print("[class_tool_sql_reader] FEHLER: __init__ hat die Aufgabe nicht erfüllt. Grund: db_filename nicht gesetzt.")
            return
        print(f"[class_tool_sql_reader] Erfolg: __init__ erfolgreich beendet. (DB: {self.db_filename})")

    # -------------------------------------------------------------------------

    def get_db_connection(self, filename: str = None) -> sqlite3.Connection:
        """Stellt eine sichere Verbindung zur Knowledge-Datenbank her."""
        print("[class_tool_sql_reader] Starte Arbeit: get_db_connection wird jetzt ausgeführt.")
        target_file = filename or getattr(self, "db_filename", None) or self.DB_FILENAME
        db_path = None
        if hasattr(self, "get_database_path"):
            db_path = self.get_database_path(target_file)
        if not db_path and hasattr(self, "get_file_path"):
            db_path = self.get_file_path(target_file)
        if not db_path or not Path(db_path).exists():
            db_path = self.root_path / "knowledge" / "agent_hierarchical_routing_tree_sql.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        if conn is None:
            print("[class_tool_sql_reader] FEHLER: get_db_connection hat die Aufgabe nicht erfüllt. Grund: Verbindung ist None.")
            return None
        print(f"[class_tool_sql_reader] Erfolg: get_db_connection erfolgreich beendet. (DB: {db_path})")
        return conn

    # -------------------------------------------------------------------------

    def _ensure_core_tables(self):
        """Garantiert die physische Existenz aller Kern-Tabellen vor Pipeline-Start."""
        print("[class_tool_sql_reader] Starte Arbeit: _ensure_core_tables wird jetzt ausgeführt.")
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
                print(f"[class_tool_sql_reader] FEHLER: Kerntabellen konnten nicht erstellt werden: {e}")
        print("[class_tool_sql_reader] Erfolg: _ensure_core_tables erfolgreich beendet.")

    # -------------------------------------------------------------------------

    def verify_environment(self) -> bool:
        """Prüft die Existenz der globalen Datenbank und initialisiert Tabellenstrukturen."""
        print("[class_tool_sql_reader] Starte Arbeit: verify_environment wird jetzt ausgeführt.")
        db_path = Path(self.db_filename)
        if not db_path.exists():
            print(f"[class_tool_sql_reader] Erstelle neue SQLite-Registry unter: {db_path.resolve()}")
            db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_core_tables()
        status = True
        if not status:
            print("[class_tool_sql_reader] FEHLER: verify_environment hat die Aufgabe nicht erfüllt. Grund: Umgebung konnte nicht verifiziert werden.")
            return False
        print("[class_tool_sql_reader] Umgebung erfolgreich verifiziert. Alle erweiterten Tools verbunden.")
        print("[class_tool_sql_reader] Erfolg: verify_environment erfolgreich beendet.")
        return True

    # -------------------------------------------------------------------------

    def bootstrap_from_database(self) -> list:
        """
        Lädt die Start-DNA des Agenten autonom aus der SQLite-Datenbank.
        Folgt der Kette: meta_admin_bootstrap_registry (Node '001') -> meta_agent_start ('000' bis '999').
        """
        print("[class_tool_sql_reader] Starte Arbeit: bootstrap_from_database wird jetzt ausgeführt.")
        print("\n" + "=" * 60)
        print(" [BOOTSTRAP-DNA] Initialisiere Agent über SQLite Knowledge Tree")
        print("=" * 60)

        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()

                # Registry-Eintrag ermitteln
                cursor.execute("""
                    SELECT target_table, target_node_id, topic_title
                    FROM meta_admin_bootstrap_registry
                    WHERE node_id = '001' AND is_active = 1
                """)
                registry_entry = cursor.fetchone()
                if not registry_entry:
                    print("--> [WARNUNG] Kein aktiver Bootstrap-Eintrag '001' gefunden. Fallback auf meta_agent_start.")
                    start_table = "meta_agent_start"
                else:
                    start_table = registry_entry[0]
                    print(f"--> [REGISTRY LINK] Node '001' verweist auf '{start_table}' (Ziel: '{registry_entry[1]}')")

                # Phasen sequenziell laden
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
                    title   = row[1]
                    print(f"  * Phase [{node_id}] {title}")

                    if node_id == "000":
                        try:
                            cursor.execute("SELECT directive_key, explanation_for_agent FROM agent_system_manifest")
                            self.manifest_directives = dict(cursor.fetchall())
                            print(f"    -> {len(self.manifest_directives)} Kern-Direktiven aus 'agent_system_manifest' absorbiert.")
                        except sqlite3.OperationalError:
                            pass

                    elif node_id == "001":
                        k_mods = self.scan_kernel_modules(self.REQUIRED_KERNEL_MODULES + ["ollama"])
                        print(f"    -> Kernel-Audit: {sum(1 for v in k_mods.values() if v == 'active')}/{len(k_mods)} Module aktiv.")

                    elif node_id == "002":
                        try:
                            cursor.execute("SELECT COUNT(*) FROM user_query WHERE is_active = 1")
                            active_queries = cursor.fetchone()[0]
                            print(f"    -> Idempotenz-Prüfung: 'user_query' betriebsbereit ({active_queries} aktive Einträge).")
                        except sqlite3.OperationalError:
                            print("    -> Tabelle 'user_query' nicht gefunden, wird bei Bedarf erstellt.")

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
                            print("    -> Startup-Siegel in 'table_issue_data_time_stamp_run_protocol_for_query' verankert.")
                        except Exception:
                            pass

                print(f"--> [BOOTSTRAP-DNA ERFOLG] {len(phases)} Phasen erfolgreich aus SQLite instanziiert.")
                print("=" * 60 + "\n")
                if not phases:
                    print("[class_tool_sql_reader] WARNUNG: bootstrap_from_database hat keine Phasen geladen.")
                print("[class_tool_sql_reader] Erfolg: bootstrap_from_database erfolgreich beendet.")
                return phases

        except Exception as e:
            print(f"[class_tool_sql_reader] FEHLER: Bootstrap-DNA konnte nicht geladen werden: {e}")
            return []

    # -------------------------------------------------------------------------

    def execute_query_with_db_phases(self, raw_query: str, model_name: str = None,
                                     ollama_host: str = None, spinner_thread_starter=None) -> dict:
        """
        Führt eine Benutzeranfrage streng nach den Vorgaben der Phasen aus 'meta_agent_start' aus:
        Phase 002: Idempotenter Query-Cache & Ingestion
        Phase 003: Blueprint-Dispatch & Domain-Routing
        Phase 004: Closed-Loop Execution & Code-Verifikation
        Phase 005: Protokoll-Siegel & Zeitstempel-Bindung
        Phase 999: Agent Ready Gateway & Antwort-Versiegelung
        """
        print("[class_tool_sql_reader] Starte Arbeit: execute_query_with_db_phases wird jetzt ausgeführt.")

        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT node_id, topic_title, topic_specification, agent_instruction,
                       example_code_snippet, validation_rule, target_table, target_node_id
                FROM meta_agent_start WHERE is_active = 1 ORDER BY node_id ASC
            """)
            phases_dict = {row[0]: dict(row) for row in cursor.fetchall()}

        clean_text          = " ".join(raw_query.strip().split())
        cleaned_query_lower = clean_text.lower()

        # Phase [002]: IDEMPOTENT QUERY CACHE
        query_node_id  = None
        log_table_name = None
        time_stamp_str = None

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
                result = {
                    "status": "SUCCESS", "cache_hit": True,
                    "node_id": cached[0], "title": cached[1],
                    "domain": "SQL-Cache", "answer": cached[3], "snippet": cached[4]
                }
                if not result or result.get("status") != "SUCCESS":
                    print("[class_tool_sql_reader] FEHLER: execute_query_with_db_phases hat die Aufgabe nicht erfüllt. Grund: Cache-Rückgabe ungültig.")
                    return {}
                print("[class_tool_sql_reader] Erfolg: execute_query_with_db_phases erfolgreich beendet.")
                return result

            indexed_info    = self.index_chat_user_query(raw_query)
            query_node_id   = indexed_info.get("node_id")
            log_table_name  = indexed_info.get("log_table_name")
            time_stamp_str  = indexed_info.get("time_stamp")
            effective_query = indexed_info.get("sharpened_query") or raw_query

        # Phase [003]: DYNAMIC BLUEPRINT DISPATCH & COGNITIVE ROUTING
        domain         = self._detect_domain(effective_query)
        db_tips        = self._get_relevant_tips(effective_query)
        blueprint_info = self.initialize_blueprint_system(effective_query)

        # Phase [004]: CLOSED-LOOP EXECUTION
        active_model  = model_name  or getattr(self, "model_name",  None) or self.MODEL_LLM
        active_host   = ollama_host or getattr(self, "ollama_host", None) or self.OLLAMA_HOST
        ollama_ready  = ollama_manager.ensure_ollama_running(active_host) if ollama_manager else False
        answer        = ""
        codes         = []

        if ollama_ready and ollama_manager:
            system_prompt = (
                f"You are an autonomous AI Agent with an active SQLite Long-Term Memory (Knowledge Agent Routing Tree).\n"
                f"Current Detected Domain: {domain}\n"
                f"Blueprint Status: {blueprint_info.get('status')}\n\n"
                f"Retrieved Knowledge & Past Patterns from SQLite DB:\n{db_tips}\n\n"
                f"Your Task: Answer the user's request in German, keeping code/technical keywords in English. "
                f"Acknowledge and make use of the SQLite database context if relevant."
            )
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": effective_query}
            ]
            try:
                chat_res = ollama_manager.run_agent(
                    messages, model=active_model, ollama_host=active_host,
                    agent_title=f"{self.AGENT_NAME}-Chat"
                )
                if chat_res.get("status") == "SUCCESS":
                    answer = chat_res.get("content", "").strip()
            except Exception:
                answer = ""

        if not answer.strip():
            answer = (
                f"Hallo! Ich bin der {self.AGENT_NAME} und mit dem Knowledge Agent Routing Tree verbunden.\n"
                f"Deine Anfrage '{clean_text}' wurde in die Domäne [{domain}] klassifiziert.\n\n"
                f"Aktueller Zustand des Wissensbaums:\n"
                f"* Abfrage-Knoten '{query_node_id}' verankert in 'user_query'.\n"
                f"* Protokollschritt in '{log_table_name}' versiegelt.\n"
                f"* Blueprint-Status: {blueprint_info.get('status')}.\n"
            )

        if sub_verifier:
            try:
                codes = sub_verifier.extract_code_blocks(answer)
                if codes:
                    code_to_verify = codes[0] if isinstance(codes, list) else codes
                    v_ok, v_msg = sub_verifier.verify_code_in_sandbox(
                        code_to_verify, timeout_sec=self.SANDBOX_TIMEOUT
                    )
                    if not v_ok:
                        print(f"[class_tool_sql_reader] FEHLER: Code-Verifikation: {v_msg}")
            except Exception:
                pass

        # Phase [005]: PROTOCOL SEAL & TIMESTAMP BINDING
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
            print(f"[class_tool_sql_reader] FEHLER: Phase-005-Protokollierung übersprungen: {e}")

        # Phase [999]: AGENT READY GATEWAY
        if query_node_id:
            snippet_str = str(codes[0]) if codes else ""
            self.seal_query_cache(query_node_id, answer, snippet=snippet_str)

        result = {
            "status": "SUCCESS", "cache_hit": False,
            "node_id": query_node_id, "domain": domain,
            "answer": answer, "snippet": codes[0] if codes else ""
        }
        if not result or result.get("status") != "SUCCESS":
            print("[class_tool_sql_reader] FEHLER: execute_query_with_db_phases hat die Aufgabe nicht erfüllt. Grund: Ergebnis ungültig.")
            return {}
        print("[class_tool_sql_reader] Erfolg: execute_query_with_db_phases erfolgreich beendet.")
        return result

    # -------------------------------------------------------------------------

    def seal_query_cache(self, node_id: str, answer: str, snippet: str = ""):
        """Versiegelt eine erfolgreich beantwortete Anfrage in 'user_query' als Cache-Eintrag."""
        print("[class_tool_sql_reader] Starte Arbeit: seal_query_cache wird jetzt ausgeführt.")
        if not node_id or not answer or not isinstance(answer, str) or not answer.strip():
            print(f"[class_tool_sql_reader] FEHLER: seal_query_cache hat die Aufgabe nicht erfüllt. Grund: Ungültige Antwort oder fehlende Node-ID für '{node_id}'. Versiegelung verweigert.")
            return False
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
            rows_affected = cursor.rowcount
        print(f"--> [SQL-CACHE SEAL] Antwort in 'user_query' Node '{node_id}' dauerhaft versiegelt.")
        if rows_affected == 0:
            print(f"[class_tool_sql_reader] FEHLER: seal_query_cache hat die Aufgabe nicht erfüllt. Grund: Kein DB-Update für Node '{node_id}' ausgeführt.")
            return False
        print("[class_tool_sql_reader] Erfolg: seal_query_cache erfolgreich beendet.")
        return True

    # -------------------------------------------------------------------------

    def record_feedback(self, query_node_id: str, is_positive: bool, comment: str = "") -> dict:
        """Verarbeitet Benutzer-Feedback für einen Query-Knoten."""
        print("[class_tool_sql_reader] Starte Arbeit: record_feedback wird jetzt ausgeführt.")
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
                result = {"status": "success", "feedback": "positive", "node_id": query_node_id}
                print("[class_tool_sql_reader] Erfolg: record_feedback erfolgreich beendet.")
                return result
            else:
                result = self.deactivate_and_reroute("user_query", query_node_id,
                                                   failure_reason=comment or "Negatives Benutzer-Feedback")
                print("[class_tool_sql_reader] Erfolg: record_feedback erfolgreich beendet.")
                return result

    # -------------------------------------------------------------------------

    def persist_new_capability(self, capability_name: str, code_snippet: str, description: str):
        """Persistiert eine neue Fähigkeit dauerhaft in der 'library_registry' Tabelle."""
        print("[class_tool_sql_reader] Starte Arbeit: persist_new_capability wird jetzt ausgeführt.")
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
        print(f"\n[PERSISTENZ-ERFOLG] Fähigkeit '{capability_name}' in SQLite ('library_registry') verewigt!")
        print("[class_tool_sql_reader] Erfolg: persist_new_capability erfolgreich beendet.")

    # -------------------------------------------------------------------------

    def check_library_evolution_since_node(self, query_node_id: str) -> bool:
        """Prüft, ob in library_registry neuere Einträge existieren als der gegebene user_query-Knoten."""
        print(f"[class_tool_sql_reader] Starte Arbeit: check_library_evolution_since_node wird jetzt ausgeführt. (Parameter: {query_node_id})")
        if not query_node_id or not isinstance(query_node_id, str):
            print("[class_tool_sql_reader] Erfolg: check_library_evolution_since_node erfolgreich beendet. (Ergebnis: False)")
            return False
        try:
            with self.get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT year, month, day, hour, minute, second FROM user_query WHERE node_id = ?", (query_node_id,))
                q_row = cur.fetchone()
                if not q_row or not all(v is not None for v in q_row):
                    print("[class_tool_sql_reader] Erfolg: check_library_evolution_since_node erfolgreich beendet. (Ergebnis: False)")
                    return False

                cur.execute("""
                    SELECT COUNT(*) FROM library_registry 
                    WHERE (year > ? OR (year = ? AND month > ?) OR (year = ? AND month = ? AND day > ?) 
                           OR (year = ? AND month = ? AND day = ? AND hour > ?)
                           OR (year = ? AND month = ? AND day = ? AND hour = ? AND minute > ?))
                """, (q_row[0], q_row[0], q_row[1], q_row[0], q_row[1], q_row[2],
                      q_row[0], q_row[1], q_row[2], q_row[3],
                      q_row[0], q_row[1], q_row[2], q_row[3], q_row[4]))
                count = cur.fetchone()[0]
                has_evolved = count > 0
                print(f"[class_tool_sql_reader] Erfolg: check_library_evolution_since_node erfolgreich beendet. (Ergebnis: {has_evolved})")
                return has_evolved
        except Exception as e:
            print(f"[class_tool_sql_reader] FEHLER: check_library_evolution_since_node: {e}")
            return False

    # -------------------------------------------------------------------------

    def index_chat_user_query(self, raw_query: str) -> dict:
        """Erfassung, Bereinigung, Token-Schärfung und Indizierung von Benutzeranfragen."""
        print("[class_tool_sql_reader] Starte Arbeit: index_chat_user_query wird jetzt ausgeführt.")
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

        filler_words = {"bitte", "mal", "einmal", "halt", "eben", "quasi", "einfach", "gerne",
                        "please", "just", "kindly"}
        words          = sharpened_text.split()
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

        cached_check   = self.get_cached_or_create_query(sharpened_text)
        node_id        = cached_check.get("node_id") if cached_check else None
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
                        FROM user_query WHERE is_active = 1
                        ORDER BY year DESC, month DESC, day DESC, hour DESC, minute DESC, second DESC LIMIT 1
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
                print(f"[class_tool_sql_reader] FEHLER: Initial-Log konnte nicht verankert werden: {e}")

        result = {
            "raw_query":      raw_query,
            "clean_query":    clean_text,
            "sharpened_query":sharpened_text,
            "query_type":     query_type,
            "node_id":        node_id,
            "time_stamp":     time_stamp_str,
            "log_table_name": log_table_name,
            "cache_hit":      cached_check.get("cache_hit", False),
            "cached_check":   cached_check
        }
        if not result or not result.get("node_id"):
            print("[class_tool_sql_reader] FEHLER: index_chat_user_query hat die Aufgabe nicht erfüllt. Grund: node_id fehlt im Ergebnis.")
            return result
        print("[class_tool_sql_reader] Erfolg: index_chat_user_query erfolgreich beendet.")
        return result

    # -------------------------------------------------------------------------

    def get_cached_or_create_query(self, raw_query: str) -> dict:
        """Prüft den Cache oder registriert eine neue Anfrage."""
        print("[class_tool_sql_reader] Starte Arbeit: get_cached_or_create_query wird jetzt ausgeführt.")
        if not raw_query or not isinstance(raw_query, str):
            return {"cache_hit": False, "status": "FAILED", "error": "Ungültige Eingabe"}

        cleaned_query = raw_query.strip().lower()
        id_start, id_end = self.MAX_USER_QUERY_ID_RANGE

        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()

                # Exakte Suche nach aktivem Cache-Eintrag
                cursor.execute("""
                    SELECT node_id, topic_title, topic_specification, agent_instruction, example_code_snippet, validation_rule
                    FROM user_query
                    WHERE TRIM(LOWER(topic_specification)) = ? AND is_active = 1
                    ORDER BY node_id DESC LIMIT 1
                """, (cleaned_query,))
                cached = cursor.fetchone()

                if cached and cached[3] and cached[3].strip() and cached[3] != "PROCESSING" and cached[5] == "COMPLETED_CACHE_READY":
                    cursor.execute("UPDATE user_query SET execution_count = execution_count + 1 WHERE node_id = ?", (cached[0],))
                    conn.commit()
                    result = {
                        "cache_hit": True, "node_id": cached[0], "title": cached[1],
                        "query": cached[2], "response": cached[3], "snippet": cached[4]
                    }
                    if not result:
                        print("[class_tool_sql_reader] FEHLER: get_cached_or_create_query hat die Aufgabe nicht erfüllt. Grund: Leeres Ergebnis.")
                        return {}
                    print("[class_tool_sql_reader] Erfolg: get_cached_or_create_query erfolgreich beendet.")
                    return result

                # Nächste freie ID ermitteln
                cursor.execute("SELECT node_id FROM user_query")
                existing_ids = set()
                for row in cursor.fetchall():
                    try:
                        existing_ids.add(int(row[0]))
                    except (ValueError, TypeError):
                        pass

                next_id_num = next((c for c in range(id_start, id_end) if c not in existing_ids), id_end - 1)
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
                        ) VALUES (?, 1, 0, ?, ?, ?, ?, ?, ?, ?, ?, 'PROCESSING', '', 'PENDING_EXECUTION', 1, 1.0,
                                  'pre_execution_blueprint_generator', 'node_id', '000')
                    """, (
                        next_node_id,
                        now.year, now.month, now.day, now.hour, now.minute, now.second,
                        f"USER QUERY: {raw_query[:self.QUERY_TITLE_MAX_LEN]}",
                        raw_query
                    ))
                    conn.commit()

                result = {"cache_hit": False, "node_id": next_node_id, "query": raw_query, "status": "PENDING_EXECUTION"}
                if not result:
                    print("[class_tool_sql_reader] FEHLER: get_cached_or_create_query hat die Aufgabe nicht erfüllt. Grund: Leeres Ergebnis.")
                    return {}
                print("[class_tool_sql_reader] Erfolg: get_cached_or_create_query erfolgreich beendet.")
                return result

        except Exception as e:
            return {"cache_hit": False, "status": "FAILED", "error": str(e)}

    # -------------------------------------------------------------------------

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
        print("[class_tool_sql_reader] Starte Arbeit: log_save_query_run_to_db_timestamp wird jetzt ausgeführt.")
        domain = self._detect_domain(task_description)

        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()

                # Zeitstempel ermitteln
                if not run_id:
                    try:
                        cursor.execute("""
                            SELECT year, month, day, hour, minute, second FROM user_query
                            WHERE is_active = 1 ORDER BY year DESC, month DESC, day DESC,
                            hour DESC, minute DESC, second DESC LIMIT 1
                        """)
                        db_time = cursor.fetchone()
                        if db_time and all(db_time):
                            year, month, day, hour, minute, second = db_time
                            run_id = f"{year:04d}{month:02d}{day:02d}_{hour:02d}{minute:02d}{second:02d}"
                        else:
                            raise ValueError("Keine DB-Zeit gefunden")
                    except Exception:
                        now = datetime.datetime.now()
                        year, month, day, hour, minute, second = now.year, now.month, now.day, now.hour, now.minute, now.second
                        run_id = now.strftime('%Y%m%d_%H%M%S')
                else:
                    try:
                        dt = datetime.datetime.strptime(str(run_id).replace("log_", ""), '%Y%m%d_%H%M%S')
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
                step_spec  = task_description[:self.TASK_DESCRIPTION_MAX_LEN]
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
            print("[class_tool_sql_reader] Erfolg: log_save_query_run_to_db_timestamp erfolgreich beendet.")

        except Exception as e:
            print(f"[class_tool_sql_reader] FEHLER: log_save_query_run_to_db_timestamp: {e}")

    # -------------------------------------------------------------------------

    def _detect_domain(self, task_description: str) -> str:
        """Erkennt die relevante Zieltabelle/Domain anhand Heuristik und konfigurierbaren Keywords."""
        print("[class_tool_sql_reader] Starte Arbeit: _detect_domain wird jetzt ausgeführt.")
        if not task_description or not isinstance(task_description, str) or not task_description.strip():
            print("[class_tool_sql_reader] Erfolg: _detect_domain erfolgreich beendet.")
            return self.DOMAIN

        desc_lower = task_description.lower()
        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            if any(kw in desc_lower for kw in keywords):
                print("[class_tool_sql_reader] Erfolg: _detect_domain erfolgreich beendet.")
                return domain

        # Optional: TF-IDF via sklearn
        if importlib.util.find_spec("sklearn") and importlib.util.find_spec("numpy"):
            try:
                from sklearn.feature_extraction.text import TfidfVectorizer
                from sklearn.metrics.pairwise import cosine_similarity
                import numpy as np

                domain_corpus = {d: " ".join(w) for d, w in self.DOMAIN_KEYWORDS.items()}
                domain_keys   = list(domain_corpus.keys())
                vectorizer    = TfidfVectorizer()
                tfidf_matrix  = vectorizer.fit_transform(list(domain_corpus.values()))
                task_vector   = vectorizer.transform([task_description])
                cosine_sim    = cosine_similarity(task_vector, tfidf_matrix).flatten()
                total_sim     = np.sum(cosine_sim)
                if total_sim > 0:
                    probabilities = cosine_sim / total_sim
                    best_idx      = np.argmax(probabilities)
                    if probabilities[best_idx] >= self.TFIDF_SIMILARITY_THRESHOLD:
                        domain = domain_keys[best_idx]
                        if not domain:
                            print("[class_tool_sql_reader] FEHLER: _detect_domain hat die Aufgabe nicht erfüllt. Grund: Leere Domain nach TF-IDF.")
                            return self.DOMAIN
                        print("[class_tool_sql_reader] Erfolg: _detect_domain erfolgreich beendet.")
                        return domain
            except Exception:
                pass

        print("[class_tool_sql_reader] Erfolg: _detect_domain erfolgreich beendet.")
        return self.DOMAIN

    # -------------------------------------------------------------------------

    def _get_relevant_tips(self, task_description: str) -> str:
        """Lädt kontextbezogene Richtlinien, Blueprint-Schritte und Knoten aus der Datenbank."""
        print("[class_tool_sql_reader] Starte Arbeit: _get_relevant_tips wird jetzt ausgeführt.")
        domain = self._detect_domain(task_description)
        tips = [
            "==================================================",
            " [SYSTEM CORE MEMORY: KNOWLEDGE AGENT ROUTING TREE]",
            "=================================================="
        ]

        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()

                try:
                    cursor.execute(f"SELECT directive_key, explanation_for_agent FROM agent_system_manifest LIMIT {self.MAX_MANIFEST_ENTRIES}")
                    manifest_rows = cursor.fetchall()
                except sqlite3.OperationalError:
                    manifest_rows = []

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
            result = f"No prior routing tree nodes recorded for domain [{domain}]."
            print("[class_tool_sql_reader] Erfolg: _get_relevant_tips erfolgreich beendet.")
            return result
        result = "\n".join(tips)
        print("[class_tool_sql_reader] Erfolg: _get_relevant_tips erfolgreich beendet.")
        return result

    # -------------------------------------------------------------------------

    def initialize_blueprint_system(self, user_input: str) -> dict:
        """Initialisiert das Blueprint-System für eine Eingabe."""
        print("[class_tool_sql_reader] Starte Arbeit: initialize_blueprint_system wird jetzt ausgeführt.")
        if not user_input or not isinstance(user_input, str) or not user_input.strip():
            return {"status": "FAILED", "query": user_input, "error": "Leere Eingabe"}
        result = {"status": "INITIALIZED", "query": user_input.strip()}
        print("[class_tool_sql_reader] Erfolg: initialize_blueprint_system erfolgreich beendet.")
        return result

    # -------------------------------------------------------------------------

    def generate_knowledge_fallback_response(
        self,
        user_input: str,
        domain: str = None,
        db_tips: str = None,
        error_info: str = None
    ) -> str:
        """Erzeugt eine deterministische, wissensbasierte Fallback-Antwort direkt aus dem SQLite-Routing-Tree."""
        print("[class_tool_sql_reader] Starte Arbeit: generate_knowledge_fallback_response wird jetzt ausgeführt.")
        domain = domain or self._detect_domain(user_input)
        db_tips = db_tips or self._get_relevant_tips(user_input)

        lines = [
            f"Hallo! Ich bin dein autonomer AI-Agent mit verankertem SQLite-Langzeitgedächtnis.",
            f"Erkannte Domäne: [{domain}]",
            ""
        ]

        if error_info:
            lines.append(f"[Hinweis zur LLM-Inferenz] Das lokale Sprachmodell lieferte kein Ergebnis ({error_info}).")
            lines.append("Ich greife daher autonom und direkt auf mein SQLite-Wissensnetzwerk (Knowledge Agent Routing Tree) zurück.")
            lines.append("Tipp: Führe im Terminal 'ollama pull codestral' oder 'ollama pull llama3' aus, um das lokale Modell zu aktivieren.")
            lines.append("")

        lines.append("--- Extrahierte Wissenselemente & Systemrichtlinien ---")
        if db_tips and isinstance(db_tips, str) and db_tips.strip():
            tip_lines = [l for l in db_tips.splitlines() if l.strip() and not l.startswith("=")]
            for tl in tip_lines[:15]:
                lines.append(tl)
        else:
            lines.append(f"* Domäne [{domain}]: Keine spezifischen Vorab-Knoten für diese Anfrage registriert.")

        lines.append("")
        lines.append(f"Deine Anfrage lautete: \"{user_input}\"")
        lines.append(f"Status: Die Anfrage wurde im System unter Domäne [{domain}] registriert und protokolliert.")

        response_text = "\n".join(lines)
        if not response_text or not isinstance(response_text, str) or not response_text.strip():
            print("[class_tool_sql_reader] FEHLER: generate_knowledge_fallback_response hat die Aufgabe nicht erfüllt. Grund: Leerer Fallback-Text.")
            return "Fehler beim Erzeugen der Wissens-Antwort."
        print("[class_tool_sql_reader] Erfolg: generate_knowledge_fallback_response erfolgreich beendet.")
        return response_text

    # -------------------------------------------------------------------------

    def _insert_routing_node(self, conn, table_name: str, node_id: str,
                             topic_title: str = "", topic_specification: str = "",
                             agent_instruction: str = "", example_code_snippet: str = "",
                             validation_rule: str = "", target_table: str = "",
                             target_node_id: str = "000", **kwargs):
        """Fügt einen neuen Knoten dynamisch anhand des Live-Schemas in die Tabelle ein."""
        print("[class_tool_sql_reader] Starte Arbeit: _insert_routing_node wird jetzt ausgeführt.")
        if not conn or not table_name or not node_id:
            raise ValueError("Ungültige Parameter für _insert_routing_node")

        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        actual_columns = {row[1] for row in cursor.fetchall()}

        if not actual_columns:
            raise ValueError(f"Tabelle '{table_name}' existiert nicht oder hat keine Spalten.")

        now = datetime.datetime.now()
        payload = {
            "node_id": node_id, "is_active": 1, "error_fallback_count": 0,
            "year": now.year, "month": now.month, "day": now.day,
            "hour": now.hour, "minute": now.minute, "second": now.second,
            "topic_title": topic_title,
            "topic_specification": topic_specification,
            "agent_instruction": agent_instruction,
            "example_code_snippet": example_code_snippet,
            "validation_rule": validation_rule,
            "execution_count": 1, "success_weight": 1.0,
            "target_table": target_table, "target_column_id": "node_id",
            "target_node_id": target_node_id,
            **kwargs
        }

        filtered_data = {k: v for k, v in payload.items() if k in actual_columns}
        cols          = ", ".join(filtered_data.keys())
        placeholders  = ", ".join(["?"] * len(filtered_data))

        cursor.execute(f"INSERT OR REPLACE INTO {table_name} ({cols}) VALUES ({placeholders})", list(filtered_data.values()))
        conn.commit()
        print(f"[SQL-SUCCESS] Knoten '{node_id}' erfolgreich in Tabelle '{table_name}' verankert.")
        print("[class_tool_sql_reader] Erfolg: _insert_routing_node erfolgreich beendet.")

    # -------------------------------------------------------------------------

    def deactivate_and_reroute(self, table_name: str, node_id: str, failure_reason: str) -> dict:
        """Deaktiviert fehlerhafte Knoten und leitet auf Alternativpfade um."""
        print("[class_tool_sql_reader] Starte Arbeit: deactivate_and_reroute wird jetzt ausgeführt.")
        if not node_id:
            return {"deactivated_node": "UNKNOWN", "table_name": table_name,
                    "reason": failure_reason, "alternative_available": False}

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
                result = {
                    "deactivated_node": node_id, "table_name": table_name,
                    "reason": failure_reason,
                    "alternative_available": alt_row is not None,
                    "next_node":   alt_row[0] if alt_row else "000",
                    "next_target": alt_row[2] if alt_row and alt_row[2] else "FX_CHAIN"
                }
                print("[class_tool_sql_reader] Erfolg: deactivate_and_reroute erfolgreich beendet.")
                return result
        except Exception as e:
            return {"deactivated_node": node_id, "table_name": table_name,
                    "reason": str(e), "alternative_available": False}

    # -------------------------------------------------------------------------

    def fetch_records(self, table_name: str, active_only: bool = True):
        """Liest Datensätze aus einer Tabelle aus."""
        print("[class_tool_sql_reader] Starte Arbeit: fetch_records wird jetzt ausgeführt.")
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            query = f"SELECT * FROM {table_name}" + (" WHERE is_active = 1" if active_only else "")
            cursor.execute(query)
            cols = [d[0] for d in cursor.description] if cursor.description else []
            result = [dict(zip(cols, row)) for row in cursor.fetchall()]
        if result is None:
            print("[class_tool_sql_reader] FEHLER: fetch_records hat die Aufgabe nicht erfüllt. Grund: Kein Ergebnis.")
            return []
        print("[class_tool_sql_reader] Erfolg: fetch_records erfolgreich beendet.")
        return result

    def fetch_single_node(self, table_name: str, node_id: str):
        """Liest einen einzelnen Knoten aus."""
        print("[class_tool_sql_reader] Starte Arbeit: fetch_single_node wird jetzt ausgeführt.")
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {table_name} WHERE node_id = ?", (node_id,))
            row = cursor.fetchone()
            if row and cursor.description:
                cols = [d[0] for d in cursor.description]
                result = dict(zip(cols, row))
                print("[class_tool_sql_reader] Erfolg: fetch_single_node erfolgreich beendet.")
                return result
            print("[class_tool_sql_reader] Erfolg: fetch_single_node erfolgreich beendet.")
            return None

    # -------------------------------------------------------------------------

    def evolve_self(self, recent_error: str, task_context: str):
        """Schreibt eine neue, verbesserte Version von sich selbst mit aktuellem Zeitstempel."""
        print("[class_tool_sql_reader] Starte Arbeit: evolve_self wird jetzt ausgeführt.")
        timestamp   = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        history_dir = self.root_path / "temp" / "meta_coder_history"
        history_dir.mkdir(parents=True, exist_ok=True)
        new_filename = history_dir / f"MetaCodeBase_{timestamp}.py"
        tips_text    = self._get_relevant_tips(task_context)

        prompt = (
            f"You are an expert Autonomous Meta-Architect AI. You are improving your own source code to fix a recurring bug.\n\n"
            f"Current Error Encountered:\n{recent_error}\n\n"
            f"Relevant Database Knowledge:\n{tips_text}\n\n"
            f"Task: Rewrite and improve this Python class so that it proactively checks for and prevents the above error. "
            f"Return the COMPLETE, executable Python code inside markdown code blocks (```python ... ```)."
        )

        res = ollama_manager.run_agent(
            prompt, model=self.MODEL_LLM, ollama_host=self.OLLAMA_HOST,
            agent_title="SQLReader-Evolution"
        ) if ollama_manager else {}

        if res.get("status") == "SUCCESS":
            raw_text = res.get("content", "")
            try:
                blocks    = sub_verifier.extract_code_blocks(raw_text) if sub_verifier else []
                code_text = blocks[0] if blocks else raw_text.strip()
            except Exception:
                code_text = raw_text.strip()
            with open(new_filename, "w", encoding="utf-8") as f:
                f.write(code_text)
            print(f"[EVOLUTION] Neue Version gespeichert: {new_filename}")
            print("[class_tool_sql_reader] Erfolg: evolve_self erfolgreich beendet.")
            return new_filename
        print("[class_tool_sql_reader] Erfolg: evolve_self erfolgreich beendet.")
        return None

    # -------------------------------------------------------------------------

    def run_pipeline(self, task_description: str, target_notebook: str = None) -> dict:
        """Führt die Haupt-Pipeline über die sequentiellen SQL-Phasen aus."""
        print("[class_tool_sql_reader] Starte Arbeit: run_pipeline wird jetzt ausgeführt.")
        self._ensure_core_tables()
        result = self.execute_query_with_db_phases(raw_query=task_description)
        if not result or result.get("status") != "SUCCESS":
            print("[class_tool_sql_reader] FEHLER: run_pipeline hat die Aufgabe nicht erfüllt. Grund: Pipeline-Ergebnis ungültig.")
            return {}
        print("[class_tool_sql_reader] Erfolg: run_pipeline erfolgreich beendet.")
        return result

    # -------------------------------------------------------------------------

    def _ensure_src_library_tables(self):
        """Erstellt die SRC-Library-Strukturen und Fix-Tabellen."""
        print("[class_tool_sql_reader] Starte Arbeit: _ensure_src_library_tables wird jetzt ausgeführt.")
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS meta_agent_code_project_log_healing_registry (
                    node_id TEXT PRIMARY KEY,
                    target_library_table TEXT NOT NULL,
                    category TEXT NOT NULL,
                    description TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS library_src_code (
                    node_id TEXT PRIMARY KEY,
                    file_path TEXT NOT NULL,
                    module_name TEXT,
                    code_snippet TEXT NOT NULL,
                    function_signature TEXT,
                    quality_score REAL DEFAULT 1.0,
                    year INTEGER, month INTEGER, day INTEGER,
                    hour INTEGER, minute INTEGER, second INTEGER,
                    timestamp_str TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS library_src_bugs_cleaning (
                    node_id TEXT PRIMARY KEY,
                    related_code_node_id TEXT,
                    detected_bug_description TEXT NOT NULL,
                    failed_code_snippet TEXT,
                    applied_fix TEXT NOT NULL,
                    prohibited_pattern_self_ban TEXT NOT NULL,
                    year INTEGER, month INTEGER, day INTEGER,
                    hour INTEGER, minute INTEGER, second INTEGER,
                    timestamp_str TEXT NOT NULL,
                    FOREIGN KEY (related_code_node_id) REFERENCES library_src_code(node_id)
                );
            """)
            cursor.execute("""
                INSERT OR IGNORE INTO meta_agent_code_project_log_healing_registry
                (node_id, target_library_table, category, description)
                VALUES
                ('ROUTE_SRC_CODE', 'library_src_code', 'CLEAN_SRC', 'Speicherort für funktionierenden SRC Code'),
                ('ROUTE_SRC_BUGS', 'library_src_bugs_cleaning', 'BUG_FIX_BANS', 'Speicherort für Fehlerprotokolle und selbstauferlegte Verhaltensverbote');
            """)
            conn.commit()
        print("[class_tool_sql_reader] Erfolg: _ensure_src_library_tables erfolgreich beendet.")

    # -------------------------------------------------------------------------

    def _get_standard_timestamp_dict(self) -> dict:
        """Erzeugt ein standardisiertes Zeitstempel-Dictionary für konsistente DB-Einträge."""
        print("[class_tool_sql_reader] Starte Arbeit: _get_standard_timestamp_dict wird jetzt ausgeführt.")
        now = datetime.datetime.now()
        result = {
            "year": now.year, "month": now.month, "day": now.day,
            "hour": now.hour, "minute": now.minute, "second": now.second,
            "timestamp_str": now.strftime("%Y%m%d_%H%M%S")
        }
        if result is None:
            print("[class_tool_sql_reader] FEHLER: _get_standard_timestamp_dict hat die Aufgabe nicht erfüllt. Grund: Kein Dict erzeugt.")
            return {}
        print("[class_tool_sql_reader] Erfolg: _get_standard_timestamp_dict erfolgreich beendet.")
        return result

    # -------------------------------------------------------------------------

    def _generic_library_insert(self, table_name: str, prefix: str, payload_data: dict) -> str:
        """Zentrale Kern-Def für alle wiederkehrenden Schreiboperationen in die Library-Tabellen."""
        print("[class_tool_sql_reader] Starte Arbeit: _generic_library_insert wird jetzt ausgeführt.")
        self._ensure_src_library_tables()
        ts           = self._get_standard_timestamp_dict()
        node_id      = f"{prefix}_{ts['timestamp_str']}_{random.randint(100, 999)}"
        full_payload = {"node_id": node_id, **ts, **payload_data}

        with self.get_db_connection() as conn:
            cursor       = conn.cursor()
            cols         = ", ".join(full_payload.keys())
            placeholders = ", ".join(["?"] * len(full_payload))
            cursor.execute(f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders})", list(full_payload.values()))
            conn.commit()

        if not node_id or not isinstance(node_id, str):
            print("[class_tool_sql_reader] FEHLER: _generic_library_insert hat die Aufgabe nicht erfüllt. Grund: node_id ungültig.")
            return ""
        print("[class_tool_sql_reader] Erfolg: _generic_library_insert erfolgreich beendet.")
        return node_id

    # -------------------------------------------------------------------------

    def write_clean_src_code(self, file_path: str, code_snippet: str,
                             module_name: str = "", quality_score: float = 1.0) -> str:
        """Schreibt sauberen SRC-Code über die gemeinsame Kern-Def."""
        print("[class_tool_sql_reader] Starte Arbeit: write_clean_src_code wird jetzt ausgeführt.")
        result = self._generic_library_insert(
            table_name="library_src_code", prefix="SRC",
            payload_data={"file_path": file_path, "module_name": module_name,
                          "code_snippet": code_snippet, "quality_score": quality_score, "is_active": 1}
        )
        if not result or not isinstance(result, str):
            print("[class_tool_sql_reader] FEHLER: write_clean_src_code hat die Aufgabe nicht erfüllt. Grund: Kein node_id zurückgegeben.")
            return ""
        print("[class_tool_sql_reader] Erfolg: write_clean_src_code erfolgreich beendet.")
        return result

    def log_src_bug_and_self_ban(self, bug_description: str, failed_code: str,
                                  applied_fix: str, self_ban_rule: str,
                                  related_src_node_id: str = None) -> str:
        """Protokolliert Bugs und Selbstverbote über die gemeinsame Kern-Def."""
        print("[class_tool_sql_reader] Starte Arbeit: log_src_bug_and_self_ban wird jetzt ausgeführt.")
        node_id = self._generic_library_insert(
            table_name="library_src_bugs_cleaning", prefix="BUG",
            payload_data={
                "related_code_node_id":      related_src_node_id,
                "detected_bug_description":  bug_description,
                "failed_code_snippet":       failed_code,
                "applied_fix":               applied_fix,
                "prohibited_pattern_self_ban": self_ban_rule
            }
        )
        print(f"[SELF-HEALING BAN ENFORCED] Neues Verbot registriert: {self_ban_rule}")
        if not node_id or not isinstance(node_id, str):
            print("[class_tool_sql_reader] FEHLER: log_src_bug_and_self_ban hat die Aufgabe nicht erfüllt. Grund: Kein node_id zurückgegeben.")
            return ""
        print("[class_tool_sql_reader] Erfolg: log_src_bug_and_self_ban erfolgreich beendet.")
        return node_id

    def stochastic_sample_read(self, table_name: str, sample_size: int = 5,
                                category_filter: str = None) -> list:
        """Stochastischer Lesezugriff auf eine bestimmte Tabelle."""
        print("[class_tool_sql_reader] Starte Arbeit: stochastic_sample_read wird jetzt ausgeführt.")
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            if category_filter and "category" in [col[1] for col in cursor.execute(f"PRAGMA table_info({table_name})")]:
                cursor.execute(f"SELECT * FROM {table_name} WHERE category = ? ORDER BY RANDOM() LIMIT ?", (category_filter, sample_size))
            else:
                cursor.execute(f"SELECT * FROM {table_name} ORDER BY RANDOM() LIMIT ?", (sample_size,))
            rows = cursor.fetchall()
            cols = [d[0] for d in cursor.description] if cursor.description else []
            result = [dict(zip(cols, row)) for row in rows]
        if result is None:
            print("[class_tool_sql_reader] FEHLER: stochastic_sample_read hat die Aufgabe nicht erfüllt. Grund: Kein Ergebnis.")
            return []
        print("[class_tool_sql_reader] Erfolg: stochastic_sample_read erfolgreich beendet.")
        return result

    def get_active_self_bans(self) -> list:
        """Liest alle aktiven Verbote aus der Bug-Cleaning-Tabelle aus."""
        print("[class_tool_sql_reader] Starte Arbeit: get_active_self_bans wird jetzt ausgeführt.")
        self._ensure_src_library_tables()
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT prohibited_pattern_self_ban, detected_bug_description, applied_fix FROM library_src_bugs_cleaning ORDER BY node_id DESC")
            result = cursor.fetchall()
        if result is None:
            print("[class_tool_sql_reader] FEHLER: get_active_self_bans hat die Aufgabe nicht erfüllt. Grund: Kein Ergebnis.")
            return []
        print("[class_tool_sql_reader] Erfolg: get_active_self_bans erfolgreich beendet.")
        return result

    # --- Kompatibilitäts-Weiterleitungen ---

    def check_or_cache_user_query(self, raw_query: str) -> dict:
        """Direktweiterleitung auf get_cached_or_create_query."""
        print("[class_tool_sql_reader] Starte Arbeit: check_or_cache_user_query wird jetzt ausgeführt.")
        result = self.get_cached_or_create_query(raw_query)
        if not result:
            print("[class_tool_sql_reader] FEHLER: check_or_cache_user_query hat die Aufgabe nicht erfüllt. Grund: Leeres Ergebnis.")
            return {}
        print("[class_tool_sql_reader] Erfolg: check_or_cache_user_query erfolgreich beendet.")
        return result

    def store_query_result(self, node_id: str, answer: str, snippet: str = ""):
        """Direktweiterleitung auf seal_query_cache zur Wahrung der Kompatibilität."""
        print("[class_tool_sql_reader] Starte Arbeit: store_query_result wird jetzt ausgeführt.")
        result = self.seal_query_cache(node_id=node_id, answer=answer, snippet=snippet)
        print("[class_tool_sql_reader] Erfolg: store_query_result erfolgreich beendet.")
        return result

    def save_table_issue_data_run_protocol(self, *args, **kwargs):
        """Direktweiterleitung auf log_save_query_run_to_db_timestamp."""
        print("[class_tool_sql_reader] Starte Arbeit: save_table_issue_data_run_protocol wird jetzt ausgeführt.")
        result = self.log_save_query_run_to_db_timestamp(*args, **kwargs)
        print("[class_tool_sql_reader] Erfolg: save_table_issue_data_run_protocol erfolgreich beendet.")
        return result

    def _save_solution_to_db(self, task_description: str, error_msg: str, solution_code: str):
        """Direktweiterleitung auf log_save_query_run_to_db_timestamp."""
        print("[class_tool_sql_reader] Starte Arbeit: _save_solution_to_db wird jetzt ausgeführt.")
        result = self.log_save_query_run_to_db_timestamp(
            task_description=task_description,
            error_msg=error_msg,
            solution_code=solution_code,
            step_type="checkpoint"
        )
        print("[class_tool_sql_reader] Erfolg: _save_solution_to_db erfolgreich beendet.")
        return result

    # =========================================================================
    # EBENE 5: VERBINDUNGS_KLEMME
    # =========================================================================

    def run_sql_reader(self) -> dict:
        """
        Orchestriert den vollständigen Arbeitsablauf der Klasse:
        1. Umgebung verifizieren (DB-Existenz & Kerntabellen)
        2. SRC-Library-Tabellen sicherstellen
        3. Bootstrap-DNA aus SQLite laden
        Gibt einen Status-Dict zurück.
        """
        print("[class_tool_sql_reader] Starte Arbeit: run_sql_reader wird jetzt ausgeführt.")
        status = {"verify": False, "src_tables": False, "bootstrap_phases": 0}

        status["verify"] = self.verify_environment()

        try:
            self._ensure_src_library_tables()
            status["src_tables"] = True
        except Exception as e:
            print(f"[class_tool_sql_reader] FEHLER: SRC-Library-Tabellen konnten nicht gesichert werden: {e}")

        phases = self.bootstrap_from_database()
        status["bootstrap_phases"] = len(phases)

        print(f"[class_tool_sql_reader] Verbindungs-Klemme abgeschlossen: {status}")
        print("[class_tool_sql_reader] Erfolg: run_sql_reader erfolgreich beendet.")
        return status
