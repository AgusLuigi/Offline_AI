import os
import json
import sys
import subprocess
import importlib
import re
import time
import socket
import tempfile
import shutil
import urllib.request
import platform

try:
    from src.Install.ollama_model_utils import sanitize_ollama_model_name, is_valid_ollama_model_name
except ImportError:
    try:
        from ollama_model_utils import sanitize_ollama_model_name, is_valid_ollama_model_name
    except ImportError:
        def sanitize_ollama_model_name(raw_name: str, default_fallback: str = "custom-model") -> str:
            if not raw_name or not isinstance(raw_name, str):
                return default_fallback
            clean = raw_name.strip().lower()
            clean = re.sub(r"[^a-z0-9._-:]+", "-", clean)
            clean = re.sub(r"[-._]{2,}", "-", clean).strip("-._")
            return clean or default_fallback

        def is_valid_ollama_model_name(name: str) -> bool:
            if not name or not isinstance(name, str):
                return False
            return bool(re.match(r"^(?:[a-z0-9]+(?:[._-][a-z0-9]+)*/)?([a-z0-9]+(?:[._-][a-z0-9]+)*)(?::([a-z0-9]+(?:[._-][a-z0-9]+)*))?$", name.strip()))


# Absicherung der Konsolenausgabe gegen Windows-Encoding-Fehler (cp1252)
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def get_project_root() -> str:
    """
    Ermittelt das Stammverzeichnis über den festen Anker 'Offline_AI'.
    Verhindert das Ausbrechen aus der Projektstruktur.
    """
    if "__file__" in globals():
        current_path = os.path.abspath(os.path.dirname(__file__))
    else:
        current_path = os.path.abspath(os.getcwd())
    
    path_parts = current_path.split(os.sep)
    if "Offline_AI" in path_parts:
        ki_index = path_parts.index("Offline_AI")
        if os.name == 'nt':
            root_path = path_parts[0] + os.sep + os.path.join(*path_parts[1:ki_index + 1])
        else:
            root_path = os.sep + os.path.join(*path_parts[:ki_index + 1])
        return os.path.abspath(root_path)

    while current_path != os.path.dirname(current_path):
        if os.path.basename(current_path) == "Offline_AI":
            return current_path
        current_path = os.path.dirname(current_path)
    return os.path.abspath(os.getcwd())

# ==============================================================================
# 1. INITIALISIERE CONFIG UND LOGGING ZUERST (Schutz vor Logikschwand)
# ==============================================================================
PROJECT_ROOT = get_project_root()
config_paths_json = os.path.join(PROJECT_ROOT, "config", "project_paths.json")

if not os.path.exists(config_paths_json):
    print(f"Fehler: '{config_paths_json}' fehlt. Bitte zuerst initialize_project.py ausführen.")
    sys.exit(1)

with open(config_paths_json, "r", encoding="utf-8") as f:
    PATHS = json.load(f)

# Zentrales Logging sauber initialisieren (Verhindert Duplikate im Notebook)
import logging
logger = logging.getLogger("HardwareOllamaDownloader")
logger.setLevel(logging.INFO)
logger.handlers.clear()  # Alte Handler entfernen vor Neu-Registrierung
logger.propagate = False

formatter = logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s')

file_handler = logging.FileHandler(os.path.join(PATHS["logs"], "app.log"), encoding="utf-8")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# ==============================================================================
# 2. SELBSTHEILUNGS-LOGIK (Python-Module)
# ==============================================================================
try:
    import psutil
    import ollama
    from ollama import Client  # Schutz vor Download-Abbrüchen durch Timeout-Steuerung
