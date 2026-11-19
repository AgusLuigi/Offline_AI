"""setup.py — Offline Coding Agent Setup (Windows)"""

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

# ZENTRALE PFAD-STRUKTUR & SINGLE SOURCE OF TRUTH (SSOT)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DIR_DATA = PROJECT_ROOT / "data"
DIR_MODELS = DIR_DATA / "models"
DIR_MODELS_OLLAMA = DIR_MODELS / "ollama"
DIR_MODELS_HUGGINGFACE = DIR_MODELS / "huggingface"

# Stelle sicher, dass Ollama IMMER in data/models/ollama speichert
DIR_MODELS_OLLAMA.mkdir(parents=True, exist_ok=True)
DIR_MODELS_HUGGINGFACE.mkdir(parents=True, exist_ok=True)
os.environ["OLLAMA_MODELS"] = str(DIR_MODELS_OLLAMA)
os.environ["HF_HOME"] = str(DIR_MODELS_HUGGINGFACE)

# Permanent in Windows User-Environment registrieren
try:
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
            val, _ = winreg.QueryValueEx(key, "OLLAMA_MODELS")
            if val != str(DIR_MODELS_OLLAMA):
                winreg.SetValueEx(key, "OLLAMA_MODELS", 0, winreg.REG_SZ, str(DIR_MODELS_OLLAMA))
    except FileNotFoundError:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_WRITE) as key:
            winreg.SetValueEx(key, "OLLAMA_MODELS", 0, winreg.REG_SZ, str(DIR_MODELS_OLLAMA))
except Exception:
    pass


def run(cmd, check=True, visible=False):
    """
    Führt einen Befehl aus.
    visible=True  → Output wird direkt im Terminal angezeigt (z. B. Download-Fortschritt).
    visible=False → Output wird gecaptured und als stdout zurückgegeben.
    """
    if visible:
        result = subprocess.run(cmd, shell=True, text=True, encoding="utf-8", errors="replace")
        if check and result.returncode != 0:
            print(f"  ✗ Fehler bei: {cmd}")
            sys.exit(1)
        return result
    else:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if check and result.returncode != 0:
            print(f"  ✗ Fehler: {result.stderr.strip()}")
            sys.exit(1)
        return result

def check(cmd):
    """Prüft, ob ein Befehl existiert / erfolgreich ist."""
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace").returncode == 0   

MIN_RAM_TIERS = [8, 12, 16, 24, 32, 48, 64, 80, 128, 256]

RAM_TIERS = {
    "16gb":  {"name": "Kompakt (<= 16 GB RAM)",    "badge": "⚡ [16 GB]",  "min_ram": 16,  "order": 1},
    "32gb":  {"name": "Mid-Range (32 GB RAM)",     "badge": "🚀 [32 GB]",  "min_ram": 32,  "order": 2},
    "64gb":  {"name": "High-End (64 GB RAM)",      "badge": "💎 [64 GB]",  "min_ram": 64,  "order": 3},
    "128gb": {"name": "Extreme (128 GB RAM)",      "badge": "🔥 [128 GB]", "min_ram": 128, "order": 4},
    "256gb": {"name": "Enterprise (256 GB RAM)",   "badge": "👑 [256 GB]", "min_ram": 256, "order": 5},
}

DOMAINS = {
    "code":      {"name": "Coding & Entwicklung",      "badge": "[💻 CODE]",     "order": 1},
    "logik":     {"name": "Logik & Reasoning",         "badge": "[🧠 LOGIK]",    "order": 2},
    "vision":    {"name": "Vision & Multimodal",       "badge": "[👁️ VISION]",   "order": 3},
    "planung":   {"name": "Planung & Architektur",     "badge": "[🎯 PLANUNG]",  "order": 4},
    "tools":     {"name": "Tools & MCP-Agenten",       "badge": "[🛠️ TOOLS]",    "order": 5},
    "embed":     {"name": "Embeddings & Vektor-RAG",   "badge": "[🔍 EMBED]",    "order": 6},
    "smalltalk": {"name": "Leichtbau & Basis",         "badge": "[⚡ BASIS]",    "order": 7},
}

