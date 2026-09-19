import os
import sqlite3
from datetime import datetime
from pathlib import Path


class class_sql_reader:
    @staticmethod
    def initialize_blueprint_system(user_input: str) -> dict:
        """Initialisiert das Blueprint-System für die Anforderung."""
        return {"status": "INITIALIZED", "query": user_input}

    def get_cached_or_create_query(self, raw_query: str) -> dict:
        """Prüft den Cache oder registriert eine neue Anfrage."""
        cleaned_query = raw_query.strip().lower()
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
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
            
            cursor.execute("SELECT node_id FROM user_query")
            existing_ids = {int(row[0]) for row in cursor.fetchall() if row[0].isdigit()}
            
            next_id_num = next((c for c in range(3, 999) if c not in existing_ids), 998)
            next_node_id = f"{next_id_num:03d}"
            
            self._insert_routing_node(
                conn=conn,
                table_name="user_query",
                node_id=next_node_id,
                topic_title=f"USER QUERY: {raw_query[:35]}",
                topic_specification=raw_query,
                agent_instruction="PROCESSING",
                example_code_snippet="",
                validation_rule="PENDING_EXECUTION",
                target_table="pre_execution_blueprint_generator"
            )
            
            return {
                "cache_hit": False,
                "node_id": next_node_id,
                "query": raw_query,
                "status": "PENDING_EXECUTION"
            }

    def store_query_result(self, node_id: str, answer: str, snippet: str = ""):
        """Versiegelt eine erfolgreich beantwortete Anfrage im Cache."""
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

    # LOG & PROTOCOL
    def log_save_query_run_to_db_timestamp(self, task_description: str, error_msg: str, solution_code: str, run_id: str = None):
        """
        Protokolliert Mikroschritte und holt den verbindlichen Zeitstempel direkt aus der Datenbank; 
        steuert die fortlaufende Append-Protokollierung und Crash-Wiederherstellung über run_id (als dynamic_table_name_Zeitstempel) und eindeutige node_id-Einträge.
        """
        domain = self._detect_domain(task_description)
        
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Wenn keine Run-ID übergeben wurde, holen wir den echten Zeitstempel des ersten Eintrags aus der DB
            if not run_id:
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
                    # Absoluter Fallfalls-Fallback, falls die Tabelle leer sein sollte
                    now = datetime.now()
                    year, month, day, hour, minute, second = now.year, now.month, now.day, now.hour, now.minute, now.second
                    run_id = now.strftime('%Y%m%d_%H%M%S')
            else:
                # Falls eine Run-ID übergeben wurde, leiten wir die Zeitkomponenten daraus ab
                try:
                    dt = datetime.strptime(run_id, '%Y%m%d_%H%M%S')
                    year, month, day, hour, minute, second = dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second
                except ValueError:
                    now = datetime.now()
                    year, month, day, hour, minute, second = now.year, now.month, now.day, now.hour, now.minute, now.second

            # Dynamischer Tabellenname basierend auf dem echten DB-Zeitstempel
            dynamic_table_name = f"run_protocol_{run_id}"
            node_id = f"STEP_{hour:02d}{minute:02d}{second:02d}_{datetime.now().strftime('%f')}"
            
            # 2. Crash-Wiederherstellung & Status-Prüfung
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (dynamic_table_name,))
            table_already_exists = cursor.fetchone() is not None
            
            if table_already_exists:
                print(f"[RECOVERY] Tabelle '{dynamic_table_name}' existiert bereits. Setze fort mit echtem DB-Zeitstempel.")
            
            # 3. Dynamische Tabelle erstellen, falls sie noch nicht existiert
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
            
            # 4. Mikroschritt schreiben
            step_title = f"Step in [{domain}]"
            if table_already_exists:
                step_title += " (Resumed)"
                
            self._insert_routing_node(
                conn=conn,
                table_name=dynamic_table_name,
                node_id=node_id,
                topic_title=step_title,
                topic_specification=task_description[:200],
                agent_instruction=error_msg.strip().split('\n')[-1][:200] if error_msg else "RUN_STEP_SUCCESS",
                example_code_snippet=solution_code,
                validation_rule="step_logged == TRUE",
                target_table=domain
            )
            
            # 5. Exakte Zeitstempel-Werte (aus der DB geholt) in den Datensatz schreiben
            cursor.execute(f"""
                UPDATE {dynamic_table_name}
                SET year = ?, month = ?, day = ?, hour = ?, minute = ?, second = ?
                WHERE node_id = ?
            """, (year, month, day, hour, minute, second, node_id))
            conn.commit()
            
        print(f"[SQL-KNOWLEDGE] Protokollschritt mit DB-Zeitstempel in '{dynamic_table_name}' verankert.")

    def _detect_domain(self, task_description: str) -> str:
        """Erkennt anhand einer zentralen Definition (Heuristik & TF-IDF kombiniert) die relevante Zieltabelle/Domain."""
        import importlib.util
        import subprocess
        import sys

        # Auto-Import & Dependency Check für scikit-learn und numpy
        required_packages = {"sklearn": "scikit-learn", "numpy": "numpy"}
        for module_name, pip_name in required_packages.items():
            if importlib.util.find_spec(module_name) is None:
                print(f"[AUTO-INSTALL] Paket '{pip_name}' nicht gefunden. Installiere es automatisch...")
                subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])

        # Bibliotheken nach erfolgreicher Prüfung importieren
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np

        desc_lower = task_description.lower()
        
        # Zentraler Korpus: Domain und ihre zugehörigen Schlüsselwörter (gleichermaßen für Fast-Path & TF-IDF)
        domain_data = {
            "sql_domain": ["sql", "database", "query", "sqlite", "postgres", "select", "insert", "update", "table"],
            "infrastructure_domain": ["docker", "container", "traefik", "ollama", "deployment", "server", "network"],
            "fehlererkennung": ["bug", "fix", "error", "exception", "debugging", "crash", "stacktrace", "failure"],
            "logische_anfrage": ["bedingung", "logik", "berechnen", "vergleichen", "auswerten", "algorithmus", "verständnis"],
            "python_domain": ["python", "script", "code", "function", "variables", "data", "science"]
        }
        
        # STUFE 1: Fast-Path Heuristik (Dynamisch aus den zentralen Listen generiert)
        for domain, keywords in domain_data.items():
            if any(kw in desc_lower for kw in keywords[:5]): # Nutzt die ersten wichtigsten Begriffe für den Schnellstart
                return domain
                
        # STUFE 2: Stochastische Vektor-Analyse (Fuzzy Matching über Kosinus-Ähnlichkeit)
        domain_corpus = {domain: " ".join(words) for domain, words in domain_data.items()}
        domain_keys = list(domain_corpus.keys())
        
        vectorizer = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform(list(domain_corpus.values()))
        task_vector = vectorizer.transform([task_description])
        cosine_sim = cosine_similarity(task_vector, tfidf_matrix).flatten()
        
        total_sim = np.sum(cosine_sim)
        if total_sim > 0:
            probabilities = cosine_sim / total_sim
            best_idx = np.argmax(probabilities)
            
            # Schwellenwert-Prüfung
            if probabilities[best_idx] < 0.15:
                return "python_domain"
                
            return domain_keys[best_idx]
        
        # STUFE 3: Standard-Fallback
        return "python_domain"

    def fetch_records(self, table_name: str, active_only: bool = True):
        """
        Liest alle Datensätze aus der angegebenen Tabelle aus.
        Unterstützt die Standard-Tabellen und prüft die Integrität.
        """
        allowed_tables = {
            "user_query",
            "table_issue_data_time_stamp_run_protocol_for_query"
        }
        
        if table_name not in allowed_tables:
            raise ValueError(f"Tabelle '{table_name}' ist nicht in der Registry zugelassen.")

        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Basis-Abfrage unter Berücksichtigung des Status (is_active)
            if active_only:
                query = f"SELECT * FROM {table_name} WHERE is_active = 1 ORDER BY year DESC, month DESC, day DESC, hour DESC, minute DESC, second DESC"
            else:
                query = f"SELECT * FROM {table_name} ORDER BY year DESC, month DESC, day DESC, hour DESC, minute DESC, second DESC"
                
            cursor.execute(query)
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
            
            # Optional: Rückgabe als Liste von Dictionaries für eine einfachere Weiterverarbeitung
            result = [dict(zip(columns, row)) for row in rows]
            return result

    def fetch_single_node(self, table_name: str, node_id: str):
        """Liest einen spezifischen Knoten anhand seiner node_id aus."""
        allowed_tables = {
            "user_query",
            "table_issue_data_time_stamp_run_protocol_for_query"
        }
        
        if table_name not in allowed_tables:
            raise ValueError(f"Tabelle '{table_name}' ist unzulässig.")

        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {table_name} WHERE node_id = ?", (node_id,))
            row = cursor.fetchone()
            
            if row:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            return None

    def _insert_routing_node(self, conn, table_name: str, node_id: str, 
                             topic_title: str = "", topic_specification: str = "", 
                             agent_instruction: str = "", example_code_snippet: str = "", 
                             validation_rule: str = "", target_table: str = "", 
                             target_node_id: str = "000", **kwargs):
        """Fügt einen neuen Knoten minimal, performant und dynamisch anhand des Live-Schemas ein."""
        cursor = conn.cursor()
        
        # Live-Schema direkt aus der SQL-Datenbank auslesen
        cursor.execute(f"PRAGMA table_info({table_name})")
        actual_columns = {row[1] for row in cursor.fetchall()}
        
        if not actual_columns:
            raise ValueError(f"Tabelle '{table_name}' existiert nicht oder ist leer.")

        now = datetime.now()
        
        # Alle Werte, Zeitstempel und Parameter in einem sauberen Dictionary bündeln
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
        
        # Dynamischer Abgleich: Nur Spalten verwenden, die die Live-Tabelle aktuell besitzt
        filtered_data = {k: v for k, v in payload.items() if k in actual_columns}
        
        # SQL-Statement generieren und ausführen
        cols = ", ".join(filtered_data.keys())
        placeholders = ", ".join(["?"] * len(filtered_data))
        
        cursor.execute(
            f"INSERT OR REPLACE INTO {table_name} ({cols}) VALUES ({placeholders})", 
            list(filtered_data.values())
        )
        conn.commit()

    def deactivate_and_reroute(self, table_name: str, node_id: str, failure_reason: str) -> dict:
        """Deaktiviert fehlerhafte Knoten und leitet auf Alternativpfade um."""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                UPDATE {table_name}
                SET is_active = 0, error_fallback_count = error_fallback_count + 1
                WHERE node_id = ?
            """, (node_id,))
            
            cursor.execute(f"""
                SELECT node_id, topic_title, target_table, target_node_id
                FROM {table_name}
                WHERE is_active = 1 AND node_id != ?
                ORDER BY success_weight DESC LIMIT 1
            """, (node_id,))
            alt_row = cursor.fetchone()
            conn.commit()
        return {
            "deactivated_node": node_id,
            "table_name": table_name,
            "reason": failure_reason,
            "alternative_available": alt_row is not None,
            "next_node": alt_row[0] if alt_row else "000",
            "next_target": alt_row[2] if alt_row and alt_row[2] else "FX_CHAIN"
        }