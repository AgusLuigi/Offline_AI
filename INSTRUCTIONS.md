# 🌿 SYSTEM-INBETRIEBNAHME & AUSFÜHRUNGS-HANDBUCH
**Projekt: Mai_AI (MaiOmni) — Das generative, private KI-Betriebssystem**

Dieses Handbuch dokumentiert die exakte Reihenfolge der Schritte, um die Plattform zu initialisieren, die Weboberfläche aufzurufen und globale Einstellungen anzupassen.

---

## 🚀 1. SCHNELLSTART (START DER PLATTFORM)

Der gesamte Stack (Infrastruktur, Gateway und Onboarding) kann mit einem einzigen Befehl aus dem Hauptverzeichnis heraus gestartet werden:

```bash
python src/docker_py/Start_AI.py
```

**Was dieses Skript tut:**
1. Es validiert und erstellt alle benötigten Ordnerstrukturen.
2. Falls du Jarvis noch nicht konfiguriert hast, startet es **vollautomatisch ein geführtes Konsolen-Onboarding** (Fragt nach deinem Namen, dem KI-Namen, Wake-up Triggern und Vision-Berechtigung).
3. Es prüft die Docker-Laufzeitumgebung und repariert sie bei Bedarf selbstständig.
4. Es startet den Reverse Proxy (Traefik) und den OAuth2-Proxy über `docker compose`.
5. Es analysiert deine Hardware (CPU, RAM, GPU) und lädt die passenden LLMs über Ollama.

---

## 🌿 2. NOTEBOOK-AUSFÜHRUNGSREIHENFOLGE (KNOTENSTELLEN)

Wenn du das System modular Schritt für Schritt über Jupyter Notebooks konfigurieren, testen oder erweitern möchtest, halte dich zwingend an diese **feste Reihenfolge**:

| Schritt | Notebook | Zweck / Aktion |
| :--- | :--- | :--- |
| **Schritt 1** | **[01_installation.ipynb](file:notebooks/01_installation.ipynb)** | **Setup & Hardware:** Installiert Core-Bibliotheken im Conda-Environment `MaiOmni` und stößt den Download der lokalen KI-Modelle via Ollama an. (Nutze `01_install.ipynb` für deinen allerersten Conda-Lauf). |
| **Schritt 2** | **[02_dockereinstellung.ipynb](file:notebooks/02_dockereinstellung.ipynb)** | **Infrastruktur:** Startet das Traefik-Netzwerk und den Google OAuth2-Proxy über die Docker-Compose-Dateien. |
| **Schritt 3** | **[03_html_embed.ipynb](file:notebooks/03_html_embed.ipynb)** | **Frontend & Sandbox:** Bereitet das Streamlit-Nutzer-Image vor und demonstriert das Iframe-Embedding-Verfahren (Javes-Alternative). |
| **Schritt 4** | **[04_sicherheit.ipynb](file:notebooks/04_sicherheit.ipynb)** | **Härtungstest:** Simuliert Angriffe auf den `FileGuard` (Pfad-Traversal-Schutz) und verifiziert die RAM/CPU-Begrenzungen der User-Docker-Container. |
| **Täglich** | **[Srart_mai_ai.ipynb](file:notebooks/Srart_mai_ai.ipynb)** | **Das Cockpit:** Lädt das Steuerungs-Dashboard `app_docker.py` und startet deinen persönlichen, isolierten Container mit integrierter Selbstheilungslogik bei Portkonflikten. |

---

## 🌐 3. SEITENAUFRUF & SCHNITTSTELLEN

Nachdem die Startsequenz durchgelaufen ist, ist die Plattform über zwei Schnittstellen erreichbar:

1.  **Lokale Entwicklung & Test:**
    *   **Dashboard-Cockpit:** `http://localhost:8080` (Oder der automatisch ermittelte Ausweichport, falls 8080 belegt ist).
    *   **Zentrale Schnittstelle:** `http://platform.local` (Erfordert lokale DNS-Einträge oder `/etc/hosts` Auflösung).
2.  **Online-Internetzugriff (DuckDNS):**
    *   **Hauptdomain:** `https://mai-ai.duckdns.org` (Vollständig geschützt durch den Google OAuth2-Proxy).

---

## ⚙️ 4. GLOBALE EINSTELLUNGEN & BEGRIFFLICHKEITEN

Alle Kern-Informationen sind zentral im [config/](file:config/) Ordner abgelegt, damit keine doppelten Begriffe entstehen. KIs und Notebooks greifen auf folgende Dateien zu:

*   **[.env](file:.env):**
    Enthält deine geheimen API-Keys, Google Client IDs, DuckDNS-Token und deine Domain. *Wichtig: Diese Datei niemals in Git hochladen!*
*   **[config/jarvis_config.json](file:config/jarvis_config.json):**
    Hier sind deine persönlichen Jarvis-Einstellungen gespeichert (Dein Name, Name deines Jarvis, Wake-Trigger, Vision Grounding Status).
*   **[config/active_model.json](file:config/active_model.json):**
    Enthält den dynamisch generierten System-Prompt (Charakter von Jarvis) und Modellparameter (Temperatur etc.).
*   **[config/project_paths.json](file:config/project_paths.json):**
    Wird stochastisch generiert und schützt deine Verzeichnis-Begriffe vor Duplikaten oder versehentlichem Überschreiben.

---
*Dieses Dokument dient als unantastbarer Leitfaden für Entwickler und zukünftige KI-Modelle. Halte dich bei jeder Modifikation strikt an diese Struktur.*