AVAILABLE_MODELS = [
    # TIER 1: KOMPAKT (<= 16 GB RAM) | VRAM: 8–12 GB
    {"id": "qwen2.5-coder:7b",   "label": "Qwen 2.5 Coder (7B)",
     "desc": "Top 1 Coder [16GB] – FIM, SWE-bench & Multi-File Refactorings",
     "size_gb": 4.7,  "ram_tier": "16gb", "min_ram": 16,
     "quant": "Q4", "hw": "both",  "vram_min": 6,
     "forge": True,  "domain": "code",      "tags": ["code", "forge", "autocomplete"]},
    {"id": "codestral:22b",       "label": "Codestral (22B)",
     "desc": "Top 2 Coder [16GB] – 80+ Sprachen, Fill-in-the-Middle IDE-Erkennung",
     "size_gb": 14.0, "ram_tier": "16gb", "min_ram": 16,
     "quant": "Q4", "hw": "cpu",   "vram_min": 0,
     "forge": False, "domain": "code",      "tags": ["code", "autocomplete"]},
    {"id": "deepseek-r1:8b",     "label": "DeepSeek R1 (8B)",
     "desc": "Top 1 Logik [16GB] – Deduktive CoT-Logik & mathematische Problemlösung",
     "size_gb": 4.9,  "ram_tier": "16gb", "min_ram": 16,
     "quant": "Q4", "hw": "both",  "vram_min": 6,
     "forge": True,  "domain": "logik",     "tags": ["logik", "forge", "cot"]},
    {"id": "qwen2.5:7b",         "label": "Qwen 2.5 (7B)",
     "desc": "Top 2 Logik [16GB] – Zuverlässige Instruktionsbefolgung & Argumentation",
     "size_gb": 4.5,  "ram_tier": "16gb", "min_ram": 16,
     "quant": "Q4", "hw": "both",  "vram_min": 6,
     "forge": False, "domain": "logik",     "tags": ["logik"]},
    {"id": "minicpm-v:8b",       "label": "MiniCPM-V (8B)",
     "desc": "Top Vision [16GB] – OCR, UI-Screenshots, Video-Frames (GPU empfohlen)",
     "size_gb": 5.5,  "ram_tier": "16gb", "min_ram": 16,
     "quant": "Q4", "hw": "gpu",   "vram_min": 8,
     "forge": True,  "domain": "vision",    "tags": ["vision", "forge"]},
    {"id": "moondream:1.8b",     "label": "Moondream (1.8B)",
     "desc": "Top Leichtbau-Vision [16GB] – Schnelle Bildprüfung auf minimaler CPU/GPU",
     "size_gb": 1.7,  "ram_tier": "16gb", "min_ram": 16,
     "quant": "F16", "hw": "both",  "vram_min": 2,
     "forge": False, "domain": "vision",    "tags": ["vision", "smalltalk"]},
    {"id": "qwen2.5:14b",        "label": "Qwen 2.5 (14B)",
     "desc": "Top Planung [16GB] – Ausgeglichene Systemarchitektur & Ablaufpläne",
     "size_gb": 9.0,  "ram_tier": "16gb", "min_ram": 16,
     "quant": "Q4", "hw": "cpu",   "vram_min": 0,
     "forge": True,  "domain": "planung",   "tags": ["planung", "forge"]},
    {"id": "hermes3:8b",         "label": "Hermes 3 (8B)",
     "desc": "Top Tools [16GB] – Fehlerfreie JSON-Function-Calls & MCP-Agenten",
     "size_gb": 4.9,  "ram_tier": "16gb", "min_ram": 16,
     "quant": "Q4", "hw": "both",  "vram_min": 6,
     "forge": True,  "domain": "tools",     "tags": ["tools", "forge", "mcp"]},
    {"id": "nomic-embed-text",   "label": "Nomic Embed Text (v1.5)",
     "desc": "Top RAG [16GB] – Semantische Codebase-Indexierung, 8192 Token Kontext",
     "size_gb": 0.3,  "ram_tier": "16gb", "min_ram": 16,
     "quant": "F32", "hw": "both",  "vram_min": 1,
     "forge": True,  "domain": "embed",     "tags": ["embed", "forge", "rag"]},
    {"id": "llama3.2:3b",        "label": "Llama 3.2 (3B)",
     "desc": "Top Basis [16GB] – Ultraschnelle Dialoge, Smalltalk & Terminal-Interaktion",
     "size_gb": 2.0,  "ram_tier": "16gb", "min_ram": 16,
     "quant": "Q4", "hw": "both",  "vram_min": 2,
     "forge": False, "domain": "smalltalk", "tags": ["smalltalk"]},

    # TIER 2: MID-RANGE (32 GB RAM) | VRAM: 12–24 GB
    # Zielgruppe: Entwickler-Workstations,
    {"id": "qwen2.5-coder:14b",  "label": "Qwen 2.5 Coder (14B)",
     "desc": "Top 1 Coder [32GB] – Perfekte Balance aus Tiefe und Geschwindigkeit",
     "size_gb": 9.0,  "ram_tier": "32gb", "min_ram": 32,
     "quant": "Q5", "hw": "both",  "vram_min": 12,
     "forge": True,  "domain": "code",      "tags": ["code", "forge"]},
    {"id": "devstral:24b",       "label": "Devstral Small 2 (24B)",
     "desc": "Top 2 Coder [32GB] – Agentic Multi-File-Edits & Codebase-Refactoring",
     "size_gb": 14.0, "ram_tier": "32gb", "min_ram": 32,
     "quant": "Q4", "hw": "both",  "vram_min": 24,
     "forge": True,  "domain": "code",      "tags": ["code", "forge"]},
    {"id": "deepseek-r1:14b",    "label": "DeepSeek R1 (14B)",
     "desc": "Top 1 Logik [32GB] – Hohe analytische Tiefe für Algorithmen & Debugging",
     "size_gb": 9.0,  "ram_tier": "32gb", "min_ram": 32,
     "quant": "Q5", "hw": "both",  "vram_min": 12,
     "forge": True,  "domain": "logik",     "tags": ["logik", "forge", "cot"]},
    {"id": "deepseek-r1:32b",    "label": "DeepSeek R1 (32B)",
     "desc": "Top 2 Logik [32GB] – Gründliche Chain-of-Thought Beweisführung",
     "size_gb": 20.0, "ram_tier": "32gb", "min_ram": 32,
     "quant": "Q4", "hw": "cpu",   "vram_min": 24,
     "forge": False, "domain": "logik",     "tags": ["logik", "cot"]},
    {"id": "llama3.2-vision:11b","label": "Llama 3.2 Vision (11B)",
     "desc": "Top Vision [32GB] – Diagramme, Architektur-Skizzen, multimodale Dokumente",
     "size_gb": 7.9,  "ram_tier": "32gb", "min_ram": 32,
     "quant": "Q4", "hw": "gpu",   "vram_min": 12,
     "forge": True,  "domain": "vision",    "tags": ["vision", "forge"]},
    {"id": "qwen2.5:32b",        "label": "Qwen 2.5 (32B)",
     "desc": "Top 1 Planung [32GB] – Umfassende Projektkonzeption, PRD & Code-Audits",
     "size_gb": 19.0, "ram_tier": "32gb", "min_ram": 32,
     "quant": "Q4", "hw": "both",  "vram_min": 24,
     "forge": True,  "domain": "planung",   "tags": ["planung", "forge"]},
    {"id": "gemma2:27b",         "label": "Gemma 2 (27B)",
     "desc": "Top 2 Planung [32GB] – Präzise logische Konsistenz und Strukturierung",
     "size_gb": 16.0, "ram_tier": "32gb", "min_ram": 32,
     "quant": "Q4", "hw": "both",  "vram_min": 24,
     "forge": False, "domain": "planung",   "tags": ["planung"]},
    {"id": "command-r:35b",      "label": "Command-R (35B)",
     "desc": "Top Tools [32GB] – Optimiert für Multi-Turn Tool-Einsatz & RAG-Synthese",
     "size_gb": 20.0, "ram_tier": "32gb", "min_ram": 32,
     "quant": "Q4", "hw": "cpu",   "vram_min": 0,
     "forge": True,  "domain": "tools",     "tags": ["tools", "forge", "rag"]},
    {"id": "bge-m3",             "label": "BGE-M3 (Multilingual)",
     "desc": "Top RAG [32GB] – Dense & Lexical Retrieval (100+ Sprachen)",
     "size_gb": 1.2,  "ram_tier": "32gb", "min_ram": 32,
     "quant": "F32", "hw": "both",  "vram_min": 2,
     "forge": True,  "domain": "embed",     "tags": ["embed", "forge", "rag"]},
    {"id": "gemma3:4b",          "label": "Gemma 3 (4B)",
     "desc": "Top Basis [32GB] – Natürlicher Sprachfluss, Textpolitur & Zusammenfassungen",
     "size_gb": 3.2,  "ram_tier": "32gb", "min_ram": 32,
     "quant": "Q4", "hw": "both",  "vram_min": 4,
     "forge": False, "domain": "smalltalk", "tags": ["smalltalk"]},

    # TIER 3: HIGH-END (64 GB RAM) | VRAM: 24–48 GB
    # Zielgruppe: KI-Workstations,

    {"id": "qwen2.5-coder:32b",  "label": "Qwen 2.5 Coder (32B)",
     "desc": "Top 1 Coder [64GB] – Open-Source Benchmark-Champion für Agenten",
     "size_gb": 20.0, "ram_tier": "64gb", "min_ram": 64,
     "quant": "Q5", "hw": "both",  "vram_min": 24,
     "forge": True,  "domain": "code",      "tags": ["code", "forge"]},
    {"id": "deepseek-coder-v2:16b","label": "DeepSeek Coder V2 (16B MoE)",
     "desc": "Top 2 Coder [64GB] – 338 Sprachen, MoE-Architektur, 128k Kontext",
     "size_gb": 8.9,  "ram_tier": "64gb", "min_ram": 64,
     "quant": "Q4", "hw": "gpu",   "vram_min": 24,
     "forge": False, "domain": "code",      "tags": ["code"]},
    {"id": "deepseek-r1:70b",    "label": "DeepSeek R1 (70B)",
     "desc": "Top 1 Logik [64GB] – Elite-Klasse CoT auf Augenhöhe mit Spitzenmodellen",
     "size_gb": 43.0, "ram_tier": "64gb", "min_ram": 64,
     "quant": "Q4", "hw": "cpu",   "vram_min": 48,
     "forge": True,  "domain": "logik",     "tags": ["logik", "forge", "cot"]},
    {"id": "qwen2.5:72b",        "label": "Qwen 2.5 (72B)",
     "desc": "Top 2 Logik [64GB] – Höchstes Sprachverständnis & Multilingual (DE/EN)",
     "size_gb": 47.0, "ram_tier": "64gb", "min_ram": 64,
     "quant": "Q4", "hw": "cpu",   "vram_min": 48,
     "forge": False, "domain": "logik",     "tags": ["logik"]},
    {"id": "qwen2.5-vl:72b",     "label": "Qwen 2.5 VL (72B)",
     "desc": "Top 1 Vision [64GB] – Hochauflösendes Video-Verständnis & UI-Audits (GPU)",
     "size_gb": 47.0, "ram_tier": "64gb", "min_ram": 64,
     "quant": "Q4", "hw": "gpu",   "vram_min": 48,
     "forge": True,  "domain": "vision",    "tags": ["vision", "forge"]},
    {"id": "llama3.2-vision:90b","label": "Llama 3.2 Vision (90B)",
     "desc": "Top 2 Vision [64GB] – Enterprise-grade Bildextraktion & komplexe Tabellen",
     "size_gb": 55.0, "ram_tier": "64gb", "min_ram": 64,
     "quant": "Q4", "hw": "cpu",   "vram_min": 0,
     "forge": False, "domain": "vision",    "tags": ["vision"]},
    {"id": "llama3.3:70b",       "label": "Llama 3.3 (70B)",
     "desc": "Top 1 Planung [64GB] – 128k Kontext, strategische Roadmap & Systemarchitektur",
     "size_gb": 43.0, "ram_tier": "64gb", "min_ram": 64,
     "quant": "Q4", "hw": "cpu",   "vram_min": 48,
     "forge": True,  "domain": "planung",   "tags": ["planung", "forge"]},
    {"id": "mistral-large:123b", "label": "Mistral Large 2 (123B)",
     "desc": "Top Tools [64GB] – Native Funktionsaufrufe, präzise JSON-Governance",
     "size_gb": 45.0, "ram_tier": "64gb", "min_ram": 64,
     "quant": "Q4", "hw": "cpu",   "vram_min": 0,
     "forge": True,  "domain": "tools",     "tags": ["tools", "forge", "mcp"]},
    {"id": "bge-large-en-v1.5",  "label": "BGE-Large-EN (v1.5)",
     "desc": "Top RAG [64GB] – Maximale Vektordichte & Präzision für Codebase-Embeddings",
     "size_gb": 1.3,  "ram_tier": "64gb", "min_ram": 64,
     "quant": "F32", "hw": "both",  "vram_min": 2,
     "forge": False, "domain": "embed",     "tags": ["embed", "rag"]},
    {"id": "phi4:14b",           "label": "Phi-4 (14B)",
     "desc": "Top Basis [64GB] – Microsofts Effizienz-Champion, STEM & Coding-Dialoge",
     "size_gb": 9.1,  "ram_tier": "64gb", "min_ram": 64,
     "quant": "Q5", "hw": "both",  "vram_min": 12,
     "forge": False, "domain": "smalltalk", "tags": ["smalltalk"]},

    # TIER 4: EXTREME (128 GB RAM) | VRAM: 48–80 GB
    # Zielgruppe: Dual-GPU-Systeme,
    {"id": "qwen3-coder-next",   "label": "Qwen3 Coder Next (80B)",
     "desc": "Top 1 Coder [128GB] – 58,7% SWE-bench, 256k Kontext, Multi-Repo Edits",
     "size_gb": 48.0, "ram_tier": "128gb", "min_ram": 128,
     "quant": "Q4", "hw": "cpu",   "vram_min": 48,
     "forge": True,  "domain": "code",      "tags": ["code", "forge"]},
    {"id": "codestral:latest",   "label": "Codestral FP16 (22B Full)",
     "desc": "Top 2 Coder [128GB] – Maximale F16-Präzision, kein Quantisierungsverlust",
     "size_gb": 45.0, "ram_tier": "128gb", "min_ram": 128,
     "quant": "F16", "hw": "gpu",   "vram_min": 48,
     "forge": False, "domain": "code",      "tags": ["code"]},
    {"id": "deepseek-r1:latest", "label": "DeepSeek R1 Q8 (70B)",
     "desc": "Top 1 Logik [128GB] – Q8-Präzision, verlustfreies mathematisches Reasoning",
     "size_gb": 75.0, "ram_tier": "128gb", "min_ram": 128,
     "quant": "Q8", "hw": "cpu",   "vram_min": 80,
     "forge": True,  "domain": "logik",     "tags": ["logik", "forge", "cot"]},
    {"id": "qwen3.5:122b",       "label": "Qwen 3.5 (122B-A10B MoE)",
     "desc": "Top 2 Logik [128GB] – MoE: 10B aktiv, ultraschnelles High-End Reasoning",
     "size_gb": 73.0, "ram_tier": "128gb", "min_ram": 128,
     "quant": "Q4", "hw": "cpu",   "vram_min": 0,
     "forge": False, "domain": "logik",     "tags": ["logik"]},
    {"id": "llama4:scout",       "label": "Llama 4 Scout (109B MoE)",
     "desc": "Top Vision [128GB] – 10M Token Kontext, Frame-by-Frame Videoanalyse (GPU)",
     "size_gb": 62.0, "ram_tier": "128gb", "min_ram": 128,
     "quant": "Q4", "hw": "gpu",   "vram_min": 48,
     "forge": True,  "domain": "vision",    "tags": ["vision", "forge"]},
    {"id": "command-r-plus:104b","label": "Command-R+ (104B)",
     "desc": "Top 1 Planung [128GB] – Multi-Step Task-Planung mit Quellenverweisen",
     "size_gb": 60.0, "ram_tier": "128gb", "min_ram": 128,
     "quant": "Q4", "hw": "cpu",   "vram_min": 0,
     "forge": True,  "domain": "planung",   "tags": ["planung", "forge", "tools"]},
    {"id": "nemotron-4:340b",    "label": "Nemotron-4 (340B Instruct)",
     "desc": "Top 2 Planung [128GB] – Höchste synthetische Qualität für Architektur",
     "size_gb": 75.0, "ram_tier": "128gb", "min_ram": 128,
     "quant": "Q4", "hw": "cpu",   "vram_min": 0,
     "forge": False, "domain": "planung",   "tags": ["planung"]},
    {"id": "qwen3:72b-instruct", "label": "Qwen3 Instruct (72B)",
     "desc": "Top Tools [128GB] – Schema-Treue bei komplexen Tool-Calls & MCP-Chains",
     "size_gb": 47.0, "ram_tier": "128gb", "min_ram": 128,
     "quant": "Q4", "hw": "both",  "vram_min": 48,
     "forge": True,  "domain": "tools",     "tags": ["tools", "forge", "mcp"]},
    {"id": "mxbai-embed-large",  "label": "mxbai-embed-large (v1)",
     "desc": "Top RAG [128GB] – Asymmetrisches Retrieval für Millionen Zeilen Quellcode",
     "size_gb": 1.5,  "ram_tier": "128gb", "min_ram": 128,
     "quant": "F32", "hw": "both",  "vram_min": 2,
     "forge": True,  "domain": "embed",     "tags": ["embed", "forge", "rag"]},
    {"id": "mistral-nemo:12b",   "label": "Mistral NeMo (12B)",
     "desc": "Top Basis [128GB] – Kompakter Allrounder für schnelle Konversation",
     "size_gb": 7.1,  "ram_tier": "128gb", "min_ram": 128,
     "quant": "Q5", "hw": "both",  "vram_min": 8,
     "forge": False, "domain": "smalltalk", "tags": ["smalltalk"]},

    # TIER 5: ENTERPRISE (256 GB RAM) | VRAM: 80 GB+ (Multi-GPU)
    # Zielgruppe: H100/A100 Multi-GPU-Cluster, Mac Studio Ultra Pro (192+ GB)
    {"id": "deepseek-coder-v2:236b", "label": "DeepSeek Coder V2 (236B MoE)",
     "desc": "Top 1 Coder [256GB] – 21B aktiv, unübertroffene Code-Synthese & Systemanalyse",
     "size_gb": 135.0, "ram_tier": "256gb", "min_ram": 256,
     "quant": "Q4", "hw": "cpu",   "vram_min": 0,
     "forge": True,  "domain": "code",      "tags": ["code", "forge"]},
    {"id": "qwen2.5-coder:72b",      "label": "Qwen 2.5 Coder (72B Full)",
     "desc": "Top 2 Coder [256GB] – Dichte 72B Q8-Architektur für fehlerfreie Großprojekte",
     "size_gb": 85.0,  "ram_tier": "256gb", "min_ram": 256,
     "quant": "Q8", "hw": "cpu",   "vram_min": 80,
     "forge": False, "domain": "code",      "tags": ["code"]},
    {"id": "deepseek-r1:671b",       "label": "DeepSeek R1 (671B MoE)",
     "desc": "Top 1 Logik [256GB] – Ultimatives Flaggschiff für formale Logik & Deduktion",
     "size_gb": 140.0, "ram_tier": "256gb", "min_ram": 256,
     "quant": "Q4", "hw": "cpu",   "vram_min": 0,
     "forge": True,  "domain": "logik",     "tags": ["logik", "forge", "cot"]},
    {"id": "wizard-math:70b",        "label": "WizardMath (70B)",
     "desc": "Top 2 Logik [256GB] – Spezialisiert auf Mathematik, Theoreme & Optimierung",
     "size_gb": 80.0,  "ram_tier": "256gb", "min_ram": 256,
     "quant": "Q8", "hw": "cpu",   "vram_min": 80,
     "forge": False, "domain": "logik",     "tags": ["logik"]},
    {"id": "internvl2-pro:78b",      "label": "InternVL 2 Pro (78B)",
     "desc": "Top Vision [256GB] – Wissenschaftliche Diagramme, Video-Sequenzen (GPU)",
     "size_gb": 85.0,  "ram_tier": "256gb", "min_ram": 256,
     "quant": "F16", "hw": "gpu",   "vram_min": 80,
     "forge": True,  "domain": "vision",    "tags": ["vision", "forge"]},
    {"id": "deepseek-v3:671b",       "label": "DeepSeek V3 (671B MoE)",
     "desc": "Top 1 Planung [256GB] – Umfassendstes Wissen für Software-Großprojekte",
     "size_gb": 140.0, "ram_tier": "256gb", "min_ram": 256,
     "quant": "Q4", "hw": "cpu",   "vram_min": 0,
     "forge": True,  "domain": "planung",   "tags": ["planung", "forge"]},
    {"id": "falcon-180b:latest",     "label": "Falcon (180B)",
     "desc": "Top 2 Planung [256GB] – Monumentales Allround-Modell für Strategie & Konzeption",
     "size_gb": 105.0, "ram_tier": "256gb", "min_ram": 256,
     "quant": "Q4", "hw": "cpu",   "vram_min": 0,
     "forge": False, "domain": "planung",   "tags": ["planung"]},
    {"id": "hermes3:70b",            "label": "Hermes 3 (70B)",
     "desc": "Top Tools [256GB] – Vollautonome Multi-Agenten-Orchestrierung & Swarm-Control",
     "size_gb": 45.0,  "ram_tier": "256gb", "min_ram": 256,
     "quant": "Q8", "hw": "both",  "vram_min": 48,
     "forge": True,  "domain": "tools",     "tags": ["tools", "forge", "mcp"]},
    {"id": "text-embedding-3-large", "label": "Embedding 3 Large (Local)",
     "desc": "Top RAG [256GB] – 3072 Dimensionen für enterprise-weite Wissensgraphen",
     "size_gb": 2.5,   "ram_tier": "256gb", "min_ram": 256,
     "quant": "F32", "hw": "both",  "vram_min": 4,
     "forge": False, "domain": "embed",     "tags": ["embed", "rag"]},
    {"id": "qwen2.5:72b-instruct",   "label": "Qwen 2.5 (72B Instruct)",
     "desc": "Top Basis [256GB] – Eloquente, nuancierte Konversation in Q8-Qualität",
     "size_gb": 85.0,  "ram_tier": "256gb", "min_ram": 256,
     "quant": "Q8", "hw": "cpu",   "vram_min": 80,
     "forge": True,  "domain": "smalltalk", "tags": ["smalltalk", "forge"]},
]

