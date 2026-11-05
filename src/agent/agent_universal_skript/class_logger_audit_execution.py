"""
Modul: class_logger_audit_execution
Bezeichnung: Zentraler Audit- und Ausführungs-Logger
Inhaltlicher Schwerpunkt:
    Vollständige Protokollierung von Mikroschritten, Hardware-Audits,
    Terminal-Spiegelung, Fehler-Tracking sowie AST-basierter
    Flugschreiber-Instrumentierung. Die Terminal-Umleitung (stdout)
    wird über class_stdout_redirector realisiert, das als eigenständige
    Klasse in class_stdout_redirector.py definiert ist.
"""

from __future__ import annotations
import ast
import datetime as _dt
import logging
import os
import platform
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

# Globale Bindings
core_infra = globals().get("class_tool_core_infrastructure")
stdout_redirector_cls = globals().get("class_stdout_redirector")


class class_logger_audit_execution:
    """
    Zentraler Logger für das Agenten- und Reparatur-System.
    Garantiert deterministische Logzeilen und dynamische Kontext-Erkennung.
    """

    _cfg: Dict[str, Any] = globals().setdefault("_AGENT_CONFIG", {})
    MAX_ROOT_SEARCH_DEPTH: int = _cfg.setdefault("MAX_ROOT_SEARCH_DEPTH", 5)
    DIR_SRC: str               = _cfg.setdefault("DIR_SRC",               "src")
    DIR_LOGS: str              = _cfg.setdefault("DIR_LOGS",              "logs")

    # Protokoll-Phasen
    LOG_PHASE_SESSION: str  = "SESSION"
    LOG_PHASE_HARDWARE: str = "HARDWARE"
    LOG_PHASE_INSTALL: str  = "INSTALL"
    LOG_PHASE_IMPORT: str   = "IMPORT"
    LOG_PHASE_REPAIR: str   = "REPAIR"
    LOG_PHASE_FILTER: str   = "FILTER"
    LOG_PHASE_AGENT: str    = "AGENT"
    LOG_PHASE_TERMINAL: str = "TERMINAL"
    LOG_PHASE_FLIGHT: str   = "FLIGHT_RECORDER"

    # Protokoll-Ereignisse
    LOG_EVENT_SESSION_START: str       = "SESSION_START"
    LOG_EVENT_STEP_ACTION: str         = "STEP_ACTION"
    LOG_EVENT_BANNED: str              = "BANNED"
    LOG_EVENT_INSTALL_FAIL: str        = "INSTALL_FAIL"
    LOG_EVENT_INLINE_REPAIR_FAIL: str  = "INLINE_REPAIR_FAIL"
    LOG_EVENT_STDOUT: str              = "STDOUT"
    LOG_EVENT_FLIGHT_STEP: str         = "FLIGHT_STEP"

    LOG_LINE_PATTERN_STR: str = (
        r"^\[(?P<pc_id>[^\]]+)\]\|\[(?P<ts>[^\]]+)\]\|\[(?P<phase>[^\]]+)\]\|"
        r"EVENT=(?P<event>[^|]*)\|MODULE=(?P<module>[^|]*)\|"
        r"DETAIL=(?P<detail>.*)\|VERSUCH=(?P<versuch>[^|]*)$"
    )
    _LOG_LINE_RE = re.compile(LOG_LINE_PATTERN_STR)

    # =========================================================================
    # EBENE 4: METHODEN
    # =========================================================================

    @classmethod
    def _detect_project_root(cls) -> Path:
        """Ermittelt den Projekt-Root ausgehend vom Arbeitsverzeichnis oder __file__."""
        print("[class_logger_audit_execution] Starte Arbeit: _detect_project_root wird jetzt ausgeführt.")
        infra = globals().get("class_tool_core_infrastructure")
        if infra and hasattr(infra, "get_project_root"):
            result = infra.get_project_root()
            print("[class_logger_audit_execution] Erfolg: _detect_project_root erfolgreich beendet.")
            return result
        current = Path.cwd()
        for parent in [current] + list(current.parents):
            if (parent / cls.DIR_SRC).is_dir():
                result = parent
                print("[class_logger_audit_execution] Erfolg: _detect_project_root erfolgreich beendet.")
                return result
        result = current
        print("[class_logger_audit_execution] Erfolg: _detect_project_root erfolgreich beendet.")
        return result

    @classmethod
    def _detect_execution_context(cls) -> Tuple[str, str]:
        """Ermittelt, ob die Ausführung im Jupyter-Notebook oder im Terminal stattfindet."""
        print("[class_logger_audit_execution] Starte Arbeit: _detect_execution_context wird jetzt ausgeführt.")
        try:
            ip = get_ipython()
            if ip is not None and "Shell" in ip.__class__.__name__:
                result = ("LOG_jupyter_session.log", "jupyter_session")
                print("[class_logger_audit_execution] Erfolg: _detect_execution_context erfolgreich beendet.")
                return result
        except NameError:
            pass
        result = ("LOG_agent_execution.log", "agent_terminal")
        print("[class_logger_audit_execution] Erfolg: _detect_execution_context erfolgreich beendet.")
        return result

    @classmethod
    def get_target_log_path(cls) -> Path:
        """Gibt den vollständigen Pfad zur aktuellen Logdatei zurück."""
        print("[class_logger_audit_execution] Starte Arbeit: get_target_log_path wird jetzt ausgeführt.")
        root     = cls._detect_project_root()
        logs_dir = root / cls.DIR_LOGS
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_name, _ = cls._detect_execution_context()
        result = logs_dir / log_name
        if result is None:
            print("[class_logger_audit_execution] FEHLER: get_target_log_path hat die Aufgabe nicht erfüllt. Grund: Kein Log-Pfad ermittelt.")
            return None
        print("[class_logger_audit_execution] Erfolg: get_target_log_path erfolgreich beendet.")
        return result

    @classmethod
    def get_dir(cls, dirname: str, ensure: bool = False) -> Path:
        """Ermittelt und erstellt (optional) Verzeichnisse im Projektkontext."""
        print(f"[class_logger_audit_execution] Starte Arbeit: get_dir wird jetzt ausgeführt. (Parameter: dirname={dirname})")
        root = cls._detect_project_root()
        target = root / dirname
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        print(f"[class_logger_audit_execution] Erfolg: get_dir erfolgreich beendet. (Pfad={target})")
        return target

    @classmethod
    def resolve_log_file_name(cls) -> str:
        """Gibt stets den aktuell ermittelten Log-Dateinamen zurück."""
        print("[class_logger_audit_execution] Starte Arbeit: resolve_log_file_name wird jetzt ausgeführt.")
        log_file, _ = cls._detect_execution_context()
        if not log_file:
            print("[class_logger_audit_execution] FEHLER: resolve_log_file_name hat die Aufgabe nicht erfüllt. Grund: Kein Log-Dateiname ermittelt.")
            return "LOG_agent_execution.log"
        print(f"[class_logger_audit_execution] Erfolg: resolve_log_file_name erfolgreich beendet. (Logfile={log_file})")
        return log_file

    @classmethod
    def initialize_logger(cls) -> logging.Logger:
        """Initialisiert das zentrale Logging-System und aktiviert die stdout-Umleitung."""
        print("[class_logger_audit_execution] Starte Arbeit: initialize_logger wird jetzt ausgeführt.")
        tgt            = cls.get_target_log_path()
        file_handler   = logging.FileHandler(tgt, mode="a", encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(logging.INFO)

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[file_handler, stream_handler],
            force=True
        )
        logger_obj = logging.getLogger("offline_ai")
        globals()["logger"] = logger_obj

        # stdout-Umleitung via ausgelagerter Klasse
        redirector_cls = globals().get("class_stdout_redirector")
        if redirector_cls and not isinstance(sys.stdout, redirector_cls):
            sys.stdout = redirector_cls(sys.stdout)

        if logger_obj is None:
            print("[class_logger_audit_execution] FEHLER: initialize_logger hat die Aufgabe nicht erfüllt. Grund: Logger-Objekt ist None.")
            return None
        print("[class_logger_audit_execution] Erfolg: initialize_logger erfolgreich beendet.")
        return logger_obj

    @staticmethod
    def _now_stamp() -> str:
        """Erzeugt einen formatierten Zeitstempel für die Logzeile."""
        print("[class_logger_audit_execution] Starte Arbeit: _now_stamp wird jetzt ausgeführt.")
        n = _dt.datetime.now()
        result = f"{n.year},{n.month:02d},{n.day:02d},{n.hour:02d},{n.minute:02d},{n.second:02d},{n.microsecond // 1000:03d}"
        if not result or not isinstance(result, str):
            print("[class_logger_audit_execution] FEHLER: _now_stamp hat die Aufgabe nicht erfüllt. Grund: Kein gültiger Zeitstempel erzeugt.")
            return ""
        print("[class_logger_audit_execution] Erfolg: _now_stamp erfolgreich beendet.")
        return result

    @classmethod
    def write_log(cls, pc_id: str = None, phase: str = LOG_PHASE_SESSION,
                  event: str = LOG_EVENT_STEP_ACTION,
                  module: str = "-", detail: str = "-", versuch: str = "-") -> None:
        """Schreibt einen strukturierten Datensatz in die Logdatei."""
        print(f"[class_logger_audit_execution] Starte Arbeit: write_log wird jetzt ausgeführt. (Parameter: {phase}|{event})")
        pc_id = pc_id or platform.node() or "LocalAgent"
        line  = f"[{pc_id}]|[{cls._now_stamp()}]|[{phase}]|EVENT={event}|MODULE={module}|DETAIL={detail}|VERSUCH={versuch}"
        try:
            tgt = cls.get_target_log_path()
            with tgt.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except Exception as e:
            print(f"[class_logger_audit_execution] FEHLER: Schreiben des Logs fehlgeschlagen: {e}")
        print("[class_logger_audit_execution] Erfolg: write_log erfolgreich beendet.")

    @classmethod
    def log_event(cls, phase: str, event: str, module: str = "-", detail: str = "-") -> None:
        """Standard-Schnittstelle zum Eintragen eines Protokoll-Ereignisses."""
        print(f"[class_logger_audit_execution] Starte Arbeit: log_event wird jetzt ausgeführt. (Parameter: {event})")
        cls.write_log(phase=phase, event=event, module=module, detail=detail)
        print("[class_logger_audit_execution] Erfolg: log_event erfolgreich beendet.")

    @classmethod
    def info(cls, msg: str, module: str = "Agent") -> None:
        """Protokolliert eine Info-Nachricht."""
        print("[class_logger_audit_execution] Starte Arbeit: info wird jetzt ausgeführt.")
        print(f"[{module}] {msg}")
        cls.write_log(phase=cls.LOG_PHASE_AGENT, event=cls.LOG_EVENT_STEP_ACTION, module=module, detail=msg)
        print("[class_logger_audit_execution] Erfolg: info erfolgreich beendet.")

    @classmethod
    def warning(cls, msg: str, module: str = "Agent") -> None:
        """Protokolliert eine Warnung."""
        print("[class_logger_audit_execution] Starte Arbeit: warning wird jetzt ausgeführt.")
        try:
            print(f"[WARNUNG] [{module}-WARNUNG] {msg}")
        except UnicodeEncodeError:
            print(f"[WARNUNG] [{module}-WARNUNG] {msg.encode('ascii', errors='replace').decode('ascii')}")
        cls.write_log(phase=cls.LOG_PHASE_FILTER, event=cls.LOG_EVENT_BANNED, module=module, detail=msg)
        print("[class_logger_audit_execution] Erfolg: warning erfolgreich beendet.")

    @classmethod
    def error(cls, msg: str, module: str = "Agent") -> None:
        """Protokolliert einen Fehler."""
        print("[class_logger_audit_execution] Starte Arbeit: error wird jetzt ausgeführt.")
        try:
            print(f"[FEHLER] [{module}-FEHLER] {msg}")
        except UnicodeEncodeError:
            print(f"[FEHLER] [{module}-FEHLER] {msg.encode('ascii', errors='replace').decode('ascii')}")
        cls.write_log(phase=cls.LOG_PHASE_REPAIR, event=cls.LOG_EVENT_INLINE_REPAIR_FAIL, module=module, detail=msg)
        print("[class_logger_audit_execution] Erfolg: error erfolgreich beendet.")

    @classmethod
    def parse_log_lines(cls) -> List[Dict]:
        """Liest und parst die strukturierten Einträge aus der Logdatei."""
        print("[class_logger_audit_execution] Starte Arbeit: parse_log_lines wird jetzt ausgeführt.")
        tgt = cls.get_target_log_path()
        if not tgt.exists():
            result = []
            print("[class_logger_audit_execution] Erfolg: parse_log_lines erfolgreich beendet.")
            return result
        try:
            with tgt.open("r", encoding="utf-8", errors="replace") as fh:
                result = [m.groupdict() for line in fh if (m := cls._LOG_LINE_RE.match(line.strip()))]
        except Exception as e:
            print(f"[class_logger_audit_execution] FEHLER: Parsen der Logdatei fehlgeschlagen: {e}")
            return []
        if result is None:
            print("[class_logger_audit_execution] FEHLER: parse_log_lines hat die Aufgabe nicht erfüllt. Grund: Ergebnis ist None.")
            return []
        print("[class_logger_audit_execution] Erfolg: parse_log_lines erfolgreich beendet.")
        return result

    @classmethod
    def instrument_code_with_flight_recorder(cls, code_content: str, module_name: str = "TargetModule") -> str:
        """Injiziert Flugschreiber-Protokollierknoten in den AST eines Moduls."""
        print(f"[class_logger_audit_execution] Starte Arbeit: instrument_code_with_flight_recorder wird jetzt ausgeführt. (Parameter: {module_name})")
        try:
            tree = ast.parse(code_content)

            class ASTFlightInstrumenter(ast.NodeTransformer):
                """Lokaler AST-Transformer: Fügt Flugschreiber-Aufrufe in Funktionen ein."""
                def __init__(self):
                    self.counter = 0

                def _log_node(self, detail: str):
                    self.counter += 1
                    return ast.Expr(
                        value=ast.Call(
                            func=ast.Attribute(
                                value=ast.Name(id="class_logger_audit_execution", ctx=ast.Load()),
                                attr="write_log", ctx=ast.Load()
                            ),
                            args=[],
                            keywords=[
                                ast.keyword(arg="phase",  value=ast.Constant(value="FLIGHT_RECORDER")),
                                ast.keyword(arg="event",  value=ast.Constant(value="FLIGHT_STEP")),
                                ast.keyword(arg="module", value=ast.Constant(value=module_name)),
                                ast.keyword(arg="detail", value=ast.Constant(value=f"STEP_{self.counter:03d} -> {detail}")),
                            ]
                        )
                    )

                def visit_FunctionDef(self, node):
                    enter = self._log_node(f"START DEF: {node.name}")
                    node.body.insert(0, enter)
                    return self.generic_visit(node)

            instrumented = ASTFlightInstrumenter().visit(tree)
            ast.fix_missing_locations(instrumented)
            result = ast.unparse(instrumented)
        except Exception as e:
            print(f"[class_logger_audit_execution] FEHLER: Instrumentierung fehlgeschlagen: {e}")
            return code_content
        if not result or not isinstance(result, str):
            print("[class_logger_audit_execution] FEHLER: instrument_code_with_flight_recorder hat die Aufgabe nicht erfüllt. Grund: Kein gültiger Code zurückgegeben.")
            return code_content
        print("[class_logger_audit_execution] Erfolg: instrument_code_with_flight_recorder erfolgreich beendet.")
        return result

    @classmethod
    def strip_flight_recorder_code(cls, instrumented_code: str) -> str:
        """Entfernt alle Flugschreiber-Protokollierknoten wieder aus dem AST."""
        print("[class_logger_audit_execution] Starte Arbeit: strip_flight_recorder_code wird jetzt ausgeführt.")
        try:
            tree = ast.parse(instrumented_code)

            class ASTFlightPurger(ast.NodeTransformer):
                """Lokaler AST-Transformer: Entfernt write_log-Aufrufe des Flugschreibers."""
                def visit_Expr(self, node):
                    if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute):
                        if (isinstance(node.value.func.value, ast.Name)
                                and node.value.func.value.id == "class_logger_audit_execution"
                                and node.value.func.attr == "write_log"):
                            return None
                    return node

            purged = ASTFlightPurger().visit(tree)
            ast.fix_missing_locations(purged)
            result = ast.unparse(purged)
        except Exception as e:
            print(f"[class_logger_audit_execution] FEHLER: Bereinigung der Instrumentierung fehlgeschlagen: {e}")
            return instrumented_code
        if not result or not isinstance(result, str):
            print("[class_logger_audit_execution] FEHLER: strip_flight_recorder_code hat die Aufgabe nicht erfüllt. Grund: Kein gültiger Code zurückgegeben.")
            return instrumented_code
        print("[class_logger_audit_execution] Erfolg: strip_flight_recorder_code erfolgreich beendet.")
        return result

    # =========================================================================
    # EBENE 5: ZENTRALE AUSFÜHRUNGSFUNKTION
    # =========================================================================

    @classmethod
    def run_audit_logger(cls) -> dict:
        """
        Zentrale Ausführungsfunktion des Audit-Loggers.
        Initialisiert den Logger, aktiviert die stdout-Umleitung
        und liefert Pfad sowie Betriebsstatus zurück.
        """
        print("[class_logger_audit_execution] Starte Arbeit: run_audit_logger wird jetzt ausgeführt.")
        try:
            logger_obj = cls.initialize_logger()
            log_path   = cls.get_target_log_path()
            result = {
                "active":     logger_obj is not None,
                "log_path":   log_path,
                "log_exists": log_path.exists()
            }
        except Exception as e:
            print(f"[class_logger_audit_execution] FEHLER: run_audit_logger fehlgeschlagen: {e}")
            return {"active": False, "log_path": None, "log_exists": False}
        if result is None:
            print("[class_logger_audit_execution] FEHLER: run_audit_logger hat die Aufgabe nicht erfüllt. Grund: Kein Ergebnis-Dict erzeugt.")
            return {"active": False, "log_path": None, "log_exists": False}
        print("[class_logger_audit_execution] Erfolg: run_audit_logger erfolgreich beendet.")
        return result
