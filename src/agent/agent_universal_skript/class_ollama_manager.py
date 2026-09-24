import os
import sys
import subprocess
import time
import urllib.request
import json
import socket
from pathlib import Path


class OllamaManager:
    """
    Universeller Manager für Ollama-Dienste und LLM-Inferenz.
    Prüft autonom die Verfügbarkeit, startet Ollama bei Bedarf im Hintergrund,
    ermittelt lokal vorhandene Modelle und steuert Chat-/Generierungsaufrufe fehlertolerant.
    """
    DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"
    DEFAULT_MODEL = "llama3.1"
    FALLBACK_MODELS = ["llama3.1:latest", "codestral:latest", "qwen-3.5:latest"]
    SOCKET_TIMEOUT = 1.0
    API_TIMEOUT = 5.0
    MAX_START_RETRIES = 6
    RETRY_WAIT_SEC = 1.5

    _verified_cache = False

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
        """
        Prüft autonom den Status von Ollama und startet den Dienst bei Bedarf
        vollständig losgelöst im Hintergrund.
        """
        if ollama_host is None:
            ollama_host = cls.DEFAULT_OLLAMA_HOST

        host_ip = ollama_host.replace("http://", "").replace("https://", "").split(":")[0]
        try:
            port = int(ollama_host.split(":")[-1])
        except ValueError:
            port = 11434

        # 1. Schneller Socket- und API-Check
        if cls.is_port_open(host_ip, port, timeout=cls.SOCKET_TIMEOUT):
            try:
                req = urllib.request.Request(f"{ollama_host}/api/tags")
                with urllib.request.urlopen(req, timeout=cls.API_TIMEOUT) as resp:
                    if resp.status == 200:
                        cls._verified_cache = True
                        return True
            except Exception:
                pass

        # 2. Dienst im Hintergrund starten (vollständig entkoppelt)
        try:
            if os.name == "nt":
                # DETACHED_PROCESS (0x00000008) | CREATE_NEW_PROCESS_GROUP (0x00000200) | CREATE_NO_WINDOW (0x08000000)
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
            print("[OLLAMA] Befehl 'ollama' nicht im System gefunden. Bitte installieren: https://ollama.com")
            return False
        except Exception as err:
            print(f"[OLLAMA] Fehler beim Starten des Ollama-Prozesses: {err}")
            return False

        # 3. Warten und verifizieren
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
    def get_available_models(cls, ollama_host: str = None) -> list:
        """Gibt eine Liste aller lokal vorhandenen Ollama-Modellnamen zurück."""
        if ollama_host is None:
            ollama_host = cls.DEFAULT_OLLAMA_HOST
        try:
            req = urllib.request.Request(f"{ollama_host}/api/tags")
            with urllib.request.urlopen(req, timeout=cls.API_TIMEOUT) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    models = [m.get("name") for m in data.get("models", []) if m.get("name")]
                    return models
        except Exception:
            pass
        return []

    @classmethod
    def resolve_model(cls, preferred_model: str = None, ollama_host: str = None) -> str:
        """
        Wählt das beste passende Modell aus den lokal installierten Modellen aus.
        """
        if preferred_model is None:
            preferred_model = cls.DEFAULT_MODEL
        if ollama_host is None:
            ollama_host = cls.DEFAULT_OLLAMA_HOST

        available = cls.get_available_models(ollama_host)
        if not available:
            return preferred_model

        # 1. Bevorzugtes Modell suchen (exakt oder Prefix)
        for m in available:
            if m.lower() == preferred_model.lower() or m.lower().startswith(f"{preferred_model.lower()}:"):
                return m

        # 2. Modell aus den Standard-Fallbacks suchen
        for fb in cls.FALLBACK_MODELS:
            for m in available:
                if m.lower() == fb.lower() or m.lower().startswith(f"{fb.lower()}:"):
                    return m

        # 3. Erstes verfügbares Modell als Fallback
        return available[0]

    @classmethod
    def get_client(cls, ollama_host: str = None):
        """Erstellt einen Ollama-Client, sofern erreichbar."""
        if ollama_host is None:
            ollama_host = cls.DEFAULT_OLLAMA_HOST
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
        """Führt einen Chat-Aufruf über Ollama aus mit automatischer Modellauflösung und Retry."""
        if ollama_host is None:
            ollama_host = cls.DEFAULT_OLLAMA_HOST

        client = cls.get_client(ollama_host)
        if not client:
            return {"status": "FAILED", "content": "", "error": "Ollama nicht erreichbar"}

        target_model = cls.resolve_model(model, ollama_host)

        # Versuch 1
        try:
            response = client.chat(model=target_model, messages=messages)
            content = response.get("message", {}).get("content", "")
            return {"status": "SUCCESS", "content": content, "model": target_model}
        except Exception as e1:
            # Falls Verbindung abgebrochen: Dienst nochmals prüfen und 1 Retry
            cls._verified_cache = False
            if cls.ensure_ollama_running(ollama_host):
                try:
                    retry_client = cls.get_client(ollama_host)
                    if retry_client:
                        response = retry_client.chat(model=target_model, messages=messages)
                        content = response.get("message", {}).get("content", "")
                        return {"status": "SUCCESS", "content": content, "model": target_model}
                except Exception as e2:
                    return {"status": "FAILED", "content": "", "error": str(e2), "model": target_model}

            return {"status": "FAILED", "content": "", "error": str(e1), "model": target_model}

    @classmethod
    def generate(cls, prompt: str, model: str = None, ollama_host: str = None) -> dict:
        """Führt eine Textgenerierung über Ollama aus."""
        if ollama_host is None:
            ollama_host = cls.DEFAULT_OLLAMA_HOST

        client = cls.get_client(ollama_host)
        if not client:
            return {"status": "FAILED", "content": "", "error": "Ollama nicht erreichbar"}

        target_model = cls.resolve_model(model, ollama_host)
        try:
            response = client.generate(model=target_model, prompt=prompt)
            content = response.get("response", "")
            return {"status": "SUCCESS", "content": content, "model": target_model}
        except Exception as e:
            return {"status": "FAILED", "content": "", "error": str(e), "model": target_model}


globals()["OllamaManager"] = OllamaManager
