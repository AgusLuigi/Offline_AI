#!/usr/bin/env python3
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src" / "agent"))
sys.path.insert(0, str(project_root / "src" / "agent" / "agent_universal_skript"))

from class_agent_ruting_struktur_balance_agent import class_agent_ruting_struktur_balance_agent
from class_logger_audit_execution import class_logger_audit_execution
from class_tool_ollama_service_manager import class_tool_ollama_service_manager

class_logger_audit_execution.initialize_logger()

router = class_agent_ruting_struktur_balance_agent()
print("Router initialized successfully!")
print("Method is_ollama_running available:", hasattr(class_tool_ollama_service_manager, "is_ollama_running"))
