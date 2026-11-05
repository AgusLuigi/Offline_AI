"""
Modul: class_agent_ruting_struktur_balance_agent
Bezeichnung: Multi-Agenten Routing- und Delegationssystem
Inhaltlicher Schwerpunkt:
    Autonome Erkennung von Code- und Strukturfehlern (Syntax, Shrinkage, Logic, AST),
    Klassifizierung in BugReports, Generierung von AgentWorkItems und
    geschlossene Patch-Verifikation. Die Datenklassen BugReport und AgentWorkItem
    sind eigenständig in class_bug_report.py bzw. class_agent_work_item.py definiert
    und werden über den globalen Namensraum eingebunden.
"""

from __future__ import annotations
import ast
import datetime
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# Globale Bindings (werden vom Bootstrap-Mechanismus befüllt)
logger          = globals().get("class_logger_audit_execution")
core_infra      = globals().get("class_tool_core_infrastructure")
ollama_manager  = globals().get("class_tool_ollama_service_manager")
sub_verifier    = globals().get("class_agent_sub_verifier")
strategy_agent  = globals().get("class_agent_strategy_balance_agent")

# Datenklassen-Referenzen aus dem globalen Namensraum
BugReport      = globals().get("class_bug_report")
AgentWorkItem  = globals().get("class_agent_work_item")


