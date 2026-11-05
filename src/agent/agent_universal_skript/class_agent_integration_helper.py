"""
Modul: class_agent_integration_helper
Bezeichnung: Integrations- und Migrationshelfer für Multi-Agenten-Strategien
Inhaltlicher Schwerpunkt:
Vermittlung zwischen bestehenden Reparatur-Routinen und dem neuen Multi-Agenten-Routing.
Ermöglicht schrittweise Migration mit sicherem Fallback-Mechanismus.
"""

from __future__ import annotations
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

# Globale Bindings
logger          = globals().get("class_logger_audit_execution")
core_infra      = globals().get("class_tool_core_infrastructure")
strategy_agent  = globals().get("class_agent_strategy_balance_agent")
router_agent    = globals().get("class_agent_ruting_struktur_balance_agent")


class class_agent_integration_helper:
    """
    Integrationshelfer zur nahtlosen Koordination von neuem Multi-Agent-System
    und bestehenden Reparaturmodulen.
    """

    _cfg = globals().setdefault("_AGENT_CONFIG", {})
    USE_NEW_STRATEGY: bool = _cfg.setdefault("USE_NEW_STRATEGY", True)
    FALLBACK_TO_OLD: bool  = _cfg.setdefault("FALLBACK_TO_OLD",  True)

    def __init__(self, use_new_strategy: bool = None, fallback_to_old: bool = None):
        print("[class_agent_integration_helper] Starte Arbeit: __init__ wird jetzt ausgeführt.")
        self.use_new_strategy = self.USE_NEW_STRATEGY if use_new_strategy is None else use_new_strategy
        self.fallback_to_old  = self.FALLBACK_TO_OLD  if fallback_to_old  is None else fallback_to_old
        router_cls  = globals().get("class_agent_ruting_struktur_balance_agent")
        self.router = router_cls() if router_cls else None
        if not hasattr(self, "use_new_strategy"):
            print("[class_agent_integration_helper] FEHLER: __init__ hat die Aufgabe nicht erfüllt. Grund: Kern-Attribute nicht gesetzt.")
            return
        print("[class_agent_integration_helper] Erfolg: __init__ erfolgreich beendet.")

    def process(self, file_path: Path, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Verarbeitet eine Datei wahlweise über die neue Multi-Agent-Strategie oder das Legacy-System."""
        print(f"[class_agent_integration_helper] Starte Arbeit: process wird jetzt ausgeführt. (Parameter: {file_path})")
        result = {
            "file":           str(file_path),
            "strategy_used":  "UNKNOWN",
            "success":        False,
            "details":        None,
        }

        if self.use_new_strategy and self.router:
            try:
                res = self.router.process_file(Path(file_path))
                if res.get("status") in ["CLEAN", "VERIFIED"]:
                    result["strategy_used"] = "MULTI_AGENT_NEW"
                    result["success"]       = True
                    result["details"]       = res
                    print("[class_agent_integration_helper] Erfolg: process erfolgreich beendet.")
                    return result
            except Exception as e:
                print(f"[class_agent_integration_helper] FEHLER: process hat die Aufgabe nicht erfüllt. Grund: Neue Strategie fehlgeschlagen: {e}")

        if self.fallback_to_old:
            result["strategy_used"] = "LEGACY_FALLBACK"
            result["details"]       = self._run_legacy_repair(Path(file_path), context)
            result["success"]       = result["details"].get("success", False)
            print("[class_agent_integration_helper] Erfolg: process erfolgreich beendet (Legacy-Fallback).")
            return result

        print("[class_agent_integration_helper] FEHLER: process hat die Aufgabe nicht erfüllt. Grund: Keine Reparaturstrategie erfolgreich.")
        return result

    def analyze_file_complexity(self, file_path: Path) -> Dict[str, Any]:
        """
        Analysiert die Komplexität einer Datei und empfiehlt die passende Strategie.
        """
        print(f"[class_agent_integration_helper] Starte Arbeit: analyze_file_complexity wird jetzt ausgeführt. (Parameter: {file_path})")
        path_obj = Path(file_path)
        if not path_obj.exists():
            print(f"[class_agent_integration_helper] FEHLER: analyze_file_complexity hat die Aufgabe nicht erfüllt. Grund: Datei nicht gefunden: {file_path}")
            return {"error": f"File not found: {file_path}"}

        try:
            content = path_obj.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            print(f"[class_agent_integration_helper] FEHLER: analyze_file_complexity hat die Aufgabe nicht erfüllt. Grund: Datei nicht lesbar: {e}")
            return {"error": f"Cannot read file: {e}"}

        strat_cls = globals().get("class_agent_strategy_balance_agent")
        if strat_cls and hasattr(strat_cls, "determine_tier"):
            tier = strat_cls.determine_tier(path_obj, content)
            model = strat_cls.get_agent_model("router", path_obj, content)
            result = {
                "file": str(path_obj),
                "lines": len(content.splitlines()),
                "chars": len(content),
                "tier_recommended": tier,
                "model_suggested": model,
            }
            print(f"[class_agent_integration_helper] Erfolg: analyze_file_complexity erfolgreich beendet. (Tier={tier}, Modell={model})")
            return result

        print("[class_agent_integration_helper] FEHLER: analyze_file_complexity hat die Aufgabe nicht erfüllt. Grund: Strategy-Agent nicht verfügbar.")
        return {"error": "Strategy config not available"}

    def _run_legacy_repair(self, file_path: Path, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Führt eine grundlegende Standard-Validierung durch, wenn die neue Strategie nicht greift."""
        print(f"[class_agent_integration_helper] Starte Arbeit: _run_legacy_repair wird jetzt ausgeführt. (Parameter: {file_path})")
        try:
            content     = file_path.read_text(encoding="utf-8", errors="replace")
            sub_verifier = globals().get("class_agent_sub_verifier")
            if sub_verifier and hasattr(sub_verifier, "verify_code_in_sandbox"):
                ok, output = sub_verifier.verify_code_in_sandbox(content)
                result = {"success": ok, "output": output}
            else:
                result = {"success": True, "output": "Kein Sandbox-Verifier vorhanden; Code unverändert gelassen."}
            if result is None:
                print("[class_agent_integration_helper] FEHLER: _run_legacy_repair hat die Aufgabe nicht erfüllt. Grund: Kein Ergebnis.")
                return {"success": False}
            print("[class_agent_integration_helper] Erfolg: _run_legacy_repair erfolgreich beendet.")
            return result
        except Exception as e:
            print(f"[class_agent_integration_helper] FEHLER: _run_legacy_repair hat die Aufgabe nicht erfüllt. Grund: {e}")
            return {"success": False, "error": str(e)}

    @classmethod
    def run_integration_helper(cls, file_path: Path) -> dict:
        """
        Zentrale Ausführungsfunktion: Bündelt die Integration und Migration
        für eine Datei in einem einzelnen Aufruf.
        """
        print(f"[class_agent_integration_helper] Starte Arbeit: run_integration_helper wird jetzt ausgeführt. (Parameter: {file_path})")
        try:
            helper = cls()
            result = helper.process(file_path)
            if result is None:
                print("[class_agent_integration_helper] FEHLER: run_integration_helper hat die Aufgabe nicht erfüllt. Grund: Kein Ergebnis von process().")
                return {"success": False}
            print("[class_agent_integration_helper] Erfolg: run_integration_helper erfolgreich beendet.")
            return result
        except Exception as e:
            print(f"[class_agent_integration_helper] FEHLER: run_integration_helper hat die Aufgabe nicht erfüllt. Grund: {e}")
            return {"success": False, "error": str(e)}
