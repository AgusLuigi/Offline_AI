import datetime
import random
import sqlite3
import sys
import threading
from pathlib import Path

# 1. Hauptverzeichnis zum Python-Pfad hinzufügen
sys.path.append(str(Path(__file__).resolve().parent))

# 2. Auto-Bootstrap & globale Registrierung aller universellen Werkzeuge
from agent_universal_skript.auto_bootstrap_and_register_agent_tools import auto_bootstrap_and_register_agent_tools
auto_bootstrap_and_register_agent_tools()

# 3. Zentrale globale Aliase mit sicherer Fallback-Logik (Defaults) direkt nach Bootstrap
logger = globals().get('class_logger_audit_execution')
core_infra = globals().get('class_tool_core_infrastructure')
ollama_manager = globals().get('class_tool_ollama_service_manager')
spinner_tool = globals().get('class_tool_resource_aware_spinner')
sql_reader = globals().get('class_tool_sql_reader')
sub_verifier = globals().get('class_agent_sub_verifier')
evolve_loop = globals().get('class_container_evolve_loop_test')

# Initialisierung des zentralen Loggers
if logger:
    logger.initialize_logger()

# Importiere die konsolidierte Pipeline aus meta_coder_sql (Single Source of Truth)
from meta_coder_sql import (
    MetaCoderSQLPipeline,
    boot_latest_metacoder,
    query_meta_coder_sql,
    AGENT_NAME,
    REQUIRED_KERNEL_MODULES,
    PROMPT_MAX_LEN,
    TASK_DESCRIPTION_MAX_LEN
)

# Eindeutige Zuweisung & Bereitstellung der Klasse
MetaCodeBase = MetaCoderSQLPipeline

# Globale Registrierung im Namespace
globals()['MetaCodeBase'] = MetaCodeBase
globals()['MetaCoderSQLPipeline'] = MetaCoderSQLPipeline
globals()['boot_latest_metacoder'] = boot_latest_metacoder
globals()['query_meta_coder_sql'] = query_meta_coder_sql


