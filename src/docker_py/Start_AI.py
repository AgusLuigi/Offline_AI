import os
import subprocess
import sys
import logging
from src.Install.folder_index import initialize_project, FOLDER_STRUCTURE
from src.Install.install_docker import download_and_install_docker_smart
from src.Install.ollama_hardware_downloader import smart_hardware_downloader

# Zentrales Logging für den Startvorgang
logger = logging.getLogger("AI_Orchestrator")
logging.basicConfig(level=logging.INFO)

def run_docker_compose():
    """
    Führt docker-compose up -d aus, um das Traefik-Gateway 
    und den Auth-Proxy zu starten.
    """
    project_root = FOLDER_STRUCTURE["root"]
    compose_path = os.path.join(project_root, "docker-compose.yml")

    if not os.path.exists(compose_path):
        logger.error(f"docker-compose.yml nicht gefunden unter: {compose_path}")
        return False

    logger.info("Starte Infrastruktur-Container (Traefik & Auth)...")
    try:
        # Wir nutzen 'docker compose' (V2), Fallback auf 'docker-compose'
        cmd = ["docker", "compose", "-f", compose_path, "up", "-d"]
        subprocess.run(cmd, check=True, cwd=project_root)
        logger.info("[✓] Infrastruktur erfolgreich gestartet.")
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
    print("   OFFLINE AI - SYSTEM STARTSEQUENZ")
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

    # 3. Schritt: Gateway & Proxy starten (Chirurgische Integration der docker-compose)
    logger.info("Schritt 3: Starte Netzwerk-Infrastruktur...")
    if not run_docker_compose():
        print("[!] Abbruch: Docker-Infrastruktur konnte nicht geladen werden.")
        sys.exit(1)

    # 4. Schritt: Hardware-Analyse und Ollama-Modell-Setup
    # Dies geschieht erst, wenn die Basis steht, um Ressourcenkonflikte zu vermeiden
    logger.info("Schritt 4: Analysiere Hardware und bereite KI-Modelle vor...")
    try:
        smart_hardware_downloader()
    except Exception as e:
        logger.error(f"Fehler beim Modell-Download: {e}")
        # Wir brechen hier nicht ab, da das Gateway bereits läuft

    print("\n" + "="*60)
    print("   SYSTEM BEREIT: Greife via http://platform.local zu")
    print("="*60 + "\n")

if __name__ == "__main__":
    # Sicherstellen, dass .env Variablen (GOOGLE_CLIENT_ID etc.) geladen sind
    # Falls du eine .env Datei nutzt, könnte hier 'load_dotenv()' stehen.
    if not os.getenv("GOOGLE_CLIENT_ID"):
        logger.warning("HINWEIS: GOOGLE_CLIENT_ID Umgebungsvariable fehlt. Auth-Proxy wird ggf. nicht starten.")
    
    main()