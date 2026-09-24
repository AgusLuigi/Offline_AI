# 🌿 Notebooks Folder

## 🎯 Zweck / Purpose
Interaktive Entwicklungs-, Verifikations- und Steuerungsumgebung mittels Jupyter Notebooks.

## 📥 Erlaubte Inhalte / Allowed Files
- *.ipynb - Jupyter Notebooks (01_installation.ipynb, 02_dockereinstellung.ipynb, 03_html_embed.ipynb, 04_sicherheit.ipynb, Srart_mai_ai.ipynb, ollama_model_download_utility.ipynb)

## 🤖 Regeln für zukünftige KI-Modelle / AI Guidelines
Diese Notebooks dienen als geführte Knotenstellen. Jedes Notebook weist auf den nächsten Schritt hin.


# Im Terminal um den Ablage pfaht von ollama zu endern
# 1: Ollama-Prozess vollständig beenden
# Stop-Process -Name "ollama" -Force -ErrorAction SilentlyContinue

# 2: Die Umgebungsvariable OLLAMA_MODELS permanent setzen
# [System.Environment]::SetEnvironmentVariable("OLLAMA_MODELS", "D:\Offline_AI_Models", "User")

# 3: Die Änderung überprüfen
# [System.Environment]::GetEnvironmentVariable("OLLAMA_MODELS", "User")


# Starte Ollama nun wieder neu – entweder über deine Windows-Verknüpfung / das Startmenü oder direkt über das Terminal:
# Start-Process "ollama" # Terminal variante