import docker
import os

class DockerOrchestrator:
    def __init__(self, base_path="/app/users"):
        self.client = docker.from_env()
        self.base_path = base_path
        os.makedirs(self.base_path, exist_ok=True)

    def prepare_user_environment(self, username):
        """Erstellt einen isolierten Arbeitsordner für den Benutzer."""
        user_dir = os.path.join(self.base_path, username)
        os.makedirs(os.path.join(user_dir, "workspace"), exist_ok=True)
        return user_dir

    def launch_user_instance(self, username, port):
        """Startet eine isolierte Instanz mit Ressourcen-Limitierung."""
        user_path = self.prepare_user_environment(username)
        
        container = self.client.containers.run(
            "mai_ai_image:latest",
            name=f"ai_user_{username}",
            detach=True,
            ports={'80/tcp': port},
            volumes={user_path: {'bind': '/app/user_data', 'mode': 'rw'}},
            mem_limit="512m",  # Ressourcen-Schutz für deinen Host
            nano_cpus=500000000, # Max 0.5 CPU-Kern
            environment={"USER_ID": username}
        )
        return container

    def stop_all_instances(self):
        """Sicherheits-Stopp aller laufenden Instanzen."""
        for container in self.client.containers.list(filters={"name": "ai_user_"}):
            container.stop()
            container.remove()