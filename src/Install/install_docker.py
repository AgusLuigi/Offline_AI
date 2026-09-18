import platform
import urllib.request
import os
import subprocess
import tempfile
import sys
import shutil
import importlib
import winreg
import glob

# 1. ERZWUNGENE & INTELLIGENTE MODUL-PRÜFUNG FÜR 'MAIOMNI'
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

# 2. LOGIK FÜR FORTSCHRITT & DOCKER-STATUS
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

def fix_windows_docker_path():
    """
    Kaskadierte, mehrstufige Logik zur Erkennung und Behebung des Docker-Pfades unter Windows.
    Stufe 1: Standard-Umgebungsvariablen & primäre Installationspfade.
    Stufe 2: Alternative Programm- und Benutzerpfade.
    Stufe 3: Windows-Registrierungs-Scan (Registry-Fallback).
    Stufe 4: Dynamische Erkennung des veränderten Installer-Namens im Temp-Verzeichnis.
    """
    if platform.system() != "Windows":
        return False

    def _add_to_path(target_path):
        """Interne Hilfsfunktion zum sauberen Ergänzen des PATH."""
        if os.path.exists(target_path):
            print(f"[i] Docker-Binärdatei gefunden unter: {target_path}")
            if target_path not in os.environ["PATH"]:
                os.environ["PATH"] += os.path.pathsep + target_path
                print("[✓] Pfad wurde erfolgreich für diese Sitzung ergänzt.")
            return True
        return False

    # --- KASKADE STUFE 1: Primäre Systemvariablen & Standardpfade ---
    print("[i] Kaskade Stufe 1: Prüfe primäre Standardpfade...")
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    local_app_data = os.environ.get("LocalAppData", os.path.expanduser(r"~\AppData\Local"))
    
    stage_1_paths = [
        os.path.join(program_files, "Docker", "Docker", "resources", "bin"),
        os.path.join(local_app_data, "Programs", "Docker", "Docker", "resources", "bin")
    ]
    
    for path in stage_1_paths:
        if _add_to_path(os.path.join(path, "docker.exe")):
            return True

    # --- KASKADE STUFE 2: Alternative / Sekundäre Pfade ---
    print("[i] Kaskade Stufe 2: Prüfe alternative Installationspfade...")
    stage_2_paths = [
        r"C:\Program Files\Docker\Docker",
        os.path.expanduser(r"~\AppData\Local\Docker\cli-plugins")
    ]
    
    for path in stage_2_paths:
        if _add_to_path(os.path.join(path, "docker.exe")):
            return True

    # --- KASKADE STUFE 3: Windows-Registry-Lookup (Professioneller Fallback) ---
    print("[i] Kaskade Stufe 3: Frage Windows-Registrierung ab...")
    registry_hives = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Docker Inc.\Docker Desktop"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Docker Inc.\Docker Desktop")
    ]
    
    for hive, reg_path in registry_hives:
        try:
            with winreg.OpenKey(hive, reg_path) as key:
                install_dir, _ = winreg.QueryValueEx(key, "InstallPath")
                if install_dir:
                    bin_path = os.path.join(install_dir, "resources", "bin")
                    if _add_to_path(os.path.join(bin_path, "docker.exe")):
                        return True
        except Exception:
            continue

    # --- KASKADE STUFE 4: Dynamische Erkennung des veränderten Installer-Namens ---
    print("[i] Kaskade Stufe 4: Suche nach veränderten Installer-Namen im Temp-Ordner...")
    temp_dir = os.environ.get("TEMP", os.path.expanduser(r"~\AppData\Local\Temp"))
    
    # Sucht flexibel nach jeder .exe-Datei, die das Wort 'docker' enthält (egal wie sie umbenannt wurde)
    search_pattern = os.path.join(temp_dir, "*docker*.exe")
    found_installers = glob.glob(search_pattern)
    
    if found_installers:
        # Sortiert nach der aktuellsten Datei, falls mehrere im Temp liegen
        found_installers.sort(key=os.path.getmtime, reverse=True)
        detected_installer_name = found_installers[0]
        print(f"[✓] Veränderten Installer-Namen erfolgreich dynamisch übernommen: {detected_installer_name}")
        
        # Du kannst die gefundene Datei hier direkt an deine Installations-Routine übergeben:
        # global DOCKER_INSTALLER_PATH
        # DOCKER_INSTALLER_PATH = detected_installer_name
        
        return False  # Gibt False zurück, weil Docker noch installiert werden muss, kennt aber jetzt den exakten Dateinamen!
    else:
        print("[!] Kein Installer mit dem Namen im Temp-Ordner gefunden.")

    print("[!] Kaskade beendet: Docker konnte in keinem Systempfad oder der Registry gefunden werden.")
    return False

