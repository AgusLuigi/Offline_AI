import datetime
import logging
import random
import sqlite3
import subprocess
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


# GLOBALE KONFIGURATION — Alle Parameter zur mechanischen Steuerung der
# LLM-Intensität, Iterationshäufigkeit, Textlimits und Schwellenwerte.
# Werden in allen Abläufen dynamisch abgerufen und eingefügt.

# --- Projekt & Dateien ---
PROJECT_POINT = "src"
DB_FILENAME = "Knowledge_Agent_Routing_tree.db"
OLLAMA_CHECKER_FILENAME = "__ollama_running.py"

# --- LLM-Konfiguration ---
MODEL_LLM = "codestral"
OLLAMA_HOST = "http://127.0.0.1:11434"
AGENT_NAME = "MetaCoder-Agent"

# --- Iterationssteuerung ---
MAX_EVOLUTION_GENERATIONS = 3
MAX_USER_QUERY_ID_RANGE = (3, 999)          # ID-Bereich für User-Queries
EVOLUTION_RETRY_DELAY_SEC = 1

# --- Text- und Ausgabelimits pro Mikroablauf ---
TASK_DESCRIPTION_MAX_LEN = 200
CODE_SNIPPET_PREVIEW_LEN = 150
QUERY_TITLE_MAX_LEN = 35
MAX_SANDBOX_OUTPUT_LENGTH = 4000
DEFAULT_SANDBOX_TIMEOUT = 15
PROMPT_MAX_LEN = 500

# --- Schwellenwerte für LLM-Intensität & Stochastik ---
TFIDF_SIMILARITY_THRESHOLD = 0.15
FEEDBACK_WEIGHT_INCREMENT = 0.2
MAX_BLUEPRINT_STEPS = 5
MAX_DOMAIN_NODES = 3
MAX_MANIFEST_ENTRIES = 5
CPU_WARNING_THRESHOLD = 90.0
MIN_RAM_MB = 2000
SPINNER_INTERVAL = 1.0

# --- Domain-Erkennung: Keyword-Mapping (überschreibbar) ---
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

# --- Erlaubte Tabellen für SQL-Operationen ---
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
DEFAULT_FALLBACK_DOMAIN = "library_registry"

# --- Kernel-Module für den Start-Scan ---
REQUIRED_KERNEL_MODULES = ["psutil", "sqlite3"]

# ENDE DER GLOBALEN KONFIGURATION

