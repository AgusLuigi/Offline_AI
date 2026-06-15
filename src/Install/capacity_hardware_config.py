import json
import os
import platform
import psutil


class SystemCapacity:
    """Ermittelt die Hardware-Leistung des Geräts und klassifiziert den Typ,

    um die passende KI-Ausführungsstrategie (Lokal vs. Online) zu bestimmen.
    Speichert die Konfiguration in einer JSON-Datei im zentralen Config-Ordner,
    um Folgeabfragen zu beschleunigen.
    """

    def __init__(self, config_dir="../config", filename="hardware_config.json"):
        # Absolute Pfade sichern, damit der Aufruf aus Notebooks oder Sub-Ordnern klappt
        self.config_dir = os.path.abspath(config_dir)
        self.config_path = os.path.join(self.config_dir, filename)

        # Standard-Attribute initialisieren (werden geladen oder analysiert)
        self.os_name = ""
        self.os_release = ""
        self.architecture = ""
        self.processor = ""
        self.logical_cores = 1
        self.physical_cores = 1
        self.ram_gb = 0.0
        self.device_type = ""

    def _calculate_ram(self):
        """Ermittelt den gesamten Arbeitsspeicher in GB."""
        try:
            total_ram_bytes = psutil.virtual_memory().total
            return round(total_ram_bytes / (1024**3), 2)
        except Exception:
            return 0.0

    def _detect_device_type(self):
        """Klassifiziert das Gerät anhand von OS und Hardware-Leistung."""
        os_lower = self.os_name.lower()

        # 1. Mobilgeräte-Erkennung (Android / iOS)
        if "android" in os_lower or "ios" in os_lower:
            if self.ram_gb >= 8:
                return "Tablet (High-End)"
            return "Smartphone / Mobilgerät"

        # 2. Server-Erkennung (Viel RAM oder viele Kerne unter Linux)
        if "linux" in os_lower and (
            self.logical_cores >= 16 or self.ram_gb >= 32
        ):
            return "Server / Enterprise Node"

        # 3. Notebook-Erkennung via Batterie-Check
        try:
            battery = psutil.sensors_battery()
            if battery is not None:
                return "Notebook / Laptop"
        except Exception:
            pass  # Falls der Zugriff vom OS blockiert wird

        # 4. Desktop-Klassifizierung nach Leistung
        if self.logical_cores >= 8 and self.ram_gb >= 16:
            return "Desktop PC (Leistungsstark)"

        return "Desktop PC / Standard"

    def execute_live_analysis(self):
        """Erzwingt eine Live-Analyse der Hardware-Komponenten."""
        self.os_name = platform.system()
        self.os_release = platform.release()
        self.architecture = platform.machine()
        self.processor = platform.processor()

        self.logical_cores = psutil.cpu_count(logical=True) or 1
        self.physical_cores = psutil.cpu_count(logical=False) or 1
        self.ram_gb = self._calculate_ram()
        self.device_type = self._detect_device_type()

    def save_to_json(self):
        """Speichert die aktuellen Attribute als JSON-Datei im config-Ordner ab."""
        config_data = self.to_sql_payload()
        # Zusätzliche Metadaten für die lokale JSON-Konfig hinzufügen
        config_data["os_release"] = self.os_release
        config_data["processor"] = self.processor
        config_data["physical_cores"] = self.physical_cores

        try:
            # Sicherstellen, dass das config-Verzeichnis existiert
            os.makedirs(self.config_dir, exist_ok=True)

            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
            print(
                f"[INFO] Hardware-Konfiguration unter '{self.config_path}' gespeichert."
            )
        except Exception as e:
            print(f"[FEHLER] Konnte JSON nicht schreiben: {e}")

    def load_or_analyze(self):
        """Prüft, ob eine Konfigurationsdatei existiert.

        Wenn ja, wird sie geladen. Wenn nein, wird die Analyse gestartet und
        gespeichert.
        """
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                self.device_type = data.get("device_type", "Unbekannt")
                self.os_name = data.get("os_name", "")
                self.os_release = data.get("os_release", "")
                self.architecture = data.get("architecture", "")
                self.processor = data.get("processor", "")
                self.logical_cores = data.get("cores", 1)
                self.physical_cores = data.get("physical_cores", 1)
                self.ram_gb = data.get("ram_gb", 0.0)

                print(
                    f"[INFO] Konfiguration erfolgreich aus '{self.config_path}' geladen (Cache)."
                )
                return True
            except Exception as e:
                print(
                    f"[WARNUNG] Fehler beim Laden der JSON, starte Live-Analyse: {e}"
                )

        # Falls keine Datei existiert oder ein Fehler auftrat: Analyse starten
        self.execute_live_analysis()
        self.save_to_json()
        return False

    def display_report(self):
        """Gibt einen übersichtlichen Report auf der Konsole aus."""
        print("=" * 45)
        print(f" LOGISTIK-REPORT: SYSTEM CAPACITY ")
        print("=" * 45)
        print(f"Gerätetyp:       {self.device_type}")
        print(f"Betriebssystem:  {self.os_name} (Rel: {self.os_release})")
        print(f"Architektur:     {self.architecture}")
        print(f"Prozessor:       {self.processor}")
        print(f"CPU-Kerne:       {self.physical_cores} physisch / {self.logical_cores} logisch")
        print(f"Arbeitsspeicher: {self.ram_gb} GB")
        print("=" * 45)

    def to_sql_payload(self):
        """Bereitet die Daten so vor, dass sie direkt in ein

        SQL-Insert-Statement übergeben werden können.
        """
        return {
            "device_type": self.device_type,
            "os_name": self.os_name,
            "architecture": self.architecture,
            "cores": self.logical_cores,
            "ram_gb": self.ram_gb,
        }


# Testlauf, wenn das Skript direkt ausgeführt wird
if __name__ == "__main__":
    # Standardmäßig wird '../config' genutzt (ideal für Ausführung aus dem 'notebooks'-Ordner)
    # Wenn du das Skript direkt im Hauptverzeichnis testest, nutze config_dir="./config"
    capacity = SystemCapacity(config_dir="../config")

    # Automatischer Ablauf: Laden oder neu analysieren
    capacity.load_or_analyze()

    # Report auf der Konsole ausgeben
    capacity.display_report()

import psutil

def get_all_disk_usage():
    disk_data = {}
    for partition in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(partition.mountpoint)
            disk_data[partition.device] = {
                "mountpoint": partition.mountpoint,
                "total_gb": round(usage.total / (1024**3), 2),
                "used_gb": round(usage.used / (1024**3), 2),
                "free_gb": round(usage.free / (1024**3), 2),
                "percent": usage.percent
            }
        except PermissionError:
            continue
    return disk_data