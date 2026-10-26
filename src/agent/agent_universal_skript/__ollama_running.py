"""
Wrapper für den Ollama-Check.
Delegiert direkt an class_tool_ollama_service_manager aus class_tool_ollama_service_manager.py.
"""
from agent_universal_skript.class_tool_ollama_service_manager import class_tool_ollama_service_manager

OLLAMA_HOST = class_tool_ollama_service_manager.OLLAMA_HOST
OLLAMA_PORT = 11434
SOCKET_TIMEOUT = class_tool_ollama_service_manager.SOCKET_TIMEOUT
API_TIMEOUT = class_tool_ollama_service_manager.API_TIMEOUT
MAX_START_RETRIES = class_tool_ollama_service_manager.MAX_START_RETRIES
RETRY_WAIT_SEC = class_tool_ollama_service_manager.RETRY_WAIT_SEC

def is_port_open(host: str, port: int, timeout: float = SOCKET_TIMEOUT) -> bool:
    return class_tool_ollama_service_manager.is_port_open(host, port, timeout)

def check_and_start_ollama(ollama_host: str = None) -> bool:
    return class_tool_ollama_service_manager.ensure_ollama_running(ollama_host)

if __name__ == "__main__":
    check_and_start_ollama()