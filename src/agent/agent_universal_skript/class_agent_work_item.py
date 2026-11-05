"""
Modul: class_agent_work_item
Bezeichnung: Datenklasse für Agenten-Aufträge
Inhaltlicher Schwerpunkt:
    Repräsentiert einen vollständig kontextualisierten Auftrag für
    einen spezialisierten Agenten. Enthält Agenten-Typ, Aufgabenbeschreibung,
    Dateiinhalt, verknüpften BugReport sowie Priorität und Ergebnis-Slot.
    Wird vom Routing-Agenten erstellt und sequenziell abgearbeitet.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Optional

# Lokales Import des BugReport (vermeidet zirkuläre Abhängigkeit)
# Der Bootstrap-Mechanismus lädt class_bug_report vorab in den globalen Namensraum
class_bug_report = globals().get("class_bug_report")


@dataclass
class class_agent_work_item:
    """
    Datenklasse für einen Agenten-Auftrag mit vollem Kontext.
    Enthält Agenten-Typ, Aufgabe, Datei-Inhalt, BugReport und Ergebnis-Slot.
    """
    agent_type: str
    agent_name: str
    task_description: str
    file_path: Optional[Path] = None
    code_content: str = ""
    bug_report: Optional[Any] = None   # class_bug_report-Instanz
    context_data: Dict[str, Any] = field(default_factory=dict)
    priority: int = 1
    result: Optional[Dict[str, Any]] = None
