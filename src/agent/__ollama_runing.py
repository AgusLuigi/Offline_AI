import os
import sys
import subprocess
import time
import urllib.request
import socket

# Modulinterner RAM-Merker: Speichert, ob Ollama in dieser Session bereits erfolgreich verifiziert wurde
_OLLAMA_VERIFIED_CACHE = False

def is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    """Schneller Socket-Check, ob der Port überhaupt erreichbar ist (Best Practice)."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False

def check_and_start_ollama(ollama_host: str = "http://127.0.0.1:11434") -> bool:
    """
    Prüft autonom den Status von Ollama (inkl. RAM-Cache), startet den Dienst 
    bei Bedarf automatisch und bleibt im Erfolgsfall komplett stumm (Silent Mode).
    """
    global _OLLAMA_VERIFIED_CACHE

    # 0. Schritt: RAM-Cache prüfen – Wenn in dieser Session bereits erfolgreich, direkt abbrechen (still)
    if _OLLAMA_VERIFIED_CACHE:
        return True

    # Host und Port für den Socket-Check extrahieren
    host_ip = ollama_host.replace("http://", "").replace("https://", "").split(":")[0]
    port = int(ollama_host.split(":")[-1]) if ":" in ollama_host else 11434

    # 1. Schritt: Minimaler Aufwand – Socket- und API-Schnelltest
    if is_port_open(host_ip, port, timeout=1.0):
        try:
            req = urllib.request.Request(f"{ollama_host}/api/tags")
            with urllib.request.urlopen(req, timeout=2) as response:
                if response.status == 200:
                    _OLLAMA_VERIFIED_CACHE = True  # Im RAM merken (ohne Print)
                    return True
        except Exception:
            pass

    # 2. Schritt: Mittlerer Aufwand – Versuche, den Dienst automatisch zu starten (ohne Print bei Erfolg)
    try:
        if os.name == 'nt':
            subprocess.Popen(["ollama", "serve"], creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        # Fehlerfall: Das Programm ist nicht vorhanden
        print("--- [OLLAMA CHECK] Fehler-Protokoll ---")
        print("--> [FEHLER] Der Befehl 'ollama' wurde im System nicht gefunden.")
        print("--> [HINWEIS] Ollama scheint nicht installiert zu sein oder der Pfad stimmt nicht.")
        print("--> Bitte installiere Ollama (https://ollama.com/download) oder löse den Start manuell aus.")
        return False
    except Exception as sub_err:
        print("--- [OLLAMA CHECK] Fehler-Protokoll ---")
        print(f"--> [FEHLER] Konnte den Ollama-Prozess nicht automatisch starten: {sub_err}")
        return False

    # 3. Schritt: Warten und verifizieren, ob der automatische Start erfolgreich war
    for attempt in range(1, 4):
        time.sleep(3)
        if is_port_open(host_ip, port, timeout=1.0):
            try:
                req = urllib.request.Request(f"{ollama_host}/api/tags")
                with urllib.request.urlopen(req, timeout=2) as response:
                    if response.status == 200:
                        _OLLAMA_VERIFIED_CACHE = True  # Im RAM merken (ohne Print)
                        return True
            except Exception:
                pass

    # Wenn nach mehreren Versuchen immer noch nichts erreichbar ist (Fehlerfall)
    print("--- [OLLAMA CHECK] Fehler-Protokoll ---")
    print("--> [HINWEIS] Ollama ist nach mehreren Versuchen immer noch nicht erreichbar.")
    print("--> Bitte starte Ollama manuell oder prüfe deine Installation.")
    return False

if __name__ == "__main__":
    check_and_start_ollama()