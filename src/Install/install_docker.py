import platform
import urllib.request
import os
import subprocess
import tempfile
import sys
import shutil
import importlib  # Verhindert, dass Jupyter das neu installierte Modul übersieht

# =========================================================================
# 1. ERZWUNGENE & INTELLIGENTE MODUL-PRÜFUNG FÜR 'MAIOMNI'
# =========================================================================
try:
    import docker
    print("[✓] Das Python-Modul 'docker' ist bereits in 'MaiOmni' aktiv.")
except ImportError:
    print("[!] Python-Modul 'docker' nicht gefunden. Installiere direkt in 'MaiOmni'...")
    try:
        # sys.executable stellt sicher, dass exakt die MaiOmni-Umgebung getroffen wird
        subprocess.check_call([sys.executable, "-m", "pip", "install", "docker"])
        
        # Wichtig für Jupyter: Pfad-Caches leeren, damit das Modul sofort importierbar ist
        importlib.invalidate_caches()
        import docker
        print("[✓] Das Python-Modul 'docker' wurde erfolgreich für 'MaiOmni' geladen!")
    except Exception as e:
        print(f"[!] Kritischer Fehler bei der Modul-Installation: {e}")
        print("-> Falls dieser Fehler anhält, führe eine separate Zelle mit '%pip install docker' aus.")
        sys.exit(1)

print("Alle notwendigen Module wurden erfolgreich geladen.\n")

# =========================================================================
# 2. DEINE ORIGINAL-LOGIK (VOLLSTÄNDIG ERHALTEN)
# =========================================================================

def progress_bar(count, block_size, total_size):
    """
    Berechnet den aktuellen Fortschritt und gibt einen Live-Ladebalken aus.
    Kompatibel mit Jupyter Notebook (.ipynb).
    """
    if total_size <= 0:
        sys.stdout.write("\rLade herunter... (Größe unbekannt)")
        sys.stdout.flush()
        return

    downloaded = count * block_size
    percent = min(int(downloaded * 100 / total_size), 100)
    downloaded_mb = downloaded / (1024 * 1024)
    total_mb = total_size / (1024 * 1024)
    
    bar_length = 30
    filled_length = int(round(bar_length * percent / 100))
    bar = '█' * filled_length + '-' * (bar_length - filled_length)
    
    sys.stdout.write(f"\rFortschritt: [{bar}] {percent}% ({downloaded_mb:.1f} / {total_mb:.1f} MB)")
    sys.stdout.flush()


def check_docker_status():
    """
    Überprüft logisch den Zustand von Docker auf dem System.
    Gibt (cli_installed, daemon_running) als Boolean-Tupel zurück.
    """
    cli_installed = shutil.which("docker") is not None
    daemon_running = False
    
    if cli_installed:
        try:
            # 'docker info' validiert, ob die Engine antwortet
            subprocess.check_output(["docker", "info"], stderr=subprocess.DEVNULL)
            daemon_running = True
        except subprocess.CalledProcessError:
            daemon_running = False
            
    return cli_installed, daemon_running


