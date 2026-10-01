import json
from pathlib import Path

NB_PATH = Path(r"d:\Benutzern\Desktop\GITHUB\Offline_AI\notebooks\ollama_model_download_utility.ipynb")
nb = json.loads(NB_PATH.read_text(encoding="utf-8"))

c8_code = '''# GGUF Hybrid Utility & Cleanup Engine
# =============================================================================
# ZENTRALE GLOBALE GGUF-PFADE & ENGINE-KONFIGURATION
# =============================================================================
DEFAULT_GGUF_SEARCH_DIR: Path = Path(globals().get("GLOBAL_DOWNLOAD_DIR", globals().get("HF_MODELS_DIR", Path.cwd() / "data" / "models"))).resolve()
GGUF_SEARCH_DIR: Path = DEFAULT_GGUF_SEARCH_DIR
GLOBAL_GGUF_FILES: list[Path] = []
CURRENT_GGUF_SCAN_RESULTS: dict[str, Path] = {}

globals()["DEFAULT_GGUF_SEARCH_DIR"] = DEFAULT_GGUF_SEARCH_DIR
globals()["GGUF_SEARCH_DIR"] = GGUF_SEARCH_DIR
globals()["GLOBAL_GGUF_FILES"] = GLOBAL_GGUF_FILES
globals()["CURRENT_GGUF_SCAN_RESULTS"] = CURRENT_GGUF_SCAN_RESULTS

FULL_WIDTH = "100%"
MAX_WIDTH = "900px"

# 🖥️ IPYWIDGETS OBERFLÄCHE DEFINIEREN
output_log = widgets.Output(
    layout=widgets.Layout(
        width=FULL_WIDTH, max_width=MAX_WIDTH, height="180px",
        border="1px solid #CBD5E1", border_radius="6px", padding="8px",
        overflow="auto", background_color="#0F172A"
    )
)

path_input = widgets.Text(
    value=str(DEFAULT_GGUF_SEARCH_DIR),
    description="Modell-Pfad:",
    disabled=False,
    layout=widgets.Layout(width="55%")
)

btn_path_fallback = widgets.Button(
    description="Standard-Pfad",
    button_style="warning",
    icon="undo",
    tooltip="Setzt den Suchpfad auf das globale Standard-Verzeichnis zurück",
    layout=widgets.Layout(width="18%")
)

backend_dropdown = widgets.Dropdown(
    options=[
        ("Ollama (Standard mit Cleanup)", "ollama"),
        ("Direct Llama-CPP (Ohne Ollama)", "llama_cpp")
    ],
    value="ollama",
    description="Backend:",
    disabled=False,
    layout=widgets.Layout(width="70%")
)

start_button = widgets.Button(
    description="Sync, Test & Start",
    button_style="success",
    icon="play",
    layout=widgets.Layout(width="28%")
)

def on_path_fallback_clicked(b):
    default_dir = globals().get("GLOBAL_DOWNLOAD_DIR", globals().get("HF_MODELS_DIR", Path.cwd() / "data" / "models"))
    p_resolved = Path(default_dir).resolve()
    path_input.value = str(p_resolved)
    with output_log:
        print(f"[✓] Suchpfad zurückgesetzt auf: {p_resolved}")

btn_path_fallback.on_click(on_path_fallback_clicked)

# 🎯 Dashboard UI Container
dashboard_box = widgets.VBox([
    widgets.HTML("<h3>🎛️ GGUF Hybrid Utility & Cleanup Engine</h3>"),
    widgets.HBox([path_input, btn_path_fallback]),
    widgets.HBox([backend_dropdown, start_button]),
    widgets.HTML("<br><b>Echtzeit-Log:</b>"),
    output_log
], layout=widgets.Layout(padding="10px", max_width=MAX_WIDTH, margin="0 auto"))


# 🎨 DASHBOARD PRINT HELPER
def print_section(title: str, subtitle: str = ""):
    print(f" 📍 {title:<64}")
    if subtitle:
        print(f"{subtitle:<64}")

def print_log(level: str, message: str, detail: str = ""):
    badges = {
        "INFO": "ℹ️ [INFO]   ",
        "SUCCESS": "✓  [OK]     ",
        "WARN": "⚠️ [WARN]   ",
        "ERROR": "❌ [FAIL]   ",
        "CLEANUP": "🧹 [REMOVE] "
    }
    prefix = badges.get(level.upper(), f"   [{level}]")
    print(f" {prefix} {message}")
    if detail:
        print(f"Details: {detail.strip()}")

def print_summary(healthy: int, broken: int, total_files: int, registered: int, skipped: int, remaining_models: list):
    print(" 📊 ZUSAMMENFASSUNG & OLLAMA STATUS")
    print(f"  • Gefundene GGUF-Dateien auf Disk: {total_files:<28}")
    print(f"  • Neu registriert:                 {registered:<28}")
    print(f"  • Bereits vorhanden (Skipped):     {skipped:<28}")
    print(f"  • Funktionstüchtige Modelle:       {healthy:<28}")
    print(f"  • Gelöscht / Inkompatibel:         {broken:<28} ")
    print("AKTIVE OLLAMA-MODELLE:")
    for idx, item in enumerate(remaining_models, 1):
        size_mb = (item.size // (1024**2)) if item.size else 0
        model_str = f"{idx}. {item.model} ({size_mb} MB)"
        print(f"{model_str:<64}")


# ⚙️ HILFSFUNKTIONEN FÜR GGUF HEADER, REKURSIVE SUCHE & NAMEN
def is_valid_gguf_header(file_path: Path | str) -> bool:
    \"\"\"Prüft vor dem Ladeversuch, ob die Datei existiert und mit b'GGUF' beginnt.\"\"\"
    try:
        p = Path(file_path)
        if not p.is_file() or p.stat().st_size < 4:
            return False
        with open(p, "rb") as f:
            return f.read(4) == b"GGUF"
    except Exception:
        return False

def scan_gguf_files_recursive(search_dir: Path | str) -> list[Path]:
    \"\"\"
    Rekursive Suche nach .gguf-Dateien sowie latenten Blobs/GGUF-Dateien ohne Endung.
    Gibt eine de-duplizierte Liste absoluter Path-Objekte (Path.resolve()) zurück.
    \"\"\"
    results = []
    seen = set()
    root = Path(search_dir).resolve()
    if not root.exists():
        return results

    # 1. Standard *.gguf Dateien rekursiv
    try:
        for f in root.rglob("*.gguf"):
            if f.is_file() and not f.name.endswith(".part"):
                p_res = f.resolve()
                if p_res not in seen and is_valid_gguf_header(p_res):
                    seen.add(p_res)
                    results.append(p_res)
    except Exception as e:
        print_log("WARN", f"Fehler bei rglob *.gguf: {e}")

    # 2. Blobs-Verzeichnis & latente Dateien ohne .gguf Endung prüfen
    candidates_dirs = [root / "blobs", root]
    for b_dir in candidates_dirs:
        if b_dir.exists():
            try:
                for f in b_dir.rglob("*"):
                    if f.is_file() and not f.name.endswith(".part") and not f.name.endswith(".json"):
                        p_res = f.resolve()
                        if p_res not in seen and is_valid_gguf_header(p_res):
                            seen.add(p_res)
                            results.append(p_res)
            except Exception as e:
                print_log("WARN", f"Fehler beim Durchsuchen von {b_dir}: {e}")

    # 3. Auch Ollama Manifests einbeziehen
    manifests_dir = root / "manifests"
    if manifests_dir.exists():
        try:
            for mf in manifests_dir.rglob("*"):
                if mf.is_file() and not mf.name.endswith(".part"):
                    try:
                        with open(mf, "r", encoding="utf-8") as fh:
                            m_data = json.load(fh)
                        digest = None
                        for layer in m_data.get("layers", []):
                            if layer.get("mediaType") == "application/vnd.ollama.image.model":
                                digest = layer.get("digest")
                                break
                        if not digest and "config" in m_data:
                            digest = m_data.get("config", {}).get("digest")
                        if digest:
                            blob_file = root / "blobs" / digest.replace(":", "-")
                            if blob_file.exists():
                                p_res = blob_file.resolve()
                                if p_res not in seen and is_valid_gguf_header(p_res):
                                    seen.add(p_res)
                                    results.append(p_res)
                    except Exception:
                        pass
        except Exception:
            pass

    return results

def resolve_model_name_for_blob(blob_path: Path, root_path: Path) -> str:
    \"\"\"Versucht den echten Modellnamen für einen Blob aus den Manifest-Dateien zu ermitteln.\"\"\"
    blob_name = blob_path.name
    digest_clean = blob_name.replace("-", ":") if blob_name.startswith("sha256-") else blob_name
    manifests_dir = root_path / "manifests"
    if manifests_dir.exists():
        for mf in manifests_dir.rglob("*"):
            if mf.is_file():
                try:
                    with open(mf, "r", encoding="utf-8") as fh:
                        m_data = json.load(fh)
                    for layer in m_data.get("layers", []):
                        d = layer.get("digest", "")
                        if d == digest_clean or d.replace(":", "-") == blob_name:
                            parts = mf.relative_to(manifests_dir).parts
                            if len(parts) >= 2:
                                return f"{parts[-2]}:{parts[-1]}" if len(parts) >= 3 else parts[-1]
                except Exception:
                    pass
    return clean_model_name(blob_path.stem)

def clean_model_name(filename_stem: str) -> str:
    name_lower = filename_stem.lower()
    model_patterns = ["deepseek", "llama", "codestral", "mistral", "qwen", "phi", "gemma", "minilm", "bert"]
    detected_model = "model"
    for m in model_patterns:
        if m in name_lower:
            detected_model = m
            break
            
    version_match = re.search(r'(v\\d+|\\d+\\.\\d+)', name_lower)
    detected_version = version_match.group(1) if version_match else ""
    intensity_keywords = ["flash", "pro", "lite", "support", "dspark", "chat", "instruct", "base", "l12", "l6", "32b", "7b", "8b"]
    found_intensities = [kw for kw in intensity_keywords if kw in name_lower]
    detected_intensity = "-".join(found_intensities[:2])
    
    parts = [detected_model]
    if detected_version: parts.append(detected_version)
    if detected_intensity: parts.append(detected_intensity)
        
    clean_name = re.sub(r'[^a-z0-9._-]', '-', "-".join(parts))
    clean_name = re.sub(r'-+', '-', clean_name).strip('-_.')
    
    if len(clean_name) > 35: clean_name = clean_name[:35].strip('-_.')
    return f"{clean_name}:latest"


def verify_model_integrity(client, model_tag: str) -> bool:
    \"\"\"
    Prüft die Modellfunktionalität:
    - Generative Modelle via client.generate()
    - Embedding-Modelle (wie all-minilm) via client.embeddings()
    \"\"\"
    try:
        client.generate(model=model_tag, prompt="Test", options={"num_predict": 1})
        print_log("SUCCESS", f"Inferenz voll funktionsfähig: '{model_tag}'")
        return True
    except Exception as err:
        err_str = str(err).lower()
        if "does not support generate" in err_str:
            # Embedding-Modell erkannt (z. B. all-minilm) -> teste über embeddings API
            try:
                client.embeddings(model=model_tag, prompt="Test")
                print_log("SUCCESS", f"Integrität bestätigt (Embedding-Modell): '{model_tag}'")
                return True
            except Exception as emb_err:
                print_log("ERROR", f"Embedding-Test fehlgeschlagen bei '{model_tag}'", str(emb_err))
                return False
        elif "unknown model architecture" in err_str or "invalid model" in err_str:
            print_log("ERROR", f"Architektur-Fehler bei '{model_tag}'", "Ollama unterstützt diese Struktur nicht.")
            return False  
        elif "out of memory" in err_str or "cuda" in err_str or "memory" in err_str or "timed out" in err_str:
            print_log("WARN", f"Ressourcen-Warnung bei '{model_tag}'", "Modell ist zu groß für VRAM/RAM, aber Datei intakt.")
            return True  
        else:
            print_log("WARN", f"Warnung beim Inferenz-Test von '{model_tag}'", str(err))
            return True  


# 🚀 HAUPTFUNKTION: HYBRID LOGIK MIT OLLAMA-GEGENKONTROLLE & REKURSIVER SUCHE
def run_hybrid_utility(models_dir: str, selected_backend: str, ollama_host: str = "http://127.0.0.1:11434"):
    output_log.clear_output()
    with output_log:
        print(" 🎛️  GGUF HYBRID UTILITY & CLEANUP ENGINE")
        print("  Offline_AI Local Engine\\n")

        # 1. Pfad prüfen & rekursiv scannen
        cleaned_models_dir = os.path.normpath(str(models_dir).strip())
        models_dir_path = Path(cleaned_models_dir).resolve()
        
        if not models_dir_path.exists():
            print_log("WARN", f"Pfad existiert nicht. Erstelle Ordner: {models_dir_path}")
            os.makedirs(models_dir_path, exist_ok=True)

        gguf_files = scan_gguf_files_recursive(models_dir_path)
        global GLOBAL_GGUF_FILES, GGUF_SEARCH_DIR
        GGUF_SEARCH_DIR = models_dir_path
        GLOBAL_GGUF_FILES = gguf_files
        globals()["GGUF_SEARCH_DIR"] = GGUF_SEARCH_DIR
        globals()["GLOBAL_GGUF_FILES"] = GLOBAL_GGUF_FILES

        print_log("INFO", f"Zielpfad (absolut): {models_dir_path}")
        print_log("INFO", f"{len(gguf_files)} verifizierte GGUF-Dateien/Blobs gefunden.")

        if not gguf_files:
            print_log("WARN", "Keine gültigen .gguf oder GGUF-Blob Dateien im Ordner gefunden.")
            return

        # 2. Gegenkontrolle: Läuft Ollama?
        ollama_is_running = False
        try:
            res = requests.get(f"{ollama_host}/api/tags", timeout=2)
            if res.status_code == 200:
                ollama_is_running = True
        except Exception:
            ollama_is_running = False

        if selected_backend == "ollama" and not ollama_is_running:
            print_log("WARN", "Ollama-Dienst ist nicht erreichbar!", "Schalte automatisch um auf 'Direct Llama-CPP'")
            selected_backend = "llama_cpp"

        # MODUS A: OLLAMA (Mit Registrierung & Cleanup)
        if selected_backend == "ollama":
            print_section("Sektion: Ollama Sync & Cleanup", "Verwende Ollama API Server")
            from ollama import Client
            ollama_client = Client(host=ollama_host)
            
            try:
                existing_models = {str(m.model).strip().lower() for m in ollama_client.list().models}
            except Exception as e:
                print_log("ERROR", "Konnte Ollama-Modelliste nicht abrufen", str(e))
                return

            registered_count, skipped_count, error_count = 0, 0, 0
            for idx, gguf_file in enumerate(gguf_files, 1):
                p_abs = gguf_file.resolve()
                model_name = resolve_model_name_for_blob(p_abs, models_dir_path)
                print(f"\\n  [{idx}/{len(gguf_files)}] Evaluieren: {model_name} ({p_abs.name})")
                
                if model_name.lower() in existing_models or any(model_name.lower().split(':')[0] == m.split(':')[0] for m in existing_models):
                    print_log("INFO", f"Übersprungen: Bereits als '{model_name}' vorhanden.")
                    skipped_count += 1
                    continue
                
                modelfile_path = p_abs.parent / f"Modelfile_{p_abs.stem}"
                absolute_gguf_path = str(p_abs).replace('\\\\', '/')
                
                with open(modelfile_path, "w", encoding="utf-8") as f:
                    f.write(f"FROM {absolute_gguf_path}\\n")
                
                url = f"{ollama_host}/api/create"
                payload = {"name": model_name, "modelfile": f"FROM {absolute_gguf_path}\\n", "stream": True}
                
                success = False
                try:
                    response = requests.post(url, json=payload, stream=True)
                    if response.status_code == 200:
                        for line in response.iter_lines():
                            if line:
                                try:
                                    data = json.loads(line.decode('utf-8'))
                                    if "error" in data:
                                        print_log("ERROR", f"Ollama Error ({model_name})", data['error'])
                                    if data.get("status") == "success" or data.get("done"): 
                                        success = True
                                except json.JSONDecodeError:
                                    continue
                except Exception as req_err:
                    print_log("ERROR", "API Request-Fehler", str(req_err))
                
                if success:
                    registered_count += 1
                    print_log("SUCCESS", f"Erfolgreich registriert als '{model_name}'")
                else:
                    error_count += 1
                    
                if modelfile_path.exists(): 
                    modelfile_path.unlink()

            # Integritäts-Check & Bereinigung
            print_section("Sektion: Integritäts-Check & Bereinigung", "Testet Modelle & entfernt inkompatible")
            
            CONFIG_DIR = "./config"
            os.makedirs(CONFIG_DIR, exist_ok=True)
            active_cfg_file = os.path.join(CONFIG_DIR, "active_model_config.json")
            
            local_models = ollama_client.list()
            healthy_models, broken_models = 0, 0

            for i, item in enumerate(local_models.models, 1):
                size_mb = item.size // (1024**2) if item.size else 0
                print(f"\\n  [{i}/{len(local_models.models)}] Prüfe: {item.model} ({size_mb} MB)")
                
                if verify_model_integrity(ollama_client, item.model):
                    healthy_models += 1
                else:
                    broken_models += 1
                    print_log("CLEANUP", f"Entferne defektes Modell '{item.model}'...")
                    try:
                        ollama_client.delete(model=item.model)
                        print_log("SUCCESS", f"Modell '{item.model}' gelöscht.")
                    except Exception as del_err:
                        print_log("ERROR", f"Fehler beim Löschen", str(del_err))

            # Zusammenfassung & Test-Inferenz
            remaining_models = ollama_client.list()
            print_summary(healthy_models, broken_models, len(gguf_files), registered_count, skipped_count, remaining_models.models)

            if remaining_models.models:
                # Wähle bevorzugt ein generatives Modell für den Text-Test, falls vorhanden
                gen_candidates = [m.model for m in remaining_models.models if "minilm" not in m.model.lower() and "embed" not in m.model.lower() and "bge" not in m.model.lower()]
                test_model_tag = gen_candidates[0] if gen_candidates else remaining_models.models[0].model

                print_section("Sektion: Test-Inferenz", f"Prüfung von '{test_model_tag}'")
                try:
                    res = ollama_client.generate(model=test_model_tag, prompt="Erkläre kurz den Vorteil lokaler KI.")
                    print("\\n 💬 ANTWORT:")
                    print(f" {res.get('response', '').strip()}\\n")
                    print_log("SUCCESS", "Inferenz erfolgreich!")
                except Exception as err:
                    err_str = str(err).lower()
                    if "does not support generate" in err_str:
                        try:
                            res_emb = ollama_client.embeddings(model=test_model_tag, prompt="Erkläre kurz den Vorteil lokaler KI.")
                            emb = res_emb.get("embedding", [])
                            print("\\n 💬 EMBEDDING-AUSGABE (Vektor):")
                            print(f" Dimension: {len(emb)}, Vektor: [{', '.join(f'{v:.4f}' for v in emb[:5])}, ...]\\n")
                            print_log("SUCCESS", "Embedding-Inferenz erfolgreich!")
                        except Exception as emb_err:
                            print_log("ERROR", "Test-Inferenz fehlgeschlagen", str(emb_err))
                    else:
                        print_log("ERROR", "Test-Inferenz fehlgeschlagen", str(err))

        # MODUS B: DIRECT LLAMA-CPP (Ohne Ollama)
        else:
            print_section("Sektion: Direct Llama-CPP Engine", "Direktes Laden via absoluten Dateipfad")
            try:
                from llama_cpp import Llama
            except ImportError:
                print_log("ERROR", "Bibliothek 'llama-cpp-python' fehlt!", "Bitte installieren.")
                return

            target_file = gguf_files[0].resolve()
            print_log("INFO", f"Lade direkt via Llama-CPP: {target_file.name}")
            print_log("INFO", f"Absoluter Pfad: {target_file}")
            print_log("INFO", "Weise Layer auf GPUs/CPU zu (n_gpu_layers=-1)...")

            try:
                is_embedding = "minilm" in target_file.name.lower() or "embed" in target_file.name.lower()
                safe_n_ctx = 512 if is_embedding else 2048
                llm_agent = Llama(
                    model_path=str(target_file),
                    n_ctx=safe_n_ctx,
                    n_gpu_layers=-1,
                    verbose=False,
                    embedding=is_embedding
                )
                print_log("SUCCESS", "Modell direkt in Speicher geladen!")

                print_section("Test-Inferenz (Direct Llama-CPP)")
                if is_embedding:
                    embed_res = llm_agent.create_embedding("Erkläre kurz in einem Satz den Vorteil lokaler KI-Modelle.")
                    vec = embed_res["data"][0]["embedding"]
                    print("\\n 💬 EMBEDDING-VEKTOR:")
                    print(f" Dimension: {len(vec)}, Vektor: [{', '.join(f'{v:.4f}' for v in vec[:5])}, ...]\\n")
                    print_log("SUCCESS", "Direkte Embedding-Inferenz erfolgreich abgeschlossen!")
                else:
                    output = llm_agent(
                        prompt="Erkläre kurz in einem Satz den Vorteil lokaler KI-Modelle.",
                        max_tokens=100, temperature=0.7, echo=False
                    )
                    print("\\n 💬 ANTWORT:")
                    print(f" {output['choices'][0]['text'].strip()}\\n")
                    print_log("SUCCESS", "Direkte Inferenz erfolgreich abgeschlossen!")

            except Exception as direct_err:
                print_log("ERROR", "Fehler beim Laden über Llama-CPP", str(direct_err))


# Button Event verknüpfen
def on_button_clicked(b):
    run_hybrid_utility(path_input.value, backend_dropdown.value)

start_button.on_click(on_button_clicked)

# Im Notebook anzeigen
if __name__ == "__main__":
    display(dashboard_box)
'''

nb['cells'][8]['source'] = c8_code.splitlines(keepends=True)
NB_PATH.write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
print("[OK] Cell 8 updated and saved.")
