import os
import subprocess
import sys
import logging
from src.Install.install_folder_index import initialize_project, FOLDER_STRUCTURE
from src.Install.install_docker import download_and_install_docker_smart
from src.Install.active_ollama_hardware_downloader import smart_hardware_downloader
from src.docker_py.docker_config import (
    load_docker_global_config,
    get_network_config,
    get_storage_config
)

# Zentrales Logging für den Startvorgang
logger = logging.getLogger("AI_Orchestrator")
logging.basicConfig(level=logging.INFO)

def verify_external_infrastructure():
    """
    Überprüft vor dem Compose-Start, ob die externen Notebook-Schnittstellen
    (Netzwerk & Volumes aus config/docker_global.json) im Docker-Daemon vorhanden sind.
    Falls nicht, werden sie automatisch angelegt, um Fehler zu vermeiden.
    """
    logger.info("Überprüfe externe Infrastruktur-Kopplung anhand config/docker_global.json...")
    config = load_docker_global_config()
    net_cfg = get_network_config(config)
    storage_cfg = get_storage_config(config)

    network_name = net_cfg.get("name", "mai-ai_network")
    required_volumes = storage_cfg.get("required_volumes", ["mai_ai_local_models", "mai_ai_db_data", "mai_ai_config"])

    try:
        # 1. Netzwerk prüfen
        net_check = subprocess.run(["docker", "network", "inspect", network_name], 
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if net_check.returncode != 0:
            logger.warning(f"Schnittstelle fehlt: Erstelle Netzwerk '{network_name}'...")
            subprocess.run(["docker", "network", "create", network_name], check=True)

        # 2. Volumes prüfen
        for vol in required_volumes:
            vol_check = subprocess.run(["docker", "volume", "inspect", vol], 
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if vol_check.returncode != 0:
                logger.warning(f"Schnittstelle fehlt: Erstelle Volume '{vol}'...")
                subprocess.run(["docker", "volume", "create", vol], check=True)
                
        return True
    except Exception as e:
        logger.error(f"Fehler bei der Infrastruktur-Kopplung: {e}")
        return False

def run_docker_compose():
    """
    Führt docker-compose up -d aus, um die modularisierte Infrastruktur zu starten:
    - Funktionsbereich 1: Reverse Proxy & Ingress (Traefik)
    - Funktionsbereich 2: Security & Identity Provider (OAuth2-Proxy)
    - Funktionsbereich 3: Core AI Computing Engine (Ollama)
    """
    project_root = FOLDER_STRUCTURE["root"]
    compose_path = os.path.join(project_root, "docker-compose.yml")

    if not os.path.exists(compose_path):
        logger.error(f"docker-compose.yml nicht gefunden unter: {compose_path}")
        return False

    # Vorabprüfung der externen Schnittstellen aus Phase 2
    if not verify_external_infrastructure():
        logger.error("Infrastruktur-Kopplung fehlgeschlagen. Breche ab.")
        return False

    logger.info("Starte 3-Funktionsbereiche (Ingress, Security, Engine)...")
    try:
        # Wir nutzen 'docker compose' (V2), Fallback auf 'docker-compose'
        cmd = ["docker", "compose", "-f", compose_path, "up", "-d"]
        subprocess.run(cmd, check=True, cwd=project_root)
        logger.info("[✓] Alle Funktionsbereiche erfolgreich initialisiert.")
        return True
    except subprocess.CalledProcessError:
        try:
            logger.warning("Docker V2 nicht gefunden, versuche Legacy docker-compose...")
            subprocess.run(["docker-compose", "-f", compose_path, "up", "-d"], check=True, cwd=project_root)
            return True
        except Exception as e:
            logger.error(f"Fehler beim Starten von Docker-Compose: {e}")
            return False

def main():
    print("\n" + "="*60)
    print("    OFFLINE AI - SYSTEM STARTSEQUENZ (MAI_AI)")
    print("="*60 + "\n")

    # 1. Schritt: Projektstruktur und Verzeichnisse sicherstellen
    logger.info("Schritt 1: Initialisiere Projektstruktur...")
    initialize_project()

    # Ersteinrichtung / Onboarding falls nicht vorhanden (Jarvis Best Practices)
    if not os.path.exists("config/jarvis_config.json"):
        logger.info("Starte geführtes Jarvis-Onboarding...")
        from src.Jarvis.jarvis_onboarding import run_guided_onboarding
        run_guided_onboarding()

    # 2. Schritt: Docker-Verfügbarkeit prüfen
    logger.info("Schritt 2: Prüfe Docker-Umgebung...")
    download_and_install_docker_smart()

    # 3. Schritt: 3-Funktionsbereiche über Compose starten
    logger.info("Schritt 3: Starte modulare Netzwerk- & Rechen-Infrastruktur...")
    if not run_docker_compose():
        print("[!] Abbruch: Docker-Infrastruktur konnte nicht geladen werden.")
        sys.exit(1)

    # 4. Schritt: Hardware-Analyse und Ollama-Modell-Setup
    logger.info("Schritt 4: Analysiere Hardware und bereite KI-Modelle vor...")
    try:
        smart_hardware_downloader()
    except Exception as e:
        logger.error(f"Fehler beim Modell-Download: {e}")

    print("\n" + "="*60)
    print("   SYSTEM BEREIT: Greife via http://platform.local zu")
    print("="*60 + "\n")

if __name__ == "__main__":
    if not os.getenv("GOOGLE_CLIENT_ID"):
        logger.warning("HINWEIS: GOOGLE_CLIENT_ID Umgebungsvariable fehlt. Auth-Proxy wird ggf. nicht starten.")
    
    main()