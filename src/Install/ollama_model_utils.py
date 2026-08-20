"""
Modul: ollama_model_utils.py
Projekt: Mai_AI (Offline_AI)

Stellt Validierungs- und Bereinigungsfunktionen für Ollama-Modellnamen bereit.
Verhindert HTTP 400 ('invalid model name') bei der Modellregistrierung und beim Pull,
indem Großbuchstaben, unzulässige Sonderzeichen, Dateiendungen (.gguf, .bin etc.),
führende/nachfolgende Trennzeichen sowie ungültige Sequenzen eliminiert werden.
"""

import re
from typing import Optional

# Offizielles Namensschema von Ollama: [host[:port]/][namespace/]name[:tag]
# Für Modell-Segmente: Nur Kleinbuchstaben, Ziffern und einzelne Trennzeichen (., -, _)
OLLAMA_MODEL_PATTERN = re.compile(
    r"^(?:[a-z0-9]+(?:[._-][a-z0-9]+)*/)?([a-z0-9]+(?:[._-][a-z0-9]+)*)(?::([a-z0-9]+(?:[._-][a-z0-9]+)*))?$"
)

# Standard-Dateiendungen, die vor der Registrierung als Modellname entfernt werden müssen
MODEL_FILE_EXTENSIONS = (
    ".gguf", ".bin", ".safetensors", ".pt", ".onnx", ".ckpt", 
    ".tar.gz", ".tgz", ".zip", ".7z", ".zst"
)

# Transliteration für deutsche Umlaute und Sonderzeichen
UMLAUT_MAP = {
    "ä": "ae", "Ä": "ae",
    "ö": "oe", "Ö": "oe",
    "ü": "ue", "Ü": "ue",
    "ß": "ss"
}


def is_valid_ollama_model_name(name: str) -> bool:
    """
    Prüft, ob ein Modellname den strikten Konventionen von Ollama entspricht.

    Regeln:
    - Nur Kleinbuchstaben (a-z), Ziffern (0-9)
    - Trennzeichen (., -, _) dürfen nur zwischen alphanumerischen Zeichen stehen
    - Optional ein Tag getrennt durch einen Doppelpunkt ':' (z. B. 'model:tag')
    - Optional ein Namespace getrennt durch einen Schrägstrich '/' (z. B. 'namespace/model:tag')
    - Keine Großbuchstaben, keine Leerzeichen, keine sonstigen Sonderzeichen

    Args:
        name (str): Zu prüfender Modellname.

    Returns:
        bool: True, wenn der Name zu 100 % valide ist, andernfalls False.
    """
    if not name or not isinstance(name, str):
        return False
    
    clean = name.strip()
    if not clean:
        return False
        
    return bool(OLLAMA_MODEL_PATTERN.match(clean))


def sanitize_ollama_model_name(raw_name: str, default_fallback: str = "custom-model") -> str:
    """
    Bereinigt und normalisiert einen beliebigen Eingabestring (z. B. GGUF-Dateiname,
    Hugging Face Repo-ID oder Benutzereingabe) zu einem garantierten, validen Ollama-Modellnamen.

    Verhindert HTTP 400 Bad Request Fehler ('invalid model name').

    Ablauf:
    1. Whitespace & Dateiendungen (.gguf, .bin etc.) entfernen
    2. Umlaute transliterieren (ä->ae, ö->oe, ü->ue, ß->ss)
    3. Umwandlung in Kleinbuchstaben (lowercase)
    4. Trennung nach Namespace (/) und Tag (:)
    5. Alle nicht zugelassenen Zeichen durch Bindestrich '-' ersetzen
    6. Mehrfache aufeinanderfolgende Trennzeichen (z. B. '--', '..', '__') reduzieren
    7. Führende und nachfolgende Trennzeichen entfernen
    8. Validierung und finaler Fallback

    Args:
        raw_name (str): Der rohe Modellname, Dateiname oder Pfad.
        default_fallback (str): Fallback-Name, falls der String leer oder ungültig wird.

    Returns:
        str: Valider, standardkonformer Ollama-Modellname.
    """
    if not raw_name or not isinstance(raw_name, str):
        return default_fallback

    clean = raw_name.strip()

    # 1. Dateiendungen entfernen (case-insensitive)
    lower_clean = clean.lower()
    for ext in MODEL_FILE_EXTENSIONS:
        if lower_clean.endswith(ext):
            clean = clean[:-len(ext)]
            lower_clean = clean.lower()
            break

    # 2. Umlaute ersetzen
    for umlaut, repl in UMLAUT_MAP.items():
        clean = clean.replace(umlaut, repl)

    # 3. Kleinbuchstaben
    clean = clean.lower()

    # 4. Namespace und Tag separieren (falls vorhanden)
    namespace = ""
    tag = ""

    if "/" in clean:
        parts = clean.split("/", 1)
        namespace = parts[0]
        clean = parts[1]

    if ":" in clean:
        parts = clean.split(":", 1)
        clean = parts[0]
        tag = parts[1]

    def _clean_part(part_str: str) -> str:
        if not part_str:
            return ""
        # Ersetze alle unzulässigen Zeichen (Klammern, Leerzeichen, Symbole etc.) durch Bindestrich
        s = re.sub(r"[^a-z0-9._-]+", "-", part_str)
        # Reduziere Sequenzen von Trennzeichen auf einen einzelnen Bindestrich
        s = re.sub(r"[-._]{2,}", "-", s)
        # Entferne führende und abschließende Sonderzeichen
        s = s.strip("-._")
        return s

    cleaned_name = _clean_part(clean)
    cleaned_tag = _clean_part(tag) if tag else ""
    cleaned_ns = _clean_part(namespace) if namespace else ""

    if not cleaned_name:
        cleaned_name = default_fallback

    result_parts = []
    if cleaned_ns:
        result_parts.append(f"{cleaned_ns}/")
    result_parts.append(cleaned_name)
    if cleaned_tag:
        result_parts.append(f":{cleaned_tag}")

    result = "".join(result_parts)

    # Finale Validierungsprüfung gegen Ollama-RegEx
    if not is_valid_ollama_model_name(result):
        # Letzte Sicherheitsstufe: Alphanumerisch mit Bindestrichen
        safe_fallback = re.sub(r"[^a-z0-9]", "-", cleaned_name).strip("-") or default_fallback
        return safe_fallback

    return result


def format_ollama_model_tag(filename_or_repo: str, custom_tag: Optional[str] = None) -> str:
    """
    Hilfsfunktion zur bequemen Generierung eines Ollama-Tags aus einem HuggingFace-Dateinamen
    oder Repository-Pfad.

    Beispiel:
        format_ollama_model_tag("Mistral-7B-Instruct-v0.2.Q4_K_M.gguf")
        -> "mistral-7b-instruct-v0.2-q4-k-m"
    """
    if custom_tag and custom_tag.strip():
        return sanitize_ollama_model_name(custom_tag)
    
    # Basename ermitteln, falls ein kompletter Pfad übergeben wurde
    clean_name = filename_or_repo.split("/")[-1].split("\\")[-1]
    return sanitize_ollama_model_name(clean_name)
