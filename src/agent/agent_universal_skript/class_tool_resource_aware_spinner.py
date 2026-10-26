import gc
import sys
import threading
import time
from pathlib import Path

# 1. Hauptverzeichnis zum Python-Pfad hinzufügen
sys.path.append(str(Path(__file__).resolve().parent))

# 2. Auto-Bootstrap & globale Registrierung
from agent_universal_skript.auto_bootstrap_and_register_agent_tools import auto_bootstrap_and_register_agent_tools
auto_bootstrap_and_register_agent_tools()

# 3. Zentrale globale Aliase mit sicherer Fallback-Logik (Defaults) direkt nach Bootstrap
logger = globals().get('class_logger_audit_execution')

# GLOBALE STANDARD-KONFIGURATION
MIN_RAM_MB = 2000
MAX_CPU_THRESHOLD = 90.0
SPINNER_INTERVAL = 1.0


class class_tool_resource_aware_spinner:
    """
    Kapselt den visuellen Terminal-Spinner inklusive Live-Ressourcenüberwachung (CPU/RAM).
    Läuft fehlertolerant im Hintergrund-Thread, ohne den Hauptprozess zu blockieren.
    Alle Schwellenwerte sind über Klassenattribute oder __init__-Parameter konfigurierbar.
    """
    # Globale Schutz- und Mindesteinstellungen (überschreibbar via __init__ oder Unterklasse)
    MIN_RAM_MB = MIN_RAM_MB
    MAX_CPU_THRESHOLD = MAX_CPU_THRESHOLD
    SPINNER_INTERVAL = SPINNER_INTERVAL

    def __init__(self, agent_name: str = "Agent",
                 min_ram_mb: int = None,
                 max_cpu_threshold: float = None,
                 spinner_interval: float = None):
        self.agent_name = agent_name
        self.has_psutil = self._check_psutil()
        # Individuelle Überschreibung der Klassenattribute pro Instanz
        if min_ram_mb is not None:
            self.MIN_RAM_MB = min_ram_mb
        if max_cpu_threshold is not None:
            self.MAX_CPU_THRESHOLD = max_cpu_threshold
        if spinner_interval is not None:
            self.SPINNER_INTERVAL = spinner_interval

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
        Bypasst den Logger-Redirector, um Steuerzeichen sauber darzustellen.
        """
        raw_terminal = sys.__stdout__ if hasattr(sys, '__stdout__') else sys.stdout
        if hasattr(sys.stdout, "terminal"):
            raw_terminal = sys.stdout.terminal
        encoding = getattr(raw_terminal, 'encoding', '') or 'ascii'
        supports_unicode = 'utf' in encoding.lower()
        chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'] if supports_unicode else ['|', '/', '-', '\\']
        base_msg = f"[{self.agent_name}] Arbeitet..." if is_de else f"[{self.agent_name}] Processing..."
        idx = 0
        
        try:
            while not stop_event.is_set():
                metrics = self._get_system_metrics()
                metric_str = f" | {metrics}" if metrics else ""
                char = chars[idx % len(chars)]
                output_line = f"\r{base_msg} {char}{metric_str}   "
                try:
                    raw_terminal.write(output_line)
                    raw_terminal.flush()
                except UnicodeEncodeError:
                    # Sofortiger Fallback auf ASCII bei Zeichensatz-Inkompatibilität
                    chars = ['|', '/', '-', '\\']
                    raw_terminal.write(f"\r{base_msg} {chars[idx % len(chars)]}{metric_str}   ")
                    raw_terminal.flush()
                
                idx += 1
                # Responsives Warten: In kurzen Abschnitten prüfen, ob stop_event gesetzt ist
                sleep_chunk = 0.1
                elapsed = 0.0
                interval = max(0.1, self.SPINNER_INTERVAL)
                while elapsed < interval and not stop_event.is_set():
                    time.sleep(min(sleep_chunk, interval - elapsed))
                    elapsed += sleep_chunk
        except Exception:
            pass  # Verhindert jeglichen Crash des Hauptprogramms durch Darstellungsfehler
        finally:
            # Zeile nach Beendigung sauber im Terminal abschließen
            check_mark = "✓" if supports_unicode else "[OK]"
            done_msg = f"[{self.agent_name}] {check_mark} Abgeschlossen" if is_de else f"[{self.agent_name}] {check_mark} Done"
            try:
                raw_terminal.write(f"\r{done_msg}" + " " * 30 + "\n")
                raw_terminal.flush()
            except Exception:
                try:
                    raw_terminal.write(f"\r[{self.agent_name}] Done\n")
                    raw_terminal.flush()
                except Exception:
                    pass