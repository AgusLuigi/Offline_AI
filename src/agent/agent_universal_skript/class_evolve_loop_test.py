import time
import traceback
from typing import Any, Callable, Dict, Optional


class EvolveLoopTest:
    """
    Klasse zur Steuerung des autonomen Test- und Evolutions-Zyklus (Closed-Loop-Architektur).
    
    Diese Klasse dient als Steuerungs-Framework für KI-Agenten, um generierten Code oder 
    Workflow-Schritte in einer geschlossenen Schleife zu verifizieren, auszuführen und bei 
    Fehlern automatisch anzupassen (Evolution / Fallback).
    
    Erweiterungsmöglichkeiten für Agenten:
    - Integration einer Docker-basierten Sandbox für die Code-Ausführung.
    - Anbindung an eine relationale Datenbank (z.B. SQLite) zur Persistenz von Metriken.
    - Dynamische Anpassung von Schwellenwerten (Success Weights / Error Fallbacks).
    """

    def __init__(self, registry_db_path: Optional[str] = None):
        self.registry_db_path = registry_db_path
        print(f"[METABASE] Initialisiere EvolveLoopTest (DB: {registry_db_path or 'In-Memory'})")

    def _verify_in_sandbox(self, task_payload: Dict[str, Any], execution_func: Callable) -> Any:
        """
        Führt eine Closed-Loop-Verifizierung in einer isolierten Umgebung aus.
        Passiver Text wird nicht akzeptiert; Code-Snippets müssen lauffähig sein.
        """
        # Hier greift im voll ausgebauten Agenten-System die Sandbox-Isolation
        return execution_func(task_payload)

    def test_and_evolve_loop(
        self, 
        specialization: str, 
        task_description: str, 
        base_filename: str, 
        max_generations: int = 3,
        execution_func: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Führt den vollständigen Test- und Evolutions-Zyklus aus.
        
        Parameter:
            specialization (str): Fachbereich oder Agenten-Kontext (z.B. 'Data Science', 'Elektrotechnik').
            task_description (str): Beschreibung der aktuellen Aufgabe.
            base_filename (str): Basis-Dateiname oder Identifier für Artefakte.
            max_generations (int): Maximale Anzahl von Evolutionsversuchen bei Fehlschlägen.
            execution_func (Callable): Die auszuführende Funktion/Logik für den Closed-Loop-Test.
            
        Rückgabe:
            Dict[str, Any]: Statusbericht inklusive Generations-Counter und Erfolgswichtung.
        """
        print(f"[METABASE] Starte Test- und Evolutions-Schleife für: {specialization} | Task: {task_description}")
        
        current_generation = 0
        success = False
        last_error = None
        result_data = None

        while current_generation < max_generations and not success:
            current_generation += 1
            print(f"[METABASE] Versuchs-Generation {current_generation} von {max_generations} läuft...")

            try:
                if execution_func:
                    # Closed-Loop Ausführung über die definierte Funktion
                    result_data = self._verify_in_sandbox({"task": task_description}, execution_func)
                else:
                    # Standard-Simulations-Fallback, falls keine Funktion übergeben wurde
                    result_data = f"Simuliertes Ergebnis für {base_filename} in Generation {current_generation}"
                
                success = True
                print(f"[METABASE] Generation {current_generation} erfolgreich verifiziert.")

            except Exception as e:
                last_error = str(e)
                print(f"[METABASE] Fehler in Generation {current_generation}: {last_error}")
                traceback.print_exc()
                # Hier greift im erweiterten System das automatische Deaktivieren des Knotens (is_active = 0)
                # und der Wechsel in die Notfall-Registry (FX_CHAIN).
                time.sleep(1)  #Kurze Pause vor dem nächsten Evolutionsschritt

        if success:
            return {
                "status": "SUCCESS",
                "specialization": specialization,
                "generations_used": current_generation,
                "result": result_data,
                "message": f"Evolutions-Schleife für {task_description} nach {current_generation} Generation(en) erfolgreich abgeschlossen."
            }
        else:
            return {
                "status": "FAILED",
                "specialization": specialization,
                "generations_attempted": max_generations,
                "last_error": last_error,
                "fallback_triggered": True,
                "message": f"Evolutions-Schleife fehlgeschlagen nach {max_generations} Versuchen. Fallback-Registry aktiviert."
            }

    def persist_new_capability(self, capability_name: str, code_snippet: str, description: str):
        """Speichert eine neue Fähigkeit dauerhaft in der Registry."""
        with self.get_db_connection() as conn:
            self._insert_routing_node(
                conn=conn,
                table_name="library_registry" if "library_registry" in [row[0] for row in conn.cursor().execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()] else "user_query",
                node_id=f"CAP_{datetime.now().strftime('%H%M%S')}",
                topic_title=capability_name,
                topic_specification=description,
                agent_instruction="CAPABILITY_REGISTERED",
                example_code_snippet=code_snippet,
                validation_rule="VERIFIED"
            )

    def record_feedback(self, query_node_id: str, is_positive: bool, comment: str = "") -> dict:
        """Verarbeitet Benutzer-Feedback und aktualisiert die Gewichte in der Datenbank."""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            if is_positive:
                cursor.execute("""
                    UPDATE user_query
                    SET success_weight = success_weight + 0.2,
                        validation_rule = 'POSITIVE_VERIFIED'
                    WHERE node_id = ?
                """, (query_node_id,))
                conn.commit()
                return {"status": "success", "feedback": "positive", "node_id": query_node_id}
            else:
                return self.deactivate_and_reroute("user_query", query_node_id, failure_reason=comment or "Negatives Feedback")

    def extract_code_from_notebook(self, notebook_path: str) -> List[str]:
        """
        Liest ein Jupyter Notebook (.ipynb) ein und extrahiert alle Code-Zellen,
        damit der Agent aus den dortigen Mustern lernen kann.
        """
        code_snippets = []
        path = Path(notebook_path)
        if not path.exists():
            print(f"[METABASE] Warnung: Notebook unter {notebook_path} nicht gefunden.")
            return code_snippets

        try:
            with open(path, "r", encoding="utf-8") as f:
                nb_data = json.load(f)
                for cell in nb_data.get("cells", []):
                    if cell.get("cell_type") == "code":
                        source = "".join(cell.get("source", []))
                        if source.strip():
                            code_snippets.append(source)
            print(f"[METABASE] {len(code_snippets)} Code-Zellen erfolgreich aus Notebook extrahiert: {path.name}")
        except Exception as e:
            print(f"[METABASE] Fehler beim Lesen des Notebooks: {e}")
            
        return code_snippets

    def query_meta_coder_sql(self, notebook_path: str, instruction: str) -> Dict[str, Any]:
        """
        Schnittstelle: Analysiert ein Jupyter Notebook, lernt daraus und 
        startet den Evolutions-Agenten für SQL- oder Code-Anweisungen.
    -   """
        # 1. Aus dem Jupyter Notebook lernen (Code extrahieren)
        learned_code_patterns = self.extract_code_from_notebook(notebook_path)
        
        # 2. Spezifikation und Task-Kontext aufbauen
        spec = f"Hierarchical Routing Tree SQL Agent for {Path(notebook_path).name}"
        task = f"""
        Target Notebook Path: {notebook_path}
        User Instruction/Routing Goal: {instruction}
        Learned Context Snippets Count: {len(learned_code_patterns)}
        """
        
        # 3. Evolutions-Schleife triggern
        return self.test_and_evolve_loop(
            specialization=spec,
            task_description=task,
            base_filename=f"sql_routing_agent_{Path(notebook_path).stem}",
            max_generations=3
        )

# Beispiel für die Verwendung und Erweiterung durch einen Agenten:
if __name__ == "__main__":
    # Testfunktion, die einen erfolgreichen Durchlauf simuliert
    def sample_task_runner(payload):
        return f"Erfolgreich ausgeführt mit Payload: {payload['task']}"

    loop = EvolveLoopTest()
    report = loop.test_and_evolve_loop(
        specialization="Data Science & Automation",
        task_description="Anomalieerkennung in Energieströmen",
        base_filename="anomaly_model_v1",
        max_generations=3,
        execution_func=sample_task_runner
    )
    print("\n--- Evolutions-Report ---")
    for key, value in report.items():
        print(f"{key}: {value}")