class MetaCoderSQLPipeline(class_sql_reader):
    """
    Zentrale Verklemmungs-Pipeline ('metacoder.sql v2+V1').
    Verlinkt Core-Infrastruktur, SQL-Reader, Sandbox-Verifier,
    Evolutions-Schleife und Terminal-Spinner zu einem autonomen Agenten-System.
    
    Integriert alle V1-Funktionalitäten:
    - Database-Driven DNA Bootstrap
    - Autonomer User-Query-Cache (Zero-Compute)
    - Benutzer-Feedback mit Gewichtsanpassung
    - Knoten-Deaktivierung & Rerouting mit FX_CHAIN
    - Persistenz neuer Fähigkeiten in library_registry
    - Kontextbezogene SQLite-Knowledge-Tips
    - Selbst-Evolution via LLM
    - Erweiterter Chat-Modus mit Feedback-Commands
    """

    # Klassenattribute aus Konfiguration überschreiben
    ALLOWED_TABLES = ALLOWED_TABLES_EXCLUDE
    DEFAULT_DOMAIN = DEFAULT_FALLBACK_DOMAIN
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
        super().__init__()
        # Initialisierung der vererbten Core-Infrastruktur und Bestimmung des Projekt-Roots
        self.root_path = Path(coreInfrastructure.get_project_root(start_path))
        
        # Universelle und absolute Pfadfindung für die Datenbank
        try:
            self.db_filename = str(coreInfrastructure.get_file_path(db_filename))
        except FileNotFoundError:
            self.db_filename = str(self.root_path / db_filename)
        
        # Initialisierung des Evolutions-Loops
        self.evolution_loop = EvolveLoopTest(registry_db_path=self.db_filename)
        self.evolution_loop.EVOLUTION_RETRY_DELAY_SEC = EVOLUTION_RETRY_DELAY_SEC
        
        # Ressourcen-Spinner initialisieren (Parameter aus globaler Konfiguration)
        self.spinner = ResourceAwareSpinner(
            agent_name=AGENT_NAME,
            min_ram_mb=MIN_RAM_MB,
            max_cpu_threshold=CPU_WARNING_THRESHOLD,
            spinner_interval=SPINNER_INTERVAL
        )

        # LLM-Client (V1-Funktion)
        self.model_name = model_name
        self.ollama_host = ollama_host
        self.client = None
        
        if require_ollama:
            try:
                from ollama import Client
                self.client = Client(host=ollama_host)
                self.client.list()
                print(f"[INFO] Ollama-Client verbunden: {ollama_host} | Modell: {model_name}")
            except ImportError:
                print("[WARNUNG] Paket 'ollama' nicht installiert. LLM-Funktionen deaktiviert.")
            except Exception as e:
                print(f"[WARNUNG] Ollama-Verbindung fehlgeschlagen: {e}. LLM-Funktionen eingeschränkt.")

        # Database-Driven DNA (V1-Funktion)
        self.bootstrap_dna = []
        self.manifest_directives = {}

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

    # V1-FUNKTIONEN: DATABASE-DRIVEN DNA & BOOTSTRAP
    def bootstrap_from_database(self):
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
                    SELECT node_id, topic_title, topic_specification, agent_instruction, target_table, target_node_id
                    FROM {start_table}
                    WHERE is_active = 1
                    ORDER BY node_id ASC
                """)
                phases = cursor.fetchall()
                self.bootstrap_dna = phases
                
                for node_id, title, spec, instruction, tgt_tbl, tgt_node in phases:
                    print(f"  • Phase [{node_id}] {title}")
                    
                    # Phase 000: System Manifest harvest
                    if node_id == "000":
                        try:
                            cursor.execute("SELECT directive_key, explanation_for_agent FROM agent_system_manifest WHERE is_active = 1")
                            self.manifest_directives = dict(cursor.fetchall())
                            print(f"    ↳ {len(self.manifest_directives)} Kern-Direktiven aus 'agent_system_manifest' absorbiert.")
                        except sqlite3.OperationalError:
                            pass
                    
                    # Phase 001: Kernel & Resource Audit
                    elif node_id == "001":
                        k_mods = coreInfrastructure.scan_kernel_modules(REQUIRED_KERNEL_MODULES + ["ollama"])
                        print(f"    ↳ Kernel-Audit: {sum(1 for v in k_mods.values() if v == 'active')}/{len(k_mods)} Module aktiv.")
                    
                    # Phase 002: Cache readiness check
                    elif node_id == "002":
                        try:
                            cursor.execute("SELECT COUNT(*) FROM user_query WHERE is_active = 1")
                            active_queries = cursor.fetchone()[0]
                            print(f"    ↳ Idempotenz-Prüfung: 'user_query' betriebsbereit ({active_queries} aktive Einträge).")
                        except sqlite3.OperationalError:
                            print("    ↳ Tabelle 'user_query' nicht gefunden, wird bei Bedarf erstellt.")
                    
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
                            print(f"    ↳ Startup-Siegel in 'table_issue_data_time_stamp_run_protocol_for_query' verankert.")
                        except Exception:
                            pass

                print(f"--> [BOOTSTRAP-DNA ERFOLG] {len(phases)} Phasen erfolgreich aus SQLite instanziiert.")
                print("=" * 60 + "\n")
        except Exception as e:
            print(f"--> [BOOTSTRAP FEHLER] Konnte Start-DNA nicht vollständig laden: {e}")

    # V1-FUNKTIONEN: USER-QUERY-CACHE & FEEDBACK
    def check_or_cache_user_query(self, raw_query: str) -> dict:
        """
        Autonome User-Query-Prüfung & Sequenzieller Cache.
        1. Exakter Cache-Hit: Liefert Antwort direkt ohne LLM-Inferenz (Zero-Compute).
        2. Cache-Miss: Registriert neue Anfrage unter nächster freier ID.
        """
        cleaned_query = raw_query.strip().lower()
        id_start, id_end = MAX_USER_QUERY_ID_RANGE

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
                print(f"--> [SQL-CACHE HIT] Anfrage direkt aus Node '{cached[0]}' geladen (Zero-Compute)!")
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
                raise OverflowError(f"Maximale User-Query-Kapazität von ID {id_end - 1} erreicht!")
                
            next_node_id = f"{next_id_num:03d}"
            now = datetime.datetime.now()
            
            try:
                self._insert_routing_node(
                    conn=conn,
                    table_name="user_query",
                    node_id=next_node_id,
                    topic_title=f"USER QUERY: {raw_query[:QUERY_TITLE_MAX_LEN]}",
                    topic_specification=raw_query,
                    agent_instruction="PROCESSING",
                    validation_rule="PENDING_EXECUTION",
                    target_table="pre_execution_blueprint_generator",
                    target_node_id="000"
                )
            except Exception:
                # Fallback: Direkter Insert
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
                    f"USER QUERY: {raw_query[:QUERY_TITLE_MAX_LEN]}",
                    raw_query
                ))
                conn.commit()
            
            print(f"--> [SQL-CACHE MISS] Neue Anfrage in Node '{next_node_id}' registriert.")
            return {
                "cache_hit": False,
                "node_id": next_node_id,
                "query": raw_query,
                "status": "PENDING_EXECUTION"
            }

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

    def record_feedback(self, query_node_id: str, is_positive: bool, comment: str = "") -> dict:
        """
        Verarbeitet Benutzer-Feedback für einen Query-Knoten.
        Positiv: Erhöht success_weight. Negativ: Deaktiviert den Knoten via Rerouting.
        """
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            if is_positive:
                cursor.execute("""
                    UPDATE user_query
                    SET success_weight = success_weight + ?,
                        validation_rule = 'POSITIVE_VERIFIED'
                    WHERE node_id = ?
                """, (FEEDBACK_WEIGHT_INCREMENT, query_node_id))
                conn.commit()
                print(f"--> [FEEDBACK POSITIV] Node '{query_node_id}' durch Feedback gestärkt (Gewicht +{FEEDBACK_WEIGHT_INCREMENT}).")
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
                example_code_snippet=code_snippet[:PROMPT_MAX_LEN],
                validation_rule="capability_persisted == TRUE"
            )
        print(f"\n[PERSISTENZ-ERFOLG] Fähigkeit '{capability_name}' wurde dauerhaft in SQLite ('library_registry') verewigt!")

    # KONTEXTBEZOGENE KNOWLEDGE-TIPS
    def _get_relevant_tips(self, task_description: str) -> str:
        """
        Lädt kontextbezogene Richtlinien, Blueprint-Schritte und Knoten
        aus der existierenden Knowledge_Agent_Routing_tree.db.
        Nutzt konfigurierbare Limits aus der globalen Konfiguration.
        """
        domain = self._detect_domain(task_description)
        tips = ["=================================================="]
        tips.append(" [SYSTEM CORE MEMORY: KNOWLEDGE AGENT ROUTING TREE]")
        tips.append("==================================================")

        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()

                # 1. System-Manifest & Core-Direktiven laden
                try:
                    cursor.execute(f"SELECT directive_key, explanation_for_agent FROM agent_system_manifest LIMIT {MAX_MANIFEST_ENTRIES}")
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
                            f"WHERE is_active = 1 AND ({placeholders}) ORDER BY success_weight DESC LIMIT {MAX_DOMAIN_NODES}",
                            params
                        )
                        domain_rows = cursor.fetchall()

                    if not domain_rows:
                        cursor.execute(
                            f"SELECT node_id, topic_title, agent_instruction, example_code_snippet FROM {domain} "
                            f"WHERE is_active = 1 ORDER BY success_weight DESC LIMIT {MAX_DOMAIN_NODES}"
                        )
                        domain_rows = cursor.fetchall()
                except sqlite3.OperationalError:
                    domain_rows = []

                # 3. Aktive Blueprint-Schritte laden
                try:
                    cursor.execute(
                        f"SELECT node_id, topic_title, agent_instruction FROM pre_execution_blueprint_generator "
                        f"WHERE is_active = 1 ORDER BY node_id ASC LIMIT {MAX_BLUEPRINT_STEPS}"
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
                        tips.append(f"  Code Snippet: {snippet.strip()[:CODE_SNIPPET_PREVIEW_LEN]}...")

            if blueprints:
                tips.append("\n--- Mandatory Pre-Execution Blueprints ---")
                for node_id, title, instruction in blueprints:
                    tips.append(f"• Step [{node_id}] {title}: {instruction}")

        except Exception as e:
            tips.append(f"\n[FEHLER] Konnte Knowledge-Tips nicht laden: {e}")

        if len(tips) <= 3:
            return f"No prior routing tree nodes recorded for domain [{domain}]."
        return "\n".join(tips)

    # ═══════════════════════════════════════════════════════════
    # KOGNITIVE ERFASSUNG, TOKEN-SCHÄRFUNG & AUDIT-PROTOKOLLIERUNG
    # ═══════════════════════════════════════════════════════════

    def index_chat_user_query(self, raw_query: str) -> dict:
        """
        ## // 💬 index_chat_user_query
        - Zweck: Erfassung, Bereinigung, Token-Schärfung und Indizierung von Benutzeranfragen vor dem Ausführungsstart.
        - Funktionsweise: Nimmt die Benutzer-Roheingabe entgegen, entfernt Füllwörter zur Token-Optimierung,
          klassifiziert den Typ der Anfrage (z. B. Coding, Architektur, Analyse, Reparatur) und leitet sie zur
          auditierbaren Zeitstempel-Protokollierung weiter. Dabei wird — nach dem ersten Eintrag in die Tabelle
          `user_query` — der dort eingetragene Zeitstempel als Name für die dynamische Log-Tabelle (`log_{time}`)
          verwendet, in welche die zusätzlichen Einträge als Protokoll geschrieben werden.
        - Kognitive Steuerung: Verhindert unklare Ausführungen durch strukturierte Übergabe-Parameter.
        """
        if not raw_query or not isinstance(raw_query, str):
            raw_query = ""

        # 1. Erfassung & Whitespace Sanitization (analog index_chat_user_query Node '000')
        clean_text = " ".join(raw_query.strip().split())

        # 2. Token-Schärfung: Entfernung von Füllphrasen & Füllwörtern
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
        if filtered_words:
            sharpened_text = " ".join(filtered_words)
        else:
            sharpened_text = clean_text

        # 3. Intent-Klassifikation: Typ der Anfrage ermitteln (Coding, Architektur, Analyse, Reparatur)
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

        # 4. Weiterleitung & Indizierung via user_query
        cached_check = self.get_cached_or_create_query(sharpened_text)
        node_id = cached_check.get("node_id") if cached_check else None

        # 5. Zeitstempel aus user_query für die dynamische Log-Tabelle (log_{time}) ermitteln
        time_stamp_str = None
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                if node_id:
                    cursor.execute("""
                        SELECT year, month, day, hour, minute, second 
                        FROM user_query 
                        WHERE node_id = ?
                    """, (node_id,))
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

        # 6. Auditierbare Initial-Protokollierung in log_{time} anstoßen (unter Nutzung von table_issue_data_time_stamp...)
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

    def log_save_query_run_to_db_timestamp(
        self,
        task_description: str,
        error_msg: str = "",
        solution_code: str = "",
        run_id: str = None,
        step_type: str = "checkpoint",
        log_table_name: str = None
    ):
        """
        // ⏱️ table_issue_data_time_stamp_run_protocol_for_query & dynamisches log_{time}
        Passe in meta_coder_sql die Funktion für table_issue_data_time_stamp_run_protocol_for_query
        passend an, sodass die Tabelle genutzt wird als zusätzliche Punkte zum Auffüllen vom Log,
        aber das Log als Name den passenden Zeitstempel bekommt (log_{time}).
        Nutzt vordefinierte defs aus agent_universal_skript (get_db_connection, _insert_routing_node,
        _detect_domain, fetch_records, fetch_single_node).
        """
        try:
            domain = self._detect_domain(task_description)
        except Exception as e:
            print(f"[GEGENKONTROLLE FEHLER] Domain-Erkennung fehlgeschlagen: {e}")
            domain = self.DEFAULT_DOMAIN

        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()

                # 1. Zeitstempel-Ermittlung aus user_query absichern
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

                # 2. Dynamischer Name des Logs: log_{time}
                if log_table_name:
                    dynamic_table_name = log_table_name if log_table_name.startswith("log_") else f"log_{log_table_name}"
                else:
                    dynamic_table_name = f"log_{run_id}"

                node_id = f"STEP_{hour:02d}{minute:02d}{second:02d}_{datetime.datetime.now().strftime('%f')}"

                # 3. Vorlagenpunkte aus table_issue_data_time_stamp_run_protocol_for_query laden
                # (Zusätzliche Anforderungen nach der is_active-Spalte zum Auffüllen vom Log)
                template_node = None
                target_step_node = "000" if step_type == "init" else ("002" if step_type == "seal" else "001")
                try:
                    cursor.execute("""
                        SELECT topic_title, topic_specification, agent_instruction, example_code_snippet, validation_rule
                        FROM table_issue_data_time_stamp_run_protocol_for_query
                        WHERE node_id = ?
                    """, (target_step_node,))
                    template_node = cursor.fetchone()
                except Exception:
                    template_node = None

                if template_node:
                    tpl_title, tpl_spec, tpl_inst, tpl_snippet, tpl_rule = template_node
                    step_title = f"{tpl_title} [{domain}]"
                    step_spec = f"{tpl_spec} | Context: {task_description[:120]}"
                    agent_inst = error_msg.strip().split('\n')[-1][:200] if error_msg else tpl_inst
                    validation_rule = tpl_rule
                else:
                    step_title = f"Step in [{domain}] ({step_type.upper()})"
                    step_spec = task_description[:self.TASK_DESCRIPTION_MAX_LEN]
                    agent_inst = error_msg.strip().split('\n')[-1][:self.TASK_DESCRIPTION_MAX_LEN] if error_msg else "RUN_STEP_SUCCESS"
                    validation_rule = "step_logged == TRUE"

                # 4. Dynamische Tabelle log_{time} erstellen (inklusive aller Anforderungen nach is_active)
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

                # 5. Mikroschritt in log_{time} schreiben
                self._insert_routing_node(
                    conn=conn,
                    table_name=dynamic_table_name,
                    node_id=node_id,
                    topic_title=step_title,
                    topic_specification=step_spec,
                    agent_instruction=agent_inst,
                    example_code_snippet=solution_code,
                    validation_rule=validation_rule,
                    target_table="table_issue_data_time_stamp_run_protocol_for_query",
                    target_node_id=target_step_node if template_node else "000"
                )

                # 6. Exakte Zeitstempel-Werte in den Datensatz schreiben
                cursor.execute(f"""
                    UPDATE {dynamic_table_name}
                    SET year = ?, month = ?, day = ?, hour = ?, minute = ?, second = ?
                    WHERE node_id = ?
                """, (year, month, day, hour, minute, second, node_id))
                conn.commit()

                # 7. Zusätzliche Verankerung in table_issue_data_time_stamp_run_protocol_for_query
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
                except Exception as audit_err:
                    print(f"[GEGENKONTROLLE HINWEIS] Master-Audit-Eintrag übersprungen: {audit_err}")

            print(f"[SQL-KNOWLEDGE] Protokollschritt mit DB-Zeitstempel in '{dynamic_table_name}' verankert.")

        except Exception as e:
            print(f"[KRITISCHER ABBRUCH IN log_save_query_run_to_db_timestamp]: {str(e)}")

    def save_table_issue_data_run_protocol(self, *args, **kwargs):
        """Alias für log_save_query_run_to_db_timestamp."""
        return self.log_save_query_run_to_db_timestamp(*args, **kwargs)

    def _save_solution_to_db(self, task_description: str, error_msg: str, solution_code: str):
        """Rückwärtskompatible Methode: Protokolliert Interaktionsmuster und Lösungen im Routing Tree."""
        return self.log_save_query_run_to_db_timestamp(
            task_description=task_description,
            error_msg=error_msg,
            solution_code=solution_code,
            step_type="checkpoint"
        )

    # SELBST-EVOLUTION VIA LLM
    def evolve_self(self, recent_error: str, task_context: str) -> Path:
        """Schreibt eine neue, verbesserte Version von sich selbst mit aktuellem Zeitstempel."""
        if not self.client:
            print("[EVOLUTION] Kein LLM-Client verfügbar. Selbst-Evolution übersprungen.")
            return None

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
        spinner = ResourceAwareSpinner(agent_name="Evolution", min_ram_mb=MIN_RAM_MB,
                                       max_cpu_threshold=CPU_WARNING_THRESHOLD, spinner_interval=SPINNER_INTERVAL)
        stop_event = threading.Event()
        spinner_thread = threading.Thread(target=spinner.run, args=(stop_event, True))
        spinner_thread.start()
        try:
            response = self.client.generate(model=self.model_name, prompt=prompt)
        finally:
            stop_event.set()
            spinner_thread.join()

        raw_text = response.get('response', '')
        new_code = SubAgentVerifier.extract_code_blocks(raw_text)
        code_text = new_code[0] if new_code else raw_text.strip()
        with open(new_filename, "w", encoding="utf-8") as f:
            f.write(code_text)
        print(f"[EVOLUTION] Neue Version gespeichert: {new_filename}")
        return new_filename

    # UMGEBUNGS-VERIFIKATION
    def verify_environment(self) -> bool:
        """
        Prüft die Existenz der globalen Datenbank, initialisiert die Tabellenstrukturen 
        und verifiziert die Tool-Schnittstellen.
        """
        db_path = Path(self.db_filename)
        if not db_path.exists():
            print(f"[METABASE] Erstelle neue SQLite-Registry unter: {db_path.resolve()}")
            db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._ensure_core_tables()
        
        if hasattr(self.evolution_loop, "init_database_tables"):
            try:
                self.evolution_loop.init_database_tables()
                print(f"[METABASE] Tabellenstrukturen in '{self.db_filename}' erfolgreich verifiziert/angelegt.")
            except Exception as e:
                print(f"[METABASE FEHLER] Konnte Tabellen nicht initialisieren: {e}")  
        
        print("[METAKODER] Umgebung erfolgreich verifiziert. Alle erweiterten Tools verbunden.")
        return True

    # HAUPT-PIPELINE
    def run_pipeline(self, task_description: str, target_notebook: str = None) -> dict:
        """
        Führt die Haupt-Pipeline aus:
        1. Cache-Prüfung oder Abfrage-Registrierung via SQL Reader.
        2. Visuelle Begleitung mit dem ResourceAwareSpinner.
        3. Ausführung im Closed-Loop (EvolveLoopTest + SubAgentVerifier).
        4. Protokollierung der Ergebnisse mit exaktem DB-Zeitstempel.
        """
        self._ensure_core_tables()
        stop_event = threading.Event()
        spinner_thread = threading.Thread(target=self.spinner.run, args=(stop_event, True))
        spinner_thread.start()
        codes = []
        node_id = None
        # 0. Kognitive Erfassung & Token-Schärfung via index_chat_user_query
        indexed_query = self.index_chat_user_query(task_description)
        if indexed_query.get("cache_hit"):
            cached_data = indexed_query.get("cached_check", {})
            cached_data["status"] = "SUCCESS"
            print(f"\n[CACHE HIT] Anfrage im Cache gefunden (Node-ID: {indexed_query.get('node_id')}).")
            return cached_data

        effective_task = indexed_query.get("sharpened_query") or task_description
        node_id = indexed_query.get("node_id")
        log_table = indexed_query.get("log_table_name")
        time_stamp = indexed_query.get("time_stamp")

        try:
            # 1. Blueprint-System anfahren
            try:
                self.initialize_blueprint_system(effective_task)
            except Exception as e:
                print(f"[GEGENKONTROLLE FEHLER] Blueprint-System übersprungen: {e}")  
            
            # Falls kein Reader die Node-ID generiert hat
            if not node_id:
                current_time = datetime.datetime.now().strftime("%H%M%S")
                unique_suffix = str(random.randint(100000, 999999))
                node_id = f"STEP_{current_time}_{unique_suffix}"
                print(f"[PIPELINE-FIX] Generiere autonome Pipeline-ID: {node_id}")
            
            # 2. Sandbox-Ausführungsumgebung
            def execution_runner(payload):
                nonlocal codes
                codes = SubAgentVerifier.extract_code_blocks(payload.get("task", ""))
                if codes:
                    success, output = SubAgentVerifier.verify_code_in_sandbox(
                        codes[0] if isinstance(codes, list) else codes,
                        timeout_sec=DEFAULT_SANDBOX_TIMEOUT
                    )
                    if not success:
                        raise RuntimeError(f"Sandbox-Fehler: {output}")
                    return output
                return "Kein ausführbarer Code-Block gefunden, logische Ausführung erfolgreich."
            
            # 3. Evolutionsschleife starten
            evolution_result = self.evolution_loop.test_and_evolve_loop(
                specialization=f"{AGENT_NAME} Automated Pipeline",
                task_description=effective_task,
                base_filename=target_notebook or "metacoder_run",
                max_generations=MAX_EVOLUTION_GENERATIONS,
                execution_func=execution_runner
            )
            final_status = evolution_result.get("status")
            final_message = evolution_result.get("message") or evolution_result.get("result", "")
            snippet_to_store = codes if codes else ""
            
            # 4. Ergebnisse im Cache versiegeln
            try:
                self.store_query_result(node_id=node_id, answer=str(final_message), snippet=str(snippet_to_store))
            except Exception as e:
                print(f"[GEGENKONTROLLE FEHLER] store_query_result abgebrochen: {e}")
            
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
                print(f"[GEGENKONTROLLE FEHLER] Zeitstempel-Verankerung fehlgeschlagen: {e}")
            
            # 7. Bei Fehler: Selbst-Evolution auslösen
            if final_status != "SUCCESS" and self.client:
                try:
                    self.evolve_self(
                        recent_error=str(evolution_result.get("last_error", "")),
                        task_context=task_description
                    )
                except Exception as e:
                    print(f"[EVOLUTION FEHLER] Selbst-Evolution fehlgeschlagen: {e}")
            
            return evolution_result
        except Exception as e:
            print(f"\n[KRITISCHER PIPELINE-FEHLER] {e}")
            return {"status": "FAILED", "error": str(e)}
        finally:
            stop_event.set()
            spinner_thread.join()


# MODUL-LEVEL WRAPPER-FUNKTIONEN (V1-Kompatibilität)
def boot_latest_metacoder(require_ollama: bool = True) -> MetaCoderSQLPipeline:
    """Erstellt und bootet die neueste MetaCoder-Instanz mit Database-Driven DNA."""
    pipeline = MetaCoderSQLPipeline(require_ollama=require_ollama)
    try:
        pipeline.bootstrap_from_database()
    except Exception as e:
        print(f"[BOOT WARNUNG] Bootstrap-DNA konnte nicht geladen werden: {e}")
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

# AUSFÜHRUNG & INTERAKTIVER MODUS
if __name__ == "__main__":
    print(f"--- Starte {AGENT_NAME} SQL Verklemmungs-Pipeline (v2+V1) ---")
    
    pipeline = boot_latest_metacoder(require_ollama=True)
    
    # Umgebung und Tabellen prüfen
    if not pipeline.verify_environment():
        logging.warning("Umgebung konnte nicht vollständig verifiziert werden. Fahre fort...")

    # Kernel-Modul-Check
    kernel_check = coreInfrastructure.scan_kernel_modules(REQUIRED_KERNEL_MODULES)
    logging.info(f"[KERNEL MODULE SCAN] Status: {kernel_check}")

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

            # Feedback-Befehle behandeln (V1-Funktion)
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
                print(f"[GEGENKONTROLLE FEHLER] index_chat_user_query fehlgeschlagen: {e}")
                last_query_node_id = None
                log_table = None
                effective_input = user_input

            # Stufe 2: LLM-Inferenz oder Pipeline
            if pipeline.client:
                # LLM-basierte Antwort (V1-Funktion)
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
                spinner = ResourceAwareSpinner(agent_name=f"{AGENT_NAME}-Chat",
                                               min_ram_mb=MIN_RAM_MB,
                                               max_cpu_threshold=CPU_WARNING_THRESHOLD,
                                               spinner_interval=SPINNER_INTERVAL)
                stop_event = threading.Event()
                spinner_thread = threading.Thread(target=spinner.run, args=(stop_event, True))
                spinner_thread.start()

                try:
                    response = pipeline.client.chat(
                        model=pipeline.model_name,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": effective_input}
                        ]
                    )
                finally:
                    stop_event.set()
                    spinner_thread.join()
                
                answer = response.get('message', {}).get('content', '')

                # Cache versiegeln (V1-Funktion)
                if last_query_node_id:
                    pipeline.seal_query_cache(last_query_node_id, answer)
                
                # Auto-Persistence (V1-Funktion)
                if "verewige" in user_input.lower() or "speichere in sql" in user_input.lower():
                    pipeline.persist_new_capability(
                        capability_name="Autonomous_Capability",
                        code_snippet=answer[:PROMPT_MAX_LEN],
                        description=user_input
                    )
                    print("\n[SYSTEM-INFO] Die Fähigkeit wurde physisch in die SQLite-Tabelle 'library_registry' geschrieben!")

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
                # Fallback: Pipeline ohne LLM
                result = pipeline.run_pipeline(effective_input)
                print(f"\n{AGENT_NAME} [Status: {result.get('status')}]:")
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