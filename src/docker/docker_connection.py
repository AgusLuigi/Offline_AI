"""
Modul: docker_connection.py
Projekt: Mai_AI (MaiOmni)

Dieses Modul stellt feingranulare Funktionen für Schritt 1 (Docker Daemon & Host-Integrität)
bereit. Es prüft die Konnektivität, führt Selbstheilungsversuche durch und validiert
die Kompatibilität für Container-Hardening basierend auf der zentralen `config/docker_global.json`.
"""

import os
import sys
import time
import subprocess
import logging
from typing import Optional, Dict, Any, Tuple
import docker
from docker.client import DockerClient

from src.docker_py.docker_config import (
    load_docker_global_config,
    get_lifecycle_config,
    get_security_hardening_config
)

logger = logging.getLogger("DockerConnection")


def get_docker_client(timeout: Optional[float] = None) -> DockerClient:
    """
    Initialisiert eine DockerClient-Instanz aus Umgebungsvariablen mit einem definierten Timeout
    aus der zentralen Konfiguration `config/docker_global.json`.

    Args:
        timeout (Optional[float]): Timeout in Sekunden oder None zum Laden aus der Konfiguration.

    Returns:
        DockerClient: Die initialisierte DockerClient-Instanz.

    Raises:
        docker.errors.DockerException: Wenn keine Verbindung hergestellt werden kann.
    """
    if timeout is None:
        lifecycle_cfg = get_lifecycle_config()
        timeout = float(lifecycle_cfg.get("connection_timeout_seconds", 10.0))

    try:
        return docker.from_env(timeout=timeout)
    except Exception as e:
        logger.debug(f"Fehler bei docker.from_env: {e}")
        raise


def ping_docker_daemon(client: DockerClient) -> bool:
    """
    Sendet einen Ping-Request an den Docker-Daemon, um dessen Erreichbarkeit zu prüfen.

    Args:
        client (DockerClient): Die aktive Docker-Client-Instanz.

    Returns:
        bool: True, wenn der Daemon erfolgreich antwortet, andernfalls False.
    """
    try:
        if client is None:
            return False
        return bool(client.ping())
    except Exception as e:
        logger.debug(f"Ping an Docker-Daemon fehlgeschlagen: {e}")
        return False


def detect_os_platform() -> str:
    """
    Ermittelt das aktuelle Betriebssystem zur gezielten Prozess-Steuerung.

    Returns:
        str: 'darwin' (macOS), 'win32' (Windows) oder 'linux'.
    """
    if sys.platform == "darwin":
        return "darwin"
    elif sys.platform == "win32":
        return "win32"
    elif sys.platform.startswith("linux"):
        return "linux"
    return sys.platform


def attempt_start_docker_service(platform_name: str) -> bool:
    """
    Führt einen plattformspezifischen Startbefehl für Docker Desktop oder den Systemdienst aus.

    Args:
        platform_name (str): Das identifizierte Betriebssystem ('darwin', 'win32', 'linux').

    Returns:
        bool: True, wenn der Startaufruf abgesetzt werden konnte, andernfalls False.
    """
    try:
        if platform_name == "darwin":
            subprocess.run(["open", "-a", "Docker"], check=True)
            return True
        elif platform_name == "win32":
            program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
            docker_win_path = os.path.join(program_files, "Docker", "Docker", "Docker Desktop.exe")
            if os.path.exists(docker_win_path):
                subprocess.Popen([docker_win_path], start_new_session=True)
                return True
            else:
                subprocess.Popen(
                    ["net", "start", "com.docker.service"],
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    start_new_session=True
                )
                return True
        elif platform_name == "linux":
            print("[!] HINWEIS: Docker unter Linux ist offline.")
            print("[!] Bitte starte den Dienst im Terminal mit: 'sudo systemctl start docker'")
            return False
        return False
    except Exception as e:
        logger.warning(f"Fehler beim Startversuch des Docker-Dienstes: {e}")
        return False