class class_agent_ruting_struktur_balance_agent:
    """
    Zentrales Routing-System für die Multi-Agenten-Architektur.
    Koordiniert Fehlererkennung, Delegation und Closed-Loop-Validierung.
    """

    _cfg = globals().setdefault("_AGENT_CONFIG", {})
    MAX_DELEGATION_CYCLES: int   = _cfg.setdefault("MAX_DELEGATION_CYCLES",   5)
    MAX_SEQUENTIAL_FAILURES: int = _cfg.setdefault("MAX_SEQUENTIAL_FAILURES", 3)

    # =========================================================================
    # EBENE 4: METHODEN
    # =========================================================================

    def __init__(self):
        print("[class_agent_ruting_struktur_balance_agent] Starte Arbeit: __init__ wird jetzt ausgeführt.")
        self.bug_database: List[Any]        = []
        self.work_queue: List[Any]          = []
        self.history: List[Dict[str, Any]]  = []
        self.consecutive_failures: int      = 0
        self.agent_priorities = {
            "router":           1,
            "context_analyzer": 2,
            "structure_guard":  3,
            "refactor":         4,
            "verification":     5,
        }

        if self.agent_priorities is None:
            print("[class_agent_ruting_struktur_balance_agent] FEHLER: __init__ hat die Aufgabe nicht erfüllt. Grund: agent_priorities konnte nicht gesetzt werden.")
            return

        print("[class_agent_ruting_struktur_balance_agent] Erfolg: __init__ erfolgreich beendet.")

    def detect_bugs_in_code(self, file_path: Path, content: str) -> List[Any]:
        """Analysiert Quellcode auf Fehler und erzeugt BugReport-Instanzen."""
        print(f"[class_agent_ruting_struktur_balance_agent] Starte Arbeit: detect_bugs_in_code wird jetzt ausgeführt. (Parameter: file_path={file_path})")
        BugReportCls = globals().get("class_bug_report")
        bugs    = []
        counter = 0

        # 1. Syntax-Prüfung
        try:
            ast.parse(content)
        except SyntaxError as e:
            counter += 1
            if BugReportCls:
                bugs.append(BugReportCls(
                    bug_id=f"BUG-{counter:03d}", bug_type="SYNTAX",
                    file_path=file_path, line_number=e.lineno, severity="CRITICAL",
                    description=f"SyntaxError: {e.msg}",
                    suggested_fix=f"Syntaxfehler in Zeile {e.lineno} korrigieren",
                    affected_agents=["structure_guard"]
                ))

        # 2. Strukturverlust-Prüfung
        structure_loss = self._check_structure_loss(content)
        if structure_loss and BugReportCls:
            counter += 1
            bugs.append(BugReportCls(
                bug_id=f"BUG-{counter:03d}", bug_type="STRUCTURE",
                file_path=file_path, severity="HIGH",
                description=f"Strukturverlust: {structure_loss}",
                suggested_fix="Wiederherstellen über structure_guard",
                affected_agents=["structure_guard", "refactor"]
            ))

        # 3. Bekannte Fehlermuster prüfen
        known_bugs = self._detect_known_bugs(content, file_path)
        for kb in known_bugs:
            counter += 1
            if BugReportCls:
                bugs.append(BugReportCls(
                    bug_id=f"BUG-{counter:03d}", bug_type=kb["type"],
                    file_path=file_path, severity=kb["severity"],
                    description=kb["description"],
                    suggested_fix=kb["patch_strategy"],
                    affected_agents=kb["affected_agents"]
                ))

        self.bug_database.extend(bugs)
        for b in bugs:
            self._log_bug_detected(b)

        if bugs is None:
            print("[class_agent_ruting_struktur_balance_agent] FEHLER: detect_bugs_in_code hat die Aufgabe nicht erfüllt. Grund: Ergebnis-Liste ist None.")
            return []

        print(f"[class_agent_ruting_struktur_balance_agent] Erfolg: detect_bugs_in_code erfolgreich beendet. ({len(bugs)} Fehler gefunden)")
        return bugs

    def _check_structure_loss(self, content: str) -> Optional[str]:
        """Prüft, ob Klassen oder Funktionen im Modul vorhanden sind."""
        print("[class_agent_ruting_struktur_balance_agent] Starte Arbeit: _check_structure_loss wird jetzt ausgeführt.")
        try:
            tree    = ast.parse(content)
            classes = [n.name for n in tree.body if isinstance(n, ast.ClassDef)]
            funcs   = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
            if not classes and not funcs:
                print("[class_agent_ruting_struktur_balance_agent] Erfolg: _check_structure_loss erfolgreich beendet. (Strukturverlust erkannt)")
                return "Keine Klassen oder Funktionen gefunden"
            print("[class_agent_ruting_struktur_balance_agent] Erfolg: _check_structure_loss erfolgreich beendet. (Struktur intakt)")
            return None
        except Exception as e:
            print(f"[class_agent_ruting_struktur_balance_agent] FEHLER: _check_structure_loss hat die Aufgabe nicht erfüllt. Grund: AST-Parsing fehlgeschlagen: {e}")
            return "AST-Parsing fehlgeschlagen"

    def _check_shrinkage(self, content: str, original_content: Optional[str]) -> Dict[str, Any]:
        """Prüft auf unzulässigen Code-Schwund durch Vergleich der Zeilenanzahl."""
        print("[class_agent_ruting_struktur_balance_agent] Starte Arbeit: _check_shrinkage wird jetzt ausgeführt.")
        if not original_content:
            print("[class_agent_ruting_struktur_balance_agent] Erfolg: _check_shrinkage erfolgreich beendet. (Kein Original, kein Vergleich)")
            return {"detected": False, "ratio": 100.0, "lost_lines": 0}

        orig_lines = len(original_content.splitlines())
        cand_lines = len(content.splitlines())
        if orig_lines > 0:
            ratio = (cand_lines / orig_lines) * 100
            lost  = orig_lines - cand_lines
            if ratio < 80.0:
                print(f"[class_agent_ruting_struktur_balance_agent] Erfolg: _check_shrinkage erfolgreich beendet. (Schwund erkannt: {ratio:.1f}%)")
                return {"detected": True, "ratio": ratio, "lost_lines": lost}

        print(f"[class_agent_ruting_struktur_balance_agent] Erfolg: _check_shrinkage erfolgreich beendet. (Kein Schwund)")
        return {"detected": False, "ratio": 100.0, "lost_lines": 0}

    def _detect_known_bugs(self, content: str, file_path: Path) -> List[Dict]:
        """Erkennt bekannte spezifische Fehlermuster im Projekt."""
        print("[class_agent_ruting_struktur_balance_agent] Starte Arbeit: _detect_known_bugs wird jetzt ausgeführt.")
        bugs = []
        if "class_tool_core_infrastructure" in content and "PROJECT_POINT" not in content:
            bugs.append({
                "type": "STRUCTURE", "severity": "CRITICAL",
                "description": "PROJECT_POINT fehlt in class_tool_core_infrastructure",
                "patch_strategy": "Attribut PROJECT_POINT = 'src' hinzufügen",
                "affected_agents": ["structure_guard"]
            })
        if "get_file_skeleton(file_path" in content and "@staticmethod" not in content:
            bugs.append({
                "type": "STRUCTURE", "severity": "HIGH",
                "description": "get_file_skeleton fehlt @staticmethod",
                "patch_strategy": "@staticmethod voranstellen",
                "affected_agents": ["structure_guard"]
            })
        if re.search(r"class\s+\w+\s*\([^)]*if\s+\w+\s+else\s+object", content):
            bugs.append({
                "type": "STRUCTURE", "severity": "CRITICAL",
                "description": "MRO-Konflikt durch dynamische Vererbung",
                "patch_strategy": "Dynamische Basisklasse bereinigen",
                "affected_agents": ["structure_guard"]
            })

        if bugs is None:
            print("[class_agent_ruting_struktur_balance_agent] FEHLER: _detect_known_bugs hat die Aufgabe nicht erfüllt. Grund: Ergebnis-Liste ist None.")
            return []

        print(f"[class_agent_ruting_struktur_balance_agent] Erfolg: _detect_known_bugs erfolgreich beendet. ({len(bugs)} Muster erkannt)")
        return bugs

    def _log_bug_detected(self, bug: Any):
        """Protokolliert einen detektierten Fehler im Audit-Logger."""
        print(f"[class_agent_ruting_struktur_balance_agent] Starte Arbeit: _log_bug_detected wird jetzt ausgeführt. (Parameter: bug_id={bug.bug_id})")
        log_tool = globals().get("class_logger_audit_execution")
        if log_tool and hasattr(log_tool, "write_log"):
            log_tool.write_log(
                phase="REPAIR", event="BUG_DETECTED", module="AgentRouter",
                detail=f"BUG={bug.bug_id}|TYPE={bug.bug_type}|SEVERITY={bug.severity}|{bug.description[:100]}",
                versuch="1"
            )
        print(f"[class_agent_ruting_struktur_balance_agent] Erfolg: _log_bug_detected erfolgreich beendet.")

    def _log_agent_delegation(self, work_item: Any, success: bool):
        """Protokolliert die Delegation an einen spezialisierten Agenten."""
        print(f"[class_agent_ruting_struktur_balance_agent] Starte Arbeit: _log_agent_delegation wird jetzt ausgeführt. (Parameter: agent={work_item.agent_name}, success={success})")
        log_tool = globals().get("class_logger_audit_execution")
        if log_tool and hasattr(log_tool, "write_log"):
            event = "AGENT_DELEGATION_SUCCESS" if success else "AGENT_DELEGATION_FAIL"
            log_tool.write_log(
                phase="AGENT", event=event, module=work_item.agent_name,
                detail=work_item.task_description[:200], versuch="1"
            )
        print(f"[class_agent_ruting_struktur_balance_agent] Erfolg: _log_agent_delegation erfolgreich beendet.")

    def create_work_item(self, bug: Any, file_path: Path, content: str) -> Any:
        """Erzeugt ein spezialisiertes AgentWorkItem für einen BugReport."""
        print(f"[class_agent_ruting_struktur_balance_agent] Starte Arbeit: create_work_item wird jetzt ausgeführt. (Parameter: bug_id={bug.bug_id})")
        AgentWorkItemCls = globals().get("class_agent_work_item")
        agent_map = {
            "SYNTAX": "structure_guard", "LOGIC": "context_analyzer",
            "SHRINKAGE": "refactor", "AST": "structure_guard",
            "STRUCTURE": "structure_guard", "UNKNOWN": "router",
        }
        agent_type = agent_map.get(bug.bug_type, "router")
        priority   = self.agent_priorities.get(agent_type, 99)

        if AgentWorkItemCls:
            result = AgentWorkItemCls(
                agent_type=agent_type,
                agent_name=f"{agent_type.replace('_', '-').title()}-Agent",
                task_description=f"Behebe {bug.bug_type}: {bug.description[:100]}",
                file_path=file_path, code_content=content,
                bug_report=bug, priority=priority
            )
            if result is None:
                print(f"[class_agent_ruting_struktur_balance_agent] FEHLER: create_work_item hat die Aufgabe nicht erfüllt. Grund: AgentWorkItem-Instanz konnte nicht erstellt werden.")
                return None
            print(f"[class_agent_ruting_struktur_balance_agent] Erfolg: create_work_item erfolgreich beendet. (Typ={agent_type})")
            return result

        print(f"[class_agent_ruting_struktur_balance_agent] FEHLER: create_work_item hat die Aufgabe nicht erfüllt. Grund: AgentWorkItem-Klasse nicht im globalen Namensraum.")
        return None

    def execute_agent(self, work_item: Any) -> Dict[str, Any]:
        """Führt den delegierten Agentenaufruf aus und erzeugt Patches."""
        print(f"[class_agent_ruting_struktur_balance_agent] Starte Arbeit: execute_agent wird jetzt ausgeführt. (Parameter: agent={work_item.agent_name})")
        result = {"success": False, "message": "", "patch": None}
        self._log_agent_delegation(work_item, False)

        try:
            strat      = globals().get("class_agent_strategy_balance_agent")
            model_name = strat.get_agent_model(
                agent_type=work_item.agent_type,
                file_path=work_item.file_path,
                content=work_item.code_content
            ) if strat else "codestral"

            mgr = globals().get("class_tool_ollama_service_manager")
            if mgr and hasattr(mgr, "generate"):
                prompt = self._generate_agent_prompt(work_item)
                res    = mgr.generate(prompt=prompt, model=model_name)
                if res and res.get("status") == "SUCCESS" and res.get("content"):
                    result["success"] = True
                    result["patch"]   = res["content"]
                    result["message"] = f"Patch via {model_name} generiert."
                else:
                    result["patch"]   = self._apply_fallback_fix(work_item.code_content, work_item.bug_report)
                    result["success"] = result["patch"] != work_item.code_content
                    result["message"] = "Fallback-Patch angewendet."
            else:
                result["patch"]   = self._apply_fallback_fix(work_item.code_content, work_item.bug_report)
                result["success"] = result["patch"] != work_item.code_content
                result["message"] = "Offline-Fallback aktiv."

            self._log_agent_delegation(work_item, result["success"])

        except Exception as e:
            self.consecutive_failures += 1
            print(f"[class_agent_ruting_struktur_balance_agent] FEHLER: execute_agent hat die Aufgabe nicht erfüllt. Grund: Agent-Ausführung fehlgeschlagen: {e}")
            result["message"] = str(e)

        self.history.append({
            "work_item": work_item,
            "result":    result,
            "timestamp": str(datetime.datetime.now())
        })

        if result is None:
            print("[class_agent_ruting_struktur_balance_agent] FEHLER: execute_agent hat die Aufgabe nicht erfüllt. Grund: Kein Ergebnis-Dictionary.")
            return {"success": False, "message": "Interner Fehler", "patch": None}

        print(f"[class_agent_ruting_struktur_balance_agent] Erfolg: execute_agent erfolgreich beendet. (success={result['success']})")
        return result

    def verify_patch(self, original_content: str, patched_content: str, file_path: Path) -> Tuple[bool, str]:
        """Validiert einen generierten Patch per AST und Zero-Loss-Prüfung."""
        print("[class_agent_ruting_struktur_balance_agent] Starte Arbeit: verify_patch wird jetzt ausgeführt.")
        try:
            ast.parse(patched_content)
        except SyntaxError as e:
            print(f"[class_agent_ruting_struktur_balance_agent] FEHLER: verify_patch hat die Aufgabe nicht erfüllt. Grund: Patch hat SyntaxError: {e}")
            return False, f"Syntaxfehler nach Patch: {e}"

        shrinkage = self._check_shrinkage(patched_content, original_content)
        if shrinkage["detected"]:
            print(f"[class_agent_ruting_struktur_balance_agent] FEHLER: verify_patch hat die Aufgabe nicht erfüllt. Grund: Code-Schwund festgestellt: {shrinkage['ratio']:.1f}%")
            return False, f"Code-Schwund festgestellt: {shrinkage['ratio']:.1f}%"

        print(f"[class_agent_ruting_struktur_balance_agent] Erfolg: verify_patch erfolgreich beendet.")
        return True, "Validierung erfolgreich bestanden"

    def process_file(self, file_path: Path) -> Dict[str, Any]:
        """Führt den vollständigen Routing- und Behebungs-Zyklus für eine Datei aus."""
        print(f"[class_agent_ruting_struktur_balance_agent] Starte Arbeit: process_file wird jetzt ausgeführt. (Parameter: file_path={file_path})")
        self.consecutive_failures = 0
        result = {
            "file": str(file_path), "status": "PROCESSING",
            "bugs_found": 0, "bugs_fixed": 0, "errors": []
        }

        try:
            content = Path(file_path).read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            print(f"[class_agent_ruting_struktur_balance_agent] FEHLER: process_file hat die Aufgabe nicht erfüllt. Grund: Datei nicht lesbar: {e}")
            result["status"] = "ERROR"
            result["errors"].append(str(e))
            return result

        result["lines"] = len(content.splitlines())
        bugs             = self.detect_bugs_in_code(Path(file_path), content)
        result["bugs_found"] = len(bugs)

        if not bugs:
            result["status"] = "CLEAN"
            print(f"[class_agent_ruting_struktur_balance_agent] Erfolg: process_file erfolgreich beendet. (Status=CLEAN)")
            return result

        for bug in bugs:
            if self.consecutive_failures >= self.MAX_SEQUENTIAL_FAILURES:
                result["status"] = "DELEGATION_LIMIT_REACHED"
                break
            work_item = self.create_work_item(bug, Path(file_path), content)
            if not work_item:
                continue
            res = self.execute_agent(work_item)
            if res.get("success") and res.get("patch"):
                result["bugs_fixed"] += 1
                content = res["patch"]
            else:
                result["errors"].append(res.get("message", "Unbekannter Fehler"))

        valid, msg       = self.verify_patch(content, content, Path(file_path))
        result["status"] = "VERIFIED" if valid else "VERIFICATION_FAILED"
        if not valid:
            result["errors"].append(msg)

        if result is None:
            print("[class_agent_ruting_struktur_balance_agent] FEHLER: process_file hat die Aufgabe nicht erfüllt. Grund: Kein Ergebnis-Dictionary.")
            return {"file": str(file_path), "status": "ERROR", "errors": ["Interner Fehler"]}

        print(f"[class_agent_ruting_struktur_balance_agent] Erfolg: process_file erfolgreich beendet. (Status={result['status']}, Fixes={result['bugs_fixed']})")
        return result

    def _generate_agent_prompt(self, work_item: Any) -> str:
        """Erzeugt einen optimierten LLM-Prompt für den Zielagenten."""
        print(f"[class_agent_ruting_struktur_balance_agent] Starte Arbeit: _generate_agent_prompt wird jetzt ausgeführt. (Parameter: agent_type={work_item.agent_type})")
        prompt = (
            f"You are a specialized code repair agent ({work_item.agent_name}).\n"
            f"Fix the following issue without deleting unrelated logic:\n"
            f"Task: {work_item.task_description}\n\n"
            f"Code:\n```python\n{work_item.code_content[:3000]}\n```\n\n"
            f"Return ONLY the complete repaired Python code in a ```python markdown block."
        )

        if not prompt:
            print("[class_agent_ruting_struktur_balance_agent] FEHLER: _generate_agent_prompt hat die Aufgabe nicht erfüllt. Grund: Leerer Prompt erzeugt.")
            return ""

        print(f"[class_agent_ruting_struktur_balance_agent] Erfolg: _generate_agent_prompt erfolgreich beendet.")
        return prompt

    def _apply_fallback_fix(self, content: str, bug_report: Any) -> str:
        """Wendet eine deterministische Korrektur an, wenn kein LLM erreichbar ist."""
        print("[class_agent_ruting_struktur_balance_agent] Starte Arbeit: _apply_fallback_fix wird jetzt ausgeführt.")
        if not bug_report:
            print("[class_agent_ruting_struktur_balance_agent] Erfolg: _apply_fallback_fix erfolgreich beendet. (Kein BugReport, unveränderter Content)")
            return content
        if "PROJECT_POINT" in bug_report.description:
            pat  = r"(class class_tool_core_infrastructure[^\n]*:\n)"
            repl = r'\1    PROJECT_POINT: str = "src"\n'
            result = re.sub(pat, repl, content)
            print(f"[class_agent_ruting_struktur_balance_agent] Erfolg: _apply_fallback_fix erfolgreich beendet. (PROJECT_POINT-Fix angewendet)")
            return result
        if "get_file_skeleton" in bug_report.description:
            result = content.replace(
                "    def get_file_skeleton(file_path",
                "    @staticmethod\n    def get_file_skeleton(file_path"
            )
            print(f"[class_agent_ruting_struktur_balance_agent] Erfolg: _apply_fallback_fix erfolgreich beendet. (staticmethod-Fix angewendet)")
            return result

        print(f"[class_agent_ruting_struktur_balance_agent] Erfolg: _apply_fallback_fix erfolgreich beendet. (Kein passender Fix, unveränderter Content)")
        return content

    # =========================================================================
    # EBENE 5: ZENTRALE AUSFÜHRUNGSFUNKTION
    # =========================================================================

    @classmethod
    def run_routing_agent(cls, file_path: Path) -> dict:
        """
        Zentrale Ausführungsfunktion des Routing-Agenten.
        Steuert den gesamten Ablauf von der Fehlererkennung
        bis zur finalen Patch-Validierung für die übergebene Datei.
        """
        print(f"[class_agent_ruting_struktur_balance_agent] Starte Arbeit: run_routing_agent wird jetzt ausgeführt. (Parameter: file_path={file_path})")
        try:
            router = cls()
            result = router.process_file(file_path)

            if result is None:
                print("[class_agent_ruting_struktur_balance_agent] FEHLER: run_routing_agent hat die Aufgabe nicht erfüllt. Grund: process_file lieferte None.")
                return {"status": "ERROR", "error": "Kein Ergebnis von process_file"}

            print(f"[class_agent_ruting_struktur_balance_agent] Erfolg: run_routing_agent erfolgreich beendet. (Status={result.get('status')})")
            return result
        except Exception as e:
            print(f"[class_agent_ruting_struktur_balance_agent] FEHLER: run_routing_agent hat die Aufgabe nicht erfüllt. Grund: {e}")
            return {"status": "ERROR", "error": str(e)}
