#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
══════════════════════════════════════════════════════════════════════════════
BALANCED MULTI-AGENT STRATEGY CONFIGURATION v1.0
══════════════════════════════════════════════════════════════════════════════
Multi-Agent Architecture mit Skalierbarkeit für verschiedene Dateigrößen und
Komplexitätsstufen:
  - LOW  (schnell, leicht)    → codestral:22b, deepseek-r1:8b, moondream
  - HIGH (mächtig, tief)      → qwen3-coder-next-ud-q4-k-xl, qwen3.5:122b, gemma3:4b

Agenten-Rollen:
  1. Router-Agent       → Qwen 3 (balanced, logisch)
  2. Structure-Guard    → Codestral (AST-präzise, Zero-Loss)
  3. Context-Agent      → Qwen 3 (Log-Analyse, Mustererkennung)
  4. Refactor-Agent     → Qwen 3 (Code-Optimierung, ABI-Integrität)
  5. Verification-Agent → Codestral (Closed-Loop, Shrinkage-Check)
"""

import ast
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# Auto-Bootstrap & Global Registry (nur lokal für Zugriff auf Werkzeuge)
# Hinweis: auto_bootstrap ist im globalen Scope von agent_repair_agent.py bereits aufgerufen
try:
    from agent_universal_skript.auto_bootstrap_and_register_agent_tools import (
        auto_bootstrap_and_register_agent_tools,
    )
    auto_bootstrap_and_register_agent_tools()
except ImportError:
    pass

# Zugriff auf zentrale Werkzeuge über globale Registry
logger = globals().get("class_logger_audit_execution")
core_infra = globals().get("class_tool_core_infrastructure")
ollama_manager = globals().get("class_tool_ollama_service_manager")


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBALE KONFIGURATION (Strategy Settings)
# ═══════════════════════════════════════════════════════════════════════════════

class class_agent_strategy_balance_agent:
    """
    Zentrale Konfiguration für die Multi-Agent-Strategie mit
    dynamischer Modellauswahl basierend auf Dateigröße und Komplexität.
    """

    # ─────────────────────────────────────────────────────────────────────────────
    # MODEL CONFIGURATION (LOW vs. HIGH Tier)
    # ─────────────────────────────────────────────────────────────────────────────
    _cfg: Dict[str, Any] = globals().setdefault("_AGENT_STRATEGY_CONFIG", {})

    # LOW-TIER MODELLE (schnell, effizient, für kleine Dateien)
    OLAMA_MODEL_CODE_LOW: str = _cfg.setdefault("OLAMA_MODEL_CODE_LOW", "codestral:22b")
    OLAMA_MODEL_LOGIC_LOW: str = _cfg.setdefault("OLAMA_MODEL_LOGIC_LOW", "deepseek-r1:8b")
    OLAMA_MODEL_TEXT_LOW: str = _cfg.setdefault("OLAMA_MODEL_TEXT_LOW", "moondream")

    # HIGH-TIER MODELLE (mächtig, tiefgehend, für große Projekte)
    OLAMA_MODEL_CODE_HIGH: str = _cfg.setdefault("OLAMA_MODEL_CODE_HIGH", "qwen3-coder-next-ud-q4-k-xl")
    OLAMA_MODEL_LOGIC_HIGH: str = _cfg.setdefault("OLAMA_MODEL_LOGIC_HIGH", "qwen3.5:122b")
    OLAMA_MODEL_TEXT_HIGH: str = _cfg.setdefault("OLAMA_MODEL_TEXT_HIGH", "gemma3:4b")

    # THRESHOLDS für Skalierung
    FILE_SIZE_THRESHOLD_LINES: int = _cfg.setdefault("FILE_SIZE_THRESHOLD_LINES", 500)
    FILE_SIZE_THRESHOLD_CHARS: int = _cfg.setdefault("FILE_SIZE_THRESHOLD_CHARS", 15000)
    COMPLEXITY_THRESHOLD: int = _cfg.setdefault("COMPLEXITY_THRESHOLD", 10)  # Cyclomatic Complexity

    # ─────────────────────────────────────────────────────────────────────────────
    # AGENT ROLES & CONFIGURATION
    # ─────────────────────────────────────────────────────────────────────────────
    AGENT_ROUTER: Dict[str, str] = {
        "name": "Router-Agent",
        "role": "Coordinator & Bug-Type Classifier",
        "model_low": OLAMA_MODEL_LOGIC_LOW,
        "model_high": OLAMA_MODEL_LOGIC_HIGH,
        "priority": 1,
    }

    AGENT_STRUCTURE_GUARD: Dict[str, str] = {
        "name": "Structure-Guard-Agent",
        "role": "Zero-Loss AST-Checker & Micro-Patcher",
        "model_low": OLAMA_MODEL_CODE_LOW,
        "model_high": OLAMA_MODEL_CODE_HIGH,
        "priority": 2,
    }

    AGENT_CONTEXT_ANALYZER: Dict[str, str] = {
        "name": "Context-Agent",
        "role": "Log-Analyzer & Error Pattern Extractor",
        "model_low": OLAMA_MODEL_LOGIC_LOW,
        "model_high": OLAMA_MODEL_LOGIC_HIGH,
        "priority": 3,
    }

    AGENT_REFACTOR: Dict[str, str] = {
        "name": "Refactor-Agent",
        "role": "Code-optimizer & ABI-Integrity-Protector",
        "model_low": OLAMA_MODEL_CODE_LOW,
        "model_high": OLAMA_MODEL_CODE_HIGH,
        "priority": 4,
    }

    AGENT_VERIFICATION: Dict[str, str] = {
        "name": "Verification-Agent",
        "role": "Closed-Loop-Test & Shrinkage-Validator",
        "model_low": OLAMA_MODEL_CODE_LOW,
        "model_high": OLAMA_MODEL_CODE_HIGH,
        "priority": 5,
    }

    # ─────────────────────────────────────────────────────────────────────────────
    # STRATEGY SWITCHING LOGIC
    # ─────────────────────────────────────────────────────────────────────────────
    @classmethod
    def determine_tier(cls, file_path: Path = None, content: str = "") -> str:
        """
        Entscheidet dynamisch between LOW und HIGH Tier basierend auf:
          - Dateigröße (Zeilen & Zeichen)
          - Komplexität (AST-Analyse)
        Returns: "LOW" or "HIGH"
        """
        if not content and file_path and file_path.exists():
            content = file_path.read_text(encoding="utf-8", errors="replace")

        # Messung
        lines = len(content.splitlines())
        chars = len(content)

        # AST-basierte Komplexitätsanalyse (Cyclomatic Complexity)
        complexity = cls._estimate_complexity(content)

        # Entscheidungslogik
        if (lines > cls.FILE_SIZE_THRESHOLD_LINES or
            chars > cls.FILE_SIZE_THRESHOLD_CHARS or
            complexity > cls.COMPLEXITY_THRESHOLD):
            return "HIGH"
        return "LOW"

    @classmethod
    def _estimate_complexity(cls, code: str) -> int:
        """Rough AST-basierte Abschätzung der cyclomatischen Komplexität."""
        try:
            tree = ast.parse(code)
            complexity = 1  # Basis-Komplexität

            for node in ast.walk(tree):
                # Jeder if/elif/else/for/while/try/except/and/or erhöht die Komplexität
                if isinstance(node, (ast.If, ast.For, ast.While, ast.Try, ast.ExceptHandler)):
                    complexity += 1
                elif isinstance(node, ast.BoolOp):
                    complexity += len(node.values) - 1

            return complexity
        except Exception:
            return 1  # Fallback: einfacher Code

    @classmethod
    def get_agent_model(cls, agent_type: str, file_path: Path = None, content: str = "") -> str:
        """
        Ermittelt das passende Modell für einen Agenten basierend auf Tier.
        """
        tier = cls.determine_tier(file_path, content)

        agent_configs = {
            "router": cls.AGENT_ROUTER,
            "structure_guard": cls.AGENT_STRUCTURE_GUARD,
            "context_analyzer": cls.AGENT_CONTEXT_ANALYZER,
            "refactor": cls.AGENT_REFACTOR,
            "verification": cls.AGENT_VERIFICATION,
        }

        agent_config = agent_configs.get(agent_type.lower())
        if not agent_config:
            raise ValueError(f"Unbekannter Agent-Typ: {agent_type}")

        return agent_config["model_high"] if tier == "HIGH" else agent_config["model_low"]

    # ─────────────────────────────────────────────────────────────────────────────
    # LOGGING KONFIGURATION
    # ─────────────────────────────────────────────────────────────────────────────
    LOG_PHASE_STRATEGY: str = "STRATEGY"
    LOG_EVENT_AGENT_SELECT: str = "AGENT_SELECT"
    LOG_EVENT_TIER_DETECTED: str = "TIER_DETECTED"
    LOG_EVENT_DELEGATION: str = "DELEGATION"

    @classmethod
    def log_strategy_decision(cls, detail: str, agent_name: str = "-", tier: str = "-"):
        """Protokolliert Strategie-Entscheidungen mit Logger."""
        if logger:
            logger.write_log(
                phase=cls.LOG_PHASE_STRATEGY,
                event=cls.LOG_EVENT_AGENT_SELECT,
                module=agent_name,
                detail=f"{detail} | TIER={tier}",
                versuch="1",
            )

    # ─────────────────────────────────────────────────────────────────────────────
    # HILFSFUNKTIONEN
    # ─────────────────────────────────────────────────────────────────────────────
    @classmethod
    def get_all_agent_configs(cls) -> List[Dict]:
        """Gibt alle Agenten-Konfigurationen als Liste zurück."""
        return [
            cls.AGENT_ROUTER,
            cls.AGENT_STRUCTURE_GUARD,
            cls.AGENT_CONTEXT_ANALYZER,
            cls.AGENT_REFACTOR,
            cls.AGENT_VERIFICATION,
        ]

    @classmethod
    def get_agent_by_name(cls, name: str) -> Optional[Dict]:
        """Sucht einen Agenten anhand seines Namens."""
        for agent in cls.get_all_agent_configs():
            if agent["name"] == name:
                return agent
        return None


# Direkte Initialisierung beim Import
if __name__ == "__main__":
    print("=" * 80)
    print("BALANCED MULTI-AGENT STRATEGY CONFIGURATION")
    print("=" * 80)

    # Beispiel: Testen der Tier-Erkennung
    test_code = "def hello(): print('World')"
    small_file = Path(__file__)
    large_file = Path("src/agent/agent_repair_agent.py")

    print(f"\n[KLEINE DATEI] {small_file.name}")
    tier_small = class_agent_strategy_balance_agent.determine_tier(small_file)
    model_small = class_agent_strategy_balance_agent.get_agent_model("router", small_file)
    print(f"  → Tier: {tier_small}")
    print(f"  → Router-Modell: {model_small}")

    if large_file.exists():
        print(f"\n[GROßE DATEI] {large_file.name}")
        tier_large = class_agent_strategy_balance_agent.determine_tier(large_file)
        model_large = class_agent_strategy_balance_agent.get_agent_model("router", large_file)
        print(f"  → Tier: {tier_large}")
        print(f"  → Router-Modell: {model_large}")

    print("\n[AGENTEN-KONFIGURATION]")
    for agent in class_agent_strategy_balance_agent.get_all_agent_configs():
        print(f"  - {agent['name']}: {agent['role']}")

    print("\n" + "=" * 80)
    print("✅ Strategy-Config initialized successfully.")
    print("=" * 80)
