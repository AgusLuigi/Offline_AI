import sys
import importlib
import inspect
from pathlib import Path
import types

def auto_bootstrap_and_register_agents():
    """
    Ermittelt stochastisch den 'agent_universal_skript'-Ordner im Projekt,
    fügt ihn dem Python-Pfad hinzu, scannt alle enthaltenen .py-Dateien 
    und registriert sowohl alle Klassen als auch alle globalen Funktionen 
    automatisch im globalen Namespace des Aufrufers.
    """
    current_file = Path(__file__).resolve()
    target_dir = None
    
    # 1. Stochastische, kaskadierende Suche nach dem Verzeichnis
    for parent in [current_file] + list(current_file.parents):
        candidate = parent / "agent_universal_skript"
        if candidate.is_dir():
            target_dir = candidate
            if str(parent) not in sys.path:
                sys.path.insert(0, str(parent))
            break
        
        # Fallback über src/agent Struktur
        src_agent = parent / "src" / "agent"
        if src_agent.is_dir() and (src_agent / "agent_universal_skript").is_dir():
            target_dir = src_agent / "agent_universal_skript"
            if str(src_agent) not in sys.path:
                sys.path.insert(0, str(src_agent))
            break

    if not target_dir or not target_dir.is_dir():
        print("[WARNUNG] 'agent_universal_skript' konnte nicht stochastisch lokalisiert werden.")
        return

    # Den globalen Namespace des aufrufenden Skripts abgreifen
    caller_globals = inspect.currentframe().f_back.f_globals

    # 2. Alle .py-Dateien im Ordner stochastisch einlesen (ohne Init-Dateien)
    for py_file in target_dir.glob("*.py"):
        if py_file.name.startswith("_"):
            continue
            
        module_name = py_file.stem
        full_module_path = f"agent_universal_skript.{module_name}"
        
        try:
            # Modul dynamisch zur Laufzeit importieren
            mod = importlib.import_module(full_module_path)
            
            # 3. Introspektion: Klassen UND Funktionen automatisch finden und globalisieren
            for attr_name in dir(mod):
                if attr_name.startswith("_"):
                    continue
                    
                attr_value = getattr(mod, attr_name)
                
                # Bedingung A: Ist es eine echte Klasse aus diesem Modul?
                is_class_from_mod = isinstance(attr_value, type) and attr_value.__module__ == mod.__name__
                
                # Bedingung B: Ist es eine Funktion, die in diesem Modul definiert wurde?
                is_func_from_mod = isinstance(attr_value, types.FunctionType) and attr_value.__module__ == mod.__name__
                
                if is_class_from_mod or is_func_from_mod:
                    caller_globals[attr_name] = attr_value
                    
        except Exception as e:
            print(f"[FEHLER beim automatischen Laden] Modul '{module_name}': {e}")

# Sofortige Ausführung beim Start des Skripts
sys.path.append(str(Path(__file__).resolve().parent))
auto_bootstrap_and_register_agents()