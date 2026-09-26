"""
Package: docker_py
Projekt: Mai_AI (MaiOmni)

Zentrales Paket für alle Docker-, Infrastruktur-, User-Isolations-,
Inbox-Messaging-, Hardening-, Config- und Lifecycle-Funktionalitäten.
"""

from src.docker_py.docker_config import (
    load_docker_global_config,
    save_docker_global_config,
    get_network_config,
    get_storage_config,
    get_containers_config,
    get_security_hardening_config,
    get_resource_limits_config,
    get_lifecycle_config,
    get_env_variables_config,
    get_sqlite_inbox_config,
    find_project_root,
    get_default_config_path
)

from src.docker_py.docker_connection import (
    get_docker_client,
    ping_docker_daemon,
    detect_os_platform,
    attempt_start_docker_service,
    verify_daemon_security_features,
    audit_docker_environment,
    run_step1_daemon_check
)

from src.docker_py.docker_network_volumes import (
    ensure_network_exists,
    ensure_volume_exists,
    ensure_infrastructure_volumes,
    audit_env_configuration,
    verify_compose_stack_files,
    check_container_status,
    run_step2_infrastructure_setup
)

from src.docker_py.docker_user_isolation import (
    sanitize_user_identifier,
    get_user_base_directory,
    create_isolated_user_workspace,
    calculate_directory_size_mb,
    check_user_storage_quota,
    generate_traefik_user_labels,
    build_user_mount_configuration,
    run_step3_user_isolation
)

from src.docker_py.docker_sqlite_inbox import (
    get_inbox_database_path,
    init_inbox_database,
    enqueue_user_request,
    fetch_pending_requests,
    store_chat_response,
    fetch_chat_history,
    run_step4_sqlite_inbox_test
)

from src.docker_py.docker_hardening_lifecycle import (
    get_hardening_security_options,
    get_resource_limit_options,
    build_hardened_container_spec,
    calculate_idle_duration_seconds,
    evaluate_idle_status,
    apply_idle_shutdown_policy,
    reactivate_user_container_on_demand,
    run_step5_hardening_and_lifecycle_check
)

from src.docker_py.docker_user_manager import MultiUserManager
from src.docker_py.docker_orchestrator import DockerOrchestrator

__all__ = [
    # Config-Manager (config/docker_global.json)
    "load_docker_global_config",
    "save_docker_global_config",
    "get_network_config",
    "get_storage_config",
    "get_containers_config",
    "get_security_hardening_config",
    "get_resource_limits_config",
    "get_lifecycle_config",
    "get_env_variables_config",
    "get_sqlite_inbox_config",
    "find_project_root",
    "get_default_config_path",

    # Schritt 1
    "get_docker_client",
    "ping_docker_daemon",
    "detect_os_platform",
    "attempt_start_docker_service",
    "verify_daemon_security_features",
    "audit_docker_environment",
    "run_step1_daemon_check",
    
    # Schritt 2
    "ensure_network_exists",
    "ensure_volume_exists",
    "ensure_infrastructure_volumes",
    "audit_env_configuration",
    "verify_compose_stack_files",
    "check_container_status",
    "run_step2_infrastructure_setup",
    
    # Schritt 3
    "sanitize_user_identifier",
    "get_user_base_directory",
    "create_isolated_user_workspace",
    "calculate_directory_size_mb",
    "check_user_storage_quota",
    "generate_traefik_user_labels",
    "build_user_mount_configuration",
    "run_step3_user_isolation",
    
    # Schritt 4
    "get_inbox_database_path",
    "init_inbox_database",
    "enqueue_user_request",
    "fetch_pending_requests",
    "store_chat_response",
    "fetch_chat_history",
    "run_step4_sqlite_inbox_test",
    
    # Schritt 5
    "get_hardening_security_options",
    "get_resource_limit_options",
    "build_hardened_container_spec",
    "calculate_idle_duration_seconds",
    "evaluate_idle_status",
    "apply_idle_shutdown_policy",
    "reactivate_user_container_on_demand",
    "run_step5_hardening_and_lifecycle_check",

    # Klassen
    "MultiUserManager",
    "DockerOrchestrator"
]
