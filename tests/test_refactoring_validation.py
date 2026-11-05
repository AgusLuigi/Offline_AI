#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Testvalidierung für die refaktorierte Codebasis:
1. Import-Tests aller universal-skript Module
2. Strukturvalidierung (keine Hardcoded Agent-Namen im Body)
3. Klassen-Instanziierung und Methoden-Check
4. Konfigurationsparameter-Prüfung
5. EvolveLoopTest Closed-Loop
6. V1-Methoden in MetaCoderSQLPipeline vorhanden
7. class_sql_reader konfigurierbare Attribute
8. SubAgentVerifier konfigurierbare Attribute
9. coreInfrastructure Ollama-Guard
"""
import os
import sys
import re
import unittest
from pathlib import Path

# Projekt-Root ermitteln
test_file = Path(__file__).resolve()
project_root = None
for parent in test_file.parents:
    if (parent / "src").is_dir():
        project_root = parent
        break

if project_root is None:
    raise RuntimeError("Konnte Projekt-Root nicht finden!")

sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src" / "agent"))
sys.path.insert(0, str(project_root / "src" / "agent" / "agent_universal_skript"))
os.chdir(str(project_root))


class TestRefactoringValidation(unittest.TestCase):

    def test_01_imports(self):
        """Import-Tests aller universal-skript Module."""
        from agent_universal_skript.class_tool_resource_aware_spinner import class_tool_resource_aware_spinner as ResourceAwareSpinner
        from agent_universal_skript.class_tool_core_infrastructure import class_tool_core_infrastructure as coreInfrastructure
        from agent_universal_skript.class_container_evolve_loop_test import class_container_evolve_loop_test as EvolveLoopTest
        from agent_universal_skript.class_tool_sql_reader import class_tool_sql_reader as class_sql_reader
        from agent_universal_skript.__ollama_running import check_and_start_ollama, is_port_open

        self.assertIsNotNone(ResourceAwareSpinner)
        self.assertIsNotNone(coreInfrastructure)
        self.assertIsNotNone(EvolveLoopTest)
        self.assertIsNotNone(class_sql_reader)
        self.assertTrue(callable(check_and_start_ollama))

    def test_02_no_fixed_agent_names(self):
        """Keine fixen Agent-Namen in universal-skripts."""
        universal_dir = project_root / "src" / "agent" / "agent_universal_skript"
        forbidden_terms = ["Codestral", "MetaCoder", "mixtral", "llama3.1", "codestral:latest"]

        for py_file in universal_dir.glob("*.py"):
            if py_file.name.startswith("__pycache__"):
                continue
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            found_terms = [t for t in forbidden_terms if t in content]
            self.assertEqual(len(found_terms), 0, f"Fixe Begriffe in {py_file.name} gefunden: {found_terms}")

    def test_03_class_instantiations(self):
        """Klassen-Instanziierung und Methoden-Check."""
        from agent_universal_skript.class_tool_resource_aware_spinner import class_tool_resource_aware_spinner as ResourceAwareSpinner
        from agent_universal_skript.class_container_evolve_loop_test import class_container_evolve_loop_test as EvolveLoopTest
        from agent_universal_skript.class_tool_core_infrastructure import class_tool_core_infrastructure as coreInfrastructure

        spinner = ResourceAwareSpinner(agent_name="TestAgent", min_ram_mb=1000, max_cpu_threshold=80.0, spinner_interval=0.5)
        self.assertEqual(spinner.agent_name, "TestAgent")

        default_spinner = ResourceAwareSpinner()
        self.assertEqual(default_spinner.agent_name, "Agent")

        loop = EvolveLoopTest(registry_db_path=":memory:")
        self.assertEqual(loop.registry_db_path, ":memory:")

        root = coreInfrastructure.get_project_root()
        self.assertTrue(root.is_dir())

    def test_04_evolve_loop_closed_loop(self):
        """EvolveLoopTest Closed-Loop Erfolg und Fehlerpfad."""
        from agent_universal_skript.class_container_evolve_loop_test import class_container_evolve_loop_test as EvolveLoopTest
        loop = EvolveLoopTest(registry_db_path=":memory:")

        def sample_runner(payload):
            return f"OK: {payload['task']}"

        result = loop.test_and_evolve_loop(
            specialization="Test",
            task_description="Unit-Test",
            base_filename="test_run",
            max_generations=1,
            execution_func=sample_runner
        )
        self.assertEqual(result["status"], "SUCCESS")

        def failing_runner(payload):
            raise RuntimeError("Geplanter Testfehler")

        fail_result = loop.test_and_evolve_loop(
            specialization="Test",
            task_description="Fail-Test",
            base_filename="test_fail",
            max_generations=1,
            execution_func=failing_runner
        )
        self.assertEqual(fail_result["status"], "FAILED")

    def test_05_configuration_parameters(self):
        """Konfigurationsparameter in meta_coder_sql.py."""
        meta_sql_path = project_root / "src" / "agent" / "meta_coder_sql.py"
        meta_content = meta_sql_path.read_text(encoding="utf-8")

        config_params = [
            "PROJECT_POINT", "DB_FILENAME", "MODEL_LLM", "OLLAMA_HOST", "AGENT_NAME",
            "MAX_EVOLUTION_GENERATIONS", "MAX_USER_QUERY_ID_RANGE",
            "TASK_DESCRIPTION_MAX_LEN", "CODE_SNIPPET_PREVIEW_LEN",
            "TFIDF_SIMILARITY_THRESHOLD", "FEEDBACK_WEIGHT_INCREMENT",
            "MAX_BLUEPRINT_STEPS", "MAX_DOMAIN_NODES", "MAX_MANIFEST_ENTRIES",
            "CPU_WARNING_THRESHOLD", "MIN_RAM_MB", "SPINNER_INTERVAL",
            "DOMAIN_KEYWORDS", "ALLOWED_TABLES", "FALLBACK_DOMAIN"
        ]

        for param in config_params:
            pattern = rf'^{param}\s*='
            found = bool(re.search(pattern, meta_content, re.MULTILINE))
            self.assertTrue(found, f"Parameter '{param}' nicht global in meta_coder_sql.py definiert")

    def test_06_v1_methods_exist(self):
        """V1-Methoden und Wrapper in meta_coder_sql.py vorhanden."""
        meta_sql_path = project_root / "src" / "agent" / "meta_coder_sql.py"
        meta_content = meta_sql_path.read_text(encoding="utf-8")

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
            self.assertIn(f"def {method}", meta_content, f"V1-Methode '{method}' fehlt in meta_coder_sql.py")

        wrapper_funcs = ["boot_latest_metacoder", "query_meta_coder_sql"]
        for func in wrapper_funcs:
            self.assertIn(f"def {func}", meta_content, f"Wrapper '{func}' fehlt in meta_coder_sql.py")

    def test_07_class_sql_reader_attributes(self):
        """class_sql_reader konfigurierbare Attribute."""
        from agent_universal_skript.class_tool_sql_reader import class_tool_sql_reader as class_sql_reader

        self.assertIsInstance(class_sql_reader.ALLOWED_TABLES, set)
        self.assertTrue(hasattr(class_sql_reader, "DOMAIN"))
        self.assertIsInstance(class_sql_reader.DOMAIN_KEYWORDS, dict)
        self.assertIsInstance(class_sql_reader.TFIDF_SIMILARITY_THRESHOLD, float)
        self.assertIsInstance(class_sql_reader.TASK_DESCRIPTION_MAX_LEN, int)

    def test_08_sub_agent_verifier_attributes(self):
        """SubAgentVerifier konfigurierbare Attribute."""
        from agent_universal_skript.class_agent_sub_verifier import class_agent_sub_verifier as SubAgentVerifier

        self.assertTrue(hasattr(SubAgentVerifier, "SANDBOX_TIMEOUT"))
        self.assertTrue(hasattr(SubAgentVerifier, "MAX_SANDBOX_OUTPUT_LENGTH"))
        self.assertIsInstance(SubAgentVerifier.FORBIDDEN_MODULES, set)

    def test_09_core_infrastructure_ollama_guard(self):
        """coreInfrastructure Ollama-Guard und Attribute."""
        universal_dir = project_root / "src" / "agent" / "agent_universal_skript"
        core_path = universal_dir / "class_tool_core_infrastructure.py"
        core_content = core_path.read_text(encoding="utf-8")

        self.assertNotIn("_OLLAMA_VERIFIED_CACHE", core_content)
        self.assertIn("_ollama_verified", core_content)
        self.assertTrue("from ollama import Client" in core_content and "except ImportError" in core_content)


if __name__ == "__main__":
    unittest.main()
