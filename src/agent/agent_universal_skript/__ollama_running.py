import os
import sys
import subprocess
import time
import urllib.request
import socket

# ═══════════════════════════════════════════════════════════════
# KONFIGURIERBARE PARAMETER
# ═══════════════════════════════════════════════════════════════
DEFAULT_OLLAMA_HOST = "http://127.0.0.1"
DEFAULT_OLLAMA_PORT = 11434
SOCKET_TIMEOUT = 1.0
API_TIMEOUT = 2
MAX_START_RETRIES = 3
RETRY_WAIT_SEC = 3

# Modulinterner RAM-Merker: Speichert, ob Ollama in dieser Session bereits erfolgreich verifiziert wurde
_OLLAMA_VERIFIED_CACHE = False

def is_port_open(host: str, port: int, timeout: float = SOCKET_TIMEOUT) -> bool:
    """Schneller Socket-Check, ob der Port überhaupt erreichbar ist (Best Practice)."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False

def check_and_start_ollama(ollama_host: str = None) -> bool:
    """
    Prüft autonom den Status von Ollama (inkl. RAM-Cache), startet den Dienst 
    bei Bedarf im Hintergrund und gibt absolut KEINE Meldungen bei Erfolg aus.
    """
    global _OLLAMA_VERIFIED_CACHE

    if ollama_host is None:
        ollama_host = f"{DEFAULT_OLLAMA_HOST}:{DEFAULT_OLLAMA_PORT}"

    # 0. Schritt: RAM-Cache prüfen – Wenn in dieser Session bereits erfolgreich, sofort still abbrechen
    if _OLLAMA_VERIFIED_CACHE:
        return True

    # Host und Port für den Socket-Check extrahieren
    host_ip = ollama_host.replace("http://", "").replace("https://", "").split(":")[0]
    try:
        port = int(ollama_host.split(":")[-1])
    except ValueError:
        port = DEFAULT_OLLAMA_PORT

    # 1. Schritt: Minimaler Aufwand – Socket- und API-Schnelltest
    if is_port_open(host_ip, port, timeout=SOCKET_TIMEOUT):
        try:
            req = urllib.request.Request(f"{ollama_host}/api/tags")
            with urllib.request.urlopen(req, timeout=API_TIMEOUT) as response:
                if response.status == 200:
                    _OLLAMA_VERIFIED_CACHE = True
                    return True
        except Exception:
            pass

    # 2. Schritt: Mittlerer Aufwand – Versuche, den Dienst im Hintergrund zu starten (ohne Ausgaben)
    try:
        if os.name == 'nt':
            subprocess.Popen(["ollama", "serve"], creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        # Nur im echten Fehlerfall (Ollama nicht gefunden) Logs ausgeben
        print("--- [OLLAMA CHECK] Fehler-Protokoll ---")
        print("--> [FEHLER] Der Befehl 'ollama' wurde im System nicht gefunden.")
        print("--> [HINWEIS] Ollama scheint nicht installiert zu sein oder der Pfad stimmt nicht.")
        print("--> Bitte installiere Ollama (https://ollama.com/download) oder löse den Start manuell aus.")
        return False
    except Exception as sub_err:
        # Nur im echten Fehlerfall Logs ausgeben
        print("--- [OLLAMA CHECK] Fehler-Protokoll ---")
        print(f"--> [FEHLER] Konnte den Ollama-Prozess nicht automatisch starten: {sub_err}")
        return False

    # 3. Schritt: Warten und verifizieren, ob der automatische Start erfolgreich war
    for attempt in range(1, MAX_START_RETRIES + 1):
        time.sleep(RETRY_WAIT_SEC)
        if is_port_open(host_ip, port, timeout=SOCKET_TIMEOUT):
            try:
                req = urllib.request.Request(f"{ollama_host}/api/tags")
                with urllib.request.urlopen(req, timeout=API_TIMEOUT) as response:
                    if response.status == 200:
                        _OLLAMA_VERIFIED_CACHE = True  # Erfolgreich im RAM merken – absolut still
                        return True
            except Exception:
                pass

    # Wenn nach mehreren Versuchen immer noch nichts erreichbar ist -> Erst jetzt das Fehler-Protokoll zeigen
    print("--- [OLLAMA CHECK] Fehler-Protokoll ---")
    print("--> [HINWEIS] Ollama ist nach mehreren Versuchen immer noch nicht erreichbar.")
    print("--> Bitte starte Ollama manuell oder prüfe deine Installation.")
    return False

if __name__ == "__main__":
    check_and_start_ollama()