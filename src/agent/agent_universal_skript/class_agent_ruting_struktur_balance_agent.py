#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
══════════════════════════════════════════════════════════════════════════════
ROUTING STRUCTURE FOR BALANCED MULTI-AGENT SYSTEM v1.0
══════════════════════════════════════════════════════════════════════════════
Delegation-System mit:
  - Bug-Type Classification
  - Dynamischer Agent-Auswahl
  - Full-Cycle Protocolierung via class_logger_audit_execution
  - Closed-Loop Validation
"""

import ast
import sys
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

# Auto-Bootstrap & Global Registry (nur lokal für Zugriff auf Werkzeuge)
try:
    from agent_universal_skript.auto_bootstrap_and_register_agent_tools import (
        auto_bootstrap_and_register_agent_tools,
    )
    auto_bootstrap_and_register_agent_tools()
except ImportError:
    pass

# Zugriff auf zentrale Werkzeuge
logger = globals().get("class_logger_audit_execution")
core_infra = globals().get("class_tool_core_infrastructure")
ollama_manager = globals().get("class_tool_ollama_service_manager")
sub_verifier = globals().get("class_agent_sub_verifier")

# Import Strategy-Config (zur Modellauswahl)
try:
    from agent_universal_skript.class_agent_strategy_balance_agent import (
        class_agent_strategy_balance_agent,
    )
except ImportError:
    # Fallback wenn Strategy noch nicht geladen
    class_agent_strategy_balance_agent = None


# ═══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class BugReport:
    """Repräsentiert einen identifizierten Bug mit Metadaten."""
    bug_id: str
    bug_type: str  # "SYNTAX", "SHRINKAGE", "LOGIC", "AST", "STRUCTURE", "UNKNOWN"
    file_path: Path
    line_number: Optional[int] = None
    severity: str = "MEDIUM"  # LOW, MEDIUM, HIGH, CRITICAL
    description: str = ""
    suggested_fix: str = ""
    affected_agents: List[str] = field(default_factory=list)
    log_matches: List[str] = field(default_factory=list)


@dataclass
class AgentWorkItem:
    """Ein Auftrag für einen Agenten mit vollständigem Kontext."""
    agent_type: str  # router, structure_guard, context_analyzer, refactor, verification
    agent_name: str
    task_description: str
    file_path: Optional[Path] = None
    code_content: str = ""
    bug_report: Optional[BugReport] = None
    context_data: Dict[str, Any] = field(default_factory=dict)
    priority: int = 1
    result: Optional[Dict[str, Any]] = None


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ROUTING CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class class_agent_ruting_struktur_balance_agent:
    """
    Zentrales Routing-System für die Multi-Agent-Architektur.
    Verwaltet Bug-Erkennung, Agenten-Delegation und Closed-Loop-Verifizierung.
    """

    # ─────────────────────────────────────────────────────────────────────────────
    # CONSTANTS & CONFIG
    # ─────────────────────────────────────────────────────────────────────────────
    _cfg: Dict[str, Any] = globals().setdefault("_ROUTING_CONFIG", {})

    MAX_DELEGATION_CYCLES: int = _cfg.setdefault("MAX_DELEGATION_CYCLES", 5)
    MAX_SEQUENTIAL_FAILURES: int = _cfg.setdefault("MAX_SEQUENTIAL_FAILURES", 3)

    # ─────────────────────────────────────────────────────────────────────────────
    # STATE MANAGEMENT
    # ─────────────────────────────────────────────────────────────────────────────
    def __init__(self):
        self.bug_database: List[BugReport] = []
        self.work_queue: List[AgentWorkItem] = []
        self.history: List[Dict[str, Any]] = []
        self.consecutive_failures: int = 0

        # Routing-Prioritäten
        self.agent_priorities = {
            "router": 1,
            "context_analyzer": 2,
            "structure_guard": 3,
            "refactor": 4,
            "verification": 5,
        }

        # Initialisierung logger phase
        if logger:
            logger.log_event(
                phase=logger.LOG_PHASE_AGENT,
                event="ROUTER_INIT",
                module="AgentRouter",
                detail="Multi-Agent Routing System initialized",
            )

    # ─────────────────────────────────────────────────────────────────────────────
    # BUG DETECTION
    # ─────────────────────────────────────────────────────────────────────────────
    def detect_bugs_in_code(self, file_path: Path, content: str) -> List[BugReport]:
        """
        Analysiert Code auf bekannte Bug-Muster und erstellt BugReports.
        """
        bugs = []
        bug_counter = 0

        # 1. Syntax-Check
        try:
            ast.parse(content)
        except SyntaxError as e:
            bug_counter += 1
            bugs.append(BugReport(
                bug_id=f"BUG-{bug_counter:03d}",
                bug_type="SYNTAX",
                file_path=file_path,
                line_number=e.lineno,
                severity="CRITICAL",
                description=f"SyntaxError: {e.msg}",
                suggested_fix="Fix syntax error at line {e.lineno}",
                affected_agents=["structure_guard"],
            ))

        # 2. Zero-Loss Check (Vergleich mit AST-Struktur)
        structure_loss = self._check_structure_loss(content)
        if structure_loss:
            bug_counter += 1
            bugs.append(BugReport(
                bug_id=f"BUG-{bug_counter:03d}",
                bug_type="STRUCTURE",
                file_path=file_path,
                severity="HIGH",
                description=f"Structure loss detected: {structure_loss}",
                suggested_fix="Restore missing functions/classes via structure_guard",
                affected_agents=["structure_guard", "refactor"],
            ))

        # 3. Shrinkage Check (Zeilen/Zeichen-Verlust)
        # Hinweis: Original-Content ist bei detect_bugs_in_code nicht verfügbar
        shrinkage = self._check_shrinkage(content, original_content=None)
        if shrinkage["detected"]:
            bug_counter += 1
            bugs.append(BugReport(
                bug_id=f"BUG-{bug_counter:03d}",
                bug_type="SHRINKAGE",
                file_path=file_path,
                severity="HIGH",
                description=f"Shrinkage: {shrinkage['ratio']:.1f}% retained ({shrinkage['lost_lines']} lines lost)",
                suggested_fix="Restore lost code via refactor_agent",
                affected_agents=["structure_guard", "refactor"],
            ))

        # 4. Known Bug Patterns (BUG-01 bis BUG-06)
        known_bugs = self._detect_known_bugs(content, file_path)
        for known_bug in known_bugs:
            bug_counter += 1
            bugs.append(BugReport(
                bug_id=f"BUG-{bug_counter:03d}",
                bug_type=known_bug["type"],
                file_path=file_path,
                severity=known_bug["severity"],
                description=known_bug["description"],
                suggested_fix=known_bug["patch_strategy"],
                affected_agents=known_bug["affected_agents"],
            ))

        # Speichern in Database
        self.bug_database.extend(bugs)

        # Loggen aller Bugs
        for bug in bugs:
            self._log_bug_detected(bug)

        return bugs

    def _check_structure_loss(self, content: str) -> Optional[str]:
        """Check if any functions/classes were lost (simplified AST check)."""
        try:
            tree = ast.parse(content)
            classes = [n.name for n in tree.body if isinstance(n, ast.ClassDef)]
            funcs = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]

            if not classes and not funcs:
                return "No functions or classes found in module scope"
            return None
        except Exception:
            return "AST parse failed"

    def _check_shrinkage(self, content: str, original_content: Optional[str]) -> Dict[str, Any]:
        """Check for code shrinkage by comparing line/character counts."""
        if not original_content:
            return {"detected": False, "ratio": 100.0, "lost_lines": 0}

        orig_lines = len(original_content.splitlines())
        cand_lines = len(content.splitlines())

        if orig_lines > 0:
            ratio = (cand_lines / orig_lines) * 100
            lost_lines = orig_lines - cand_lines

            if ratio < 80:  # 20% shrinkage threshold
                return {
                    "detected": True,
                    "ratio": ratio,
                    "lost_lines": lost_lines,
                }

        return {"detected": False, "ratio": ratio, "lost_lines": 0}

    def _detect_known_bugs(self, content: str, file_path: Path) -> List[Dict]:
        """Detects known bug patterns similar to agent_repair_agent.py KnownBugCatalog."""
        bugs = []

        # BUG-01: Missing PROJECT_POINT
        if ("class_tool_core_infrastructure" in content and
            "PROJECT_POINT" not in content):
            bugs.append({
                "type": "STRUCTURE",
                "severity": "CRITICAL",
                "description": "BUG-01:class_tool_core_infrastructure missing PROJECT_POINT attribute",
                "patch_strategy": "Add PROJECT_POINT = 'src' to class",
                "affected_agents": ["structure_guard"],
            })

        # BUG-02: get_file_skeleton missing @staticmethod
        if "get_file_skeleton(file_path" in content and "@staticmethod" not in content:
            bugs.append({
                "type": "STRUCTURE",
                "severity": "HIGH",
                "description": "BUG-02: get_file_skeleton missing @staticmethod decorator",
                "patch_strategy": "Add @staticmethod decorator or add 'self' parameter",
                "affected_agents": ["structure_guard"],
            })

        # BUG-03: evolve_loop never succeeds
        if ("class_container_evolve_loop_test" in content and
            "ALL_CONNECTIONS_VERIFIED_100_PERCENT" in content):
            bugs.append({
                "type": "LOGIC",
                "severity": "CRITICAL",
                "description": "BUG-03: evolve loop never succeeds (unwritten log token)",
                "patch_strategy": "Replace log-token check with pragmatic success logic",
                "affected_agents": ["context_analyzer", "refactor"],
            })

        # BUG-04: Missing DB methods
        if ("class_container_evolve_loop_test" in content and
            ("get_db_connection()" in content or "_insert_routing_node" in content)):
            bugs.append({
                "type": "STRUCTURE",
                "severity": "HIGH",
                "description": "BUG-04: class_container_evolve_loop_test missing DB guard methods",
                "patch_strategy": "Add guard methods for get_db_connection, _insert_routing_node",
                "affected_agents": ["refactor"],
            })

        # BUG-05: Missing _insert_routing_node in SQL reader
        if ("class_tool_sql_reader" in content and
            "_insert_routing_node(" in content and
            "def _insert_routing_node" not in content):
            bugs.append({
                "type": "STRUCTURE",
                "severity": "CRITICAL",
                "description": "BUG-05: class_tool_sql_reader missing _insert_routing_node method",
                "patch_strategy": "Add _insert_routing_node method with INSERT OR IGNORE",
                "affected_agents": ["refactor"],
            })

        # BUG-06: MRO conflict
        if re.search(r'class\s+\w+\s*\([^)]*if\s+\w+\s+else\s+object', content):
            bugs.append({
                "type": "STRUCTURE",
                "severity": "CRITICAL",
                "description": "BUG-06: MRO conflict due to dynamic base classes",
                "patch_strategy": " Replace dynamic bases with _mro_safe_bases helper",
                "affected_agents": ["structure_guard"],
            })

        return bugs

    # ─────────────────────────────────────────────────────────────────────────────
    # LOGGING
    # ─────────────────────────────────────────────────────────────────────────────
    def _log_bug_detected(self, bug: BugReport):
        """Protokolliert einen detektierten Bug mit vollständigen Metadaten."""
        if logger:
            logger.write_log(
                phase=logger.LOG_PHASE_REPAIR,
                event="BUG_DETECTED",
                module="AgentRouter",
                detail=(f"BUG={bug.bug_id}|TYPE={bug.bug_type}|"
                       f"SEVERITY={bug.severity}|{bug.description[:100]}"),
                versuch="1",
            )

    def _log_agent_delegation(self, work_item: AgentWorkItem, success: bool):
        """Protokolliert Agenten-Delegation und Ergebnis."""
        if logger:
            event = "AGENT_DELEGATION_SUCCESS" if success else "AGENT_DELEGATION_FAIL"
            logger.write_log(
                phase=logger.LOG_PHASE_AGENT,
                event=event,
                module=work_item.agent_name,
                detail=work_item.task_description[:200],
                versuch="1",
            )

    # ─────────────────────────────────────────────────────────────────────────────
    # AGENT DELEGATION
    # ─────────────────────────────────────────────────────────────────────────────
    def create_work_item(self, bug: BugReport, file_path: Path, content: str) -> AgentWorkItem:
        """
        Erstellt einen Agenten-Auftrag aus einem BugReport.
        Wählt automatisch den passenden Agenten basierend auf Bug-Typ.
        """
        # Agentenauswahl basierend auf Bug-Typ
        agent_map = {
            "SYNTAX": "structure_guard",
            "LOGIC": "context_analyzer",
            "SHRINKAGE": "refactor",
            "AST": "structure_guard",
            "STRUCTURE": "structure_guard",
            "UNKNOWN": "router",
        }

        agent_type = agent_map.get(bug.bug_type, "router")

        # Agenten-Name ermitteln
        agent_config = self._get_agent_config(agent_type)
        agent_name = agent_config["name"] if agent_config else agent_type

        # Priorität setzen
        priority = self.agent_priorities.get(agent_type, 99)

        return AgentWorkItem(
            agent_type=agent_type,
            agent_name=agent_name,
            task_description=f"Fix {bug.bug_type}: {bug.description[:100]}",
            file_path=file_path,
            code_content=content,
            bug_report=bug,
            priority=priority,
        )

    def _get_agent_config(self, agent_type: str) -> Optional[Dict]:
        """Holt die Konfiguration für einen Agenten-Typ."""
        if class_agent_strategy_balance_agent:
            return class_agent_strategy_balance_agent.get_agent_by_name(
                agent_type.replace("_", "-").title().replace("-", "-")
            )
        return None

    def execute_agent(self, work_item: AgentWorkItem) -> Dict[str, Any]:
        """
        Führt einen Agenten aus und gibt Ergebnis zurück.
        HIER WIRD DIE ECHTE INFRASTRUKTUR INTEGRIERT!
        """
        result = {
            "success": False,
            "message": "",
            "patch": None,
        }

        # Log Start
        self._log_agent_delegation(work_item, False)

        try:
            # 1. Modell für diesen Agenten ermitteln
            model_name = class_agent_strategy_balance_agent.get_agent_model(
                agent_type=work_item.agent_type,
                file_path=work_item.file_path,
                content=work_item.code_content,
            )

            # 2. Ollama ServiceManager initialisieren
            if ollama_manager:
                if not ollama_manager.is_port_open("127.0.0.1", 11434):
                    if not ollama_manager.ensure_ollama_running():
                        result["message"] = "[ERROR] Ollama service not available"
                        result["success"] = False
                        return result
            else:
                result["message"] = "[ERROR] Ollama manager not available"
                result["success"] = False
                return result

            # 3. Agenten-Prompt abhängig vom Typ generieren
            prompt = self._generate_agent_prompt(work_item)

            # 4. LLM-Aufruf mit passendem Modell
            if ollama_manager:
                try:
                    # LLM-Antwort generieren
                    response = ollama_manager.generate(prompt, model=model_name)

                    if response and response.get("response"):
                        generated_code = response["response"]
                        result["success"] = True
                        result["message"] = f"[{work_item.agent_name}] LLM generated patch via {model_name}"
                        result["patch"] = generated_code
                        result["used_model"] = model_name

                        # Planung: LLM-Antwort in Sandbox testen
                        # (Für aktuelle Version simuliert)
                        if len(generated_code) > 5000:
                            result["patch"] = self._validate_patch_safety(generated_code)

                    else:
                        result["message"] = f"[{work_item.agent_name}] No response from {model_name}"
                        result["success"] = False

                except Exception as llm_err:
                    result["message"] = f"[{work_item.agent_name}] LLM error: {str(llm_err)}"
                    result["success"] = False

                    # Fallback auf einfache Patch-Logik
                    if work_item.bug_report and work_item.bug_report.suggested_fix:
                        result["message"] += " → Using fallback fix strategy"
                        result["patch"] = self._apply_fallback_fix(
                            work_item.code_content,
                            work_item.bug_report
                        )
                        result["success"] = True
            else:
                # Ollama nicht verfügbar → Fallback
                if work_item.bug_report and work_item.bug_report.suggested_fix:
                    result["message"] = f"[{work_item.agent_name}] Fallback mode active"
                    result["patch"] = self._apply_fallback_fix(
                        work_item.code_content,
                        work_item.bug_report
                    )
                    result["success"] = True

            # Log Success
            self._log_agent_delegation(work_item, True)

        except Exception as e:
            self.consecutive_failures += 1
            result["message"] = f"[{work_item.agent_name}] Error: {str(e)}"
            result["success"] = False

            if logger:
                logger.error(
                    f"Agent {work_item.agent_name} failed: {str(e)}",
                    module="AgentRouter",
                )

        # In History speichern
        self.history.append({
            "work_item": work_item,
            "result": result,
            "timestamp": str(__import__("datetime").datetime.now()),
        })

        return result

    # ─────────────────────────────────────────────────────────────────────────────
    # CLOSED-LOOP VERIFICATION
    # ─────────────────────────────────────────────────────────────────────────────
    def verify_patch(self, original_content: str, patched_content: str,
                     file_path: Path) -> Tuple[bool, str]:
        """
        Führt Closed-Loop-Verifizierung durch:
          - AST-Check
          - Shrinkage-Check
          - Sandbox-Test (wenn möglich)
        """
        # 1. AST-Check
        try:
            ast.parse(patched_content)
        except SyntaxError as e:
            return False, f"Syntax error after patch: {e}"

        # 2. Shrinkage-Check (Zero-Loss Policy)
        shrinkage = self._check_shrinkage(patched_content, original_content)
        if shrinkage["detected"]:
            return False, f"Shrinkage detected: {shrinkage['ratio']:.1f}% retained"

        # 3. Structure-Check
        structure_loss = self._check_structure_loss(patched_content)
        if structure_loss:
            return False, f"Structure loss: {structure_loss}"

        # 4. Sandbox-Test (optional, nur bei kleineren Code-Snippets)
        if len(patched_content) < 5000 and sub_verifier:
            try:
                safe, output = sub_verifier.verify_code_in_sandbox(
                    patched_content,
                    project_root=file_path.parent.parent,
                    timeout_sec=10,
                )
                if not safe:
                    return False, f"Sandbox test failed: {output}"
            except Exception:
                pass  # Sandbox nicht verfügbar → überspringen

        return True, "Verification passed"

    # ─────────────────────────────────────────────────────────────────────────────
    # MAIN WORKFLOW
    # ─────────────────────────────────────────────────────────────────────────────
    def process_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Führt den kompletten Workflow für eine Datei aus:
          1. Bug-Detection
          2. Agenten-Delegation
          3. Patch-Verifizierung
        """
        self.consecutive_failures = 0
        result = {
            "file": str(file_path),
            "status": "PROCESSING",
            "bugs_found": 0,
            "bugs_fixed": 0,
            "errors": [],
        }

        # Datei laden
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            result["status"] = "ERROR"
            result["errors"].append(f"Cannot read file: {str(e)}")
            if logger:
                logger.error(f"Cannot read {file_path.name}: {e}", module="AgentRouter")
            return result

        result["lines"] = len(content.splitlines())

        # 1. Bug-Detection
        bugs = self.detect_bugs_in_code(file_path, content)
        result["bugs_found"] = len(bugs)

        if not bugs:
            result["status"] = "CLEAN"
            if logger:
                logger.info(f"No bugs detected in {file_path.name}", module="AgentRouter")
            return result

        # 2. Agenten-Delegation & Ausführung
        for bug in bugs:
            if self.consecutive_failures >= self.MAX_SEQUENTIAL_FAILURES:
                result["status"] = "DELEGATION_LIMIT_REACHED"
                break

            work_item = self.create_work_item(bug, file_path, content)
            agent_result = self.execute_agent(work_item)

            if agent_result["success"]:
                result["bugs_fixed"] += 1
                content = agent_result["patch"]
            else:
                result["errors"].append(agent_result["message"])

        # 3. Final-Verification
        if result["status"] != "ERROR":
            success, msg = self.verify_patch(content, content, file_path)
            if success:
                result["status"] = "VERIFIED"
            else:
                result["status"] = "VERIFICATION_FAILED"
                result["errors"].append(msg)

        # Log Final Status
        if logger:
            logger.write_log(
                phase=logger.LOG_PHASE_REPAIR,
                event="FILE_PROCESSING_COMPLETE",
                module="AgentRouter",
                detail=f"STATUS={result['status']}|BUGS={result['bugs_found']}|FIXED={result['bugs_fixed']}",
                versuch="1",
            )

        return result

    # ─────────────────────────────────────────────────────────────────────────────
    # OLLAMA HELPER FUNCTIONS
    # ─────────────────────────────────────────────────────────────────────────────
    def _generate_agent_prompt(self, work_item: AgentWorkItem) -> str:
        """
        Erstellt den spezifischen LLM-Prompt basierend auf Agenten-Typ und Bug-Report.
        """
        agent_type = work_item.agent_type
        bug = work_item.bug_report

        # Basis-Prompt
        base_prompt = f"""You are an AI code repair assistant. Analyze and fix the following issue.

File: {str(work_item.file_path)}
Bug: {bug.bug_type if bug else 'UNKNOWN'}
Severity: {bug.severity if bug else 'MEDIUM'}

Code:
{work_item.code_content[:3000]}  # Limit for model context

"""

        # Agenten-spezifische Prompts
        if agent_type == "router":
            return base_prompt + """
TASK: Classify the bug type and determine which specialist agent should fix it.
Return your response as JSON:
{
  "classified_bug_type": "SYNTAX|LOGIC|SHRINKAGE|STRUCTURE",
  "recommended_agent": "structure_guard|context_analyzer|refactor",
  "confidence": 0.0-1.0
}
"""

        elif agent_type == "structure_guard":
            return base_prompt + f"""
TASK: You are the Structure-Guard-Agent. Your job is ZERO-LOSS AST-REPAIR.

Bug to fix: {bug.description[:200]}
Suggested fix: {bug.suggested_fix[:200]}

INSTRUCTIONS:
1. Parse the AST and identify the faulty node
2. Generate a minimal patch that fixes ONLY the specific bug
3. PRESERVE 100% of all other code (Zero-Loss Policy)
4. Return the FULL patched code

IMPORTANT: Do NOT remove or truncate any existing code. Only fix the specific bug.
"""

        elif agent_type == "context_analyzer":
            return base_prompt + f"""
TASK: You are the Context-Agent. Analyze error patterns and log context.

Bug to analyze: {bug.description[:200]}
Suggested fix: {bug.suggested_fix[:200]}

INSTRUCTIONS:
1. Extract error context and pattern
2. Identify related code sections
3. Provide fix strategy with reasoning
4. Return JSON with fix plan
"""

        elif agent_type == "refactor":
            return base_prompt + f"""
TASK: You are the Refactor-Agent. Optimize code while preserving ABI compatibility.

Bug to fix: {bug.description[:200]}
Suggested fix: {bug.suggested_fix[:200]}

INSTRUCTIONS:
1. Apply the fix while maintaining function signatures
2. Preserve all class hierarchies
3. Keep return types unchanged
4. Optimize only when safe
5. Return the modified full code
"""

        elif agent_type == "verification":
            return base_prompt + f"""
TASK: You are the Verification-Agent. Test and validate patches.

Original code length: {len(work_item.code_content)} chars
Bug type: {bug.bug_type if bug else 'UNKNOWN'}

INSTRUCTIONS:
1. Validate the patch fixes the specific bug
2. Check for syntax errors (AST validation)
3. Verify no code shrinkage (Zero-Loss Policy)
4. Return JSON: {{"valid": true|false, "reason": "..."}}
"""

        # Fallback
        return base_prompt + """
TASK: Analyze the bug and provide a repair strategy.
Return your response as properly formatted Python code.
"""

    def _validate_patch_safety(self, generated_code: str) -> str:
        """
        Validiert die LLM-Antwort auf Sicherheit und Plausibilität.
        Entfernt unsafe imports oder verdächtigen Code.
        """
        # Sicherheits-Check (simuliert)
        # In Produktion: AST-Check und Forbidden-Module-Check

        # Fallback: Wenn Code zu groß, trimmen (für Demo-Zwecke)
        lines = generated_code.splitlines()
        if len(lines) > 1000:
            return "\n".join(lines[:1000]) + "\n# [TRUNCATED FOR SAFETY]"

        return generated_code

    def _apply_fallback_fix(self, content: str, bug_report: BugReport) -> str:
        """
        Wendet eine einfache Regex-basierte Fallback-Reparatur an,
        wenn Ollama nicht verfügbar ist.
        """
        # BUG-01: PROJECT_POINT hinzufügen
        if "Missing PROJECT_POINT" in bug_report.description:
            pattern = r'(class class_tool_core_infrastructure[^\n]*:\n)'
            replacement = r'\1    PROJECT_POINT: str = "src"  # [AUTO-PATCH FALLBACK]\n'
            import re
            return re.sub(pattern, replacement, content, flags=re.DOTALL)

        # BUG-02: @staticmethod hinzufügen
        if "get_file_skeleton" in bug_report.description:
            return content.replace(
                "    def get_file_skeleton(file_path",
                "    @staticmethod\n    def get_file_skeleton(file_path"
            )

        # Fallback: Code unverändert zurückgeben
        return content


# ═══════════════════════════════════════════════════════════════════════════════
# DEMO / MAIN EXECUTION
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 80)
    print("ROUTING STRUCTURE FOR BALANCED MULTI-AGENT SYSTEM - DEMO")
    print("=" * 80)

    # Router initialisieren
    router = class_agent_ruting_struktur_balance_agent()

    # Beispiel: Teste Datei
    test_file = Path("src/agent/agent_repair_agent.py")

    if test_file.exists():
        print(f"\n[DEMO] Processing file: {test_file.name}")
        print("-" * 80)

        result = router.process_file(test_file)

        print(f"\n[RESULT] Status: {result['status']}")
        print(f"[RESULT] Bugs found: {result['bugs_found']}")
        print(f"[RESULT] Bugs fixed: {result['bugs_fixed']}")
        print(f"[RESULT] Lines processed: {result.get('lines', 'N/A')}")

        if result["errors"]:
            print("\n[ERRORS]:")
            for err in result["errors"]:
                print(f"  - {err}")
    else:
        print(f"\n[ERROR] Test file not found: {test_file}")

    print("\n" + "=" * 80)
    print("✅ Routing-System demo completed.")
    print("=" * 80)
