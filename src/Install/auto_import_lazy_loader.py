# -*- coding: utf-8 -*-
"""
AUTO_IMPORT_LAZY_LOAD - Stochastic & Self-Healing Dependency Manager
Offline-AI Platform Pipeline Component

Retains established pipeline architecture (logging, hardware profiling,
PC_ID hashing, download manager with wheel fallback, Ollama & Hermes guard).
Removes rigid package whitelists in favor of dynamic runtime interception,
stochastic package name resolution, absence verification, autonomous installation,
and a seamless retry loop.
"""

import builtins
import ctypes
import datetime as _dt
import hashlib
import importlib
import importlib.util
import logging
import os
import platform
import re
import subprocess
import sys
import time
import types
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Module-level constants & defaults
LOG_FILE_NAME          = "LOG_ollama_model_download_utility.log"
MAX_RETRIES            = 2
CPU_CAPABILITY_TAGS: Set[str] = {"AVX", "AVX2", "AVX512", "FMA", "BMI2", "SSE4"}
VC_REDIST_HINT_VERSION = "14.38.33130 (Visual C++ 2015-2022, x64) oder neuer"
ERROR_PATTERNS: List[str] = [
    r"0x45[aA]", r"WinError 1114", r"DllMain returned false",
    r"Illegal instruction", r"AVX[2]?", r"instruction set",
    r"not a valid Win32 application", r"wrong ELF class",
    r"c10\.dll", r"_pywrap_tensorflow_internal",
]

# Baseline core libraries (used as defaults, not a closed whitelist)
DEFAULT_CORE_IMPORT: List[Tuple] = [
    ("ctypes",         None,      "",           None),
    ("importlib",      None,      "",           None),
    ("json",           None,      "",           None),
    ("logging",        None,      "",           None),
    ("os",             None,      "",           None),
    ("platform",       None,      "",           None),
    ("re",             None,      "",           None),
    ("shutil",         None,      "",           None),
    ("subprocess",     None,      "",           None),
    ("sys",            None,      "",           None),
    ("threading",      None,      "",           None),
    ("time",           None,      "",           None),
    ("urllib.request", None,      "",           None),
    ("ipywidgets",     "widgets", "ipywidgets", None),
    ("ollama",         None,      "ollama",     None),
    ("psutil",         None,      "psutil",     None),
    ("requests",       None,      "requests",   None),
    ("tqdm",           None,      "tqdm",       None),
]

DEFAULT_CORE_FROM: List[Tuple] = [
    ("pathlib",         "Path",            None, ""),
    ("huggingface_hub", "HfApi",           None, "huggingface_hub"),
    ("huggingface_hub", "hf_hub_download", None, "huggingface_hub"),
    ("IPython.display", "HTML",            None, "ipython"),
    ("IPython.display", "clear_output",    None, "ipython"),
    ("IPython.display", "display",         None, "ipython"),
    ("llama_cpp",       "Llama",           None, "llama-cpp-python"),
    ("ollama",          "Client",          None, "ollama"),
]

# Aliases for backward compatibility
LIBRARY_IMPORT = DEFAULT_CORE_IMPORT
LIBRARY_FROM   = DEFAULT_CORE_FROM

# Bootstrap packages mapping
_BOOTSTRAP_DEPS: List[Tuple[str, str, List[Tuple[str, str]]]] = [
    ("psutil",               "psutil",    [("psutil", "psutil")]),
    ("tqdm",                 "tqdm",      [("tqdm", "_tqdm_mod"), ("tqdm.tqdm", "tqdm")]),
    ("packaging.specifiers", "packaging", [
        ("packaging.specifiers.InvalidSpecifier", "InvalidSpecifier"),
        ("packaging.specifiers.SpecifierSet",     "SpecifierSet"),
    ]),
    ("importlib.metadata",   "",          [
        ("importlib.metadata.PackageNotFoundError", "PackageNotFoundError"),
        ("importlib.metadata.version",              "version"),
    ]),
]


