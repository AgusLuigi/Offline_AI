# -*- coding: utf-8 -*-
import os
import sys
import types
import unittest
import importlib
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.Install.auto_import_lazy_loader import (
    AUTO_IMPORT_LAZY_LOAD,
    CORE_IMPORT,
    ZONE_FROM,
)


class TestAutoImportLazyLoader(unittest.TestCase):

    def setUp(self):
        AUTO_IMPORT_LAZY_LOAD.uninstall_import_interceptor()

    def tearDown(self):
        AUTO_IMPORT_LAZY_LOAD.uninstall_import_interceptor()

    def test_consolidated_two_table_architecture(self):
        """Verify strict consolidation into exactly TWO central tables at module top."""
        import src.Install.auto_import_lazy_loader as loader_mod

        # 1. Exactly the two primary structures
        self.assertIsInstance(CORE_IMPORT, list)
        self.assertIsInstance(ZONE_FROM, list)

        # 2. Schema check for CORE_IMPORT:
        # (import_name, alias, pip_name, version_constraint, patterns, is_bootstrap)
        self.assertGreater(len(CORE_IMPORT), 20)
        for row in CORE_IMPORT:
            self.assertGreaterEqual(len(row), 6, f"Invalid tuple length in CORE_IMPORT: {row}")
            self.assertIsInstance(row[0], str)  # import_name
            self.assertTrue(row[1] is None or isinstance(row[1], str))  # alias
            self.assertIsInstance(row[2], str)  # pip_name
            self.assertTrue(row[3] is None or isinstance(row[3], str))  # version_constraint
            self.assertTrue(row[4] is None or isinstance(row[4], (list, str)))  # patterns
            self.assertIsInstance(row[5], bool) # is_bootstrap

        # 3. Schema check for ZONE_FROM:
        # (module, import_target, alias, pip_name, version, patterns, is_bootstrap)
        self.assertGreater(len(ZONE_FROM), 5)
        for row in ZONE_FROM:
            self.assertGreaterEqual(len(row), 7, f"Invalid tuple length in ZONE_FROM: {row}")
            self.assertIsInstance(row[0], str)  # module
            self.assertIsInstance(row[1], str)  # import_target
            self.assertTrue(row[2] is None or isinstance(row[2], str))  # alias
            self.assertIsInstance(row[3], str)  # pip_name
            self.assertTrue(row[4] is None or isinstance(row[4], str))  # version
            self.assertTrue(row[5] is None or isinstance(row[5], (list, str)))  # patterns
            self.assertIsInstance(row[6], bool) # is_bootstrap

        # 4. Ensure obsolete separate tables and redundant global aliases are abolished
        obsolete_tables = [
            "ecosystem_canonical_map",
            "STDLIB_MODULE_NAMES",
            "_BOOTSTRAP_DEPS",
            "LLAMA_BOOTSTRAP_PACKAGES",
            "CORE_FROM",
            "LIBRARY_IMPORT",
            "LIBRARY_FROM",
        ]
        for name in obsolete_tables:
            self.assertFalse(
                hasattr(loader_mod, name),
                f"Obsolete symbol or alias '{name}' should not exist; single source of truth required",
            )

        # 5. Ensure OLLAMA_SERVICE_GUARD eliminated redundant shadow attributes
        guard_cls = AUTO_IMPORT_LAZY_LOAD.OLLAMA_SERVICE_GUARD
        redundant_guard_attrs = [
            "WIN_INSTALLER_URL", "MAC_INSTALLER_URL", "LINUX_INSTALL_CMD",
            "LINUX_FALLBACK_URLS", "HERMES_PREFERRED", "PULL_STREAM_TIMEOUT",
        ]
        for attr in redundant_guard_attrs:
            self.assertFalse(
                hasattr(guard_cls, attr),
                f"OLLAMA_SERVICE_GUARD should not shadow '{attr}'; use global constants directly",
            )

    def test_pipeline_structure_retention(self):
        """1. Retain Existing Pipeline Structure: verify all structural stages & methods exist."""
        expected_methods = [
            "bootstrap",
            "_detect_project_root",
            "get_dir",
            "get_active_model_config_path",
            "detect_notebook_name",
            "resolve_log_file_name",
            "get_target_log_path",
            "_setup_logging_and_paths",
            "write_log",
            "parse_log_lines",
            "get_hardware_information",
            "compute_hw_hash",
            "get_or_register_pc_id",
            "build_status_table",
            "split_patterns",
            "check_capability_compatibility",
            "is_known_error_pattern",
            "build_vcredist_hint",
            "get_platform_specific_pip_name",
            "process_library_pipeline",
            "ensure_ollama_and_hermes",
            "require",
            "lazy_import",
            "stochastic_self_heal",
            "install_import_interceptor",
            "uninstall_import_interceptor",
        ]
        for method_name in expected_methods:
            self.assertTrue(
                hasattr(AUTO_IMPORT_LAZY_LOAD, method_name),
                f"Missing expected pipeline method: {method_name}"
            )

        # DICT_FOLDERS dict muss global vorhanden und befüllt sein (nicht in der Klasse dupliziert)
        import src.Install.auto_import_lazy_loader as loader_mod
        self.assertTrue(hasattr(loader_mod, "DICT_FOLDERS"))
        self.assertIsInstance(loader_mod.DICT_FOLDERS, dict)
        self.assertFalse(hasattr(AUTO_IMPORT_LAZY_LOAD, "DICT_FOLDERS"))
        self.assertIn("src",    loader_mod.DICT_FOLDERS)
        self.assertIn("logs",   loader_mod.DICT_FOLDERS)
        self.assertIn("config", loader_mod.DICT_FOLDERS)
        self.assertIn("data",   loader_mod.DICT_FOLDERS)
        self.assertIn("models", loader_mod.DICT_FOLDERS)

        # Check nested managers
        self.assertTrue(hasattr(AUTO_IMPORT_LAZY_LOAD, "DOWNLOAD_MANAGER"))
        self.assertTrue(hasattr(AUTO_IMPORT_LAZY_LOAD, "OLLAMA_SERVICE_GUARD"))

    def test_stochastic_name_resolution(self):
        """2. Stochastic & Autonomous Package Analysis."""
        # Known Ollama / LLM ecosystem mappings
        candidates = AUTO_IMPORT_LAZY_LOAD.resolve_canonical_pip_name("open_webui")
        self.assertIn("open-webui", candidates)

        candidates_hermes = AUTO_IMPORT_LAZY_LOAD.resolve_canonical_pip_name("hermes")
        self.assertTrue(any("hermes" in c for c in candidates_hermes))

        candidates_llama = AUTO_IMPORT_LAZY_LOAD.resolve_canonical_pip_name("llama_cpp")
        self.assertIn("llama-cpp-python", candidates_llama)

        candidates_ollama = AUTO_IMPORT_LAZY_LOAD.resolve_canonical_pip_name("ollama")
        self.assertIn("ollama", candidates_ollama)

        # Data science & tools
        self.assertIn("pyyaml", AUTO_IMPORT_LAZY_LOAD.resolve_canonical_pip_name("yaml"))
        self.assertIn("opencv-python", AUTO_IMPORT_LAZY_LOAD.resolve_canonical_pip_name("cv2"))
        self.assertIn("pillow", AUTO_IMPORT_LAZY_LOAD.resolve_canonical_pip_name("PIL"))

        # Future unknown packages: heuristic generation
        future_candidates = AUTO_IMPORT_LAZY_LOAD.resolve_canonical_pip_name("future_ollama_agent")
        self.assertIn("future-ollama-agent", future_candidates)
        self.assertIn("future-ollama-agent-client", future_candidates)

    def test_stdlib_detection(self):
        """Verify standard library packages are identified and never treated as missing pip pkgs."""
        self.assertTrue(AUTO_IMPORT_LAZY_LOAD._is_stdlib("sys"))
        self.assertTrue(AUTO_IMPORT_LAZY_LOAD._is_stdlib("os"))
        self.assertTrue(AUTO_IMPORT_LAZY_LOAD._is_stdlib("math"))
        self.assertTrue(AUTO_IMPORT_LAZY_LOAD._is_stdlib("json"))
        self.assertFalse(AUTO_IMPORT_LAZY_LOAD._is_stdlib("ollama"))
        self.assertFalse(AUTO_IMPORT_LAZY_LOAD._is_stdlib("open_webui"))

    def test_dynamic_interception_and_seamless_retry(self):
        """Test interception on the fly, automated installation, and immediate retry."""
        test_module_name = "_test_mock_ai_pkg"

        # Mock download manager
        mock_dm = MagicMock()
        def fake_install(pip_pkg, base_pkg, force_reinstall=False):
            # Create a mock module dynamically in sys.modules simulating successful pip install
            mod = types.ModuleType(base_pkg)
            mod.AI_VERSION = "2.0.0"
            mod.test_func = lambda: "SUCCESS"
            sys.modules[base_pkg] = mod
            return True

        mock_dm.install_package_isolated.side_effect = fake_install

        import src.Install.auto_import_lazy_loader as loader_mod
        with patch.dict(sys.modules):
            if test_module_name in sys.modules:
                del sys.modules[test_module_name]

            with patch.dict(loader_mod.__dict__, {"download_manager": mock_dm, "STATUS_TABLE": {}}):
                AUTO_IMPORT_LAZY_LOAD.install_import_interceptor()

                # Attempt importing the uninstalled module
                # The interceptor catches ModuleNotFoundError, analyzes it, installs via fake_install,
                # invalidates caches, and retries immediately!
                mod = importlib.import_module(test_module_name)
                self.assertIsNotNone(mod)
                self.assertEqual(mod.AI_VERSION, "2.0.0")
                self.assertEqual(mod.test_func(), "SUCCESS")

                # Verify install was called
                self.assertTrue(mock_dm.install_package_isolated.called)

    def test_existing_package_bypass(self):
        """If package is already present, it should bypass installation and import directly."""
        mock_dm = MagicMock()
        import src.Install.auto_import_lazy_loader as loader_mod
        with patch.dict(loader_mod.__dict__, {"download_manager": mock_dm}):
            AUTO_IMPORT_LAZY_LOAD.install_import_interceptor()
            import json
            self.assertIsNotNone(json.loads)
            # mock_dm should NOT have been called
            self.assertFalse(mock_dm.install_package_isolated.called)

    def test_require_and_lazy_import_api(self):
        """Test require() and lazy_import() programmatic APIs."""
        mock_dm = MagicMock()
        def fake_install(pip_pkg, base_pkg, force_reinstall=False):
            mod = types.ModuleType(base_pkg)
            mod.HERMES_READY = True
            sys.modules[base_pkg] = mod
            return True

        mock_dm.install_package_isolated.side_effect = fake_install
        import src.Install.auto_import_lazy_loader as loader_mod
        with patch.dict(loader_mod.__dict__, {"download_manager": mock_dm, "STATUS_TABLE": {}}):
            AUTO_IMPORT_LAZY_LOAD.install_import_interceptor()
            res = AUTO_IMPORT_LAZY_LOAD.require("mock_hermes_client", inject_globals=False)
            self.assertIn("mock_hermes_client", res)
            self.assertTrue(res["mock_hermes_client"].HERMES_READY)

            mod_alias = AUTO_IMPORT_LAZY_LOAD.lazy_import("mock_hermes_client", alias="mhc")
            self.assertTrue(mod_alias.HERMES_READY)

    def test_failed_install_exhaustion(self):
        """When an uninstalled package fails installation across all retries, raise ModuleNotFoundError cleanly."""
        mock_dm = MagicMock()
        mock_dm.install_package_isolated.return_value = False  # Installation fails

        import src.Install.auto_import_lazy_loader as loader_mod
        with patch.dict(loader_mod.__dict__, {"download_manager": mock_dm, "STATUS_TABLE": {}}):
            AUTO_IMPORT_LAZY_LOAD.install_import_interceptor()
            with self.assertRaises(ModuleNotFoundError):
                importlib.import_module("completely_invalid_package_12345")

    def test_hardware_profiling(self):
        """Hardware information check retains established metrics."""
        hw = AUTO_IMPORT_LAZY_LOAD.get_hardware_information()
        self.assertIn("CORE", hw)
        self.assertIn("RAM", hw)
        self.assertIn("PLATFORM", hw)
        self.assertIn("CPU_FLAGS", hw)
        self.assertIsInstance(hw["CPU_FLAGS"], set)

    def test_dynamic_paths_and_context_sensitive_logging(self):
        """Test dynamic path resolution via _detect_project_root() and context-sensitive log file naming."""
        root = AUTO_IMPORT_LAZY_LOAD._detect_project_root()
        self.assertIsInstance(root, Path)
        self.assertTrue(root.is_dir())

        # DICT_FOLDERS-Schleife – passiv: kein mkdir beim Pfad-Abruf
        src_dir    = AUTO_IMPORT_LAZY_LOAD.get_dir("DIR_SRC")
        logs_dir   = AUTO_IMPORT_LAZY_LOAD.get_dir("DIR_LOGS")
        config_dir = AUTO_IMPORT_LAZY_LOAD.get_dir("DIR_CONFIG")
        data_dir   = AUTO_IMPORT_LAZY_LOAD.get_dir("DIR_DATA")
        models_dir = AUTO_IMPORT_LAZY_LOAD.get_dir("DIR_MODELS")
        self.assertEqual(src_dir,    root / "src")
        self.assertEqual(logs_dir,   root / "logs")
        self.assertEqual(config_dir, root / "config")
        self.assertEqual(data_dir,   root / "data")
        self.assertEqual(models_dir, root / "data" / "models")


        # ensure=True legt den Ordner bei Bedarf an (bedarfsgesteuert)
        self.assertTrue(AUTO_IMPORT_LAZY_LOAD.get_dir("DIR_LOGS", ensure=True).is_dir())

        cfg_path = AUTO_IMPORT_LAZY_LOAD.get_active_model_config_path()
        self.assertEqual(cfg_path, config_dir / "active_model_config.json")

        # PROJECT_ANCHOR_DIR ist im Kopfbereich ein Rohling – wird erst nach Bootstrap gesetzt.
        import src.Install.auto_import_lazy_loader as loader_mod
        self.assertEqual(loader_mod.PROJECT_ANCHOR_DIR, "Project_Folder_Name")   # Rohling
        self.assertEqual(loader_mod.LOG_FILE_NAME, "app_import_terminal.log")
        self.assertFalse(hasattr(loader_mod, "LOG_FILE_FALLBACK"))
        self.assertEqual(AUTO_IMPORT_LAZY_LOAD._detect_project_root().name, root.name)

        # Fallback in terminal/script context
        with patch.dict(os.environ, {}, clear=True):
            with patch("sys.argv", ["script.py"]):
                self.assertEqual(AUTO_IMPORT_LAZY_LOAD.resolve_log_file_name(), "app_import_terminal.log")
                self.assertEqual(AUTO_IMPORT_LAZY_LOAD.get_target_log_path(), logs_dir / "app_import_terminal.log")

        # Jupyter notebook context via JPY_SESSION_NAME
        with patch.dict(os.environ, {"JPY_SESSION_NAME": "notebooks/custom_analysis.ipynb"}):
            self.assertEqual(AUTO_IMPORT_LAZY_LOAD.detect_notebook_name(), "custom_analysis")
            self.assertEqual(AUTO_IMPORT_LAZY_LOAD.resolve_log_file_name(), "LOG_custom_analysis.log")
            self.assertEqual(
                AUTO_IMPORT_LAZY_LOAD.get_target_log_path(),
                logs_dir / "LOG_custom_analysis.log",
            )

        # Jupyter notebook context via sys.argv nbconvert/papermill
        with patch.dict(os.environ, {}, clear=True):
            with patch("sys.argv", ["papermill", "ollama_model_download_utility.ipynb"]):
                self.assertEqual(AUTO_IMPORT_LAZY_LOAD.detect_notebook_name(), "ollama_model_download_utility")
                self.assertEqual(AUTO_IMPORT_LAZY_LOAD.resolve_log_file_name(), "LOG_ollama_model_download_utility.log")

        # Jupyter notebook detection via IPython ZMQInteractiveShell
        mock_ipython = MagicMock()
        mock_zmq_shell = MagicMock()
        type(mock_zmq_shell).__name__ = "ZMQInteractiveShell"
        mock_ipython.get_ipython.return_value = mock_zmq_shell
        with patch.dict(sys.modules, {"IPython": mock_ipython}):
            self.assertTrue(AUTO_IMPORT_LAZY_LOAD.is_jupyter_environment())
            # Wenn Notebook-Name im Jupyter-Kontext nicht ermittelbar → LOG_jupyter_notebook.log
            with patch.object(AUTO_IMPORT_LAZY_LOAD, "_resolve_notebook_name", return_value=None):
                self.assertEqual(AUTO_IMPORT_LAZY_LOAD.resolve_log_file_name(), "LOG_jupyter_notebook.log")

        # Terminal interactive shell is NOT Jupyter notebook
        mock_ipython_term = MagicMock()
        mock_terminal_shell = MagicMock(spec=[])   # spec=[] → no auto-attributes
        type(mock_terminal_shell).__name__ = "TerminalInteractiveShell"
        mock_terminal_shell.configure_mock(**{"config": {}})
        mock_ipython_term.get_ipython.return_value = mock_terminal_shell
        with patch.dict(os.environ, {}, clear=True):
            with patch("sys.argv", ["python"]):
                with patch.dict(sys.modules, {"IPython": mock_ipython_term}):
                    self.assertFalse(AUTO_IMPORT_LAZY_LOAD.is_jupyter_environment())
                    self.assertEqual(AUTO_IMPORT_LAZY_LOAD.resolve_log_file_name(), "app_import_terminal.log")


if __name__ == "__main__":
    unittest.main()
