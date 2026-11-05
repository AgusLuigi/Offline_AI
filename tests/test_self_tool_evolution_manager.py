#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-Tests für class_self_tool_evolution_manager:
1. Introspektion & Bestandserfassung (Prüfung library_registry, Anti-Code-Shrinking)
2. Sandbox-Verifikation & Real-Testing via SubAgentVerifier
3. Additive Persistierung in library_registry (non-destruktiv)
4. Dynamischer RAM-Bootstrap (Runtime Capability Injection via exec() in den Arbeitsspeicher)
"""

import os
import sys
import unittest
from pathlib import Path

# Projekt-Root ermitteln
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src" / "agent"))
sys.path.insert(0, str(project_root / "src" / "agent" / "agent_universal_skript"))

from class_self_tool_evolution_manager import class_self_tool_evolution_manager
from class_tool_core_infrastructure import class_tool_core_infrastructure


class TestSelfToolEvolutionManager(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db_path = str(class_tool_core_infrastructure.get_database_path())
        cls.manager = class_self_tool_evolution_manager(db_path=cls.db_path)

    def test_01_introspect_existing_library(self):
        """Testet die Introspektion der bestehenden library_registry."""
        inventory = self.manager.introspect_existing_library()
        self.assertIsInstance(inventory, dict)
        self.assertIn("total_count", inventory)
        self.assertGreater(inventory["total_count"], 0)
        self.assertIn("functions", inventory)
        self.assertIn("nodes", inventory)
        print(f"[TEST 1 OK] Introspektion erfolgreich: {inventory['total_count']} Werkzeuge gefunden.")

    def test_02_duplicate_and_anti_shrinking_guard(self):
        """Testet den Schutz vor Duplikaten und das Anti-Code-Shrinking-Prinzip."""
        # Bereits existierender Knoten [000] 'Mandatory Library Bootstrapping & Core Routing Setup'
        exists = self.manager.check_capability_exists("Mandatory Library Bootstrapping & Core Routing Setup")
        self.assertTrue(exists)

        # Neuer, noch nicht existierender Name
        not_exists = self.manager.check_capability_exists("BrandNewUnseenFunctionXYZ_99999")
        self.assertFalse(not_exists)
        print("[TEST 2 OK] Duplikatserkennung & Anti-Code-Shrinking aktiv.")

    def test_03_sandbox_verification_positive_and_negative(self):
        """Testet die Sandbox-Verifikation (Erfolg bei validem Code, Fehler bei fehlerhaftem Code)."""
        # Valider Code mit den bekannten Log-Meldungen
        valid_code = '''
def dynamic_calculator_add(a: int, b: int) -> int:
    print("[dynamic_calculator_add] Starte Arbeit: dynamic_calculator_add wird jetzt ausgeführt.")
    result = a + b
    if result is None:
        print("[dynamic_calculator_add] FEHLER: Berechnung fehlgeschlagen.")
        return 0
    print("[dynamic_calculator_add] Erfolg: dynamic_calculator_add erfolgreich beendet.")
    return result

print("SANDBOX_TEST_OK:", dynamic_calculator_add(10, 20) == 30)
'''
        is_valid, out = self.manager.verify_tool_in_sandbox("dynamic_calculator_add", valid_code)
        self.assertTrue(is_valid, f"Sandbox failed on valid code: {out}")
        self.assertIn("SANDBOX_TEST_OK: True", out)

        # Invalider Code mit Laufzeitfehler
        invalid_code = '''
def broken_tool():
    raise ZeroDivisionError("Absichtlicher Testfehler")

broken_tool()
'''
        is_valid_broken, out_broken = self.manager.verify_tool_in_sandbox("broken_tool", invalid_code)
        self.assertFalse(is_valid_broken)
        print("[TEST 3 OK] Sandbox-Verifikation unterscheidet zuverlässig zwischen validem und fehlerhaftem Code.")

    def test_04_additive_persistence_and_ram_injection(self):
        """Testet die additive Persistierung in SQL und die sofortige RAM-Injektion."""
        unique_name = f"auto_test_tool_{os.urandom(4).hex()}"
        tool_code = f'''
def {unique_name}(x: int) -> int:
    print(f"[{unique_name}] Starte Arbeit: {unique_name} wird jetzt ausgeführt.")
    res = x * 2
    print(f"[{unique_name}] Erfolg: {unique_name} erfolgreich beendet.")
    return res
'''
        # Ziel-Agenten-Dummy
        class MockAgent:
            pass
        agent = MockAgent()

        # Vollständigen Evolutions-Zyklus (Stufen 1-4) ausführen
        res = self.manager.evolve_and_register_new_tool(
            tool_name=unique_name,
            code_snippet=tool_code,
            description="Test-Werkzeug für automatische RAM-Injektion",
            target_agent=agent
        )

        self.assertEqual(res["status"], "SUCCESS")
        self.assertTrue(res["node_id"].startswith("CAP_"))
        self.assertIn(unique_name, res["injected_functions"])

        # Prüfen, ob das Werkzeug unmittelbar am Agenten im RAM aufrufbar ist
        self.assertTrue(hasattr(agent, unique_name))
        injected_fn = getattr(agent, unique_name)
        result_call = injected_fn(21)
        self.assertEqual(result_call, 42)
        print(f"[TEST 4 OK] Werkzeug '{unique_name}' erfolgreich persistiert, in RAM injiziert und ausgeführt (21 * 2 = 42)!")

    def test_05_bootstrap_ram_capabilities(self):
        """Testet den automatischen RAM-Bootstrap aller aktiven Fähigkeiten beim Start."""
        class MockAgentBoot:
            pass
        boot_agent = MockAgentBoot()

        boot_res = self.manager.bootstrap_ram_capabilities(target_agent=boot_agent)
        self.assertEqual(boot_res["status"], "SUCCESS")
        self.assertGreaterEqual(boot_res["bootstrapped_count"], 1)
        print(f"[TEST 5 OK] RAM-Bootstrap erfolgreich: {boot_res['bootstrapped_count']} Fähigkeiten in den RAM geladen.")


if __name__ == "__main__":
    unittest.main()
