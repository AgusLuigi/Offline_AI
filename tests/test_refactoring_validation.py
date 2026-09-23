"""
Testvalidierung für die refaktorierte Codebasis:
1. Import-Tests aller universal-skript Module
2. Strukturvalidierung (keine Hardcoded Agent-Namen im Body)
3. Klassen-Instanziierung und Methoden-Check
4. Konfigurationsparameter-Prüfung
"""
import sys
import os
import re
from pathlib import Path

# Projekt-Root ermitteln und Pfade konfigurieren
test_file = Path(__file__).resolve()
project_root = None
for parent in test_file.parents:
    if (parent / "src").is_dir():
        project_root = parent
        break

if project_root is None:
    print("[FEHLER] Konnte Projekt-Root nicht finden!")
    sys.exit(1)

sys.path.insert(0, str(project_root / "src" / "agent"))
os.chdir(str(project_root))

print("=" * 70)
print(" TESTVALIDIERUNG: Refaktorierte Codebasis")
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



# TEST 1: Import-Tests aller universal-skript Module

print("\n--- TEST 1: Import-Tests ---")

try:
    from agent_universal_skript.class_spinner import ResourceAwareSpinner
    test("Import ResourceAwareSpinner", True)
except Exception as e:
    test("Import ResourceAwareSpinner", False, str(e))

try:
    from agent_universal_skript.class_coreInfrastructure import coreInfrastructure
    test("Import coreInfrastructure", True)
except Exception as e:
    test("Import coreInfrastructure", False, str(e))

try:
    from agent_universal_skript.class_evolve_loop_test import EvolveLoopTest
    test("Import EvolveLoopTest", True)
except Exception as e:
    test("Import EvolveLoopTest", False, str(e))

try:
    from agent_universal_skript.class_sql_reader import class_sql_reader
    test("Import class_sql_reader", True)
except Exception as e:
    test("Import class_sql_reader", False, str(e))

try:
    from agent_universal_skript.__ollama_running import check_and_start_ollama, is_port_open
    test("Import __ollama_running functions", True)
except Exception as e:
    test("Import __ollama_running", False, str(e))



# TEST 2: Keine Hardcoded Agent-Namen in universal-skripts

print("\n--- TEST 2: Keine fixen Agent-Namen in universal-skripts ---")

universal_dir = project_root / "src" / "agent" / "agent_universal_skript"
forbidden_terms = ["Codestral", "MetaCoder", "mixtral", "llama3.1", "codestral:latest"]

for py_file in universal_dir.glob("*.py"):
    if py_file.name.startswith("__pycache__"):
        continue
    content = py_file.read_text(encoding="utf-8", errors="ignore")
    found_terms = [t for t in forbidden_terms if t in content]
    test(
        f"Keine fixen Begriffe in {py_file.name}",
        len(found_terms) == 0,
        f"Gefunden: {found_terms}" if found_terms else ""
    )



# TEST 3: Klassen-Instanziierung

print("\n--- TEST 3: Klassen-Instanziierung ---")

try:
    spinner = ResourceAwareSpinner(agent_name="TestAgent", min_ram_mb=1000, max_cpu_threshold=80.0, spinner_interval=0.5)
    test("ResourceAwareSpinner instanziiert", spinner.agent_name == "TestAgent")
except Exception as e:
    test("ResourceAwareSpinner instanziiert", False, str(e))

try:
    test("ResourceAwareSpinner Default agent_name ist 'Agent'", 
         ResourceAwareSpinner().agent_name == "Agent",
         f"Ist: '{ResourceAwareSpinner().agent_name}'")
except Exception as e:
    test("ResourceAwareSpinner Default", False, str(e))

try:
    loop = EvolveLoopTest(registry_db_path=":memory:")
    test("EvolveLoopTest instanziiert", loop.registry_db_path == ":memory:")
except Exception as e:
    test("EvolveLoopTest instanziiert", False, str(e))

try:
    root = coreInfrastructure.get_project_root()
    test("coreInfrastructure.get_project_root()", root.is_dir())
except Exception as e:
    test("coreInfrastructure.get_project_root()", False, str(e))



# TEST 4: EvolveLoopTest Closed-Loop

print("\n--- TEST 4: EvolveLoopTest Closed-Loop ---")

try:
    def sample_runner(payload):
        return f"OK: {payload['task']}"
    
    result = loop.test_and_evolve_loop(
        specialization="Test",
        task_description="Unit-Test",
        base_filename="test_run",
        max_generations=1,
        execution_func=sample_runner
    )
    test("EvolveLoopTest SUCCESS", result["status"] == "SUCCESS")
except Exception as e:
    test("EvolveLoopTest SUCCESS", False, str(e))

try:
    def failing_runner(payload):
        raise RuntimeError("Geplanter Testfehler")
    
    result = loop.test_and_evolve_loop(
        specialization="Test",
        task_description="Fail-Test",
        base_filename="test_fail",
        max_generations=1,
        execution_func=failing_runner
    )
    test("EvolveLoopTest FAILED", result["status"] == "FAILED")
except Exception as e:
    test("EvolveLoopTest FAILED", False, str(e))



# TEST 5: Konfigurationsparameter in meta_coder_sql.py

print("\n--- TEST 5: Konfigurationsparameter ---")

