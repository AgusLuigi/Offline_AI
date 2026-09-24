"""
Legacy Wrapper für den Ollama-Check.
Delegiert direkt an OllamaManager aus class_ollama_manager.py.
"""
from agent_universal_skript.class_ollama_manager import OllamaManager

DEFAULT_OLLAMA_HOST = OllamaManager.DEFAULT_OLLAMA_HOST
DEFAULT_OLLAMA_PORT = 11434
SOCKET_TIMEOUT = OllamaManager.SOCKET_TIMEOUT
API_TIMEOUT = OllamaManager.API_TIMEOUT
MAX_START_RETRIES = OllamaManager.MAX_START_RETRIES
RETRY_WAIT_SEC = OllamaManager.RETRY_WAIT_SEC

def is_port_open(host: str, port: int, timeout: float = SOCKET_TIMEOUT) -> bool:
    return OllamaManager.is_port_open(host, port, timeout)

def check_and_start_ollama(ollama_host: str = None) -> bool:
    return OllamaManager.ensure_ollama_running(ollama_host)

if __name__ == "__main__":
    check_and_start_ollama()