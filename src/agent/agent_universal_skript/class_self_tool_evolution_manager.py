"""
Modul: class_self_tool_evolution_manager.py
Projekt: Offline_AI

Verwaltet den autonomen Selbst-Werkzeug-Evolutionszyklus und den dynamischen RAM-Bootstrap:
1. Introspektion & Bestandserfassung (Prüfung der bestehenden library_registry & Anti-Code-Shrinking)
2. Sandbox-Verifikation & Real-Testing via SubAgentVerifier
3. Additive Persistierung in die SQLite-Tabelle 'library_registry' (strikt non-destruktiv)
4. Dynamischer RAM-Bootstrap (Runtime Capability Injection via exec() in den Arbeitsspeicher)
"""

import ast
import datetime
import importlib.util
import os
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


class class_self_tool_evolution_manager:
    """
    Manager für die autonome Erstellung, Verifikation, Speicherung und
    Arbeitsspeicher-Injektion von Werkzeugen und Fähigkeiten.
    """

    _cfg = globals().setdefault("_AGENT_CONFIG", {})
    TARGET_TABLE: str = _cfg.setdefault("EVOLUTION_TARGET_TABLE", "library_registry")
    MAX_CAPABILITY_CODE_LEN: int = _cfg.setdefault("MAX_CAPABILITY_CODE_LEN", 10000)
    SANDBOX_TIMEOUT_SEC: int = _cfg.setdefault("SANDBOX_TIMEOUT_SEC", 15)
    NODE_ID_PREFIX: str = _cfg.setdefault("NODE_ID_PREFIX", "CAP")

    def __init__(self, db_path: str = None):
        """Initialisiert den Tool-Evolutions-Manager mit Zugriff auf die Knowledge-DB."""
        print("[class_self_tool_evolution_manager] Starte Arbeit: __init__ wird jetzt ausgeführt.")
        self.ram_capabilities: Dict[str, Any] = {}

        # Datenbankpfad ermitteln
        if db_path and Path(db_path).exists() and Path(db_path).stat().st_size > 0:
            self.db_path = str(Path(db_path).resolve())
        else:
            core_infra = globals().get("class_tool_core_infrastructure")
            if core_infra and hasattr(core_infra, "get_database_path"):
                self.db_path = str(core_infra.get_database_path())
            else:
                self.db_path = str(Path(__file__).resolve().parent.parent.parent / "knowledge" / "agent_hierarchical_routing_tree_sql.db")

        if not self.db_path or not Path(self.db_path).exists():
            print(f"[class_self_tool_evolution_manager] FEHLER: __init__ hat die Aufgabe nicht erfüllt. Grund: Ungültiger Datenbankpfad '{self.db_path}'.")
            return

        print(f"[class_self_tool_evolution_manager] Erfolg: __init__ erfolgreich beendet. (DB: {self.db_path})")

    # -------------------------------------------------------------------------
    # HILFSMETHODEN ZUR DATENBANKVERBINDUNG
    # -------------------------------------------------------------------------

    def get_db_connection(self):
        """Erstellt eine fehlertolerante SQLite-Verbindung zur Knowledge-Datenbank."""
        print("[class_self_tool_evolution_manager] Starte Arbeit: get_db_connection wird jetzt ausgeführt.")
        try:
            conn = sqlite3.connect(self.db_path, timeout=10.0)
            conn.row_factory = sqlite3.Row
            print(f"[class_self_tool_evolution_manager] Erfolg: get_db_connection erfolgreich beendet. (DB: {self.db_path})")
            return conn
        except Exception as e:
            print(f"[class_self_tool_evolution_manager] FEHLER: get_db_connection hat die Aufgabe nicht erfüllt. Grund: {e}")
            raise

    # -------------------------------------------------------------------------
    # SCHRITT 1: INTROSPEKTION & BESTANDSERFASSUNG (READ EXISTING LIBRARY)
    # -------------------------------------------------------------------------

    def introspect_existing_library(self) -> dict:
        """
        Analysiert die bestehende SQLite-Wissensdatenbank (library_registry).
        Erfasst alle aktiven Fähigkeiten, Funktionen und Signaturen (Anti-Code-Shrinking).
        """
        print("[class_self_tool_evolution_manager] Starte Arbeit: introspect_existing_library wird jetzt ausgeführt.")
        inventory = {
            "total_count": 0,
            "tools": {},
            "functions": set(),
            "classes": set(),
            "nodes": []
        }

        try:
            with self.get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (self.TARGET_TABLE,))
                if not cur.fetchone():
                    print(f"[class_self_tool_evolution_manager] FEHLER: introspect_existing_library hat die Aufgabe nicht erfüllt. Grund: Tabelle '{self.TARGET_TABLE}' fehlt.")
                    return inventory

                cur.execute(f"""
                    SELECT node_id, is_active, topic_title, topic_specification, agent_instruction, example_code_snippet
                    FROM {self.TARGET_TABLE}
                    WHERE is_active = 1
                    ORDER BY node_id ASC
                """)
                rows = cur.fetchall()

                for row in rows:
                    node_id = row["node_id"]
                    title = row["topic_title"] or ""
                    snippet = row["example_code_snippet"] or ""

                    entry = {
                        "node_id": node_id,
                        "title": title,
                        "specification": row["topic_specification"] or "",
                        "instruction": row["agent_instruction"] or "",
                        "has_code": bool(snippet.strip()),
                        "extracted_functions": [],
                        "extracted_classes": []
                    }

                    # Code analysieren und Funktionen/Klassen extrahieren
                    if snippet.strip():
                        try:
                            tree = ast.parse(snippet)
                            for node in ast.walk(tree):
                                if isinstance(node, ast.FunctionDef):
                                    entry["extracted_functions"].append(node.name)
                                    inventory["functions"].add(node.name)
                                elif isinstance(node, ast.ClassDef):
                                    entry["extracted_classes"].append(node.name)
                                    inventory["classes"].add(node.name)
                        except Exception:
                            pass

                    inventory["nodes"].append(entry)
                    inventory["tools"][node_id] = entry

                inventory["total_count"] = len(inventory["nodes"])

        except Exception as e:
            print(f"[class_self_tool_evolution_manager] FEHLER: introspect_existing_library hat die Aufgabe nicht erfüllt. Grund: {e}")
            return inventory

        print(f"[class_self_tool_evolution_manager] Erfolg: introspect_existing_library erfolgreich beendet. (Gefundene Tools: {inventory['total_count']}, Funktionen: {len(inventory['functions'])})")
        return inventory

    def check_capability_exists(self, candidate_name: str, candidate_code: str = "") -> bool:
        """
        Prüft, ob ein Tool oder eine Funktion bereits in der library_registry existiert.
        Verhindert Duplikate und schützt bestehende Fähigkeiten strikt (Anti-Code-Shrinking).
        """
        print(f"[class_self_tool_evolution_manager] Starte Arbeit: check_capability_exists wird jetzt ausgeführt. (Parameter: {candidate_name})")
        if not candidate_name:
            print("[class_self_tool_evolution_manager] FEHLER: check_capability_exists hat die Aufgabe nicht erfüllt. Grund: Leerer Kandidatenname.")
            return False

        inventory = self.introspect_existing_library()
        candidate_clean = candidate_name.strip().lower()

        # 1. Titel- und Bezeichner-Prüfung
        for node in inventory["nodes"]:
            if node["title"].strip().lower() == candidate_clean:
                print(f"[class_self_tool_evolution_manager] Schutz: Fähigkeit mit Titel '{candidate_name}' existiert bereits in Node '{node['node_id']}'.")
                print("[class_self_tool_evolution_manager] Erfolg: check_capability_exists erfolgreich beendet. (Ergebnis: True)")
                return True

        # 2. Prüfung extrahierter Funktionsnamen aus dem neuen Code
        if candidate_code:
            try:
                tree = ast.parse(candidate_code)
                new_funcs = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
                duplicates = new_funcs.intersection(inventory["functions"])
                if duplicates:
                    print(f"[class_self_tool_evolution_manager] Schutz: Funktionen {duplicates} existieren bereits in der Bibliothek.")
                    print("[class_self_tool_evolution_manager] Erfolg: check_capability_exists erfolgreich beendet. (Ergebnis: True)")
                    return True
            except Exception:
                pass

        print("[class_self_tool_evolution_manager] Erfolg: check_capability_exists erfolgreich beendet. (Ergebnis: False)")
        return False

    # -------------------------------------------------------------------------
    # SCHRITT 2: SANDBOX-VERIFIKATION & REAL-TESTING (SUBAGENTVERIFIER)
    # -------------------------------------------------------------------------

    def verify_tool_in_sandbox(self, tool_name: str, code_snippet: str, test_call: str = "") -> Tuple[bool, str]:
        """
        Testet das neue Code-Snippet vor der Persistierung in einer isolierten Sandbox.
        Verifiziert Returncode 0, syntaktische Gültigkeit und Laufzeitstabilität.
        """
        print(f"[class_self_tool_evolution_manager] Starte Arbeit: verify_tool_in_sandbox wird jetzt ausgeführt. (Parameter: {tool_name})")
        if not code_snippet or not isinstance(code_snippet, str) or not code_snippet.strip():
            print("[class_self_tool_evolution_manager] FEHLER: verify_tool_in_sandbox hat die Aufgabe nicht erfüllt. Grund: Leerer Code.")
            return False, "Leeres Code-Snippet"

        # 1. AST-Syntaxprüfung
        try:
            tree = ast.parse(code_snippet)
        except SyntaxError as se:
            print(f"[class_self_tool_evolution_manager] FEHLER: verify_tool_in_sandbox hat die Aufgabe nicht erfüllt. Grund: SyntaxError in Zeile {se.lineno}: {se.msg}")
            return False, f"Syntaxfehler: {se}"

        # 2. Prüfen, ob bekannte Logging-Muster vorhanden sind; wenn nicht, Code syntaktisch aufbereiten
        has_start_log = "Starte Arbeit" in code_snippet or "Start" in code_snippet
        has_success_log = "Erfolg" in code_snippet or "Success" in code_snippet or "return" in code_snippet

        # 3. Test-Skript für Sandbox vorbereiten (inklusive Testaufruf)
        executable_test_code = code_snippet + "\n"
        if test_call and test_call.strip():
            executable_test_code += f"\n# Automatischer Validierungsaufruf\n{test_call.strip()}\n"
        else:
            # Falls Funktionen definiert wurden: ersten auffindbaren Funktionsaufruf probehalber auslösen
            funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
            if funcs:
                first_fn = funcs[0]
                executable_test_code += f"\n# Automatischer Funktions-Check\nprint('TEST_VERIFY_CALL:', callable({first_fn}))\n"

        # 4. Sandbox-Ausführung über class_agent_sub_verifier
        sub_verifier = globals().get("class_agent_sub_verifier")
        if sub_verifier and hasattr(sub_verifier, "verify_code_in_sandbox"):
            is_valid, output = sub_verifier.verify_code_in_sandbox(
                executable_test_code,
                timeout_sec=self.SANDBOX_TIMEOUT_SEC
            )
        else:
            # Direkter Fallback-Sandbox-Subprozess
            core_infra = globals().get("class_tool_core_infrastructure")
            project_root = Path(core_infra.get_project_root()) if core_infra else Path.cwd()
            temp_dir = project_root / "temp"
            temp_dir.mkdir(parents=True, exist_ok=True)
            temp_file = temp_dir / f"test_sandbox_{datetime.datetime.now().strftime('%H%M%S_%f')}.py"

            try:
                temp_file.write_text(executable_test_code, encoding="utf-8")
                import subprocess
                res = subprocess.run(
                    [sys.executable, str(temp_file)],
                    capture_output=True, text=True,
                    timeout=self.SANDBOX_TIMEOUT_SEC, cwd=str(temp_dir)
                )
                is_valid = (res.returncode == 0)
                output = res.stdout.strip() if is_valid else (res.stderr.strip() or res.stdout.strip())
            except Exception as ex:
                is_valid = False
                output = str(ex)
            finally:
                if temp_file.exists():
                    try:
                        temp_file.unlink()
                    except Exception:
                        pass

        if not is_valid:
            print(f"[class_self_tool_evolution_manager] FEHLER: verify_tool_in_sandbox hat die Aufgabe nicht erfüllt. Grund: Sandbox meldet Fehler: {output}")
            return False, output

        print(f"[class_self_tool_evolution_manager] Erfolg: verify_tool_in_sandbox erfolgreich beendet. (Sandbox: Returncode 0)")
        return True, output

    # -------------------------------------------------------------------------
    # SCHRITT 3: ADDITIVE PERSISTIERUNG IN DIE SQL-REGISTRY
    # -------------------------------------------------------------------------

    def persist_new_tool(
        self,
        tool_name: str,
        code_snippet: str,
        description: str = "",
        target_table: str = None
    ) -> str:
        """
        Trägt ein erfolgreich getestetes Werkzeug additiv in die Tabelle 'library_registry' ein.
        Bestehende Datensätze werden niemals gelöscht oder überschrieben (strikt additiv).
        """
        print(f"[class_self_tool_evolution_manager] Starte Arbeit: persist_new_tool wird jetzt ausgeführt. (Parameter: {tool_name})")
        if not tool_name or not code_snippet:
            print("[class_self_tool_evolution_manager] FEHLER: persist_new_tool hat die Aufgabe nicht erfüllt. Grund: Ungültige Eingaben.")
            return ""

        table_name = target_table or self.TARGET_TABLE
        now = datetime.datetime.now()
        micro = now.strftime("%f")[:3]
        node_id = f"{self.NODE_ID_PREFIX}_{now.strftime('%Y%m%d_%H%M%S')}_{micro}"

        try:
            with self.get_db_connection() as conn:
                cur = conn.cursor()

                # Tabelle bei Bedarf absichern
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {table_name} (
                        node_id TEXT PRIMARY KEY,
                        is_active INTEGER DEFAULT 1,
                        error_fallback_count INTEGER DEFAULT 0,
                        year INTEGER, month INTEGER, day INTEGER, hour INTEGER, minute INTEGER, second INTEGER,
                        topic_title TEXT,
                        topic_specification TEXT,
                        agent_instruction TEXT,
                        example_code_snippet TEXT,
                        validation_rule TEXT,
                        execution_count INTEGER DEFAULT 0,
                        success_weight REAL DEFAULT 1.0,
                        target_table TEXT,
                        target_column_id TEXT,
                        target_node_id TEXT
                    )
                """)

                # Transaktionaler Insert/Replace
                cur.execute(f"""
                    INSERT OR REPLACE INTO {table_name} (
                        node_id, is_active, error_fallback_count,
                        year, month, day, hour, minute, second,
                        topic_title, topic_specification, agent_instruction,
                        example_code_snippet, validation_rule, execution_count,
                        success_weight, target_table, target_column_id, target_node_id
                    ) VALUES (?, 1, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'SANDBOX_VERIFIED_RETURNCODE_0', 1, 1.0, 'user_query', 'node_id', '000')
                """, (
                    node_id,
                    now.year, now.month, now.day, now.hour, now.minute, now.second,
                    tool_name,
                    description or f"Autonom erstelltes Werkzeug: {tool_name}",
                    f"EXECUTE_TOOL: {tool_name}",
                    code_snippet[:self.MAX_CAPABILITY_CODE_LEN]
                ))
                conn.commit()

        except Exception as e:
            print(f"[class_self_tool_evolution_manager] FEHLER: persist_new_tool hat die Aufgabe nicht erfüllt. Grund: {e}")
            return ""

        print(f"[class_self_tool_evolution_manager] Erfolg: persist_new_tool erfolgreich beendet. (Node-ID: {node_id})")
        return node_id

    # -------------------------------------------------------------------------
    # SCHRITT 4: DYNAMISCHER RAM-BOOTSTRAP (RUNTIME CAPABILITY INJECTION)
    # -------------------------------------------------------------------------

    def inject_capability_into_ram(self, code_snippet: str, target_agent: object = None) -> dict:
        """
        Kompiliert und führt ein Code-Snippet via exec() aus und injiziert die
        darin definierten Funktionen/Klassen direkt in den Arbeitsspeicher (RAM).
        Bindet diese unmittelbar als ausführbare Methoden an die Ziel-Instanz.
        """
        print("[class_self_tool_evolution_manager] Starte Arbeit: inject_capability_into_ram wird jetzt ausgeführt.")
        if not code_snippet or not isinstance(code_snippet, str) or not code_snippet.strip():
            print("[class_self_tool_evolution_manager] FEHLER: inject_capability_into_ram hat die Aufgabe nicht erfüllt. Grund: Leerer Code.")
            return {"status": "FAILED", "injected": []}

        # Ausführungsumgebung mit Standardbibliotheken vorbereiten
        exec_env = {
            "__builtins__": __builtins__,
            "datetime": datetime,
            "os": os,
            "sys": sys,
            "Path": Path,
            "sqlite3": sqlite3,
            "math": __import__("math"),
            "re": re
        }

        try:
            # 1. Dynamische Injektion in den RAM
            exec(code_snippet, exec_env)

            # 2. Extrahieren aller neu definierten Callables
            injected_symbols = []
            for name, val in exec_env.items():
                if name.startswith("__") or name in ("datetime", "os", "sys", "Path", "sqlite3", "math", "re"):
                    continue
                if callable(val):
                    self.ram_capabilities[name] = val
                    injected_symbols.append(name)

                    # An Zielagenten binden (z. B. Pipeline-Instanz)
                    if target_agent is not None:
                        try:
                            setattr(target_agent, name, val)
                        except Exception:
                            pass

                    # Im Aufrufer-Global registrieren
                    try:
                        sys.modules["__main__"].__dict__[name] = val
                    except Exception:
                        pass

            if not injected_symbols:
                print("[class_self_tool_evolution_manager] FEHLER: inject_capability_into_ram hat die Aufgabe nicht erfüllt. Grund: Keine ausführbaren Callables gefunden.")
                return {"status": "FAILED", "injected": []}

            result = {"status": "SUCCESS", "injected": injected_symbols}
            print(f"[class_self_tool_evolution_manager] Erfolg: inject_capability_into_ram erfolgreich beendet. (Injiziert: {injected_symbols})")
            return result

        except Exception as e:
            print(f"[class_self_tool_evolution_manager] FEHLER: inject_capability_into_ram hat die Aufgabe nicht erfüllt. Grund: Runtime-Injektionsfehler: {e}")
            return {"status": "FAILED", "error": str(e), "injected": []}

    def bootstrap_ram_capabilities(self, target_agent: object = None) -> dict:
        """
        Lädt während des Boot-Vorgangs alle aktiven Snippets aus 'library_registry'
        und injiziert sie in den RAM („neue Arme und Beine“).
        """
        print("[class_self_tool_evolution_manager] Starte Arbeit: bootstrap_ram_capabilities wird jetzt ausgeführt.")
        bootstrapped = []

        try:
            with self.get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (self.TARGET_TABLE,))
                if not cur.fetchone():
                    print(f"[class_self_tool_evolution_manager] FEHLER: bootstrap_ram_capabilities: Tabelle '{self.TARGET_TABLE}' fehlt.")
                    return {"status": "FAILED", "bootstrapped_count": 0, "functions": []}

                cur.execute(f"""
                    SELECT node_id, topic_title, example_code_snippet
                    FROM {self.TARGET_TABLE}
                    WHERE is_active = 1 AND example_code_snippet IS NOT NULL AND TRIM(example_code_snippet) != ''
                    ORDER BY node_id ASC
                """)
                rows = cur.fetchall()

                for row in rows:
                    snippet = row["example_code_snippet"]
                    if snippet and not snippet.startswith("# FX_") and ("def " in snippet or "class " in snippet):
                        inj_res = self.inject_capability_into_ram(snippet, target_agent=target_agent)
                        if inj_res.get("status") == "SUCCESS":
                            bootstrapped.extend(inj_res.get("injected", []))

            result = {
                "status": "SUCCESS",
                "bootstrapped_count": len(bootstrapped),
                "functions": bootstrapped
            }
            print(f"[class_self_tool_evolution_manager] Erfolg: bootstrap_ram_capabilities erfolgreich beendet. (Bootstrapped: {len(bootstrapped)} Funktionen)")
            return result

        except Exception as e:
            print(f"[class_self_tool_evolution_manager] FEHLER: bootstrap_ram_capabilities hat die Aufgabe nicht erfüllt. Grund: {e}")
            return {"status": "FAILED", "error": str(e), "bootstrapped_count": 0, "functions": []}

    # -------------------------------------------------------------------------
    # GANZHEITLICHER EVOLUTIONS-ZYKLUS: 1 -> 2 -> 3 -> 4
    # -------------------------------------------------------------------------

    def evolve_and_register_new_tool(
        self,
        tool_name: str,
        code_snippet: str,
        description: str = "",
        test_call: str = "",
        target_agent: object = None,
        allow_replace: bool = False
    ) -> dict:
        """
        Führt den vollständigen, verbindlichen 4-Stufen-Evolutionszyklus aus:
        1. Introspektion & Bestandserfassung (Prüfung gegen Duplikate / Anti-Shrinkage)
        2. Sandbox-Verifikation & Real-Testing via SubAgentVerifier
        3. Additive Persistierung in 'library_registry'
        4. Dynamischer RAM-Bootstrap (Sofortige Bereitstellung zur Laufzeit)
        """
        print(f"[class_self_tool_evolution_manager] Starte Arbeit: evolve_and_register_new_tool wird jetzt ausgeführt. (Tool: {tool_name})")

        # STUFE 1: Introspektion & Bestandserfassung
        if not allow_replace:
            already_exists = self.check_capability_exists(candidate_name=tool_name, candidate_code=code_snippet)
            if already_exists:
                print(f"[class_self_tool_evolution_manager] FEHLER: evolve_and_register_new_tool hat die Aufgabe nicht erfüllt. Grund: Tool '{tool_name}' existiert bereits. Überschreiben abgewiesen.")
                return {
                    "status": "REJECTED_DUPLICATE",
                    "message": f"Fähigkeit '{tool_name}' existiert bereits. Anti-Code-Shrinking aktiv."
                }

        # STUFE 2: Sandbox-Verifikation & Real-Testing
        verified, verify_output = self.verify_tool_in_sandbox(
            tool_name=tool_name,
            code_snippet=code_snippet,
            test_call=test_call
        )
        if not verified:
            print(f"[class_self_tool_evolution_manager] FEHLER: evolve_and_register_new_tool hat die Aufgabe nicht erfüllt. Grund: Sandbox-Test fehlgeschlagen.")
            return {
                "status": "FAILED_SANDBOX",
                "error": verify_output
            }

        # STUFE 3: Additive Persistierung in SQL-Registry
        node_id = self.persist_new_tool(
            tool_name=tool_name,
            code_snippet=code_snippet,
            description=description
        )
        if not node_id:
            print(f"[class_tool_sql_reader] FEHLER: evolve_and_register_new_tool: DB-Persistierung fehlgeschlagen.")
            return {
                "status": "FAILED_PERSISTENCE",
                "error": "Konnte nicht in library_registry gespeichert werden."
            }

        # STUFE 4: Dynamischer RAM-Bootstrap (Runtime Capability Injection)
        injection_result = self.inject_capability_into_ram(code_snippet=code_snippet, target_agent=target_agent)

        result = {
            "status": "SUCCESS",
            "node_id": node_id,
            "tool_name": tool_name,
            "injected_functions": injection_result.get("injected", []),
            "sandbox_output": verify_output
        }
        print(f"[class_self_tool_evolution_manager] Erfolg: evolve_and_register_new_tool erfolgreich beendet. (Fähigkeit aktiv im RAM verankert: {node_id})")
        return result

    # -------------------------------------------------------------------------
    # ZENTRALE VERBINDUNGS- UND AUSFÜHRUNGSFUNKTION
    # -------------------------------------------------------------------------

    def run_self_tool_evolution_manager(self, action: str = "bootstrap", **kwargs) -> Any:
        """
        Zentrale Ausführungsfunktion der Klasse gemäß Architektur-Leitlinie.
        Steuert Introspektion, Evolution und RAM-Bootstrap modular.
        """
        print(f"[class_self_tool_evolution_manager] Starte Arbeit: run_self_tool_evolution_manager wird jetzt ausgeführt. (Aktion: {action})")
        if action == "bootstrap":
            result = self.bootstrap_ram_capabilities(target_agent=kwargs.get("target_agent"))
        elif action == "introspect":
            result = self.introspect_existing_library()
        elif action == "evolve":
            result = self.evolve_and_register_new_tool(
                tool_name=kwargs.get("tool_name", "Autonomous_Tool"),
                code_snippet=kwargs.get("code_snippet", ""),
                description=kwargs.get("description", ""),
                test_call=kwargs.get("test_call", ""),
                target_agent=kwargs.get("target_agent")
            )
        elif action == "inject":
            result = self.inject_capability_into_ram(
                code_snippet=kwargs.get("code_snippet", ""),
                target_agent=kwargs.get("target_agent")
            )
        else:
            print(f"[class_self_tool_evolution_manager] FEHLER: run_self_tool_evolution_manager hat die Aufgabe nicht erfüllt. Grund: Unbekannte Aktion '{action}'.")
            return None

        if result is None:
            print(f"[class_self_tool_evolution_manager] FEHLER: run_self_tool_evolution_manager hat die Aufgabe nicht erfüllt. Grund: Ergebnis ist None.")
            return None

        print(f"[class_self_tool_evolution_manager] Erfolg: run_self_tool_evolution_manager erfolgreich beendet.")
        return result
