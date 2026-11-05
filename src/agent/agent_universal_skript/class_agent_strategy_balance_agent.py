"""
Modul: class_agent_strategy_balance_agent
Bezeichnung: Multi-Agenten-Strategiekonfiguration und dynamische Modell-Skalierung
Inhaltlicher Schwerpunkt:
Ermittlung von Komplexitäts-Tiers (LOW vs. HIGH) basierend auf Dateigröße und AST-Metriken,
Zuweisung spezialisierter LLM-Modelle an Rollen (Router, Guard, Context, Refactor, Verification).
"""

import ast
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# Globale Bindings
logger = globals().get("class_logger_audit_execution")
core_infra = globals().get("class_tool_core_infrastructure")
ollama_manager = globals().get("class_tool_ollama_service_manager")


class class_agent_strategy_balance_agent:
    """
    Zentrale Konfiguration für die Multi-Agent-Strategie.
    Wählt Modelle dynamisch basierend auf Quellcodekomplexität und Dateigröße.
    """

    _cfg = globals().setdefault("_AGENT_STRATEGY_CONFIG", {})

    OLAMA_MODEL_CODE_LOW: str = _cfg.setdefault("OLAMA_MODEL_CODE_LOW", "codestral:22b")
    OLAMA_MODEL_LOGIC_LOW: str = _cfg.setdefault("OLAMA_MODEL_LOGIC_LOW", "deepseek-r1:8b")
    OLAMA_MODEL_TEXT_LOW: str = _cfg.setdefault("OLAMA_MODEL_TEXT_LOW", "moondream")

    OLAMA_MODEL_CODE_HIGH: str = _cfg.setdefault("OLAMA_MODEL_CODE_HIGH", "qwen3-coder-next-ud-q4-k-xl")
    OLAMA_MODEL_LOGIC_HIGH: str = _cfg.setdefault("OLAMA_MODEL_LOGIC_HIGH", "qwen3.5:122b")
    OLAMA_MODEL_TEXT_HIGH: str = _cfg.setdefault("OLAMA_MODEL_TEXT_HIGH", "gemma3:4b")

    FILE_SIZE_THRESHOLD_LINES: int = _cfg.setdefault("FILE_SIZE_THRESHOLD_LINES", 500)
    FILE_SIZE_THRESHOLD_CHARS: int = _cfg.setdefault("FILE_SIZE_THRESHOLD_CHARS", 15000)
    COMPLEXITY_THRESHOLD: int = _cfg.setdefault("COMPLEXITY_THRESHOLD", 10)

    AGENT_ROUTER: Dict[str, Any] = {
        "name": "Router-Agent",
        "role": "Coordinator & Bug-Type Classifier",
        "model_low": OLAMA_MODEL_LOGIC_LOW,
        "model_high": OLAMA_MODEL_LOGIC_HIGH,
        "priority": 1,
    }

    AGENT_STRUCTURE_GUARD: Dict[str, Any] = {
        "name": "Structure-Guard-Agent",
        "role": "Zero-Loss AST-Checker & Micro-Patcher",
        "model_low": OLAMA_MODEL_CODE_LOW,
        "model_high": OLAMA_MODEL_CODE_HIGH,
        "priority": 2,
    }

    AGENT_CONTEXT_ANALYZER: Dict[str, Any] = {
        "name": "Context-Agent",
        "role": "Log-Analyzer & Error Pattern Extractor",
        "model_low": OLAMA_MODEL_LOGIC_LOW,
        "model_high": OLAMA_MODEL_LOGIC_HIGH,
        "priority": 3,
    }

    AGENT_REFACTOR: Dict[str, Any] = {
        "name": "Refactor-Agent",
        "role": "Code-optimizer & ABI-Integrity-Protector",
        "model_low": OLAMA_MODEL_CODE_LOW,
        "model_high": OLAMA_MODEL_CODE_HIGH,
        "priority": 4,
    }

    AGENT_VERIFICATION: Dict[str, Any] = {
        "name": "Verification-Agent",
        "role": "Closed-Loop-Test & Shrinkage-Validator",
        "model_low": OLAMA_MODEL_CODE_LOW,
        "model_high": OLAMA_MODEL_CODE_HIGH,
        "priority": 5,
    }

    @classmethod
    def determine_tier(cls, file_path: Path = None, content: str = "") -> str:
        """Ermittelt dynamisch die Komplexitätsstufe (LOW oder HIGH) für den Quelltext."""
        print("[class_agent_strategy_balance_agent] Starte Arbeit: determine_tier wird jetzt ausgeführt.")
        if not content and file_path and Path(file_path).exists():
            try:
                content = Path(file_path).read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                print(f"[class_agent_strategy_balance_agent] FEHLER: determine_tier hat die Aufgabe nicht erfüllt. Grund: Datei nicht lesbar: {e}")
                return "LOW"

        lines = len(content.splitlines())
        chars = len(content)
        complexity = cls._estimate_complexity(content)

        if lines > cls.FILE_SIZE_THRESHOLD_LINES or chars > cls.FILE_SIZE_THRESHOLD_CHARS or complexity > cls.COMPLEXITY_THRESHOLD:
            tier = "HIGH"
        else:
            tier = "LOW"

        if tier not in ("LOW", "HIGH"):
            print(f"[class_agent_strategy_balance_agent] FEHLER: determine_tier hat die Aufgabe nicht erfüllt. Grund: Ungültiger Tier-Wert: {tier}")
            return "LOW"

        print(f"[class_agent_strategy_balance_agent] Erfolg: determine_tier erfolgreich beendet. (Tier={tier})")
        return tier

    @classmethod
    def _estimate_complexity(cls, code: str) -> int:
        """Schätzt die cyclomatische Komplexität des Codes per AST ab."""
        print("[class_agent_strategy_balance_agent] Starte Arbeit: _estimate_complexity wird jetzt ausgeführt.")
        try:
            tree = ast.parse(code)
            complexity = 1
            for node in ast.walk(tree):
                if isinstance(node, (ast.If, ast.For, ast.While, ast.Try, ast.ExceptHandler)):
                    complexity += 1
                elif isinstance(node, ast.BoolOp):
                    complexity += len(node.values) - 1

            if complexity is None or not isinstance(complexity, int):
                print("[class_agent_strategy_balance_agent] FEHLER: _estimate_complexity hat die Aufgabe nicht erfüllt. Grund: Kein gültiger Integer-Wert ermittelt.")
                return 1

            print(f"[class_agent_strategy_balance_agent] Erfolg: _estimate_complexity erfolgreich beendet. (Komplexität={complexity})")
            return complexity
        except Exception as e:
            print(f"[class_agent_strategy_balance_agent] FEHLER: _estimate_complexity hat die Aufgabe nicht erfüllt. Grund: {e}")
            return 1

    @classmethod
    def get_agent_model(cls, agent_type: str, file_path: Path = None, content: str = "") -> str:
        """Liefert das zuständige Modell für einen Agententyp basierend auf dem Tier."""
        print(f"[class_agent_strategy_balance_agent] Starte Arbeit: get_agent_model wird jetzt ausgeführt. (Parameter: agent_type={agent_type})")
        tier = cls.determine_tier(file_path, content)
        agent_configs = {
            "router": cls.AGENT_ROUTER,
            "structure_guard": cls.AGENT_STRUCTURE_GUARD,
            "context_analyzer": cls.AGENT_CONTEXT_ANALYZER,
            "refactor": cls.AGENT_REFACTOR,
            "verification": cls.AGENT_VERIFICATION,
        }
        cfg = agent_configs.get(agent_type.lower())
        if not cfg:
            print(f"[class_agent_strategy_balance_agent] FEHLER: get_agent_model hat die Aufgabe nicht erfüllt. Grund: Unbekannter Agententyp '{agent_type}'")
            return cls.OLAMA_MODEL_CODE_LOW

        model = cfg["model_high"] if tier == "HIGH" else cfg["model_low"]

        if not model:
            print(f"[class_agent_strategy_balance_agent] FEHLER: get_agent_model hat die Aufgabe nicht erfüllt. Grund: Kein Modell für Typ '{agent_type}' gefunden.")
            return cls.OLAMA_MODEL_CODE_LOW

        print(f"[class_agent_strategy_balance_agent] Erfolg: get_agent_model erfolgreich beendet. (Modell={model})")
        return model

    @classmethod
    def log_strategy_decision(cls, detail: str, agent_name: str = "-", tier: str = "-"):
        """Protokolliert strategische Zuweisungen im zentralen Logger."""
        print(f"[class_agent_strategy_balance_agent] Starte Arbeit: log_strategy_decision wird jetzt ausgeführt. (Parameter: agent_name={agent_name}, tier={tier})")
        log_tool = globals().get("class_logger_audit_execution")
        if log_tool and hasattr(log_tool, "write_log"):
            log_tool.write_log(
                phase="STRATEGY",
                event="AGENT_SELECT",
                module=agent_name,
                detail=f"{detail} | TIER={tier}",
                versuch="1"
            )
        print(f"[class_agent_strategy_balance_agent] Erfolg: log_strategy_decision erfolgreich beendet.")

    @classmethod
    def get_all_agent_configs(cls) -> List[Dict]:
        """Gibt die Liste aller konfigurierten Agenten zurück."""
        print("[class_agent_strategy_balance_agent] Starte Arbeit: get_all_agent_configs wird jetzt ausgeführt.")
        result = [
            cls.AGENT_ROUTER,
            cls.AGENT_STRUCTURE_GUARD,
            cls.AGENT_CONTEXT_ANALYZER,
            cls.AGENT_REFACTOR,
            cls.AGENT_VERIFICATION,
        ]

        if result is None:
            print("[class_agent_strategy_balance_agent] FEHLER: get_all_agent_configs hat die Aufgabe nicht erfüllt. Grund: Keine Agenten-Konfigurationen vorhanden.")
            return []

        print(f"[class_agent_strategy_balance_agent] Erfolg: get_all_agent_configs erfolgreich beendet. ({len(result)} Agenten)")
        return result

    @classmethod
    def get_agent_by_name(cls, name: str) -> Optional[Dict]:
        """Sucht einen Agenten anhand seines Namens."""
        print(f"[class_agent_strategy_balance_agent] Starte Arbeit: get_agent_by_name wird jetzt ausgeführt. (Parameter: name={name})")
        for agent in cls.get_all_agent_configs():
            if agent["name"] == name:
                print(f"[class_agent_strategy_balance_agent] Erfolg: get_agent_by_name erfolgreich beendet. (Gefunden: {name})")
                return agent

        print(f"[class_agent_strategy_balance_agent] Erfolg: get_agent_by_name erfolgreich beendet. (Agent '{name}' nicht vorhanden – None zurückgegeben)")
        return None

    @classmethod
    def run_strategy_agent(cls, file_path: Path = None, content: str = "") -> dict:
        """
        Zentrale Ausführungsfunktion: Bündelt die vollständige Analyse einer Datei
        und weist allen Agentenrollen die optimalen Modelle zu.
        """
        print("[class_agent_strategy_balance_agent] Starte Arbeit: run_strategy_agent wird jetzt ausgeführt.")
        try:
            tier = cls.determine_tier(file_path=file_path, content=content)
            assignments = {}
            for role in ["router", "structure_guard", "context_analyzer", "refactor", "verification"]:
                assignments[role] = cls.get_agent_model(role, file_path=file_path, content=content)

            cls.log_strategy_decision(detail="Strategie-Zuweisung", agent_name="Strategy", tier=tier)

            result = {
                "tier": tier,
                "model_assignments": assignments,
                "configs": cls.get_all_agent_configs()
            }

            if result is None:
                print("[class_agent_strategy_balance_agent] FEHLER: run_strategy_agent hat die Aufgabe nicht erfüllt. Grund: Kein Ergebnis-Dictionary erzeugt.")
                return None

            print(f"[class_agent_strategy_balance_agent] Erfolg: run_strategy_agent erfolgreich beendet. (Tier={tier})")
            return result
        except Exception as e:
            print(f"[class_agent_strategy_balance_agent] FEHLER: run_strategy_agent hat die Aufgabe nicht erfüllt. Grund: {e}")
            return None
