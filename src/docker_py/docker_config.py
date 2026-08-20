"""
Modul: docker_config.py
Projekt: Mai_AI (MaiOmni)

Zentraler Konfigurations-Manager für Docker, Ingress, Security, Quotas und Lifecycle.
Lädt und validiert die zentrale `config/docker_global.json`, damit keinerlei Hardcoding-Werte
in den jeweiligen Python-Skripten verstreut sind.
"""

import os
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("DockerConfig")

DEFAULT_FALLBACK_CONFIG: Dict[str, Any] = {
    "meta": {
        "project": "Mai_AI",
        "version": "2.0.0",
        "description": "Zentrale globale Konfiguration für Docker, Ingress, Security, Quotas & Lifecycle"
    },
    "network": {
        "name": "mai-ai_network",
        "driver": "bridge",
        "attachable": True,
        "domain_name": "mai-ai.duckdns.org",
        "local_domain": "platform.local",
        "service_port": 8000,
        "host_port": 8080,
        "ollama_port": 11434,
        "traefik_priority": "20"
    },
    "storage": {
        "required_volumes": [
            "mai_ai_local_models",
            "mai_ai_db_data",
            "mai_ai_config"
        ],
        "user_quota_max_mb": 500.0,
        "base_users_dir": "data/users",
        "base_inbox_dir": "data/inbox"
    },
    "containers": {
        "default_image": "python:3.11-slim",
        "mai_ai_image": "mai_ai_image:latest",
        "ollama_image": "ollama/ollama:latest",
        "engine_container_name": "mai_ai_ollama_engine",
        "traefik_container_name": "traefik_gateway",
        "oauth_container_name": "oauth2_proxy"
    },
    "security_hardening": {
        "read_only": True,
        "cap_drop": ["ALL"],
        "security_opt": ["no-new-privileges:true"],
        "user": "1000:1000",
        "tmpfs": {
            "/tmp": "rw,noexec,nosuid,size=64m",
            "/run": "rw,noexec,nosuid,size=32m"
        }
    },
    "resource_limits": {
        "mem_limit": "1g",
        "cpu_cores": 1.0,
        "nano_cpus": 1000000000,
        "memswap_limit": "1g",
        "default_instance_mem": "512m",
        "default_instance_cpu": 0.5
    },
    "lifecycle": {
        "idle_timeout_minutes": 10.0,
        "auto_shutdown_enabled": True,
        "on_demand_wakeup_enabled": True,
        "connection_timeout_seconds": 10.0,
        "connection_retries": 3,
        "connection_retry_delay_seconds": 3
    },
    "environment_variables": {
        "required_keys": [
            "GOOGLE_CLIENT_ID",
            "GOOGLE_CLIENT_SECRET",
            "COOKIE_SECRET",
            "DOMAIN_NAME"
        ],
        "env_file_path": ".env"
    },
    "sqlite_inbox": {
        "db_filename": "user_inbox.db",
        "shared_db_filename": "platform_inbox.db",
        "default_priority": 1,
        "default_model": "Codestral"
    }
}


def find_project_root() -> str:
    """
    Ermittelt das Stammverzeichnis des Projekts über das Auffinden von `config/` und `data/`.

    Returns:
        str: Absoluter Pfad zum Projektverzeichnis.
    """
    current = os.path.abspath(os.getcwd())
    candidates = [
        current,
        os.path.abspath(os.path.join(current, "..")),
        os.path.abspath(os.path.join(current, "../..")),
    ]
    for c in candidates:
        if os.path.exists(os.path.join(c, "config", "docker_global.json")) or (
            os.path.exists(os.path.join(c, "config")) and os.path.exists(os.path.join(c, "data"))
        ):
            return c
    return os.path.abspath(os.path.join(current, ".."))


def get_default_config_path() -> str:
    """
    Liefert den Standardpfad zur Datei `config/docker_global.json`.

    Returns:
        str: Absoluter Pfad zur Konfigurationsdatei.
    """
    root = find_project_root()
    return os.path.join(root, "config", "docker_global.json")


def load_docker_global_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Lädt die zentrale Docker-Konfiguration aus `config/docker_global.json`.
    Falls die Datei nicht existiert oder fehlerhaft ist, wird der definierte Standard
    zurückgegeben und geloggt.

    Args:
        config_path (Optional[str]): Benutzerdefinierter Pfad oder None für automatische Auflösung.

    Returns:
        Dict[str, Any]: Die geladene Konfiguration als verschachteltes Dictionary.
    """
    target_path = config_path or get_default_config_path()

    if not os.path.exists(target_path):
        logger.warning(f"Konfigurationsdatei nicht gefunden unter {target_path}. Nutze Fallback-Konfiguration.")
        return DEFAULT_FALLBACK_CONFIG.copy()

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.debug(f"Konfiguration erfolgreich aus {target_path} geladen.")
        return data
    except Exception as e:
        logger.error(f"Fehler beim Lesen der Konfigurationsdatei {target_path}: {e}")
        return DEFAULT_FALLBACK_CONFIG.copy()


def save_docker_global_config(config_data: Dict[str, Any], config_path: Optional[str] = None) -> bool:
    """
    Speichert eine aktualisierte Konfiguration in die `config/docker_global.json`.

    Args:
        config_data (Dict[str, Any]): Das zu serialisierende Dictionary.
        config_path (Optional[str]): Zielpfad oder None für Standard.

    Returns:
        bool: True bei Erfolg, andernfalls False.
    """
    target_path = config_path or get_default_config_path()
    try:
        os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)
        logger.info(f"Konfiguration erfolgreich in {target_path} gespeichert.")
        return True
    except Exception as e:
        logger.error(f"Fehler beim Schreiben der Konfiguration nach {target_path}: {e}")
        return False


def get_network_config(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Liefert die Netzwerk- und Ingress-Parameter."""
    cfg = config or load_docker_global_config()
    return cfg.get("network", DEFAULT_FALLBACK_CONFIG["network"])


def get_storage_config(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Liefert die Volume- und Storage-Quota-Parameter."""
    cfg = config or load_docker_global_config()
    return cfg.get("storage", DEFAULT_FALLBACK_CONFIG["storage"])


def get_containers_config(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Liefert die Standard-Container- und Image-Namen."""
    cfg = config or load_docker_global_config()
    return cfg.get("containers", DEFAULT_FALLBACK_CONFIG["containers"])


def get_security_hardening_config(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Liefert die Kernel- und Hardening-Sicherheitsoptionen (Read-Only, Cap-Drop, etc.)."""
    cfg = config or load_docker_global_config()
    return cfg.get("security_hardening", DEFAULT_FALLBACK_CONFIG["security_hardening"])


def get_resource_limits_config(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Liefert die CPU-, RAM- und Swap-Limits."""
    cfg = config or load_docker_global_config()
    return cfg.get("resource_limits", DEFAULT_FALLBACK_CONFIG["resource_limits"])


def get_lifecycle_config(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Liefert die Timeout-, Retry- und Auto-Shutdown-Parameter."""
    cfg = config or load_docker_global_config()
    return cfg.get("lifecycle", DEFAULT_FALLBACK_CONFIG["lifecycle"])


def get_env_variables_config(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Liefert die zu prüfenden Umgebungsvariablen."""
    cfg = config or load_docker_global_config()
    return cfg.get("environment_variables", DEFAULT_FALLBACK_CONFIG["environment_variables"])


def get_sqlite_inbox_config(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Liefert die SQLite-Inbox-Konfiguration."""
    cfg = config or load_docker_global_config()
    return cfg.get("sqlite_inbox", DEFAULT_FALLBACK_CONFIG["sqlite_inbox"])