except ImportError as e:
    missing_module = str(e).split("'")[-2] if "'" in str(e) else str(e)
    logger.warning(f"Fehlende Abhängigkeit erkannt: Das Paket '{missing_module}' ist nicht bereit.")
    logger.info("Starte automatische Hintergrund-Installation via pip...")
    
    try:
        print(f"\n[AUTO-REPARATUR] Installiere fehlende Python-Module im Hintergrund...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "ollama", "psutil"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if result.returncode == 0:
            logger.info("Abhängigkeiten erfolgreich nachinstalliert. Erneuter Import-Versuch...")
            psutil = importlib.import_module('psutil')
            ollama = importlib.import_module('ollama')
            from ollama import Client
            print("[AUTO-REPARATUR] Module erfolgreich im RAM registriert.\n")
        else:
            logger.error(f"Pip-Installationsfehler (Returncode {result.returncode}): {result.stderr}")
            print(f"\n[FEHLER] Automatische Installation fehlgeschlagen.\nDetails: {result.stderr}")
            sys.exit(1)
            
    except Exception as install_error:
        logger.error(f"Kritischer Systemfehler bei der Paketreparatur: {install_error}", exc_info=True)
        sys.exit(1)

# ==============================================================================
# 3. PLATTFORMÜBERGREIFENDE OLLAMA-VERWALTUNG (Windows, macOS, Linux)
# ==============================================================================
def progress_bar(count, block_size, total_size):
    """Gibt einen Live-Ladebalken für Downloads aus."""
    if total_size <= 0:
        sys.stdout.write("\rLade herunter... (Größe wird ermittelt)")
        sys.stdout.flush()
        return

    downloaded = count * block_size
    percent = min(int(downloaded * 100 / total_size), 100)
    downloaded_mb = downloaded / (1024 * 1024)
    total_mb = total_size / (1024 * 1024)
    
    bar_length = 30
    filled_length = int(round(bar_length * percent / 100))
    bar = '=' * filled_length + '-' * (bar_length - filled_length)
    
    sys.stdout.write(f"\rFortschritt: [{bar}] {percent}% ({downloaded_mb:.1f} / {total_mb:.1f} MB)")
    sys.stdout.flush()

class BaseOllamaManager:
    """Basis-Manager für plattformunabhängige Ollama-Operationen."""
    def __init__(self, host: str = "127.0.0.1", port: int = 11434):
        self.host = host
        self.port = port
        self.system = platform.system()
        self.machine = platform.machine().lower()

    def log(self, message: str):
        logger.info(message)
        print(f"[Ollama] {message}")

    def log_warn(self, message: str):
        logger.warning(message)
        print(f"[WARNUNG] {message}")

    def log_error(self, message: str):
        logger.error(message)
        print(f"[FEHLER] {message}")

    def inject_to_path(self, dir_path: str):
        """Fügt ein Verzeichnis zur PATH-Umgebungsvariable hinzu, falls noch nicht vorhanden."""
        if not dir_path or not os.path.exists(dir_path):
            return
        abs_dir = os.path.abspath(dir_path)
        current_path = os.environ.get("PATH", "")
        if abs_dir.lower() not in current_path.lower():
            os.environ["PATH"] = abs_dir + os.pathsep + current_path

    def is_service_running(self, timeout: float = 1.5) -> bool:
        """Prüft, ob der Ollama-Dienst auf dem Host/Port antwortet."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                if s.connect_ex((self.host, self.port)) == 0:
                    try:
                        url = f"http://{self.host}:{self.port}/"
                        req = urllib.request.Request(url, method="GET")
                        with urllib.request.urlopen(req, timeout=timeout) as resp:
                            return resp.status in (200, 404)
                    except Exception:
                        return True
        except Exception:
            pass
        return False

    def download_file(self, url: str, target_path: str):
        """Lädt eine Datei mit Fortschrittsanzeige herunter."""
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Offline_AI Installer)"})
        with urllib.request.urlopen(req) as response, open(target_path, "wb") as out_file:
            total_length = response.headers.get("Content-Length")
            total_size = int(total_length) if total_length else 0
            count = 0
            block_size = 1024 * 1024  # 1 MB Blöcke
            
            while True:
                chunk = response.read(block_size)
                if not chunk:
                    break
                out_file.write(chunk)
                count += 1
                progress_bar(count, block_size, total_size)
        print()

    def resolve_path(self) -> str | None:
        raise NotImplementedError

    def install(self) -> str:
        raise NotImplementedError

    def start_service(self, max_wait_seconds: int = 25) -> bool:
        raise NotImplementedError

    def ensure_ready(self) -> str:
        """Stellt sicher, dass Ollama installiert ist und der Dienst läuft."""
        print("\n" + "=" * 60)
        print(f" [OLLAMA] SYSTEM- & DIENST-VERIFIKATION ({self.system})")
        print("=" * 60)
        
        bin_path = self.resolve_path()
        if not bin_path:
            bin_path = self.install()
        else:
            self.log(f"Installation verifiziert: {bin_path}")

        if self.is_service_running():
            self.log(f"Dienst ist aktiv und erreichbar (Port {self.port}).")
        else:
            self.start_service(max_wait_seconds=25)

        print("=" * 60 + "\n")
        return bin_path


class WindowsOllamaManager(BaseOllamaManager):
    """Spezifische Ollama-Verwaltung für Windows."""
    
    def resolve_path(self) -> str | None:
        # 1. PATH-Check
        for candidate in ["ollama.exe", "ollama"]:
            found = shutil.which(candidate)
            if found and os.path.exists(found):
                self.inject_to_path(os.path.dirname(found))
                return os.path.abspath(found)

        # 2. Umgebungsvariablen
        for env_var in ["OLLAMA_EXE", "OLLAMA_PATH", "OLLAMA_HOME"]:
            val = os.environ.get(env_var)
            if val and os.path.exists(val):
                if os.path.isdir(val):
                    sub = os.path.join(val, "ollama.exe")
                    if os.path.exists(sub):
                        self.inject_to_path(val)
                        return os.path.abspath(sub)
                self.inject_to_path(os.path.dirname(val))
                return os.path.abspath(val)

        # 3. Windows-Standardpfade
        home_dir = os.path.expanduser("~")
        local_appdata = os.environ.get("LOCALAPPDATA", os.path.join(home_dir, "AppData", "Local"))
        program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
        program_files_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")

        candidates = [
            os.path.join(local_appdata, "Programs", "Ollama", "ollama.exe"),
            os.path.join(local_appdata, "Programs", "Ollama", "ollama app.exe"),
            os.path.join(program_files, "Ollama", "ollama.exe"),
            os.path.join(program_files_x86, "Ollama", "ollama.exe"),
            os.path.join(home_dir, ".ollama", "ollama.exe"),
            "C:\\Ollama\\ollama.exe"
        ]

        for path in candidates:
            if os.path.exists(path):
                self.inject_to_path(os.path.dirname(path))
                return os.path.abspath(path)

        return None

    def install(self) -> str:
        self.log_warn("Ollama ist auf Windows nicht installiert. Starte automatische Installation...")
        temp_dir = tempfile.gettempdir()
        installer_url = "https://ollama.com/download/OllamaSetup.exe"
        installer_path = os.path.join(temp_dir, "OllamaSetup.exe")

        self.log(f"Lade Windows-Setup von '{installer_url}' herunter...")
        try:
            self.download_file(installer_url, installer_path)
            self.log("[OK] Download erfolgreich abgeschlossen.")
        except Exception as dl_err:
            self.log_error(f"Download fehlgeschlagen: {dl_err}")
            raise dl_err

        self.log("Führe Ollama-Setup aus (Silent-Modus)... Bitte kurz warten.")
        try:
            res = subprocess.run([installer_path, "/SP-", "/VERYSILENT", "/NORESTART"], check=False)
            if res.returncode != 0:
                self.log("Silent-Installation meldete Code != 0. Starte regulären Installer...")
                subprocess.Popen([installer_path], shell=True)
        except Exception as inst_err:
            self.log_warn(f"Standard-Ausführung: {inst_err}")
            try:
                os.startfile(installer_path)
            except Exception:
                subprocess.Popen([installer_path], shell=True)

        self.log("Warte auf Abschluss der Windows-Installation...")
        for _ in range(60):
            time.sleep(1)
            bin_path = self.resolve_path()
            if bin_path:
                self.log(f"[OK] Ollama erfolgreich auf Windows installiert: {bin_path}")
                return bin_path

        raise RuntimeError("Ollama-Installation auf Windows konnte nicht verifiziert werden.")

    def start_service(self, max_wait_seconds: int = 25) -> bool:
        if self.is_service_running():
            return True

        ollama_path = self.resolve_path() or self.install()
        self.log_warn("Ollama-Dienst nicht aktiv (WinError 10061 abgefangen). Starte Hintergrundprozess...")

        app_dir = os.path.dirname(ollama_path)
        app_exe = os.path.join(app_dir, "ollama app.exe")

        creationflags = 0
        if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP") and hasattr(subprocess, "DETACHED_PROCESS"):
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        elif hasattr(subprocess, "CREATE_NO_WINDOW"):
            creationflags = subprocess.CREATE_NO_WINDOW

        try:
            # 1. Primärer Start als entkoppelter Daemon
            subprocess.Popen(
                [ollama_path, "serve"],
                creationflags=creationflags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                close_fds=True
            )
            # 2. Desktop-App als Begleitprozess (falls vorhanden)
            if os.path.exists(app_exe):
                try:
                    subprocess.Popen([app_exe], creationflags=creationflags)
                except Exception:
                    pass
        except Exception as e:
            self.log_warn(f"Hintergrund-Start über subprocess: {e}")

        # Polling-Schleife
        self.log(f"Warte auf Initialisierung des Ollama-Servers auf http://{self.host}:{self.port}...")
        start_time = time.time()
        while time.time() - start_time < max_wait_seconds:
            time.sleep(1)
            if self.is_service_running():
                self.log("[OK] Ollama-Dienst erfolgreich verbunden und einsatzbereit!")
                return True

        self.log_warn(f"Ollama-Dienst hat nicht innerhalb von {max_wait_seconds}s geantwortet.")
        return False


class MacOSOllamaManager(BaseOllamaManager):
    """Spezifische Ollama-Verwaltung für macOS (Apple Silicon & Intel)."""

    def resolve_path(self) -> str | None:
        # 1. PATH-Check
        found = shutil.which("ollama")
        if found and os.path.exists(found):
            self.inject_to_path(os.path.dirname(found))
            return os.path.abspath(found)

        # 2. Umgebungsvariablen
        for env_var in ["OLLAMA_EXE", "OLLAMA_PATH", "OLLAMA_HOME"]:
            val = os.environ.get(env_var)
            if val and os.path.exists(val):
                sub = os.path.join(val, "ollama") if os.path.isdir(val) else val
                if os.path.exists(sub):
                    self.inject_to_path(os.path.dirname(sub))
                    return os.path.abspath(sub)

        # 3. macOS Standardpfade (App-Bundle, Homebrew, /usr/local)
        home_dir = os.path.expanduser("~")
        candidates = [
            "/Applications/Ollama.app/Contents/Resources/ollama",
            os.path.join(home_dir, "Applications", "Ollama.app", "Contents", "Resources", "ollama"),
            "/opt/homebrew/bin/ollama",
            "/usr/local/bin/ollama",
            os.path.join(home_dir, ".ollama", "bin", "ollama"),
            os.path.join(home_dir, ".local", "bin", "ollama")
        ]

        for path in candidates:
            if os.path.exists(path):
                self.inject_to_path(os.path.dirname(path))
                return os.path.abspath(path)

        return None

    def install(self) -> str:
        self.log_warn("Ollama ist auf macOS nicht installiert. Starte automatischen Download...")
        temp_dir = tempfile.gettempdir()
        installer_url = "https://ollama.com/download/Ollama-darwin.zip"
        zip_path = os.path.join(temp_dir, "Ollama-darwin.zip")

        self.log(f"Lade macOS Ollama-Bundle von '{installer_url}' herunter...")
        try:
            self.download_file(installer_url, zip_path)
            self.log("[OK] Download erfolgreich abgeschlossen.")
        except Exception as dl_err:
            self.log_error(f"macOS-Download fehlgeschlagen: {dl_err}")
            raise dl_err

        # Entpacken in /Applications oder Benutzer-Verzeichnis
        target_dest = "/Applications"
        if not os.access(target_dest, os.W_OK):
            target_dest = os.path.expanduser("~/Applications")
            os.makedirs(target_dest, exist_ok=True)

        self.log(f"Entpacke Ollama nach {target_dest}...")
        try:
            import zipfile
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(target_dest)
        except Exception:
            subprocess.run(["unzip", "-q", "-o", zip_path, "-d", target_dest], check=True)

        # Berechtigungen sicherstellen
        app_bin = os.path.join(target_dest, "Ollama.app", "Contents", "Resources", "ollama")
        if os.path.exists(app_bin):
            try:
                os.chmod(app_bin, 0o755)
            except Exception:
                pass

        bin_path = self.resolve_path()
        if bin_path:
            self.log(f"[OK] Ollama erfolgreich auf macOS bereitgestellt: {bin_path}")
            return bin_path

        raise RuntimeError("Ollama-Installation auf macOS konnte nicht abgeschlossen werden.")

    def start_service(self, max_wait_seconds: int = 25) -> bool:
        if self.is_service_running():
            return True

        ollama_path = self.resolve_path() or self.install()
        self.log_warn("Ollama-Dienst nicht aktiv. Starte macOS-Hintergrunddienst...")

        try:
            # 1. Versuche Start über macOS 'open'
            subprocess.Popen(["open", "-a", "Ollama"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

        try:
            # 2. Entkoppelter Start via POSIX Session
            subprocess.Popen(
                [ollama_path, "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True
            )
        except Exception as e:
            self.log_warn(f"Direkter Hintergrund-Start: {e}")

        # Polling-Schleife
        self.log(f"Warte auf Initialisierung des Ollama-Servers auf http://{self.host}:{self.port}...")
        start_time = time.time()
        while time.time() - start_time < max_wait_seconds:
            time.sleep(1)
            if self.is_service_running():
                self.log("[OK] Ollama-Dienst erfolgreich verbunden und einsatzbereit!")
                return True

        self.log_warn(f"Ollama-Dienst hat nicht innerhalb von {max_wait_seconds}s geantwortet.")
        return False


class LinuxOllamaManager(BaseOllamaManager):
    """Spezifische Ollama-Verwaltung für Linux (x86_64, ARM64, Container & Standalone)."""

    def resolve_path(self) -> str | None:
        # 1. PATH-Check
        found = shutil.which("ollama")
        if found and os.path.exists(found):
            self.inject_to_path(os.path.dirname(found))
            return os.path.abspath(found)

        # 2. Umgebungsvariablen
        for env_var in ["OLLAMA_EXE", "OLLAMA_PATH", "OLLAMA_HOME"]:
            val = os.environ.get(env_var)
            if val and os.path.exists(val):
                sub = os.path.join(val, "ollama") if os.path.isdir(val) else val
                if os.path.exists(sub):
                    self.inject_to_path(os.path.dirname(sub))
                    return os.path.abspath(sub)

        # 3. Linux Standardpfade
        home_dir = os.path.expanduser("~")
        candidates = [
            "/usr/local/bin/ollama",
            "/usr/bin/ollama",
            "/bin/ollama",
            os.path.join(home_dir, ".ollama", "bin", "ollama"),
            os.path.join(home_dir, ".local", "bin", "ollama"),
            os.path.join(home_dir, "bin", "ollama")
        ]

        for path in candidates:
            if os.path.exists(path):
                self.inject_to_path(os.path.dirname(path))
                return os.path.abspath(path)

        return None

    def install(self) -> str:
        self.log_warn("Ollama ist auf Linux nicht installiert. Starte automatische Installation...")
        
        # Methode 1: Offizielles Installations-Skript (falls sudo / root vorhanden)
        try:
            self.log("Versuche Installation über offizielles Ollama-Skript (curl | sh)...")
            res = subprocess.run("curl -fsSL https://ollama.com/install.sh | sh", shell=True, check=False)
            if res.returncode == 0:
                bin_path = self.resolve_path()
                if bin_path:
                    self.log(f"[OK] Ollama via Install-Script installiert: {bin_path}")
                    return bin_path
        except Exception as e:
            self.log_warn(f"Install-Script fehlgeschlagen: {e}")

        # Methode 2: Standalone User-Space Installation (ohne root / sudo)
        arch = "arm64" if "arm" in self.machine or "aarch64" in self.machine else "amd64"
        tar_url = f"https://ollama.com/download/ollama-linux-{arch}.tgz"
        temp_dir = tempfile.gettempdir()
        tar_path = os.path.join(temp_dir, f"ollama-linux-{arch}.tgz")
        user_ollama_dir = os.path.expanduser("~/.ollama")

        self.log(f"Lade eigenständiges Linux-Tarball ({arch}) von '{tar_url}' herunter...")
        try:
            import tarfile
            self.download_file(tar_url, tar_path)
            os.makedirs(user_ollama_dir, exist_ok=True)
            
            with tarfile.open(tar_path, "r:gz") as tar_ref:
                tar_ref.extractall(user_ollama_dir)
                
            bin_path = os.path.join(user_ollama_dir, "bin", "ollama")
            if os.path.exists(bin_path):
                os.chmod(bin_path, 0o755)
                self.inject_to_path(os.path.join(user_ollama_dir, "bin"))
                self.log(f"[OK] Ollama erfolgreich standalone in User-Space installiert: {bin_path}")
                return bin_path
        except Exception as err:
            self.log_error(f"User-Space Installation fehlgeschlagen: {err}")
            raise err

        bin_path = self.resolve_path()
        if bin_path:
            return bin_path

        raise RuntimeError("Ollama konnte auf Linux nicht automatisch installiert werden.")

    def start_service(self, max_wait_seconds: int = 25) -> bool:
        if self.is_service_running():
            return True

        ollama_path = self.resolve_path() or self.install()
        self.log_warn("Ollama-Dienst nicht aktiv. Starte Linux-Dienst...")

        # 1. Falls systemd vorhanden ist, versuche Service-Start
        try:
            subprocess.run(["systemctl", "start", "ollama"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1)
            if self.is_service_running():
                self.log("[OK] Ollama-Dienst via systemctl gestartet.")
                return True
        except Exception:
            pass

        # 2. Standalone Daemon mit start_new_session=True (funktioniert auch ohne root/systemd)
        try:
            env = os.environ.copy()
            env["OLLAMA_HOST"] = f"{self.host}:{self.port}"
            subprocess.Popen(
                [ollama_path, "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                env=env,
                start_new_session=True
            )
        except Exception as e:
            self.log_warn(f"Fehler beim Daemon-Start: {e}")

        # Polling-Schleife
        self.log(f"Warte auf Initialisierung des Ollama-Servers auf http://{self.host}:{self.port}...")
        start_time = time.time()
        while time.time() - start_time < max_wait_seconds:
            time.sleep(1)
            if self.is_service_running():
                self.log("[OK] Ollama-Dienst erfolgreich verbunden und einsatzbereit!")
                return True

        self.log_warn(f"Ollama-Dienst hat nicht innerhalb von {max_wait_seconds}s geantwortet.")
        return False


def get_ollama_manager(host: str = "127.0.0.1", port: int = 11434) -> BaseOllamaManager:
    """Factory-Funktion zur Bereitstellung des betriebssystemspezifischen Managers."""
    current_system = platform.system()
    if current_system == "Windows":
        return WindowsOllamaManager(host, port)
    elif current_system == "Darwin":
        return MacOSOllamaManager(host, port)
    else: # Linux / andere Unix
        return LinuxOllamaManager(host, port)


# ==============================================================================
# 4. GLOBALE SCHNITTSTELLEN-FUNKTIONEN (100% Backwards-Compatible)
# ==============================================================================
def resolve_ollama_path() -> str | None:
    return get_ollama_manager().resolve_path()

def install_ollama_if_missing() -> str:
    manager = get_ollama_manager()
    return manager.resolve_path() or manager.install()

def is_ollama_service_running(host: str = "127.0.0.1", port: int = 11434, timeout: float = 1.5) -> bool:
    return get_ollama_manager(host, port).is_service_running(timeout=timeout)

def start_ollama_service(ollama_path: str = None, host: str = "127.0.0.1", port: int = 11434, max_wait_seconds: int = 25) -> bool:
    return get_ollama_manager(host, port).start_service(max_wait_seconds=max_wait_seconds)

def ensure_ollama_ready():
    return get_ollama_manager().ensure_ready()

# ==============================================================================
# 4. LIVE-MODELLDATEN UND HARDWARE-ABGLEICH
# ==============================================================================
def fetch_online_model_library() -> list:
    """
    Lädt die tagesaktuelle, verifizierte Liste der Ollama-Modelle herunter.
    Sichert verschachtelte JSON-Objekte strukturell ab.
    """
    print("[INFO] Stelle Verbindung zum zentralen Open-Source-Repository her...")
    logger.info("Rufe aktuelle Modell-Bibliothek aus dem Internet ab...")
    
    url = "https://raw.githubusercontent.com/chrizzo84/OllamaScraper/refs/heads/main/out/ollama_models.json"
    
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            print("[INFO] Modell-Metadaten erfolgreich empfangen.")
            data = json.loads(response.read().decode("utf-8"))
            
            if isinstance(data, dict):
                for key in ["models", "library", "available_models"]:
                    if key in data and isinstance(data[key], list):
                        return data[key]
                return [data]
                
            return data if isinstance(data, list) else []
    except Exception as e:
        logger.warning(f"Online-Abruf fehlgeschlagen ({e}). Nutze integrierten Hardware-Sicherheits-Fallback.")
        print("[HINWEIS] Online-Bibliothek nicht erreichbar. Fallback-Modellmatrix geladen.")
        return [
            {"name": "gemma3:4b", "size_gb": 3.2, "description": "Gemma 3 Leichtgewicht"},
            {"name": "deepseek-r1:8b", "size_gb": 6.5, "description": "DeepSeek R1 Logik/Reasoning"},
            {"name": "qwen3:14b", "size_gb": 11.2, "description": "Qwen 3 Starker Allrounder"},
            {"name": "qwen3-coder:30b", "size_gb": 22.4, "description": "High-End Coding für Software-Architektur"},
            {"name": "qwen3:30b", "size_gb": 22.0, "description": "Königsklasse für logisches Denken / Jarvis"}
        ]

def analyze_system_and_select_model(models: list):
    """
    Prüft die tatsächliche Hardware-Leistung des Geräts und filtert 
    vollautomatisch das mathematisch stabilste Modell heraus.
    Bereinigt und validiert Modellnamen strikt nach Ollama-Konventionen
    (keine Großbuchstaben, keine Sonderzeichen), um HTTP 400 Fehler zu verhindern.
    """
    print("[INFO] Starte Hardware-Leistungs-Check...")
    total_ram_gb = round(psutil.virtual_memory().total / (1024**3), 2)
    safe_ram_budget = round(total_ram_gb * 0.70, 1)
    
    logger.info(f"Geräte-Leistungs-Check: {total_ram_gb} GB RAM erkannt.")
    logger.info(f"Berechnete maximale Obergrenze für Modellgröße: {safe_ram_budget} GB.")

    valid_models = []
    for m in models:
        if isinstance(m, str):
            raw_name = m.strip()
            size = None
            description = "Lokales LLM-Modell (Direkt-Link)"
        elif isinstance(m, dict):
            raw_name = str(m.get("name", "unbekannt")).strip()
            size = m.get("size_gb") or m.get("size", 0) / (1024**3) if isinstance(m.get("size"), (int, float)) else None
            description = m.get("description", m.get("blurb", "Lokales LLM-Modell"))
        else:
            continue
        
        name_lower = raw_name.lower()
        metadata_blacklist = [
            "scraped", "updated", "timestamp", "unbekannt", 
            "reference", "readme", "license", "manifest", "note"
        ]
        if any(indicator in name_lower for indicator in metadata_blacklist):
            continue

        # Bereinigung nach Ollama-Konventionen (lowercase, keine Sonderzeichen/Dateiendungen)
        sanitized_name = sanitize_ollama_model_name(raw_name)

        if not is_valid_ollama_model_name(sanitized_name):
            logger.warning(f"Modellname '{raw_name}' entspricht nicht den Ollama-Konventionen (Bereinigt: '{sanitized_name}'). Überspringe.")
            continue

        if not size:
            if "32b" in sanitized_name or "30b" in sanitized_name: size = 22.0
            elif "14b" in sanitized_name: size = 11.0
            elif "8b" in sanitized_name or "9b" in sanitized_name: size = 6.5
            elif "3b" in sanitized_name or "4b" in sanitized_name: size = 3.5
            else: size = 4.0
            
        if size <= safe_ram_budget:
            valid_models.append({
                "name": sanitized_name,
                "size_gb": round(size, 1),
                "desc": description
            })

    valid_models = sorted(valid_models, key=lambda x: x["size_gb"], reverse=True)
    return total_ram_gb, safe_ram_budget, valid_models

# ==============================================================================
# 5. DOWNLOAD AUSFÜHRUNG MIT AUTO-RETRY BEI VERBINDUNGSFEHLERN
# ==============================================================================
def smart_hardware_downloader():
    logger.info("=== Start der automatisisierten Ollama-Hardware-Analyse ===")
    
    # Vorabprüfung: Installation & Dienst-Status am Skriptanfang sicherstellen
    ensure_ollama_ready()
    
    raw_models = fetch_online_model_library()
    total_ram, safe_budget, fit_models = analyze_system_and_select_model(raw_models)
    
    if not fit_models:
        logger.error("Fehler: Kein gültiges Modell passt in die Hardware-Spezifikationen dieses Geräts.")
        print("[ABBRUCH] Hardware reicht für die verfügbaren Modelle nicht aus.")
        return

    perfect_match = fit_models[0]
    pull_model_name = sanitize_ollama_model_name(perfect_match['name'])
    
    print("\n" + "="*80)
    print(f" SYSTEM-ANALYSE REPRODUZIERT:")
    print(f" -> VERFÜGGBARER ARBEITSSPEICHER : {total_ram} GB RAM")
    print(f" -> MAXIMALES SCHUTZ-BUDGET     : {safe_budget} GB")
    print(f" -> GEWÄHLTES KI-OPTIMUM        : {pull_model_name} ({perfect_match['size_gb']} GB)")
    print("="*80)
    print(f" Einsatzbereich: {perfect_match['desc']}")
    print("="*80 + "\n")
    
    print(f"[AUTOMATION] Starte direkten Download für Core-Modell: '{pull_model_name}'")
    logger.info(f"Starte automatisisierten Download für: '{pull_model_name}'")

    # Verbindungsprüfung und Pull mit Auto-Recovery
    client = None
    try:
        client = Client(timeout=3600.0)
        client.list()
    except Exception as conn_err:
        logger.warning(f"Initialer Verbindungsversuch fehlgeschlagen ({conn_err}). Starte Dienst erneut...")
        start_ollama_service()
        client = Client(timeout=3600.0)

    try:
        current_digest = None
        for progress in client.pull(model=pull_model_name, stream=True):
            status = progress.get('status', '')
            completed = progress.get('completed')
            
            total = progress.get('total')
            digest = progress.get('digest', '')
            
            if digest != current_digest and digest:
                print(f"\nÜbertrage Daten-Layer [{digest[:12]}]...")
                current_digest = digest
                
            if isinstance(total, int) and isinstance(completed, int) and total > 0:
                percent = (completed / total) * 100
                sys.stdout.write(f"\rFortschritt: {percent:.2f}% ({completed // (1024**2)}MB / {total // (1024**2)}MB) | Status: {status}")
                sys.stdout.flush()
            else:
                sys.stdout.write(f"\rStatus: {status}")
                sys.stdout.flush()

        print("\n")
        logger.info(f"Erfolgreich! '{pull_model_name}' wurde hardwarekonform installiert.")
        
        active_config = os.path.join(PATHS["config"], "active_model_config.json")
        with open(active_config, "w", encoding="utf-8") as f:
            json.dump({
                "model_name": pull_model_name,
                "allocated_size_gb": perfect_match['size_gb'],
                "detected_ram_gb": total_ram
            }, f, indent=4, ensure_ascii=False)
            
        logger.info(f"Aktiver System-Status gesichert in: {active_config}")
        print("--- Prozess fehlerfrei beendet. Dein Jarvis-Kern steht! ---")

    except Exception as e:
        logger.error(f"Kritischer Fehler beim Pull-Vorgang: {e}", exc_info=True)
        print(f"\n[FEHLER] Verbindung zu Ollama abgebrochen. Details: {e}")
        print("Starte Reparatur des Hintergrundprozesses...")
        if start_ollama_service():
            print("Dienst wiederhergestellt. Bitte Zelle erneut ausführen.")
        sys.exit(1)

if __name__ == "__main__":
    smart_hardware_downloader()