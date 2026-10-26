import ast
import datetime as _dt
import logging
import os
import platform
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# 1. Hauptverzeichnis zum Python-Pfad hinzufügen
sys.path.append(str(Path(__file__).resolve().parent))

# 2. Auto-Bootstrap & globale Registrierung
try:
    from agent_universal_skript.auto_bootstrap_and_register_agent_tools import (
        auto_bootstrap_and_register_agent_tools,
    )

    auto_bootstrap_and_register_agent_tools()
except ImportError:
    pass

# Optionaler psutil-Import für präzise RAM-Erkennung
try:
    import psutil
except ImportError:
    psutil = None


class class_logger_audit_execution:
    """Zentraler, robuster Logger für den Agenten-Workflow zur lückenlosen
    Protokollierung aller Mikroschritte, Terminal-Ausgaben, Hardware-Analysen,
    Audits und dynamischen AST-Flight-Recordings. Inklusive automatischer
    Kontext- und Notebook-Erkennung.
    """

    # GLOBALE KONFIGURATIONEN NUR FÜR DEN LOGGER (_cfg.setdefault)
    _cfg: Dict[str, Any] = globals().setdefault("_AGENT_CONFIG", {})

    MAX_ROOT_SEARCH_DEPTH: int = _cfg.setdefault("MAX_ROOT_SEARCH_DEPTH", 5)
    DIR_SRC: str = _cfg.setdefault("DIR_SRC", "src")
    DIR_LOGS: str = _cfg.setdefault("DIR_LOGS", "logs")

    # DYNAMISCHE KONTEXT- & NAMENSERKENNUNG (IPYNB vs. AGENT)
    @classmethod
    def _detect_execution_context(cls) -> Tuple[str, str]:
        """Ermittelt vollautomatisch zur Laufzeit, ob der Code in einem Jupyter Notebook
        (.ipynb) oder im Terminal (Agent) ausgeführt wird, und bestimmt den passenden Log-Namen.
        """
        is_jupyter = False
        identifier = "agent_terminal"

        try:
            ip = get_ipython()
            if ip is not None:
                shell_type = ip.__class__.__name__
                if "Shell" in shell_type:
                    is_jupyter = True
                    try:
                        root = cls._detect_project_root()
                        notebooks_dir = (
                            root / "notebooks"
                            if (root / "notebooks").exists()
                            else Path.cwd()
                        )
                        ipynb_files = sorted(
                            notebooks_dir.rglob("*.ipynb"),
                            key=os.path.getmtime,
                            reverse=True,
                        )
                        if ipynb_files:
                            identifier = f"notebook_{ipynb_files[0].stem}"
                        else:
                            identifier = "jupyter_session"
                    except Exception:
                        identifier = "jupyter_session"
        except NameError:
            pass

        if is_jupyter:
            log_filename = f"LOG_{identifier}.log"
            logger_name = f"jupyter_{identifier}"
        else:
            log_filename = "LOG_agent_execution.log"
            logger_name = "agent_terminal"

        return log_filename, logger_name

    @classmethod
    def resolve_log_file_name(cls) -> str:
        """Gibt stets den aktuell ermittelten Log-Dateinamen zurück."""
        log_file, _ = cls._detect_execution_context()
        return log_file

    @classmethod
    def resolve_logger_name(cls) -> str:
        """Gibt stets den aktuell ermittelten Logger-Namen zurück."""
        _, logger_name = cls._detect_execution_context()
        return logger_name

    @classmethod
    def get_target_log_path(cls) -> Path:
        return cls.get_dir(cls.DIR_LOGS) / cls.resolve_log_file_name()

    # 1. Log-Phasen & Events
    LOG_PHASE_SESSION: str      = "SESSION"
    LOG_PHASE_HARDWARE: str     = "HARDWARE"
    LOG_PHASE_INSTALL: str      = "INSTALL"
    LOG_PHASE_IMPORT: str       = "IMPORT"
    LOG_PHASE_REPAIR: str       = "REPAIR"
    LOG_PHASE_FILTER: str       = "FILTER"
    LOG_PHASE_AGENT: str        = "AGENT_IPYNB"
    LOG_PHASE_TERMINAL: str     = "TERMINAL"
    LOG_PHASE_FLIGHT: str       = "FLIGHT_RECORDER"

    LOG_EVENT_SESSION_START: str= "SESSION_START"
    LOG_EVENT_HW_NEW: str       = "HW_NEW"
    LOG_EVENT_HW_KNOWN: str     = "HW_KNOWN"
    LOG_EVENT_INSTALL_TRY: str  = "INSTALL_TRY"
    LOG_EVENT_INSTALL_OK: str   = "INSTALL_OK"
    LOG_EVENT_INSTALL_FAIL: str = "INSTALL_FAIL"
    LOG_EVENT_IMPORT_OK: str    = "IMPORT_OK"
    LOG_EVENT_RETRY: str        = "RETRY"
    LOG_EVENT_RETRY_EXHAUSTED: str      = "RETRY_EXHAUSTED"
    LOG_EVENT_INLINE_REPAIR_TRY: str    = "INLINE_REPAIR_TRY"
    LOG_EVENT_INLINE_REPAIR_OK: str     = "INLINE_REPAIR_OK"
    LOG_EVENT_INLINE_REPAIR_FAIL: str   = "INLINE_REPAIR_FAIL"
    LOG_EVENT_SKIP_HW: str              = "SKIP_HW"
    LOG_EVENT_BANNED: str               = "BANNED"
    LOG_EVENT_STEP_ACTION: str          = "STEP_ACTION"
    LOG_EVENT_AUDIT_RESULT: str         = "AUDIT_RESULT"
    LOG_EVENT_STDOUT: str               = "STDOUT"
    LOG_EVENT_FLIGHT_STEP: str          = "FLIGHT_STEP"

    STATUS_EVENT_MAP: Dict[str, str] = {
        LOG_EVENT_SKIP_HW:           "HW_INCOMPATIBLE",
        LOG_EVENT_IMPORT_OK:         "OK",
        LOG_EVENT_INLINE_REPAIR_OK:  "OK",
        LOG_EVENT_BANNED:            "BANNED",
        LOG_EVENT_RETRY_EXHAUSTED:   "RETRY_EXHAUSTED",
    }

    LOG_LINE_PATTERN_STR: str = (
        r"^\[(?P<pc_id>[^\]]+)\]\|\[(?P<ts>[^\]]+)\]\|\[(?P<phase>[^\]]+)\]\|"
        r"EVENT=(?P<event>[^|]*)\|MODULE=(?P<module>[^|]*)\|"
        r"DETAIL=(?P<detail>.*)\|VERSUCH=(?P<versuch>[^|]*)$"
    )
    _LOG_LINE_RE = re.compile(LOG_LINE_PATTERN_STR)

    class class_stdout_redirector:
        """Interner Helfer: Spiegelt sämtliche Terminal-Ausgaben vollautomatisch
        in das Log, ohne den Konsolenfluss zu stören.
        """
        def __init__(self, original_stream):
            self.terminal = original_stream

        def write(self, message):
            self.terminal.write(message)
            self.terminal.flush()
            if message and message.strip():
                cleaned = message.strip()
                if (
                    not cleaned.startswith("[LOG")
                    and not cleaned.startswith("[AGENT LOGIC")
                    and "Arbeitet..." not in cleaned
                ):
                    try:
                        pc_id = platform.node() or "LocalAgent"
                        class_logger_audit_execution.write_log(
                            pc_id=pc_id,
                            phase=class_logger_audit_execution.LOG_PHASE_TERMINAL,
                            event=class_logger_audit_execution.LOG_EVENT_STDOUT,
                            detail=cleaned,
                        )
                    except Exception:
                        pass

        def flush(self):
            self.terminal.flush()

    @classmethod
    def _detect_project_root(cls) -> Path:
        """Stochastische Projekterkennung via CWD & __file__."""
        start_paths: List[Path] = [Path.cwd()]
        try:
            f = globals().get("__file__")
            if f:
                start_paths.append(Path(f).resolve().parent)
        except Exception:
            pass
        for start in start_paths:
            d = start.resolve()
            if d.name == "notebooks" and (d.parent / cls.DIR_SRC).is_dir():
                return d.parent
            if d.name == cls.DIR_SRC:
                return d.parent
            for _ in range(cls.MAX_ROOT_SEARCH_DEPTH):
                if (
                    (d / cls.DIR_SRC).is_dir()
                    or (d / "DIR_CONFIG").is_dir()
                    or (d / ".git").is_dir()
                ):
                    return d
                if d.name == cls.DIR_SRC:
                    return d.parent
                if d.parent == d:
                    break
                d = d.parent
        return Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()

    @classmethod
    def get_dir(cls, dirname: str, ensure: bool = False) -> Path:
        """Ermittelt und erstellt (optional) Verzeichnisse im Projektkontext."""
        root = cls._detect_project_root()
        target = root / dirname
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    @classmethod
    def initialize_logger(cls) -> logging.Logger:
        """Initialisiert das Logging-System dynamisch basierend auf dem aktuellen Kontext."""
        root = cls._detect_project_root()
        logs = cls.get_dir(cls.DIR_LOGS, ensure=True)
        resolved_log = cls.resolve_log_file_name()
        resolved_logger_name = cls.resolve_logger_name()
        tgt = logs / resolved_log
        g = globals()
        g["PROJECT_ANCHOR_DIR"] = root.name
        g["LOG_FILE_NAME"] = resolved_log
        g["PROJECT_ROOT"], g["LOGS_DIR"], g["TARGET_LOG_PATH"] = root, logs, tgt
        file_handler = logging.FileHandler(tgt, mode="w", encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(logging.INFO)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[file_handler, stream_handler],
            force=True,
        )
        logger_obj = logging.getLogger(resolved_logger_name)
        g["logger"] = logger_obj
        if not isinstance(sys.stdout, cls.class_stdout_redirector):
            sys.stdout = cls.class_stdout_redirector(sys.stdout)
        return logger_obj

    @staticmethod
    def _now_stamp() -> str:
        n = _dt.datetime.now()
        return f"{n.year},{n.month:02d},{n.day:02d},{n.hour:02d},{n.minute:02d},{n.second:02d},{n.microsecond // 1000:03d}"

    @classmethod
    def write_log(cls,pc_id: str = None,phase: str = LOG_PHASE_SESSION,event: str = LOG_EVENT_STEP_ACTION,
                    module: str = "-",detail: str = "-",versuch: str = "-",) -> None:
        """Schreibt Mikroschritte fortlaufend im Append-Modus (mode='a')."""
        if pc_id is None:
            pc_id = platform.node() or "LocalAgent"
        line = (
                f"[{pc_id}]|[{cls._now_stamp()}]|[{phase}]|"
                f"EVENT={event}|MODULE={module}|DETAIL={detail}|VERSUCH={versuch}"
                )
        tgt = cls.get_target_log_path()
        try:
            tgt.parent.mkdir(parents=True, exist_ok=True)
            with tgt.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except Exception as exc:
            if hasattr(sys.stdout, "terminal"):
                print(f"[LOG WRITE ERROR] {exc}", file=sys.stdout.terminal)
            else:
                sys.__stderr__.write(f"[LOG WRITE ERROR] {exc}\n")

        if event in (
            cls.LOG_EVENT_BANNED,
            cls.LOG_EVENT_INSTALL_FAIL,
            cls.LOG_EVENT_RETRY_EXHAUSTED,
            cls.LOG_EVENT_INLINE_REPAIR_FAIL,
            cls.LOG_EVENT_SKIP_HW,
        ):
            logging.warning(f"[AGENT LOGIC WARNING] {line}")

    @classmethod
    def log_event(cls, phase: str, event: str, module: str = "-", detail: str = "-") -> None:
        """Standardisierter Aufruf zum Eintragen eines spezifischen Workflow-Events."""
        cls.write_log(phase=phase, event=event, module=module, detail=detail)

    @classmethod
    def info(cls, msg: str, module: str = "Agent") -> None:
        """Standardisiertes Info-Logging über Terminal und Datei."""
        print(f"[{module}] {msg}")
        cls.write_log(
            phase=cls.LOG_PHASE_AGENT,
            event=cls.LOG_EVENT_STEP_ACTION,
            module=module,
            detail=msg,
        )

    @classmethod
    def warning(cls, msg: str, module: str = "Agent") -> None:
        """Standardisiertes Warning-Logging über Terminal und Datei."""
        print(f"⚠️ [{module}-WARNUNG] {msg}")
        cls.write_log(
            phase=cls.LOG_PHASE_FILTER,
            event=cls.LOG_EVENT_BANNED,
            module=module,
            detail=msg,
        )

    @classmethod
    def error(cls, msg: str, module: str = "Agent") -> None:
        """Standardisiertes Error-Logging über Terminal und Datei."""
        print(f"❌ [{module}-FEHLER] {msg}")
        cls.write_log(
            phase=cls.LOG_PHASE_REPAIR,
            event=cls.LOG_EVENT_INLINE_REPAIR_FAIL,
            module=module,
            detail=msg,
        )

    @classmethod
    def parse_log_lines(cls) -> List[Dict]:
        """Liest das Log des letzten Laufs ein und filtert fehler-/zustandsrelevante Daten."""
        tgt = cls.get_target_log_path()
        if not tgt.exists():
            return []
        try:
            with tgt.open("r", encoding="utf-8", errors="replace") as fh:
                return [
                    m.groupdict()
                    for line in fh
                    if (m := cls._LOG_LINE_RE.match(line.strip()))
                ]
        except Exception as exc:
            print(f"[LOG PARSE ERROR] {exc}", file=sys.stderr)
            return []

    # DYNAMISCHE FLUGSCHREIBER-INSTRUMENTIERUNG (AST-BASED)
    @classmethod
    def instrument_code_with_flight_recorder(
        cls, code_content: str, module_name: str = "TargetModule"
    ) -> str:
        """Injiziert vor jeder logischen Zeile und Methode einen Schritt-Log-Eintrag."""
        try:
            tree = ast.parse(code_content)

            class ASTFlightInstrumenter(ast.NodeTransformer):
                def __init__(self):
                    self.step_counter = 0

                def _generate_log_node(self, details: str) -> ast.Expr:
                    self.step_counter += 1
                    return ast.Expr(
                        value=ast.Call(
                            func=ast.Attribute(
                                value=ast.Name(
                                    id="class_logger_audit_execution",
                                    ctx=ast.Load(),
                                ),
                                attr="write_log",
                                ctx=ast.Load(),
                            ),
                            args=[],
                            keywords=[
                                ast.keyword(
                                    arg="phase",
                                    value=ast.Constant(
                                        value=class_logger_audit_execution.LOG_PHASE_FLIGHT
                                    ),
                                ),
                                ast.keyword(
                                    arg="event",
                                    value=ast.Constant(
                                        value=class_logger_audit_execution.LOG_EVENT_FLIGHT_STEP
                                    ),
                                ),
                                ast.keyword(
                                    arg="module",
                                    value=ast.Constant(value=module_name),
                                ),
                                ast.keyword(
                                    arg="detail",
                                    value=ast.Constant(
                                        value=f"STEP_{self.step_counter:03d} -> {details}"
                                    ),
                                ),
                            ],
                        )
                    )

                def visit_FunctionDef(self, node):
                    enter_log = self._generate_log_node(f"START DEF: {node.name}")
                    node.body.insert(0, enter_log)
                    new_body = []
                    for item in node.body:
                        if (
                            isinstance(
                                item, (ast.Assign, ast.Call, ast.Return, ast.Expr)
                            )
                            and item != enter_log
                        ):
                            try:
                                src_preview = (
                                    ast.unparse(item)
                                    .strip()
                                    .replace("\n", " ")[:40]
                                )
                            except Exception:
                                src_preview = type(item).__name__
                            new_body.append(
                                self._generate_log_node(
                                    f"EXEC LINE: {src_preview}"
                                )
                            )
                        new_body.append(item)
                    node.body = new_body
                    return self.generic_visit(node)

            instrumenter = ASTFlightInstrumenter()
            modified_tree = instrumenter.visit(tree)
            ast.fix_missing_locations(modified_tree)
            return ast.unparse(modified_tree)
        except Exception as e:
            cls.write_log(
                phase=cls.LOG_PHASE_REPAIR,
                event=cls.LOG_EVENT_INLINE_REPAIR_FAIL,
                detail=f"Flight recorder failure: {str(e)}",
            )
            return code_content

    @classmethod
    def strip_flight_recorder_code(cls, instrumented_code: str) -> str:
        """Entfernt alle injizierten Flugschreiber-Knoten restlos aus dem AST."""
        try:
            tree = ast.parse(instrumented_code)

            class ASTFlightPurger(ast.NodeTransformer):
                def visit_Expr(self, node):
                    if isinstance(node.value, ast.Call) and isinstance(
                        node.value.func, ast.Attribute
                    ):
                        if (
                            isinstance(node.value.func.value, ast.Name)
                            and node.value.func.value.id
                            == "class_logger_audit_execution"
                        ):
                            if node.value.func.attr == "write_log":
                                return None
                    return node

            purged_tree = ASTFlightPurger().visit(tree)
            ast.fix_missing_locations(purged_tree)
            return ast.unparse(purged_tree)
        except Exception:
            return instrumented_code