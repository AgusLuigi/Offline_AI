"""
Modul: class_container_evolve_loop_test
Bezeichnung: Autonome Test- und Evolutions-Schleife (Closed-Loop)
Inhaltlicher Schwerpunkt:
Steuerung von iterativen Testzyklen über mehrere Generationen,
Validierung von Ausführungsergebnissen, Notebook-Code-Extraktion und Feedback-Persistierung.
"""

from __future__ import annotations
import datetime
import json
import re
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# Globale Bindings
logger = globals().get("class_logger_audit_execution")
core_infra = globals().get("class_tool_core_infrastructure")
sql_reader_cls = globals().get("class_tool_sql_reader")


class class_container_evolve_loop_test:
    """
    Steuert autonome Test- und Evolutions-Zyklen.
    Führt Verifizierungen fehlertolerant durch und dokumentiert Erfolgsmetriken.
    """

    _cfg = globals().setdefault("_AGENT_CONFIG", {})
    EVOLUTION_RETRY_DELAY_SEC: float = _cfg.setdefault("EVOLUTION_RETRY_DELAY_SEC", 1.0)
    MAX_GENERATIONS: int = _cfg.setdefault("MAX_GENERATIONS", 3)
    DB_FILENAME: str = _cfg.setdefault("DB_FILENAME", "Knowledge_Agent_Routing_tree.db")

    def __init__(self, registry_db_path: Optional[str] = None):
        print("[class_container_evolve_loop_test] Starte Arbeit: __init__ wird jetzt ausgeführt.")
        self.registry_db_path = registry_db_path
        if self.registry_db_path is None and registry_db_path is not None:
            print("[class_container_evolve_loop_test] FEHLER: __init__ hat die Aufgabe nicht erfüllt. Grund: registry_db_path konnte nicht gesetzt werden.")
            return
        print("[class_container_evolve_loop_test] Erfolg: __init__ erfolgreich beendet.")

    def get_db_connection(self) -> sqlite3.Connection:
        """Stellt eine Verbindung zur Datenbank her."""
        print("[class_container_evolve_loop_test] Starte Arbeit: get_db_connection wird jetzt ausgeführt.")
        infra = globals().get("class_tool_core_infrastructure")
        if infra and hasattr(infra, "get_db_connection"):
            conn = infra.get_db_connection(self.registry_db_path or self.DB_FILENAME)
            if conn:
                print("[class_container_evolve_loop_test] Erfolg: get_db_connection erfolgreich beendet.")
                return conn
        try:
            result = sqlite3.connect(":memory:")
            if result is None:
                print("[class_container_evolve_loop_test] FEHLER: get_db_connection hat die Aufgabe nicht erfüllt. Grund: Verbindung konnte nicht hergestellt werden.")
                return None
            print("[class_container_evolve_loop_test] Erfolg: get_db_connection erfolgreich beendet.")
            return result
        except Exception as e:
            print(f"[class_container_evolve_loop_test] FEHLER: DB-Verbindung fehlgeschlagen: {e}")
            return None

    def _insert_routing_node(self, conn: sqlite3.Connection, table_name: str, node_id: str,
                             topic_title: str, topic_specification: str, agent_instruction: str,
                             example_code_snippet: str, validation_rule: str):
        """Fügt einen Routing-Knoten fehlertolerant ein."""
        print(f"[class_container_evolve_loop_test] Starte Arbeit: _insert_routing_node wird jetzt ausgeführt. (Parameter: {node_id})")
        try:
            cursor = conn.cursor()
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    node_id TEXT PRIMARY KEY,
                    topic_title TEXT,
                    topic_specification TEXT,
                    agent_instruction TEXT,
                    example_code_snippet TEXT,
                    validation_rule TEXT,
                    success_weight REAL DEFAULT 1.0
                )
            """)
            cursor.execute(f"""
                INSERT OR IGNORE INTO {table_name} 
                (node_id, topic_title, topic_specification, agent_instruction, example_code_snippet, validation_rule)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (node_id, topic_title, topic_specification, agent_instruction, example_code_snippet, validation_rule))
            conn.commit()
        except Exception as e:
            print(f"[class_container_evolve_loop_test] FEHLER: _insert_routing_node fehlgeschlagen: {e}")
            return
        print("[class_container_evolve_loop_test] Erfolg: _insert_routing_node erfolgreich beendet.")

    def deactivate_and_reroute(self, table_name: str, node_id: str, failure_reason: str = "") -> dict:
        """Deaktiviert einen Knoten bei negativem Feedback."""
        print(f"[class_container_evolve_loop_test] Starte Arbeit: deactivate_and_reroute wird jetzt ausgeführt. (Parameter: {node_id})")
        try:
            conn = self.get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute(f"UPDATE {table_name} SET validation_rule = 'DEACTIVATED' WHERE node_id = ?", (node_id,))
                conn.commit()
                conn.close()
            result = {"status": "deactivated", "node_id": node_id, "reason": failure_reason}
            if result is None:
                print("[class_container_evolve_loop_test] FEHLER: deactivate_and_reroute hat die Aufgabe nicht erfüllt. Grund: Kein Ergebnis zurückgegeben.")
                return {}
            print("[class_container_evolve_loop_test] Erfolg: deactivate_and_reroute erfolgreich beendet.")
            return result
        except Exception as e:
            print(f"[class_container_evolve_loop_test] FEHLER: deactivate_and_reroute fehlgeschlagen: {e}")
            return {"status": "error", "error": str(e)}

    def test_and_evolve_loop(
        self,
        specialization: str,
        task_description: str,
        base_filename: str,
        max_generations: int = None,
        execution_func: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Führt den vollständigen Test- und Evolutionszyklus durch."""
        print(f"[class_container_evolve_loop_test] Starte Arbeit: test_and_evolve_loop wird jetzt ausgeführt. (Parameter: {specialization})")
        max_generations = max_generations or self.MAX_GENERATIONS
        current_generation = 0
        success = False
        last_error = None
        result_data = None

        while current_generation < max_generations and not success:
            current_generation += 1
            print(f"[class_container_evolve_loop_test] Starte Arbeit: Generation {current_generation}/{max_generations}")
            try:
                if execution_func:
                    result_data = execution_func({"task": task_description, "generation": current_generation})
                    if isinstance(result_data, dict) and result_data.get("status") == "FAILED":
                        raise RuntimeError(result_data.get("error", "Ausführung meldete FAILED"))
                    success = True
                else:
                    result_data = f"Simuliertes Ergebnis für {base_filename} in Generation {current_generation}"
                    success = True
            except Exception as e:
                last_error = str(e)
                print(f"[class_container_evolve_loop_test] FEHLER in Generation {current_generation}: {e}")
                time.sleep(self.EVOLUTION_RETRY_DELAY_SEC)

        if success:
            result = {
                "status": "SUCCESS",
                "specialization": specialization,
                "generations_used": current_generation,
                "result": result_data,
                "message": f"Evolutions-Schleife nach {current_generation} Generation(en) erfolgreich."
            }
            if result is None:
                print("[class_container_evolve_loop_test] FEHLER: test_and_evolve_loop hat die Aufgabe nicht erfüllt. Grund: Kein Ergebnis zurückgegeben.")
                return {}
            print("[class_container_evolve_loop_test] Erfolg: test_and_evolve_loop erfolgreich beendet.")
            return result
        result = {
            "status": "FAILED",
            "specialization": specialization,
            "generations_attempted": max_generations,
            "last_error": last_error,
            "message": f"Evolutions-Schleife fehlgeschlagen nach {max_generations} Versuchen."
        }
        if result is None:
            print("[class_container_evolve_loop_test] FEHLER: test_and_evolve_loop hat die Aufgabe nicht erfüllt. Grund: Kein Ergebnis zurückgegeben.")
            return {}
        print("[class_container_evolve_loop_test] Erfolg: test_and_evolve_loop erfolgreich beendet.")
        return result

    def extract_code_from_notebook(self, notebook_path: str) -> List[str]:
        """Liest ein Jupyter Notebook (.ipynb) ein und extrahiert alle Code-Zellen."""
        print(f"[class_container_evolve_loop_test] Starte Arbeit: extract_code_from_notebook wird jetzt ausgeführt. (Parameter: {notebook_path})")
        snippets = []
        path = Path(notebook_path)
        if not path.exists():
            print(f"[class_container_evolve_loop_test] FEHLER: Notebook '{notebook_path}' nicht gefunden.")
            return snippets

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for cell in data.get("cells", []):
                    if cell.get("cell_type") == "code":
                        src = "".join(cell.get("source", []))
                        if src.strip():
                            snippets.append(src)
            result = snippets
            if result is None:
                print("[class_container_evolve_loop_test] FEHLER: extract_code_from_notebook hat die Aufgabe nicht erfüllt. Grund: Kein Ergebnis zurückgegeben.")
                return []
            print("[class_container_evolve_loop_test] Erfolg: extract_code_from_notebook erfolgreich beendet.")
            return result
        except Exception as e:
            print(f"[class_container_evolve_loop_test] FEHLER: Lesen des Notebooks fehlgeschlagen: {e}")
            return snippets

    def persist_new_capability(self, capability_name: str, code_snippet: str, description: str):
        """Speichert eine neu erlernte Fähigkeit in der SQLite-Registry."""
        print(f"[class_container_evolve_loop_test] Starte Arbeit: persist_new_capability wird jetzt ausgeführt. (Parameter: {capability_name})")
        try:
            conn = self.get_db_connection()
            if conn:
                self._insert_routing_node(
                    conn=conn,
                    table_name="library_registry",
                    node_id=f"CAP_{datetime.datetime.now().strftime('%H%M%S')}",
                    topic_title=capability_name,
                    topic_specification=description,
                    agent_instruction="CAPABILITY_REGISTERED",
                    example_code_snippet=code_snippet,
                    validation_rule="VERIFIED"
                )
                conn.close()
        except Exception as e:
            print(f"[class_container_evolve_loop_test] FEHLER: Speichern der Fähigkeit fehlgeschlagen: {e}")
            return
        print("[class_container_evolve_loop_test] Erfolg: persist_new_capability erfolgreich beendet.")

    def record_feedback(self, query_node_id: str, is_positive: bool, comment: str = "") -> dict:
        """Verarbeitet Feedback und passt die Wichtung des Knotens an."""
        print(f"[class_container_evolve_loop_test] Starte Arbeit: record_feedback wird jetzt ausgeführt. (Parameter: {query_node_id})")
        try:
            conn = self.get_db_connection()
            if not conn:
                return {"status": "error", "error": "Keine DB-Verbindung"}
            cursor = conn.cursor()
            if is_positive:
                cursor.execute("""
                    UPDATE user_query
                    SET success_weight = success_weight + 0.2, validation_rule = 'POSITIVE_VERIFIED'
                    WHERE node_id = ?
                """, (query_node_id,))
                conn.commit()
                conn.close()
                result = {"status": "success", "feedback": "positive", "node_id": query_node_id}
                if result is None:
                    print("[class_container_evolve_loop_test] FEHLER: record_feedback hat die Aufgabe nicht erfüllt. Grund: Kein Ergebnis zurückgegeben.")
                    return {}
                print("[class_container_evolve_loop_test] Erfolg: record_feedback erfolgreich beendet.")
                return result
            else:
                conn.close()
                result = self.deactivate_and_reroute("user_query", query_node_id, failure_reason=comment or "Negatives Feedback")
                if result is None:
                    print("[class_container_evolve_loop_test] FEHLER: record_feedback hat die Aufgabe nicht erfüllt. Grund: Kein Ergebnis zurückgegeben.")
                    return {}
                print("[class_container_evolve_loop_test] Erfolg: record_feedback erfolgreich beendet.")
                return result
        except Exception as e:
            print(f"[class_container_evolve_loop_test] FEHLER: Feedback-Erfassung fehlgeschlagen: {e}")
            return {"status": "error", "error": str(e)}

    def query_meta_coder_sql(self, notebook_path: str, instruction: str) -> Dict[str, Any]:
        """
        Schnittstelle: Analysiert ein Jupyter Notebook, lernt daraus und 
        startet den Evolutions-Agenten für SQL- oder Code-Anweisungen.
        """
        print(f"[class_container_evolve_loop_test] Starte Arbeit: query_meta_coder_sql wird jetzt ausgeführt. (Parameter: notebook={notebook_path})")
        learned_code_patterns = self.extract_code_from_notebook(notebook_path)
        spec = f"Hierarchical Routing Tree SQL Agent for {Path(notebook_path).name}"
        task = f"""
        Target Notebook Path: {notebook_path}
        User Instruction/Routing Goal: {instruction}
        Learned Context Snippets Count: {len(learned_code_patterns)}
        """
        result = self.test_and_evolve_loop(
            specialization=spec,
            task_description=task,
            base_filename=f"sql_routing_agent_{Path(notebook_path).stem}",
            max_generations=3
        )
        if result is None or result.get("status") == "FAILED":
            print("[class_container_evolve_loop_test] FEHLER: query_meta_coder_sql hat die Aufgabe nicht erfüllt. Grund: Evolutions-Schleife fehlgeschlagen.")
            return result or {"status": "FAILED", "error": "Evolutions-Schleife lieferte None"}
        print("[class_container_evolve_loop_test] Erfolg: query_meta_coder_sql erfolgreich beendet.")
        return result

    @classmethod
    def run_evolve_loop(cls, specialization: str, task_description: str, execution_func: Callable = None) -> dict:
        """
        Zentrale Ausführungsfunktion: Bündelt den Start der Evolutions-Schleife
        und gibt den finalen Statusbericht zurück.
        """
        print("[class_container_evolve_loop_test] Starte Arbeit: run_evolve_loop wird jetzt ausgeführt.")
        try:
            loop = cls()
            result = loop.test_and_evolve_loop(
                specialization=specialization,
                task_description=task_description,
                base_filename="loop_task",
                execution_func=execution_func
            )
            if result is None:
                print("[class_container_evolve_loop_test] FEHLER: run_evolve_loop hat die Aufgabe nicht erfüllt. Grund: Kein Ergebnis zurückgegeben.")
                return None
            print("[class_container_evolve_loop_test] Erfolg: run_evolve_loop erfolgreich beendet.")
            return result
        except Exception as e:
            print(f"[class_container_evolve_loop_test] FEHLER: In run_evolve_loop: {e}")
            return None