# TAG-BESCHREIBUNG (für UI / Auswahl)
TAG_LABELS = {
    "code":         "Code & Refactoring",
    "logik":        "Logik & Reasoning",
    "allrounder":   "Allrounder",
    "planung":      "Planung & Architektur",
    "system":       "System & Automatisierung",
    "vision":       "Vision & Multimodal",
    "tools":        "Tools & MCP",
    "embed":        "Embeddings & RAG",
    "kreativ":      "Kreativ & Synthese",
    "autocomplete": "Autocomplete / IDE",
    "smalltalk":    "Smalltalk & Basis",
}

# Offizieller OpenCode-Standard für lokale Ollama-Nutzung:
# → 'ollama launch opencode --model devstral' ist der offizielle Quickstart-Befehl
# → devstral ist fine-tuned für agentic Tool-Calls, File-Edits & 128k Kontext
OLLAMA_MODEL_DEFAULT = "devstral:24b"

def get_installed_models() -> list:
    """
    Liest die lokal vorhandenen Ollama-Modelle über 'ollama list' aus.
    Liefert eine Liste kleiner, lower-case Modellnamen (z. B. ['qwen3-coder:30b']).
    """
    result = run("ollama list", check=False)
    installed = []
    for line in result.stdout.splitlines():
        parts = line.strip().split()
        if not parts or parts[0].lower() == "name":
            continue
        installed.append(parts[0].lower())
    return installed


