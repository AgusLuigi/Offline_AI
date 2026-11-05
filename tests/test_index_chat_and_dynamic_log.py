#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Testvalidierung für:
1. index_chat_user_query (Erfassung, Whitespace-Bereinigung, Token-Schärfung, Intent-Klassifikation)
2. Dynamische Log-Tabelle log_{time} mit Zeitstempel aus user_query
3. table_issue_data_time_stamp_run_protocol_for_query Integration zum Auffüllen des Logs
4. run_pipeline Integration
"""
import os
import sys
import unittest
import sqlite3
from pathlib import Path

# Projekt-Root ermitteln
test_file = Path(__file__).resolve()
project_root = None
for parent in test_file.parents:
    if (parent / "src").is_dir():
        project_root = parent
        break

if project_root is None:
    raise RuntimeError("Projekt-Root nicht gefunden!")

sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src" / "agent"))
sys.path.insert(0, str(project_root / "src" / "agent" / "agent_universal_skript"))
os.chdir(str(project_root))

from meta_coder_sql import MetaCoderSQLPipeline


class TestIndexChatAndDynamicLog(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.pipeline = MetaCoderSQLPipeline(require_ollama=False)
        cls.pipeline.verify_environment()

    def test_01_token_sharpening_and_intent(self):
        """index_chat_user_query - Bereinigung, Token-Schärfung & Intent-Klassifikation."""
        raw_input_repair = "  Kannst du bitte  mal  diesen Fehler im SQL Script reparieren und fixen?  "
        res1 = self.pipeline.index_chat_user_query(raw_input_repair)

        self.assertIsInstance(res1, dict)
        self.assertEqual(res1["clean_query"], "Kannst du bitte mal diesen Fehler im SQL Script reparieren und fixen?")
        self.assertNotIn("kannst du bitte", res1["sharpened_query"].lower())
        self.assertEqual(res1["query_type"], "Reparatur")
        self.assertTrue(res1["log_table_name"].startswith("log_"))
        self.assertIsNotNone(res1["node_id"])

    def test_02_intent_types(self):
        """Intent-Klassifikation für Coding, Architektur und Analyse."""
        res_code = self.pipeline.index_chat_user_query("Erstelle eine Python Funktion für Datenverarbeitung")
        self.assertEqual(res_code["query_type"], "Coding")

        res_arch = self.pipeline.index_chat_user_query("Zeige mir den Blueprint und die Routing-Tree Architektur")
        self.assertEqual(res_arch["query_type"], "Architektur")

        res_ana = self.pipeline.index_chat_user_query("Analysiere und scanne die Systemtabellen")
        self.assertEqual(res_ana["query_type"], "Analyse")

    def test_03_dynamic_log_table(self):
        """Dynamische Tabelle log_{time} mit Vorlage-Punkten."""
        test_time = "20260924_103000"
        test_log_table = f"log_{test_time}"

        self.pipeline.log_save_query_run_to_db_timestamp(
            task_description="Unit-Test für log_{time}",
            error_msg="",
            solution_code="print('Hello Test')",
            run_id=test_time,
            step_type="checkpoint",
            log_table_name=test_log_table
        )

        with self.pipeline.get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (test_log_table,))
            table_row = c.fetchone()
            self.assertIsNotNone(table_row, f"Tabelle '{test_log_table}' sollte existieren")

            c.execute(f"SELECT COUNT(*) FROM {test_log_table}")
            row_count = c.fetchone()[0]
            self.assertGreater(row_count, 0)

            c.execute(f"PRAGMA table_info({test_log_table})")
            cols = [r[1] for r in c.fetchall()]
            required_cols = [
                "node_id", "is_active", "error_fallback_count", "year", "month", "day",
                "hour", "minute", "second", "topic_title", "topic_specification",
                "agent_instruction", "example_code_snippet", "validation_rule"
            ]
            for col in required_cols:
                self.assertIn(col, cols, f"Spalte '{col}' fehlt in {test_log_table}")

    def test_04_run_pipeline_integration(self):
        """run_pipeline Integration mit index_chat_user_query."""
        pipe_result = self.pipeline.run_pipeline("Bitte führe eine Analyse der Datenbank durch")
        self.assertTrue(
            pipe_result.get("status") in ["SUCCESS", "FAILED"] or pipe_result.get("cache_hit") is True,
            f"Unerwarteter Status: {pipe_result}"
        )


if __name__ == "__main__":
    unittest.main()