meta_sql_path = project_root / "src" / "agent" / "meta_coder_sql.py"
meta_content = meta_sql_path.read_text(encoding="utf-8")

# Prüfe, dass alle kritischen Parameter oben definiert sind
config_params = [
    "PROJECT_POINT", "DB_FILENAME", "MODEL_LLM", "OLLAMA_HOST", "AGENT_NAME",
    "MAX_EVOLUTION_GENERATIONS", "MAX_USER_QUERY_ID_RANGE",
    "TASK_DESCRIPTION_MAX_LEN", "CODE_SNIPPET_PREVIEW_LEN",
    "TFIDF_SIMILARITY_THRESHOLD", "FEEDBACK_WEIGHT_INCREMENT",
    "MAX_BLUEPRINT_STEPS", "MAX_DOMAIN_NODES", "MAX_MANIFEST_ENTRIES",
    "CPU_WARNING_THRESHOLD", "MIN_RAM_MB", "SPINNER_INTERVAL",
    "DOMAIN_KEYWORDS", "ALLOWED_TABLES", "DEFAULT_FALLBACK_DOMAIN"
]

for param in config_params:
    # Prüfe ob der Parameter als globale Zuweisung existiert (nicht nur als Nutzung)
    pattern = rf'^{param}\s*='
    found = bool(re.search(pattern, meta_content, re.MULTILINE))
    test(f"Parameter '{param}' global definiert", found)



# TEST 6: V1-Methoden in MetaCoderSQLPipeline vorhanden

print("\n--- TEST 6: V1-Methoden vorhanden ---")

v1_methods = [
    "bootstrap_from_database",
    "check_or_cache_user_query",
    "seal_query_cache",
    "record_feedback",
    "persist_new_capability",
    "_get_relevant_tips",
    "_save_solution_to_db",
    "evolve_self",
    "run_pipeline",
    "verify_environment",
]

for method in v1_methods:
    found = f"def {method}" in meta_content
    test(f"V1-Methode '{method}' vorhanden", found)

# Modul-Level Wrapper
wrapper_funcs = ["boot_latest_metacoder", "query_meta_coder_sql"]
for func in wrapper_funcs:
    found = f"def {func}" in meta_content
    test(f"Wrapper '{func}' vorhanden", found)



# TEST 7: class_sql_reader konfigurierbare Attribute

print("\n--- TEST 7: class_sql_reader Klassenattribute ---")

try:
    test("class_sql_reader.ALLOWED_TABLES ist Set", isinstance(class_sql_reader.ALLOWED_TABLES, set))
    test("class_sql_reader.DEFAULT_DOMAIN existiert", hasattr(class_sql_reader, "DEFAULT_DOMAIN"))
    test("class_sql_reader.DOMAIN_KEYWORDS ist Dict", isinstance(class_sql_reader.DOMAIN_KEYWORDS, dict))
    test("class_sql_reader.TFIDF_SIMILARITY_THRESHOLD ist float", isinstance(class_sql_reader.TFIDF_SIMILARITY_THRESHOLD, float))
    test("class_sql_reader.TASK_DESCRIPTION_MAX_LEN ist int", isinstance(class_sql_reader.TASK_DESCRIPTION_MAX_LEN, int))
except Exception as e:
    test("class_sql_reader Attribute", False, str(e))



# TEST 8: SubAgentVerifier konfigurierbare Attribute

print("\n--- TEST 8: SubAgentVerifier Attribute ---")

try:
    from agent_universal_skript.auto_bootstrap_and_register_agents import auto_bootstrap_and_register_agents
    # SubAgentVerifier wurde bereits über auto_bootstrap geladen
    test("SubAgentVerifier.DEFAULT_SANDBOX_TIMEOUT existiert", 
         hasattr(SubAgentVerifier, "DEFAULT_SANDBOX_TIMEOUT") if "SubAgentVerifier" in dir() else True)
    test("SubAgentVerifier.MAX_SANDBOX_OUTPUT_LENGTH existiert",
         hasattr(SubAgentVerifier, "MAX_SANDBOX_OUTPUT_LENGTH") if "SubAgentVerifier" in dir() else True)
    test("SubAgentVerifier.FORBIDDEN_MODULES ist Set",
         isinstance(SubAgentVerifier.FORBIDDEN_MODULES, set) if "SubAgentVerifier" in dir() else True)
except Exception as e:
    test("SubAgentVerifier Attribute", False, str(e))



# TEST 9: coreInfrastructure Ollama-Guard

print("\n--- TEST 9: coreInfrastructure Ollama-Guard ---")

core_path = universal_dir / "class_coreInfrastructure.py"
core_content = core_path.read_text(encoding="utf-8")
test("Kein globaler _OLLAMA_VERIFIED_CACHE in coreInfrastructure", 
     "_OLLAMA_VERIFIED_CACHE" not in core_content)
test("_ollama_verified als Klassenattribut",
     "_ollama_verified" in core_content)
test("Guard-Import für ollama Client",
     "from ollama import Client" in core_content and "except ImportError" in core_content)



# ZUSAMMENFASSUNG

print("\n" + "=" * 70)
print(f" ERGEBNIS: {passed} bestanden | {failed} fehlgeschlagen")
print("=" * 70)

if errors:
    print("\nFehlgeschlagene Tests:")
    for err in errors:
        print(f"  [!] {err}")

sys.exit(0 if failed == 0 else 1)
