import docker
import os
import logging
from src.Install.folder_index import FOLDER_STRUCTURE

class MultiUserManager:
    """Verwaltet die dynamische Bereitstellung von isolierten Benutzer-Umgebungen."""
    
    def __init__(self, network="ai_platform_network"):
        self.client = docker.from_env()
        self.network = network
        self.logger = logging.getLogger("MultiUserManager")

    def provision_user(self, user_id):
        """Erstellt einen isolierten Container für den User mit Traefik-Routing."""
        container_name = f"ai_user_{user_id.replace('@', '_').replace('.', '_')}"
        user_workspace = os.path.join(FOLDER_STRUCTURE["root"], "users", user_id, "workspace")
        os.makedirs(user_workspace, exist_ok=True)

        # Traefik Labels für dynamisches Routing basierend auf dem OAuth2 Header
        labels = {
            "traefik.enable": "true",
            "traefik.http.routers.{}.rule".format(container_name): 
                f"Host(`platform.local`) && Header(`X-Forwarded-User`, `{user_id}`)",
            "traefik.http.services.{}.loadbalancer.server.port".format(container_name): "8000"
        }

        try:
            container = self.client.containers.run(
                image="python:3.11-slim",
                name=container_name,
                detach=True,
                labels=labels,
                network=self.network,
                mem_limit="1g",
                nano_cpus=1000000000, # 1 CPU
                volumes={
                    user_workspace: {'bind': '/workspace', 'mode': 'rw'},
                    # Der FileGuard wird in den Container gemountet
                    os.path.join(FOLDER_STRUCTURE["src"], "Security"): {'bind': '/app/security', 'mode': 'ro'}
                },
                extra_hosts={'host.docker.internal': 'host-gateway'},
                environment={
                    "USER_ID": user_id,
                    "OLLAMA_HOST": "http://host.docker.internal:11434"
                }
            )
            return container
        except Exception as e:
            self.logger.error(f"Provisionierung fehlgeschlagen für {user_id}: {e}")
            return None
