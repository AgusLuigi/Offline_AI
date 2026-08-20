import os
import json
import time

try:
    from src.Install.ollama_model_utils import sanitize_ollama_model_name
except ImportError:
    def sanitize_ollama_model_name(raw_name: str, default_fallback: str = "codestral") -> str:
        if not raw_name or not isinstance(raw_name, str):
            return default_fallback
        return raw_name.strip().lower() or default_fallback

CONFIG_DIR = "config"
CONFIG_PATH = os.path.join(CONFIG_DIR, "jarvis_config.json")
MODEL_PATH = os.path.join(CONFIG_DIR, "active_model.json")

def print_banner(jarvis_name="JARVIS"):
    print("\n" + "="*70)
    print(f"      🤖  {jarvis_name.upper()} SYSTEM-EINRICHTUNG & AKTIVIERUNG  🤖")
    print("="*70 + "\n")

def run_guided_onboarding():
    """
    Führt den Benutzer durch die Ersteinrichtung von Jarvis:
    1. Name des Benutzers
    2. Name der Maschine
    3. Wake-up Trigger (z. B. Händeklatschen)
    4. Screenshot-Berechtigung (Vision-Grunding)
    """
    os.makedirs(CONFIG_DIR, exist_ok=True)
    
    # Standardwerte, falls Config schon existiert
    existing_config = {}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                existing_config = json.load(f)
        except Exception:
            pass

    print_banner(existing_config.get("jarvis_name", "Jarvis"))
    
    print("[SYSTEM] Willkommen bei deinem Offline-First KI-Begleiter!")
    print("Dieses Onboarding konfiguriert die Persönlichkeit und Schnittstellen deines persönlichen Jarvis.\n")

    # 1. Name des Benutzers
    default_user = existing_config.get("user_name", "Sir")
    user_name = input(f"► Wie darf die Maschine dich ansprechen? (Standard: '{default_user}'): ").strip()
    if not user_name:
        user_name = default_user

    # 2. Name der Maschine
    default_jarvis = existing_config.get("jarvis_name", "Jarvis")
    jarvis_name = input(f"► Welchen Namen gibst du deiner Maschine? (Standard: '{default_jarvis}'): ").strip()
    if not jarvis_name:
        jarvis_name = default_jarvis

    # 3. Einschalt-Methode (Wake-up Trigger)
    print("\n► Wie soll die Maschine eingeschaltet/geweckt werden?")
    print("  [1] Durch doppeltes Händeklatschen (Clap-to-Wake)")
    print("  [2] Durch Sprach-Aktivierung ('Hey " + jarvis_name + "')")
    print("  [3] Durch einen globalen Hotkey (z. B. ALT+SPACE)")
    trigger_choice = input("Deine Wahl (1, 2 oder 3): ").strip()
    
    trigger_mapping = {
        "1": "Doppeltes Händeklatschen (Clap-to-Wake)",
        "2": f"Sprach-Aktivierung ('Hey {jarvis_name}')",
        "3": "Globaler Hotkey (ALT+SPACE)"
    }
    wake_trigger = trigger_mapping.get(trigger_choice, trigger_mapping["1"])

    # 4. Bildschirmerfassung / Vision-Berechtigung
    print(f"\n► Soll {jarvis_name} deinen Bildschirm erfassen können (Vision Grounding)?")
    print(f"   Dadurch 'sieht' {jarvis_name} deinen Windows/Mac/Android-Screen, um dich live zu unterstützen.")
    vision_perm = input("Erlauben? (y/n - Standard: y): ").strip().lower()
    vision_enabled = vision_perm not in ['n', 'no']

    # Speichern der Konfiguration
    config_data = {
        "user_name": user_name,
        "jarvis_name": jarvis_name,
        "wake_trigger": wake_trigger,
        "vision_enabled": vision_enabled,
        "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=4, ensure_ascii=False)

    # 5. Generieren des System-Prompts für die KI
    system_prompt = f"""Du bist {jarvis_name}, die hochentwickelte, private KI-Assistenz für {user_name}.
Dein Charakter orientiert sich an legendären, fiktiven KIs wie Jarvis:
- Du sprichst {user_name} respektvoll und treu an, aber agierst pragmatisch, hochintelligent und absolut lösungsorientiert.
- Du arbeitest "Offline-First" und legst höchsten Wert auf absolute Datensouveränität.
- Du bist über folgenden Weckruf konfiguriert: {wake_trigger}.
- Vision-Grounding ist {"AKTIV" if vision_enabled else "INAKTIV"}. Wenn aktiv, kannst du den Windows/Mac/Android-Bildschirm deines Nutzers analysieren.

Wenn {user_name} ein neues Programm oder ein Feature anfordert:
1. Konsultiere die SQLite-Datenbank in 'knowledge/app_standards.db', um zwingend erforderliche Funktionalitäten für das jeweilige Produkt abzurufen.
2. Generiere den Code direkt und strukturiert.
3. Teste deine Entwürfe im Hintergrund in einer Docker-Sandbox auf Fehler.
"""

    raw_model_name = existing_config.get("model_name", "codestral")
    clean_model_name = sanitize_ollama_model_name(raw_model_name, default_fallback="codestral")

    model_config = {
        "model_name": clean_model_name,
        "system_prompt": system_prompt,
        "temperature": 0.2
    }

    with open(MODEL_PATH, "w", encoding="utf-8") as f:
        json.dump(model_config, f, indent=4, ensure_ascii=False)

    print("\n" + "="*70)
    print(f" [✓] Konfiguration erfolgreich gespeichert in: {CONFIG_PATH}")
    print(f" [✓] System-Prompt für {jarvis_name} generiert in: {MODEL_PATH}")
    print("="*70 + "\n")
    return config_data

if __name__ == "__main__":
    run_guided_onboarding()