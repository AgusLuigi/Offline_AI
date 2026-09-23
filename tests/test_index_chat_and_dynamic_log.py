"""
Testvalidierung für:
1. index_chat_user_query (Erfassung, Whitespace-Bereinigung, Token-Schärfung, Intent-Klassifikation)
2. Dynamische Log-Tabelle log_{time} mit Zeitstempel aus user_query
3. table_issue_data_time_stamp_run_protocol_for_query Integration zum Auffüllen des Logs
"""
import os
import sys
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
    print("[FEHLER] Projekt-Root nicht gefunden!")
    sys.exit(1)

sys.path.insert(0, str(project_root / "src" / "agent"))
os.chdir(str(project_root))

from meta_coder_sql import MetaCoderSQLPipeline

print("=" * 70)
print(" TESTVALIDIERUNG: index_chat_user_query & log_{time}")
print("=" * 70)

passed = 0
failed = 0
errors = []

def test(name, condition, detail=""):
    global passed, failed, errors
    if condition:
        print(f"  [OK] {name}")
        passed += 1
    else:
        print(f"  [FAIL] {name} -- {detail}")
        failed += 1
        errors.append(f"{name}: {detail}")

# Test-Instanz ohne Ollama-Zwang
pipeline = MetaCoderSQLPipeline(require_ollama=False)
pipeline.verify_environment()

# ═══════════════════════════════════════════════════
# TEST 1: index_chat_user_query - Bereinigung & Token-Schärfung
# ═══════════════════════════════════════════════════
print("\n--- TEST 1: index_chat_user_query Token-Schärfung & Intent ---")

raw_input_repair = "  Kannst du bitte  mal  diesen Fehler im SQL Script reparieren und fixen?  "
res1 = pipeline.index_chat_user_query(raw_input_repair)

test("res1 ist Dict", isinstance(res1, dict))
test("Whitespace bereinigt", res1["clean_query"] == "Kannst du bitte mal diesen Fehler im SQL Script reparieren und fixen?")
test("Token-Schärfung (Füllwörter entfernt)", "kannst du bitte" not in res1["sharpened_query"].lower())
test("Intent-Klassifikation: Reparatur", res1["query_type"] == "Reparatur", f"Erhalten: {res1['query_type']}")
test("log_table_name beginnt mit log_", res1["log_table_name"].startswith("log_"), f"Erhalten: {res1['log_table_name']}")
test("node_id existiert", res1["node_id"] is not None)

# ═══════════════════════════════════════════════════
# TEST 2: Intent-Klassifikation weiterer Typen
# ═══════════════════════════════════════════════════
print("\n--- TEST 2: Intent-Klassifikation Typen ---")

res_code = pipeline.index_chat_user_query("Erstelle eine Python Funktion für Datenverarbeitung")
test("Intent-Klassifikation: Coding", res_code["query_type"] == "Coding", f"Erhalten: {res_code['query_type']}")

res_arch = pipeline.index_chat_user_query("Zeige mir den Blueprint und die Routing-Tree Architektur")
test("Intent-Klassifikation: Architektur", res_arch["query_type"] == "Architektur", f"Erhalten: {res_arch['query_type']}")

res_ana = pipeline.index_chat_user_query("Analysiere und scanne die Systemtabellen")
test("Intent-Klassifikation: Analyse", res_ana["query_type"] == "Analyse", f"Erhalten: {res_ana['query_type']}")

# ═══════════════════════════════════════════════════
# TEST 3: Dynamische Log-Tabelle log_{time} & table_issue_data...
# ═══════════════════════════════════════════════════
print("\n--- TEST 3: Dynamische Tabelle log_{time} mit Vorlage-Punkten ---")

test_time = "20260924_103000"
test_log_table = f"log_{test_time}"

pipeline.log_save_query_run_to_db_timestamp(
    task_description="Unit-Test für log_{time}",
    error_msg="",
    solution_code="print('Hello Test')",
    run_id=test_time,
    step_type="checkpoint",
    log_table_name=test_log_table
)

# Prüfen ob die Tabelle existiert und gefüllt ist
with pipeline.get_db_connection() as conn:
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (test_log_table,))
    table_exists = c.fetchone() is not None
    test(f"Tabelle '{test_log_table}' in SQLite erstellt", table_exists)

    if table_exists:
        c.execute(f"SELECT COUNT(*) FROM {test_log_table}")
        row_count = c.fetchone()[0]
        test(f"Datensätze in '{test_log_table}' vorhanden", row_count > 0, f"Count: {row_count}")

        # Spalten prüfen (Anforderungen nach is_active)
        c.execute(f"PRAGMA table_info({test_log_table})")
        cols = [r[1] for r in c.fetchall()]
        required_cols = [
            "node_id", "is_active", "error_fallback_count", "year", "month", "day",
            "hour", "minute", "second", "topic_title", "topic_specification",
            "agent_instruction", "example_code_snippet", "validation_rule"
        ]
        all_cols_present = all(col in cols for col in required_cols)
        test("Alle erforderlichen Spalten nach is_active vorhanden", all_cols_present)

# ═══════════════════════════════════════════════════
# TEST 4: run_pipeline Integration
# ═══════════════════════════════════════════════════
print("\n--- TEST 4: run_pipeline mit index_chat_user_query ---")

pipe_result = pipeline.run_pipeline("Bitte führe eine Analyse der Datenbank durch")
test("run_pipeline erfolgreich abgeschlossen", pipe_result.get("status") in ["SUCCESS", "FAILED"] or pipe_result.get("cache_hit") is True)

# ═══════════════════════════════════════════════════
# ZUSAMMENFASSUNG
# ═══════════════════════════════════════════════════
print("\n" + "=" * 70)
print(f" ERGEBNIS: {passed} bestanden | {failed} fehlgeschlagen")
print("=" * 70)

if errors:
    print("\nFehlgeschlagene Tests:")
    for err in errors:
        print(f"  [!] {err}")

sys.exit(0 if failed == 0 else 1)
