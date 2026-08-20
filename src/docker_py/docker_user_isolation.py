"""
Modul: docker_user_isolation.py
Projekt: Mai_AI (MaiOmni)

Dieses Modul stellt feingranulare Funktionen für Schritt 3 (Dynamische Benutzer-Isolation & Storage-Quotas)
bereit. Es kapselt die Erstellung getrennter User-Spaces, überwacht Quotas und erzeugt Traefik-Header-Routing-Labels
dynamisch anhand der zentralen `config/docker_global.json`.
"""

import os
import sys
import re
import logging
from typing import Dict, Any, Optional, Tuple, List

from src.docker_py.docker_config import (
    load_docker_global_config,
    get_network_config,
    get_storage_config,
    find_project_root
)

logger = logging.getLogger("DockerUserIsolation")


def sanitize_user_identifier(user_id: str) -> str:
    """
    Bereinigt eine Benutzer-Kennung (z.B. E-Mail-Adresse oder Name) in einen sicheren,
    POSIX- und Docker-kompatiblen Bezeichner für Verzeichnisse und Containernamen.

    Args:
        user_id (str): Die Rohkennung des Benutzers (z.B. 'alice.dev@mai-ai.local').

    Returns:
        str: Bereinigter String (z.B. 'alice_dev_mai-ai_local').
    """
    if not user_id:
        return "anonymous_user"
    clean = re.sub(r'[^a-zA-Z0-9_\-]', '_', user_id.strip().lower())
    clean = re.sub(r'_+', '_', clean).strip('_')
    return clean or "user"


def get_user_base_directory(
    base_dir: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None
) -> str:
    """
    Liefert den zentralen Basispfad für alle Benutzer-Spaces (`data/users`),
    definiert in `config/docker_global.json`.

    Args:
        base_dir (Optional[str]): Optionaler benutzerdefinierter Basispfad.
        config (Optional[Dict[str, Any]]): Optionale Konfiguration.

    Returns:
        str: Absoluter Pfad zum Benutzerverzeichnis.
    """
    storage_cfg = get_storage_config(config)
    configured_rel = storage_cfg.get("base_users_dir", "data/users")

    if base_dir:
        abs_base = os.path.abspath(base_dir)
        if abs_base.endswith(os.path.normpath(configured_rel)) or os.path.basename(abs_base) == "users":
            target = abs_base
        elif os.path.basename(abs_base) == "data":
            target = os.path.join(abs_base, "users")
        else:
            target = os.path.join(abs_base, configured_rel)
    else:
        root = find_project_root()
        target = os.path.join(root, configured_rel)

    os.makedirs(target, exist_ok=True)
    return target


def create_isolated_user_workspace(
    user_id: str,
    base_dir: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, str]:
    """
    Erstellt ein streng isoliertes Verzeichnis-Layout für einen Benutzer:
    - `workspace/`: Arbeitsbereich für transiente Dateien
    - `history/`: Gespeicherte Chat-Verläufe
    - `inbox/`: SQLite-Inbox für Anfragen
    - `output/`: Generierte Artefakte

    Args:
        user_id (str): Die Benutzerkennung.
        base_dir (Optional[str]): Basispfad oder None.
        config (Optional[Dict[str, Any]]): Optionale Konfiguration.

    Returns:
        Dict[str, str]: Pfad-Dictionary aller angelegten Verzeichnisse.
    """
    clean_id = sanitize_user_identifier(user_id)
    user_root = os.path.join(get_user_base_directory(base_dir, config=config), clean_id)
    
    subdirs = {
        "user_root": user_root,
        "workspace": os.path.join(user_root, "workspace"),
        "history": os.path.join(user_root, "history"),
        "inbox": os.path.join(user_root, "inbox"),
        "output": os.path.join(user_root, "output")
    }
    
    for key, path in subdirs.items():
        os.makedirs(path, exist_ok=True)
        
    return subdirs


def calculate_directory_size_mb(path: str) -> float:
    """
    Berechnet die Gesamtgröße aller Dateien in einem Verzeichnis in Megabyte.

    Args:
        path (str): Das zu scannende Verzeichnis.

    Returns:
        float: Größe in MB.
    """
    total_bytes = 0
    if not os.path.exists(path):
        return 0.0
    for root, _, files in os.walk(path):
        for f in files:
            fp = os.path.join(root, f)
            try:
                if not os.path.islink(fp):
                    total_bytes += os.path.getsize(fp)
            except OSError:
                continue
    return round(total_bytes / (1024 * 1024), 3)