def download_and_install_docker_smart():
    os_name = platform.system()
    arch = platform.machine()
    
    # 1. Vorab-Prüfung: Ist Docker schon aktiv?
    print("--- Prüfe System-Umgebung ---")
    cli_installed, daemon_running = check_docker_status()
    
    if cli_installed and daemon_running:
        print("[✓] Docker ist bereits installiert und aktiv. Keine Aktion erforderlich.\n")
        return
    elif cli_installed and not daemon_running:
        print("[!] Docker CLI gefunden, aber der Docker-Daemon schläft.")
        print("-> Bitte starte 'Docker Desktop' manuell über deine Anwendungen.\n")
        return
    
    print("[-] Docker wurde nicht im Systempfad gefunden. Bereite Setup vor...")

    # 2. Dynamische Links bestimmen
    if os_name == "Darwin":  # macOS
        if "arm" in arch.lower() or "chroot" in arch.lower():
            print("Hardware-Erkennung: Apple Silicon (M1/M2/M3/...)")
            url = "https://desktop.docker.com/mac/main/arm64/Docker.dmg"
        else:
            print("Hardware-Erkennung: Intel Mac")
            url = "https://desktop.docker.com/mac/main/amd64/Docker.dmg"
        filename = "Docker.dmg"
        
    elif os_name == "Windows":
        print("Hardware-Erkennung: Windows PC")
        url = "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe"
        filename = "Docker_Installer.exe"
    else:
        print(f"Abbruch: Betriebssystem {os_name} wird nicht unterstützt.")
        return

    # 3. System-Temp-Ordner nutzen
    temp_dir = tempfile.gettempdir()
    full_path = os.path.join(temp_dir, filename)

    # Prüfung auf existierende Datei vor Download
    if os.path.exists(full_path):
        print(f"\n[i] Installationsdatei bereits lokal gefunden unter: {full_path}")
        print("-> Überspringe Download und fahre direkt mit der Installation fort.\n")
    else:
        print(f"\nNutze temporären Speicherpfad: {full_path}")
        print(f"Hole aktuellste Version von Docker-Servern...")
        try:
            urllib.request.urlretrieve(url, full_path, reporthook=progress_bar)
            print("\n\nDownload temporär erfolgreich abgeschlossen.")
        except Exception as e:
            print("\n\n[!] FEHLER beim Download!")
            print(f"Die Docker-Downloadseite ist unter diesem Link nicht erreichbar: {e}")
            return

    # 4. Installationsprozess starten
    print("Starte Installationsprozess...")
    dmg_mounted = False # Status-Flag für sauberes Unmounten
    installation_successful = False # Status-Flag für intelligentes Aufräumen
    
    try:
        if os_name == "Darwin":
            print("Mounte DMG im Hintergrund...")
            try:
                # capture_output=True fängt Fehlermeldungen ab, falls die DMG korrupt ist
                subprocess.run(["hdiutil", "attach", full_path, "-nobrowse"], check=True, capture_output=True, text=True)
                dmg_mounted = True
            except subprocess.CalledProcessError as mount_error:
                # Logische Erkennung einer beschädigten / unvollständigen DMG-Datei
                error_msg = (mount_error.stderr or "").lower()
                if "no mountable file systems" in error_msg or "keine aktivierbaren dateisysteme" in error_msg:
                    print("\n[!] LOGIK-STOPP: Die gefundene Datei ist korrupt (unvollständiger Download).")
                    print("-> Lösche die fehlerhafte Datei automatisch, um Platz für den Neustart zu machen...")
                    if os.path.exists(full_path):
                        os.remove(full_path)
                    print("[✓] Gelöscht. Bitte starte das Skript einfach noch einmal, um frisch herunterzuladen.\n")
                    return
                else:
                    # Wenn es ein anderer Fehler war (z.B. Rechte), werfen wir ihn weiter
                    raise mount_error
            
            source_app = "/Volumes/Docker/Docker.app"
            if os.path.exists(source_app):
                print("Kopiere Docker in den Programme-Ordner... (Das kann kurz dauern)")
                subprocess.run(["cp", "-R", source_app, "/Applications"], check=True)
                print("[✓] Docker erfolgreich unter /Applications abgelegt!")
                installation_successful = True
            else:
                print("[!] Fehler: DMG wurde gemountet, aber Docker.app fehlt im Volume.")
            
        elif os_name == "Windows":
            print("Öffne Windows-Installationsassistenten...")
            os.startfile(full_path)
            print("Bitte folge den Anweisungen auf dem Bildschirm.")
            installation_successful = True

    except Exception as e:
        print(f"\n[!] Fehler während der Installation: {e}")
        print("Hinweis: Ggf. wurden Admin-Rechte verweigert oder der Kopiervorgang wurde abgebrochen.")
        
    finally:
        # =========================================================================
        # ABSOLUT SICHERES & INTELLIGENTES AUFRÄUMEN
        # =========================================================================
        if os_name == "Darwin" and dmg_mounted:
            print("Werfe Image wieder aus...")
            try:
                subprocess.run(["hdiutil", "detach", "/Volumes/Docker"], check=True)
            except Exception as detach_error:
                print(f"Warnung beim Auswerfen der DMG: {detach_error}")

        # Datei löschen wenn alles geklappt hat
        if os.path.exists(full_path) and installation_successful:
            print("Räume Installationsdatei auf, um Speicherplatz freizugeben...")
            try:
                os.remove(full_path)
                print("[✓] Temporäre Datei erfolgreich gelöscht!")
            except Exception as e:
                print(f"Fehler beim Löschen der Temp-Datei: {e}")
        elif os.path.exists(full_path) and not installation_successful:
            print(f"[i] Datei unter {full_path} wurde für spätere Installationsversuche beibehalten.")


if __name__ == "__main__":
    download_and_install_docker_smart()