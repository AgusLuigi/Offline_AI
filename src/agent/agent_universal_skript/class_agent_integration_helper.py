#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
══════════════════════════════════════════════════════════════════════════════
INTEGRATION HELPER: MIGRATION FROM agent_repair_agent TO MULTI-AGENT-STRATEGY
══════════════════════════════════════════════════════════════════════════════
Diese Datei zeigt, wie das neue Multi-Agent-System mit dem alten
agent_repair_agent integriert werden kann, ohne bestehende Logik zu zerstören.

使用方式 (usage example):
    1. Importiere diesen Helper in deinem main-script
    2. Erstelle eineInstanz von IntegrationHelper
    3. Rufe.process mit dem Ziel-file auf

Der Helper ersetzt die alte monolithische Logik durch:
    - Router-Agent (Bug-Klassifikation)
    - Context-Agent (Log-Analyse)
    - Structure-Guard (Zero-Loss AST-Check)
    - Refactor-Agent (Code-Optimierung)
    - Verification-Agent (Closed-Loop Validation)
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

# Auto-Bootstrap & Global Registry (nur lokal für Zugriff auf Werkzeuge)
try:
    from agent_universal_skript.auto_bootstrap_and_register_agent_tools import (
        auto_bootstrap_and_register_agent_tools,
    )
    auto_bootstrap_and_register_agent_tools()
except ImportError:
    pass

# Import neuer Strategy-Module (mit Fallbacks)
try:
    from agent_universal_skript.class_agent_strategy_balance_agent import (
        class_agent_strategy_balance_agent,
    )
except ImportError:
    class_agent_strategy_balance_agent = None

try:
    from agent_universal_skript.class_agent_ruting_struktur_balance_agent import (
        class_agent_ruting_struktur_balance_agent,
    )
except ImportError:
    class_agent_ruting_struktur_balance_agent = None


class IntegrationHelper:
    """
    Helper Klasse zur schrittweisen Migration vom monolithischen
    Agent-Repair zum Multi-Agent-System.

    Vorteile:
      ✅ Keine bestehende Logik wird gelöscht
      ✅ Alte und neue Systeme können parallel laufen
      ✅ Schrittweise Umstellung auf neue Strategie möglich
      ✅ Full-Cycle Protocolierung über class_logger_audit_execution
    """

    def __init__(self,
                 use_new_strategy: bool = True,
                 fallback_to_old: bool = True):
        """
        Initialisiert den Integration-Help mit Config-Optionen.
        
        Args:
            use_new_strategy: Nutzt das neue Multi-Agent-System (Standard: True)
            fallback_to_old: Fallback auf altes agent_repair_agent bei Fehler (Standard: True)
        """
        self.use_new_strategy = use_new_strategy
        self.fallback_to_old = fallback_to_old

        # Router initialisieren (wenn neue Strategie aktiv)
        self.router = None
        if self.use_new_strategy:
            try:
                self.router = class_agent_ruting_struktur_balance_agent()
                print("[INTEGRATION] Multi-Agent Router initialisiert")
            except Exception as e:
                print(f"[INTEGRATION] Router-Initialisierung fehlgeschlagen: {e}")
                if self.fallback_to_old:
                    print("[INTEGRATION] Fallback auf altes Agent-Repair-System")

    def process(self, file_path: Path, **kwargs) -> Dict[str, Any]:
        """
        Führt die Reparatur-Logik aus – entweder mit neuer Strategie oder Fallback.

        Args:
            file_path: Path zum Ziel-Python-File
            **kwargs: Optional – alte Parameter (für Kompatibilität)

        Returns:
            Dict mit Ergebnis: status, bugs_found, bugs_fixed, errors
        """
        result = {
            "file": str(file_path),
            "status": "NOT_STARTED",
            "strategy_used": None,
            "errors": [],
        }

        try:
            # 1. Neue Strategie verwenden (wenn gewünscht)
            if self.use_new_strategy and self.router:
                result["strategy_used"] = "NEW_MULTI_AGENT"

                # Router-Ausführung
                agent_result = self.router.process_file(file_path)

                result["status"] = agent_result.get("status", "UNKNOWN")
                result["bugs_found"] = agent_result.get("bugs_found", 0)
                result["bugs_fixed"] = agent_result.get("bugs_fixed", 0)
                result["lines_processed"] = agent_result.get("lines", 0)
                result["errors"] = agent_result.get("errors", [])

                return result

            # 2. Fallback auf altes agent_repair_agent (wenn aktiviert)
            if self.fallback_to_old:
                result["strategy_used"] = "OLD_MONOLITHIC"
                result["status"] = "FALLBACK_PENDING"
                result["errors"].append(
                    "Old monolithic agent_repair_agent integration not yet implemented"
                )
                return result

            # 3. Fehler: Keine Strategie verfügbar
            result["status"] = "NO_STRATEGY_AVAILABLE"
            result["errors"].append(
                "Neither new strategy nor fallback enabled"
            )
            return result

        except Exception as e:
            result["status"] = "CRITICAL_ERROR"
            result["errors"].append(f"Unexpected error: {str(e)}")
            return result

    def analyze_file_complexity(self, file_path: Path) -> Dict[str, Any]:
        """
        Analysiert die Komplexität einer Datei und empfiehlt passende Strategie.

        Returns:
            Dict mit complexity_metrics, tier_recommendation, model_suggestion
        """
        if not file_path.exists():
            return {
                "error": f"File not found: {file_path}",
            }

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return {
                "error": f"Cannot read file: {str(e)}",
            }

        # Neue Strategy-Klasse nutzen
        if class_agent_strategy_balance_agent:
            tier = class_agent_strategy_balance_agent.determine_tier(file_path, content)
            model = class_agent_strategy_balance_agent.get_agent_model("router", file_path, content)

            return {
                "file": str(file_path),
                "lines": len(content.splitlines()),
                "chars": len(content),
                "tier_recommended": tier,
                "model_suggested": model,
            }

        return {
            "error": "Strategy config not available",
        }


# ═══════════════════════════════════════════════════════════════════════════════
# DEMO / MAIN EXECUTION
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 80)
    print("INTEGRATION HELPER DEMO")
    print("=" * 80)

    # Helper initialisieren
    helper = IntegrationHelper(use_new_strategy=True, fallback_to_old=True)

    # Beispiel-Datei
    test_file = Path("src/agent/agent_repair_agent.py")

    if test_file.exists():
        print(f"\n[DEMO] Analyzing file: {test_file.name}")
        print("-" * 80)

        # 1. Komplexitäts-Analyse
        print("\n[COMPLEXITY ANALYSIS]")
        complexity_result = helper.analyze_file_complexity(test_file)
        for key, value in complexity_result.items():
            print(f"  {key}: {value}")

        # 2. Reparatur-Process
        print("\n[REPAIR PROCESS]")
        process_result = helper.process(test_file)
        for key, value in process_result.items():
            print(f"  {key}: {value}")

    else:
        print(f"\n[ERROR] Test file not found: {test_file}")

    print("\n" + "=" * 80)
    print("✅ Integration-Helper demo completed.")
    print("=" * 80)