if __name__ == "__main__":
    if logger:
        logger.info(f"--- Starte {AGENT_NAME} SQL Verklemmungs-Pipeline (v2+V1) ---")
    
    pipeline = boot_latest_metacoder(require_ollama=True)
    
    # Umgebung und Tabellen prüfen
    if not pipeline.verify_environment() and logger:
        logger.warning("Umgebung konnte nicht vollständig verifiziert werden. Fahre fort...")

    # Kernel-Modul-Check
    if core_infra:
        kernel_check = core_infra.scan_kernel_modules(REQUIRED_KERNEL_MODULES)
        if logger:
            logger.info(f"[KERNEL MODULE SCAN] Status: {kernel_check}")

    print(f" [INTELLIGENTER CHAT-MODUS] Verbunden mit SQLite-Langzeitgedächtnis")
    print(f" {AGENT_NAME} nutzt aktiv den Knowledge Agent Routing Tree.")
    print(" Befehle: '!positiv' / '!negativ' für Feedback | 'exit' zum Beenden")

    last_query_node_id = None
    while True:
        try:
            user_input = input("\nDu: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit"]:
                print("\nAgent: Bis zum nächsten Mal!")
                break

            # Feedback-Befehle behandeln
            if user_input.lower().startswith("!feedback") or user_input.lower() in ["!positiv", "!negativ"]:
                if not last_query_node_id:
                    print("--> [FEEDBACK] Bisher wurde noch keine Anfrage ausgeführt, die bewertet werden könnte.")
                    continue
                is_pos = "positiv" in user_input.lower()
                comment = user_input.split(" ", 1)[1] if " " in user_input else ("Positives Feedback" if is_pos else "Negatives Feedback")
                fb_res = pipeline.record_feedback(last_query_node_id, is_positive=is_pos, comment=comment)
                print(f"--> [FEEDBACK REGISTRIERT] Node '{last_query_node_id}' bewertet: {fb_res}")
                continue

            # Stufe 1: Kognitive Erfassung, Bereinigung & Token-Schärfung (index_chat_user_query)
            try:
                indexed_context = pipeline.index_chat_user_query(user_input)
                last_query_node_id = indexed_context.get("node_id")
                log_table = indexed_context.get("log_table_name")
                effective_input = indexed_context.get("sharpened_query") or user_input

                if indexed_context.get("cache_hit"):
                    cached_data = indexed_context.get("cached_check", {})
                    print(f"\n{AGENT_NAME} [Domain: SQL-Cache | DB aktiv | Node {last_query_node_id}]:")
                    print(cached_data.get("response"))
                    print("-" * 70)
                    continue
            except Exception as e:
                if logger:
                    logger.warning(f"[GEGENKONTROLLE FEHLER] index_chat_user_query fehlgeschlagen: {e}")
                last_query_node_id = None
                log_table = None
                effective_input = user_input

            # Stufe 2: LLM-Inferenz oder Pipeline mit automatischer Spinner-Koppelung (run_agent)
            if pipeline.client:
                domain = pipeline._detect_domain(effective_input)
                db_tips = pipeline._get_relevant_tips(effective_input)
                user_blueprint = pipeline.initialize_blueprint_system(effective_input)

                system_prompt = f"""
You are an autonomous AI Agent with an active SQLite Long-Term Memory (Knowledge Agent Routing Tree).
Current Detected Domain: {domain}
Blueprint Status: {user_blueprint['status']}

Retrieved Knowledge & Past Patterns from SQLite DB:
{db_tips}

Your Task: Answer the user's request in German, keeping any code or technical keywords strictly in English. 
Acknowledge and make use of the SQLite database context if relevant.
"""
                chat_messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": effective_input}
                ]

                # Zentraler Agenten-Aufruf via run_agent mit automatischem Spinner
                chat_res = ollama_manager.run_agent(
                    chat_messages,
                    agent_title=f"{AGENT_NAME}-Chat",
                    model=pipeline.model_name,
                    ollama_host=pipeline.ollama_host
                ) if ollama_manager else {"content": ""}

                answer = chat_res.get("content", "")

                # Cache versiegeln
                if last_query_node_id:
                    pipeline.seal_query_cache(last_query_node_id, answer)
                
                # Auto-Persistence
                if "verewige" in user_input.lower() or "speichere in sql" in user_input.lower():
                    pipeline.persist_new_capability(
                        capability_name="Autonomous_Capability",
                        code_snippet=answer[:PROMPT_MAX_LEN],
                        description=user_input
                    )
                    if logger:
                        logger.info("\n[SYSTEM-INFO] Die Fähigkeit wurde physisch in die SQLite-Tabelle 'library_registry' geschrieben!")

                elif "sql" in user_input.lower() or "fehler" in user_input.lower() or "code" in user_input.lower():
                    pipeline.log_save_query_run_to_db_timestamp(
                        task_description=effective_input,
                        error_msg=f"User interaction pattern in domain [{domain}]",
                        solution_code=answer[:TASK_DESCRIPTION_MAX_LEN],
                        run_id=indexed_context.get("time_stamp") if 'indexed_context' in locals() else None,
                        step_type="checkpoint",
                        log_table_name=log_table
                    )

                print(f"\n{AGENT_NAME} [Domain: {domain} | DB aktiv]:\n{answer}\n" + "-" * 70)
            else:
                result = pipeline.run_pipeline(effective_input)
                print(f"\n{AGENT_NAME} [Status: {result.get('status')}]:")
                print(result.get("message") or result.get("result") or result.get("error"))
                print("-" * 70)

        except KeyboardInterrupt:
            print("\n\nAgent: Sitzung durch Benutzer abgebrochen.")
            break
        except Exception as e:
            if logger:
                logger.error(f"[FEHLER IM AGENTEN-LOOP] Konnte Anfrage nicht verarbeiten: {e}")