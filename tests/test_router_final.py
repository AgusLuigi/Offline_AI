#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src" / "agent" / "agent_universal_skript"))

from class_agent_ruting_struktur_balance_agent import class_agent_ruting_struktur_balance_agent
from class_logger_audit_execution import class_logger_audit_execution

class_logger_audit_execution.initialize_logger()

router = class_agent_ruting_struktur_balance_agent()
print("Router initialized successfully!")
print("Method is_ollama_running available:", hasattr(router.ollama_manager, "is_ollama_running") if router.ollama_manager else "N/A")
