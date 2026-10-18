
import datetime as _dt
import logging
import platform
import re
import sys
from pathlib import Path
from typing import Dict, List

# Optionaler psutil-Import für präzise RAM-Erkennung
try:
    import psutil
except ImportError:
    psutil = None

class class_agent_logger:
    """Zentraler, robuster Logger für den Agenten-Workflow zur lückenlosen 
    Protokollierung aller Mikroschritte, Terminal-Ausgaben, Hardware-Analysen und Audits.
    """

    # --- 1. Log-Phasen & Events ---
    LOG_PHASE_SESSION: str      = "SESSION"
    LOG_PHASE_HARDWARE: str     = "HARDWARE"
    LOG_PHASE_INSTALL: str      = "INSTALL"
    LOG_PHASE_IMPORT: str       = "IMPORT"
    LOG_PHASE_REPAIR: str       = "REPAIR"
    LOG_PHASE_FILTER: str       = "FILTER"
    LOG_PHASE_AGENT: str        = "AGENT_IPYNB"
    LOG_PHASE_TERMINAL: str     = "TERMINAL"

    LOG_EVENT_SESSION_START: str  = "SESSION_START"
    LOG_EVENT_HW_NEW: str         = "HW_NEW"
    LOG_EVENT_HW_KNOWN: str       = "HW_KNOWN"
    LOG_EVENT_INSTALL_TRY: str    = "INSTALL_TRY"
    LOG_EVENT_INSTALL_OK: str     = "INSTALL_OK"
    LOG_EVENT_INSTALL_FAIL: str   = "INSTALL_FAIL"
    LOG_EVENT_IMPORT_OK: str      = "IMPORT_OK"
    LOG_EVENT_RETRY: str          = "RETRY"
    LOG_EVENT_RETRY_EXHAUSTED: str = "RETRY_EXHAUSTED"
    LOG_EVENT_INLINE_REPAIR_TRY: str = "INLINE_REPAIR_TRY"
    LOG_EVENT_INLINE_REPAIR_OK: str  = "INLINE_REPAIR_OK"
    LOG_EVENT_INLINE_REPAIR_FAIL: str = "INLINE_REPAIR_FAIL"
    LOG_EVENT_SKIP_HW: str        = "SKIP_HW"
    LOG_EVENT_BANNED: str         = "BANNED"
    LOG_EVENT_STEP_ACTION: str    = "STEP_ACTION"
    LOG_EVENT_AUDIT_RESULT: str   = "AUDIT_RESULT"
    LOG_EVENT_STDOUT: str         = "STDOUT"

    STATUS_EVENT_MAP: Dict[str, str] = {
        LOG_EVENT_SKIP_HW:           "HW_INCOMPATIBLE",
        LOG_EVENT_IMPORT_OK:         "OK",
        LOG_EVENT_INLINE_REPAIR_OK:  "OK",
        LOG_EVENT_BANNED:            "BANNED",
        LOG_EVENT_RETRY_EXHAUSTED:   "RETRY_EXHAUSTED",
    }

    # Konfiguration & Dateinamen
    LOG_FILE_NAME: str = "LOG_agent_ipynb_execution.log"
    LOGGER_NAME: str = "agent_ipynb"
    DIR_SRC: str = "src"
    DIR_LOGS: str = "logs"
    MAX_ROOT_SEARCH_DEPTH: int = 5

    LOG_LINE_PATTERN_STR: str = (
        r"^\[(?P<pc_id>[^\]]+)\]\|\[(?P<ts>[^\]]+)\]\|\[(?P<phase>[^\]]+)\]\|"
        r"EVENT=(?P<event>[^|]*)\|MODULE=(?P<module>[^|]*)\|"
        r"DETAIL=(?P<detail>.*)\|VERSUCH=(?P<versuch>[^|]*)$"
    )
    _LOG_LINE_RE = re.compile(LOG_LINE_PATTERN_STR)

    class class_stdout_redirector:
        """Interner Helfer: Spiegelt sämtliche Terminal-Ausgaben (print etc.) 
        vollautomatisch in das Log, ohne den Konsolenfluss zu stören.
        """
        def __init__(self, original_stream):
            self.terminal = original_stream

        def write(self, message):
            self.terminal.write(message)
            self.terminal.flush()
            if message and message.strip():
                cleaned = message.strip()
                # Verhindere Endlosschleifen durch interne Log-Fehlerausgaben
                if not cleaned.startswith("[LOG") and not cleaned.startswith("[AGENT LOGIC"):
                    try:
                        pc_id = platform.node() or "LocalAgent"
                        class_agent_logger.write_log(
                            pc_id=pc_id,
                            phase=class_agent_logger.LOG_PHASE_TERMINAL,
                            event=class_agent_logger.LOG_EVENT_STDOUT,
                            detail=cleaned
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
                if (d / cls.DIR_SRC).is_dir() or (d / "DIR_CONFIG").is_dir() or (d / ".git").is_dir():
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
    def resolve_log_file_name(cls) -> str:
        return cls.LOG_FILE_NAME

    @classmethod
    def get_target_log_path(cls) -> Path:
        return cls.get_dir(cls.DIR_LOGS) / cls.resolve_log_file_name()

    @classmethod
    def initialize_logger(cls) -> logging.Logger:
        """Initialisiert das Logging-System, setzt die Log-Datei beim Start 
        einmalig per mode='w' frisch auf und aktiviert die automatische Terminal-Spiegelung.
        """
        root = cls._detect_project_root()
        logs = cls.get_dir(cls.DIR_LOGS, ensure=True)
        resolved_log = cls.resolve_log_file_name()
        tgt = logs / resolved_log

        # Globals für den Agentenkontext setzen
        g = globals()
        g["PROJECT_ANCHOR_DIR"] = root.name
        g["LOG_FILE_NAME"] = resolved_log
        g["PROJECT_ROOT"], g["LOGS_DIR"], g["TARGET_LOG_PATH"] = root, logs, tgt

        # Einmaliges Überschreiben beim Start (mode="w")
        file_handler = logging.FileHandler(tgt, mode="w", encoding="utf-8")
        file_handler.setLevel(logging.INFO)

        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(logging.INFO)

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[file_handler, stream_handler],
            force=True
        )
        logger = logging.getLogger(cls.LOGGER_NAME)
        g["logger"] = logger

        # AUTOMATISCHES TERMINAL-MIRRORING AKTIVIEREN
        if not isinstance(sys.stdout, cls.class_stdout_redirector):
            sys.stdout = cls.class_stdout_redirector(sys.stdout)

        return logger

    @staticmethod
    def _now_stamp() -> str:
        n = _dt.datetime.now()
        return f"{n.year},{n.month:02d},{n.day:02d},{n.hour:02d},{n.minute:02d},{n.second:02d},{n.microsecond // 1000:03d}"

    @classmethod
    def write_log(cls, pc_id: str, phase: str, event: str,
                  module: str = "-", detail: str = "-", versuch: str = "-") -> None:
        """Schreibt Mikroschritte fortlaufend im Append-Modus (mode='a'), 
        damit während der Laufzeit nichts verloren geht.
        """
        line = (f"[{pc_id}]|[{cls._now_stamp()}]|[{phase}]|"
                f"EVENT={event}|MODULE={module}|DETAIL={detail}|VERSUCH={versuch}")
        tgt = cls.get_target_log_path()
        try:
            tgt.parent.mkdir(parents=True, exist_ok=True)
            with tgt.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except Exception as exc:
            # Direkt auf den echten Terminal-Stream schreiben, um Endlosschleifen zu umgehen
            if hasattr(sys.stdout, "terminal"):
                print(f"[LOG WRITE ERROR] {exc}", file=sys.stdout.terminal)
            else:
                sys.__stderr__.write(f"[LOG WRITE ERROR] {exc}\n")

        if event in (cls.LOG_EVENT_BANNED, cls.LOG_EVENT_INSTALL_FAIL, 
                     cls.LOG_EVENT_RETRY_EXHAUSTED, cls.LOG_EVENT_INLINE_REPAIR_FAIL, 
                     cls.LOG_EVENT_SKIP_HW):
            logging.warning(f"[AGENT LOGIC WARNING] {line}")

    @classmethod
    def parse_log_lines(cls) -> List[Dict]:
        """Liest das Log des letzten Laufs ein und filtert fehler-/zustandsrelevante Daten."""
        tgt = cls.get_target_log_path()
        if not tgt.exists():
            return []
        try:
            with tgt.open("r", encoding="utf-8", errors="replace") as fh:
                return [m.groupdict() for line in fh if (m := cls._LOG_LINE_RE.match(line.strip()))]
        except Exception as exc:
            print(f"[LOG PARSE ERROR] {exc}", file=sys.stderr)
            return []

# Automatische Registrierung im Namespace
globals()['class_agent_logger'] = class_agent_logger