def download_and_install_docker_smart():
    os_name = platform.system()
    arch = platform.machine()
    
    # 1. Vorab-Prüfung: Ist Docker schon aktiv?
    print("--- Prüfe System-Umgebung ---")
    cli_installed, daemon_running = check_docker_status()
    
    # Automatischer Fix-Versuch für Windows, falls CLI nicht im PATH liegt
    if not cli_installed and os_name == "Windows":
        if fix_windows_docker_path():
            cli_installed, daemon_running = check_docker_status()

    if cli_installed and daemon_running:
        print("[✓] Docker ist bereits installiert und aktiv. Keine Aktion erforderlich.\n")
        return
    elif cli_installed and not daemon_running:
        print("[!] Docker CLI gefunden, aber der Docker-Daemon schläft.")
        print("-> Bitte starte 'Docker Desktop' manuell über deine Anwendungen.\n")
        return
    
    print("[-] Docker wurde nicht im Systempfad gefunden. Bereite Setup vor...")

    # System-Temp-Ordner vorab definieren, da er für die Windows-Erkennung benötigt wird
    temp_dir = tempfile.gettempdir()

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
        
        # Dynamische Erkennung, falls der Installer im Temp einen veränderten Namen hat
        existing_installers = glob.glob(os.path.join(temp_dir, "*docker*.exe"))
        if existing_installers:
            existing_installers.sort(key=os.path.getmtime, reverse=True)
            filename = os.path.basename(existing_installers[0])
            print(f"[i] Nutze dynamisch erkannten Installer: {filename}")
        else:
            filename = "Docker_Installer.exe"
    else:
        print(f"Abbruch: Betriebssystem {os_name} wird nicht unterstützt.")
        return

    # 3. System-Temp-Pfad zusammenbauen
    full_path = os.path.join(temp_dir, filename)

    # Prüfung auf existierende Datei vor Download
    if os.path.exists(full_path):
        print(f"\n[i] Installationsdatei bereits lokal gefunden unter: {full_path}")
        print("-> Überspringe Download und fahre direkt mit der Installation fort.\n")
    else:
        print(f"\nNutze temporären Speicherpfad: {full_path}")
        print("Hole aktuellste Version von Docker-Servern...")
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
                subprocess.run(["hdiutil", "attach", full_path, "-nobrowse"], check=True, capture_output=True, text=True)
                dmg_mounted = True
            except subprocess.CalledProcessError as mount_error:
                error_msg = (mount_error.stderr or "").lower()
                if "no mountable file systems" in error_msg or "keine aktivierbaren dateisysteme" in error_msg:
                    print("\n[!] LOGIK-STOPP: Die gefundene Datei ist korrupt (unvollständiger Download).")
                    print("-> Lösche die fehlerhafte Datei automatisch, um Platz für den Neustart zu machen...")
                    if os.path.exists(full_path):
                        os.remove(full_path)
                    print("[✓] Gelöscht. Bitte starte das Skript einfach noch einmal, um frisch herunterzuladen.\n")
                    return
                else:
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
            print("Prüfe bestehende Docker-Installation...")
            if fix_windows_docker_path():
                print("[✓] Docker wurde erfolgreich im System erkannt und eingebunden.")
                installation_successful = True
            else:
                print("Öffne Windows-Installationsassistenten mit Admin-Rechten...")
                try:
                    # Erzwingt die Ausführung mit Administrator-Rechten unter Windows (öffnet UAC-Abfrage)
                    subprocess.run([
                        "powershell", 
                        "-Command", 
                        f"Start-Process -FilePath '{full_path}' -Verb RunAs -Wait"
                    ], check=True)
                    print("[✓] Installationsassistent beendet.")
                    installation_successful = True
                except subprocess.CalledProcessError:
                    print("[!] Hinweis: Installer wurde übersprungen oder abgebrochen. Prüfe manuellen Pfad...")
                    if fix_windows_docker_path():
                        installation_successful = True
                    else:
                        installation_successful = False

    except Exception as e:
        print(f"\n[!] Fehler während der Installation: {e}")
        print("Hinweis: Ggf. wurden Admin-Rechte verweigert oder der Kopiervorgang wurde abgebrochen.")
        
    finally:
        # ABSOLUT SICHERES & INTELLIGENTES AUFRÄUMEN
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
            
            # --- AUTOMATISCHER FALLBACK-VERSUCH ---
            print("\n--- Starte automatische Nachprüfung / Behebung ---")
            if fix_windows_docker_path():
                c_inst, d_run = check_docker_status()
                if c_inst:
                    print("[✓] Docker wurde über den Standardpfad erfolgreich in die Umgebung eingebunden!")
                    if not d_run:
                        print("[!] Hinweis: Der Docker-Daemon läuft aktuell noch nicht. Bitte starte 'Docker Desktop' über Windows.")

if __name__ == "__main__":
    download_and_install_docker_smart()