def check_user_storage_quota(
    user_id: str,
    max_quota_mb: Optional[float] = None,
    base_dir: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Überprüft die Einhaltung des Speicherplatzlimits (Quotas) für den User-Space.
    Standard-Limit wird aus `config/docker_global.json` geladen.

    Args:
        user_id (str): Benutzerkennung.
        max_quota_mb (Optional[float]): Maximal zulässiger Speicher in MB oder None.
        base_dir (Optional[str]): Basispfad.
        config (Optional[Dict[str, Any]]): Optionale Konfiguration.

    Returns:
        Dict[str, Any]: Quota-Status mit 'user_id', 'used_mb', 'quota_mb', 'within_limit'.
    """
    storage_cfg = get_storage_config(config)
    eff_quota = max_quota_mb if max_quota_mb is not None else float(storage_cfg.get("user_quota_max_mb", 500.0))

    clean_id = sanitize_user_identifier(user_id)
    user_root = os.path.join(get_user_base_directory(base_dir, config=config), clean_id)
    used_mb = calculate_directory_size_mb(user_root)
    within_limit = used_mb <= eff_quota
    
    return {
        "user_id": user_id,
        "clean_id": clean_id,
        "path": user_root,
        "used_mb": used_mb,
        "quota_mb": eff_quota,
        "usage_percent": round((used_mb / eff_quota) * 100, 2) if eff_quota > 0 else 0.0,
        "within_limit": within_limit
    }


def generate_traefik_user_labels(
    user_id: str,
    domain_name: Optional[str] = None,
    local_domain: Optional[str] = None,
    port: Optional[int] = None,
    priority: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, str]:
    """
    Generiert die Traefik-Routing-Labels zur dynamischen Benutzer-Isolation.
    Anfragen werden anhand des Google-OAuth2-Headers `X-Forwarded-User` auf den
    jeweiligen User-Container geroutet. Parameter werden aus `config/docker_global.json` bezogen.

    Args:
        user_id (str): Die authentifizierte E-Mail/User-ID.
        domain_name (Optional[str]): Externe Domain oder None.
        local_domain (Optional[str]): Lokale Domain oder None.
        port (Optional[int]): Interner Service-Port oder None.
        priority (Optional[str]): Router-Priorität oder None.
        config (Optional[Dict[str, Any]]): Optionale Konfiguration.

    Returns:
        Dict[str, str]: Dictionary mit Traefik-Label-Definitionen.
    """
    net_cfg = get_network_config(config)
    eff_domain = domain_name or net_cfg.get("domain_name", "mai-ai.duckdns.org")
    eff_local = local_domain or net_cfg.get("local_domain", "platform.local")
    eff_port = port if port is not None else int(net_cfg.get("service_port", 8000))
    eff_priority = priority or str(net_cfg.get("traefik_priority", "20"))

    clean_id = sanitize_user_identifier(user_id)
    router_name = f"user_{clean_id}"
    
    rule = (
        f"(Host(`{eff_local}`) || Host(`{eff_domain}`)) && "
        f"Header(`X-Forwarded-User`, `{user_id}`)"
    )
    
    return {
        "traefik.enable": "true",
        f"traefik.http.routers.{router_name}.rule": rule,
        f"traefik.http.routers.{router_name}.priority": str(eff_priority),
        f"traefik.http.routers.{router_name}.entrypoints": "web",
        f"traefik.http.services.{router_name}.loadbalancer.server.port": str(eff_port)
    }


def build_user_mount_configuration(
    user_id: str,
    base_dir: Optional[str] = None,
    project_root: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Dict[str, str]]:
    """
    Baut die strikte Dateisystem-Isolation für den Benutzer-Container auf:
    - User-Workspace: gemountet auf `/workspace` (rw)
    - System-Sicherheitsregeln: `/src/Security` gemountet auf `/app/security` (ro - Read-Only)

    Args:
        user_id (str): Die Benutzerkennung.
        base_dir (Optional[str]): Basispfad für User-Spaces.
        project_root (Optional[str]): Projekt-Root.
        config (Optional[Dict[str, Any]]): Optionale Konfiguration.

    Returns:
        Dict[str, Dict[str, str]]: Docker SDK konformes Mount-Dictionary.
    """
    paths = create_isolated_user_workspace(user_id, base_dir, config=config)
    root = project_root or find_project_root()
    security_src = os.path.join(root, "src", "Security")
    os.makedirs(security_src, exist_ok=True)
    
    return {
        paths["workspace"]: {"bind": "/workspace", "mode": "rw"},
        security_src: {"bind": "/app/security", "mode": "ro"}
    }


def run_step3_user_isolation(
    user_id: str = "user_alice@mai-ai.local",
    quota_mb: Optional[float] = None,
    base_dir: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    Orchestrierungsfunktion für Schritt 3 im Notebook:
    Erstellt die dynamische Benutzer-Isolation, prüft Speicher-Quotas und generiert
    die isolierten Traefik-Header-Routing-Labels basierend auf `config/docker_global.json`.

    Args:
        user_id (str): Test-Benutzerkennung.
        quota_mb (Optional[float]): Maximaler Speicherplatz in MB oder None für Config-Wert.
        base_dir (Optional[str]): Optionaler Basispfad.
        config (Optional[Dict[str, Any]]): Globale Konfiguration.

    Returns:
        Tuple[bool, Dict[str, Any]]: Erfolg (bool) und Status-Metadaten.
    """
    cfg = config or load_docker_global_config()

    # 1. User Workspace anlegen
    workspaces = create_isolated_user_workspace(user_id, base_dir, config=cfg)
    
    # 2. Quota Check
    quota_info = check_user_storage_quota(user_id, max_quota_mb=quota_mb, base_dir=base_dir, config=cfg)
    
    # 3. Traefik Routing Labels erstellen
    traefik_labels = generate_traefik_user_labels(user_id, config=cfg)
    
    # 4. Mount Mapping erstellen
    mounts = build_user_mount_configuration(user_id, base_dir, config=cfg)

    print(f"[✓] Schritt 3 erfolgreich konfiguriert: Dynamische Benutzer-Isolation eingerichtet")
    print(f"    -> User-Space Pfad: {workspaces['user_root']}")
    print(f"    -> Storage-Quota: {quota_info['used_mb']} MB / {quota_info['quota_mb']} MB ({quota_info['usage_percent']}% belegt - Status: {'OK' if quota_info['within_limit'] else 'ÜBER SCHWELLE'})")
    print(f"    -> Header-Routing: X-Forwarded-User == '{user_id}'")
    print(f"    -> Isolierte Mounts: /workspace (rw), /app/security (ro)")

    return True, {
        "workspaces": workspaces,
        "quota": quota_info,
        "traefik_labels": traefik_labels,
        "mounts": mounts
    }
