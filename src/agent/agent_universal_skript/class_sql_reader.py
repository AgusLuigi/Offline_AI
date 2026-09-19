import os
import sqlite3
from datetime import datetime
from pathlib import Path


class class_sql_reader:

    def seal_query_cache(self, node_id: str, answer: str, snippet: str = ""):
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

    def check_or_cache_user_query(self, raw_query: str) -> dict:
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

    @staticmethod
    def initialize_blueprint_system(user_input: str) -> dict:
        """Initialisiert das Blueprint-System für die Anforderung."""
        return {"status": "INITIALIZED", "query": user_input}

    def _save_solution_to_db(self, task_description: str, error_msg: str, solution_code: str):
        """Protokolliert Interaktionsmuster und Lösungen im Routing Tree."""
        domain = self._detect_domain(task_description)
        node_id = f"LOG_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        with self.get_db_connection() as conn:
            self._insert_routing_node(
                conn=conn,
                table_name="table_issue_data_time_stamp_run_protocol_for_query",
                node_id=node_id,
                topic_title=f"Pattern in [{domain}]",
                topic_specification=task_description[:200],
                agent_instruction=error_msg.strip().split('\n')[-1][:200],
                example_code_snippet=solution_code,
                validation_rule="protocol_logged == TRUE",
                target_table=domain
            )
        print(f"[SQL-KNOWLEDGE] Eintrag erfolgreich in Protokolltabelle verankert.")

    def _detect_domain(self, task_description: str) -> str:
        """Erkennt anhand von Schlüsselwörtern die relevante Zieltabelle/Domain."""
        desc_lower = task_description.lower()
        if any(k in desc_lower for k in ["sql", "database", "query", "sqlite", "postgres"]):
            return "sql_domain"
        elif any(k in desc_lower for k in ["docker", "container", "traefik", "ollama"]):
            return "infrastructure_domain"
        else:
            return "python_domain"

    def _init_database(self):
        """Initialisiert grundlegende Tabellen, falls diese noch nicht existieren."""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
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
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS table_issue_data_time_stamp_run_protocol_for_query (
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

    def _insert_routing_node(self, conn, table_name: str, node_id: str, topic_title: str,
                             topic_specification: str, agent_instruction: str,
                             example_code_snippet: str, validation_rule: str,
                             target_table: str = "", target_node_id: str = "000"):
        """Fügt einen neuen Knoten in eine beliebige Routing-Tabelle ein."""
        now = datetime.now()
        cursor = conn.cursor()
        cursor.execute(f"""
            INSERT OR REPLACE INTO {table_name} (
                node_id, is_active, error_fallback_count,
                year, month, day, hour, minute, second,
                topic_title, topic_specification, agent_instruction,
                example_code_snippet, validation_rule, execution_count,
                success_weight, target_table, target_column_id, target_node_id
            ) VALUES (?, 1, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1.0, ?, 'node_id', ?)
        """, (
            node_id, now.year, now.month, now.day, now.hour, now.minute, now.second,
            topic_title, topic_specification, agent_instruction,
            example_code_snippet, validation_rule, target_table, target_node_id
        ))
        conn.commit()

    def _save_solution_to_db(self, task_description: str, error_msg: str, solution_code: str):
        """Protokolliert Interaktionsmuster und Lösungen im Routing Tree."""
        domain = self._detect_domain(task_description)
        node_id = f"LOG_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        with self.get_db_connection() as conn:
            self._insert_routing_node(
                conn=conn,
                table_name="table_issue_data_time_stamp_run_protocol_for_query",
                node_id=node_id,
                topic_title=f"Pattern in [{domain}]",
                topic_specification=task_description[:200],
                agent_instruction=error_msg.strip().split('\n')[-1][:200],
                example_code_snippet=solution_code,
                validation_rule="protocol_logged == TRUE",
                target_table=domain
            )
        print(f"[SQL-KNOWLEDGE] Eintrag erfolgreich in Protokolltabelle verankert.")

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

    def test_and_evolve_loop(self, specialization: str, task_description: str, base_filename: str, max_generations: int = 3):
        """Führt den Test- und Evolutions-Zyklus aus."""
        print(f"[METABASE] Starte Test- und Evolutions-Schleife für: {specialization}")
        return f"Evolutions-Schleife für {task_description} erfolgreich initialisiert."

    def record_feedback(self, query_node_id: str, is_positive: bool, comment: str = "") -> dict:
        """Verarbeitet Benutzer-Feedback und aktualisiert Gewichte."""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            if is_positive:
                cursor.execute("""
                    UPDATE user_query
                    SET success_weight = success_weight + 0.2,
                        validation_rule = 'POSITIVE_VERIFIED'
                    WHERE node_id = ?
                """, (query_node_id,))
                conn.commit()
                return {"status": "success", "feedback": "positive", "node_id": query_node_id}
            else:
                return self.deactivate_and_reroute("user_query", query_node_id, failure_reason=comment or "Negatives Feedback")

    def persist_new_capability(self, capability_name: str, code_snippet: str, description: str):
        """Speichert eine neue Fähigkeit dauerhaft in der Registry."""
        with self.get_db_connection() as conn:
            self._insert_routing_node(
                conn=conn,
                table_name="library_registry" if "library_registry" in [row[0] for row in conn.cursor().execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()] else "user_query",
                node_id=f"CAP_{datetime.now().strftime('%H%M%S')}",
                topic_title=capability_name,
                topic_specification=description,
                agent_instruction="CAPABILITY_REGISTERED",
                example_code_snippet=code_snippet,
                validation_rule="VERIFIED"
            )

    def query_meta_coder_sql(notebook_path: str, instruction: str):
        metacoder = boot_latest_metacoder()
        spec = f"Hierarchical Routing Tree SQL Agent for {Path(notebook_path).name}"
        task = f"""
        Target Notebook/Module Path: {notebook_path}
        User Instruction/Routing Goal: {instruction}
        """
        return metacoder.test_and_evolve_loop(
            specialization=spec,
            task_description=task,
            base_filename=f"sql_routing_agent_{Path(notebook_path).stem}",
            max_generations=3
        )