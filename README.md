[<img src="https://cdn-icons-png.flaticon.com/512/6295/6295417.png" align="left" width="15%" padding="20">]()

## &nbsp;&nbsp; OFFLINE AI (MAIOMNI PLATFORM) in work 15.06.2026

&nbsp;&nbsp;&nbsp;&nbsp; *Autonomous, Generative, and Fully Private Jarvis Platform*

<p align="left">&nbsp;&nbsp;
    <img src="https://img.shields.io/github/license/AgusLuigi/Offline_AI?style=flat&logo=opensourceinitiative&logoColor=white&color=526CFE" alt="license">
    <img src="https://img.shields.io/github/last-commit/AgusLuigi/Offline_AI?style=flat&logo=git&logoColor=white&color=526CFE" alt="last-commit">
    <img src="https://img.shields.io/github/languages/top/AgusLuigi/Offline_AI?style=flat&logo=python&logoColor=white&color=526CFE" alt="repo-top-language">
    <img src="https://img.shields.io/github/languages/count/AgusLuigi/Offline_AI?style=flat&color=526CFE" alt="repo-language-count">
</p>
<br>

<details><summary>Table of Contents</summary>

- [📍 Overview](#-overview)
- [👾 Features](#-features)
- [📁 Project Structure](#-project-structure)
  - [🗂️ Module Index](#%EF%B8%8F-module-index)
- [🚀 Getting Started](#-getting-started)
  - [📋 Prerequisites](#-prerequisites)
  - [⚙️ Setup & Installation](#%EF%B8%8F-setup--installation)
  - [💻 Running the Platform](#-running-the-platform)
- [🛡️ Security & Privacy](#%EF%B8%8F-security--privacy)
- [🤝 Community & Synchronization](#-community--synchronization)
- [📜 License](#-license)

</details>
<hr>

## 📍 Overview

Offline AI (MaiOmni) ist eine private, hochperformante und vollständig selbstgehostete **Jarvis-Schnittstelle**. Inspiriert von den modernen Software-Design-Richtlinien von **OpenHuman** und **GitHub Spec-Kit** bricht diese Plattform mit dem herkömmlichen Konzept starrer App-Stores. Statt hunderte datenhungriger Apps herunterzuladen, generiert und testet deine persönliche Jarvis-Maschine maßgeschneiderte App-Module live und offline in isolierten Docker-Sandboxes auf deiner eigenen Hardware (NVIDIA-Infrastruktur).

---

## 👾 Features

|   | Feature-Kategorie | Beschreibung & Technische Implementierung |
| :--- | :--- | :--- |
| 🗣️ | **Geführtes Onboarding** | Personalisierung von Name, Jarvis-Name, Weckruf-Methoden (z. B. Händeklatschen) und Visual Grounding direkt beim Systemstart. |
| 🐳 | **Sandbox-Isolation** | Jeder Google-authentifizierte Benutzer arbeitet in einem physisch isolierten Docker-Container mit streng begrenztem RAM und CPU-Ressourcen. |
| 🛡️ | **Vision & Screen Capture** | Native und plattformübergreifende Bildschirmanalyse (Windows, macOS, Linux, Android) zur visuellen Unterstützung. |
| ⚙️ | **Self-Healing-Dienst** | Automatische Fehlerbehebung bei Systemstart (Dienstaktivierung, Port-Ausweich-Scans bei Konflikten, Datei-Integritätsprüfungen). |
| 📖 | **Wissens-Schnittstelle** | SQLite-gestützte Validierung (`knowledge/app_standards.db`) zur Gewährleistung globaler App-Qualitätsstandards (z. B. Navigation, Dateimanager). |
| 🔒 | **Clientseitige Privacy** | Lokale Maskierung und Tokenisierung sensibler Daten (IBANs, Namen) vor einer optionalen Synchronisation. |

---

## 📁 Project Structure

```text
Offline_AI/
├── config/              # Single Source of Truth für globale Variablen & Jarvis-Profile
├── data/                # Isolierte Workspaces der registrierten Benutzer
├── docker/              # Dockerfiles und Build-Vorgaben für die Containerisierung
├── knowledge/           # SQLite-Datenbanken mit Spezifikationsvorgaben
├── logs/                # Erfassung aller Laufzeitfehler für die nächtliche Optimierung
├── notebooks/           # Ausführbare Knotenstellen (01 bis 04) & Steuerungs-Cockpits
├── privacy/             # Skripte zur clientseitigen Datenanonymisierung
├── src/                 # Festes Python-Quellcode-Fundament (Bootstrapper)
└── temp/                # Temporärer Speicher, asynchroner Sync-Puffer & Trainingsdaten
```

### 🗂️ Module Index

*   **[Start_AI.py](file:src/docker_py/Start_AI.py):** Der zentrale System-Bootstrapper. Führt Onboarding durch, prüft Docker und fährt die Traefik-Proxy-Infrastruktur hoch.
*   **[jarvis_agent.py](file:src/Jarvis/jarvis_agent.py):** Kognitiver Kern. Verwaltet Benutzeranfragen, Datenbankprüfungen und Vision-Grounding.
*   **[screen_grabber.py](file:src/Jarvis/screen_grabber.py):** Selbstheilende Bildschirmanalyse mit Unterstützung von nativen Schnittstellen und simulierten Fallbacks.
*   **[jarvis_onboarding.py](file:src/Jarvis/jarvis_onboarding.py):** Geführtes Setup des KI-Begleiters zur Erzeugung des individuellen System-Prompts.
*   **[app_docker.py](file:src/docker_py/app_docker.py):** Interaktive Benutzeroberfläche zur Systemsteuerung und Live-Visualisierung der Containerlandschaft.

---

## 🚀 Getting Started

### 📋 Prerequisites

*   **Betriebssystem:** Windows 10/11, macOS oder Linux.
*   **Umgebung:** Python 3.10+ (Empfohlen: Anaconda/Miniconda).
*   **Containerisierung:** Docker Desktop / Docker Engine aktiv.
*   **KI-Modell-Server:** Ollama lokal auf dem Host-Rechner installiert.

### ⚙️ Setup & Installation

1.  **Conda-Umgebung aufbauen & Abhängigkeiten laden:**
    Führe das Notebook `01_install.ipynb` oder die modularisierte Spezifikation aus:
    ```bash
    # Erstellt das Conda-Environment "MaiOmni"
    python src/Install/install.py
    ```

2.  **Konfiguration vorbereiten:**
    Kopiere die Umgebungsvariablen-Schablone und trage deine Domain und Google OAuth-Keys ein:
    ```bash
    cp .env.example .env
    ```

### 💻 Running the Platform

Starte die gesamte Plattform mit einem einzigen Befehl:
```bash
python src/docker_py/Start_AI.py
```
*Folge den interaktiven Onboarding-Anweisungen in deiner Konsole, um deinen Jarvis einzurichten!*

Für die interaktive, schrittweise Verifikation und das Härtungstraining stehen dir die **ausführbaren Knotenstellen** im `notebooks/`-Ordner zur Verfügung (von `01_installation.ipynb` bis `04_sicherheit.ipynb`).

---

## 🛡️ Security & Privacy

Offline AI stellt deine Datensouveränität in den Mittelpunkt:
*   **Data Residency:** Alle Benutzer-Workspaces liegen physikalisch auf deiner lokalen Hardware unter `/app/users/{username}/`.
*   **Clientseitige Tokenisierung:** Das `privacy/`-Modul anonymisiert sensible Texte lokal auf dem Endgerät vor jeglicher Übertragung.
*   **FileGuard-Schutz:** Verhindert Path-Traversal-Angriffe und isoliert Benutzer-Dockerinstanzen voneinander.

---

## 🤝 Community & Synchronization

Das System unterstützt einen asynchronen Synchronisationsfluss. Unterwegs aufgezeichnete Sprachnotizen und Feature-Requests werden verschlüsselt zwischengespeichert und im Heimnetzwerk auf deinen NVIDIA-Server hochgeladen. In inaktiven Systemstunden (Idle-Time) generiert und verifiziert der Server die gewünschten Applikationsknöpfe und synchronisiert sie zurück auf dein Gerät.

---

## 📜 License

Dieses Projekt ist unter der **MIT-Lizenz** lizenziert. Weitere Details findest du im Repository.

---
*Generated with 💙 and inspired by readme-ai guidelines.*
