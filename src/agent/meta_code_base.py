"""
Alias-Wrapper für meta_coder_base.py.
Ermöglicht den Aufruf von MetaCodeBase sowohl über meta_code_base.py als auch über meta_coder_base.py.
"""
import os
import sys

# Basisverzeichnis des Projekts ermitteln und im Pfad registrieren
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.abspath(os.path.join(_current_dir, "..", ".."))

if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from meta_coder_base import (
    MetaCodeBase,
    boot_latest_metacoder,
    query_meta_coder_base
)

globals()["MetaCodeBase"] = MetaCodeBase
globals()["boot_latest_metacoder"] = boot_latest_metacoder
globals()["query_meta_coder_base"] = query_meta_coder_base

if __name__ == "__main__":
    metacoder = boot_latest_metacoder()

    if len(sys.argv) > 2:
        nb_path = sys.argv[1]
        user_task = sys.argv[2]
        query_meta_coder_base(nb_path, user_task)
    else:
        print("\n==================================================")
        print(" [META-CODER] Interaktiver Terminal-Modus aktiv ")
        print("==================================================")
        choice = input("Möchtest du ein Jupyter-Notebook korrigieren lassen? (j/n): ").strip().lower()

        if choice == "j":
            nb_path = input("Pfad zum Jupyter-Notebook (z. B. notebooks/test.ipynb): ").strip()
            user_task = input("Was soll der Agent tun/korrigieren?: ").strip()
            query_meta_coder_base(nb_path, user_task)
        else:
            spec = "Ollama Environment Inspector"
            task = """
            Create a Python script that connects to the local Ollama instance, lists local models,
            and ensures no timeout occurs. Exit with code 0 on success.
            """
            metacoder.test_and_evolve_loop(
                specialization=spec,
                task_description=task,
                base_filename="ollama_inspector",
                max_generations=3
            )
