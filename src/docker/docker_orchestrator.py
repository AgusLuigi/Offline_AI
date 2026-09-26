"""
Modul: docker_orchestrator.py
Projekt: Mai_AI (MaiOmni)

Orchestrierungs-Klasse für isolierte User-Instanzen mit dynamischen Ressourcen-Limits
und Dateisystem-Sandboxing aus `config/docker_global.json`.
"""

import os
import logging
from typing import Optional, List, Any, Dict
import docker
from docker.client import DockerClient

from src.docker_py.docker_config import (
    load_docker_global_config,
    get_storage_config,
    get_containers_config,
    get_network_config,
    get_resource_limits_config
)
from src.docker_py.docker_user_isolation import (
    sanitize_user_identifier,
    create_isolated_user_workspace,
    get_user_base_directory
)
from src.docker_py.docker_hardening_lifecycle import (
    get_hardening_security_options,
    get_resource_limit_options
)

logger = logging.getLogger("DockerOrchestrator")


class DockerOrchestrator:
    """Orchestrierer für isolierte Benutzer-Container."""
    
    def __init__(
        self,
        base_path: Optional[str] = None,
        client: Optional[DockerClient] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialisiert den DockerOrchestrator.

        Args:
            base_path (Optional[str]): Basispfad oder None für Config-Wert.
            client (Optional[DockerClient]): Optionale Docker-Client-Instanz.
            config (Optional[Dict[str, Any]]): Globale Konfiguration.
        """
        self.config = config or load_docker_global_config()
        self.client = client or docker.from_env()
        self.base_path = base_path or get_user_base_directory(config=self.config)
        os.makedirs(self.base_path, exist_ok=True)

    def prepare_user_environment(self, username: str) -> str:
        """
        Erstellt einen isolierten Arbeitsordner für den Benutzer.

        Args:
            username (str): Benutzerkennung.

        Returns:
            str: Absoluter Pfad zum Benutzerordner.
        """
        paths = create_isolated_user_workspace(username, self.base_path, config=self.config)
        return paths["user_root"]

    def launch_user_instance(
        self,
        username: str,
        port: Optional[int] = None,
        image: Optional[str] = None
    ) -> Optional[Any]:
        """
        Startet eine isolierte Instanz mit Ressourcen-Limitierung und Hardening aus der Konfiguration.

        Args:
            username (str): Benutzerkennung.
            port (Optional[int]): Host-Port oder None für Config-Wert.
            image (Optional[str]): Docker-Image oder None für Config-Wert.

        Returns:
            Optional[Container]: Die gestartete Container-Instanz.
        """
        net_cfg = get_network_config(self.config)
        containers_cfg = get_containers_config(self.config)
        res_cfg = get_resource_limits_config(self.config)

        eff_port = port if port is not None else int(net_cfg.get("host_port", 8080))
        eff_image = image or containers_cfg.get("mai_ai_image", "mai_ai_image:latest")
        clean_id = sanitize_user_identifier(username)
        user_dir = self.prepare_user_environment(username)
        workspace_dir = os.path.join(user_dir, "workspace")
        
        sec_opts = get_hardening_security_options(config=self.config)
        inst_mem = res_cfg.get("default_instance_mem", "512m")
        inst_cpu = float(res_cfg.get("default_instance_cpu", 0.5))
        res_opts = get_resource_limit_options(ram_limit=inst_mem, cpu_cores=inst_cpu, config=self.config)

        try:
            container = self.client.containers.run(
                eff_image,
                name=f"ai_user_{clean_id}",
                detach=True,
                ports={'80/tcp': eff_port},
                volumes={workspace_dir: {'bind': '/app/user_data', 'mode': 'rw'}},
                environment={"USER_ID": username},
                **sec_opts,
                **res_opts
            )
            return container
        except Exception as e:
            logger.error(f"Fehler beim Starten der User-Instanz für {username}: {e}")
            return None

    def stop_all_instances(self) -> int:
        """
        Sicherheits-Stopp aller laufenden User-Instanzen.

        Returns:
            int: Anzahl der gestoppten Container.
        """
        stopped = 0
        try:
            for container in self.client.containers.list(all=True, filters={"name": "ai_user_"}):
                try:
                    container.stop(timeout=2)
                    container.remove(force=True)
                    stopped += 1
                except Exception as e:
                    logger.warning(f"Konnte Container {container.name} nicht stoppen: {e}")
        except Exception as e:
            logger.error(f"Fehler bei stop_all_instances: {e}")
        return stopped