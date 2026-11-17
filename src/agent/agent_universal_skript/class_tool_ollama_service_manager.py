"""
Modul: class_tool_ollama_service_manager
Bezeichnung: Service-Manager für Ollama-Dienst und lokale LLM-Inferenz
Inhaltlicher Schwerpunkt:
Autonome Überprüfung und Starten des lokalen Ollama-Dienstes, Modell-Auflösung,
Modellbereinigung und fehlertolerante Durchführung von Chat-, Generierungs- und REST-Anfragen.
"""

import asyncio
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import warnings
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Set

import nltk
import ollama
import psutil
import spacy
from sentence_transformers import CrossEncoder
from sympy import sympify

#  Environment & Warnings 
warnings.filterwarnings("ignore", category=FutureWarning)
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')
from nltk.corpus import stopwords

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    nlp_de = spacy.load("de_core_news_lg")
except OSError:
    subprocess.run(["python", "-m", "spacy", "download", "de_core_news_lg"], check=True)
    nlp_de = spacy.load("de_core_news_lg")

nli_model_name = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"
try:
    nli_model = CrossEncoder(nli_model_name, local_files_only=True)
except Exception:
    nli_model = CrossEncoder(nli_model_name, local_files_only=False)

# Globale Bindings
logger = globals().get("class_logger_audit_execution")
spinner_cls_global = globals().get("class_tool_resource_aware_spinner")

