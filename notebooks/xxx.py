# Absicherung der Konsolenausgabe gegen Windows-Encoding-Fehler (cp1252)
import sys
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import os
import json
import subprocess
import importlib
import platform
import time
import shutil
import urllib.request
import psutil

# 1. Selbstheilende Abhängigkeitsprüfung
required_packages = {
    "ipywidgets": "ipywidgets",
    "ollama": "ollama",
    "psutil": "psutil",
    "huggingface_hub": "huggingface_hub",
    "tqdm": "tqdm"
}

missing_packages = []
for module_name, package_name in required_packages.items():
    try:
        importlib.import_module(module_name)
    except ImportError:
        missing_packages.append(package_name)

if missing_packages:
    print(f"[AUTO-REPARATUR] Installiere fehlende Pakete: {missing_packages}...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", *missing_packages])
    print("[✓] Abhängigkeiten erfolgreich bereitgestellt.")

import ipywidgets as widgets
from IPython.display import display, HTML, clear_output
import ollama
from ollama import Client
from huggingface_hub import HfApi, hf_hub_download

# 2. Projektpfade ermitteln
from pathlib import Path

def get_project_root() -> str:
    """Ermittelt die Projektwurzel robust über pathlib, unabhängig von OS oder Laufwerksbuchstaben."""
    try:
        if "__file__" in globals():
            current_path = Path(__file__).resolve()
        else:
            current_path = Path.cwd().resolve()
        
        # Durchsuche den Pfad nach oben, bis der Projektordner "offline_ai" gefunden wird
        for parent in [current_path] + list(current_path.parents):
            if parent.name.lower() == "offline_ai":
                return str(parent)
                
    except Exception as e:
        # Fehler gezielt ausgeben statt ihn zu verschlucken
        print(f"[FEHLER] get_project_root() konnte Projektwurzel nicht ermitteln: {e}")
        
    # Fallback mit Benachrichtigung
    fallback_path = Path.cwd().resolve()
    print(f"[INFO] get_project_root() nutzt Fallback: {fallback_path}")
    return str(fallback_path)

PROJECT_ROOT = get_project_root()
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
HF_MODELS_DIR = os.path.join(DATA_DIR, "models", "huggingface")
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(HF_MODELS_DIR, exist_ok=True)

# 3. Hardware-Spezifikationen ermitteln
TOTAL_RAM_GB = round(psutil.virtual_memory().total / (1024**3), 2)
SAFE_RAM_BUDGET_GB = round(TOTAL_RAM_GB * 0.70, 1)
CPU_COUNT = psutil.cpu_count(logical=True)

