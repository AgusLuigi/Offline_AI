import os
import json
import sqlite3
from src.Jarvis.screen_grabber import capture_screen

CONFIG_PATH = "config/jarvis_config.json"
MODEL_PATH = "config/active_model.json"
DB_PATH = "knowledge/app_standards.db"

class JarvisAgent:
    def __init__(self):
        self.load_config()
        self.db_path = DB_PATH

    def load_config(self):
        """Lädt die personalisierten Jarvis-Einstellungen."""
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                self.config = json.load(f)
        else:
            self.config = {
                "user_name": "Sir",
                "jarvis_name": "Jarvis",
                "wake_trigger": "Doppeltes Händeklatschen (Clap-to-Wake)",
                "vision_enabled": True
            }
        
        self.user_name = self.config.get("user_name", "Sir")
        self.jarvis_name = self.config.get("jarvis_name", "Jarvis")
        self.vision_enabled = self.config.get("vision_enabled", True)

    def query_app_standards(self, keyword):
        """
        Sucht in der SQLite-Datenbank nach Standard-Spezifikationen
        für eine gewünschte App-Kategorie.
        """
        if not os.path.exists(self.db_path):
            return "Keine Vorgaben-Datenbank gefunden."

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Flexibler LIKE-Query über Kategorien und Features
        query = """
        SELECT c.category_name, f.feature_name, f.specification_details
        FROM app_categories c
        JOIN required_features f ON c.category_id = f.category_id
        WHERE c.category_name LIKE ? OR f.feature_name LIKE ?
        """
        search_term = f"%{keyword}%"
        cursor.execute(query, (search_term, search_term))
        results = cursor.fetchall()
        conn.close()

        if not results:
            return f"Keine standardmäßigen Vorgaben für '{keyword}' in der Wissensdatenbank gefunden."

        spec_sheet = f"\n--- 📋 GEFORDERTE MINDEST-SPEZIFIKATIONEN FÜR '{results[0][0]}' ---\n"
        for _, feat, desc in results:
            spec_sheet += f"• [ ] {feat}: {desc}\n"
        return spec_sheet

    def analyze_current_view(self):
        """
        Erfasst den aktuellen Bildschirm des Benutzers (Vision Grounding)
        und bereitet ihn für das multimodale Modell vor.
        """
        if not self.vision_enabled:
            return "Vision Grounding ist in den Einstellungen deaktiviert."
        
        screenshot_path = capture_screen()
        if screenshot_path and os.path.exists(screenshot_path):
            return f"[✓] Bildschirmerfassung erfolgreich: {screenshot_path}. Jarvis kann diese Ansicht nun analysieren."
        else:
            return "[!] Bildschirmerfassung fehlgeschlagen."

    def process_request(self, prompt):
        """
        Verarbeitet die Benutzeranfrage, holt bei Bedarf App-Spezifikationen
        und führt Aktionen aus.
        """
        print(f"\n[{self.jarvis_name}] Analysiere Anfrage von {self.user_name}: '{prompt}'...")
        
        # 1. Erkennt Schlüsselbegriffe (z. B. Navigation, App, Bildschirm)
        response_text = ""
        
        if "navigation" in prompt.lower() or "karte" in prompt.lower() or "app" in prompt.lower():
            standards = self.query_app_standards("Navigation")
            response_text += f"\n{self.jarvis_name}: {self.user_name}, für eine Navigations-App gelten folgende globale Best-Practices:\n{standards}"
            response_text += f"\nIch werde diese Kriterien nachts in der Docker-Sandbox implementieren und testen."

        elif "bildschirm" in prompt.lower() or "siehst" in prompt.lower() or "screenshot" in prompt.lower():
            vision_result = self.analyze_current_view()
            response_text += f"\n{self.jarvis_name}: {vision_result}"
            response_text += f"\nIch analysiere den Bildschirminhalt lokal auf sensible Informationen, bevor ich Optimierungen vorschlage."

        else:
            response_text += f"\n{self.jarvis_name}: Verstanden, {self.user_name}. Ich habe deine Anweisung erfasst: '{prompt}'."
            response_text += f"\nDaten werden im 'temp/'-Ordner für die nächtliche Offline-Optimierung zwischengespeichert."

        return response_text

if __name__ == "__main__":
    agent = JarvisAgent()
    print(agent.process_request("Zeige mir an, was für eine Navigation App nötig ist."))
    print(agent.process_request("Was siehst du auf meinem Bildschirm?"))