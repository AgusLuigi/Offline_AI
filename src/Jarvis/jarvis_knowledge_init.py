import sqlite3
import os
import sys

# Pfad zur Wissensdatenbank
DB_DIR = "knowledge"
DB_PATH = os.path.join(DB_DIR, "app_standards.db")

def initialize_knowledge_db():
    """
    Initialisiert die SQLite-Wissensdatenbank für die Jarvis-Maschine
    und befüllt sie mit den Standardvorgaben (Google Maps Funktionen etc.).
    """
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Tabellen erstellen
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS app_categories (
        category_id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_name VARCHAR(100) NOT NULL UNIQUE,
        description TEXT
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS required_features (
        feature_id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER,
        feature_name VARCHAR(150) NOT NULL,
        reference_provider VARCHAR(100),
        specification_details TEXT,
        FOREIGN KEY(category_id) REFERENCES app_categories(category_id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ai_learned_code_templates (
        template_id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER,
        feature_name VARCHAR(150),
        python_streamlit_code TEXT,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(category_id) REFERENCES app_categories(category_id)
    );
    """)

    # 2. Seed-Daten einfügen (App-Kategorien)
    categories = [
        ('Navigation', 'Plattformübergreifende Karten- und Routenführung für Fußgänger, Fahrräder, Autos, Züge und Flugzeuge.'),
        ('Dateimanager', 'Sicherer, lokaler Dateimanager mit integrierter KI-Suchfunktion und automatischer Bereinigung.'),
        ('Notizen & Brainstorming', 'Asynchrones Protokollierungs- und Dokumentations-System mit automatischer Strukturierung.')
    ]
    
    for cat_name, desc in categories:
        cursor.execute("INSERT OR IGNORE INTO app_categories (category_name, description) VALUES (?, ?)", (cat_name, desc))

    # 3. Seed-Daten für Navigation abrufen (Zuweisung der ID)
    cursor.execute("SELECT category_id FROM app_categories WHERE category_name = 'Navigation'")
    nav_id = cursor.fetchone()[0]

    # Zwingend erforderliche Navigations-Features (Vollständigkeitskriterien)
    nav_features = [
        ('Fußgänger-Karten', 'Google Maps / OSM', 'Lokale Kartendarstellung, Fußgängerpfade, POI-Suche (Points of Interest), Schritt-für-Schritt-Führung.'),
        ('Fahrrad-Routing', 'Komoot / Google Maps', 'Fahrradtaugliche Wege, Höhenprofile, Berücksichtigung von unbefestigten Straßen und Steigungen.'),
        ('Zugverbindung-Anzeige', 'DB Navigator / Google Transit', 'Abfrage von Fahrplänen, Zugnummern, Verspätungs-Anzeigen und Umsteige-Stationen.'),
        ('Fahrzeug-Navigation', 'Waze / Google Maps', 'Echtzeit-Staudaten, optimierte Routenberechnung für Pkw, Geschwindigkeitsbegrenzungen.'),
        ('Flugrouten-Planer', 'Flightradar24', 'Flugsuche, Distanz- und Zeitberechnungen, Flughafen-Informationen und Transitrouten.')
    ]

    for feat_name, ref, spec in nav_features:
        # Verhindert Duplikate beim wiederholten Ausführen
        cursor.execute("""
        SELECT COUNT(*) FROM required_features 
        WHERE category_id = ? AND feature_name = ?
        """, (nav_id, feat_name))
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
            INSERT INTO required_features (category_id, feature_name, reference_provider, specification_details)
            VALUES (?, ?, ?, ?)
            """, (nav_id, feat_name, ref, spec))

    conn.commit()
    conn.close()
    print(f"[✓] SQLite Wissensdatenbank erfolgreich initialisiert unter: {DB_PATH}")

if __name__ == "__main__":
    initialize_knowledge_db()