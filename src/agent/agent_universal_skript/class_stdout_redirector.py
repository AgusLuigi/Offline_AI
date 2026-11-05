"""
Modul: class_stdout_redirector
Bezeichnung: Standard-Output-Umleitung zum Audit-Logger
Inhaltlicher Schwerpunkt:
    Leitet alle Konsolenausgaben (sys.stdout) transparent in die
    Audit-Log-Datei um. Wird von class_logger_audit_execution
    automatisch als sys.stdout-Ersatz eingesetzt.
"""


class class_stdout_redirector:
    """
    Spiegelt Konsolenausgaben parallel in das Logfile.
    Wird als sys.stdout-Ersatz eingesetzt und delegiert
    Schreiboperationen an den zentralen Audit-Logger.
    """

    def __init__(self, original_stream):
        print("[class_stdout_redirector] Starte Arbeit: __init__ wird jetzt ausgeführt.")
        self.terminal = original_stream
        if not hasattr(self, "terminal") or self.terminal is None:
            print("[class_stdout_redirector] FEHLER: __init__ hat die Aufgabe nicht erfüllt. Grund: terminal-Attribut nicht gesetzt.")
            return
        print("[class_stdout_redirector] Erfolg: __init__ erfolgreich beendet.")

    def write(self, message: str) -> None:
        """Schreibt eine Ausgabe in den Original-Stream und protokolliert sie."""
        print("[class_stdout_redirector] Starte Arbeit: write wird jetzt ausgeführt.")
        self.terminal.write(message)
        self.terminal.flush()
        if message and message.strip():
            cleaned = message.strip()
            if not cleaned.startswith("[") and "Arbeitet..." not in cleaned:
                try:
                    import platform
                    pc_id = platform.node() or "LocalAgent"
                    logger_cls = globals().get("class_logger_audit_execution")
                    if logger_cls:
                        logger_cls.write_log(
                            pc_id=pc_id,
                            phase=logger_cls.LOG_PHASE_TERMINAL,
                            event=logger_cls.LOG_EVENT_STDOUT,
                            detail=cleaned
                        )
                except Exception:
                    pass
        print("[class_stdout_redirector] Erfolg: write erfolgreich beendet.")

    def flush(self) -> None:
        """Leert den Ausgabepuffer des Original-Streams."""
        print("[class_stdout_redirector] Starte Arbeit: flush wird jetzt ausgeführt.")
        self.terminal.flush()
        print("[class_stdout_redirector] Erfolg: flush erfolgreich beendet.")
