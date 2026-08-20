"""
Modul: docker_network_volumes.py
Projekt: Mai_AI (MaiOmni)

Dieses Modul stellt feingranulare Funktionen für Schritt 2 (Infrastruktur-Netzwerk & Datenschnittstellen)
bereit. Es verwaltet das geschlossene Bridge-Netzwerk, Named Volumes, prüft die `.env`-Konfiguration
und überwacht Basis-Container dynamisch anhand der `config/docker_global.json`.
"""

import os
import sys
import logging
from typing import Dict, Any, List, Optional, Tuple
import docker
from docker.client import DockerClient
from docker.errors import NotFound, DockerException

from src.docker_py.docker_config import (
    load_docker_global_config,
    get_network_config,
    get_storage_config,
    get_containers_config,
    get_env_variables_config,
    find_project_root
)
from src.docker_py.docker_connection import get_docker_client

logger = logging.getLogger("DockerNetworkVolumes")


def ensure_network_exists(
    client: DockerClient,
    network_name: Optional[str] = None,
    driver: Optional[str] = None,
    attachable: Optional[bool] = None,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Prüft, ob das angegebene Docker-Netzwerk existiert, und erstellt es andernfalls.
    Standardparameter werden dynamisch aus `config/docker_global.json` bezogen.

    Args:
        client (DockerClient): Die aktive Docker-Client-Instanz.
        network_name (Optional[str]): Der Name des Netzwerks oder None für Config-Wert.
        driver (Optional[str]): Der Netzwerk-Treiber oder None für Config-Wert.
        attachable (Optional[bool]): Flag für attachable oder None für Config-Wert.
        config (Optional[Dict[str, Any]]): Optionale Konfiguration.

    Returns:
        Dict[str, Any]: Status-Dictionary mit 'name', 'status' ('existing' | 'created' | 'error') und 'id'.
    """
    net_cfg = get_network_config(config)
    eff_name = network_name or net_cfg.get("name", "mai-ai_network")
    eff_driver = driver or net_cfg.get("driver", "bridge")
    eff_attachable = attachable if attachable is not None else net_cfg.get("attachable", True)

    try:
        networks = client.networks.list(names=[eff_name])
        for net in networks:
            if net.name == eff_name:
                return {"name": eff_name, "status": "existing", "id": net.short_id}
        
        created_net = client.networks.create(eff_name, driver=eff_driver, attachable=eff_attachable)
        return {"name": eff_name, "status": "created", "id": created_net.short_id}
    except Exception as e:
        logger.error(f"Fehler bei ensure_network_exists für {eff_name}: {e}")
        return {"name": eff_name, "status": "error", "error": str(e)}


def ensure_volume_exists(client: DockerClient, volume_name: str) -> Dict[str, Any]:
    """
    Prüft, ob ein bestimmtes Docker-Volume existiert, und erstellt es bei Bedarf.

    Args:
        client (DockerClient): Die aktive Docker-Client-Instanz.
        volume_name (str): Name des sicherzustellenden Volumes.

    Returns:
        Dict[str, Any]: Status-Dictionary mit 'name', 'status' ('existing' | 'created' | 'error').
    """
    try:
        client.volumes.get(volume_name)
        return {"name": volume_name, "status": "existing"}
    except NotFound:
        try:
            client.volumes.create(name=volume_name)
            return {"name": volume_name, "status": "created"}
        except Exception as create_err:
            logger.error(f"Volume-Erstellung für {volume_name} fehlgeschlagen: {create_err}")
            return {"name": volume_name, "status": "error", "error": str(create_err)}
    except Exception as e:
        logger.error(f"Fehler bei ensure_volume_exists für {volume_name}: {e}")
        return {"name": volume_name, "status": "error", "error": str(e)}


def ensure_infrastructure_volumes(
    client: DockerClient,
    volume_names: Optional[List[str]] = None,
    config: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Stellt sicher, dass alle für die Plattform benötigten Kern-Volumes vorhanden sind.
    Standardmäßig werden die Volumes aus `config/docker_global.json` bezogen.

    Args:
        client (DockerClient): Die aktive Docker-Client-Instanz.
        volume_names (Optional[List[str]]): Liste der Volume-Namen oder None für Config-Werte.
        config (Optional[Dict[str, Any]]): Optionale Konfiguration.

    Returns:
        List[Dict[str, Any]]: Liste von Status-Ergebnissen der einzelnen Volumes.
    """
    if volume_names is None:
        storage_cfg = get_storage_config(config)
        volume_names = storage_cfg.get("required_volumes", ["mai_ai_local_models", "mai_ai_db_data", "mai_ai_config"])

    results = []
    for vol_name in volume_names:
        res = ensure_volume_exists(client, vol_name)
        results.append(res)
    return results


def audit_env_configuration(
    env_path: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Überprüft die Existenz und Schlüsselparameter der `.env`-Datei für das Ingress- und Security-Gateway.
    Die Liste der Pflichtvariablen wird dynamisch aus `config/docker_global.json` geladen.

    Args:
        env_path (Optional[str]): Pfad zur `.env`-Datei oder None für automatische Suche.
        config (Optional[Dict[str, Any]]): Optionale Konfiguration.

    Returns:
        Dict[str, Any]: Audit-Ergebnis mit 'exists', 'keys_found', 'keys_missing' und 'is_ready'.
    """
    env_cfg = get_env_variables_config(config)
    required_keys = env_cfg.get("required_keys", [
        "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "COOKIE_SECRET", "DOMAIN_NAME"
    ])

    if env_path is None:
        root = find_project_root()
        env_file_rel = env_cfg.get("env_file_path", ".env")
        env_path = os.path.join(root, env_file_rel)

    audit_result = {
        "env_path": env_path,
        "exists": os.path.exists(env_path),
        "keys_found": [],
        "keys_missing": [],
        "is_ready": False
    }

    if not audit_result["exists"]:
        audit_result["keys_missing"] = required_keys
        return audit_result

    try:
        with open(env_path, "r", encoding="utf-8") as f:
            content = f.read()

        for k in required_keys:
            if f"{k}=" in content and not f"{k}=your_" in content and not f"{k}=\"\"" in content:
                audit_result["keys_found"].append(k)
            else:
                audit_result["keys_missing"].append(k)

        audit_result["is_ready"] = (len(audit_result["keys_missing"]) == 0)
    except Exception as e:
        logger.error(f"Fehler beim Lesen der .env-Datei: {e}")
        audit_result["error"] = str(e)

    return audit_result


def verify_compose_stack_files(project_root: Optional[str] = None) -> bool:
    """
    Prüft, ob die docker-compose.yml im Projektverzeichnis vorhanden ist.

    Args:
        project_root (Optional[str]): Pfad zum Projektroot oder None.

    Returns:
        bool: True, wenn docker-compose.yml existiert.
    """
    root = project_root or find_project_root()
    compose_path = os.path.join(root, "docker-compose.yml")
    return os.path.exists(compose_path)


def check_container_status(client: DockerClient, container_name: str) -> Dict[str, Any]:
    """
    Ermittelt den aktuellen Zustand eines Containers (laufend, pausiert, gestoppt oder nicht vorhanden).

    Args:
        client (DockerClient): Die aktive Docker-Client-Instanz.
        container_name (str): Name des zu prüfenden Containers.

    Returns:
        Dict[str, Any]: Status-Information mit 'name', 'status' und 'short_id'.
    """
    try:
        c = client.containers.get(container_name)
        return {"name": container_name, "status": c.status, "short_id": c.short_id}
    except NotFound:
        return {"name": container_name, "status": "not_found", "short_id": None}
    except Exception as e:
        return {"name": container_name, "status": "error", "error": str(e)}


def run_step2_infrastructure_setup(
    client: Optional[DockerClient] = None,
    env_path: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    Orchestrierungsfunktion für Schritt 2 im Notebook:
    Erstellt das Netzwerk, initialisiert Core-Volumes, validiert Umgebungsvariablen
    und liefert konsistentes Feedback basierend auf `config/docker_global.json`.

    Args:
        client (Optional[DockerClient]): Docker-Client oder None.
        env_path (Optional[str]): Pfad zur `.env` oder None.
        config (Optional[Dict[str, Any]]): Globale Konfiguration.

    Returns:
        Tuple[bool, Dict[str, Any]]: Erfolg (bool) und Result-Dictionary.
    """
    cfg = config or load_docker_global_config()
    net_cfg = get_network_config(cfg)
    storage_cfg = get_storage_config(cfg)
    containers_cfg = get_containers_config(cfg)

    if client is None:
        try:
            client = get_docker_client()
        except Exception as e:
            print(f"[X] Schritt 2 fehlgeschlagen: Keine Verbindung zu Docker: {e}")
            return False, {"error": str(e)}

    # 1. Netzwerk sicherstellen
    net_res = ensure_network_exists(client, network_name=net_cfg.get("name"), config=cfg)

    # 2. Volumes sicherstellen
    vol_res = ensure_infrastructure_volumes(client, volume_names=storage_cfg.get("required_volumes"), config=cfg)

    # 3. .env Audit
    env_audit = audit_env_configuration(env_path, config=cfg)

    # 4. Engine-Container-Status prüfen
    engine_name = containers_cfg.get("engine_container_name", "mai_ai_ollama_engine")
    engine_status = check_container_status(client, engine_name)

    print(f"[✓] Schritt 2 erfolgreich konfiguriert: Infrastruktur-Netzwerk & Datenschnittstellen aktiv")
    print(f"    -> Brücken-Netzwerk: '{net_res['name']}' ({net_res['status']})")
    for v in vol_res:
        print(f"    -> Datenschnittstelle: '{v['name']}' ({v['status']})")
    
    if env_audit["exists"]:
        print(f"    -> Gateway-Konfiguration (.env): lokalisiert (Keys aktiv: {len(env_audit['keys_found'])})")
    else:
        print(f"    -> Hinweis Gateway-Konfiguration: '.env' noch nicht angelegt (wird bei Start_AI.py initialisiert)")

    print(f"    -> KI-Engine Container Status: '{engine_status['name']}' -> {engine_status['status']}")

    return True, {
        "network": net_res,
        "volumes": vol_res,
        "env_audit": env_audit,
        "engine_status": engine_status
    }