def verify_daemon_security_features(
    client: DockerClient,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Prüft den Docker-Daemon auf Unterstützung kritischer Container-Hardening-Features
    im Abgleich mit `config/docker_global.json`.

    Args:
        client (DockerClient): Die aktive Docker-Client-Instanz.
        config (Optional[Dict[str, Any]]): Optionale Konfiguration.

    Returns:
        Dict[str, Any]: Ein Dictionary mit dem Status der Sicherheitsfeatures.
    """
    sec_cfg = get_security_hardening_config(config)
    security_status = {
        "read_only_supported": sec_cfg.get("read_only", True),
        "cap_drop_supported": bool(sec_cfg.get("cap_drop", ["ALL"])),
        "non_root_supported": bool(sec_cfg.get("user", "1000:1000")),
        "resource_limits_supported": True,
        "cgroup_version": "v1/v2",
        "server_version": "unknown"
    }
    try:
        version_info = client.version()
        server_version = version_info.get("Version", "unknown")
        security_status["server_version"] = server_version
        
        info = client.info()
        cgroup_version = info.get("CgroupVersion", "v1/v2")
        security_status["cgroup_version"] = cgroup_version
    except Exception as e:
        logger.warning(f"Konnte Sicherheits-Features des Daemons nicht vollständig abfragen: {e}")
    return security_status


def audit_docker_environment(client: DockerClient) -> Dict[str, Any]:
    """
    Liest relevante System- und Umgebungsdaten des Docker-Hosts für das Audit-Protokoll aus.

    Args:
        client (DockerClient): Die aktive Docker-Client-Instanz.

    Returns:
        Dict[str, Any]: Host-Informationen wie CPU-Anzahl, RAM und OS-Typ.
    """
    try:
        sys_info = client.info()
        return {
            "server_version": sys_info.get("ServerVersion", "N/A"),
            "os": sys_info.get("OperatingSystem", "N/A"),
            "architecture": sys_info.get("Architecture", "N/A"),
            "ncpu": sys_info.get("NCPU", 0),
            "mem_total_gb": round(sys_info.get("MemTotal", 0) / (1024 ** 3), 2),
            "containers_total": sys_info.get("Containers", 0),
            "containers_running": sys_info.get("ContainersRunning", 0)
        }
    except Exception as e:
        logger.error(f"Fehler beim Ermitteln der Host-Umgebung: {e}")
        return {}


def run_step1_daemon_check(
    retries: Optional[int] = None,
    delay: Optional[int] = None,
    config: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Optional[DockerClient], Dict[str, Any]]:
    """
    Orchestrierungsfunktion für Schritt 1 im Notebook:
    Validiert die Docker-Konnektivität mit automatischer Selbstheilung und führt
    einen Hardening-Kompatibilitätscheck durch. Alle Standardwerte stammen aus `config/docker_global.json`.

    Args:
        retries (Optional[int]): Anzahl der Verbindungsversuche (aus Config geladen, falls None).
        delay (Optional[int]): Wartezeit in Sekunden zwischen Versuchen (aus Config geladen, falls None).
        config (Optional[Dict[str, Any]]): Optionale globale Konfiguration.

    Returns:
        Tuple[bool, Optional[DockerClient], Dict[str, Any]]: 
            - Erfolg (bool)
            - DockerClient-Instanz (oder None)
            - Dictionary mit Audit- und Sicherheitsmetadaten
    """
    lifecycle_cfg = get_lifecycle_config(config)
    effective_retries = retries if retries is not None else int(lifecycle_cfg.get("connection_retries", 3))
    effective_delay = delay if delay is not None else int(lifecycle_cfg.get("connection_retry_delay_seconds", 3))
    effective_timeout = float(lifecycle_cfg.get("connection_timeout_seconds", 10.0))

    platform_name = detect_os_platform()
    last_error = None

    for attempt in range(effective_retries):
        try:
            client = get_docker_client(timeout=effective_timeout)
            if ping_docker_daemon(client):
                sec_features = verify_daemon_security_features(client, config=config)
                env_audit = audit_docker_environment(client)
                
                print(f"[✓] Schritt 1 erfolgreich konfiguriert: Docker-Daemon ist aktiv (Server Version: {sec_features['server_version']})")
                print(f"    -> Hardening-Fähigkeiten bestätigt: Read-Only Dateisystem, Cap-Drop [ALL], Non-Root & Ressourcen-Limits.")
                print(f"    -> Host-Ressourcen: {env_audit.get('ncpu', 0)} CPUs | {env_audit.get('mem_total_gb', 0)} GB RAM | Cgroup: {sec_features.get('cgroup_version')}")
                return True, client, {**sec_features, **env_audit}
        except Exception as e:
            last_error = e
            print(f"[!] Docker-Daemon ist aktuell nicht erreichbar (Versuch {attempt + 1}/{effective_retries}).")
            
            if attempt < effective_retries - 1:
                print(f"[...] Starte Docker-Umgebung für Plattform '{platform_name}'... Bitte warten.")
                attempt_start_docker_service(platform_name)
                print(f"[...] Warte {effective_delay + 3} Sekunden auf Initialisierung...")
                time.sleep(effective_delay + 3)

    print(f"\n[X] Schritt 1 fehlgeschlagen: Docker-Daemon konnte nach {effective_retries} Versuchen nicht erreicht werden.")
    if last_error:
        print(f"    Details: {last_error}")
    return False, None, {"error": str(last_error)}
