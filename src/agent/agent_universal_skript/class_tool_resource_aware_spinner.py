"""
Modul: class_tool_resource_aware_spinner
Bezeichnung: Ressourcen-bewusster Terminal-Spinner
Inhaltlicher Schwerpunkt:
Visuelle Rückmeldung im Terminal während asynchroner oder ressourcenintensiver Prozesse
unter gleichzeitiger Überwachung von RAM- und CPU-Schwellenwerten.
"""

import gc
import sys
import threading
import time
from pathlib import Path

# Globale Bindings
logger = globals().get("class_logger_audit_execution")


class class_tool_resource_aware_spinner:
    """
    Kapselt den visuellen Terminal-Spinner inklusive Live-Ressourcenüberwachung.
    Läuft fehlertolerant in einem Hintergrund-Thread, ohne den Hauptprozess zu blockieren.
    """

    _cfg = globals().setdefault("_AGENT_CONFIG", {})
    MIN_RAM_MB: int = _cfg.setdefault("MIN_RAM_MB", 2000)
    MAX_CPU_THRESHOLD: float = _cfg.setdefault("MAX_CPU_THRESHOLD", 90.0)
    SPINNER_INTERVAL: float = _cfg.setdefault("SPINNER_INTERVAL", 1.0)

    def __init__(self, agent_name: str = "Agent", min_ram_mb: int = None,
                 max_cpu_threshold: float = None, spinner_interval: float = None):
        print(f"[class_tool_resource_aware_spinner] Starte Arbeit: __init__ wird jetzt ausgeführt. (Parameter: agent_name={agent_name})")
        self.agent_name = agent_name
        self.min_ram_mb = min_ram_mb if min_ram_mb is not None else self.MIN_RAM_MB
        self.max_cpu_threshold = max_cpu_threshold if max_cpu_threshold is not None else self.MAX_CPU_THRESHOLD
        self.spinner_interval = spinner_interval if spinner_interval is not None else self.SPINNER_INTERVAL
        self.has_psutil = self._check_psutil()

        if self.agent_name is None:
            print("[class_tool_resource_aware_spinner] FEHLER: __init__ hat die Aufgabe nicht erfüllt. Grund: agent_name ist None.")
            return

        print(f"[class_tool_resource_aware_spinner] Erfolg: __init__ erfolgreich beendet. (psutil verfügbar={self.has_psutil})")

    @staticmethod
    def _check_psutil() -> bool:
        """Prüft, ob psutil zur Ressourcenmessung verfügbar ist."""
        print("[class_tool_resource_aware_spinner] Starte Arbeit: _check_psutil wird jetzt ausgeführt.")
        try:
            import psutil
            result = True
        except ImportError:
            result = False

        print(f"[class_tool_resource_aware_spinner] Erfolg: _check_psutil erfolgreich beendet. (verfügbar={result})")
        return result

    def _get_system_metrics(self) -> str:
        """Liest CPU- und RAM-Werte für die Terminalanzeige aus."""
        print("[class_tool_resource_aware_spinner] Starte Arbeit: _get_system_metrics wird jetzt ausgeführt.")
        if not self.has_psutil:
            print("[class_tool_resource_aware_spinner] Erfolg: _get_system_metrics erfolgreich beendet. (psutil nicht verfügbar, leerer String)")
            return ""
        try:
            import psutil
            ram_avail = psutil.virtual_memory().available / (1024 ** 3)
            cpu_usage = psutil.cpu_percent(interval=None)

            if ram_avail < (self.min_ram_mb / 1024):
                gc.collect()
                metric_str = f"⚠️ RAM niedrig ({ram_avail:.2f}GB) | GC aktiv"
            elif cpu_usage > self.max_cpu_threshold:
                metric_str = f"🔥 CPU Last hoch ({cpu_usage:.0f}%)"
            else:
                metric_str = f"RAM frei: {ram_avail:.1f}GB | CPU: {cpu_usage:.0f}%"

            print(f"[class_tool_resource_aware_spinner] Erfolg: _get_system_metrics erfolgreich beendet.")
            return metric_str
        except Exception as e:
            print(f"[class_tool_resource_aware_spinner] FEHLER: _get_system_metrics hat die Aufgabe nicht erfüllt. Grund: Metrikerfassung fehlgeschlagen: {e}")
            return ""

    def run(self, stop_event: threading.Event, is_de: bool = True):
        """Führt die Animationsschleife im Terminal aus, bis stop_event gesetzt wird."""
        print(f"[class_tool_resource_aware_spinner] Starte Arbeit: run wird jetzt ausgeführt. (Parameter: is_de={is_de})")
        raw_terminal = sys.__stdout__ if hasattr(sys, "__stdout__") else sys.stdout
        if hasattr(sys.stdout, "terminal"):
            raw_terminal = sys.stdout.terminal
        encoding = getattr(raw_terminal, "encoding", "") or "ascii"
        supports_unicode = "utf" in encoding.lower()
        chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"] if supports_unicode else ["|", "/", "-", "\\"]
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
                    chars = ["|", "/", "-", "\\"]
                    raw_terminal.write(f"\r{base_msg} {chars[idx % len(chars)]}{metric_str}   ")
                    raw_terminal.flush()

                idx += 1
                sleep_chunk = 0.1
                elapsed = 0.0
                interval = max(0.1, self.spinner_interval)
                while elapsed < interval and not stop_event.is_set():
                    time.sleep(min(sleep_chunk, interval - elapsed))
                    elapsed += sleep_chunk
        except Exception as e:
            print(f"[class_tool_resource_aware_spinner] FEHLER: run hat die Aufgabe nicht erfüllt. Grund: Spinner-Schleife unterbrochen: {e}")
        finally:
            check_mark = "✓" if supports_unicode else "[OK]"
            done_msg = f"[{self.agent_name}] {check_mark} Abgeschlossen\n" if is_de else f"[{self.agent_name}] {check_mark} Done\n"
            try:
                raw_terminal.write(f"\r{done_msg}")
                raw_terminal.flush()
            except Exception:
                pass
            print(f"[class_tool_resource_aware_spinner] Erfolg: run erfolgreich beendet.")

    @classmethod
    def run_resource_spinner(cls, agent_title: str = "Agent", spinner_interval: float = None):
        """
        Zentrale Ausführungsfunktion: Erstellt und startet den Spinner in einem eigenständigen Thread
        und liefert ein stop_event sowie den Thread zur einfachen Prozess-Steuerung zurück.
        """
        print(f"[class_tool_resource_aware_spinner] Starte Arbeit: run_resource_spinner wird jetzt ausgeführt. (Parameter: agent_title={agent_title})")
        try:
            spinner = cls(agent_name=agent_title, spinner_interval=spinner_interval)
            stop_event = threading.Event()
            thread = threading.Thread(target=spinner.run, args=(stop_event, True))
            thread.daemon = True
            thread.start()

            result = {"spinner": spinner, "stop_event": stop_event, "thread": thread}

            if result is None or not result.get("thread"):
                print("[class_tool_resource_aware_spinner] FEHLER: run_resource_spinner hat die Aufgabe nicht erfüllt. Grund: Thread wurde nicht gestartet.")
                return None

            print(f"[class_tool_resource_aware_spinner] Erfolg: run_resource_spinner erfolgreich beendet.")
            return result
        except Exception as e:
            print(f"[class_tool_resource_aware_spinner] FEHLER: run_resource_spinner hat die Aufgabe nicht erfüllt. Grund: {e}")
            return None