def get_model_status(model_id: str, installed_models: list) -> str:
    """
    Ermittelt den zentralen Anzeigestatus eines Modells:
      - '[local]'    -> Modell ist bereits lokal vorhanden (via 'ollama list' erkannt).
      - '[download]' -> Modell ist in der Offline-Bibliothek gelistet und kann via 'ollama pull' geladen werden.
      - '[online]'   -> Modell ist online bzw. im Katalog verfügbar, lokal nicht vorhanden.
    """
    if not model_id or not isinstance(model_id, str):
        return "[online]"
    clean = model_id.strip().lower()
    base = clean.split(":")[0].strip()
    for m in installed_models or []:
        if str(m).strip().lower().split(":")[0].strip() == base:
            return "[local]"
    for m in AVAILABLE_MODELS:
        mid = str(m.get("id") or "").strip().lower()
        if mid.split(":")[0].strip() == base:
            return "[download]"
    return "[online]"


def build_model_entries(installed_models: list) -> list:
    """
    Baut die strukturierte, nach Hardware-RAM-Tiers und Domänen gegliederte
    und alphanumerisch sortierte Modell-Auswahlliste auf.
    Jeder Eintrag enthält:
      - id, label, desc, size_gb, status ('[local]' oder '[download]')
      - domain, domain_name, domain_badge, domain_order
      - ram_tier, ram_tier_name, ram_badge, min_ram
      - forge (bool), forge_badge
      - quant  → Quantisierungsstufe (Q4/Q5/Q8/F16/F32)
      - hw     → Primäre Hardware ('cpu' | 'gpu' | 'both')
      - vram_min → Mindest-VRAM für GPU-Betrieb in GB (0 = kein GPU nötig)
      - hw_badge → Lesbare Hardware-Anzeige mit VRAM-Info
    """
    installed = [str(m).strip().lower() for m in (installed_models or []) if m and str(m).strip()]
    entries = []
    seen_ids = set()
    pool_lookup = {}
    for m in AVAILABLE_MODELS:
        mid = str(m.get("id") or "").strip().lower()
        pool_lookup[mid.split(":")[0].strip()] = m

    def hw_badge(hw: str, quant: str, vram_min: int) -> str:
        """Erzeugt das Hardware-Anzeige-Badge: Modus + Quant + VRAM-Hinweis."""
        icons = {"cpu": "🖥️ CPU", "gpu": "🎮 GPU", "both": "⚡ CPU+GPU"}
        base = icons.get(hw, "🖥️ CPU")
        q = f"[{quant}]" if quant else ""
        v = f" ≥{vram_min}GB VRAM" if vram_min > 0 and hw in ("gpu", "both") else ""
        return f"{base} {q}{v}".strip()

    def add_entry(model_id: str, label: str, desc: str, size_gb, status: str, installed_flag: bool,
                  from_pool: bool, domain: str = "code", ram_tier: str = "16gb", min_ram: int = 16,
                  forge: bool = False, quant: str = "Q4", hw: str = "cpu", vram_min: int = 0) -> None:
        clean_id = str(model_id).strip().lower()
        if clean_id in seen_ids:
            return
        seen_ids.add(clean_id)
        dom_meta = DOMAINS.get(domain, DOMAINS["code"])
        tier_meta = RAM_TIERS.get(ram_tier, RAM_TIERS["16gb"])
        entries.append({
            "id": clean_id,
            "label": label,
            "desc": desc,
            "size_gb": size_gb,
            "status": status,
            "installed": installed_flag,
            "from_pool": from_pool,
            "domain": domain,
            "domain_name": dom_meta["name"],
            "domain_badge": dom_meta["badge"],
            "domain_order": dom_meta["order"],
            "ram_tier": ram_tier,
            "ram_tier_name": tier_meta["name"],
            "ram_badge": tier_meta["badge"],
            "min_ram": min_ram,
            "tier_order": tier_meta["order"],
            "forge": forge,
            "forge_badge": "⭐[CF]" if forge else "🌐[COM]",
            "quant": quant,
            "hw": hw,
            "vram_min": vram_min,
            "hw_badge": hw_badge(hw, quant, vram_min),
        })

    # 1) Alle lokal vorhandenen Modelle
    for name in installed:
        meta = pool_lookup.get(name.split(":")[0].strip())
        if meta:
            add_entry(
                name,
                str(meta.get("label") or name),
                str(meta.get("desc") or "Lokal vorhanden"),
                meta.get("size_gb"),
                "[local]",
                True,
                False,
                domain=meta.get("domain", "code"),
                ram_tier=meta.get("ram_tier", "16gb"),
                min_ram=meta.get("min_ram", 16),
                forge=meta.get("forge", False),
                quant=meta.get("quant", "Q4"),
                hw=meta.get("hw", "cpu"),
                vram_min=meta.get("vram_min", 0),
            )
        else:
            add_entry(name, name, "Lokal vorhanden", None, "[local]", True, False,
                      domain="code", ram_tier="16gb", min_ram=16, forge=False,
                      quant="Q4", hw="cpu", vram_min=0)

    # 2) Alle verfügbaren Bibliotheks-Modelle
    for m in AVAILABLE_MODELS:
        mid = str(m.get("id") or "").strip().lower()
        base = mid.split(":")[0].strip()
        is_local = any(str(i).split(":")[0].strip() == base for i in installed)
        if is_local:
            continue
        add_entry(
            mid,
            str(m.get("label") or mid),
            str(m.get("desc") or ""),
            m.get("size_gb"),
            "[download]",
            False,
            True,
            domain=m.get("domain", "code"),
            ram_tier=m.get("ram_tier", "16gb"),
            min_ram=m.get("min_ram", 16),
            forge=m.get("forge", False),
            quant=m.get("quant", "Q4"),
            hw=m.get("hw", "cpu"),
            vram_min=m.get("vram_min", 0),
        )

    # Sortierung: 1. RAM-Tier, 2. Domäne, 3. Label alphanumerisch
    entries.sort(key=lambda e: (e["tier_order"], e["domain_order"], e["label"].lower()))
    return entries


