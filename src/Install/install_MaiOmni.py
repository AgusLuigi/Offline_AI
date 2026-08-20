import os
import sys
import platform
import subprocess
import urllib.request
import shutil
import importlib

# Absicherung der Konsolenausgabe gegen Windows-Encoding-Fehler (cp1252)
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

class BaseInstaller:
    """Basis-Klasse mit gemeinsamen Funktionen für alle Betriebssysteme."""
    def __init__(self, target_env_name="MaiOmni", python_version="3.11.0"):
        self.target_env_name = target_env_name
        self.python_version = python_version
        self.system = platform.system()
        self.conda_root = None
        self.conda_executable = self._resolve_conda_path()

    def log(self, message):
        print(f"[Installer] {message}")

    def _inject_conda_to_path(self, conda_root):
        """Injiziert gefundene Conda-Pfade an den Anfang von os.environ['PATH']."""
        if not conda_root or not os.path.exists(conda_root):
            return
        
        self.conda_root = os.path.abspath(conda_root)
        current_path = os.environ.get("PATH", "")
        
        if self.system == "Windows":
            conda_dirs = [
                self.conda_root,
                os.path.join(self.conda_root, "condabin"),
                os.path.join(self.conda_root, "Scripts"),
                os.path.join(self.conda_root, "Library", "bin"),
                os.path.join(self.conda_root, "Library", "usr", "bin"),
                os.path.join(self.conda_root, "Library", "mingw-w64", "bin")
            ]
        else: # macOS / Linux
            conda_dirs = [
                os.path.join(self.conda_root, "bin"),
                os.path.join(self.conda_root, "condabin"),
                self.conda_root
            ]
            
        new_entries = [d for d in conda_dirs if os.path.exists(d) and d.lower() not in current_path.lower()]
        if new_entries:
            os.environ["PATH"] = os.pathsep.join(new_entries) + os.pathsep + current_path

    def _resolve_conda_path(self):
        """
        Robuste Multi-Stufen Conda-Pfad-Erkennung:
        1. Umgebungsvariablen (CONDA_EXE, CONDA_PREFIX, CONDA_BAT)
        2. PATH-Check via shutil.which
        3. Aktives Python-Verzeichnis (sys.prefix)
        4. Bekannte Standardverzeichnisse für Windows, macOS und Linux
        """
        # Stufe 1: Umgebungsvariablen
        for env_var in ["CONDA_EXE", "CONDA_BAT"]:
            val = os.environ.get(env_var)
            if val and os.path.exists(val):
                root_dir = os.path.dirname(os.path.dirname(val))
                self._inject_conda_to_path(root_dir)
                return os.path.abspath(val)

        conda_prefix = os.environ.get("CONDA_PREFIX")
        if conda_prefix and os.path.exists(conda_prefix):
            self._inject_conda_to_path(conda_prefix)

        # Stufe 2: Direkte PATH-Auflösung
        for candidate in ["conda.bat", "conda.exe", "conda"]:
            found = shutil.which(candidate)
            if found and os.path.exists(found):
                root_dir = os.path.dirname(os.path.dirname(found))
                self._inject_conda_to_path(root_dir)
                return os.path.abspath(found)

        # Stufe 3: sys.prefix & sys.executable Umfeld
        sys_candidates = []
        if self.system == "Windows":
            sys_candidates = [
                os.path.join(sys.prefix, "condabin", "conda.bat"),
                os.path.join(sys.prefix, "Scripts", "conda.exe"),
                os.path.join(os.path.dirname(sys.executable), "condabin", "conda.bat"),
                os.path.join(os.path.dirname(sys.executable), "Scripts", "conda.exe"),
            ]
        else:
            sys_candidates = [
                os.path.join(sys.prefix, "bin", "conda"),
                os.path.join(os.path.dirname(sys.executable), "bin", "conda")
            ]
        for sc in sys_candidates:
            if os.path.exists(sc):
                root_dir = os.path.dirname(os.path.dirname(sc))
                self._inject_conda_to_path(root_dir)
                return os.path.abspath(sc)

        # Stufe 4: Standard-Installationspfade nach Betriebssystem scannen
        home_dir = os.path.expanduser("~")
        
        if self.system == "Windows":
            local_appdata = os.environ.get("LOCALAPPDATA", os.path.join(home_dir, "AppData", "Local"))
            program_data = os.environ.get("ProgramData", "C:\\ProgramData")
            
            potential_roots = [
                os.path.join(home_dir, "miniconda3"),
                os.path.join(home_dir, "anaconda3"),
                os.path.join(home_dir, "miniforge3"),
                os.path.join(home_dir, "mambaforge"),
                os.path.join(local_appdata, "miniconda3"),
                os.path.join(local_appdata, "anaconda3"),
                os.path.join(local_appdata, "Continuum", "anaconda3"),
                os.path.join(program_data, "miniconda3"),
                os.path.join(program_data, "anaconda3"),
                "C:\\miniconda3",
                "C:\\anaconda3",
                "C:\\tools\\miniconda3"
            ]
            
            for root in potential_roots:
                if os.path.exists(root):
                    for sub in [os.path.join("condabin", "conda.bat"), os.path.join("Scripts", "conda.exe"), "_conda.exe"]:
                        exe_path = os.path.join(root, sub)
                        if os.path.exists(exe_path):
                            self._inject_conda_to_path(root)
                            self.log(f"[AUTO-FIX] Conda lokalisiert: {exe_path}")
                            return os.path.abspath(exe_path)
        else: # macOS / Linux
            potential_roots = [
                os.path.join(home_dir, "miniconda3"),
                os.path.join(home_dir, "anaconda3"),
                os.path.join(home_dir, "miniforge3"),
                os.path.join(home_dir, "mambaforge"),
                "/opt/miniconda3",
                "/opt/anaconda3",
                "/opt/homebrew/Caskroom/miniconda/base",
                "/usr/local/miniconda3",
                "/usr/local/anaconda3",
                "/usr/local"
            ]
            
            for root in potential_roots:
                if os.path.exists(root):
                    for sub in [os.path.join("bin", "conda"), os.path.join("condabin", "conda")]:
                        exe_path = os.path.join(root, sub)
                        if os.path.exists(exe_path):
                            self._inject_conda_to_path(root)
                            self.log(f"[AUTO-FIX] Conda lokalisiert: {exe_path}")
                            return os.path.abspath(exe_path)

        return "conda"

    def is_running_on_target_kernel(self):
        """Prüft, ob der aktuelle Python-Prozess bereits in der Zielumgebung läuft."""
        current_python = sys.executable.lower()
        if self.target_env_name.lower() in current_python:
            self.log(f"[SICHERHEITSSCHUTZ] Das Skript läuft bereits in der Zielumgebung '{self.target_env_name}'.")
            return True
        return False

    def _build_command_list(self, command):
        """Konvertiert einen Befehls-String oder eine Liste in eine sichere Ausführungsliste."""
        if isinstance(command, list):
            cmd_list = list(command)
        else:
            cmd_list = command.split()
            
        if cmd_list and cmd_list[0] == "conda":
            cmd_list[0] = self.conda_executable
        return cmd_list

    def run_command_raw(self, command):
        """Führt einen Befehl direkt und zuverlässig aus."""
        cmd_list = self._build_command_list(command)
        try:
            result = subprocess.run(cmd_list, check=True, text=True)
            return result.returncode == 0
        except Exception:
            try:
                cmd_str = " ".join(f'"{c}"' if " " in c else c for c in cmd_list)
                result = subprocess.run(cmd_str, shell=True, check=True, text=True)
                return result.returncode == 0
            except Exception:
                return False

    def run_command(self, command):
        """Führt einen Terminal-Befehl aus und fängt typische Fehler mit Selbstheilung ab."""
        cmd_list = self._build_command_list(command)
        try:
            subprocess.run(cmd_list, check=True, text=True, capture_output=True)
            return True
        except subprocess.CalledProcessError as e:
            error_output = (e.stderr or "") + (e.stdout or "")
            
            if "ipykernel" in error_output.lower() or "requires the ipykernel package" in error_output.lower():
                self.log("[FEHLER-ERKENNUNG] Fehlendes/beschädigtes 'ipykernel' erkannt. Starte Auto-Reparatur...")
                self.ensure_base_and_runtime_ipykernel()
                return self.run_command_raw(command)
            
            self.log(f"Fehler beim Ausführen von: {' '.join(cmd_list)}\nDetails: {error_output}")
            return False

    def check_miniconda(self):
        """Prüft, ob Conda/Miniconda verfügbar ist."""
        if self.conda_executable == "conda":
            self.conda_executable = self._resolve_conda_path()
            
        test_cmd = [self.conda_executable, "--version"]
        try:
            subprocess.run(test_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            try:
                subprocess.run(f'"{self.conda_executable}" --version', shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except Exception:
                return False

    def check_env_exists(self):
        """Prüft via CLI, ob die Conda-Umgebung bereits existiert."""
        try:
            output = subprocess.check_output([self.conda_executable, "env", "list"], text=True)
            envs = [line.split()[0] for line in output.splitlines() if line and not line.startswith("#")]
            return self.target_env_name in envs
        except Exception:
            try:
                output = subprocess.check_output(f'"{self.conda_executable}" env list', shell=True, text=True)
                envs = [line.split()[0] for line in output.splitlines() if line and not line.startswith("#")]
                return self.target_env_name in envs
            except Exception:
                return False

    def ensure_base_and_runtime_ipykernel(self):
        """
        Zentrale Selbstheilungs- und Reparaturroutine:
        1. Prüft und repariert 'ipykernel' in der aktuellen Python-Laufzeitumgebung.
        2. Prüft und repariert 'ipykernel' in der Conda 'base'-Umgebung (über conda install / pip).
        Verhindert Kernel-Ausführungsfehler in Jupyter Notebooks (z. B. 01_installation.ipynb).
        """
        self.log("--- Überprüfe IPykernel-Integrität (Laufzeitumgebung & Conda base) ---")
        
        # 1. Prüfung der aktuellen Python-Laufzeitumgebung
        try:
            import ipykernel
            self.log(f"[OK] 'ipykernel' ({ipykernel.__version__}) ist in der aktuellen Laufzeitumgebung aktiv.")
        except ImportError:
            self.log("[!] 'ipykernel' fehlt in der aktuellen Laufzeitumgebung. Installiere automatisch...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "ipykernel"])
                importlib.invalidate_caches()
                import ipykernel
                self.log(f"[OK] 'ipykernel' erfolgreich in der aktuellen Laufzeitumgebung installiert.")
            except Exception as e:
                self.log(f"[WARNUNG] Installation von ipykernel in der Laufzeitumgebung fehlgeschlagen: {e}")

        # 2. Prüfung der Conda 'base'-Umgebung
        if self.check_miniconda():
            base_ok = False
            
            try:
                check_cmd = [self.conda_executable, "run", "-n", "base", "python", "-c", "import ipykernel"]
                res = subprocess.run(check_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if res.returncode == 0:
                    base_ok = True
            except Exception:
                pass

            if not base_ok and self.conda_root:
                base_python = os.path.join(self.conda_root, "python.exe") if self.system == "Windows" else os.path.join(self.conda_root, "bin", "python")
                if os.path.exists(base_python):
                    try:
                        res = subprocess.run([base_python, "-c", "import ipykernel"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        if res.returncode == 0:
                            base_ok = True
                    except Exception:
                        pass

            if base_ok:
                self.log("[OK] 'ipykernel' ist in der Conda 'base'-Umgebung bereits funktionsfähig.")
            else:
                self.log("[!] 'ipykernel' fehlt in der Conda 'base'-Umgebung. Starte automatische Reparatur...")
                
                repaired = False
                
                # Methode 1: Empfohlener Weg mit conda install
                fix_conda_cmd = [self.conda_executable, "install", "-n", "base", "ipykernel", "--update-deps", "-y"]
                self.log("    -> Reparatur-Versuch 1: 'conda install -n base ipykernel'...")
                if self.run_command_raw(fix_conda_cmd):
                    repaired = True
                    self.log("[OK] 'ipykernel' erfolgreich via conda in 'base' installiert.")
                
                # Methode 2: Fallback mit pip via conda run
                if not repaired:
                    self.log("    -> Reparatur-Versuch 2: 'conda run -n base pip install ipykernel'...")
                    fix_pip_cmd = [self.conda_executable, "run", "-n", "base", "pip", "install", "ipykernel"]
                    if self.run_command_raw(fix_pip_cmd):
                        repaired = True
                        self.log("[OK] 'ipykernel' erfolgreich via pip in 'base' installiert.")

                # Methode 3: Direkter Interpreter-Aufruf des Base-Python
                if not repaired and self.conda_root:
                    base_python = os.path.join(self.conda_root, "python.exe") if self.system == "Windows" else os.path.join(self.conda_root, "bin", "python")
                    if os.path.exists(base_python):
                        self.log(f"    -> Reparatur-Versuch 3: Direktes pip install über {base_python}...")
                        try:
                            subprocess.check_call([base_python, "-m", "pip", "install", "ipykernel"])
                            repaired = True
                            self.log("[OK] 'ipykernel' erfolgreich über direkten Python-Interpreter in 'base' installiert.")
                        except Exception as e:
                            self.log(f"[FEHLER] Direkte Installation fehlgeschlagen: {e}")

                if not repaired:
                    self.log("[WARNUNG] Automatische Installation von ipykernel in 'base' konnte nicht abgeschlossen werden.")

    def ensure_target_ipykernel(self):
        """Stellt sicher, dass ipykernel in der Zielumgebung vorhanden und als Jupyter-Kernel registriert ist."""
        self.log(f"Überprüfe und registriere Jupyter-Kernel für '{self.target_env_name}'...")
        
        check_cmd = [self.conda_executable, "run", "-n", self.target_env_name, "python", "-c", "import ipykernel"]
        try:
            res = subprocess.run(check_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode != 0:
                self.log(f"[!] 'ipykernel' in '{self.target_env_name}' fehlt. Installiere...")
                install_cmd = [self.conda_executable, "run", "-n", self.target_env_name, "pip", "install", "jupyter", "ipykernel"]
                self.run_command_raw(install_cmd)
        except Exception:
            install_cmd = [self.conda_executable, "run", "-n", self.target_env_name, "pip", "install", "jupyter", "ipykernel"]
            self.run_command_raw(install_cmd)

        kernel_cmd = [
            self.conda_executable, "run", "-n", self.target_env_name,
            "python", "-m", "ipykernel", "install", "--user",
            "--name", self.target_env_name,
            "--display-name", f"Python ({self.target_env_name})"
        ]
        if self.run_command_raw(kernel_cmd):
            self.log(f"[OK] Jupyter-Kernel '{self.target_env_name}' erfolgreich im System registriert.")
        else:
            self.log(f"[WARNUNG] Kernel-Registrierung für '{self.target_env_name}' fehlgeschlagen.")

    def _accept_conda_tos_if_needed(self):
        """Akzeptiert automatisch Conda Terms of Service für Standard-Kanäle."""
        for ch in [
            "https://repo.anaconda.com/pkgs/main",
            "https://repo.anaconda.com/pkgs/r",
            "https://repo.anaconda.com/pkgs/msys2"
        ]:
            try:
                cmd = [self.conda_executable, "tos", "accept", "--override-channels", "--channel", ch]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

    def create_conda_env(self):
        """Erstellt die gewünschte Python-Umgebung via Conda mit Überschreib-Abfrage und Selbstschutz."""
        if not self.check_miniconda():
            self.log("Conda wurde nicht gefunden! Installiere erst Miniconda.")
            return False
        
        if self.is_running_on_target_kernel():
            self.log("[INFO] Überspringe Umgebungserstellung/Löschung, da der Installer im aktiven Ziel-Kernel läuft.")
            self.ensure_target_ipykernel()
            return True
        
        if self.check_env_exists():
            print("\n" + "=" * 60)
            user_choice = input(f"[ACHTUNG] Die Umgebung '{self.target_env_name}' existiert bereits.\nSoll sie überschrieben werden? (y/n): ").strip().lower()
            print("=" * 60 + "\n")
            
            if user_choice in ['y', 'yes']:
                self.log(f"Lösche alte Umgebung '{self.target_env_name}'...")
                remove_cmd = [self.conda_executable, "env", "remove", "-n", self.target_env_name, "-y"]
                if not self.run_command_raw(remove_cmd):
                    self.log("[FEHLER] Alte Umgebung konnte nicht sauber entfernt werden.")
                    return False
            else:
                self.log(f"Überspringe Erstellung. Bestehende Umgebung '{self.target_env_name}' bleibt unverändert.")
                self.ensure_target_ipykernel()
                return True

        self.log(f"Erstelle Conda-Umgebung '{self.target_env_name}' mit Python {self.python_version}...")
        self._accept_conda_tos_if_needed()
        command = [self.conda_executable, "create", "-n", self.target_env_name, f"python={self.python_version}", "-y"]
        if self.run_command_raw(command):
            self.ensure_target_ipykernel()
            return True
        
        # Fallback auf conda-forge
        self.log(f"[!] Erster Versuch fehlgeschlagen. Versuche Erstellung via 'conda-forge'...")
        forge_cmd = [self.conda_executable, "create", "-n", self.target_env_name, "--override-channels", "-c", "conda-forge", f"python={self.python_version}", "-y"]
        if self.run_command_raw(forge_cmd):
            self.ensure_target_ipykernel()
            return True

        return False

    def install_dependencies(self):
        """Installiert die Basis-Bibliotheken in die neue Umgebung mit Integritätsprüfung."""
        self.log(f"Installiere/Überprüfe Basis-Pakete in '{self.target_env_name}'...")
        install_command = [self.conda_executable, "run", "-n", self.target_env_name, "pip", "install", "jupyter", "ipykernel"]
        
        if not self.run_command_raw(install_command):
            self.log(f"[WARNUNG] Fehler beim Ausführen von pip install in '{self.target_env_name}'.")
            
        self.ensure_target_ipykernel()
        return True

    def run(self):
        """Haupt-Workflow der Installation."""
        raise NotImplementedError("Die 'run'-Methode muss von der Subklasse implementiert werden!")


class WindowsInstaller(BaseInstaller):
    """Spezifische Installations-Logik für Windows."""
    def install_miniconda_sys(self):
        if self.check_miniconda():
            self.log("Conda ist bereits auf Windows installiert.")
            return True
        
        self.log("Lade Miniconda für Windows herunter...")
        url = "https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe"
        installer_path = os.path.join(os.environ.get("TEMP", "."), "miniconda_installer.exe")
        
        try:
            urllib.request.urlretrieve(url, installer_path)
            self.log("Starte Miniconda-Installation (Silent)... Bitte kurz warten.")
            
            target_dir = os.path.expanduser("~\\miniconda3")
            install_cmd = f'"{installer_path}" /InstallationType=JustMe /RegisterPython=0 /S /D={target_dir}'
            
            if self.run_command_raw(install_cmd):
                self.conda_executable = self._resolve_conda_path()
                self.log("Miniconda erfolgreich installiert und Pfad automatisch eingebunden.")
                return True
        except Exception as e:
            self.log(f"Fehler bei der Windows-Miniconda-Installation: {e}")
        return False

    def run(self):
        self.log("--- Starte Windows Installation ---")
        if not self.check_miniconda():
            if not self.install_miniconda_sys():
                return
        
        # 1. Sofortige Absicherung von ipykernel für base und die Laufzeitumgebung
        self.ensure_base_and_runtime_ipykernel()
        
        # 2. Zielumgebung vorbereiten und Pakete installieren
        if self.create_conda_env():
            self.install_dependencies()
            self.log("Windows-Setup abgeschlossen!")


class MacOSInstaller(BaseInstaller):
    """Spezifische Installations-Logik für macOS (M-Chips/Intel)."""
    def install_miniconda_sys(self):
        if self.check_miniconda():
            self.log("Conda ist bereits auf macOS installiert.")
            return True
        
        self.log("Lade Miniconda für macOS herunter...")
        arch = "arm64" if platform.processor() == "arm" else "x86_64"
        url = f"https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-{arch}.sh"
        installer_path = "/tmp/miniconda_installer.sh"
        
        try:
            urllib.request.urlretrieve(url, installer_path)
            self.log("Starte Miniconda-Installation...")
            self.run_command_raw(f"chmod +x {installer_path}")
            install_cmd = f"sh {installer_path} -b -p $HOME/miniconda3"
            if self.run_command_raw(install_cmd):
                self.conda_executable = self._resolve_conda_path()
                self.log("Miniconda erfolgreich installiert!")
                return True
        except Exception as e:
            self.log(f"Fehler bei der macOS-Miniconda-Installation: {e}")
        return False

    def run(self):
        self.log("--- Starte macOS Installation ---")
        if not self.check_miniconda():
            if not self.install_miniconda_sys():
                self.log("Bitte stelle sicher, dass Conda in deinem $PATH liegt.")
                return
        
        # 1. Sofortige Absicherung von ipykernel für base und die Laufzeitumgebung
        self.ensure_base_and_runtime_ipykernel()
        
        # 2. Zielumgebung vorbereiten und Pakete installieren
        if self.create_conda_env():
            self.install_dependencies()
            self.log("macOS-Setup abgeschlossen!")


def main():
    current_os = platform.system()
    
    if current_os == "Windows":
        installer = WindowsInstaller()
    elif current_os == "Darwin":
        installer = MacOSInstaller()
    else:
        installer = BaseInstaller()
        
    installer.run()

if __name__ == "__main__":
    main()