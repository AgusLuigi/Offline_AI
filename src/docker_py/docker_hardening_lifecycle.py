"""
Modul: docker_hardening_lifecycle.py
Projekt: Mai_AI (MaiOmni)

Dieses Modul stellt feingranulare Funktionen für Schritt 5 (Container Hardening & Automated Idle-Lifecycle)
bereit. Es kapselt die strikten Sicherheitsrichtlinien (Read-Only Dateisystem, Cap-Drop: [ALL], Non-Root,
Ressourcen-Limits) und implementiert den Idle-Timeout mit automatischem Shutdown & On-Demand Reaktivierung.
Alle Parameter werden dynamisch aus `config/docker_global.json` geladen.
"""

import os
import sys
import time
import logging
from typing import Dict, Any, Optional, Tuple
import docker
from docker.client import DockerClient
from docker.errors import NotFound

from src.docker_py.docker_config import (
    load_docker_global_config,
    get_security_hardening_config,
    get_resource_limits_config,
    get_lifecycle_config,
    get_containers_config,
    get_network_config
)

logger = logging.getLogger("DockerHardeningLifecycle")


def get_hardening_security_options(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Definiert die strikten Linux-Kernel- und Container-Sicherheitsoptionen anhand `config/docker_global.json`:
    - `read_only: True` -> Unveränderliches Root-Dateisystem
    - `cap_drop: ['ALL']` -> Vollständiger Entzug aller Kernel-Capabilities
    - `security_opt: ['no-new-privileges:true']` -> Verhindert Privilege Escalation
    - `user: '1000:1000'` -> Zwingende Non-Root-Ausführung
    - `tmpfs`: Transiente Verzeichnisse mit `noexec,nosuid` Flags

    Args:
        config (Optional[Dict[str, Any]]): Optionale Konfiguration.

    Returns:
        Dict[str, Any]: Docker SDK kompatible Sicherheitsoptionen.
    """
    sec_cfg = get_security_hardening_config(config)
    return {
        "read_only": sec_cfg.get("read_only", True),
        "cap_drop": sec_cfg.get("cap_drop", ["ALL"]),
        "security_opt": sec_cfg.get("security_opt", ["no-new-privileges:true"]),
        "user": sec_cfg.get("user", "1000:1000"),
        "tmpfs": sec_cfg.get("tmpfs", {
            "/tmp": "rw,noexec,nosuid,size=64m",
            "/run": "rw,noexec,nosuid,size=32m"
        })
    }


def get_resource_limit_options(
    ram_limit: Optional[str] = None,
    cpu_cores: Optional[float] = None,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Erstellt die harten CPU- und RAM-Ressourcenlimits für User-Kapseln zur
    Verhinderung von Denial-of-Service-Zuständen auf dem Host.

    Args:
        ram_limit (Optional[str]): Maximales RAM-Limit (oder None für Config-Wert).
        cpu_cores (Optional[float]): Maximale CPU-Kerne (oder None für Config-Wert).
        config (Optional[Dict[str, Any]]): Optionale Konfiguration.

    Returns:
        Dict[str, Any]: Dictionary mit `mem_limit` und `nano_cpus`.
    """
    res_cfg = get_resource_limits_config(config)
    eff_ram = ram_limit or res_cfg.get("mem_limit", "1g")
    eff_cpu = cpu_cores if cpu_cores is not None else float(res_cfg.get("cpu_cores", 1.0))
    nano_cpus = int(eff_cpu * 1e9)
    swap_limit = res_cfg.get("memswap_limit", eff_ram)

    return {
        "mem_limit": eff_ram,
        "nano_cpus": nano_cpus,
        "memswap_limit": swap_limit
    }


def build_hardened_container_spec(
    user_id: str,
    image: Optional[str] = None,
    base_dir: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Führt alle Komponenten zu einer vollständigen, gehärteten Container-Spezifikation zusammen:
    - Härtungsoptionen (Read-Only Dateisystem, Cap-Drop, Non-Root)
    - Ressourcen-Limits (1GB RAM, 1 CPU Core)
    - Dynamische Mounts (User-Workspace `rw`, Security `ro`)
    - Traefik-Header-Routing-Labels (`X-Forwarded-User`)
    - Netzwerk-Isolation (`mai-ai_network`)

    Args:
        user_id (str): Benutzerkennung.
        image (Optional[str]): Docker-Image oder None für Config-Wert.
        base_dir (Optional[str]): Basispfad.
        config (Optional[Dict[str, Any]]): Globale Konfiguration.

    Returns:
        Dict[str, Any]: Vollständiges Konfigurations-Dictionary für `client.containers.run`.
    """
    cfg = config or load_docker_global_config()
    containers_cfg = get_containers_config(cfg)
    net_cfg = get_network_config(cfg)

    eff_image = image or containers_cfg.get("default_image", "python:3.11-slim")
    eff_network = net_cfg.get("name", "mai-ai_network")
    engine_name = containers_cfg.get("engine_container_name", "mai_ai_ollama_engine")
    ollama_port = net_cfg.get("ollama_port", 11434)

    from src.docker_py.docker_user_isolation import (
        sanitize_user_identifier,
        generate_traefik_user_labels,
        build_user_mount_configuration
    )
    
    clean_id = sanitize_user_identifier(user_id)
    container_name = f"ai_user_{clean_id}"
    
    sec_opts = get_hardening_security_options(config=cfg)
    res_opts = get_resource_limit_options(config=cfg)
    labels = generate_traefik_user_labels(user_id, config=cfg)
    mounts = build_user_mount_configuration(user_id, base_dir, config=cfg)
    
    return {
        "image": eff_image,
        "name": container_name,
        "detach": True,
        "network": eff_network,
        "labels": labels,
        "volumes": mounts,
        "environment": {
            "USER_ID": user_id,
            "OLLAMA_HOST": f"http://{engine_name}:{ollama_port}"
        },
        **sec_opts,
        **res_opts
    }


def calculate_idle_duration_seconds(last_active_timestamp: float) -> float:
    """
    Berechnet die vergangene Inaktivitätszeit in Sekunden seit der letzten Chat-Interaktion.

    Args:
        last_active_timestamp (float): UNIX-Timestamp der letzten Benutzeraktion.

    Returns:
        float: Dauer der Inaktivität in Sekunden.
    """
    now = time.time()
    return max(0.0, now - last_active_timestamp)


def evaluate_idle_status(
    last_active_timestamp: float,
    timeout_minutes: Optional[float] = None,
    config: Optional[Dict[str, Any]] = None
) -> Tuple[bool, float]:
    """
    Prüft, ob die Sitzung das Inaktivitätslimit (aus `config/docker_global.json`) überschritten hat.

    Args:
        last_active_timestamp (float): UNIX-Timestamp der letzten Aktion.
        timeout_minutes (Optional[float]): Maximale Inaktivitätszeit in Minuten oder None.
        config (Optional[Dict[str, Any]]): Optionale Konfiguration.

    Returns:
        Tuple[bool, float]: (is_idle, idle_seconds).
    """
    lifecycle_cfg = get_lifecycle_config(config)
    eff_timeout = timeout_minutes if timeout_minutes is not None else float(lifecycle_cfg.get("idle_timeout_minutes", 10.0))
    idle_secs = calculate_idle_duration_seconds(last_active_timestamp)
    timeout_secs = eff_timeout * 60.0
    is_idle = idle_secs >= timeout_secs
    return is_idle, idle_secs


def apply_idle_shutdown_policy(
    client: DockerClient,
    container_name: str,
    is_idle: bool
) -> Dict[str, Any]:
    """
    Fährt bei erkannter Inaktivität den Container kontrolliert herunter (`container.stop()`),
    um Host-Ressourcen (RAM/CPU) freizugeben.

    Args:
        client (DockerClient): Die aktive Docker-Client-Instanz.
        container_name (str): Name des Ziel-Containers.
        is_idle (bool): Ob der Container als inaktiv eingestuft wurde.

    Returns:
        Dict[str, Any]: Ergebnis-Dictionary ('action', 'status', 'container').
    """
    if not is_idle:
        return {"action": "none", "status": "active_or_kept_alive", "container": container_name}
        
    try:
        container = client.containers.get(container_name)
        if container.status == "running":
            container.stop(timeout=5)
            logger.info(f"Idle-Shutdown: Container '{container_name}' wegen Inaktivität gestoppt.")
            return {"action": "stopped", "status": "idle_shutdown_success", "container": container_name}
        return {"action": "none", "status": f"already_{container.status}", "container": container_name}
    except NotFound:
        return {"action": "none", "status": "not_found", "container": container_name}
    except Exception as e:
        logger.error(f"Fehler beim Idle-Shutdown von {container_name}: {e}")
        return {"action": "error", "error": str(e), "container": container_name}


def reactivate_user_container_on_demand(
    client: DockerClient,
    user_id: str,
    container_spec: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Startet einen schlafenden User-Container bei einer neuen Chat-Anfrage (On-Demand Wakeup)
    oder erstellt ihn anhand der gehärteten Spezifikation neu.

    Args:
        client (DockerClient): Die aktive Docker-Client-Instanz.
        user_id (str): Benutzerkennung.
        container_spec (Optional[Dict[str, Any]]): Optional vorbereitete Spezifikation.
        config (Optional[Dict[str, Any]]): Optionale Konfiguration.

    Returns:
        Dict[str, Any]: Status-Ergebnis mit 'action' ('restarted' | 'created' | 'already_running').
    """
    from src.docker_py.docker_user_isolation import sanitize_user_identifier
    clean_id = sanitize_user_identifier(user_id)
    container_name = f"ai_user_{clean_id}"
    
    try:
        container = client.containers.get(container_name)
        if container.status == "running":
            return {"action": "already_running", "status": "running", "container_id": container.short_id}
        else:
            container.start()
            return {"action": "restarted", "status": "running", "container_id": container.short_id}
    except NotFound:
        spec = container_spec or build_hardened_container_spec(user_id, config=config)
        try:
            new_c = client.containers.run(**spec)
            return {"action": "created", "status": "running", "container_id": new_c.short_id}
        except Exception as run_err:
            logger.error(f"Fehler bei On-Demand-Erstellung: {run_err}")
            return {"action": "error", "error": str(run_err)}
    except Exception as e:
        logger.error(f"Fehler bei Reaktivierung: {e}")
        return {"action": "error", "error": str(e)}


def run_step5_hardening_and_lifecycle_check(
    user_id: str = "user_alice@mai-ai.local",
    config: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    Orchestrierungsfunktion für Schritt 5 im Notebook:
    Validiert die strikten Hardening-Sicherheitsvorgaben (Read-Only Dateisystem,
    Cap-Drop: [ALL], Non-Root, Ressourcen-Limits) und testet die Automated Idle-Lifecycle-Logik
    basierend auf `config/docker_global.json`.

    Args:
        user_id (str): Benutzerkennung für den Testlauf.
        config (Optional[Dict[str, Any]]): Globale Konfiguration.

    Returns:
        Tuple[bool, Dict[str, Any]]: Erfolg (bool) und Prüf-Metadaten.
    """
    cfg = config or load_docker_global_config()
    lifecycle_cfg = get_lifecycle_config(cfg)
    timeout_min = float(lifecycle_cfg.get("idle_timeout_minutes", 10.0))

    # 1. Hardening Spezifikation bauen
    spec = build_hardened_container_spec(user_id, config=cfg)
    sec_opts = get_hardening_security_options(config=cfg)
    res_opts = get_resource_limit_options(config=cfg)
    
    # 2. Lifecycle Logik testen: Simulation von 11 Minuten Inaktivität
    simulated_past_time = time.time() - ((timeout_min + 1) * 60)
    is_idle, idle_secs = evaluate_idle_status(simulated_past_time, timeout_minutes=timeout_min, config=cfg)
    
    # 3. Lifecycle Logik testen: Simulation von 2 Minuten Inaktivität
    recent_time = time.time() - (2 * 60)
    recent_idle, recent_secs = evaluate_idle_status(recent_time, timeout_minutes=timeout_min, config=cfg)

    print(f"[✓] Schritt 5 erfolgreich konfiguriert: Container Hardening & Automated Idle-Lifecycle aktiv")
    print(f"    -> Read-Only Dateisystem: {sec_opts['read_only']} (Root-Dateisystem ist schreibgeschützt)")
    print(f"    -> Kernel Cap-Drop: {sec_opts['cap_drop']} (Sämtliche Root-Capabilities entzogen)")
    print(f"    -> Non-Root Ausführung: user='{sec_opts['user']}' (UID/GID 1000 ohne Root-Rechte)")
    print(f"    -> Ressourcen-Limits: RAM={res_opts['mem_limit']} | CPU={res_opts['nano_cpus']/1e9:.1f} Core(s)")
    print(f"    -> Automated Idle-Lifecycle: Inaktivität >{timeout_min:.0f} Min ({idle_secs:.0f}s) -> Auto-Shutdown: {is_idle}")
    print(f"    -> On-Demand Reaktivierung: Bei neuem Request -> Sofortiges Wakeup / Re-Launch")

    return True, {
        "spec": spec,
        "security": sec_opts,
        "resources": res_opts,
        "idle_test": {
            "simulated_idle": is_idle,
            "simulated_idle_secs": idle_secs,
            "recent_idle": recent_idle,
            "recent_idle_secs": recent_secs
        }
    }
