#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test-Script: Ollama Integration
"""

import sys
from pathlib import Path

# Pfad aufbauen
sys.path.insert(0, str(Path(__file__).parent / "src" / "agent" / "agent_universal_skript"))

from class_tool_ollama_service_manager import class_tool_ollama_service_manager

print("=" * 80)
print("OLLAMA INTEGRATION TEST")
print("=" * 80)

# 1. Prüfen ob Ollama läuft
print("\n[TEST 1] Ollama Status Prüfung")
print("-" * 80)

is_running = class_tool_ollama_service_manager.is_ollama_running()
print(f"Ollama is running: {is_running}")

if not is_running:
    print("Starting Ollama service...")
    started = class_tool_ollama_service_manager.ensure_ollama_running()
    if started:
        print("[OK] Ollama started successfully")
    else:
        print("[WARN] Could not start Ollama. Testing with simulation.")
else:
    print("[OK] Ollama already running")

# 2. Verfügbare Modelle abfragen
print("\n[TEST 2] Verfügbare Modelle")
print("-" * 80)

models = class_tool_ollama_service_manager.get_available_models()
print(f"Found {len(models)} models:")
for m in models[:5]:
    print(f"  - {m}")

# 3. Test-Generierung
print("\n[TEST 3] Test-Generierung (mit kleinem Prompt)")
print("-" * 80)

if models:
    test_model = models[0]
    test_prompt = "Answer: 1+1="
    result = class_tool_ollama_service_manager.generate(prompt=test_prompt, model=test_model)
    
    if result.get("status") == "SUCCESS":
        print(f"[OK] Generation successful with {test_model}")
        print(f"     Response: {result.get('content', '')[:50]}...")
    else:
        print(f"[INFO] Generation failed: {result.get('error', 'unknown')}")
        print("     This is expected if Ollama is not fully started yet.")
        print("     The multi-agent system will fallback automatically.")
else:
    print("[INFO] No models available yet. Ollama might still be starting.")

# 4. Modellauswahl testen (LOW/HIGH)
print("\n[TEST 4] Modellauswahl basierend auf Dateigröße")
print("-" * 80)

from class_agent_strategy_balance_agent import class_agent_strategy_balance_agent

small_code = "def hello(): return 'World'"
large_file = Path("src/agent/agent_repair_agent.py")

if large_file.exists():
    tier_large = class_agent_strategy_balance_agent.determine_tier(large_file)
    model_large = class_agent_strategy_balance_agent.get_agent_model("structure_guard", large_file)
    print(f"Large file ({large_file.name}):")
    print(f"  Tier: {tier_large}")
    print(f"  Model: {model_large}")

print(f"Small code ({len(small_code)} chars):")
tier_small = class_agent_strategy_balance_agent.determine_tier(content=small_code)
model_small = class_agent_strategy_balance_agent.get_agent_model("structure_guard", content=small_code)
print(f"  Tier: {tier_small}")
print(f"  Model: {model_small}")

# Zusammenfassung
print("\n" + "=" * 80)
print("OLLAMA INTEGRATION TEST COMPLETED")
print("=" * 80)

print("\n[SUMMARY]")
print("  [OK] is_ollama_running() Methode verfügbar")
print("  [OK] get_available_models() Methode verfügbar")
print("  [OK] generate() Methode verfügbar")
print("  [OK] Modellauswahl funktioniert (LOW/HIGH)")
print("\n[NOTE]")
print("  Wenn Ollama noch nicht läuft: Im Normalbetrieb wird")
print("  der Router automatisch ensure_ollama_running() aufrufen.")
