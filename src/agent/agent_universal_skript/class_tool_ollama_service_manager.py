import os
import sys
import subprocess
import time
import urllib.request
import json
import socket
import re
import threading
from pathlib import Path

OLLAMA_HOST = "http://127.0.0.1:11434"
MODEL = "llama3.1"
FALLBACK_MODELS = ["llama3.1:latest", "codestral:latest", "qwen-3.5:latest"]
SOCKET_TIMEOUT = 1.0
API_TIMEOUT = 5.0
MAX_START_RETRIES = 6
RETRY_WAIT_SEC = 1.5


class class_tool_ollama_service_manager:
    """
    Universeller Manager für Ollama-Dienste und LLM-Inferenz.
    Prüft autonom die Verfügbarkeit, startet Ollama bei Bedarf im Hintergrund,
    ermittelt lokal vorhandene Modelle und steuert Chat-/Generierungsaufrufe fehlertolerant.
    """
    OLLAMA_HOST = OLLAMA_HOST
    MODEL = MODEL
    FALLBACK_MODELS = FALLBACK_MODELS
    SOCKET_TIMEOUT = SOCKET_TIMEOUT
    API_TIMEOUT = API_TIMEOUT
    MAX_START_RETRIES = MAX_START_RETRIES
    RETRY_WAIT_SEC = RETRY_WAIT_SEC

    _verified_cache = False
    _inference_lock = threading.Lock()

    @classmethod
    def is_port_open(cls, host: str, port: int, timeout: float = None) -> bool:
        """Prüft per Socket, ob der angegebene Port erreichbar ist."""
        if timeout is None:
            timeout = cls.SOCKET_TIMEOUT
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            return False

    @classmethod
    def ensure_ollama_running(cls, ollama_host: str = None) -> bool:
        """Prüft autonom den Status von Ollama und startet den Dienst bei Bedarf."""
        if ollama_host is None:
            ollama_host = cls.OLLAMA_HOST
        host_ip = ollama_host.replace("http://", "").replace("https://", "").split(":")[0]
        try:
            port = int(ollama_host.split(":")[-1])
        except ValueError:
            port = 11434

        # 1. Socket-Check
        if cls.is_port_open(host_ip, port, timeout=cls.SOCKET_TIMEOUT):
            try:
                req = urllib.request.Request(f"{ollama_host}/api/tags")
                with urllib.request.urlopen(req, timeout=cls.API_TIMEOUT) as resp:
                    if resp.status == 200:
                        cls._verified_cache = True
                        return True
            except Exception:
                pass

        # 2. Start Ollama im Hintergrund
        try:
            if os.name == "nt":
                flags = 0x08000000 | 0x00000200 | 0x00000008
                subprocess.Popen(
                    ["ollama", "serve"],
                    creationflags=flags,
                    close_fds=True
                )
            else:
                subprocess.Popen(
                    ["ollama", "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
        except FileNotFoundError:
            print("[OLLAMA] 'ollama' command not found. Install: https://ollama.com")
            return False
        except Exception as err:
            print(f"[OLLAMA] Failed to start Ollama: {err}")
            return False

        # 3. Warten auf Start
        for attempt in range(1, cls.MAX_START_RETRIES + 1):
            time.sleep(cls.RETRY_WAIT_SEC)
            if cls.is_port_open(host_ip, port, timeout=cls.SOCKET_TIMEOUT):
                try:
                    req = urllib.request.Request(f"{ollama_host}/api/tags")
                    with urllib.request.urlopen(req, timeout=cls.API_TIMEOUT) as resp:
                        if resp.status == 200:
                            cls._verified_cache = True
                            return True
                except Exception:
                    pass
        return False

    @classmethod
    def is_ollama_running(cls, ollama_host: str = None) -> bool:
        """Prüft in Echtzeit, ob Ollama läuft."""
        if ollama_host is None:
            ollama_host = cls.OLLAMA_HOST
        host_ip = ollama_host.replace("http://", "").replace("https://", "").split(":")[0]
        try:
            port = int(ollama_host.split(":")[-1])
        except ValueError:
            port = 11434
        return cls.is_port_open(host_ip, port, timeout=cls.SOCKET_TIMEOUT)

    @classmethod
    def get_available_models(cls, ollama_host: str = None) -> list:
        """Gibt Liste aller lokal installierten Modelle zurück."""
        if ollama_host is None:
            ollama_host = cls.OLLAMA_HOST
        try:
            req = urllib.request.Request(f"{ollama_host}/api/tags")
            with urllib.request.urlopen(req, timeout=cls.API_TIMEOUT) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    return [m.get("name") for m in data.get("models", []) if m.get("name")]
        except Exception:
            pass
        return []

    @classmethod
    def resolve_model(cls, preferred_model: str = None, ollama_host: str = None) -> str:
        """Wählt passendes Modell aus."""
        if preferred_model is None:
            preferred_model = cls.MODEL
        if ollama_host is None:
            ollama_host = cls.OLLAMA_HOST
        available = cls.get_available_models(ollama_host)
        if not available:
            return preferred_model

        for m in available:
            if m.lower() == preferred_model.lower() or m.lower().startswith(f"{preferred_model.lower()}:"):
                return m
        for fb in cls.FALLBACK_MODELS:
            for m in available:
                if m.lower() == fb.lower() or m.lower().startswith(f"{fb.lower()}:"):
                    return m
        return available[0] if available else preferred_model

    @classmethod
    def get_client(cls, ollama_host: str = None):
        """Erstellt Ollama-Client."""
        if ollama_host is None:
            ollama_host = cls.OLLAMA_HOST
        if not cls.ensure_ollama_running(ollama_host):
            return None
        try:
            from ollama import Client
            client = Client(host=ollama_host)
            client.list()
            return client
        except Exception:
            return None

    @classmethod
    def chat(cls, messages: list, model: str = None, ollama_host: str = None) -> dict:
        """Führt Chat-Aufruf aus."""
        with cls._inference_lock:
            if ollama_host is None:
                ollama_host = cls.OLLAMA_HOST
            client = cls.get_client(ollama_host)
            if not client:
                return {"status": "FAILED", "content": "", "error": "Ollama not available"}
            target_model = cls.resolve_model(model, ollama_host)
            try:
                response = client.chat(model=target_model, messages=messages)
                content = response.get("message", {}).get("content", "")
                return {"status": "SUCCESS", "content": content, "model": target_model}
            except Exception as e:
                return {"status": "FAILED", "content": "", "error": str(e), "model": target_model}

    @classmethod
    def generate(cls, prompt: str, model: str = None, ollama_host: str = None) -> dict:
        """Führt Text-Generierung aus."""
        with cls._inference_lock:
            if ollama_host is None:
                ollama_host = cls.OLLAMA_HOST
            client = cls.get_client(ollama_host)
            if not client:
                return {"status": "FAILED", "content": "", "error": "Ollama not available"}
            target_model = cls.resolve_model(model, ollama_host)
            try:
                response = client.generate(model=target_model, prompt=prompt)
                content = response.get("response", "")
                return {"status": "SUCCESS", "content": content, "model": target_model}
            except Exception as e:
                return {"status": "FAILED", "content": "", "error": str(e), "model": target_model}

    @classmethod
    def pull_model(cls, model_name: str, ollama_host: str = None) -> dict:
        """Lädt Modell herunter."""
        with cls._inference_lock:
            if ollama_host is None:
                ollama_host = cls.OLLAMA_HOST
            if not cls.ensure_ollama_running(ollama_host):
                return {"status": "FAILED", "error": f"Ollama host {ollama_host} not reachable."}
            url = f"{ollama_host}/api/pull"
            payload = json.dumps({"name": model_name, "stream": False}).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=300) as resp:
                    status_code = resp.status
                    raw_body = resp.read().decode("utf-8")
                    try:
                        return json.loads(raw_body)
                    except json.JSONDecodeError:
                        return {"status": status_code, "raw": raw_body}
            except urllib.error.HTTPError as e:
                return {"status": e.code, "error": str(e.reason)}

    @classmethod
    def run_agent(cls, task_or_fn, *args, agent_title: str = "Agent",
                  model: str = None, ollama_host: str = None,
                  min_ram_mb: int = 2000, max_cpu_threshold: float = 90.0,
                  spinner_interval: float = 1.0, **kwargs):
        """
        Zentrale Methode zur standardisierten Ausführung aller Agenten-Abläufe
        mit automatischem Start und Koppelung des class_tool_resource_aware_spinner.
        
        Nimmt dem Aufrufer das manuelle Verwalten von Threads und Stop-Events ab.
        Unterstützt:
        1. Übergabe einer ausführbaren Funktion: task_or_fn(*args, **kwargs)
        2. Übergabe von Chat-Nachrichten (list): Ruft chat() mit Spinner auf.
        3. Übergabe eines Prompts (str): Ruft generate() mit Spinner auf.
        4. Übergabe eines Payloads (dict): Ruft call_ollama() mit Spinner auf.
        """
        spinner_cls = spinner_tool or globals().get('class_tool_resource_aware_spinner')
        if not spinner_cls:
            try:
                import importlib
                mod = importlib.import_module('agent_universal_skript.class_tool_resource_aware_spinner')
                spinner_cls = getattr(mod, 'class_tool_resource_aware_spinner', None)
            except Exception:
                spinner_cls = None

        spinner = None
        if spinner_cls:
            try:
                spinner = spinner_cls(
                    agent_name=agent_title,
                    min_ram_mb=min_ram_mb,
                    max_cpu_threshold=max_cpu_threshold,
                    spinner_interval=spinner_interval
                )
            except Exception:
                spinner = None

        stop_event = threading.Event() if spinner else None
        spinner_thread = None
        if spinner and stop_event:
            spinner_thread = threading.Thread(target=spinner.run, args=(stop_event, True))
            spinner_thread.daemon = True
            spinner_thread.start()

        try:
            # Fall 1: Aufrufbare Funktion/Methode
            if callable(task_or_fn):
                return task_or_fn(*args, **kwargs)

            # Fall 2: Chat-Nachrichten (Liste von Dicts)
            elif isinstance(task_or_fn, list):
                return cls.chat(messages=task_or_fn, model=model, ollama_host=ollama_host)

            # Fall 3: Text-Prompt (String)
            elif isinstance(task_or_fn, str):
                return cls.generate(prompt=task_or_fn, model=model, ollama_host=ollama_host)

            # Fall 4: REST-API Payload (Dict)
            elif isinstance(task_or_fn, dict):
                endpoint = kwargs.get("endpoint", "/api/generate")
                return cls.call_ollama(endpoint=endpoint, payload=task_or_fn, agent_title=agent_title, ollama_host=ollama_host)

            else:
                raise ValueError(f"Nicht unterstützter Typ für run_agent: {type(task_or_fn)}")

        finally:
            if stop_event:
                stop_event.set()
            if spinner_thread:
                spinner_thread.join()

    @classmethod
    def call_ollama(cls, endpoint: str, payload: dict, agent_title: str = "Ollama",
                    timeout_sec: int = 1800, ollama_host: str = None) -> tuple[bool, dict]:
        """
        Zentrale Zero-Dependency Ollama-Kommunikation mit integriertem Terminal-Spinner
        und konfigurierbarem Timeout. Single Source of Truth für rohe REST-API-Endpunkte.
        """
        import threading
        with cls._inference_lock:
            if ollama_host is None:
                ollama_host = cls.OLLAMA_HOST

            url = f"{ollama_host}{endpoint}"
            
            try:
                data = json.dumps(payload).encode("utf-8")
            except Exception as json_err:
                return False, {"error": f"Payload JSON Encoding Error: {str(json_err)}"}

            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

            spinner_cls = globals().get('class_tool_resource_aware_spinner')
            spinner = spinner_cls(agent_name=agent_title, spinner_interval=1.0) if spinner_cls else None
            stop_event = threading.Event() if spinner else None
            spinner_thread = None
            if spinner and stop_event:
                spinner_thread = threading.Thread(target=spinner.run, args=(stop_event, True))
                spinner_thread.start()

            try:
                with urllib.request.urlopen(req, timeout=timeout_sec) as response:
                    if response.status == 200:
                        res_data = json.loads(response.read().decode("utf-8"))
                        return True, res_data
                    else:
                        return False, {"error": f"HTTP Status {response.status}"}
            except urllib.request.HTTPError as e:
                try:
                    err_body = json.loads(e.read().decode("utf-8"))
                    return False, {"error": err_body.get("error", str(e))}
                except Exception:
                    return False, {"error": f"HTTP Error {e.code}: {e.reason}"}
            except (socket.timeout, TimeoutError) as te:
                return False, {"error": f"Ollama Request Timeout nach {timeout_sec}s: {str(te)}"}
            except Exception as e:
                return False, {"error": f"Netzwerk/Socket-Fehler bei Ollama: {str(e)}"}
            finally:
                if stop_event:
                    stop_event.set()
                if spinner_thread:
                    spinner_thread.join()
            return False, {"error": "Unbekannter Fehler bei der Ollama-Kommunikation"}

    @classmethod
    def get_active_model(cls, preferred_patterns: list = None, exclude_patterns: list = None,
                         fallback_default: str = "hermes", ollama_host: str = None) -> str:
        """
        Ermittelt das optimale lokale LLM über die Ollama-API, filtert ungeeignete Modelle
        und greift intelligent auf lokale Fallbacks zurück.
        """
        if ollama_host is None:
            ollama_host = cls.OLLAMA_HOST
        if preferred_patterns is None:
            preferred_patterns = ["hermes", "qwen", "codestral", "llama"]
        if exclude_patterns is None:
            exclude_patterns = ["671b", "deepseek-v3"]

        url = f"{ollama_host}/api/tags"
        try:
            req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=cls.API_TIMEOUT) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    models = data.get("models", [])
                    if models:
                        model_names = [m.get("name") for m in models if isinstance(m, dict) and "name" in m]
                        valid_models = [m for m in model_names if not any(ex in m.lower() for ex in exclude_patterns)]
                        if not valid_models:
                            valid_models = model_names
                        for pat in preferred_patterns:
                            for name in valid_models:
                                if pat.lower() in name.lower():
                                    return name
                        return valid_models[0]
        except Exception:
            pass
        return fallback_default

    @staticmethod
    def is_valid_model_name(name: str) -> bool:
        """Prüft, ob ein Modellname den strikten Konventionen von Ollama entspricht."""
        if not name or not isinstance(name, str):
            return False
        clean = name.strip()
        pattern = re.compile(r"^(?:[a-z0-9]+(?:[._-][a-z0-9]+)*/)?([a-z0-9]+(?:[._-][a-z0-9]+)*)(?::([a-z0-9]+(?:[._-][a-z0-9]+)*))?$")
        return bool(pattern.match(clean))

    @classmethod
    def sanitize_model_name(cls, raw_name: str, default_fallback: str = "custom-model") -> str:
        """Bereinigt und normalisiert einen beliebigen Eingabestring zu einem validen Ollama-Modellnamen."""
        if not raw_name or not isinstance(raw_name, str):
            return default_fallback
        clean = raw_name.strip()
        for ext in (".gguf", ".bin", ".safetensors", ".pt", ".onnx", ".ckpt", ".tar.gz", ".tgz", ".zip"):
            if clean.lower().endswith(ext):
                clean = clean[:-len(ext)]
                break
        umlaut_map = {"ä": "ae", "Ä": "ae", "ö": "oe", "Ö": "oe", "ü": "ue", "Ü": "ue", "ß": "ss"}
        for k, v in umlaut_map.items():
            clean = clean.replace(k, v)
        clean = clean.lower()
        clean = re.sub(r"[^a-z0-9\.\_\-\:\/]", "-", clean)
        clean = re.sub(r"-+", "-", clean).strip("-._")
        return clean or default_fallback