def prompt_model_selection(default_model: str = OLLAMA_MODEL_DEFAULT) -> list:
    """
    Interaktive Modell-Auswahl strukturiert nach Hardware-RAM-Tiers & Fachdomänen.
    Unterstützt:
      - Einzelne oder kommagetrennte Nummern (z. B. '1, 4, 12, 25')
      - Domänen-Filter (z. B. 'code', 'logik', 'vision', 'planung', 'tools', 'embed', 'smalltalk')
      - RAM-Tier-Filter (z. B. '16gb', '32gb', '64gb', '128gb', '256gb')
      - Schnellfilter: 'forge' oder 'codeforge' (wählt alle CodeForge-zertifizierten Modelle)
      - 'all' (wählt alle gelisteten Modelle)
      - Direkte Eingabe von Modellbezeichnungen
    """
    print("\n╔══════════════════════════════════════════════════════════════════════════════╗")
    print("║          [5/6] MODELL-AUSWAHL – 50 KURATIERTE TOP-MODELLE                    ║")
    print("╠══════════════════════════════════════════════════════════════════════════════╣")
    print("║  RAM-KLASSEN (Mindest-Systemspeicher inkl. KV-Cache & Overhead):             ║")
    print("║   ⚡ [16 GB]  → Kompakt-Laptops & Standard-PCs          (≤ 16 GB RAM)        ║")
    print("║   🚀 [32 GB]  → Produktive Entwickler-Workstations       (≤ 32 GB RAM)       ║")
    print("║   💎 [64 GB]  → High-End KI-Systeme & Dual-Channel-RAM   (≤ 64 GB RAM)       ║")
    print("║   🔥 [128 GB] → Extreme Workstations & Dual-GPU-Setups   (≤ 128 GB RAM)      ║")
    print("║   👑 [256 GB] → Enterprise-Server & Multi-GPU-Cluster    (≤ 256 GB RAM)      ║")
    print("╠══════════════════════════════════════════════════════════════════════════════╣")
    print("║  VRAM-KLASSEN (dedizierter GPU-Speicher für GPU-optimierte Modelle):         ║")
    print("║   🎮  8 GB VRAM → Consumer (RTX 3060/4060)  |  12 GB → RTX 3080/4070         ║")
    print("║   🎮 24 GB VRAM → RTX 3090/4090 (Top-Consumer)                               ║")
    print("║   🎮 48 GB VRAM → RTX 6000 Ada / L40S (Profi-Workstation)                    ║")
    print("║   🎮 80 GB VRAM → A100/H100 (Enterprise-GPU, Multi-GPU Cluster)              ║")
    print("╠══════════════════════════════════════════════════════════════════════════════╣")
    print("║  QUANTISIERUNG:  Q4/Q5 → 4-5 Bit (CPU/RAM-effizient)                         ║")
    print("║                  Q8    → 8 Bit (höhere Qualität, mehr RAM/VRAM nötig)        ║")
    print("║                  F16   → 16 Bit Float (GPU-nativ, braucht viel VRAM)         ║")
    print("╠══════════════════════════════════════════════════════════════════════════════╣")
    print("║  ZERTIFIZIERUNG: ⭐[CF]  = CodeForge-getestet für autonome Agenten           ║")
    print("║                  🌐[COM] = Community-Modell, offline nutzbar                 ║")
    print("╠══════════════════════════════════════════════════════════════════════════════╣")
    print("║  HARDWARE:  🖥️ CPU = läuft im System-RAM  |  🎮 GPU = bevorzugt VRAM          ║")
    print("║             ⚡ CPU+GPU = läuft gut auf beiden (je nach VRAM-Verfügbarkeit)   ║")
    print("╚══════════════════════════════════════════════════════════════════════════════╝")
    installed_models = get_installed_models()
    entries = build_model_entries(installed_models)

    current_tier = None
    for idx, e in enumerate(entries, start=1):
        if e["ram_tier"] != current_tier:
            current_tier = e["ram_tier"]
            tier_desc = {
                "16gb":  "Kompakt · Laptops & Standard-PCs · Modelle ≤ 12 GB on-disk · VRAM 8–12 GB",
                "32gb":  "Mid-Range · Entwickler-WS · Modelle ≤ 20 GB on-disk · VRAM 12–24 GB",
                "64gb":  "High-End · KI-Systeme · Modelle ≤ 50 GB on-disk · VRAM 24–48 GB",
                "128gb": "Extreme · Dual-GPU/Unified-Memory · Modelle ≤ 100 GB on-disk · VRAM 48–80 GB",
                "256gb": "Enterprise · Multi-GPU-Cluster & Server · Modelle ≤ 200 GB on-disk · VRAM 80 GB+",
            }.get(e["ram_tier"], "")
            print("\n  ┌──────────────────────────────────────────────────────────────────────────────┐")
            print(f"  │  {e['ram_badge']}  {e['ram_tier_name'].upper()}")
            print(f"  │  {tier_desc}")
            print("  └──────────────────────────────────────────────────────────────────────────────┘")
        size_txt = f"{e.get('size_gb', '?'):>5.1f} GB" if e.get("size_gb") else "  ?   GB"
        vram_txt = f"VRAM≥{e['vram_min']}GB" if e.get("vram_min", 0) > 0 else "       "
        hw_icon  = {"cpu": "🖥️ ", "gpu": "🎮 ", "both": "⚡ "}.get(e.get("hw", "cpu"), "🖥️ ")
        quant    = e.get("quant", "Q4")
        print(f"    [{idx:2d}] {e['status']:10s} {e['forge_badge']} {e['domain_badge']:14s}"
              f" {hw_icon}[{quant:<3}] {vram_txt}  {size_txt}  {e['label']}")
        print(f"         └─ {e['desc']}\n")

    print("\n  ┌───────────────────────────────────────────────────────────────────────────────┐")
    print("  │  FILTER & AUSWAHL")
    print("  │  • Nummern:    Kommagetrennt             z. B.   → 1, 3, 7, 11")
    print("  │  • Domain:     Kürzel eingeben           z. B.   → code  logik  vision")
    print("  │  │                                               → planung  tools  embed")
    print("  │  │                                               → smalltalk")
    print("  │  • RAM-Tier:   Klasse eingeben           z. B.   → 16gb  32gb  64gb")
    print("  │  │                                               → 128gb  256gb")
    print("  │  • forge:      Alle ⭐ CodeForge-zertifizierten Modelle auf einmal")
    print("  │  • all:        Alle 50 Modelle laden")
    print(f"  │  • [Enter]:   Standard '{default_model:<37}'")
    print("  └───────────────────────────────────────────────────────────────────────────────┘")
    choice = input("  → Deine Auswahl: ").strip().lower()

    selected_models = []
    if not choice:
        selected_models = [default_model]
        print(f"  ✓ Gewählt (Standard): '{default_model}'")
    elif choice in ("forge", "codeforge"):
        selected_models = [e["id"] for e in entries if e["forge"]]
        print(f"  ✓ Schnellfilter 'CODEFORGE' gewählt ({len(selected_models)} Modelle zertifiziert für autonome Agenten).")
    elif choice == "all":
        selected_models = [e["id"] for e in entries]
        print(f"  ✓ Alle {len(selected_models)} Modelle ausgewählt.")
    elif choice in RAM_TIERS:
        selected_models = [e["id"] for e in entries if e["ram_tier"] == choice]
        print(f"  ✓ RAM-Klasse '{RAM_TIERS[choice]['name']}' gewählt ({len(selected_models)} Modelle).")
    elif choice in DOMAINS:
        selected_models = [e["id"] for e in entries if e["domain"] == choice]
        print(f"  ✓ Domäne '{DOMAINS[choice]['name']}' gewählt ({len(selected_models)} Modelle).")
    else:
        parts = [p.strip() for p in choice.replace(";", ",").split(",") if p.strip()]
        for part in parts:
            if part.isdigit():
                val = int(part)
                if 1 <= val <= len(entries):
                    m_id = entries[val - 1]["id"]
                    if m_id not in selected_models:
                        selected_models.append(m_id)
            elif part in ("forge", "codeforge"):
                for e in entries:
                    if e["forge"] and e["id"] not in selected_models:
                        selected_models.append(e["id"])
            elif part in RAM_TIERS:
                for e in entries:
                    if e["ram_tier"] == part and e["id"] not in selected_models:
                        selected_models.append(e["id"])
            elif part in DOMAINS:
                for e in entries:
                    if e["domain"] == part and e["id"] not in selected_models:
                        selected_models.append(e["id"])
            else:
                cleaned = "".join(c for c in part if c.isalnum() or c in "._-:/")
                cleaned = cleaned.strip("._-")
                if cleaned and cleaned not in selected_models:
                    selected_models.append(cleaned)

        if not selected_models:
            selected_models = [default_model]
            print(f"  ⚠ Keine gültige Auswahl erkannt. Verwende Standard: '{default_model}'")
        else:
            print(f"  ✓ Gewählte Modelle ({len(selected_models)}): {selected_models}")
    return selected_models


