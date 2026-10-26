import sys
import importlib
import inspect
from pathlib import Path
import types

def auto_bootstrap_and_register_agent_tools():
    """
    Ermittelt stochastisch den 'agent_universal_skript'-Ordner im Projekt,
    fügt ihn dem Python-Pfad hinzu, scannt alle enthaltenen .py-Dateien 
    und registriert sowohl alle Klassen als auch alle globalen Funktionen 
    automatisch im globalen Namespace des Aufrufers.
    NEU: Erstellt automatisch die globalen Namespace-Zuweisungszeichenketten
    (z.B. globals()['name'] = value) dynamisch auf Basis der gefundenen Klassen.
    """
    current_file = Path(__file__).resolve()
    target_dir = None
    for parent in [current_file] + list(current_file.parents):
        candidate = parent / "agent_universal_skript"
        if candidate.is_dir():
            target_dir = candidate
            if str(parent) not in sys.path:
                sys.path.insert(0, str(parent))
            break
        src_agent = parent / "src" / "agent"
        if src_agent.is_dir() and (src_agent / "agent_universal_skript").is_dir():
            target_dir = src_agent / "agent_universal_skript"
            if str(src_agent) not in sys.path:
                sys.path.insert(0, str(src_agent))
            break
    if not target_dir or not target_dir.is_dir():
        print("[WARNUNG] 'agent_universal_skript' konnte nicht stochastisch lokalisiert werden.")
        return
    caller_globals = inspect.currentframe().f_back.f_globals
    for py_file in target_dir.glob("*.py"):
        if py_file.name.startswith("_"):
            continue
        module_name = py_file.stem
        full_module_path = f"agent_universal_skript.{module_name}"
        try:
            # Modul dynamisch zur Laufzeit importieren
            mod = importlib.import_module(full_module_path)
            for attr_name in dir(mod):
                if attr_name.startswith("_"):
                    continue
                attr_value = getattr(mod, attr_name)
                is_class_from_mod = isinstance(attr_value, type) and attr_value.__module__ == mod.__name__
                is_func_from_mod = isinstance(attr_value, types.FunctionType) and attr_value.__module__ == mod.__name__
                if is_class_from_mod or is_func_from_mod:
                    caller_globals[attr_name] = attr_value
                    registration_string = f"globals()['{attr_name}'] = {attr_name}"
                    if "_GLOBAL_GENERATED_REGISTRATIONS" not in caller_globals:
                        caller_globals["_GLOBAL_GENERATED_REGISTRATIONS"] = {}
                    caller_globals["_GLOBAL_GENERATED_REGISTRATIONS"][attr_name] = registration_string
        except Exception as e:
            print(f"[FEHLER beim automatischen Laden] Modul '{module_name}': {e}")

# Sofortige Ausführung beim Start des Skripts
sys.path.append(str(Path(__file__).resolve().parent))
auto_bootstrap_and_register_agent_tools()