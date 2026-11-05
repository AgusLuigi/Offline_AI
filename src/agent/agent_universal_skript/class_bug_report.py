"""
Modul: class_bug_report
Bezeichnung: Datenklasse für identifizierte Code-Fehler
Inhaltlicher Schwerpunkt:
    Repräsentiert einen erkannten Fehler mit vollständigen Metadaten
    wie Typ, Schweregrad, Dateipfad, Zeilennummer, Beschreibung
    und Reparaturvorschlag. Wird vom Routing-Agenten erzeugt und
    an spezialisierte Agenten weitergegeben.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class class_bug_report:
    """
    Datenklasse für einen identifizierten Code-Fehler mit vollständigen Metadaten.
    Enthält Typ, Schweregrad, Speicherort und Reparaturvorschlag.
    """
    bug_id: str
    bug_type: str
    file_path: Path
    line_number: Optional[int] = None
    severity: str = "MEDIUM"
    description: str = ""
    suggested_fix: str = ""
    affected_agents: List[str] = field(default_factory=list)
    log_matches: List[str] = field(default_factory=list)