class AUTO_IMPORT_LAZY_LOAD:
    """
    Encapsulates the full stochastic lazy-load & self-healing dependency-management pipeline.

    Single public entry point:
        AUTO_IMPORT_LAZY_LOAD.bootstrap()
    """

    _interceptor_installed: bool = False
    _orig_builtin_import = None
    _orig_importlib_import = None
    _is_healing: bool = False

    # CHAPTER 2: PROJECT ROOT & LOG PATH
    @staticmethod
    def get_project_root() -> Path:
        """Sucht rekursiv nach dem Projektverzeichnis ('Offline_AI' oder mit src-Ordner)."""
        d = Path.cwd()
        for _ in range(7):
            if (d / "src").is_dir() or d.name == "Offline_AI":
                return d
            if d.name == "src":
                return d.parent
            if d.parent == d:
                break
            d = d.parent
        return Path.cwd()

    @classmethod
    def _setup_logging_and_paths(cls) -> None:
        """Initialises PROJECT_ROOT, LOGS_DIR, TARGET_LOG_PATH, and logging."""
        root = cls.get_project_root()
        logs = root / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        tgt  = logs / LOG_FILE_NAME
        g    = globals()
        g["PROJECT_ROOT"], g["LOGS_DIR"], g["TARGET_LOG_PATH"] = root, logs, tgt
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[
                logging.FileHandler(tgt, encoding="utf-8"),
                logging.StreamHandler(sys.stdout),
            ],
        )
        g["logger"] = logging.getLogger("AutoImporter")

    # CHAPTER 3: LOG WRITER / PARSER
    @staticmethod
    def _now_stamp() -> str:
        n = _dt.datetime.now()
        return f"{n.year},{n.month:02d},{n.day:02d},{n.hour:02d},{n.minute:02d},{n.second:02d}"

    @staticmethod
    def write_log(pc_id: str, phase: str, event: str,
                  module: str = "-", detail: str = "-", versuch: str = "-") -> None:
        """Einziger Schreibpunkt fuer das strukturierte Log."""
        line = (f"[{pc_id}]|[{AUTO_IMPORT_LAZY_LOAD._now_stamp()}]|[{phase}]|"
                f"EVENT={event}|MODULE={module}|DETAIL={detail}|VERSUCH={versuch}")
        tgt = globals().get("TARGET_LOG_PATH")
        if tgt:
            try:
                Path(tgt).open("a", encoding="utf-8").write(line + "\n")
            except Exception as exc:
                print(f"[LOG WRITE ERROR] {exc}", file=sys.stderr)
        if event in ("BANNED", "INSTALL_FAIL", "RETRY_EXHAUSTED", "INLINE_REPAIR_FAIL", "SKIP_HW"):
            logging.warning(f"[IMPORT LOGIC] {line}")

    _LOG_LINE_RE = re.compile(
        r"^\[(?P<pc_id>[^\]]+)\]\|\[(?P<ts>[^\]]+)\]\|\[(?P<phase>[^\]]+)\]\|"
        r"EVENT=(?P<event>[^|]*)\|MODULE=(?P<module>[^|]*)\|"
        r"DETAIL=(?P<detail>.*)\|VERSUCH=(?P<versuch>[^|]*)$"
    )

    @classmethod
    def parse_log_lines(cls) -> List[Dict]:
        """Liest das komplette Log ein, eine Regex pro Zeile."""
        tgt = globals().get("TARGET_LOG_PATH")
        if not tgt or not Path(tgt).exists():
            return []
        try:
            with Path(tgt).open("r", encoding="utf-8", errors="replace") as fh:
                return [m.groupdict() for line in fh if (m := cls._LOG_LINE_RE.match(line.strip()))]
        except Exception as exc:
            print(f"[LOG PARSE ERROR] {exc}", file=sys.stderr)
            return []

    # CHAPTER 4: HARDWARE INFORMATION
    @staticmethod
    def _detect_cpu_flags() -> Set[str]:
        """Proaktive Erkennung unterstuetzter Instruction-Sets, plattformabhaengig."""
        flags: Set[str] = set()
        sys_name = platform.system()
        if sys_name == "Linux":
            try:
                with open("/proc/cpuinfo") as fh:
                    tokens = set(
                        next((l for l in fh.read().lower().splitlines() if l.startswith("flags")), "")
                        .split(":", 1)[-1].split()
                    )
                for tok, tag in [("avx", "AVX"), ("avx2", "AVX2"), ("avx512f", "AVX512"),
                                 ("fma", "FMA"), ("bmi2", "BMI2")]:
                    if tok in tokens: flags.add(tag)
                if "sse4_1" in tokens or "sse4_2" in tokens: flags.add("SSE4")
            except Exception:
                pass
        elif sys_name == "Windows":
            try:
                k32 = ctypes.windll.kernel32
                for feat_id, tag in [(17, "AVX"), (40, "AVX2"), (41, "AVX512")]:
                    if k32.IsProcessorFeaturePresent(feat_id): flags.add(tag)
            except Exception:
                pass
        elif sys_name == "Darwin":
            try:
                out = subprocess.run(
                    ["sysctl", "-n", "machdep.cpu.features", "machdep.cpu.leaf7_features"],
                    capture_output=True, text=True, timeout=3,
                ).stdout.upper()
                for substr, tag in [("AVX2", "AVX2"), (" AVX ", "AVX"), (" AVX1.0 ", "AVX"),
                                    ("FMA", "FMA"), ("BMI2", "BMI2"), ("SSE4.1", "SSE4"), ("SSE4.2", "SSE4")]:
                    if substr in f" {out} ": flags.add(tag)
            except Exception:
                pass
        return flags

    @staticmethod
    def _detect_gpu_ram() -> Dict:
        """Erfasst alle Nvidia-GPUs mit Namen und VRAM."""
        gpu_list: List[Dict] = []
        total = 0.0
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=3,
            )
            if out.returncode == 0:
                for line in filter(None, out.stdout.strip().splitlines()):
                    parts = line.strip().split(",")
                    if len(parts) == 2:
                        try: vram = round(float(parts[1].strip()) / 1024, 1)
                        except ValueError: vram = 0.0
                        gpu_list.append({"name": parts[0].strip(), "vram_gb": vram})
                        total += vram
        except Exception:
            pass
        return {"count": len(gpu_list), "total_vram": round(total, 1), "details": gpu_list}

    @classmethod
    def get_hardware_information(cls) -> Dict:
        """Collects CPU, RAM (via psutil), GPU, and platform info."""
        _psutil  = globals().get("psutil")
        gpu_info = cls._detect_gpu_ram()
        try:
            ram_gb = round(_psutil.virtual_memory().total / 1024**3, 1) if _psutil else 0.0
        except Exception:
            ram_gb = 0.0
        return {
            "CORE": os.cpu_count() or 0, "RAM": ram_gb,
            "GPU_COUNT": gpu_info["count"], "GPU_TOTAL_VRAM": gpu_info["total_vram"],
            "GPU_DETAILS": gpu_info["details"], "PLATFORM": platform.system(),
            "OS_BITNESS": "64bit" if sys.maxsize > 2**32 else "32bit",
            "CPU_ARCH": platform.machine(), "CPU_FLAGS": cls._detect_cpu_flags(),
        }

    @staticmethod
    def compute_hw_hash(hw_info: Dict) -> str:
        """HW_HASH-Basis: OHNE MAC/RAM/GPU_RAM."""
        basis = f"{hw_info['CPU_ARCH']}|{hw_info['PLATFORM']}|{hw_info['OS_BITNESS']}|{hw_info['CORE']}"
        return hashlib.sha1(basis.encode()).hexdigest()[:8]

    # CHAPTER 5: PC_ID VERGABE
    @classmethod
    def get_or_register_pc_id(cls) -> str:
        """
        Bekannte Hardware -> PC_ID uebernehmen (HW_KNOWN).
        Unbekannte Hardware -> neue PC<N>-ID vergeben (HW_NEW).
        """
        hw_info  = cls.get_hardware_information()
        hw_hash  = cls.compute_hw_hash(hw_info)
        entries  = cls.parse_log_lines()
        known: Dict[str, str] = {}
        max_n = 0
        for e in entries:
            if e["phase"] == "HARDWARE" and e["event"] in ("HW_NEW", "HW_KNOWN"):
                if m := re.search(r"hash:([0-9a-fA-F]+)", e["detail"]):
                    known.setdefault(m.group(1), e["pc_id"])
                if m2 := re.match(r"PC(\d+)$", e["pc_id"]):
                    max_n = max(max_n, int(m2.group(1)))
        if hw_hash in known:
            pc_id = known[hw_hash]
            cls.write_log(pc_id, "HARDWARE", "HW_KNOWN", detail=f"hash:{hw_hash}")
            return pc_id
        pc_id = f"PC{max_n + 1}"
        flags_str      = ";".join(sorted(hw_info["CPU_FLAGS"])) or "-"
        gpus_formatted = (";".join(f"{g['name']} ({g['vram_gb']}GB)" for g in hw_info["GPU_DETAILS"])
                          if hw_info["GPU_DETAILS"] else "None")
        detail = (
            f"hash:{hw_hash},arch:{hw_info['CPU_ARCH']},os:{hw_info['PLATFORM']},"
            f"bitness:{hw_info['OS_BITNESS']},core:{hw_info['CORE']},ram:{hw_info['RAM']},"
            f"gpu_count:{hw_info['GPU_COUNT']},gpu_total_vram:{hw_info['GPU_TOTAL_VRAM']},"
            f"gpus:{gpus_formatted},flags:{flags_str}"
        )
        cls.write_log(pc_id, "HARDWARE", "HW_NEW", detail=detail)
        return pc_id

    # CHAPTER 6: MODULE STATUS FROM LOG
    @classmethod
    def build_status_table(cls, pc_id: str) -> Dict:
        """Reconstructs { top_level_name: {status, retry_count} } from the log."""
        _EV_STATUS = {
            "SKIP_HW":          "HW_INCOMPATIBLE",
            "IMPORT_OK":        "OK",
            "INLINE_REPAIR_OK": "OK",
            "BANNED":           "BANNED",
            "RETRY_EXHAUSTED":  "RETRY_EXHAUSTED",
        }
        table: Dict = {}
        for e in cls.parse_log_lines():
            if e["pc_id"] != pc_id or e["module"] in ("-", ""):
                continue
            row = table.setdefault(e["module"], {"status": "UNKNOWN", "retry_count": 0})
            if e["event"] in _EV_STATUS:
                row["status"] = _EV_STATUS[e["event"]]
            elif e["event"] == "RETRY":
                row["status"]      = "RETRYING"
                row["retry_count"] = int(e["versuch"]) if e["versuch"].isdigit() else row["retry_count"] + 1
        return table

    # CHAPTER 7: PROACTIVE HARDWARE FILTER & CHECKS
    @staticmethod
    def split_patterns(patterns: Optional[List]) -> Tuple[List, List]:
        """Splits patterns into capability tags (proactive) and error texts (reactive)."""
        if not patterns:
            return [], []
        caps      = [p for p in patterns if str(p).upper() in CPU_CAPABILITY_TAGS]
        err_texts = [p for p in patterns if str(p).upper() not in CPU_CAPABILITY_TAGS]
        return caps, err_texts

    @staticmethod
    def check_capability_compatibility(cap_tags: List, cpu_flags: Set[str]) -> Tuple[bool, List]:
        """Prueft Faehigkeits-Tags gegen die tatsaechlich erkannten CPU_FLAGS."""
        missing = [t for t in cap_tags if str(t).upper() not in cpu_flags]
        return (not missing), missing

    # CHAPTER 8: REACTIVE ERROR ANALYSIS
    @staticmethod
    def is_known_error_pattern(err_msg: str, extra: Optional[List] = None) -> Optional[str]:
        """Returns the first matching error pattern or None."""
        for p in list(ERROR_PATTERNS) + [str(x) for x in (extra or [])]:
            if re.search(p, err_msg, re.IGNORECASE):
                return p
        return None

    @staticmethod
    def build_vcredist_hint(err_msg: str) -> Optional[str]:
        """Nur Hinweistext, KEIN Auto-Install."""
        if platform.system() == "Windows" and re.search(
            r"1114|DllMain returned false|vcruntime|msvcp", err_msg, re.IGNORECASE
        ):
            return f"Bitte installiere Microsoft Visual C++ Redistributable Version {VC_REDIST_HINT_VERSION}."
        return None

    # CHAPTER 9: STOCHASTIC PACKAGE RESOLUTION & VERIFICATION
    @staticmethod
    def _top_level_name(mod_name: str) -> str:
        """Status-Schluessel: IMMER der Top-Level-Import-Name."""
        return mod_name.split(".")[0]

    @staticmethod
    def _is_stdlib(mod_name: str) -> bool:
        """Prueft, ob mod_name Teil der Python-Standardbibliothek ist."""
        if hasattr(sys, "stdlib_module_names"):
            return mod_name in sys.stdlib_module_names
        stdlib_names = {
            "abc", "argparse", "ast", "asyncio", "base64", "builtins", "collections",
            "concurrent", "contextlib", "copy", "csv", "ctypes", "datetime", "decimal",
            "difflib", "dis", "email", "enum", "errno", "faulthandler", "fcntl",
            "fnmatch", "fractions", "functools", "gc", "getopt", "getpass", "glob",
            "gzip", "hashlib", "heapq", "hmac", "html", "http", "importlib", "inspect",
            "io", "ipaddress", "itertools", "json", "logging", "math", "mimetypes",
            "mmap", "multiprocessing", "numbers", "operator", "os", "pathlib", "pickle",
            "platform", "posixpath", "pprint", "queue", "random", "re", "select",
            "selectors", "shelve", "shlex", "shutil", "signal", "socket", "sqlite3",
            "ssl", "stat", "statistics", "string", "struct", "subprocess", "sys",
            "sysconfig", "tarfile", "tempfile", "textwrap", "threading", "time",
            "timeit", "traceback", "types", "typing", "unittest", "urllib", "uuid",
            "warnings", "weakref", "zipfile", "zipimport", "zlib"
        }
        return mod_name in stdlib_names

    @staticmethod
    def _is_importable(mod: str) -> bool:
        """Non-invasive probe: True if *mod* is already importable."""
        try:
            return importlib.util.find_spec(mod) is not None
        except (ModuleNotFoundError, ValueError, AttributeError):
            return False

    @classmethod
    def resolve_canonical_pip_name(cls, mod_name: str) -> List[str]:
        """
        Stochastically derives candidate pip package names for a requested module.
        Prioritizes known mappings (Ollama/LLM/AI ecosystem, data science tools),
        followed by heuristic variations and fallback naming conventions.
        """
        base = cls._top_level_name(mod_name)
        candidates: List[str] = []

        # 1. Canonical Ecosystem & Common Mappings
        known_map: Dict[str, List[str]] = {
            # Ollama, Hermes, OpenWebUI & LLM client variants
            "ollama": ["ollama"],
            "openwebui": ["open-webui", "openwebui"],
            "open_webui": ["open-webui", "openwebui"],
            "hermes": ["hermes-agent", "hermes", "nous-hermes"],
            "hermes_agent": ["hermes-agent", "hermes"],
            "llama_cpp": ["llama-cpp-python"],
            "huggingface_hub": ["huggingface_hub"],
            "litellm": ["litellm"],
            "transformers": ["transformers"],
            "datasets": ["datasets"],
            "accelerate": ["accelerate"],
            "sentence_transformers": ["sentence-transformers"],
            "langchain": ["langchain"],
            "langchain_core": ["langchain-core"],
            "langchain_community": ["langchain-community"],
            "vllm": ["vllm"],
            "chromadb": ["chromadb"],
            "duckdb": ["duckdb"],

            # Data Science / Core Tooling
            "yaml": ["pyyaml"],
            "PIL": ["pillow"],
            "pillow": ["pillow"],
            "cv2": ["opencv-python", "opencv-python-headless"],
            "sklearn": ["scikit-learn"],
            "IPython": ["ipython"],
            "ipywidgets": ["ipywidgets"],
            "psutil": ["psutil"],
            "requests": ["requests"],
            "tqdm": ["tqdm"],
            "dotenv": ["python-dotenv"],
            "fitz": ["pymupdf"],
            "bs4": ["beautifulsoup4"],
            "serial": ["pyserial"],
            "dateutil": ["python-dateutil"],
            "fastapi": ["fastapi"],
            "uvicorn": ["uvicorn"],
            "pydantic": ["pydantic"],
            "jwt": ["pyjwt"],
            "magic": ["python-magic", "python-magic-bin"],
            "mss": ["mss"],
            "playwright": ["playwright"],
            "sweetviz": ["sweetviz"],
            "pandasai": ["pandasai"],
        }

        if base in known_map:
            candidates.extend(known_map[base])
        elif base.lower() in known_map:
            candidates.extend(known_map[base.lower()])

        # 2. Heuristic derivation
        norm_base = base.lower()
        hyphenated = norm_base.replace("_", "-")

        for cand in [base, norm_base, hyphenated]:
            if cand not in candidates:
                candidates.append(cand)

        # 3. AI / Python ecosystem variants for unknown packages
        ecosystem_variants = [
            f"{hyphenated}-client",
            f"{hyphenated}-python",
            f"python-{hyphenated}",
            f"{hyphenated}-ai",
        ]
        for variant in ecosystem_variants:
            if variant not in candidates:
                candidates.append(variant)

        return candidates

    @staticmethod
    def get_platform_specific_pip_name(mod_name: str, default_pip: str, version_spec: Any = None) -> str:
        """Adapts pip name for platform specifics (e.g. tensorflow-macos)."""
        base = ("tensorflow-macos"
                if mod_name == "tensorflow" and platform.system() == "Darwin" and platform.machine() == "arm64"
                else (default_pip or mod_name))
        if version_spec:
            v = str(version_spec).strip()
            if not any(v.startswith(op) for op in ("==", "<", ">", "<=", ">=", "~=", "!=")):
                v = f"=={v}"
            return f"{base}{v}"
        return base

    # CHAPTER 10: DYNAMIC RUNTIME IMPORT INTERCEPTOR & SELF-HEALING ENGINE
    @classmethod
    def stochastic_self_heal(
        cls,
        requested_name: str,
        exc: Optional[Exception] = None,
        fromlist: Tuple = (),
        level: int = 0
    ) -> bool:
        """
        Autonomously intercepts missing package errors at runtime:
        1. Analyzes the required package name & sub-module context.
        2. Verifies presence in the local environment (bypasses if healthy).
        3. Stochastically derives candidates and installs via pip / DOWNLOAD_MANAGER.
        4. Executes a seamless retry loop and injects loaded symbols without manual intervention.
        """
        if cls._is_healing:
            return False

        cls._is_healing = True
        try:
            # Determine actual missing target symbol / module
            missing_name = None
            if isinstance(exc, ModuleNotFoundError) and getattr(exc, "name", None):
                missing_name = exc.name
            elif exc:
                err_str = str(exc)
                m = re.search(r"No module named\s+['\"]([^'\"]+)['\"]", err_str)
                if m:
                    missing_name = m.group(1)
                else:
                    m2 = re.search(r"cannot import name\s+['\"]([^'\"]+)['\"]\s+from\s+['\"]([^'\"]+)['\"]", err_str)
                    if m2:
                        missing_name = m2.group(2)

            if not missing_name:
                missing_name = requested_name

            if not missing_name:
                return False

            base_pkg = cls._top_level_name(missing_name)

            # Never attempt to pip install standard library modules
            if cls._is_stdlib(base_pkg):
                return False

            g = globals()
            pc_id = g.get("PC_ID") or "PC_SYSTEM"
            st = g.setdefault("STATUS_TABLE", {})
            row = st.setdefault(base_pkg, {"status": "UNKNOWN", "retry_count": 0})

            # Check if permanently banned or exhausted
            if row["status"] in ("BANNED", "RETRY_EXHAUSTED", "HW_INCOMPATIBLE"):
                return False

            dm = g.get("download_manager")
            if not dm:
                dm = cls.DOWNLOAD_MANAGER()
                g["download_manager"] = dm

            # If module is already importable without error, bypass install
            if cls._is_importable(missing_name) and exc is None:
                row["status"] = "OK"
                return True

            attempt = row["retry_count"] + 1
            if attempt > MAX_RETRIES:
                cls.write_log(pc_id, "INSTALL", "RETRY_EXHAUSTED", module=base_pkg, versuch=str(attempt))
                row["status"] = "RETRY_EXHAUSTED"
                return False

            row["retry_count"] = attempt
            candidates = cls.resolve_canonical_pip_name(base_pkg)

            installed_candidate = None
            for cand in candidates:
                pip_pkg = cls.get_platform_specific_pip_name(base_pkg, cand)
                cls.write_log(pc_id, "INSTALL", "INSTALL_TRY", module=base_pkg,
                              detail=f"stochastic_pip:{pip_pkg}", versuch=str(attempt))
                logging.info(f"[AUTO_IMPORT_LAZY_LOAD] Stochastic install attempt for '{base_pkg}' using '{pip_pkg}' (attempt {attempt})...")

                if dm.install_package_isolated(pip_pkg, base_pkg):
                    cls.write_log(pc_id, "INSTALL", "INSTALL_OK", module=base_pkg, detail=f"pip:{pip_pkg}")
                    installed_candidate = pip_pkg
                    break
                else:
                    cls.write_log(pc_id, "INSTALL", "INSTALL_FAIL", module=base_pkg,
                                  detail=f"pip:{pip_pkg}", versuch=str(attempt))

            if not installed_candidate:
                cls.write_log(pc_id, "INSTALL", "RETRY", module=base_pkg, versuch=str(attempt))
                row["status"] = "RETRYING"
                return False

            # Seamless Retry Loop: Invalidate caches and verify immediate import
            importlib.invalidate_caches()
            try:
                mod = importlib.import_module(missing_name)
                cls.write_log(pc_id, "IMPORT", "IMPORT_OK", module=base_pkg)
                row["status"] = "OK"
                if base_pkg not in g:
                    g[base_pkg] = sys.modules.get(base_pkg, mod)
                return True
            except Exception as post_err:
                post_err_str = str(post_err)
                matched = cls.is_known_error_pattern(post_err_str)
                if matched:
                    hint = cls.build_vcredist_hint(post_err_str)
                    detail = f"matched_pattern:{matched}, {post_err_str}" + (f" | HINWEIS: {hint}" if hint else "")
                    cls.write_log(pc_id, "INSTALL", "BANNED", module=base_pkg, detail=detail, versuch=str(attempt))
                    row["status"] = "BANNED"
                    return False

                # Inline force-reinstall repair cascade
                cls.write_log(pc_id, "REPAIR", "INLINE_REPAIR_TRY", module=base_pkg, versuch=str(attempt))
                if dm.install_package_isolated(installed_candidate, base_pkg, force_reinstall=True):
                    importlib.invalidate_caches()
                    try:
                        mod = importlib.import_module(missing_name)
                        cls.write_log(pc_id, "REPAIR", "INLINE_REPAIR_OK", module=base_pkg)
                        cls.write_log(pc_id, "IMPORT", "IMPORT_OK", module=base_pkg)
                        row["status"] = "OK"
                        if base_pkg not in g:
                            g[base_pkg] = sys.modules.get(base_pkg, mod)
                        return True
                    except Exception as final_err:
                        cls.write_log(pc_id, "REPAIR", "INLINE_REPAIR_FAIL", module=base_pkg,
                                      detail=str(final_err), versuch=str(attempt))
                else:
                    cls.write_log(pc_id, "REPAIR", "INLINE_REPAIR_FAIL", module=base_pkg, versuch=str(attempt))

                row["status"] = "BANNED"
                return False

        finally:
            cls._is_healing = False

    @classmethod
    def install_import_interceptor(cls) -> None:
        """
        Dynamically intercepts runtime import requests across the entire process.
        Catches ImportError or ModuleNotFoundError on the fly for ANY package,
        autonomously analyzes package names, checks local presence, installs via pip,
        and seamlessly retries the import so execution continues without manual intervention.
        """
        if cls._interceptor_installed:
            return

        cls._orig_builtin_import = builtins.__import__
        cls._orig_importlib_import = importlib.import_module

        def _builtin_interceptor(name, globals=None, locals=None, fromlist=(), level=0):
            try:
                return cls._orig_builtin_import(name, globals, locals, fromlist, level)
            except (ImportError, ModuleNotFoundError) as exc:
                if cls._is_healing:
                    raise
                if cls.stochastic_self_heal(name, exc=exc, fromlist=fromlist, level=level):
                    importlib.invalidate_caches()
                    return cls._orig_builtin_import(name, globals, locals, fromlist, level)
                raise

        def _importlib_interceptor(name, package=None):
            try:
                return cls._orig_importlib_import(name, package=package)
            except (ImportError, ModuleNotFoundError) as exc:
                if cls._is_healing:
                    raise
                if cls.stochastic_self_heal(name, exc=exc):
                    importlib.invalidate_caches()
                    return cls._orig_importlib_import(name, package=package)
                raise

        builtins.__import__ = _builtin_interceptor
        importlib.import_module = _importlib_interceptor
        cls._interceptor_installed = True
        logging.info("[AUTO_IMPORT_LAZY_LOAD] Dynamic Stochastic & Self-Healing Import Interceptor active.")

    @classmethod
    def uninstall_import_interceptor(cls) -> None:
        """Restores original Python import mechanisms."""
        if cls._interceptor_installed:
            if cls._orig_builtin_import:
                builtins.__import__ = cls._orig_builtin_import
            if cls._orig_importlib_import:
                importlib.import_module = cls._orig_importlib_import
            cls._interceptor_installed = False

    @classmethod
    def require(cls, *packages: str, inject_globals: bool = True) -> Dict[str, Any]:
        """
        Public programmatic API:
        Autonomously verifies, installs (if absent), and loads any package or packages on demand.
        """
        results: Dict[str, Any] = {}
        g = globals()
        for pkg in packages:
            mod_name = pkg.strip()
            if not mod_name:
                continue
            base = cls._top_level_name(mod_name)
            try:
                mod = importlib.import_module(mod_name)
            except (ImportError, ModuleNotFoundError) as exc:
                if cls.stochastic_self_heal(mod_name, exc=exc):
                    mod = importlib.import_module(mod_name)
                else:
                    raise
            results[base] = mod
            if inject_globals and base not in g:
                g[base] = sys.modules.get(base, mod)
        return results

    @classmethod
    def lazy_import(cls, mod_name: str, alias: Optional[str] = None, fromlist: Tuple = ()) -> Any:
        """Safely imports any module at runtime with stochastic self-healing."""
        res = cls.require(mod_name, inject_globals=False)
        mod = res.get(cls._top_level_name(mod_name))
        g = globals()
        key = alias or (mod_name.split(".")[0] if "." in mod_name else mod_name)
        g[key] = mod
        return mod

    @classmethod
    def _resolve_into_globals(cls, dotted: str, key: str) -> None:
        """Imports symbol at dotted path and stores it in globals() under key."""
        parts  = dotted.rsplit(".", 1)
        mod_p, attr = (parts[0], parts[1]) if len(parts) == 2 else (parts[0], None)
        try:
            mod = importlib.import_module(mod_p)
            obj = getattr(mod, attr) if attr else mod
            globals()[key] = obj
        except Exception as exc:
            logging.error(f"[AUTO_IMPORT_LAZY_LOAD] Cannot resolve {dotted!r} -> {key!r}: {exc}")

    @classmethod
    def _bootstrap_externals(cls) -> None:
        """
        Ensures foundational dependencies (psutil, tqdm, packaging) are present
        via the stochastic self-healing engine and resolves them into globals().
        """
        for probe, pip_name, mappings in _BOOTSTRAP_DEPS:
            if not cls._is_importable(probe):
                if pip_name:
                    logging.info(f"[AUTO_IMPORT_LAZY_LOAD] {probe} not found – installing {pip_name!r}...")
                    cls.stochastic_self_heal(probe)
            for dotted, key in mappings:
                cls._resolve_into_globals(dotted, key)

    @classmethod
    def process_library_pipeline(
        cls,
        import_list:  Optional[List[Tuple]] = None,
        from_list:    Optional[List[Tuple]] = None,
        pc_id:        Optional[str] = None,
        status_table: Optional[Dict] = None,
        download_mgr: Optional[Any] = None,
        cpu_flags:    Optional[Set[str]] = None,
    ) -> None:
        """
        Core pipeline processing.
        Maintains full compatibility with established structural flow while leveraging
        the stochastic & self-healing import engine.
        """
        g = globals()
        import_list = import_list if import_list is not None else DEFAULT_CORE_IMPORT
        from_list   = from_list   if from_list   is not None else DEFAULT_CORE_FROM
        pc_id       = pc_id or g.get("PC_ID") or cls.get_or_register_pc_id()
        status_table = status_table if status_table is not None else g.get("STATUS_TABLE") or cls.build_status_table(pc_id)
        download_mgr = download_mgr or g.get("download_manager") or cls.DOWNLOAD_MANAGER()
        cpu_flags   = cpu_flags if cpu_flags is not None else (g.get("_CPU_FLAGS") or set())

        def inject(mod, entry, is_from: bool) -> None:
            if is_from:
                targets = entry[1]
                alias   = entry[2] if len(entry) > 2 and entry[2] else None
                if isinstance(targets, list):
                    for t in targets: g[t] = getattr(mod, t, None)
                else:
                    g[alias if alias else targets] = getattr(mod, targets, None)
            else:
                mod_name = entry[0]
                alias    = entry[1] if len(entry) > 1 and entry[1] else None
                if alias:
                    g[alias] = mod
                elif "." in mod_name:
                    g[mod_name.split(".")[0]] = sys.modules.get(mod_name.split(".")[0], mod)
                else:
                    g[mod_name] = mod

        def process_entry(entry, is_from: bool) -> None:
            mod_name = entry[0]
            base_pkg = cls._top_level_name(mod_name)
            patterns = entry[5] if is_from and len(entry) > 5 else (entry[4] if not is_from and len(entry) > 4 else None)

            # Proactive hardware filtering
            cap_tags, err_texts = cls.split_patterns(patterns)
            if cap_tags:
                ok, missing = cls.check_capability_compatibility(cap_tags, cpu_flags)
                if not ok:
                    cls.write_log(pc_id, "FILTER", "SKIP_HW", module=base_pkg,
                                  detail=f"benoetigt:{';'.join(missing)}")
                    status_table.setdefault(base_pkg, {})["status"] = "HW_INCOMPATIBLE"
                    return

            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    mod = importlib.import_module(mod_name)
                if status_table.get(base_pkg, {}).get("status") != "OK":
                    cls.write_log(pc_id, "IMPORT", "IMPORT_OK", module=base_pkg)
                status_table.setdefault(base_pkg, {})["status"] = "OK"
                inject(mod, entry, is_from)
            except Exception as exc:
                if cls.stochastic_self_heal(mod_name, exc=exc):
                    mod = importlib.import_module(mod_name)
                    inject(mod, entry, is_from)

        for entry in import_list:
            process_entry(entry, is_from=False)
        for entry in from_list:
            process_entry(entry, is_from=True)

    # DOWNLOAD_MANAGER (inner class)
    class DOWNLOAD_MANAGER:
        """
        Unified pip installer with real-time tqdm progress bar.
        tqdm and packaging symbols are resolved from globals() after Step 4.
        Includes stochastic C++/Build failure recovery & Python 3.14+ ABI fallback matrix.
        """
        PIP_PROGRESS_PATTERN = re.compile(
            r"(?:Downloading\s+(?P<filename>\S+))?.*?"
            r"(?P<downloaded>[\d\.]+)\s*(?P<d_unit>[kMG]?B)\s*/\s*"
            r"(?P<total>[\d\.]+)\s*(?P<t_unit>[kMG]?B)",
            re.IGNORECASE,
        )

        def __init__(self, inactivity_timeout_sec: int = 90):
            self.inactivity_timeout_sec = inactivity_timeout_sec

        def _to_bytes(self, val_str: str, unit_str: str) -> int:
            try: val = float(val_str)
            except ValueError: return 0
            unit = unit_str.upper()
            if unit == "KB": return int(val * 1024)
            if unit == "MB": return int(val * 1024 * 1024)
            if unit == "GB": return int(val * 1024 * 1024 * 1024)
            return int(val)

        def _is_build_or_cpp_error(self, log_output: str) -> bool:
            """Erkennt typische C++-Compiler-, Wheel-Build- oder Header-Fehler."""
            patterns = [
                r"Failed building wheel for",
                r"Microsoft Visual C\+\+ 14\.\d+ or greater is required",
                r"error: command '.*' failed with exit status",
                r"fatal error C\d+:",
                r"error: [a-zA-Z0-9_\-]+: No such file or directory",
                r"ninja: build stopped: subcommand failed",
            ]
            return any(re.search(p, log_output, re.IGNORECASE) for p in patterns)

        def download_and_install_pkg(self, cmd: list) -> tuple[bool, str]:
            """
            Executes pip command in isolated subprocess, updates progress bar,
            enforces inactivity timeout. Returns (success, captured_logs).
            """
            _psutil = globals().get("psutil")
            import io
            buf = io.StringIO()
            pbar = None
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                )
            except Exception as exc:
                logging.error(f"[DOWN_PIP] Failed to spawn pip process: {exc}")
                return False, str(exc)

            last_read_ts = time.time()
            try:
                while True:
                    line = proc.stdout.readline()
                    if line:
                        last_read_ts = time.time()
                        buf.write(line)
                        pbar = self._process_line(line, pbar)
                    elif proc.poll() is not None:
                        break
                    else:
                        time.sleep(0.05)
                        if time.time() - last_read_ts > self.inactivity_timeout_sec:
                            logging.warning("[DOWN_PIP] Inactivity timeout reached! Terminating process tree...")
                            try:
                                if _psutil:
                                    parent = _psutil.Process(proc.pid)
                                    for child in parent.children(recursive=True):
                                        child.kill()
                                    parent.kill()
                                else:
                                    proc.kill()
                            except Exception:
                                proc.kill()
                            if pbar: pbar.close()
                            return False, buf.getvalue()
                ret = proc.wait()
                if pbar: pbar.close()
                return ret == 0, buf.getvalue()
            except Exception as exc:
                if pbar: pbar.close()
                return False, buf.getvalue()

        def _process_line(self, line: str, pbar):
            _tqdm = globals().get("tqdm")
            if not _tqdm:
                return pbar
            m = self.PIP_PROGRESS_PATTERN.search(line)
            if not m:
                return pbar
            d = m.groupdict()
            filename = d.get("filename") or "package"
            dl       = self._to_bytes(d["downloaded"], d["d_unit"])
            total    = self._to_bytes(d["total"],      d["t_unit"])
            if total > 0:
                if pbar is None or getattr(pbar, "filename", None) != filename:
                    if pbar: pbar.close()
                    pbar = _tqdm(
                        desc=f"  [download] {filename[:25]:<25}", total=total,
                        unit="B", unit_scale=True, unit_divisor=1024,
                        bar_format="{desc}: {percentage:3.0f}%|{bar:30}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
                        leave=True, file=sys.stdout,
                    )
                    pbar.filename = filename
                delta = dl - pbar.n
                if delta > 0: pbar.update(delta)
            return pbar

        def install_package_isolated(self, pip_pkg: str, mod_name: str, force_reinstall: bool = False) -> bool:
            """
            Version-checks before install; handles C++ build failures via stochastic fallback cascades.
            """
            import tempfile
            import urllib.request
            import zipfile
            _ver  = globals().get("version")
            _PNF  = globals().get("PackageNotFoundError")
            _Spec = globals().get("SpecifierSet")
            _Inv  = globals().get("InvalidSpecifier")
            m = re.match(r"^([a-zA-Z0-9_\-\.]+)\s*([<>=~!].*)?$", pip_pkg.strip())
            base, ver_con = (m.group(1), (m.group(2) or "").strip()) if m else (pip_pkg.strip(), "")
            if not force_reinstall and _ver and _PNF:
                try:
                    installed = _ver(base)
                    if ver_con and _Spec and _Inv:
                        try:
                            if installed in _Spec(ver_con): return True
                        except (_Inv,): pass
                    else:
                        return True
                except (_PNF,): pass
            if "llama" in base.lower():
                logging.info(f"[DOWN_PIP] Bereite Bootstrapping fuer {base} vor...")
                bootstrap_cmd = [
                    sys.executable, "-m", "pip", "install",
                    "typing-extensions", "numpy", "diskcache", "pydantic",
                    "--prefer-binary", "--only-binary=:all:"
                ]
                self.download_and_install_pkg(bootstrap_cmd)
            cmd = [sys.executable, "-m", "pip", "install", "--no-cache-dir"]
            if force_reinstall: cmd.extend(["--upgrade", "--force-reinstall"])
            if base in ("torch", "torchvision") and sys.platform == "win32":
                cmd.extend(["--index-url", "https://download.pytorch.org/whl/cpu"])
            cmd.append(pip_pkg)
            logging.info(f"[DOWN_PIP] Starte Installation von: {pip_pkg}")
            success, logs = self.download_and_install_pkg(cmd)
            if success:
                importlib.invalidate_caches()
                return True
            if self._is_build_or_cpp_error(logs) or "llama" in base.lower():
                logging.warning(f"[DOWN_PIP] Starte Binary-Fallback-Kaskade fuer '{pip_pkg}'...")
                cmd_b2a = [
                    sys.executable, "-m", "pip", "install", pip_pkg,
                    "--prefer-binary", "--only-binary=:all:", "--no-cache-dir",
                    "--extra-index-url", "https://abetlen.github.io/llama-cpp-python/wheels/cpu"
                ]
                success_b2a, _ = self.download_and_install_pkg(cmd_b2a)
                if success_b2a:
                    importlib.invalidate_caches()
                    return True
                py_ver = f"cp{sys.version_info.major}{sys.version_info.minor}"
                plat_tag = "win_amd64" if sys.platform == "win32" else "manylinux_2_28_x86_64"
                candidate_vers = [py_ver, "cp312", "cp311"]
                for c_ver in dict.fromkeys(candidate_vers):
                    wheel_url = f"https://github.com/abetlen/llama-cpp-python/releases/download/v0.2.90/llama_cpp_python-0.2.90-{c_ver}-{c_ver}-{plat_tag}.whl"
                    logging.warning(f"[DOWN_PIP] Versuche Download & Bypass fuer Wheel ({c_ver})...")
                    try:
                        with tempfile.TemporaryDirectory() as tmpdir:
                            raw_whl = os.path.join(tmpdir, "downloaded.whl")
                            patched_whl = os.path.join(tmpdir, "llama_cpp_python-0.2.90-py3-none-any.whl")
                            req = urllib.request.Request(wheel_url, headers={"User-Agent": "Mozilla/5.0"})
                            with urllib.request.urlopen(req) as resp, open(raw_whl, "wb") as f:
                                f.write(resp.read())
                            extract_dir = os.path.join(tmpdir, "extracted")
                            with zipfile.ZipFile(raw_whl, "r") as z_in:
                                z_in.extractall(extract_dir)
                            for root, _, files in os.walk(extract_dir):
                                for file in files:
                                    if file == "WHEEL":
                                        w_path = os.path.join(root, file)
                                        with open(w_path, "r", encoding="utf-8") as wf:
                                            lines = wf.readlines()
                                        lines = [l for l in lines if not l.startswith("Tag:")]
                                        lines.append("Tag: py3-none-any\n")
                                        with open(w_path, "w", encoding="utf-8") as wf:
                                            wf.writelines(lines)
                            with zipfile.ZipFile(patched_whl, "w", zipfile.ZIP_DEFLATED) as z_out:
                                for root, _, files in os.walk(extract_dir):
                                    for file in files:
                                        fp = os.path.join(root, file)
                                        z_out.write(fp, os.path.relpath(fp, extract_dir))
                            cmd_b2b = [sys.executable, "-m", "pip", "install", patched_whl,
                                       "--no-deps", "--force-reinstall"]
                            success_b2b, _ = self.download_and_install_pkg(cmd_b2b)
                            if success_b2b:
                                importlib.invalidate_caches()
                                logging.info(f"[DOWN_PIP] Erzielte erfolgreiche Installation via Wheel-Bypass ({c_ver})!")
                                return True
                    except Exception as err:
                        logging.warning(f"[DOWN_PIP] Download/Patch fehlgeschlagen fuer {c_ver}: {err}")
            logging.error(f"[DOWN_PIP] Installation endgueltig fehlgeschlagen: {pip_pkg}")
            return False

    # CHAPTER 11: OLLAMA SERVICE GUARD + HERMES AUTO DOWNLOADER
    class OLLAMA_SERVICE_GUARD:
        """
        Unified lazy-loading guard for Ollama service + Hermes Agent.
        """
        OLLAMA_HOST_BASE       = "http://127.0.0.1:11434"
        OLLAMA_IP              = '127.0.0.1'
        OLLAMA_PORT            = 11434
        SERVICE_TIMEOUT_SEC    = 1.5
        SERVICE_MAX_WAIT_SEC   = 30
        KILL_WAIT_SEC          = 3
        HERMES_PREFERRED       = "qwen3"
        HERMES_FALLBACK_MODEL  = "qwen3:8b"
        PULL_STREAM_TIMEOUT    = 3600
        WIN_INSTALLER_URL      = "https://ollama.com/download/OllamaSetup.exe"
        MAC_INSTALLER_URL      = "https://ollama.com/download/Ollama-darwin.zip"
        LINUX_INSTALL_CMD      = "curl -fsSL https://ollama.com/install.sh | sh"
        LINUX_FALLBACK_URLS    = {
            "amd64": "https://ollama.com/download/ollama-linux-amd64.tgz",
            "arm64": "https://ollama.com/download/ollama-linux-arm64.tgz",
        }
        _guard_active: bool = False

        @classmethod
        def _log(cls, msg: str, level: str = "info") -> None:
            _logger = globals().get("logger", logging.getLogger("AutoImporter"))
            fn = getattr(_logger, level, _logger.info)
            fn(f"[OLLAMA_GUARD] {msg}")

        @classmethod
        def _is_service_running(cls) -> bool:
            """True iff HTTP GET /api/tags responds within SERVICE_TIMEOUT_SEC."""
            import urllib.request as _urlr
            try:
                url = f"{cls.OLLAMA_HOST_BASE}/api/tags"
                req = _urlr.Request(url, headers={"User-Agent": "OllamaGuard/1.0"})
                with _urlr.urlopen(req, timeout=cls.SERVICE_TIMEOUT_SEC) as resp:
                    return resp.status == 200
            except Exception:
                return False

        @classmethod
        def _wait_for_service(cls) -> bool:
            """Polls _is_service_running() every second up to SERVICE_MAX_WAIT_SEC."""
            cls._log("Waiting for Ollama service to respond...")
            start = time.time()
            while time.time() - start < cls.SERVICE_MAX_WAIT_SEC:
                if cls._is_service_running():
                    cls._log(f"Service online after {time.time() - start:.1f}s.")
                    return True
                time.sleep(1.0)
            cls._log(f"Service did not start within {cls.SERVICE_MAX_WAIT_SEC}s.", "error")
            return False

        @classmethod
        def _resolve_ollama_binary(cls) -> Optional[str]:
            """Returns the absolute path to the ollama binary or None."""
            import shutil as _sh
            found = _sh.which("ollama")
            if found:
                return str(Path(found).resolve())
            sys_name = platform.system()
            candidates: List[Path] = []
            if sys_name == "Windows":
                lad = os.environ.get("LOCALAPPDATA", "")
                pf  = os.environ.get("ProgramFiles",  "")
                pf8 = os.environ.get("ProgramFiles(x86)", "")
                candidates += [
                    Path(lad) / "Programs" / "Ollama" / "ollama.exe",
                    Path(pf)  / "Ollama"   / "ollama.exe",
                    Path(pf8) / "Ollama"   / "ollama.exe",
                ]
            elif sys_name == "Darwin":
                candidates += [
                    Path("/Applications/Ollama.app/Contents/Resources/ollama"),
                    Path("/usr/local/bin/ollama"),
                    Path.home() / ".ollama" / "bin" / "ollama",
                ]
            elif sys_name == "Linux":
                candidates += [
                    Path("/usr/local/bin/ollama"),
                    Path("/usr/bin/ollama"),
                    Path.home() / ".ollama" / "bin" / "ollama",
                ]
            for p in candidates:
                if p.is_file():
                    return str(p.resolve())
            return None

        @classmethod
        def _install_ollama(cls) -> Optional[str]:
            """Downloads and runs the platform installer."""
            import tempfile, urllib.request as _urlr
            sys_name = platform.system()
            cls._log(f"Ollama binary not found. Starting auto-install for {sys_name}...")
            if sys_name == "Windows":
                try:
                    installer = Path(tempfile.gettempdir()) / "OllamaSetup.exe"
                    cls._log(f"Downloading Windows installer from {cls.WIN_INSTALLER_URL}...")
                    _urlr.urlretrieve(cls.WIN_INSTALLER_URL, str(installer))
                    cls._log("Running installer silently (/SILENT)...")
                    subprocess.run([str(installer), "/SILENT"], check=True)
                    time.sleep(3)
                    bin_path = cls._resolve_ollama_binary()
                    if bin_path:
                        cls._log(f"Installation successful: {bin_path}")
                        return bin_path
                except Exception as exc:
                    cls._log(f"Windows install failed: {exc}", "error")
            elif sys_name == "Darwin":
                try:
                    zip_path = Path(tempfile.gettempdir()) / "Ollama-darwin.zip"
                    _urlr.urlretrieve(cls.MAC_INSTALLER_URL, str(zip_path))
                    subprocess.run(["unzip", "-q", "-o", str(zip_path), "-d", "/Applications"], check=True)
                    bin_path = cls._resolve_ollama_binary()
                    if bin_path: return bin_path
                except Exception as exc:
                    cls._log(f"macOS install failed: {exc}", "error")
            elif sys_name == "Linux":
                try:
                    subprocess.run(cls.LINUX_INSTALL_CMD, shell=True, check=True)
                    bin_path = cls._resolve_ollama_binary()
                    if bin_path: return bin_path
                except Exception as exc:
                    cls._log(f"Linux install failed: {exc}", "error")
            cls._log("Auto-install failed. Please install Ollama manually: https://ollama.com", "error")
            return None

        @classmethod
        def _start_service(cls, binary_path: str) -> bool:
            """Starts 'ollama serve' as a detached background process."""
            _psutil = globals().get("psutil")
            cls._log("Checking for stale ollama processes...")
            if _psutil:
                for proc in _psutil.process_iter(["name", "pid"]):
                    try:
                        if "ollama" in (proc.info["name"] or "").lower():
                            cls._log(f"Killing stale process {proc.info['name']} (PID {proc.info['pid']})...")
                            proc.kill()
                    except Exception:
                        pass
                time.sleep(cls.KILL_WAIT_SEC)
            cls._log(f"Starting 'ollama serve' via: {binary_path}")
            flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            try:
                subprocess.Popen(
                    [binary_path, "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=flags,
                )
            except Exception as exc:
                cls._log(f"Failed to launch 'ollama serve': {exc}", "error")
                return False
            return cls._wait_for_service()

        @classmethod
        def _get_local_models(cls) -> List[str]:
            """Returns list of locally installed ollama model names via REST."""
            import json as _json, urllib.request as _urlr
            try:
                url = f"{cls.OLLAMA_HOST_BASE}/api/tags"
                with _urlr.urlopen(_urlr.Request(url), timeout=cls.SERVICE_TIMEOUT_SEC) as resp:
                    data = _json.loads(resp.read().decode("utf-8"))
                    return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
            except Exception:
                return []

        @classmethod
        def _resolve_hermes_model(cls, local_models: List[str]) -> str:
            """Resolves the best Hermes / Qwen model name."""
            import json as _json
            try:
                root = globals().get("PROJECT_ROOT")
                cfg = Path(root) / "config" / "active_model_config.json" if root else None
                if cfg and cfg.exists():
                    txt = cfg.read_text(encoding="utf-8")
                    txt = re.sub(r'("model_name":\s*"[^"]+")\s*\n\s*"', r'\1,\n"', txt)
                    name = _json.loads(txt).get("model_name", "").strip()
                    if name:
                        return name
            except Exception:
                pass
            if local_models:
                matched = [m for m in local_models if cls.HERMES_PREFERRED.lower() in m.lower()]
                if matched:
                    return matched[0]
                return local_models[0]
            return cls.HERMES_FALLBACK_MODEL

        @classmethod
        def _is_model_local(cls, model_name: str, local_models: List[str]) -> bool:
            """Checks whether model_name (or its base) is in local_models."""
            base = model_name.split(":")[0].lower()
            return any(
                n.lower() == model_name.lower() or n.lower().startswith(base + ":")
                for n in local_models
            )

        @classmethod
        def _pull_model(cls, model_name: str) -> bool:
            """Streaming pull via ollama.Client with live progress output."""
            cls._log(f"Pulling model: '{model_name}' ...")
            _Client = globals().get("Client")
            if _Client is None:
                try:
                    from ollama import Client as _Client
                except ImportError:
                    cls._log("ollama.Client unavailable – skipping pull.", "error")
                    return False
            try:
                client = _Client(
                    host=cls.OLLAMA_HOST_BASE,
                    timeout=cls.PULL_STREAM_TIMEOUT
                )
                current_digest = None
                for progress in client.pull(model=model_name, stream=True):
                    digest    = progress.get("digest", "")
                    completed = progress.get("completed")
                    total     = progress.get("total")
                    if digest and digest != current_digest:
                        print(f"  -> Layer [{digest[:12]}]")
                        current_digest = digest
                    if isinstance(total, int) and isinstance(completed, int) and total > 0:
                        pct = int(completed * 100 / total)
                        mb_c = completed / 1_048_576
                        mb_t = total / 1_048_576
                        sys.stdout.write(f"\r  Downloading: {pct:3d}% [{mb_c:6.1f} / {mb_t:6.1f} MB]")
                        sys.stdout.flush()
                print()
                cls._log(f"Pull complete: '{model_name}'.")
                return True
            except Exception as exc:
                cls._log(f"Pull error for '{model_name}': {exc}", "error")
                return False

        @classmethod
        def _launch_hermes(cls, model_name: str) -> None:
            """Associates Hermes with model_name via 'ollama launch hermes'."""
            try:
                cls._log(f"Associating Hermes agent with model '{model_name}'...")
                res = subprocess.run(
                    ["ollama", "launch", "hermes", "--model", model_name],
                    capture_output=True, text=True, timeout=10, check=False,
                )
                if res.returncode == 0:
                    cls._log("Hermes association verified.")
                else:
                    cls._log(f"'ollama launch hermes' exit code {res.returncode} (non-fatal): {res.stderr.strip()}", "warning")
            except Exception as exc:
                cls._log(f"Hermes launch skipped: {exc}", "warning")

        @classmethod
        def _collect_hardware(cls) -> dict:
            _psutil = globals().get("psutil")
            ram_gb  = round(_psutil.virtual_memory().total / 1024**3, 1) if _psutil else 0.0
            return {
                "total_ram":   ram_gb,
                "safe_budget": round(ram_gb * 0.70, 1),
                "cpu_count":   os.cpu_count() or 1,
            }

        @classmethod
        def ensure(cls, force: bool = False) -> bool:
            """
            Lazy-loading trigger – intercepts any Ollama / Hermes request.
            """
            if cls._guard_active and not force:
                return globals().get("OLLAMA_READY", False)
            g = globals()
            cls._log("=" * 60)
            cls._log("Lazy-load trigger: Ollama + Hermes Auto Downloader")
            cls._log("=" * 60)

            bin_path = cls._resolve_ollama_binary()
            if not bin_path:
                bin_path = cls._install_ollama()
            if bin_path:
                os.environ["PATH"] = str(Path(bin_path).parent) + os.pathsep + os.environ.get("PATH", "")
                cls._log(f"Ollama binary: {bin_path}")
            else:
                cls._log("Binary not found – Ollama unavailable.", "error")
                g["OLLAMA_READY"] = g["ollama_ready"] = False
                return False

            if cls._is_service_running():
                cls._log(f"Service already running on port {cls.OLLAMA_PORT}.")
            else:
                ok = cls._start_service(bin_path)
                if not ok:
                    cls._log("Service could not be started.", "error")
                    g["OLLAMA_READY"] = g["ollama_ready"] = False
                    return False

            local_models = cls._get_local_models()
            cls._log(f"Local models found: {local_models or '(none)'}")
            model_name = cls._resolve_hermes_model(local_models)

            if cls._is_model_local(model_name, local_models):
                cls._log(f"Model '{model_name}' present locally. [OK]")
            else:
                cls._log(f"Model '{model_name}' not found – pulling now...")
                ok = cls._pull_model(model_name)
                if ok:
                    local_models = cls._get_local_models()
                else:
                    cls._log(f"Pull failed. '{model_name}' may not be available.", "warning")

            cls._launch_hermes(model_name)

            try:
                cls._log("Installed models on this system:")
                subprocess.run(["ollama", "list"], check=False)
            except Exception: pass

            hw = cls._collect_hardware()

            g["OLLAMA_READY"]       = cls._is_service_running()
            g["ollama_ready"]       = g["OLLAMA_READY"]
            g["OLLAMA_BIN"]         = bin_path
            g["OLLAMA_HOST"]        = cls.OLLAMA_HOST_BASE
            g["HERMES_MODEL"]       = model_name
            g["LOCAL_MODELS"]       = local_models
            g["service_manager"]    = cls
            g["TOTAL_RAM_GB"]       = hw["total_ram"]
            g["SAFE_RAM_BUDGET_GB"] = hw["safe_budget"]
            g["CPU_COUNT"]          = hw["cpu_count"]
            if "HF_MODELS_DIR" not in g:
                root = g.get("PROJECT_ROOT")
                g["HF_MODELS_DIR"] = str(Path(root) / "data" / "models") if root else str(Path.cwd() / "data" / "models")
            cls._guard_active = True

            status = "[OK] READY" if g["OLLAMA_READY"] else "[!] NOT READY"
            cls._log(f"Ollama: {status} | Active model: {model_name}")
            cls._log("=" * 60)
            return g["OLLAMA_READY"]

    # CHAPTER 12: LAZY-LOAD TRIGGER (outer classmethod)
    @classmethod
    def ensure_ollama_and_hermes(cls, force: bool = False) -> bool:
        """Public trigger on AUTO_IMPORT_LAZY_LOAD."""
        return cls.OLLAMA_SERVICE_GUARD.ensure(force=force)

    # BOOTSTRAP – public entry point
    @classmethod
    def bootstrap(cls) -> None:
        """
        Runs the complete stochastic self-healing lazy-load pipeline and populates globals.

        Step 1 – Setup logging, directories, and target paths.
        Step 2 – Hardware profiling and PC_ID registration.
        Step 3 – Install Stochastic & Self-Healing Import Interceptor on Python runtime.
        Step 4 – Bootstrap foundational externals (psutil, tqdm, packaging).
        Step 5 – Dynamic baseline library pipeline.
        Step 6 – Ollama & Hermes lazy-load guard (service + model on demand).
        Step 7 – Readiness summary banner.
        """
        g = globals()
        logging.info("[AUTO_IMPORT_LAZY_LOAD] Step 1: stdlib & logging setup...")
        cls._setup_logging_and_paths()

        dm = cls.DOWNLOAD_MANAGER()
        g["download_manager"] = dm
        pc_id = cls.get_or_register_pc_id()
        g["PC_ID"] = pc_id
        cls.write_log(pc_id, "SESSION", "SESSION_START")
        hw_info = cls.get_hardware_information()
        g["_HW_INFO"], g["_CPU_FLAGS"] = hw_info, hw_info["CPU_FLAGS"]
        st = cls.build_status_table(pc_id)
        g["STATUS_TABLE"] = st

        # Step 3: Install dynamic import interceptor
        logging.info("[AUTO_IMPORT_LAZY_LOAD] Step 3: Activating Stochastic Self-Healing Interceptor...")
        cls.install_import_interceptor()

        # Step 4: Bootstrap externals
        logging.info("[AUTO_IMPORT_LAZY_LOAD] Step 4: Bootstrapping externals...")
        cls._bootstrap_externals()

        # Export public helper bindings into globals
        for name, fn in [
            ("write_log",                      cls.write_log),
            ("parse_log_lines",                cls.parse_log_lines),
            ("get_hardware_information",       cls.get_hardware_information),
            ("compute_hw_hash",                cls.compute_hw_hash),
            ("get_or_register_pc_id",          cls.get_or_register_pc_id),
            ("build_status_table",             cls.build_status_table),
            ("split_patterns",                 cls.split_patterns),
            ("check_capability_compatibility", cls.check_capability_compatibility),
            ("is_known_error_pattern",         cls.is_known_error_pattern),
            ("build_vcredist_hint",            cls.build_vcredist_hint),
            ("get_platform_specific_pip_name", cls.get_platform_specific_pip_name),
            ("get_project_root",               cls.get_project_root),
            ("ensure_ollama_and_hermes",       cls.ensure_ollama_and_hermes),
            ("require",                        cls.require),
            ("lazy_import",                    cls.lazy_import),
            ("stochastic_self_heal",           cls.stochastic_self_heal),
            ("install_import_interceptor",     cls.install_import_interceptor),
            ("uninstall_import_interceptor",   cls.uninstall_import_interceptor),
        ]:
            g[name] = fn

        _log = g.get("logger", logging.getLogger("AutoImporter"))
        _log.info("[AUTO_IMPORT_LAZY_LOAD] Step 5: Executing dynamic library pipeline...")
        cls.process_library_pipeline(
            import_list=DEFAULT_CORE_IMPORT, from_list=DEFAULT_CORE_FROM,
            pc_id=pc_id, status_table=st,
            download_mgr=dm, cpu_flags=hw_info["CPU_FLAGS"],
        )
        _log.info("[AUTO_IMPORT_LAZY_LOAD] Library pipeline complete.")

        # Step 6 – Activate Ollama / Hermes guard
        _log.info("[AUTO_IMPORT_LAZY_LOAD] Step 6: Activating Ollama/Hermes guard...")
        cls.ensure_ollama_and_hermes()

        # Step 7 – Readiness summary banner
        _log.info("[AUTO_IMPORT_LAZY_LOAD] Step 7: Readiness summary.")
        g2 = globals()
        _ready   = g2.get("OLLAMA_READY", False)
        _model   = g2.get("HERMES_MODEL", "n/a")
        _ram     = g2.get("TOTAL_RAM_GB", 0.0)
        _budget  = g2.get("SAFE_RAM_BUDGET_GB", 0.0)
        _cpu     = g2.get("CPU_COUNT", 0)
        _host    = g2.get("OLLAMA_HOST", cls.OLLAMA_SERVICE_GUARD.OLLAMA_HOST_BASE)
        _sym     = "[OK]" if _ready else "[!]"
        print()
        print("=" * 64)
        print(f"  AUTO_IMPORT_LAZY_LOAD - Stochastic & Self-Healing Active")
        print("=" * 64)
        print(f"  System    : {platform.system()} {platform.machine()} | {_cpu} cores | {_ram} GB RAM")
        print(f"  RAM budget: {_budget} GB (70 % safety cap)")
        print(f"  Ollama    : {_sym} {'READY' if _ready else 'NOT READY'} at {_host}")
        print(f"  Model     : {_model}")
        print(f"  PC_ID     : {pc_id}")
        print("=" * 64)
        print()