def prompt_model_cleanup():
    """
    [5/6b] Modell-Verwaltung / Bereinigung:
    Erlaubt das gezielte Löschen von lokal nicht mehr benötigten Modellen via 'ollama rm'.
    Der Nutzer kann einzelne Nummern (z.B. '3'), mehrere durch Komma getrennte Nummern (z.B. '1,2,3') 
    oder Enter zum Überspringen eingeben.
    """
    print("\n[5/6b] Lokale Modell-Bereinigung (Optionale Speicherplatz-Freigabe):")
    installed_models = get_installed_models()
    if not installed_models:
        print("  → Keine lokalen Modelle gefunden, die gelöscht werden könnten.")
        return
    entries = build_model_entries(installed_models)
    # Filtere nur die heraus, die tatsächlich lokal vorhanden sind ([local])
    local_entries = [e for e in entries if e["status"] == "[local]"]
    if not local_entries:
        print("  → Keine lokalen Modelle vorhanden.")
        return
    print("  Aktuell lokal installierte Modelle:")
    for idx, e in enumerate(local_entries, start=1):
        size_txt = f" ({e.get('size_gb')} GB)" if e.get("size_gb") else ""
        print(f"  [{idx}] {e['id']}{size_txt} – {e['desc']}")
    choice = input(
        "  → Möchtest du Modelle löschen? Gib Nummern ein (z.B. 3 oder 1,2) oder Enter zum Überspringen: "
    ).strip()
    if not choice:
        print("  → Übersprungen. Keine Modelle gelöscht.")
        return
    indices_to_delete = []
    for part in choice.replace(";", ",").split(","):
        part = part.strip()
        if part.isdigit():
            val = int(part)
            if 1 <= val <= len(local_entries):
                indices_to_delete.append(val - 1)
    for idx in sorted(set(indices_to_delete), reverse=True):
        model_to_rm = local_entries[idx]["id"]
        print(f"  → Lösche lokales Modell '{model_to_rm}' via ollama rm...")
        run(f'ollama rm "{model_to_rm}"', check=False)
        print(f"  ✓ Modell '{model_to_rm}' wurde entfernt.")