class class_tool_ollama_service_manager:
    """
    Universeller Manager für Ollama-Dienste und LLM-Inferenz.
    Prüft autonom die Verfügbarkeit, startet Ollama bei Bedarf im Hintergrund,
    ermittelt lokal vorhandene Modelle und steuert Inferenzaufrufe fehlertolerant.
    """

    _cfg = globals().setdefault("_AGENT_CONFIG", {})
    # Netzwerk- und Ausführungs-Einstellungen für Ollama
    MODEL: str              = _cfg.setdefault("MODEL", "")
    FALLBACK_MODELS: list   = _cfg.setdefault("FALLBACK_MODELS", [])
    OLLAMA_HOST: str        = _cfg.setdefault("OLLAMA_HOST", "http://127.0.0.1:11434")
    SOCKET_TIMEOUT: float   = _cfg.setdefault("SOCKET_TIMEOUT", 1.0)
    API_TIMEOUT: float      = _cfg.setdefault("API_TIMEOUT", 1.5)
    MAX_START_RETRIES: int  = _cfg.setdefault("MAX_START_RETRIES", 5)
    RETRY_WAIT_SEC: float   = _cfg.setdefault("RETRY_WAIT_SEC", 1.5)
    PORT_DEFAULT: int       = _cfg.setdefault("PORT_DEFAULT", 11434)

    OLAMA_MODEL_CODE_LOW    = _cfg.setdefault("OLAMA_MODEL_CODE_LOW",    "codestral:22b")
    OLAMA_MODEL_CODE_HIGH   = _cfg.setdefault("OLAMA_MODEL_CODE_HIGH",   "qwen3-coder-next-ud-q4-k-xl")
    OLAMA_MODEL_LOGIC_LOW   = _cfg.setdefault("OLAMA_MODEL_LOGIC_LOW",   "deepseek-r1:8b")
    OLAMA_MODEL_LOGIC_HIGH  = _cfg.setdefault("OLAMA_MODEL_LOGIC_HIGH",  "qwen3-coder-next-ud-q4-k-xl")
    OLAMA_MODEL_TEXT_LOW    = _cfg.setdefault("OLAMA_MODEL_TEXT_LOW",    "gemma3:4b")
    OLAMA_MODEL_TEXT_HIGH   = _cfg.setdefault("OLAMA_MODEL_TEXT_HIGH",   "qwen3.6:27b")
    OLAMA_MODEL_FUSION      = _cfg.setdefault("OLAMA_MODEL_FUSION",      "qwen3.5-2b-artemis-q5-k-m")

    _verified_cache: bool = False
    _inference_lock = threading.Lock()

    @classmethod
    def check_hardware_capacity(cls) -> bool:
        """
        Prüft den System-RAM und den kombinierten VRAM aller verfügbaren GPUs über nvidia-smi
        """
        print('check_hardware_capacity')
        mem = psutil.virtual_memory()
        free_ram_gb = mem.available / (1024 ** 3)
        total_ram_gb = mem.total / (1024 ** 3)
        print(f"[Hardware-Check] System RAM  - Gesamt: {total_ram_gb:.1f} GB | Frei: {free_ram_gb:.1f} GB")
        vram_sufficient = True
        try:
            result = subprocess.run(['nvidia-smi', '--query-gpu=memory.free', '--format=csv,nounits,noheader'],capture_output=True, text=True, check=True)
            free_vram_list = [int(x) for x in result.stdout.strip().split('\n') if x.strip()]
            device_count = len(free_vram_list)
            free_vram_gb = sum(free_vram_list) / 1024.0
            print(f"[Hardware-Check] GPU VRAM (Multi-GPU via nvidia-smi) - Freier VRAM gesamt: {free_vram_gb:.1f} GB ({device_count} GPUs aktiv)")
            if free_vram_gb < 6.0:
                print("[Hardware-Check] Warnung: VRAM-Kapazität kritisch (< 6 GB frei).")
                vram_sufficient = False
        except Exception as e:
            print(f"[Hardware-Check] nvidia-smi VRAM-Abfrage fehlgeschlagen: {e}")
            # Fallback auf PyTorch, falls nvidia-smi fehlschlägt
            if cls.TORCH_AVAILABLE and torch.cuda.is_available():
                try:
                    device_count = torch.cuda.device_count()
                    total_free_vram = 0
                    for i in range(device_count):
                        free_bytes, _ = torch.cuda.mem_get_info(i)
                        total_free_vram += free_bytes
                    free_vram_gb = total_free_vram / (1024 ** 3)
                    print(f"[Hardware-Check] GPU VRAM (PyTorch Fallback) - Freier VRAM gesamt: {free_vram_gb:.1f} GB ({device_count} GPUs aktiv)")
                    if free_vram_gb < 6.0:
                        vram_sufficient = False
                except Exception as inner_e:
                    print(f"[Hardware-Check] Auch PyTorch VRAM-Abfrage fehlgeschlagen: {inner_e}")
            else:
                print("[Hardware-Check] Keine CUDA-GPU via nvidia-smi oder PyTorch erkannt.")

        if free_ram_gb < 4.0 or not vram_sufficient:
            print("[Hardware-Check] Entscheidung: Modus = SEQUENZIELL (Hardware-Schutz aktiv).")
            return False
        else:
            print("[Hardware-Check] Entscheidung: Modus = PARALLEL (Ausreichend Ressourcen).")
            return True

    @classmethod
    def validate_and_adjust_models(active_models: list, available_models_dict: dict) -> list:
        """
        Prüft, ob die gewünschten Modelle lokal vorhanden sind (unterstützt Teil- und 
        Toleranzmatching bei Namensabweichungen), bereinigt Leerzeichen/Zeilenumbrüche, 
        verhindert Duplikate und gleicht die Modellgrößen mit den Hardware-Ressourcen ab.
        """
        print('validate_and_adjust_models')
        validated_models = []
        if isinstance(available_models_dict, dict):
            available_names_cleaned = {str(m).strip(): size for m, size in available_models_dict.items()}
            available_names = list(available_names_cleaned.keys())
        else:
            available_names_cleaned = {str(m).strip(): 0.0 for m in available_models_dict}
            available_names = list(available_names_cleaned.keys())
            available_models_dict = available_names_cleaned
        #print("\n Starte Validierung der aktiven Modelle ") 
        for model in active_models:
            clean_model = str(model).strip()
            matched_model = None
            if clean_model in available_names:
                matched_model = clean_model
            else:
                base_query = clean_model.split(':')[0].lower()
                for avail in available_names:
                    if base_query in avail.lower():
                        matched_model = avail
                        #print(f"[Info] Fuzzy-Match: '{clean_model}' wurde auf lokalem Modell '{matched_model}' abgebildet.")
                        break
            if matched_model:
                if matched_model not in validated_models:
                    model_size = available_models_dict.get(matched_model, 0.0)
                    if model_size > 70.0:  # Z.B. das 122B Modell
                        print(f"[Warnung] Modell '{matched_model}' ({model_size:.2f} GB) überschreitet die sicheren Hardware-Kapazitäten!")
                    else:
                        validated_models.append(matched_model)
            else:
                print(f"[Warnung] Modell '{clean_model}' nicht auf Festplatte gefunden.")
                if available_names:
                    fallback = next((m for m in available_names if m not in validated_models), available_names[0])
                    print(f"-> Verwende stattdessen verfügbares Fallback-Modell: {fallback}")
                    if fallback not in validated_models:
                        validated_models.append(fallback)
        #print(f"Validierte aktive Modelle: {validated_models}\n")
        return validated_models

    @classmethod
    def is_port_open(cls, host: str, port: int, timeout: float = None) -> bool:
        """Prüft per Socket, ob der angegebene Port erreichbar ist."""
        print(f"[class_tool_ollama_service_manager] Starte Arbeit: is_port_open wird jetzt ausgeführt. (Parameter: {host}:{port})")
        timeout = timeout or cls.SOCKET_TIMEOUT
        try:
            with socket.create_connection((host, port), timeout=timeout):
                result = True
        except (socket.timeout, ConnectionRefusedError, OSError):
            result = False
        print("[class_tool_ollama_service_manager] Erfolg: is_port_open erfolgreich beendet.")
        return result

    @classmethod
    def ensure_ollama_running(cls,ollama_host: str = None) -> bool:
        """
        Prüft autonom, ob Ollama läuft, und synchronisiert die Konfiguration 
        sauber und kompakt über das globale _AGENT_CONFIG-Dictionary.
        """
        def is_port_open(ip, port, timeout):
            try:
                with socket.create_connection((ip, port), timeout=timeout):
                    return True
            except (socket.timeout, ConnectionRefusedError, OSError):
                return False

        host_ip = cls.OLLAMA_HOST.replace("http://", "").replace("https://", "").split(":")[0]
        try:
            port = int(cls.OLLAMA_HOST.split(":")[-1])
        except ValueError:
            port = cls.PORT_DEFAULT

        # 1. Schritt: Prüfen, ob der Dienst bereits läuft und antwortet
        if is_port_open(host_ip, port, timeout=cls.SOCKET_TIMEOUT):
            try:
                req = urllib.request.Request(f"{cls.OLLAMA_HOST}/api/tags")
                with urllib.request.urlopen(req, timeout=cls.API_TIMEOUT) as resp:
                    if resp.status == 200:
                        return True
            except Exception:
                pass

        # 2. Schritt: Dienst läuft nicht -> Autonomer Startversuch im Hintergrund
        try:
            if os.name == "nt":
                flags = 0x08000000 | 0x00000200 | 0x00000008
                subprocess.Popen(["ollama", "serve"], creationflags=flags, close_fds=True)
            else:
                subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        except FileNotFoundError:
            print(f"\n[class_tool_ollama_service_manager] Der Befehl 'ollama' wurde im System-PATH nicht gefunden. Bitte Ollama installieren.")
            return False
        except Exception as e:
            print(f"\n[class_tool_ollama_service_manager] Unerwarteter Systemfehler beim Starten des Ollama-Prozesses: {e}")
            return False

        # 3. Schritt: Warten / Polling bis der Server erreichbar ist
        for _ in range(cls.MAX_START_RETRIES):
            time.sleep(cls.RETRY_WAIT_SEC)
            if is_port_open(host_ip, port, timeout=cls.SOCKET_TIMEOUT):
                try:
                    req = urllib.request.Request(f"{cls.OLLAMA_HOST}/api/tags")
                    with urllib.request.urlopen(req, timeout=cls.API_TIMEOUT) as resp:
                        if resp.status == 200:
                            return True
                except Exception:
                    pass
        print(f"\n[class_tool_ollama_service_manager] Timeout: Der Ollama-Dienst konnte nach {MAX_START_RETRIES * RETRY_WAIT_SEC} Sekunden nicht erfolgreich gestartet werden.")
        return False

    @classmethod
    def is_ollama_running(cls, ollama_host: str = None) -> bool:
        """Prüft in Echtzeit, ob der Ollama-Port erreichbar ist."""
        print("[class_tool_ollama_service_manager] Starte Arbeit: is_ollama_running wird jetzt ausgeführt.")
        ollama_host = ollama_host or cls.OLLAMA_HOST
        host_ip = ollama_host.replace("http://", "").replace("https://", "").split(":")[0]
        try:
            port = int(ollama_host.split(":")[-1])
        except ValueError:
            port = 11434
        result = cls.is_port_open(host_ip, port, timeout=cls.SOCKET_TIMEOUT)
        if result is False or result is None:
            print("[class_tool_ollama_service_manager] FEHLER: is_ollama_running hat die Aufgabe nicht erfüllt. Grund: Port nicht erreichbar.")
            return False
        print("[class_tool_ollama_service_manager] Erfolg: is_ollama_running erfolgreich beendet.")
        return result

    @classmethod
    def get_available_models(cls, ollama_host: str = None) -> list:
        """Fragt alle lokal installierten Modelle von Ollama ab."""
        print("[class_tool_ollama_service_manager] Starte Arbeit: get_available_models wird jetzt ausgeführt.")
        ollama_host = ollama_host or cls.OLLAMA_HOST
        try:
            req = urllib.request.Request(f"{ollama_host}/api/tags")
            with urllib.request.urlopen(req, timeout=cls.API_TIMEOUT) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    result = [m.get("name") for m in data.get("models", []) if m.get("name")]
                    print("[class_tool_ollama_service_manager] Erfolg: get_available_models erfolgreich beendet.")
                    return result
        except Exception as e:
            print(f"[class_tool_ollama_service_manager] FEHLER: Konnte Modell-Liste nicht abrufen: {e}")
        print("[class_tool_ollama_service_manager] Erfolg: get_available_models erfolgreich beendet.")
        return []

    @classmethod
    def get_available_local_models(cls) -> dict:
        """
        Ruft alle aktiv bei Ollama registrierten Modelle direkt über die API ab,
        nutzt die globalen Host-Einstellungen aus _AGENT_CONFIG, ermittelt deren 
        Dateigröße und gibt ein Dictionary zurück ({name: größe_gb}).
        Prüft zusätzlich das lokale Projektverzeichnis auf .gguf-Dateien.
        """
        print('get_available_local_models')
        local_models_dict = {}
        
        try:
            client = ollama.Client(host=cls.OLLAMA_HOST)
            response = client.list()
            models_info = response.get('models', []) if isinstance(response, dict) else getattr(response, 'models', [])
            if not models_info:
                print("  Keine Modelle in Ollama registriert gefunden.")
            for m in models_info:
                name = m.get('model') if isinstance(m, dict) else getattr(m, 'model', str(m))
                size_bytes = m.get('size', 0) if isinstance(m, dict) else getattr(m, 'size', 0)
                if name:
                    size_gb = size_bytes / (1024 ** 3) if size_bytes else 0.0
                    local_models_dict[name] = size_gb
                    print(f"  - {name} ({size_gb:.2f} GB)")
        except Exception as e:
            print(f"[Fehler beim Abrufen der Ollama-Modelle von {cls.OLLAMA_HOST}]: {e}")
        models_path = Path(cls.PROJECT_MODELS_DIR)
        if not models_path.exists() and Path("data/models").exists():
            models_path = Path("data/models")
        if models_path.exists() and models_path.is_dir():
            gguf_files = list(models_path.rglob("*.gguf"))
            if gguf_files:
                for file_path in gguf_files:
                    size_gb = file_path.stat().st_size / (1024 ** 3)
                    print(f"  - {file_path.name} ({size_gb:.2f} GB)")
            else:
                print(f"  Keine .gguf-Modelldateien in '{models_path.resolve()}' gefunden.")
        else:
            print(f"  Verzeichnis '{cls.PROJECT_MODELS_DIR}' wurde nicht gefunden.")
        return local_models_dict

    @classmethod
    def resolve_model(cls, preferred_model: str = None, ollama_host: str = None) -> str:
        """Wählt das bestmögliche verfügbare Modell anhand von Prioritäten aus."""
        print(f"[class_tool_ollama_service_manager] Starte Arbeit: resolve_model wird jetzt ausgeführt. (Parameter: {preferred_model})")
        preferred_model = preferred_model or cls.MODEL
        ollama_host = ollama_host or cls.OLLAMA_HOST
        available = cls.get_available_models(ollama_host)
        if not available:
            print("[class_tool_ollama_service_manager] Erfolg: resolve_model erfolgreich beendet.")
            return preferred_model

        for m in available:
            if m.lower() == preferred_model.lower() or m.lower().startswith(f"{preferred_model.lower()}:"):
                print("[class_tool_ollama_service_manager] Erfolg: resolve_model erfolgreich beendet.")
                return m
        for fb in cls.FALLBACK_MODELS:
            for m in available:
                if m.lower() == fb.lower() or m.lower().startswith(f"{fb.lower()}:"):
                    print("[class_tool_ollama_service_manager] Erfolg: resolve_model erfolgreich beendet.")
                    return m
        result = available[0]
        print("[class_tool_ollama_service_manager] Erfolg: resolve_model erfolgreich beendet.")
        return result

    @classmethod
    def get_client(cls, ollama_host: str = None):
        """Erstellt einen ollama-Python-Client."""
        print("[class_tool_ollama_service_manager] Starte Arbeit: get_client wird jetzt ausgeführt.")
        ollama_host = ollama_host or cls.OLLAMA_HOST
        if not cls.ensure_ollama_running(ollama_host):
            return None
        try:
            from ollama import Client
            client = Client(host=ollama_host)
            client.list()
            result = client
        except Exception as e:
            print(f"[class_tool_ollama_service_manager] FEHLER: Client-Erstellung fehlgeschlagen: {e}")
            return None
        if result is None:
            print("[class_tool_ollama_service_manager] FEHLER: get_client hat die Aufgabe nicht erfüllt. Grund: Kein Client erstellt.")
            return None
        print("[class_tool_ollama_service_manager] Erfolg: get_client erfolgreich beendet.")
        return result

    @classmethod
    def chat(cls, messages: list, model: str = None, ollama_host: str = None) -> dict:
        """Führt eine Chat-Inferenz über Ollama aus."""
        print("[class_tool_ollama_service_manager] Starte Arbeit: chat wird jetzt ausgeführt.")
        with cls._inference_lock:
            ollama_host = ollama_host or cls.OLLAMA_HOST
            if not cls.ensure_ollama_running(ollama_host):
                print(f"[class_tool_ollama_service_manager] FEHLER: Ollama Server {ollama_host} nicht erreichbar.")
                return {"status": "FAILED", "content": "", "error": f"Ollama Server {ollama_host} nicht erreichbar."}
            available = cls.get_available_models(ollama_host)
            if not available:
                print(f"[class_tool_ollama_service_manager] FEHLER: Keine Modelle in Ollama installiert auf {ollama_host}. Bitte ein Modell herunterladen.")
                return {"status": "FAILED", "content": "", "error": "Keine Modelle in Ollama installiert. Bitte ein Modell herunterladen (z. B. 'ollama pull <model>')."}
            client = cls.get_client(ollama_host)
            if not client:
                print("[class_tool_ollama_service_manager] FEHLER: Ollama Client nicht verfügbar.")
                return {"status": "FAILED", "content": "", "error": "Ollama not available"}
            target_model = cls.resolve_model(model, ollama_host)
            try:
                response = client.chat(model=target_model, messages=messages)
                content = response.get("message", {}).get("content", "")
                content = cls.clean_model_response(content)
                result = {"status": "SUCCESS", "content": content, "model": target_model}
            except Exception as e:
                print(f"[class_tool_ollama_service_manager] FEHLER: Chat-Inferenz fehlgeschlagen: {e}")
                return {"status": "FAILED", "content": "", "error": str(e), "model": target_model}
        if result is None:
            print("[class_tool_ollama_service_manager] FEHLER: chat hat die Aufgabe nicht erfüllt. Grund: Kein Ergebnis.")
            return {"status": "FAILED", "content": "", "error": "Kein Ergebnis"}
        print("[class_tool_ollama_service_manager] Erfolg: chat erfolgreich beendet.")
        return result

    @classmethod
    def generate(cls, prompt: str, model: str = None, ollama_host: str = None) -> dict:
        """Führt eine Text-Generierung über Ollama aus."""
        print("[class_tool_ollama_service_manager] Starte Arbeit: generate wird jetzt ausgeführt.")
        with cls._inference_lock:
            ollama_host = ollama_host or cls.OLLAMA_HOST
            if not cls.ensure_ollama_running(ollama_host):
                print(f"[class_tool_ollama_service_manager] FEHLER: Ollama Server {ollama_host} nicht erreichbar.")
                return {"status": "FAILED", "content": "", "error": f"Ollama Server {ollama_host} nicht erreichbar."}
            available = cls.get_available_models(ollama_host)
            if not available:
                print(f"[class_tool_ollama_service_manager] FEHLER: Keine Modelle in Ollama installiert auf {ollama_host}. Bitte ein Modell herunterladen.")
                return {"status": "FAILED", "content": "", "error": "Keine Modelle in Ollama installiert. Bitte ein Modell herunterladen (z. B. 'ollama pull <model>')."}
            client = cls.get_client(ollama_host)
            if not client:
                print("[class_tool_ollama_service_manager] FEHLER: Ollama Client nicht verfügbar.")
                return {"status": "FAILED", "content": "", "error": "Ollama not available"}
            target_model = cls.resolve_model(model, ollama_host)
            try:
                response = client.generate(model=target_model, prompt=prompt)
                content = response.get("response", "")
                content = cls.clean_model_response(content)
                result = {"status": "SUCCESS", "content": content, "model": target_model}
            except Exception as e:
                print(f"[class_tool_ollama_service_manager] FEHLER: Text-Generierung fehlgeschlagen: {e}")
                return {"status": "FAILED", "content": "", "error": str(e), "model": target_model}
        if result is None:
            print("[class_tool_ollama_service_manager] FEHLER: generate hat die Aufgabe nicht erfüllt. Grund: Kein Ergebnis.")
            return {"status": "FAILED", "content": "", "error": "Kein Ergebnis"}
        print("[class_tool_ollama_service_manager] Erfolg: generate erfolgreich beendet.")
        return result

    @classmethod
    def pull_model(cls, model_name: str, ollama_host: str = None) -> dict:
        """Lädt ein Modell über die Ollama API herunter."""
        print(f"[class_tool_ollama_service_manager] Starte Arbeit: pull_model wird jetzt ausgeführt. (Parameter: {model_name})")
        with cls._inference_lock:
            ollama_host = ollama_host or cls.OLLAMA_HOST
            if not cls.ensure_ollama_running(ollama_host):
                print(f"[class_tool_ollama_service_manager] FEHLER: Ollama Host {ollama_host} nicht erreichbar.")
                return {"status": "FAILED", "error": f"Ollama host {ollama_host} not reachable."}
            url = f"{ollama_host}/api/pull"
            payload = json.dumps({"name": model_name, "stream": False}).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=300) as resp:
                    raw_body = resp.read().decode("utf-8")
                    try:
                        result = json.loads(raw_body)
                    except json.JSONDecodeError:
                        result = {"status": resp.status, "raw": raw_body}
            except Exception as e:
                print(f"[class_tool_ollama_service_manager] FEHLER: Modell-Download fehlgeschlagen: {e}")
                return {"status": "FAILED", "error": str(e)}
        if result is None:
            print("[class_tool_ollama_service_manager] FEHLER: pull_model hat die Aufgabe nicht erfüllt. Grund: Kein Ergebnis.")
            return {"status": "FAILED", "error": "Kein Ergebnis"}
        print("[class_tool_ollama_service_manager] Erfolg: pull_model erfolgreich beendet.")
        return result

    @classmethod
    def call_ollama(cls, endpoint: str, payload: dict, agent_title: str = "Ollama",
                    timeout_sec: int = 1800, ollama_host: str = None) -> tuple:
        """Führt einen rohen REST-API-Aufruf an Ollama mit Terminal-Spinner aus."""
        print(f"[class_tool_ollama_service_manager] Starte Arbeit: call_ollama wird jetzt ausgeführt. (Parameter: {endpoint})")
        with cls._inference_lock:
            ollama_host = ollama_host or cls.OLLAMA_HOST
            url = f"{ollama_host}{endpoint}"
            try:
                data = json.dumps(payload).encode("utf-8")
            except Exception as e:
                print(f"[class_tool_ollama_service_manager] FEHLER: Payload-Codierung fehlgeschlagen: {e}")
                return False, {"error": str(e)}

            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            spinner_module = globals().get("class_tool_resource_aware_spinner")
            spinner = spinner_module(agent_name=agent_title, spinner_interval=1.0) if spinner_module else None
            stop_event = threading.Event() if spinner else None
            spinner_thread = None
            if spinner and stop_event:
                spinner_thread = threading.Thread(target=spinner.run, args=(stop_event, True))
                spinner_thread.daemon = True
                spinner_thread.start()

            try:
                with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                    if resp.status == 200:
                        res_data = json.loads(resp.read().decode("utf-8"))
                        print("[class_tool_ollama_service_manager] Erfolg: call_ollama erfolgreich beendet.")
                        return True, res_data
                    print("[class_tool_ollama_service_manager] FEHLER: call_ollama hat die Aufgabe nicht erfüllt. Grund: HTTP-Fehler.")
                    return False, {"error": f"HTTP Status {resp.status}"}
            except Exception as e:
                print(f"[class_tool_ollama_service_manager] FEHLER: Ollama REST-Aufruf fehlgeschlagen: {e}")
                return False, {"error": str(e)}
            finally:
                if stop_event:
                    stop_event.set()
                if spinner_thread:
                    spinner_thread.join()

    @classmethod
    def run_agent(cls, task_or_fn, *args, agent_title: str = "Agent",
                  model: str = None, ollama_host: str = None,
                  min_ram_mb: int = 2000, max_cpu_threshold: float = 90.0,
                  spinner_interval: float = 1.0, **kwargs):
        """Führt eine Agenten-Funktion oder LLM-Anfrage mit gekoppeltem Terminal-Spinner aus."""
        print(f"[class_tool_ollama_service_manager] Starte Arbeit: run_agent wird jetzt ausgeführt. (Parameter: {agent_title})")
        spinner_module = globals().get("class_tool_resource_aware_spinner")
        spinner = None
        if spinner_module:
            try:
                spinner = spinner_module(agent_name=agent_title, min_ram_mb=min_ram_mb,
                                        max_cpu_threshold=max_cpu_threshold, spinner_interval=spinner_interval)
            except Exception:
                spinner = None

        stop_event = threading.Event() if spinner else None
        spinner_thread = None
        if spinner and stop_event:
            spinner_thread = threading.Thread(target=spinner.run, args=(stop_event, True))
            spinner_thread.daemon = True
            spinner_thread.start()

        try:
            if callable(task_or_fn):
                result = task_or_fn(*args, **kwargs)
            elif isinstance(task_or_fn, list):
                result = cls.chat(messages=task_or_fn, model=model, ollama_host=ollama_host)
            elif isinstance(task_or_fn, str):
                result = cls.generate(prompt=task_or_fn, model=model, ollama_host=ollama_host)
            elif isinstance(task_or_fn, dict):
                endpoint = kwargs.get("endpoint", "/api/generate")
                result = cls.call_ollama(endpoint=endpoint, payload=task_or_fn, agent_title=agent_title, ollama_host=ollama_host)
            else:
                print(f"[class_tool_ollama_service_manager] FEHLER: Nicht unterstützter Typ: {type(task_or_fn)}")
                result = None
            print("[class_tool_ollama_service_manager] Erfolg: run_agent erfolgreich beendet.")
            return result
        finally:
            if stop_event:
                stop_event.set()
            if spinner_thread:
                spinner_thread.join()

    @classmethod
    def get_active_model(cls, preferred_patterns: list = None, exclude_patterns: list = None,
                         fallback_default: str = "hermes", ollama_host: str = None) -> str:
        """Ermittelt das optimale lokale LLM unter Ausschluss unerwünschter Muster."""
        print("[class_tool_ollama_service_manager] Starte Arbeit: get_active_model wird jetzt ausgeführt.")
        ollama_host = ollama_host or cls.OLLAMA_HOST
        preferred_patterns = preferred_patterns or ["hermes", "qwen", "coder", "instruct"]
        exclude_patterns = exclude_patterns or ["671b", "deepseek-v3"]
        try:
            req = urllib.request.Request(f"{ollama_host}/api/tags", headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=cls.API_TIMEOUT) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    model_names = [m.get("name") for m in data.get("models", []) if isinstance(m, dict) and "name" in m]
                    valid = [m for m in model_names if not any(ex in m.lower() for ex in exclude_patterns)]
                    if not valid:
                        valid = model_names
                    for pat in preferred_patterns:
                        for name in valid:
                            if pat.lower() in name.lower():
                                print("[class_tool_ollama_service_manager] Erfolg: get_active_model erfolgreich beendet.")
                                return name
                    if valid:
                        print("[class_tool_ollama_service_manager] Erfolg: get_active_model erfolgreich beendet.")
                        return valid[0]
        except Exception as e:
            print(f"[class_tool_ollama_service_manager] FEHLER: get_active_model fehlgeschlagen: {e}")
        print("[class_tool_ollama_service_manager] Erfolg: get_active_model erfolgreich beendet.")
        return fallback_default
    
    @classmethod
    def select_active_models(cls,query: str) -> list:
        """
        Ermittelt den Schwerpunkt der Benutzeranfrage und wählt 
        die passenden Modelle direkt aus den globalen Variablen aus.
        """
        print('select_active_models')
        normalized_query = query.lower()
        is_code = any(kw in normalized_query for kw in ["code", "python", "script", "funktion", "bug", "programm"])
        is_logic = any(kw in normalized_query for kw in ["warum", "analysiere", "berechne", "logik", "vergleiche", "strategie"])
        if is_code:
            return [cls.OLAMA_MODEL_CODE_LOW, cls.OLAMA_MODEL_CODE_HIGH, cls.OLAMA_MODEL_TEXT_LOW]
        elif is_logic:
            return [cls.OLAMA_MODEL_LOGIC_LOW, cls.OLAMA_MODEL_LOGIC_HIGH, cls.OLAMA_MODEL_TEXT_LOW]
        else:
            return [cls.OLAMA_MODEL_TEXT_LOW, cls.OLAMA_MODEL_LOGIC_LOW, cls.OLAMA_MODEL_TEXT_HIGH]

    @classmethod
    def is_valid_model_name(name: str) -> bool:
        """Validiert einen Modellnamen gemäß den Namenskonventionen von Ollama."""
        print(f"[class_tool_ollama_service_manager] Starte Arbeit: is_valid_model_name wird jetzt ausgeführt. (Parameter: {name})")
        if not name or not isinstance(name, str):
            print("[class_tool_ollama_service_manager] FEHLER: is_valid_model_name hat die Aufgabe nicht erfüllt. Grund: Ungültiger Name.")
            return False
        pattern = re.compile(r"^(?:[a-z0-9]+(?:[._-][a-z0-9]+)*/)?([a-z0-9]+(?:[._-][a-z0-9]+)*)(?::([a-z0-9]+(?:[._-][a-z0-9]+)*))?$")
        result = bool(pattern.match(name.strip()))
        if result is False or result is None:
            print("[class_tool_ollama_service_manager] FEHLER: is_valid_model_name hat die Aufgabe nicht erfüllt. Grund: Name entspricht nicht dem Muster.")
            return False
        print("[class_tool_ollama_service_manager] Erfolg: is_valid_model_name erfolgreich beendet.")
        return result

    @classmethod
    def sanitize_model_name(cls, raw_name: str, fallback: str = "custom-model") -> str:
        """Normalisiert einen Roh-String in einen validen Ollama-Modellnamen."""
        print(f"[class_tool_ollama_service_manager] Starte Arbeit: sanitize_model_name wird jetzt ausgeführt. (Parameter: {raw_name})")
        if not raw_name or not isinstance(raw_name, str):
            print("[class_tool_ollama_service_manager] Erfolg: sanitize_model_name erfolgreich beendet.")
            return fallback
        clean = raw_name.strip()
        for ext in (".gguf", ".bin", ".safetensors", ".pt", ".onnx", ".ckpt", ".tar.gz", ".tgz", ".zip"):
            if clean.lower().endswith(ext):
                clean = clean[:-len(ext)]
                break
        umlaut_map = {"ä": "ae", "Ä": "ae", "ö": "oe", "Ö": "oe", "ü": "ue", "Ü": "ue", "ß": "ss"}
        for k, v in umlaut_map.items():
            clean = clean.replace(k, v)
        clean = re.sub(r"[^a-z0-9\.\\_\\-\\:\\/]", "-", clean.lower())
        clean = re.sub(r"-+", "-", clean).strip("-._")
        result = clean or fallback
        if not result or not isinstance(result, str):
            print("[class_tool_ollama_service_manager] FEHLER: sanitize_model_name hat die Aufgabe nicht erfüllt. Grund: Leeres Ergebnis.")
            return fallback
        print("[class_tool_ollama_service_manager] Erfolg: sanitize_model_name erfolgreich beendet.")
        return result

    @classmethod
    def clean_model_response(cls, raw_content: str) -> str:
        """Entfernt interne Denkblöcke (<think>...</think>) und bereinigt Modellantworten."""
        print("[class_tool_ollama_service_manager] Starte Arbeit: clean_model_response wird jetzt ausgeführt.")
        if not raw_content or not isinstance(raw_content, str):
            print("[class_tool_ollama_service_manager] Erfolg: clean_model_response erfolgreich beendet.")
            return ""
        cleaned = re.sub(r"<think>.*?</think>", "", raw_content, flags=re.DOTALL).strip()
        result = cleaned if cleaned else raw_content.strip()
        print("[class_tool_ollama_service_manager] Erfolg: clean_model_response erfolgreich beendet.")
        return result

    @classmethod
    def run_ollama_manager(cls, preferred_model: str = None, ollama_host: str = None) -> dict:
        """
        Zentrale Ausführungsfunktion: Bündelt die Initialisierung des Ollama-Managers,
        prüft den Dienst, löst das Zielmodell auf und liefert die Inferenzkonfiguration zurück.
        """
        print("[class_tool_ollama_service_manager] Starte Arbeit: run_ollama_manager wird jetzt ausgeführt.")
        try:
            running = cls.ensure_ollama_running(ollama_host)
            if not running:
                print("[class_tool_ollama_service_manager] FEHLER: Dienst konnte nicht gestartet werden.")
                return {"ready": False, "model": None, "host": ollama_host or cls.OLLAMA_HOST}
            active_model = cls.resolve_model(preferred_model, ollama_host)
            result = {
                "ready": True,
                "model": active_model,
                "host": ollama_host or cls.OLLAMA_HOST,
                "available_models": cls.get_available_models(ollama_host)
            }
        except Exception as e:
            print(f"[class_tool_ollama_service_manager] FEHLER: In run_ollama_manager: {e}")
            return None
        if result is None:
            print("[class_tool_ollama_service_manager] FEHLER: run_ollama_manager hat die Aufgabe nicht erfüllt. Grund: Kein Ergebnis.")
            return None
        print("[class_tool_ollama_service_manager] Erfolg: run_ollama_manager erfolgreich beendet.")
        return result
