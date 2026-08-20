"""
Modul: docker_user_manager.py
Projekt: Mai_AI (MaiOmni)

Verwaltet die dynamische Bereitstellung von isolierten Benutzer-Umgebungen
mit Traefik-Header-Routing und Container-Hardening anhand `config/docker_global.json`.
"""

import os
import logging
from typing import Optional, Dict, Any
import docker
from docker.client import DockerClient

from src.docker_py.docker_config import (
    load_docker_global_config,
    get_network_config,
    get_containers_config
)
from src.docker_py.docker_user_isolation import sanitize_user_identifier
from src.docker_py.docker_hardening_lifecycle import build_hardened_container_spec

logger = logging.getLogger("MultiUserManager")


class MultiUserManager:
    """Verwaltet die dynamische Bereitstellung von isolierten Benutzer-Umgebungen."""
    
    def __init__(
        self,
        network: Optional[str] = None,
        client: Optional[DockerClient] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialisiert den MultiUserManager.

        Args:
            network (Optional[str]): Docker-Netzwerkname oder None für Config-Wert.
            client (Optional[DockerClient]): Optionale Docker-Client-Instanz.
            config (Optional[Dict[str, Any]]): Globale Konfiguration.
        """
        self.config = config or load_docker_global_config()
        net_cfg = get_network_config(self.config)
        self.network = network or net_cfg.get("name", "mai-ai_network")
        self.client = client or docker.from_env()
        self.logger = logging.getLogger("MultiUserManager")

    def provision_user(self, user_id: str, image: Optional[str] = None) -> Optional[Any]:
        """
        Erstellt einen isolierten, gehärteten Container für den User mit Traefik-Routing.

        Args:
            user_id (str): Die authentifizierte Benutzer-ID.
            image (Optional[str]): Basis-Image oder None für Config-Wert.

        Returns:
            Optional[Container]: Die gestartete Container-Instanz oder None bei Fehler.
        """
        containers_cfg = get_containers_config(self.config)
        eff_image = image or containers_cfg.get("default_image", "python:3.11-slim")
        clean_id = sanitize_user_identifier(user_id)
        container_name = f"ai_user_{clean_id}"

        # 1. Bestehenden Container prüfen
        try:
            existing = self.client.containers.get(container_name)
            if existing.status == "running":
                self.logger.info(f"Container '{container_name}' läuft bereits.")
                return existing
            else:
                existing.start()
                return existing
        except docker.errors.NotFound:
            pass

        # 2. Gehärtete Spezifikation erstellen und starten
        spec = build_hardened_container_spec(user_id, image=eff_image, config=self.config)
        try:
            container = self.client.containers.run(**spec)
            self.logger.info(f"Container '{container_name}' erfolgreich provisioniert.")
            return container
        except Exception as e:
            self.logger.error(f"Provisionierung fehlgeschlagen für {user_id}: {e}")
            return None

    def terminate_user(self, user_id: str) -> bool:
        """
        Beendet und entfernt die isolierte Benutzer-Kapsel sicher.

        Args:
            user_id (str): Benutzerkennung.

        Returns:
            bool: True bei Erfolg, andernfalls False.
        """
        clean_id = sanitize_user_identifier(user_id)
        container_name = f"ai_user_{clean_id}"
        try:
            c = self.client.containers.get(container_name)
            c.stop(timeout=2)
            c.remove(force=True)
            return True
        except docker.errors.NotFound:
            return True
        except Exception as e:
            self.logger.error(f"Fehler beim Beenden von {container_name}: {e}")
            return False