def main():
    print("  Offline Coding Agent Setup")
    print("\n[1/6] Prüfe Python...")
    print(f"  ✓ Python {sys.version.split()[0]}")
    print("\n[2/6] Prüfe PyTorch...")
    if check('python -c "import torch"'):
        ver = run('python -c "import torch; print(torch.__version__)"').stdout.strip()
        print(f"  ✓ PyTorch {ver} ist installiert.")
    else:
        print("  → Installiere PyTorch...")
        if check("nvidia-smi"):
            print("  → NVIDIA GPU erkannt, CUDA-Variante...")
            run('pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126', check=False)
        else:
            print("  → Keine NVIDIA GPU, CPU-Variante...")
            run('pip install torch torchvision torchaudio', check=False)
        print("  ✓ PyTorch installiert.")
    print("\n[3/6] Prüfe Ollama...")
    if check("ollama --version"):
        print("  ✓ Ollama ist installiert.")
    else:
        print("  → Installiere Ollama...")
        run("winget install Ollama.Ollama", check=False)
        print("  ✓ Ollama installiert.")
        print("  ⚠ Neustart des Terminals nötig.")
        input("  Enter drücken nach Neustart...")
    print("\n[4/6] Prüfe Ollama-Dienst...")
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3)
        print(f"  ✓ Ollama läuft bereits (Zielordner: {DIR_MODELS_OLLAMA}).")
    except Exception:
        print(f"  → Starte Ollama mit Zielverzeichnis {DIR_MODELS_OLLAMA}...")
        subprocess.Popen("ollama serve", shell=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(5)
        try:
            urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3)
            print(f"  ✓ Ollama läuft (Modelle landen in: {DIR_MODELS_OLLAMA}).")
        except Exception:
            print("  ⚠ Ollama startet nicht. Starte manuell: ollama serve")
            sys.exit(1)
    print("\n[5/6] Prüfe Modelle...")
    SELECTED_MODELS = prompt_model_selection(OLLAMA_MODEL_DEFAULT)
    prompt_model_cleanup()
    installed_models = get_installed_models()
    for model in SELECTED_MODELS:
        if get_model_status(model, installed_models) != "[local]":
            print(f"  → Lade Modell '{model}' (kann je nach Größe dauern)...")
            run(f'ollama pull "{model}"', check=False, visible=True)
            print(f"  ✓ Modell '{model}' geladen.")
            installed_models = get_installed_models()
        else:
            print(f"  ✓ Modell '{model}' ist bereits lokal vorhanden.")
    PRIMARY_MODEL = SELECTED_MODELS[0]
    print("\n[6/6] Prüfe OpenCode...")
    if check("opencode --version"):
        print("  ✓ OpenCode ist installiert.")
    else:
        if not check("npm --version"):
            print("  → npm nicht gefunden. Installiere Node.js...")
            run("winget install OpenJS.NodeJS.LTS", check=False)
            nodejs_dir = os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "nodejs")
            os.environ["PATH"] = nodejs_dir + os.pathsep + os.environ.get("PATH", "")
            time.sleep(2)
            if not check("npm --version"):
                print("  ⚠ Node.js installiert, aber npm nicht im PATH.")
                print("  → Terminal NEU öffnen und Skript erneut ausführen.")
                sys.exit(0)
            print("  ✓ Node.js installiert.")
        print("  → Installiere OpenCode...")
        npm_global = os.path.join(os.environ.get("APPDATA", ""), "npm")
        nodejs_dir = os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "nodejs")
        os.environ["PATH"] = npm_global + os.pathsep + nodejs_dir + os.pathsep + os.environ.get("PATH", "")
        result = run("npm install -g opencode-ai", check=False)
        if result.returncode != 0:
            print("  → npm-Installation fehlgeschlagen. Versuche Binary-Download...")
            run('powershell -ExecutionPolicy Bypass -Command "irm https://opencode.ai/install.ps1 | iex"', check=False)
        if check("opencode --version"):
            print("  ✓ OpenCode installiert.")
        else:
            print("  ⚠ OpenCode nicht im PATH. Terminal neu öffnen und erneut ausführen.")
            sys.exit(0)   
    config_dir = Path.home() / ".config" / "opencode"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "opencode.json"
    if not config_file.exists():
        models_dict = {}
        for m in SELECTED_MODELS:
            meta = next((item for item in AVAILABLE_MODELS if item["id"] == m), None)
            ctx = 131072 if (meta and meta.get("forge")) else 32768
            models_dict[m] = {
                "name": meta["label"] if meta else m,
                "tools": True,
                "options": {"num_ctx": ctx},
            }
        config = {
            "$schema": "https://opencode.ai/config.json",
            "provider": {
                "ollama": {
                    "npm": "@ai-sdk/openai-compatible",
                    "name": "Ollama (local)",
                    "options": {"baseURL": "http://localhost:11434/v1"},
                    "models": models_dict,
                }
            },
        }
        config_file.write_text(json.dumps(config, indent=2), encoding="utf-8")
        print(f"\n  ✓ Config geschrieben: {config_file}")
        print(f"  ✓ Primärmodell: {PRIMARY_MODEL} | Kontext: {models_dict[PRIMARY_MODEL]['options']['num_ctx'] // 1024}k Token")
    print("  ✓ Setup fertig!")
    print(f"\n  Starte mit: opencode --model ollama/{PRIMARY_MODEL}\n")
    ans = input("Soll ich OpenCode jetzt starten? [J/n]: ")
    if ans.lower() != "n":
        npm_global = os.path.join(os.environ.get("APPDATA", ""), "npm")
        nodejs_dir = os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "nodejs")
        os.environ["PATH"] = npm_global + os.pathsep + nodejs_dir + os.pathsep + os.environ.get("PATH", "")
        os.system("opencode")

if __name__ == "__main__":
    main()   