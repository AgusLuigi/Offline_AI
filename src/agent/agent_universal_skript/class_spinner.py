import gc
import sys
import threading
import time


class ResourceAwareSpinner:
    """
    Kapselt den visuellen Terminal-Spinner inklusive Live-Ressourcenüberwachung (CPU/RAM).
    Läuft fehlertolerant im Hintergrund-Thread, ohne den Hauptprozess zu blockieren.
    """
    # Globale Schutz- und Mindesteinstellungen für den Agenten
    MIN_RAM_MB = 2000          # Mindestens 2 GB RAM-Sicherheitspuffer
    MAX_CPU_THRESHOLD = 90.0   # Warnschwelle bei CPU-Auslastung
    SPINNER_INTERVAL = 1.0     # Taktung der Aktualisierung in Sekunden

    def __init__(self, agent_name: str = "Codestral-Agent"):
        self.agent_name = agent_name
        self.has_psutil = self._check_psutil()

    @staticmethod
    def _check_psutil() -> bool:
        try:
            import psutil
            return True
        except ImportError:
            return False

    def _get_system_metrics(self) -> str:
        """Sammelt ressourcenschonend CPU- und RAM-Werte für die Live-Anzeige."""
        if not self.has_psutil:
            return ""
        
        try:
            import psutil
            ram_avail = psutil.virtual_memory().available / (1024**3)
            cpu_usage = psutil.cpu_percent(interval=None)

            # Automatisches Aufräumen, falls der RAM unter das Limit fällt
            if ram_avail < (self.MIN_RAM_MB / 1024):
                gc.collect()
                return f"⚠️ RAM kritisch ({ram_avail:.2f}GB) | GC aktiv"

            if cpu_usage > self.MAX_CPU_THRESHOLD:
                return f"🔥 CPU Last hoch ({cpu_usage:.0f}%)"

            return f"RAM frei: {ram_avail:.1f}GB | CPU: {cpu_usage:.0f}%"
        except Exception:
            return ""

    def run(self, stop_event: threading.Event, is_de: bool = True):
        """
        Startet die Endlos-Visualisierung im Terminal, bis das `stop_event` gesetzt wird.
        """
        chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        base_msg = f"[{self.agent_name}] Arbeitet..." if is_de else f"[{self.agent_name}] Processing..."
        idx = 0
        
        try:
            while not stop_event.is_set():
                metrics = self._get_system_metrics()
                metric_str = f" | {metrics}" if metrics else ""
                
                output_line = f"\r{base_msg} {chars[idx % len(chars)]}{metric_str}   "
                sys.stdout.write(output_line)
                sys.stdout.flush()
                
                idx += 1
                time.sleep(self.SPINNER_INTERVAL)
        except Exception:
            pass  # Verhindert jeglichen Crash des Hauptprogramms durch Darstellungsfehler
        finally:
            # Zeile nach Beendigung sauber im Terminal bereinigen
            sys.stdout.write('\r' + ' ' * 100 + '\r')
            sys.stdout.flush()

globals()['ResourceAwareSpinner'] = ResourceAwareSpinner