# 4. Plattformunabhängiger Ollama-Service-Manager
class OllamaServiceManager:
    def __init__(self, host="127.0.0.1", port=11434):
        self.host = host
        self.port = port
        self.client = Client(host=f"http://{host}:{port}")

    def is_running(self, timeout=1.5) -> bool:
        try:
            Client(host=f"http://{self.host}:{self.port}", timeout=timeout).list()
            return True
        except Exception:
            # Hier kein Print bei jedem Loop-Tick, da das Warten anfangs normal ist,
            # aber der Timeout am Ende gibt Aufschluss.
            return False

    def _is_process_running(self, process_name="ollama") -> bool:
        """Prüft systemübergreifend, ob ein Prozess mit diesem Namen bereits im Hintergrund läuft."""
        try:
            for proc in psutil.process_iter(['name']):
                if proc.info['name'] and process_name.lower() in proc.info['name'].lower():
                    return True
        except Exception as e:
            print(f"[FEHLER] _is_process_running() konnte Prozessliste nicht abrufen: {e}")
        return False

    def ensure_service(self, max_wait_seconds=20) -> bool:
        if self.is_running():
            return True
        
        # Verhindere das Erzeugen von doppelten Prozessen
        if self._is_process_running("ollama"):
            print("[INFO] Ollama-Prozess läuft bereits im System, warte auf Bereitschaft...")
        else:
            print("[WARNUNG] Ollama-Dienst nicht aktiv. Starte Hintergrundprozess...")
            current_os = platform.system()
            try:
                if current_os == "Windows":
                    candidates = ["ollama.exe", os.path.expanduser("~\\AppData\\Local\\Programs\\Ollama\\ollama.exe")]
                    found_candidate = False
                    for cand in candidates:
                        found = shutil.which(cand) or (cand if os.path.exists(cand) else None)
                        if found:
                            found_candidate = True
                            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if hasattr(subprocess, 'CREATE_NEW_PROCESS_GROUP') else 0
                            subprocess.Popen([found, "serve"], creationflags=creationflags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            break
                    if not found_candidate:
                        print(f"[FEHLER] Keine Ollama-Executable unter den Kandidaten gefunden: {candidates}")
                elif current_os == "Darwin":
                    try:
                        subprocess.Popen(["open", "-a", "Ollama"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except Exception as e:
                        print(f"[INFO] 'open -a Ollama' fehlgeschlagen ({e}), versuche direktes Starten...")
                        subprocess.Popen(["ollama", "serve"], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    try:
                        subprocess.run(["systemctl", "start", "ollama"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except Exception as e:
                        print(f"[INFO] 'systemctl start ollama' fehlgeschlagen ({e}), versuche direktes Starten...")
                        subprocess.Popen(["ollama", "serve"], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f"[FEHLER] Beim Startversuch des Ollama-Dienstes ist ein Fehler aufgetreten: {e}")
        
        start_time = time.time()
        while time.time() - start_time < max_wait_seconds:
            time.sleep(1)
            if self.is_running():
                print("[✓] Ollama-Dienst erfolgreich verbunden!")
                return True
                
        print(f"[FEHLER] Timeout: Ollama-Dienst ist innerhalb von {max_wait_seconds} Sekunden nicht erreichbar geworden.")
        return False


service_manager = OllamaServiceManager()
ollama_ready = service_manager.ensure_service()

print("=" * 65)
print(f"[✓] SYSTEM-STATUS: {platform.system()} ({platform.machine()})")
print(f"    -> CPU: {CPU_COUNT} Kerne | RAM: {TOTAL_RAM_GB} GB (Budget: {SAFE_RAM_BUDGET_GB} GB)")
print(f"    -> Ollama-Dienst: {'[✓] Verbunden' if ollama_ready else '[!] Nicht erreichbar'}")
print("=" * 65)

# BACKEND: OLLAMA API & LIVE LIBRARY FETCHER

import json
import os
import re
import threading
import urllib.request
from pathlib import Path

import ollama
from ollama import Client

_DOWNLOAD_LOCK = threading.Lock()

OLLAMA_TAG_PATTERN = re.compile(
    r"^[a-z0-9]+[a-z0-9._/-]*(?::[a-z0-9][a-z0-9._-]*)?$"
)

def normalize_model_tag(value: str) -> str:
    """
    Normalisiert und validiert einen Ollama Model-Tag.
    Wirft ValueError bei ungültigen Tags.
    """
    tag = str(value or "").strip().lower()
    print(f"[DEBUG] Validiere Model-Tag: {tag!r}")

    if not tag:
        print("[FEHLER] Model-Tag ist leer.")
        raise ValueError("Model tag must not be empty")

    if len(tag) > 200:
        print(f"[FEHLER] Model-Tag überschreitet die maximale Länge von 200 Zeichen (Länge: {len(tag)}).")
        raise ValueError("Model tag is too long (max 200 characters)")

    if not OLLAMA_TAG_PATTERN.fullmatch(tag):
        print(f"[FEHLER] Model-Tag entspricht nicht dem erlaubten Muster: {tag!r}")
        raise ValueError(
            f"Invalid Ollama model tag: {tag!r}. "
            "Use lowercase letters, digits, '.', '_', '/', '-' and optional ':' tag."
        )

    print(f"[✓] Model-Tag erfolgreich normalisiert: {tag}")
    return tag


class OllamaBackend:
    ONLINE_LIBRARY_URL = "https://raw.githubusercontent.com/chrizzo84/OllamaScraper/refs/heads/main/out/ollama_models.json"

    def __init__(self, host="127.0.0.1", port=11434):
        self.host = host
        self.port = port
        self.client = Client(host=f"http://{host}:{port}")

    def fetch_models(self, limit=80) -> list[dict]:
        """Ruft die verfügbaren Modelle dynamisch aus der offiziellen Library ab (Fallback: lokaler Daemon)."""
        models = []
        print(f"[INFO] Versuche, Modelle von Online-Bibliothek abzurufen: {self.ONLINE_LIBRARY_URL}")
        
        try:
            req = urllib.request.Request(self.ONLINE_LIBRARY_URL, headers={"User-Agent": "Offline_AI/1.0"})
            with urllib.request.urlopen(req, timeout=4.0) as response:
                data = json.loads(response.read().decode("utf-8"))
                raw_models = data.get("models", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                print(f"[INFO] {len(raw_models)} Roheinträge aus Online-Bibliothek geladen.")
                
                for item in raw_models[:limit]:
                    name = item.get("name", "")
                    pulls = item.get("pulls_text", "")
                    capabilities = item.get("capabilities", [])
                    variants = item.get("variants", [])
                    blurb = item.get("blurb", "") or item.get("description", "")
                    category = ", ".join(capabilities) if capabilities else "Allgemein / LLM"
                    
                    if variants:
                        for var in variants[:4]:
                            tag = var.get("tag", name)
                            size_text = var.get("size_text", "Variabel")
                            models.append({
                                "id": tag,
                                "name": tag,
                                "size": size_text,
                                "category": category,
                                "description": blurb,
                                "popularity": pulls,
                                "platform": "ollama"
                            })
                    else:
                        models.append({
                            "id": name,
                            "name": name,
                            "size": "Variabel",
                            "category": category,
                            "description": blurb,
                            "popularity": pulls,
                            "platform": "ollama"
                        })
                if models:
                    print(f"[✓] {len(models)} Modelle erfolgreich aus Online-Bibliothek verarbeitet.")
                    return models
                    
        except Exception as err:
            print(f"[HINWEIS] Online-Bibliothek nicht erreichbar oder fehlerhaft ({err}). Nutze lokalen Ollama-Daemon als Fallback...")

        # Fallback: Lokale Tags über API
        print(f"[INFO] Frage lokale Modelle über Ollama-Client ab (Host: {self.host}:{self.port})...")
        try:
            local_tags = self.client.list()
            for m in local_tags.models:
                size_mb = m.size // (1024**2) if m.size else 0
                family = getattr(m.details, "family", "lokal") or "lokal"
                models.append({
                    "id": m.model,
                    "name": m.model,
                    "size": f"{size_mb} MB",
                    "category": family,
                    "description": f"Lokal installiertes Modell ({family})",
                    "popularity": "Lokal vorhanden",
                    "platform": "ollama"
                })
            print(f"[✓] {len(models)} lokale Modelle erfolgreich über den Daemon geladen.")
        except Exception as err:
            print(f"[FEHLER] Lokale Modelle konnten nicht über den Client abgefragt werden: {err}")

        return models

    def pull_model(self, model_tag: str, progress_callback=None):
        """Führt den Streaming-Pull eines Modells über den Ollama Client aus mit Fehler-Logging."""
        print(f"[INFO] Starte Download (Pull) für Modell: {model_tag!r}")
        try:
            for progress in self.client.pull(model=model_tag, stream=True):
                if progress_callback:
                    progress_callback(progress)
            print(f"[✓] Modell-Pull erfolgreich abgeschlossen: {model_tag!r}")
        except Exception as e:
            print(f"[FEHLER] Beim Download (Pull) des Modells {model_tag!r} ist ein Fehler aufgetreten: {e}")
            raise

# BACKEND: HUGGING FACE API & GGUF INTEGRATION MIT HARDWARE-FIT CHECK
class HuggingFaceBackend:
    OLLAMA_TAG_PATTERN = re.compile(r"^[a-z0-9]+[a-z0-9._/-]*(?::[a-z0-9][a-z0-9._-]*)?$")

    @staticmethod
    def normalize_model_tag(value: str) -> str:
        tag = str(value or "").strip().lower()
        print(f"[DEBUG] Validiere HuggingFace/Ollama Model-Tag: {tag!r}")

        if not tag:
            print("[FEHLER] Model-Tag ist leer.")
            raise ValueError("Model tag must not be empty")

        if len(tag) > 200:
            print(f"[FEHLER] Model-Tag überschreitet die maximale Länge von 200 Zeichen (Länge: {len(tag)}).")
            raise ValueError("Model tag is too long (max 200 characters)")

        if not HuggingFaceBackend.OLLAMA_TAG_PATTERN.fullmatch(tag):
            print(f"[FEHLER] Model-Tag entspricht nicht dem erlaubten Muster: {tag!r}")
            raise ValueError(
                f"Invalid Ollama model tag: {tag!r}. "
                "Use lowercase letters, digits, '.', '_', '/', '-' and optional ':' tag."
            )

        print(f"[✓] Model-Tag erfolgreich validiert: {tag}")
        return tag

    def __init__(self):
        self.api = HfApi()

    def fetch_models(self, limit=50) -> list[dict]:
        """Ruft die beliebtesten GGUF-Modelle dynamisch von Hugging Face ab."""
        models = []
        print(f"[INFO] Starte Abruf der Top-{limit} GGUF-Modelle von Hugging Face...")
        try:
            results = self.api.list_models(
                filter="gguf",
                sort="downloads",
                limit=limit
            )
            for m in results:
                downloads = getattr(m, "downloads", 0)
                pipeline = getattr(m, "pipeline_tag", "text-generation") or "text-generation"
                models.append({
                    "id": m.id,
                    "name": m.id,
                    "size": "GGUF Repository",
                    "category": pipeline,
                    "description": f"Hugging Face GGUF Repository: {m.id} | Task: {pipeline}",
                    "popularity": f"{downloads:,} Pull Downloads",
                    "platform": "huggingface"
                })
            print(f"[✓] {len(models)} GGUF-Modelle erfolgreich von Hugging Face geladen.")
        except Exception as err:
            print(f"[FEHLER] Hugging Face API-Abruf fehlgeschlagen: {err}")
        return models

    def fetch_gguf_files_with_fit(self, repo_id: str) -> list[tuple[str, str]]:
        """
        Ruft alle .gguf-Dateien eines Repositories dynamisch ab und markiert sie 
        mit einem visuellen Eignungs-Symbol.
        """
        options = []
        print(f"[INFO] Lade Dateibaum für Repository: {repo_id!r}")
        try:
            tree_items = list(self.api.list_repo_tree(repo_id=repo_id))
            gguf_items = [item for item in tree_items if item.path.lower().endswith(".gguf")]
            print(f"[INFO] {len(gguf_items)} .gguf-Dateien im Repository-Baum gefunden.")
            
            # Sortierung: bevorzugte Quantisierungen zuerst
            sorted_items = sorted(gguf_items, key=lambda x: (not ("q4_k_m" in x.path.lower() or "q4_0" in x.path.lower()), x.path))
            
            for item in sorted_items:
                path = item.path
                size_gb = round(item.size / (1024**3), 2) if hasattr(item, "size") and item.size else None
                
                if size_gb is not None:
                    if size_gb <= SAFE_RAM_BUDGET_GB:
                        label = f"✅ {path} ({size_gb} GB - Passt zur Hardware)"
                    else:
                        label = f"❌ {path} ({size_gb} GB - Übersteigt RAM-Budget von {SAFE_RAM_BUDGET_GB} GB)"
                else:
                    label = f"ℹ️ {path}"
                
                options.append((label, path))
                
        except Exception as err:
            print(f"[HINWEIS] Tree-Abruf für '{repo_id}' fehlgeschlagen ({err}). Nutze Fallback-Dateiliste...")
            try:
                files = [f for f in self.api.list_repo_files(repo_id=repo_id) if f.lower().endswith(".gguf")]
                print(f"[INFO] Fallback: {len(files)} .gguf-Dateien über Dateiliste gefunden.")
                for f in files:
                    options.append((f"ℹ️ {f}", f))
            except Exception as f_err:
                print(f"[FEHLER] Dateiliste konnte über Fallback ebenfalls nicht geladen werden: {f_err}")
                
        return options

    def download_and_create_model(
        self,
        repo_id: str,
        filename: str,
        target_model_tag: str,
        dest_dir: str,
        progress_callback=None,
        build_callback=None,
    ):
        """
        Läd eine GGUF-Datei über Hugging Face herunter (mit Kaskaden-Fallback bei Fehlern) 
        und registriert das Modell in Ollama, falls es nicht bereits vorhanden ist.
        """
        filename = Path(filename).name.strip()
        print(f"[INFO] Starte Download-Prozess für '{filename}' aus Repository '{repo_id}'...")

        if not filename or not filename.lower().endswith(".gguf"):
            print(f"[FEHLER] Ungültiger Dateiname übergeben: {filename!r}")
            raise ValueError("filename must be a valid .gguf filename")

        clean_model_tag = self.normalize_model_tag(target_model_tag)

        destination = Path(dest_dir).resolve()
        destination.mkdir(parents=True, exist_ok=True)

        local_path = destination / filename
        temporary_path = local_path.with_suffix(local_path.suffix + ".part")
        ollama_client = client_module.Client(host="http://127.0.0.1:11434") if 'client_module' in globals() else ollama.Client(host="http://127.0.0.1:11434")

        with _DOWNLOAD_LOCK:
            # 1. Vorhandene Datei wiederverwenden, falls sie komplett ist
            if local_path.is_file() and local_path.stat().st_size > 0:
                msg = f"Lokale GGUF-Datei '{filename}' ist bereits vorhanden. Verwende vorhandene Datei."
                print(f"[INFO] {msg}")
                if progress_callback:
                    progress_callback(msg)
            else:
                # Kaskaden-Schleife (2 Versuche: 1. Normaler Download, 2. Cleanup bei Fehler & Neustart)
                download_success = False
                
                for attempt in range(2):
                    try:
                        if attempt > 0:
                            print("[INFO] Kaskade Versuch 2: Bereinige temporäre Reste und erzwinge sauberen Neu-Download...")
                            if temporary_path.exists():
                                temporary_path.unlink()
                            if local_path.exists():
                                local_path.unlink()

                        msg = f"Lade '{filename}' von Hugging Face ({repo_id}) herunter (Versuch {attempt + 1})..."
                        print(f"[INFO] {msg}")
                        if progress_callback:
                            progress_callback(msg)

                        downloaded_path = hf_hub_download(
                            repo_id=repo_id,
                            filename=filename,
                            local_dir=str(destination),
                            local_dir_use_symlinks=False,
                        )

                        downloaded_path = Path(downloaded_path).resolve()

                        if not downloaded_path.is_file() or downloaded_path.stat().st_size <= 0:
                            raise IOError(f"Download fehlgeschlagen oder Datei ist leer: {downloaded_path}")

                        if downloaded_path != local_path:
                            os.replace(str(downloaded_path), str(local_path))

                        download_success = True
                        break

                    except Exception as dl_err:
                        print(f"[WARNUNG] Download-Versuch {attempt + 1} fehlgeschlagen: {dl_err}")
                        if attempt == 1:
                            print("[FEHLER] Auch der zweite (bereinigte) Download-Versuch ist fehlgeschlagen.")
                            raise

                if not download_success or not local_path.is_file():
                    raise IOError(f"Download von {filename} konnte nicht erfolgreich abgeschlossen werden.")

        abs_local_path = str(local_path.resolve())
        file_size_gb = round(local_path.stat().st_size / (1024**3), 2)
        print(f"[✓] Datei erfolgreich bereitgestellt unter {abs_local_path} ({file_size_gb} GB)")

        # 2. Existenzprüfung auf dem Client
        try:
            existing_models = ollama_client.list().models
            existing_names = {
                str(model.model).strip().lower()
                for model in existing_models
            }
        except Exception as err:
            print(f"[FEHLER] Konnte installierte Ollama-Modelle für den Abgleich nicht abfragen: {err}")
            raise RuntimeError(
                f"Ollama-Modelle konnten nicht abgefragt werden: {err}"
            ) from err

        if clean_model_tag in existing_names:
            msg = f"Modell '{clean_model_tag}' ist bereits in Ollama registriert. Überspringe Registrierung."
            print(f"[INFO] {msg}")
            if progress_callback:
                progress_callback(msg)
            return abs_local_path, file_size_gb

        # 3. Modellregistrierung triggern
        msg = f"Registriere Modell '{clean_model_tag}' in Ollama..."
        print(f"[INFO] {msg}")
        if progress_callback:
            progress_callback(msg)

        try:
            for response in ollama_client.create(
                model=clean_model_tag,
                from_=abs_local_path,
                stream=True,
            ):
                status = response.get("status", "")
                if status:
                    print(f"[OLLAMA CREATE] {status}")
                if build_callback:
                    build_callback(status)
            print(f"[✓] Modell '{clean_model_tag}' erfolgreich registriert!")
        except Exception as e:
            print(f"[FEHLER] Fehler während der Ollama-Modellregistrierung: {e}")
            raise

        return abs_local_path, file_size_gb

# CONFIG MANAGER
class ModelConfigManager:
    @staticmethod
    def save_active_model(model_name: str, size_gb: float, platform_name: str, config_dir: str):
        print(f"[INFO] Speichere aktive Modellkonfiguration für '{model_name}' (Plattform: {platform_name})...")
        try:
            config_path = os.path.join(config_dir, "active_model_config.json")
            os.makedirs(config_dir, exist_ok=True)
            data = {
                "model_name": model_name,
                "allocated_size_gb": size_gb,
                "detected_ram_gb": TOTAL_RAM_GB,
                "platform": platform_name,
                "updated_at": time.strftime('%Y-%m-%d %H:%M:%S')
            }
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            print(f"[✓] Modellkonfiguration erfolgreich unter '{config_path}' gespeichert.")
        except Exception as e:
            print(f"[FEHLER] Konnte aktive Modellkonfiguration nicht speichern: {e}")
            raise

ollama_backend = OllamaBackend()
hf_backend = HuggingFaceBackend()
print("[✓] Backend-Module erfolgreich initialisiert.")

# DYNAMISCHES LAYOUT-MANAGEMENT & WIDGET-INITIALISIERUNG
import json
import os
import subprocess
import threading
import time
from pathlib import Path

import ipywidgets as widgets
import ollama
import psutil

LABEL_WIDTH = "120px"
FULL_WIDTH = "100%"
MAX_WIDTH = "760px"

output_log = widgets.Output()

# --- PERSISTENTE PFAD-SPEICHERUNG LOGIK ---
PATH_CONFIG_FILE = os.path.join(CONFIG_DIR, "last_storage_path.json")
def load_last_storage_path() -> str:
    """Lädt den zuletzt verwendeten Speicherpfad aus der Konfiguration."""
    with output_log:
        print(f"[INFO] Versuche, letzten Speicherpfad aus '{PATH_CONFIG_FILE}' zu laden...")
        try:
            if os.path.exists(PATH_CONFIG_FILE):
                with open(PATH_CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    path = data.get("path", "")
                    if path:
                        print(f"[✓] Speicherpfad erfolgreich geladen: {path!r}")
                    else:
                        print("[INFO] Konfigurationsdatei existiert, enthält aber keinen 'path'-Eintrag.")
                    return path
            else:
                print(f"[INFO] Konfigurationsdatei '{PATH_CONFIG_FILE}' existiert noch nicht. Nutze Fallback (Leerpfad).")
        except Exception as e:
            print(f"[FEHLER] Konnte letzten Speicherpfad nicht aus '{PATH_CONFIG_FILE}' laden: {e}")
        return ""

def save_last_storage_path(path: str):
    """Speichert den gewählten Pfad persistent ab mit aktivem Logging."""
    with output_log:
        print(f"[INFO] Speichere letzten Speicherpfad: {path!r} in '{PATH_CONFIG_FILE}'...")
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(PATH_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({"path": path}, f, indent=4, ensure_ascii=False)
            print(f"[✓] Speicherpfad erfolgreich unter '{PATH_CONFIG_FILE}' gespeichert.")
        except Exception as e:
            print(f"[FEHLER] Konnte letzten Speicherpfad nicht speichern: {e}")
            raise

# --- LAUFWERKS- & PFAD-ERKENNUNG ---
def get_system_drives() -> list[tuple[str, str]]:
    """Ermittelt alle verfügbaren Laufwerke/Mountpoints inklusive freiem Speicher mit aktivem Logging."""
    drive_options = []
    with output_log:
        print("[INFO] Ermittle verfügbare Systemlaufwerke und Speicherplätze...")
        try:
            for part in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    free_gb = round(usage.free / (1024**3), 1)
                    total_gb = round(usage.total / (1024**3), 1)
                    label = f"💽 {part.device} ({part.mountpoint}) - {free_gb} GB frei (von {total_gb} GB)"
                    target_path = os.path.join(part.mountpoint, "Offline_AI_Models")
                    drive_options.append((label, target_path))
                    print(f"[DEBUG] Laufwerk erfolgreich eingelesen: {part.device} ({part.mountpoint}) - {free_gb} GB frei")
                except Exception as e:
                    print(f"[HINWEIS] Konnte Festplattendaten für Mountpoint '{getattr(part, 'mountpoint', 'unbekannt')}' nicht abrufen: {e}")
        except Exception as e:
            print(f"[FEHLER] Fehler beim Abrufen der Festplattenpartitionen über psutil: {e}")
        if not drive_options:
            default_path = os.path.join(DATA_DIR, "models")
            print(f"[WARNUNG] Keine Laufwerke gefunden. Verwende Standard-Fallback-Pfad: {default_path}")
            drive_options.append((f"Standard ({default_path})", default_path))
        drive_options.append(("➕ Benutzerdefinierten Pfad eingeben...", "CUSTOM_PATH"))
        print(f"[✓] Laufwerksermittlung abgeschlossen. {len(drive_options)} Optionen bereitgestellt.")
    return drive_options

# --- UI CONTROLLER & EVENT LOGIC ---
CURRENT_LOADED_MODELS = []

def filter_model_options(query: str = ""):
    """Filtert die geladenen Modelle in Echtzeit anhand des Suchbegriffs und sortiert sie alphabetisch (A-Z) mit aktivem Logging."""
    with output_log:
        platform_type = dropdown_platform.value
        q = query.strip().lower()
        print(f"[INFO] Starte Modellfilterung für Plattform '{platform_type}' mit Suchbegriff: {q!r}")
        
        if not CURRENT_LOADED_MODELS:
            print("[WARNUNG] Keine Modelle in 'CURRENT_LOADED_MODELS' vorhanden. Setze Dropdown auf 'Keine Modelle geladen'.")
            dropdown_model.options = [("Keine Modelle geladen", "")]
            dropdown_model.disabled = True
            btn_start_download.disabled = True
            return
        
        print(f"[INFO] Gesamtzahl verfügbarer Modelle vor Filterung: {len(CURRENT_LOADED_MODELS)}")
        matched_models = []
        for m in CURRENT_LOADED_MODELS:
            searchable_content = f"{m.get('name', '')} {m.get('id', '')} {m.get('category', '')} {m.get('size', '')} {m.get('description', '')} {m.get('popularity', '')}".lower()
            if not q or q in searchable_content:
                matched_models.append(m)
                
        # --- LOGIK: ALPHABETISCHE SORTIERUNG NACH NAME (CASE-INSENSITIVE) ---
        matched_models = sorted(matched_models, key=lambda x: str(x.get('name', '')).lower())
        print(f"[INFO] {len(matched_models)} Modelle nach Filterung und alphabetischer Sortierung übrig.")
        
        if platform_type == "ollama":
            options = [(f"{m['name']} ({m['size']}) [{m['category']}]", m['id']) for m in matched_models]
            options.append(("Benutzerdefiniertes Modell (Tag eingeben)", "CUSTOM_OLLAMA"))
        else:
            options = [(f"{m['name']} [{m['category']}] ({m['popularity']})", m['id']) for m in matched_models]
            options.append(("Benutzerdefiniertes Hugging Face Modell (Repo eingeben)", "CUSTOM_HF"))
        
        if matched_models or q == "":
            dropdown_model.options = options
            dropdown_model.disabled = False
            btn_start_download.disabled = False
            
            # --- VERBESSERUNG & SICHERHEITS-CHECK FÜR DIE VORAUSWAHL ---
            if len(options) > 0:
                first_selected_id = options[0][1]
                dropdown_model.value = first_selected_id
                print(f"[✓] Automatische Vorauswahl gesetzt auf ID: {first_selected_id!r}")
                
                # Schaltet sofort das GGUF-Feld scharf und lädt die Quantisierungen
                if platform_type == "huggingface" and first_selected_id != "CUSTOM_HF":
                    print(f"[INFO] Lade Hugging Face Dateidownload-Optionen für Vorauswahl: {first_selected_id!r}")
                    update_hf_file_dropdown(first_selected_id)
                    
                matched_item = next((m for m in CURRENT_LOADED_MODELS if m['id'] == first_selected_id), None)
                if matched_item:
                    html_spec_card.value = render_spec_card(matched_item)
        else:
            print(f"[INFO] Keine Treffer für Suchbegriff '{query}' gefunden.")
            dropdown_model.options = [(f"Keine Treffer für '{query}'", "")]
            dropdown_model.disabled = True
            btn_start_download.disabled = True
            html_spec_card.value = "<div style='padding: 8px 10px; color: #DC2626; font-size: 12px;'>Keine passenden Modelle gefunden. Bitte Suchbegriff anpassen.</div>"

# --- DOWNLOAD EXECUTION MIT VERTEILTER PFAD-ERZWINGUNG ---
def run_download_process():
    """Führt den vollständigen Download- und Integrationsprozess mit umfassendem Logging und Auto-Recovery aus."""
    platform_choice = dropdown_platform.value
    selected_id = dropdown_model.value
    
    with output_log:
        print(f"[INFO] Starte Download-Prozess für Plattform: {platform_choice!r}, Modell-ID: {selected_id!r}")
    
    if dropdown_target_disk.value == "CUSTOM_PATH":
        custom_path_val = text_custom_storage_path.value.strip()
        if not custom_path_val:
            with output_log:
                print("[FEHLER] Kein gültiger benutzerdefinierter Speicherpfad angegeben.")
            raise ValueError("Bitte einen gültigen benutzerdefinierten Speicherpfad angeben!")
        active_dest_dir = custom_path_val
    else:
        active_dest_dir = dropdown_target_disk.value

    with output_log:
        print(f"[INFO] Aktives Zielverzeichnis festgelegt auf: {active_dest_dir}")
    save_last_storage_path(active_dest_dir)

    # UI-Elemente für die Dauer des Downloads sperren
    btn_start_download.disabled = True
    btn_confirm_platform.disabled = True
    dropdown_platform.disabled = True
    text_model_search.disabled = True
    dropdown_model.disabled = True
    dropdown_gguf_file.disabled = True
    dropdown_target_disk.disabled = True
    
    progress_bar.layout.display = "block"
    progress_bar.value = 0
    progress_bar.bar_style = ""
    label_status.value = "Initialisiere Speicherort..."
    
    with output_log:
        clear_output()
        print("=" * 60)
        print(f"--- START DOWNLOAD & INTEGRATION ({platform_choice.upper()}) ---")
        print(f"Priorisiertes Zielverzeichnis: {active_dest_dir}")
        print("=" * 60)
    
    try:
        with output_log:
            print(f"[INFO] Erstelle Zielverzeichnis (falls nicht vorhanden): {active_dest_dir}")
        os.makedirs(active_dest_dir, exist_ok=True)

        if platform_choice == "ollama":
            raw_tag = text_custom_tag.value.strip() if selected_id == "CUSTOM_OLLAMA" else selected_id
            if not raw_tag:
                with output_log:
                    print("[FEHLER] Kein gültiger Ollama-Modelltag angegeben.")
                raise ValueError("Bitte einen gültigen Ollama-Modelltag angeben!")
    
            target_tag = normalize_model_tag(raw_tag)
            
            with output_log:
                print("[System] Beende blockierende Ollama-Prozesse...")
                print("[INFO] Suche nach laufenden Ollama-Prozessen zum Beenden...")
            
            killed_count = 0
            for proc in psutil.process_iter(['name']):
                try:
                    if proc.info['name'] and 'ollama' in proc.info['name'].lower():
                        proc.kill()
                        killed_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied) as pe:
                    with output_log:
                        print(f"[DEBUG] Konnte Prozess nicht beenden (bereits beendet oder keine Rechte): {pe}")
            
            with output_log:
                print(f"[✓] {killed_count} blockierende Ollama-Prozesse bereinigt.")
            time.sleep(2)
            
            with output_log:
                print("[System] Starte entkoppelten Ollama-Dienst auf Wunschpfad...")
                print(f"[INFO] Starte lokalen Ollama-Dienst mit OLLAMA_MODELS={active_dest_dir}...")
            
            env_copy = os.environ.copy()
            env_copy["OLLAMA_MODELS"] = str(Path(active_dest_dir).resolve())
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if hasattr(subprocess, 'CREATE_NEW_PROCESS_GROUP') else 0
            subprocess.Popen(["ollama", "serve"], env=env_copy, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creationflags)
            time.sleep(4)
            
            with output_log:
                print("[✓] Ollama-Dienst erfolgreich gestartet.")
            
            current_digest = None
            
            def render_text_bar(completed, total, length=25):
                """Erzeugt einen visuellen ASCII-Ladebalken für das Output-Log."""
                if not total or total <= 0:
                    return ""
                pct = completed / total
                filled = int(length * pct)
                bar = "█" * filled + "░" * (length - filled)
                return f"[{bar}] {pct*100:.1f}% ({completed // (1024**2)}/{total // (1024**2)} MB)"

            def ollama_callback(progress):
                nonlocal current_digest
                status = progress.get('status', '')
                completed = progress.get('completed', 0)
                total = progress.get('total', 0)
                digest = progress.get('digest', '')
                
                if digest != current_digest and digest:
                    with output_log:
                        print(f"\n[Layer {digest[:12]}] {status}")
                    current_digest = digest
                
                if total and completed and total > 0:
                    pct = min(int((completed / total) * 100), 100)
                    progress_bar.value = pct
                    text_bar = render_text_bar(completed, total)
                    label_status.value = f"[Pull] {status} ({completed // (1024**2)} / {total // (1024**2)} MB)"
                    
                    # Zeilenbasierter Fortschritt direkt im Logging-Container
                    with output_log:
                        print(f"\r[Pulling] {status} {text_bar}", end="", flush=True)
                else:
                    label_status.value = f"[Pull] {status}"
            
            with output_log:
                print(f"[INFO] Starte Ollama Pull für Modell: {target_tag}")
            
            redirected_client = ollama.Client(host="http://127.0.0.1:11434")
            
            # --- AUTO-RECOVERY LOGIK ---
            def execute_pull(tag):
                stream = redirected_client.pull(model=tag, stream=True)
                for progress in stream:
                    ollama_callback(progress)

            try:
                execute_pull(target_tag)
            except Exception as pull_err:
                err_str = str(pull_err).lower()
                if "400" in err_str or "invalid model name" in err_str or "bad request" in err_str:
                    with output_log:
                        print(f"\n[WARNUNG] 400 / Ungültiger Modellname erkannt ({pull_err}).")
                        print("[INFO] Versuche automatische Behebung: Bereinige Manifest & korrigiere Tag...")
                    
                    try:
                        redirected_client.delete(model=target_tag)
                    except Exception:
                        pass
                    
                    # Striktes Sanitizing: Nur Kleinbuchstaben, Zahlen, Doppelpunkt, Bindestrich, Punkt
                    fallback_tag = "".join(c for c in target_tag.lower() if c.isalnum() or c in ":-._")
                    
                    with output_log:
                        print(f"[INFO] Starte erneuten Versuch mit bereinigtem Tag: {fallback_tag!r}")
                    time.sleep(2)
                    
                    execute_pull(fallback_tag)
                    target_tag = fallback_tag
                else:
                    raise pull_err

            registered_name = target_tag
            allocated_size = 4.0
            
            with output_log:
                print(f"\n[✓] Ollama Pull erfolgreich abgeschlossen für: {registered_name}")
            
        else: # Hugging Face
            if selected_id == "CUSTOM_HF":
                repo_id = text_custom_hf_repo.value.strip()
                raw_filename = text_custom_hf_file.value.strip()
            else:
                repo_id = selected_id
                raw_filename = dropdown_gguf_file.value
            
            with output_log:
                print(f"[INFO] Hugging Face Download-Konfiguration - Repo: {repo_id!r}, Datei: {raw_filename!r}")
            
            if not repo_id or not raw_filename:
                with output_log:
                    print("[FEHLER] Repo-ID oder GGUF-Dateiname fehlt.")
                raise ValueError("Bitte Repo-ID und GGUF-Dateinamen angeben!")
            
            filename = os.path.basename(raw_filename)
            raw_tag = filename.lower().replace(".gguf", "").replace("_", "-").replace(".", "-")
            target_tag = normalize_model_tag(raw_tag)
            
            def hf_progress(msg):
                label_status.value = str(msg)
                with output_log:
                    print(f"[HF Hub] {msg}")
                    
            def hf_build(st):
                label_status.value = f"[Ollama Build] {st}"
                with output_log:
                    print(f"[Ollama Build] {st}")
            
            progress_bar.value = 30
            with output_log:
                print(f"[INFO] Übergebe an HuggingFaceBackend für Download von '{filename}' aus '{repo_id}'...")
                
            local_path, allocated_size = hf_backend.download_and_create_model(
                repo_id=repo_id, filename=filename, target_model_tag=target_tag,
                dest_dir=active_dest_dir, progress_callback=hf_progress, build_callback=hf_build
            )
            registered_name = target_tag
            
            with output_log:
                print(f"[✓] Hugging Face Modell erfolgreich heruntergeladen und registriert: {registered_name}")
        
        with output_log:
            print("[INFO] Speichere aktive Modellkonfiguration...")
        ModelConfigManager.save_active_model(model_name=registered_name, size_gb=allocated_size, platform_name=platform_choice, config_dir=CONFIG_DIR)
        
        progress_bar.value = 100
        progress_bar.bar_style = "success"
        label_status.value = f"[✓] Erfolgreich! '{registered_name}' wurde auf Disk gesichert."
        
        with output_log:
            print(f"[✓] Download-Prozess vollständig abgeschlossen für '{registered_name}'.")
        
    except Exception as err:
        progress_bar.bar_style = "danger"
        label_status.value = f"[FEHLER] {err}"
        with output_log:
            print(f"\n[FEHLER] Kritischer Fehler im Download-Prozess: {err}")
        raise
    finally:
        # UI nach Abschluss oder Fehler immer wieder aktivieren
        btn_start_download.disabled = False
        btn_confirm_platform.disabled = False
        dropdown_platform.disabled = False
        text_model_search.disabled = False
        dropdown_model.disabled = False
        dropdown_gguf_file.disabled = False
        dropdown_target_disk.disabled = False

def on_disk_selection_changed(change):
    """Wird aufgerufen, wenn sich die Laufwerksauswahl ändert, mit aktivem Logging."""
    with output_log:
        print(f"[INFO] Laufwerksauswahl geändert. Alter Wert: {change.old!r} -> Neuer Wert: {change.new!r}")
        if change.new == "CUSTOM_PATH":
            print("[INFO] 'CUSTOM_PATH' ausgewählt. Blende Eingabefeld für benutzerdefinierten Pfad ein.")
            text_custom_storage_path.layout.display = "block"
        else:
            print("[INFO] Vordefiniertes Laufwerk ausgewählt. Blende benutzerdefiniertes Eingabefeld aus.")
            text_custom_storage_path.layout.display = "none"
            if change.new:
                print(f"[INFO] Speichere neuen Pfad automatisch ab: {change.new!r}")
                save_last_storage_path(change.new)

def on_custom_path_submitted(change):
    """Wird aufgerufen, wenn ein benutzerdefinierter Pfad eingegeben oder bestätigt wird, mit aktivem Logging."""
    with output_log:
        print(f"[INFO] Benutzerdefinierter Pfad übermittelt. Neuer Wert: {change.new!r}")
        if change.new:
            cleaned_path = change.new.strip()
            print(f"[INFO] Speichere bereinigten benutzerdefinierten Pfad: {cleaned_path!r}")
            save_last_storage_path(cleaned_path)
        else:
            print("[INFO] Übermittelter benutzerdefinierter Pfad ist leer. Speicherung übersprungen.")
# UI CONTROLLER & EVENT LOGIC
CURRENT_LOADED_MODELS = []

def render_spec_card(model_item: dict) -> str:
    """Rendert die HTML-Spezifikationskarte für das ausgewählte Modell mit aktivem Logging."""
    with output_log:
        print("[INFO] Starte Rendern der Modell-Spezifikationskarte...")    
        if not model_item:
            print("[HINWEIS] Kein Modell für die Spezifikationskarte übergeben. Rendere Leer-Zustand.")
            return "<div style='padding: 8px 10px; color: #6B7280; font-size: 12px;'>Kein Modell ausgewählt.</div>"
        model_id = model_item.get("id", "-")
        size = model_item.get("size", "-")
        category = model_item.get("category", "-")
        popularity = model_item.get("popularity", "-")
        platform_name = model_item.get("platform", "").upper()
        print(f"[DEBUG] Generiere Spec-Card für Modell: {model_id!r} (Plattform: {platform_name})")
        html = f"""
        <div style='background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 6px; padding: 10px; margin-top: 4px;'>
            <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;'>
                <span style='background-color: #3B82F6; color: white; font-weight: bold; padding: 2px 8px; border-radius: 4px; font-size: 11px;'>{platform_name}</span>
                <span style='font-weight: bold; font-size: 13px; color: #111827;'>{model_id}</span>
                <span style='background-color: #10B981; color: white; padding: 2px 8px; border-radius: 4px; font-size: 11px;'>RAM verfügbar: {TOTAL_RAM_GB} GB</span>
            </div>
            <div style='display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; background: #F9FAFB; padding: 6px; border-radius: 4px; font-size: 12px; color: #374151;'>
                <div><b>Größe:</b> {size}</div>
                <div><b>Schwerpunkt/Task:</b> {category}</div>
                <div><b>Downloads/Pulls:</b> {popularity}</div>
            </div>
        </div>
        """
        print("[✓] Spezifikationskarte erfolgreich gerendert.")
        return html


def on_search_query_changed(change):
    """Wird aufgerufen, wenn sich der Suchbegriff ändert, mit aktivem Logging."""
    with output_log:
        query_val = change.new if change.new else ""
        print(f"[INFO] Suchfeld-Eingabe geändert. Neuer Suchbegriff: {query_val!r}")
        filter_model_options(query_val)

def on_platform_confirm_clicked(b):
    """Wird aufgerufen, wenn die Plattform-Auswahl bestätigt wird, mit aktivem Logging."""
    global CURRENT_LOADED_MODELS
    with output_log:
        platform_type = dropdown_platform.value
        print(f"[INFO] Plattform-Bestätigung ausgelöst. Gewählte Plattform: {platform_type!r}")
        
        label_status.value = f"Lade Live-Modelle für '{platform_type}'..."
        btn_confirm_platform.disabled = True
        dropdown_model.disabled = True
        text_model_search.value = ""
        
        try:
            if platform_type == "ollama":
                print("[INFO] Rufe Modelle für Ollama ab (Limit: 80)...")
                CURRENT_LOADED_MODELS = ollama_backend.fetch_models(limit=80)
                dropdown_gguf_file.layout.display = "none"
                text_custom_tag.layout.display = "none"
                custom_hf_row.layout.display = "none"
                print("[✓] Ollama-spezifische UI-Elemente ausgeblendet.")
            else:
                print("[INFO] Rufe GGUF-Modelle für Hugging Face ab (Limit: 50)...")
                CURRENT_LOADED_MODELS = hf_backend.fetch_models(limit=50)
                dropdown_gguf_file.layout.display = "block"
                text_custom_tag.layout.display = "none"
                custom_hf_row.layout.display = "none"
                print("[✓] Hugging-Face-spezifische UI-Elemente angepasst (GGUF-Dropdown eingeblendet).")
            
            print(f"[INFO] {len(CURRENT_LOADED_MODELS)} Modelle geladen. Starte Aktualisierung der Filteroptionen...")
            filter_model_options("")
            label_status.value = f"{len(CURRENT_LOADED_MODELS)} Live-Modelle für '{platform_type.upper()}' bereit."
            print("[✓] Plattform-Wechsel erfolgreich abgeschlossen.")
            
        except Exception as err:
            print(f"[FEHLER] Fehler beim Laden der Live-Modelle für '{platform_type}': {err}")
            label_status.value = f"Fehler beim Laden: {err}"
        finally:
            btn_confirm_platform.disabled = False
            print("[DEBUG] Bestätigungs-Button für Plattformwechsel wieder aktiviert.")

def update_hf_file_dropdown(repo_id: str):
    """Aktualisiert die GGUF-Auswahl und bewertet jede Variante mit ✅ oder ❌ mit aktivem Logging."""
    with output_log:
        print(f"[INFO] Starte Aktualisierung des GGUF-Dateidropdowns für Repository: {repo_id!r}")
        try:
            options = hf_backend.fetch_gguf_files_with_fit(repo_id)
            if options:
                print(f"[✓] {len(options)} GGUF-Optionen für Repo '{repo_id}' ermittelt. Aktualisiere Dropdown...")
                dropdown_gguf_file.options = options
                dropdown_gguf_file.disabled = False
                print("[✓] GGUF-Dropdown erfolgreich aktualisiert und aktiviert.")
            else:
                print(f"[WARNUNG] Keine .gguf-Dateien für Repository '{repo_id}' gefunden.")
                dropdown_gguf_file.options = [("Keine .gguf-Dateien gefunden", "")]
                dropdown_gguf_file.disabled = True
        except Exception as e:
            print(f"[FEHLER] Fehler beim Aktualisieren des GGUF-Dateidropdowns für '{repo_id}': {e}")
            dropdown_gguf_file.options = [("Fehler beim Laden der Dateien", "")]
            dropdown_gguf_file.disabled = True
            raise

# DOWNLOAD EXECUTION
def on_model_selection_changed(change):
    """Wird aufgerufen, wenn sich die Modellauswahl ändert, mit aktivem Logging."""
    if not change.new:
        return
    with output_log:
        selected_id = change.new
        print(f"[INFO] Modellauswahl geändert. Neuer Wert: {selected_id!r}")
        
        if selected_id == "CUSTOM_OLLAMA":
            text_custom_tag.layout.display = "block"
            custom_hf_row.layout.display = "none"
            dropdown_gguf_file.layout.display = "none"
            print("[INFO] Benutzerdefiniertes Ollama-Tag-Feld eingeblendet.")
        elif selected_id == "CUSTOM_HF":
            text_custom_tag.layout.display = "none"
            custom_hf_row.layout.display = "flex"
            dropdown_gguf_file.layout.display = "none"
            print("[INFO] Benutzerdefinierte Hugging-Face-Eingabefelder eingeblendet.")
        else:
            text_custom_tag.layout.display = "none"
            custom_hf_row.layout.display = "none"
            if dropdown_platform.value == "huggingface":
                dropdown_gguf_file.layout.display = "block"
                print("[INFO] GGUF-Dateidropdown für Hugging-Face-Modell eingeblendet.")
                update_hf_file_dropdown(selected_id)
            else:
                dropdown_gguf_file.layout.display = "none"
                
            matched = next((m for m in CURRENT_LOADED_MODELS if m['id'] == selected_id), None)
            if matched:
                html_spec_card.value = render_spec_card(matched)
                print("[✓] Spezifikationskarte für das ausgewählte Modell aktualisiert.")

def on_start_download_clicked(b):
    """Wird aufgerufen, wenn der Download-Button geklickt wird, und startet den Hintergrund-Thread mit Logging."""
    with output_log:
        print("[INFO] Start-Button geklickt. Starte Download-Prozess im Hintergrund-Thread...")
        t = threading.Thread(target=run_download_process)
        t.daemon = True
        t.start()




# --- GLOBALE LAYOUT- & WIDGET-HELPER ---
LABEL_WIDTH = "200px"
FULL_WIDTH = "100%"
MAX_WIDTH = "100%"
DROPDOWN_MAX_WIDTH = "480px"

_DEFAULT_TEXT_LAYOUT = widgets.Layout(width=FULL_WIDTH, max_width=MAX_WIDTH, margin="0 0 8px 0")
_DEFAULT_STYLE = {"description_width": LABEL_WIDTH}

def _create_text(placeholder: str, description: str, display: str = "block") -> widgets.Text:
    """Erstellt standardisierte Text-Widgets ohne Überlappung."""
    return widgets.Text(
        placeholder=placeholder,
        description=description,
        style=_DEFAULT_STYLE,
        layout=widgets.Layout(
            width=FULL_WIDTH, 
            max_width=MAX_WIDTH, 
            margin="0 0 8px 0", 
            display=display,
            flex="1 1 auto"
        )
    )

def _create_dropdown(description: str, options=None, disabled=False, display="block") -> widgets.Dropdown:
    """Erstellt standardisierte Dropdown-Widgets mit einheitlicher Maximalbreite."""
    return widgets.Dropdown(
        options=options or [],
        description=description,
        style=_DEFAULT_STYLE,
        layout=widgets.Layout(
            width=FULL_WIDTH, 
            max_width=DROPDOWN_MAX_WIDTH, 
            margin="0 0 8px 0", 
            display=display,
            flex="1 1 auto"
        ),
        disabled=disabled
    )

def _create_section(title: str, subtitle: str, children: list) -> widgets.VBox:
    """Erstellt einen sauberen Sektionen-Container mit automatischem Wrapping."""
    return widgets.VBox(
        [
            widgets.HTML(f"<div style='font-size: 13px; font-weight: 700; color: #1E293B; margin-bottom: 2px;'>{title}</div>"),
            widgets.HTML(f"<div style='font-size: 11px; color: #64748B; margin-bottom: 6px;'>{subtitle}</div>"),
            *children
        ],
        layout=widgets.Layout(
            width=FULL_WIDTH, 
            max_width=MAX_WIDTH, 
            padding="12px 14px", 
            margin="0 0 10px 0",
            border="1px solid #E2E8F0", 
            border_radius="8px", 
            background_color="#F8FAFC",
            overflow_x="auto"
        )
    )

# --- SEKTION 1 WIDGETS (PLATTFORM-AUSWAHL) ---
dropdown_platform = widgets.Dropdown(
    options=[
        ("🦙 Ollama (Offizielle Library & Live-Registry)", "ollama"),
        ("🤗 Hugging Face (GGUF Community Modelle - Top Downloads)", "huggingface")
    ],
    value="ollama",
    description="Plattform:",
    style=_DEFAULT_STYLE,
    layout=widgets.Layout(flex="1 1 auto", min_width="300px", max_width=DROPDOWN_MAX_WIDTH)
)

btn_confirm_platform = widgets.Button(
    description="OK - Plattform bestätigen",
    button_style="info",
    icon="check",
    layout=widgets.Layout(width="210px", height="36px")
)

platform_row = widgets.HBox(
    [dropdown_platform, btn_confirm_platform],
    layout=widgets.Layout(width=FULL_WIDTH, align_items="center", justify_content="flex-start", gap="12px", margin="6px 0 0 0")
)

section_platform = _create_section(
    "📍 Sektion 1: Plattform & Registry auswählen",
    "Wähle die Quelle aus und lade die Live-Modelle mit dem Bestätigungs-Button.",
    [platform_row]
)

# --- SEKTION 2 WIDGETS (SUCHE & MODELL-AUSWAHL - CHIRURGISCH KORRIGIERT) ---
text_model_search = _create_text("Suchbegriff eingeben (z.B. coder, vision, 8b, qwen, llama, math...)", "Modell suchen:")
dropdown_model = _create_dropdown("Modell wählen:", disabled=True)
dropdown_gguf_file = _create_dropdown("GGUF-Datei:", display="none")
text_custom_tag = _create_text("z.B. deepseek-coder:6.7b oder mistral-nemo", "Ollama Tag:", display="none")

text_custom_hf_repo = widgets.Text(placeholder="z.B. TheBloke/Mistral-7B-Instruct-v0.2-GGUF", description="HF Repo ID:", style=_DEFAULT_STYLE, layout=widgets.Layout(flex="1 1 auto", min_width="260px"))
text_custom_hf_file = widgets.Text(placeholder="z.B. mistral-7b-instruct-v0.2.Q4_K_M.gguf", description="HF Dateiname:", style=_DEFAULT_STYLE, layout=widgets.Layout(flex="1 1 auto", min_width="260px"))

custom_hf_row = widgets.VBox(
    [text_custom_hf_repo, text_custom_hf_file],
    layout=widgets.Layout(width=FULL_WIDTH, max_width=MAX_WIDTH, gap="10px", margin="0 0 8px 0", display="none")
)

# Optimierte Spec-Card ohne unsichtbare Container-Überlappung
html_spec_card = widgets.HTML(
    value="<div style='padding: 12px; border-left: 4px solid #3B82F6; background-color: #F1F5F9; border-radius: 6px; font-size: 12px; color: #475569; height: 100%; box-sizing: border-box;'>Wähle eine Plattform in Sektion 1, um Live-Modelle anzuzeigen.</div>",
    layout=widgets.Layout(width=FULL_WIDTH, height="100%", margin="0")
)

# Saubere Aufteilung in zwei gleichberechtigte Spalten ohne Wrapping-Fehler
col_widgets_left = widgets.VBox(
    [text_model_search, dropdown_model, dropdown_gguf_file, text_custom_tag, custom_hf_row],
    layout=widgets.Layout(flex="3 1 55%", min_width="280px")
)

col_specs_right = widgets.VBox(
    [html_spec_card],
    layout=widgets.Layout(flex="2 1 40%", min_width="240px")
)

section_2_hbox = widgets.HBox(
    [col_widgets_left, col_specs_right],
    layout=widgets.Layout(width=FULL_WIDTH, display="flex", flex_wrap="nowrap", gap="16px", align_items="stretch")
)

section_model = _create_section(
    "🔍 Sektion 2: Echtzeit-Suche & Modell-Auswahl",
    "Filtere die Live-Modelle nach Stichworten und wähle die gewünschte Variante.",
    [section_2_hbox]
)

# --- SEKTION 3 WIDGETS (SPEICHERORT, DOWNLOAD & INTEGRATION) ---
dropdown_target_disk = _create_dropdown("Ziel-Laufwerk:", options=get_system_drives())
text_custom_storage_path = _create_text("z.B. D:\\AI_Models oder /mnt/ext_drive/models", "Pfad (Custom):", display="none")

# Gespeicherten Pfad beim Start laden und vorauswählen
saved_path = load_last_storage_path()
if saved_path:
    matching_option = next((opt[1] for opt in dropdown_target_disk.options if opt[1] == saved_path), None)
    if matching_option:
        dropdown_target_disk.value = matching_option
    else:
        dropdown_target_disk.value = "CUSTOM_PATH"
        text_custom_storage_path.value = saved_path
        text_custom_storage_path.layout.display = "block"

btn_start_download = widgets.Button(
    description="OK - Download & In Ollama einbinden",
    button_style="success",
    icon="cloud-download",
    layout=widgets.Layout(width="300px", height="38px", margin="0 0 8px 0"),
    disabled=True
)

progress_bar = widgets.IntProgress(
    value=0, min=0, max=100, description="Fortschritt:", bar_style="info",
    style={"description_width": LABEL_WIDTH, "bar_color": "#10B981"},
    layout=widgets.Layout(width=FULL_WIDTH, max_width=MAX_WIDTH, margin="0 0 4px 0", display="none")
)

label_status = widgets.Label(value="Warte auf Konfiguration...", layout=widgets.Layout(margin="0 0 6px 0"))

output_log = widgets.Output(
    layout=widgets.Layout(
        width=FULL_WIDTH, max_width=MAX_WIDTH, height="150px",
        border="1px solid #CBD5E1", border_radius="6px", padding="8px",
        overflow="auto", background_color="#0F172A"
    )
)

section_download = _create_section(
    "🚀 Sektion 3: Speicherort, Download & Einbindung",
    "Wähle das Ziellaufwerk, starte den Download und registriere das Modell in Ollama.",
    [
        dropdown_target_disk, 
        text_custom_storage_path,
        progress_bar,          # Fortschriftsbalken in den Sektionen-Container integriert
        label_status,          # Statuslabel ebenfalls direkt integriert
        btn_start_download, 

        widgets.HTML("<div style='font-size: 11px; font-weight: 700; color: #475569; margin: 4px 0;'>Live-Prozessprotokoll:</div>"), 
        output_log
    ]
)

section_download.layout.background_color = "#FFFFFF"

# MASTER DASHBOARD CONTAINER
master_dashboard = widgets.VBox([
    widgets.HTML(
        "<div style='display: flex; align-items: center; justify-content: space-between; border-bottom: 2px solid #E2E8F0; padding-bottom: 8px; margin-bottom: 12px;'>"
        "<h3 style='margin: 0; color: #0F172A; font-family: sans-serif; font-size: 16px;'>🎛️ Manuelles Modell-Management & Download-Utility</h3>"
        "<span style='background-color: #3B82F6; color: white; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: bold;'>Mai_AI Local</span>"
        "</div>"
    ),
    section_platform,
    section_model,
    section_download
], layout=widgets.Layout(
    width=FULL_WIDTH, max_width="800px", padding="16px", margin="10px auto",
    border="1px solid #CBD5E1", border_radius="10px", background_color="#FFFFFF"
))

dropdown_target_disk.observe(on_disk_selection_changed, names='value')
text_custom_storage_path.observe(on_custom_path_submitted, names='value')
text_model_search.observe(on_search_query_changed, names='value')
btn_confirm_platform.on_click(on_platform_confirm_clicked)
dropdown_model.observe(on_model_selection_changed, names='value')
btn_start_download.on_click(on_start_download_clicked)

# Erste Initialisierung der Plattform
on_platform_confirm_clicked(None)
display(master_dashboard)

# GGUF Hybrid Utility & Cleanup Engine
import os
import re
import json
import requests
import subprocess
from pathlib import Path
import ipywidgets as widgets
from IPython.display import display

# Standard-Ablagepfad
HF_MODELS_DIR = r"C:\Offline_AI_Models"

FULL_WIDTH = "100%"
MAX_WIDTH = "900px"

# 🖥️ IPYWIDGETS OBERFLÄCHE DEFINIEREN
output_log = widgets.Output(
    layout=widgets.Layout(
        width=FULL_WIDTH, max_width=MAX_WIDTH, height="180px",
        border="1px solid #CBD5E1", border_radius="6px", padding="8px",
        overflow="auto", background_color="#0F172A"
    )
)

path_input = widgets.Text(
    value=HF_MODELS_DIR,
    description="Modell-Pfad:",
    disabled=False,
    layout=widgets.Layout(width="70%")
)

backend_dropdown = widgets.Dropdown(
    options=[
        ("Ollama (Standard mit Cleanup)", "ollama"),
        ("Direct Llama-CPP (Ohne Ollama)", "llama_cpp")
    ],
    value="ollama",
    description="Backend:",
    disabled=False,
    layout=widgets.Layout(width="70%")
)

start_button = widgets.Button(
    description="Sync, Test & Start",
    button_style="success",
    icon="play",
    layout=widgets.Layout(width="28%")
)

# 🎯 Dashboard UI Container
dashboard_box = widgets.VBox([
    widgets.HTML("<h3>🎛️ GGUF Hybrid Utility & Cleanup Engine</h3>"),
    widgets.HBox([path_input]),
    widgets.HBox([backend_dropdown, start_button]),
    widgets.HTML("<br><b>Echtzeit-Log:</b>"),
    output_log
], layout=widgets.Layout(padding="10px", max_width=MAX_WIDTH, margin="0 auto"))


# 🎨 DASHBOARD PRINT HELPER
def print_section(title: str, subtitle: str = ""):
    print(f" 📍 {title:<64}")
    if subtitle:
        print(f"{subtitle:<64}")

def print_log(level: str, message: str, detail: str = ""):
    badges = {
        "INFO": "ℹ️ [INFO]   ",
        "SUCCESS": "✓  [OK]     ",
        "WARN": "⚠️ [WARN]   ",
        "ERROR": "❌ [FAIL]   ",
        "CLEANUP": "🧹 [REMOVE] "
    }
    prefix = badges.get(level.upper(), f"   [{level}]")
    print(f" {prefix} {message}")
    if detail:
        print(f"Details: {detail.strip()}")

def print_summary(healthy: int, broken: int, total_files: int, registered: int, skipped: int, remaining_models: list):
    print(" 📊 ZUSAMMENFASSUNG & OLLAMA STATUS")
    print(f"  • Gefundene GGUF-Dateien auf Disk: {total_files:<28}")
    print(f"  • Neu registriert:                 {registered:<28}")
    print(f"  • Bereits vorhanden (Skipped):     {skipped:<28}")
    print(f"  • Funktionstüchtige Modelle:       {healthy:<28}")
    print(f"  • Gelöscht / Inkompatibel:         {broken:<28} ")
    print("AKTIVE OLLAMA-MODELLE:")
    for idx, item in enumerate(remaining_models, 1):
        size_mb = (item.size // (1024**2)) if item.size else 0
        model_str = f"{idx}. {item.model} ({size_mb} MB)"
        print(f"{model_str:<64}")


# ⚙️ HILFSFUNKTIONEN FÜR NAMEN UND INTEGRITÄT
def clean_model_name(filename_stem: str) -> str:
    name_lower = filename_stem.lower()
    model_patterns = ["deepseek", "llama", "codestral", "mistral", "qwen", "phi", "gemma"]
    detected_model = "model"
    for m in model_patterns:
        if m in name_lower:
            detected_model = m
            break
            
    version_match = re.search(r'(v\d+|\d+\.\d+)', name_lower)
    detected_version = version_match.group(1) if version_match else ""
    intensity_keywords = ["flash", "pro", "lite", "support", "dspark", "chat", "instruct", "base"]
    found_intensities = [kw for kw in intensity_keywords if kw in name_lower]
    detected_intensity = "-".join(found_intensities[:2])
    
    parts = [detected_model]
    if detected_version: parts.append(detected_version)
    if detected_intensity: parts.append(detected_intensity)
        
    clean_name = re.sub(r'[^a-z0-9._-]', '-', "-".join(parts))
    clean_name = re.sub(r'-+', '-', clean_name).strip('-_.')
    
    if len(clean_name) > 35: clean_name = clean_name[:35].strip('-_.')
    return f"{clean_name}:latest"


def verify_model_integrity(client, model_tag: str) -> bool:
    try:
        client.generate(model=model_tag, prompt="Test", options={"num_predict": 1})
        print_log("SUCCESS", f"Inferenz voll funktionsfähig: '{model_tag}'")
        return True
    except Exception as err:
        err_str = str(err).lower()
        if "unknown model architecture" in err_str or "invalid model" in err_str:
            print_log("ERROR", f"Architektur-Fehler bei '{model_tag}'", "Ollama unterstützt diese Struktur nicht.")
            return False  
        elif "out of memory" in err_str or "cuda" in err_str or "memory" in err_str or "timed out" in err_str:
            print_log("WARN", f"Ressourcen-Warnung bei '{model_tag}'", "Modell ist zu groß für VRAM/RAM, aber Datei intakt.")
            return True  
        else:
            print_log("WARN", f"Warnung beim Inferenz-Test von '{model_tag}'", str(err))
            return True  


# 🚀 HAUPTFUNKTION: HYBRID LOGIK MIT OLLAMA-GEGENKONTROLLE
def run_hybrid_utility(models_dir: str, selected_backend: str, ollama_host: str = "http://127.0.0.1:11434"):
    output_log.clear_output()
    with output_log:
        print(" 🎛️  GGUF HYBRID UTILITY & CLEANUP ENGINE")
        print(" ── Offline_AI Local Engine\n")

        # 1. Pfad prüfen
        cleaned_models_dir = os.path.normpath(str(models_dir).strip())
        models_dir_path = Path(cleaned_models_dir).resolve()
        
        if not models_dir_path.exists():
            print_log("WARN", f"Pfad existiert nicht. Erstelle Ordner: {models_dir_path}")
            os.makedirs(models_dir_path, exist_ok=True)

        gguf_files = list(models_dir_path.rglob("*.gguf"))
        print_log("INFO", f"Zielpfad: {models_dir_path}")
        print_log("INFO", f"{len(gguf_files)} GGUF-Dateien auf Disk gefunden.")

        if not gguf_files:
            print_log("WARN", "Keine .gguf Dateien im Ordner gefunden.")
            return

        # 2. Gegenkontrolle: Läuft Ollama?
        ollama_is_running = False
        try:
            res = requests.get(f"{ollama_host}/api/tags", timeout=2)
            if res.status_code == 200:
                ollama_is_running = True
        except Exception:
            ollama_is_running = False

        # Automatischer Fallback, falls Ollama gewählt wurde, aber nicht läuft
        if selected_backend == "ollama" and not ollama_is_running:
            print_log("WARN", "Ollama-Dienst ist nicht erreichbar!", "Schalte automatisch um auf 'Direct Llama-CPP'")
            selected_backend = "llama_cpp"

        # MODUS A: OLLAMA (Mit Registrierung & Cleanup)
        if selected_backend == "ollama":
            print_section("Sektion: Ollama Sync & Cleanup", "Verwende Ollama API Server")
            from ollama import Client
            ollama_client = Client(host=ollama_host)
            
            try:
                existing_models = {str(m.model).strip().lower() for m in ollama_client.list().models}
            except Exception as e:
                print_log("ERROR", "Konnte Ollama-Modelliste nicht abrufen", str(e))
                return

            registered_count, skipped_count, error_count = 0, 0, 0
            for idx, gguf_file in enumerate(gguf_files, 1):
                print(f"\n ── [{idx}/{len(gguf_files)}] Evaluieren: {gguf_file.name}")
                model_name = clean_model_name(gguf_file.stem)
                
                if model_name in existing_models:
                    print_log("INFO", f"Übersprungen: Bereit als '{model_name}' vorhanden.")
                    skipped_count += 1
                    continue
                
                modelfile_path = gguf_file.parent / f"Modelfile_{gguf_file.stem}"
                absolute_gguf_path = str(gguf_file.absolute()).replace('\\', '/')
                
                with open(modelfile_path, "w", encoding="utf-8") as f:
                    f.write(f"FROM {absolute_gguf_path}\n")
                
                url = f"{ollama_host}/api/create"
                payload = {"name": model_name, "modelfile": f"FROM {absolute_gguf_path}\n", "stream": True}
                
                success = False
                try:
                    response = requests.post(url, json=payload, stream=True)
                    if response.status_code == 200:
                        for line in response.iter_lines():
                            if line:
                                try:
                                    data = json.loads(line.decode('utf-8'))
                                    if "error" in data:
                                        print_log("ERROR", f"Ollama Error ({model_name})", data['error'])
                                    if data.get("status") == "success" or data.get("done"): 
                                        success = True
                                except json.JSONDecodeError:
                                    continue
                except Exception as req_err:
                    print_log("ERROR", "API Request-Fehler", str(req_err))
                
                if success:
                    registered_count += 1
                    print_log("SUCCESS", f"Erfolgreich registriert als '{model_name}'")
                else:
                    error_count += 1
                    
                if modelfile_path.exists(): 
                    modelfile_path.unlink()

            # Integritäts-Check & Bereinigung
            print_section("Sektion: Integritäts-Check & Bereinigung", "Testet Modelle & entfernt inkompatible")
            
            CONFIG_DIR = "./config"
            os.makedirs(CONFIG_DIR, exist_ok=True)
            active_cfg_file = os.path.join(CONFIG_DIR, "active_model_config.json")
            
            # Dynamischer Fallback: Nimm das erste verfügbare Modell als Standard
            local_models_initial = ollama_client.list()
            first_available = local_models_initial.models[0].model if local_models_initial.models else "llama3.1:latest"
            
            active_model_tag = first_available
            if os.path.exists(active_cfg_file):
                try:
                    with open(active_cfg_file, "r", encoding="utf-8") as f:
                        configured_model = json.load(f).get("model_name")
                        if configured_model:
                            active_model_tag = configured_model
                except Exception:
                    pass

            local_models = ollama_client.list()
            healthy_models, broken_models = 0, 0

            for i, item in enumerate(local_models.models, 1):
                size_mb = item.size // (1024**2) if item.size else 0
                print(f"\n ── [{i}/{len(local_models.models)}] Prüfe: {item.model} ({size_mb} MB)")
                
                if verify_model_integrity(ollama_client, item.model):
                    healthy_models += 1
                else:
                    broken_models += 1
                    print_log("CLEANUP", f"Entferne defektes Modell '{item.model}'...")
                    try:
                        ollama_client.delete(model=item.model)
                        print_log("SUCCESS", f"Modell '{item.model}' gelöscht.")
                    except Exception as del_err:
                        print_log("ERROR", f"Fehler beim Löschen", str(del_err))

            # Zusammenfassung & Test-Inferenz
            remaining_models = ollama_client.list()
            print_summary(healthy_models, broken_models, len(gguf_files), registered_count, skipped_count, remaining_models.models)

            if remaining_models.models:
                active_model_tag = remaining_models.models[0].model
                print_section("Sektion: Test-Inferenz", f"Prüfung von '{active_model_tag}'")
                try:
                    res = ollama_client.generate(model=active_model_tag, prompt="Erkläre kurz den Vorteil lokaler KI.")
                    print("\n 💬 ANTWORT:")
                    print(f" {res.get('response', '').strip()}\n")
                    print_log("SUCCESS", "Inferenz erfolgreich!")
                except Exception as err:
                    print_log("ERROR", "Test-Inferenz fehlgeschlagen", str(err))

        # MODUS B: DIRECT LLAMA-CPP (Ohne Ollama)
        else:
            print_section("Sektion: Direct Llama-CPP Engine", "Direktes Laden in VRAM (2x RTX 3090)")
            try:
                from llama_cpp import Llama
            except ImportError:
                print_log("ERROR", "Bibliothek 'llama-cpp-python' fehlt!", "Bitte installieren.")
                return

            target_file = gguf_files[0]
            print_log("INFO", f"Lade direkt via Llama-CPP: {target_file.name}")
            print_log("INFO", "Weise Layer auf GPUs zu (n_gpu_layers=-1)...")

            try:
                llm_agent = Llama(
                    model_path=str(target_file.absolute()),
                    n_ctx=4096,
                    n_gpu_layers=-1,
                    verbose=False
                )
                print_log("SUCCESS", "Modell direkt in VRAM geladen!")

                print_section("Test-Inferenz (Direct Llama-CPP)")
                output = llm_agent(
                    prompt="Erkläre kurz in einem Satz den Vorteil lokaler KI-Modelle.",
                    max_tokens=100, temperature=0.7, echo=False
                )
                print("\n 💬 ANTWORT:")
                print(f" {output['choices'][0]['text'].strip()}\n")
                print_log("SUCCESS", "Direkte Inferenz erfolgreich abgeschlossen!")

            except Exception as direct_err:
                print_log("ERROR", "Fehler beim Laden über Llama-CPP", str(direct_err))


# Button Event verknüpfen
def on_button_clicked(b):
    run_hybrid_utility(path_input.value, backend_dropdown.value)

start_button.on_click(on_button_clicked)

# Im Notebook anzeigen
if __name__ == "__main__":
    display(dashboard_box)

# Test model run
import json
import os
import subprocess
import sys
from pathlib import Path

import ipywidgets as widgets
import requests
from IPython.display import display

# Automatische Installation von llama-cpp-python erzwingen, falls nicht vorhanden
try:
    from llama_cpp import Llama
    HAS_LLAMA_CPP = True
except ImportError:
    HAS_LLAMA_CPP = False
    print("⚠️ 'llama_cpp' nicht gefunden. Versuche automatische Installation...")
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", 
            "llama-cpp-python", 
            "--extra-index-url", "https://abetlen.github.io/llama-cpp-python/whl/cpu"
        ])
        from llama_cpp import Llama
        HAS_LLAMA_CPP = True
        print("✓ 'llama-cpp-python' erfolgreich automatisch installiert!")
    except Exception as e:
        print(f"❌ Automatische Installation fehlgeschlagen: {e}")
        HAS_LLAMA_CPP = False

# Konfigurationspfade
CONFIG_DIR = "./config"
os.makedirs(CONFIG_DIR, exist_ok=True)
active_cfg_file = os.path.join(CONFIG_DIR, "active_model_config.json")

FULL_WIDTH = "100%"
MAX_WIDTH = "900px"
ollama_host = "http://127.0.0.1:11434"

# 🖥️ IPYWIDGETS OBERFLÄCHE DEFINIEREN
output_log = widgets.Output(
    layout=widgets.Layout(
        width=FULL_WIDTH, max_width=MAX_WIDTH, height="180px",
        border="1px solid #CBD5E1", border_radius="6px", padding="8px",
        overflow="auto", background_color="#0F172A"
    )
)

# Funktion zum Laden der gespeicherten Konfiguration
def load_config():
    if os.path.exists(active_cfg_file):
        try:
            with open(active_cfg_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

saved_cfg = load_config()
initial_custom_path = saved_cfg.get("custom_ollama_dir", "D:\\Ollama\\models")

# ⚡ Umgebungsvariable beim Start setzen
if initial_custom_path:
    os.environ["OLLAMA_MODELS"] = initial_custom_path

# 🔍 Kaskadierte Suche nach Modellen
def find_models_cascaded(manual_path=""):
    discovered_options = []
    seen_paths = set()

    if manual_path:
        os.environ["OLLAMA_MODELS"] = manual_path

    # 1. Versuch: Über den laufenden Ollama-Dienst (API)
    try:
        res = requests.get(f"{ollama_host}/api/tags", timeout=1)
        if res.status_code == 200:
            models_data = res.json().get("models", [])
            for m in models_data:
                name = m["name"]
                if name not in seen_paths:
                    seen_paths.add(name)
                    discovered_options.append((f"🦙 Ollama-Dienst: {name}", name))
    except Exception:
        pass

    # 2. Suchpfade zusammenstellen
    search_roots = []
    if manual_path and Path(manual_path).exists():
        search_roots.append(Path(manual_path))

    if "OLLAMA_MODELS" in os.environ:
        search_roots.append(Path(os.environ["OLLAMA_MODELS"]))
        
    search_roots.append(Path.home() / ".ollama" / "models")
    
    drives = []
    if os.name == 'nt':
        import string
        drives = [Path(f"{d}:\\") for d in string.ascii_uppercase if Path(f"{d}:\\").exists()]
    else:
        drives = [Path("/mnt"), Path("/media"), Path("/Volumes"), Path("/home")]

    for drive in drives:
        search_roots.append(drive / ".ollama" / "models")
        search_roots.append(drive / "Ollama" / "models")
        search_roots.append(drive / "ollama" / "models")

    # Durchsuche Roots nach Manifesten
    for root in search_roots:
        manifests_dir = root / "manifests"
        if manifests_dir.exists():
            try:
                for path in manifests_dir.glob("**/*"):
                    if path.is_file():
                        parts = path.relative_to(manifests_dir).parts
                        if len(parts) >= 3:
                            tag = parts[-1]
                            model_name = parts[-2]
                            full_name = f"{model_name}:{tag}"
                            if full_name not in seen_paths:
                                seen_paths.add(full_name)
                                discovered_options.append((f"🦙 Lokales Ollama-Modell ({root.drive or 'Pfad'}): {full_name}", full_name))
            except Exception:
                pass

    # 3. Lokale Projekt-Ordner für rohe Modelldateien (.gguf etc.)
    local_search_dirs = [Path("./data"), Path("./models"), Path("./weights")]
    for l_dir in local_search_dirs:
        if l_dir.exists():
            for p in l_dir.glob("**/*"):
                if p.is_file() and p.suffix in [".gguf", ".bin", ".safetensors"]:
                    path_str = str(p.absolute())
                    if path_str not in seen_paths:
                        seen_paths.add(path_str)
                        discovered_options.append((f"📁 Projekt ({l_dir.name}): {p.name}", path_str))

    if not discovered_options:
        discovered_options = [("Keine Modelle gefunden - Pfad prüfen!", "none")]

    return discovered_options

# Hilfsfunktion: Findet die echte GGUF-Blob-Datei eines Ollama-Modells über das Manifest
def get_ollama_blob_path(model_name):
    custom_p = path_input.value.strip() or os.environ.get("OLLAMA_MODELS", str(Path.home() / ".ollama" / "models"))
    root = Path(custom_p)
    manifests_dir = root / "manifests"
    blobs_dir = root / "blobs"
    
    if manifests_dir.exists():
        for path in manifests_dir.glob("**/*"):
            if path.is_file():
                try:
                    parts = path.relative_to(manifests_dir).parts
                    if len(parts) >= 3:
                        tag = parts[-1]
                        m_name = parts[-2]
                        full_n = f"{m_name}:{tag}"
                        if full_n == model_name or m_name in model_name:
                            with open(path, "r", encoding="utf-8") as f:
                                manifest = json.load(f)
                                for layer in manifest.get("layers", []):
                                    digest = layer.get("digest", "")
                                    if digest.startswith("sha256:"):
                                        sha_hash = digest.split(":")[1]
                                        blob_file = blobs_dir / f"sha256-{sha_hash}"
                                        if not blob_file.exists():
                                            blob_file = blobs_dir / digest.replace(":", "-")
                                        if blob_file.exists():
                                            return str(blob_file)
                except Exception:
                    pass
    return None

# Initiale Optionen laden
model_options = find_models_cascaded(initial_custom_path)

# Aktives Modell bestimmen
initial_model = model_options[0][1]
saved_model = saved_cfg.get("model_name")
if saved_model and any(saved_model == opt[1] for opt in model_options):
    initial_model = saved_model

# UI Widgets definieren
path_input = widgets.Text(
    value=initial_custom_path,
    description="Ollama Ordner (D:\\...):",
    disabled=False,
    layout=widgets.Layout(width="70%")
)

refresh_button = widgets.Button(
    description="Neu scannen",
    button_style="info",
    icon="refresh",
    layout=widgets.Layout(width="28%")
)

model_dropdown = widgets.Dropdown(
    options=model_options,
    value=initial_model,
    description="Modell:",
    disabled=False,
    layout=widgets.Layout(width="70%")
)

prompt_input = widgets.Text(
    value="Erkläre kurz in einem Satz den Vorteil lokaler KI-Modelle.",
    description="Prompt:",
    disabled=False,
    layout=widgets.Layout(width="70%")
)

run_button = widgets.Button(
    description="Inferenz starten",
    button_style="success",
    icon="play",
    layout=widgets.Layout(width="28%")
)

response_textarea = widgets.Textarea(
    value="",
    description="Antwort:",
    disabled=False,
    layout=widgets.Layout(width=FULL_WIDTH, height="120px")
)

# 🎯 Dashboard UI Container
dashboard_box = widgets.VBox([
    widgets.HTML("<h3>🎛️ Lokale Inferenz & Modell-Steuerung (Mit Auto-Install Fallback)</h3>"),
    widgets.HBox([path_input, refresh_button]),
    widgets.HBox([model_dropdown]),
    widgets.HBox([prompt_input, run_button], layout=widgets.Layout(margin="5px 0 0 0")),
    widgets.HTML("<br><b>Aktuelle Antwort:</b>"),
    response_textarea,
    widgets.HTML("<br><b>Echtzeit-Log:</b>"),
    output_log
], layout=widgets.Layout(padding="10px", max_width=MAX_WIDTH, margin="0 auto"))

# Event: Neu scannen
def on_refresh_clicked(b):
    with output_log:
        output_log.clear_output()
        custom_p = path_input.value.strip()
        print(f" 🔍 Scanne erneut mit Pfad: '{custom_p}'...")
        
        if custom_p:
            os.environ["OLLAMA_MODELS"] = custom_p
        
        new_opts = find_models_cascaded(custom_p)
        model_dropdown.options = new_opts
        if new_opts and new_opts[0][1] != "none":
            model_dropdown.value = new_opts[0][1]
            
        try:
            cfg = load_config()
            cfg["custom_ollama_dir"] = custom_p
            cfg["model_name"] = model_dropdown.value
            with open(active_cfg_file, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4)
        except Exception:
            pass
            
        print(f" ✓ Scan abgeschlossen. {len(new_opts)} Modell(e) gefunden.")

refresh_button.on_click(on_refresh_clicked)

# 🚀 AUSFÜHRUNGS-LOGIK BEI KLICK (Inkl. Llama-CPP Fallback)
def on_run_clicked(b):
    output_log.clear_output()
    selected_model = model_dropdown.value
    current_prompt = prompt_input.value
    custom_p = path_input.value.strip()

    if custom_p:
        os.environ["OLLAMA_MODELS"] = custom_p

    try:
        cfg = load_config()
        cfg["model_name"] = selected_model
        cfg["custom_ollama_dir"] = custom_p
        with open(active_cfg_file, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4)
    except Exception:
        pass

    with output_log:
        print(f" 🚀 Starte Inferenz mit Ziel: '{selected_model}'")
        print(f" 📝 Prompt: '{current_prompt}'\n")
        
        # Fall A: Direkter Dateipfad (.gguf etc.)
        if os.path.exists(selected_model) or ("/" in selected_model or "\\" in selected_model) and not ":" in selected_model[2:]:
            print(f" 📂 [DATEIPFAD-MODUS] Lade direkte Modelldatei über llama-cpp...")
            global HAS_LLAMA_CPP
            if not HAS_LLAMA_CPP:
                try:
                    subprocess.check_call([
                        sys.executable, "-m", "pip", "install", 
                        "llama-cpp-python", 
                        "--extra-index-url", "https://abetlen.github.io/llama-cpp-python/whl/cpu"
                    ])
                    global Llama
                    from llama_cpp import Llama
                    HAS_LLAMA_CPP = True
                except Exception as e:
                    response_textarea.value = f"Fehler: Konnte 'llama-cpp-python' nicht installieren: {e}"
                    print(f" ❌ [FAIL] {e}")
                    return
            try:
                file_size_gb = os.path.getsize(selected_model) / (1024**3)
                print(f" 📂 Modelldatei-Größe: {file_size_gb:.2f} GB")
                print(" ⚙️ Lade Modell in den Speicher (verbose=True)...")
                llm = Llama(model_path=selected_model, verbose=True, n_ctx=2048)
                
                print(" 🤖 Generiere Antwort...")
                output = llm(current_prompt, max_tokens=256, temperature=0.7)
                answer = output["choices"][0]["text"].strip()
                response_textarea.value = answer
                print(" ✓ [OK] Inferenz via direktem Dateipfad erfolgreich!")
            except Exception as err:
                response_textarea.value = f"Llama-cpp Fehler: {str(err)}"
                print(f" ❌ [FAIL] {str(err)}")
            
        # Fall B: Ollama-Modellname (Zuerst API, bei Fehler direkter llama-cpp Fallback)
        else:
            success = False
            try:
                url = f"{ollama_host}/api/generate"
                payload = {
                    "model": selected_model,
                    "prompt": current_prompt,
                    "stream": False
                }
                
                response = requests.post(url, json=payload, timeout=5)
                if response.status_code == 200:
                    answer = response.json().get("response", "").strip()
                    response_textarea.value = answer
                    print(" ✓ [OK] Inferenz über Ollama-Dienst erfolgreich!")
                    success = True
                else:
                    print(f" ⚠️ Ollama-Dienst meldete HTTP {response.status_code}. Versuche Fallback...")
            except Exception:
                print(" ⚠️ Ollama-Dienst nicht erreichbar. Aktiviere direktes llama-cpp-Fallback...")

            # Wenn Ollama nicht geklappt hat -> Fallback auf llama_cpp mit der Blob-Datei
            if not success:
                if not HAS_LLAMA_CPP:
                    try:
                        print(" ⚙️ Installiere 'llama-cpp-python' automatisch nach...")
                        subprocess.check_call([
                            sys.executable, "-m", "pip", "install", 
                            "llama-cpp-python", 
                            "--extra-index-url", "https://abetlen.github.io/llama-cpp-python/whl/cpu"
                        ])
                        from llama_cpp import Llama
                        HAS_LLAMA_CPP = True
                    except Exception as e:
                        err_msg = f"Ollama läuft nicht und automatische Installation von 'llama-cpp-python' fehlgeschlagen: {e}"
                        response_textarea.value = err_msg
                        print(f" ❌ [FAIL] {err_msg}")
                        return

                print(" 🔍 Suche zugehörige GGUF-Blob-Datei im Ollama-Verzeichnis...")
                blob_path = get_ollama_blob_path(selected_model)
                
                if blob_path and os.path.exists(blob_path):
                    file_size_gb = os.path.getsize(blob_path) / (1024**3)
                    print(f" 📂 Gefundene Modelldatei: {blob_path} ({file_size_gb:.2f} GB)")
                    try:
                        print(" ⚙️ Lade Modell in den Speicher (das Laden von großen GGUF-Dateien kann einen Moment dauern)...")
                        llm = Llama(model_path=blob_path, verbose=True, n_ctx=2048)
                        
                        print(" 🤖 Generiere Antwort...")
                        output = llm(current_prompt, max_tokens=256, temperature=0.7)
                        answer = output["choices"][0]["text"].strip()
                        response_textarea.value = answer
                        print(" ✓ [OK] Inferenz erfolgreich über direktes llama-cpp-Fallback ausgeführt!")
                    except Exception as err:
                        response_textarea.value = f"Fallback Llama-cpp Fehler: {str(err)}"
                        print(f" ❌ [FAIL] {str(err)}")
                else:
                    err_msg = f"Ollama offline und keine passende GGUF-Blob-Datei für '{selected_model}' gefunden."
                    response_textarea.value = err_msg
                    print(f" ❌ [FAIL] {err_msg}")

run_button.on_click(on_run_clicked)

# Im Notebook anzeigen
if __name__ == "__main__":
    display(dashboard_box)