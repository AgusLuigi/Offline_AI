# DYNAMISCHES LAYOUT-MANAGEMENT & WIDGET-INITIALISIERUNG

output_log = widgets.Output()

# --- PERSISTENTE PFAD-SPEICHERUNG LOGIK ---
PATH_CONFIG_FILE = os.path.join(CONFIG_DIR, "last_storage_path.json")
def load_last_storage_path() -> str:
    """Lädt den zuletzt verwendeten Speicherpfad aus der Konfiguration."""
    with output_log:
        print(f"[INFO] Versuche, letzten Speicherpfad aus '{PATH_CONFIG_FILE}' zu laden...")
        try:
            if os.path.exists(PATH_CONFIG_FILE):
                with open(PATH_CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    path = data.get("path", "")
                    if path:
                        print(f"[✓] Speicherpfad erfolgreich geladen: {path!r}")
                    else:
                        print("[INFO] Konfigurationsdatei existiert, enthält aber keinen 'path'-Eintrag.")
                    return path
            else:
                print(f"[INFO] Konfigurationsdatei '{PATH_CONFIG_FILE}' existiert noch nicht. Nutze Fallback (Leerpfad).")
        except Exception as e:
            print(f"[FEHLER] Konnte letzten Speicherpfad nicht aus '{PATH_CONFIG_FILE}' laden: {e}")
        return ""

def save_last_storage_path(path: str):
    """Speichert den gewählten Pfad persistent ab mit aktivem Logging."""
    with output_log:
        print(f"[INFO] Speichere letzten Speicherpfad: {path!r} in '{PATH_CONFIG_FILE}'...")
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(PATH_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({"path": path}, f, indent=4, ensure_ascii=False)
            print(f"[✓] Speicherpfad erfolgreich unter '{PATH_CONFIG_FILE}' gespeichert.")
        except Exception as e:
            print(f"[FEHLER] Konnte letzten Speicherpfad nicht speichern: {e}")
            raise

# --- LAUFWERKS- & PFAD-ERKENNUNG ---
def get_system_drives() -> list[tuple[str, str]]:
    """Ermittelt alle verfügbaren Laufwerke/Mountpoints inklusive freiem Speicher mit aktivem Logging."""
    drive_options = []
    with output_log:
        print("[INFO] Ermittle verfügbare Systemlaufwerke und Speicherplätze...")
        try:
            for part in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    free_gb = round(usage.free / (1024**3), 1)
                    total_gb = round(usage.total / (1024**3), 1)
                    label = f"💽 {part.device} ({part.mountpoint}) - {free_gb} GB frei (von {total_gb} GB)"
                    target_path = os.path.join(part.mountpoint, "Offline_AI_Models")
                    drive_options.append((label, target_path))
                    print(f"[DEBUG] Laufwerk erfolgreich eingelesen: {part.device} ({part.mountpoint}) - {free_gb} GB frei")
                except Exception as e:
                    print(f"[HINWEIS] Konnte Festplattendaten für Mountpoint '{getattr(part, 'mountpoint', 'unbekannt')}' nicht abrufen: {e}")
        except Exception as e:
            print(f"[FEHLER] Fehler beim Abrufen der Festplattenpartitionen über psutil: {e}")
        if not drive_options:
            default_path = os.path.join(DATA_DIR, "models")
            print(f"[WARNUNG] Keine Laufwerke gefunden. Verwende Standard-Fallback-Pfad: {default_path}")
            drive_options.append((f"Standard ({default_path})", default_path))
        drive_options.append(("➕ Benutzerdefinierten Pfad eingeben...", "CUSTOM_PATH"))
        print(f"[✓] Laufwerksermittlung abgeschlossen. {len(drive_options)} Optionen bereitgestellt.")
    return drive_options

# --- UI CONTROLLER & EVENT LOGIC ---
CURRENT_LOADED_MODELS = []

def filter_model_options(query: str = ""):
    """Filtert die geladenen Modelle in Echtzeit anhand des Suchbegriffs und sortiert sie alphabetisch (A-Z) mit aktivem Logging."""
    with output_log:
        platform_type = dropdown_platform.value
        q = query.strip().lower()
        print(f"[INFO] Starte Modellfilterung für Plattform '{platform_type}' mit Suchbegriff: {q!r}")
        
        if not CURRENT_LOADED_MODELS:
            print("[WARNUNG] Keine Modelle in 'CURRENT_LOADED_MODELS' vorhanden. Setze Dropdown auf 'Keine Modelle geladen'.")
            dropdown_model.options = [("Keine Modelle geladen", "")]
            dropdown_model.disabled = True
            btn_start_download.disabled = True
            return
        
        print(f"[INFO] Gesamtzahl verfügbarer Modelle vor Filterung: {len(CURRENT_LOADED_MODELS)}")
        matched_models = []
        for m in CURRENT_LOADED_MODELS:
            searchable_content = f"{m.get('name', '')} {m.get('id', '')} {m.get('category', '')} {m.get('size', '')} {m.get('description', '')} {m.get('popularity', '')}".lower()
            if not q or q in searchable_content:
                matched_models.append(m)
                
        # --- LOGIK: ALPHABETISCHE SORTIERUNG NACH NAME (CASE-INSENSITIVE) ---
        matched_models = sorted(matched_models, key=lambda x: str(x.get('name', '')).lower())
        print(f"[INFO] {len(matched_models)} Modelle nach Filterung und alphabetischer Sortierung übrig.")
        
        if platform_type == "ollama":
            options = [(f"{m['name']} ({m['size']}) [{m['category']}]", m['id']) for m in matched_models]
            options.append(("Benutzerdefiniertes Modell (Tag eingeben)", "CUSTOM_OLLAMA"))
        else:
            options = [(f"{m['name']} [{m['category']}] ({m['popularity']})", m['id']) for m in matched_models]
            options.append(("Benutzerdefiniertes Hugging Face Modell (Repo eingeben)", "CUSTOM_HF"))
        
        if matched_models or q == "":
            dropdown_model.options = options
            dropdown_model.disabled = False
            btn_start_download.disabled = False
            
            # --- VERBESSERUNG & SICHERHEITS-CHECK FÜR DIE VORAUSWAHL ---
            if len(options) > 0:
                first_selected_id = options[0][1]
                dropdown_model.value = first_selected_id
                print(f"[✓] Automatische Vorauswahl gesetzt auf ID: {first_selected_id!r}")
                
                # Schaltet sofort das GGUF-Feld scharf und lädt die Quantisierungen
                if platform_type == "huggingface" and first_selected_id != "CUSTOM_HF":
                    print(f"[INFO] Lade Hugging Face Dateidownload-Optionen für Vorauswahl: {first_selected_id!r}")
                    update_hf_file_dropdown(first_selected_id)
                    
                matched_item = next((m for m in CURRENT_LOADED_MODELS if m['id'] == first_selected_id), None)
                if matched_item:
                    html_spec_card.value = render_spec_card(matched_item)
        else:
            print(f"[INFO] Keine Treffer für Suchbegriff '{query}' gefunden.")
            dropdown_model.options = [(f"Keine Treffer für '{query}'", "")]
            dropdown_model.disabled = True
            btn_start_download.disabled = True
            html_spec_card.value = "<div style='padding: 8px 10px; color: #DC2626; font-size: 12px;'>Keine passenden Modelle gefunden. Bitte Suchbegriff anpassen.</div>"

# --- DOWNLOAD EXECUTION MIT VERTEILTER PFAD-ERZWINGUNG ---
def run_download_process():
    """Führt den vollständigen Download- und Integrationsprozess mit umfassendem Logging und Auto-Recovery aus."""
    platform_choice = dropdown_platform.value
    selected_id = dropdown_model.value
    
    with output_log:
        print(f"[INFO] Starte Download-Prozess für Plattform: {platform_choice!r}, Modell-ID: {selected_id!r}")
    
    if dropdown_target_disk.value == "CUSTOM_PATH":
        custom_path_val = text_custom_storage_path.value.strip()
        if not custom_path_val:
            with output_log:
                print("[FEHLER] Kein gültiger benutzerdefinierter Speicherpfad angegeben.")
            raise ValueError("Bitte einen gültigen benutzerdefinierten Speicherpfad angeben!")
        active_dest_dir = custom_path_val
    else:
        active_dest_dir = dropdown_target_disk.value

    with output_log:
        print(f"[INFO] Aktives Zielverzeichnis festgelegt auf: {active_dest_dir}")
    save_last_storage_path(active_dest_dir)

    # UI-Elemente für die Dauer des Downloads sperren
    btn_start_download.disabled = True
    btn_confirm_platform.disabled = True
    dropdown_platform.disabled = True
    text_model_search.disabled = True
    dropdown_model.disabled = True
    dropdown_gguf_file.disabled = True
    dropdown_target_disk.disabled = True
    
    progress_bar.layout.display = "block"
    progress_bar.value = 0
    progress_bar.bar_style = ""
    label_status.value = "Initialisiere Speicherort..."
    
    with output_log:
        clear_output()
        print("=" * 60)
        print(f"--- START DOWNLOAD & INTEGRATION ({platform_choice.upper()}) ---")
        print(f"Priorisiertes Zielverzeichnis: {active_dest_dir}")
        print("=" * 60)
    
    try:
        with output_log:
            print(f"[INFO] Erstelle Zielverzeichnis (falls nicht vorhanden): {active_dest_dir}")
        os.makedirs(active_dest_dir, exist_ok=True)

        if platform_choice == "ollama":
            raw_tag = text_custom_tag.value.strip() if selected_id == "CUSTOM_OLLAMA" else selected_id
            if not raw_tag:
                with output_log:
                    print("[FEHLER] Kein gültiger Ollama-Modelltag angegeben.")
                raise ValueError("Bitte einen gültigen Ollama-Modelltag angeben!")
    
            target_tag = normalize_model_tag(raw_tag)
            
            with output_log:
                print("[System] Beende blockierende Ollama-Prozesse...")
                print("[INFO] Suche nach laufenden Ollama-Prozessen zum Beenden...")
            
            killed_count = 0
            for proc in psutil.process_iter(['name']):
                try:
                    if proc.info['name'] and 'ollama' in proc.info['name'].lower():
                        proc.kill()
                        killed_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied) as pe:
                    with output_log:
                        print(f"[DEBUG] Konnte Prozess nicht beenden (bereits beendet oder keine Rechte): {pe}")
            
            with output_log:
                print(f"[✓] {killed_count} blockierende Ollama-Prozesse bereinigt.")
            time.sleep(2)
            
            with output_log:
                print("[System] Starte entkoppelten Ollama-Dienst auf Wunschpfad...")
                print(f"[INFO] Starte lokalen Ollama-Dienst mit OLLAMA_MODELS={active_dest_dir}...")
            
            env_copy = os.environ.copy()
            env_copy["OLLAMA_MODELS"] = str(Path(active_dest_dir).resolve())
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if hasattr(subprocess, 'CREATE_NEW_PROCESS_GROUP') else 0
            subprocess.Popen(["ollama", "serve"], env=env_copy, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creationflags)
            time.sleep(4)
            
            with output_log:
                print("[✓] Ollama-Dienst erfolgreich gestartet.")
            
            current_digest = None
            
            def render_text_bar(completed, total, length=25):
                """Erzeugt einen visuellen ASCII-Ladebalken für das Output-Log."""
                if not total or total <= 0:
                    return ""
                pct = completed / total
                filled = int(length * pct)
                bar = "█" * filled + "░" * (length - filled)
                return f"[{bar}] {pct*100:.1f}% ({completed // (1024**2)}/{total // (1024**2)} MB)"

            def ollama_callback(progress):
                nonlocal current_digest
                status = progress.get('status', '')
                completed = progress.get('completed', 0)
                total = progress.get('total', 0)
                digest = progress.get('digest', '')
                
                if digest != current_digest and digest:
                    with output_log:
                        print(f"\n[Layer {digest[:12]}] {status}")
                    current_digest = digest
                
                if total and completed and total > 0:
                    pct = min(int((completed / total) * 100), 100)
                    progress_bar.value = pct
                    text_bar = render_text_bar(completed, total)
                    label_status.value = f"[Pull] {status} ({completed // (1024**2)} / {total // (1024**2)} MB)"
                    
                    # Zeilenbasierter Fortschritt direkt im Logging-Container
                    with output_log:
                        print(f"\r[Pulling] {status} {text_bar}", end="", flush=True)
                else:
                    label_status.value = f"[Pull] {status}"
            
            with output_log:
                print(f"[INFO] Starte Ollama Pull für Modell: {target_tag}")
            
            redirected_client = ollama.Client(host="http://127.0.0.1:11434")
            
            # --- AUTO-RECOVERY LOGIK ---
            def execute_pull(tag):
                stream = redirected_client.pull(model=tag, stream=True)
                for progress in stream:
                    ollama_callback(progress)

            try:
                execute_pull(target_tag)
            except Exception as pull_err:
                err_str = str(pull_err).lower()
                if "400" in err_str or "invalid model name" in err_str or "bad request" in err_str:
                    with output_log:
                        print(f"\n[WARNUNG] 400 / Ungültiger Modellname erkannt ({pull_err}).")
                        print("[INFO] Versuche automatische Behebung: Bereinige Manifest & korrigiere Tag...")
                    
                    try:
                        redirected_client.delete(model=target_tag)
                    except Exception:
                        pass
                    
                    # Striktes Sanitizing: Nur Kleinbuchstaben, Zahlen, Doppelpunkt, Bindestrich, Punkt
                    fallback_tag = "".join(c for c in target_tag.lower() if c.isalnum() or c in ":-._")
                    
                    with output_log:
                        print(f"[INFO] Starte erneuten Versuch mit bereinigtem Tag: {fallback_tag!r}")
                    time.sleep(2)
                    
                    execute_pull(fallback_tag)
                    target_tag = fallback_tag
                else:
                    raise pull_err

            registered_name = target_tag
            allocated_size = 4.0
            
            with output_log:
                print(f"\n[✓] Ollama Pull erfolgreich abgeschlossen für: {registered_name}")
            
        else: # Hugging Face
            if selected_id == "CUSTOM_HF":
                repo_id = text_custom_hf_repo.value.strip()
                raw_filename = text_custom_hf_file.value.strip()
            else:
                repo_id = selected_id
                raw_filename = dropdown_gguf_file.value
            
            with output_log:
                print(f"[INFO] Hugging Face Download-Konfiguration - Repo: {repo_id!r}, Datei: {raw_filename!r}")
            
            if not repo_id or not raw_filename:
                with output_log:
                    print("[FEHLER] Repo-ID oder GGUF-Dateiname fehlt.")
                raise ValueError("Bitte Repo-ID und GGUF-Dateinamen angeben!")
            
            filename = os.path.basename(raw_filename)
            raw_tag = filename.lower().replace(".gguf", "").replace("_", "-").replace(".", "-")
            target_tag = normalize_model_tag(raw_tag)
            
            def hf_progress(msg):
                label_status.value = str(msg)
                with output_log:
                    print(f"[HF Hub] {msg}")
                    
            def hf_build(st):
                label_status.value = f"[Ollama Build] {st}"
                with output_log:
                    print(f"[Ollama Build] {st}")
            
            progress_bar.value = 30
            with output_log:
                print(f"[INFO] Übergebe an HuggingFaceBackend für Download von '{filename}' aus '{repo_id}'...")
                
            local_path, allocated_size = hf_backend.download_and_create_model(
                repo_id=repo_id, filename=filename, target_model_tag=target_tag,
                dest_dir=active_dest_dir, progress_callback=hf_progress, build_callback=hf_build
            )
            registered_name = target_tag
            
            with output_log:
                print(f"[✓] Hugging Face Modell erfolgreich heruntergeladen und registriert: {registered_name}")
        
        with output_log:
            print("[INFO] Speichere aktive Modellkonfiguration...")
        ModelConfigManager.save_active_model(model_name=registered_name, size_gb=allocated_size, platform_name=platform_choice, config_dir=CONFIG_DIR)
        
        progress_bar.value = 100
        progress_bar.bar_style = "success"
        label_status.value = f"[✓] Erfolgreich! '{registered_name}' wurde auf Disk gesichert."
        
        with output_log:
            print(f"[✓] Download-Prozess vollständig abgeschlossen für '{registered_name}'.")
        
    except Exception as err:
        progress_bar.bar_style = "danger"
        label_status.value = f"[FEHLER] {err}"
        with output_log:
            print(f"\n[FEHLER] Kritischer Fehler im Download-Prozess: {err}")
        raise
    finally:
        # UI nach Abschluss oder Fehler immer wieder aktivieren
        btn_start_download.disabled = False
        btn_confirm_platform.disabled = False
        dropdown_platform.disabled = False
        text_model_search.disabled = False
        dropdown_model.disabled = False
        dropdown_gguf_file.disabled = False
        dropdown_target_disk.disabled = False

def on_disk_selection_changed(change):
    """Wird aufgerufen, wenn sich die Laufwerksauswahl ändert, mit aktivem Logging."""
    with output_log:
        print(f"[INFO] Laufwerksauswahl geändert. Alter Wert: {change.old!r} -> Neuer Wert: {change.new!r}")
        if change.new == "CUSTOM_PATH":
            print("[INFO] 'CUSTOM_PATH' ausgewählt. Blende Eingabefeld für benutzerdefinierten Pfad ein.")
            text_custom_storage_path.layout.display = "block"
        else:
            print("[INFO] Vordefiniertes Laufwerk ausgewählt. Blende benutzerdefiniertes Eingabefeld aus.")
            text_custom_storage_path.layout.display = "none"
            if change.new:
                print(f"[INFO] Speichere neuen Pfad automatisch ab: {change.new!r}")
                save_last_storage_path(change.new)

def on_custom_path_submitted(change):
    """Wird aufgerufen, wenn ein benutzerdefinierter Pfad eingegeben oder bestätigt wird, mit aktivem Logging."""
    with output_log:
        print(f"[INFO] Benutzerdefinierter Pfad übermittelt. Neuer Wert: {change.new!r}")
        if change.new:
            cleaned_path = change.new.strip()
            print(f"[INFO] Speichere bereinigten benutzerdefinierten Pfad: {cleaned_path!r}")
            save_last_storage_path(cleaned_path)
        else:
            print("[INFO] Übermittelter benutzerdefinierter Pfad ist leer. Speicherung übersprungen.")
# UI CONTROLLER & EVENT LOGIC
CURRENT_LOADED_MODELS = []

def render_spec_card(model_item: dict) -> str:
    """Rendert die HTML-Spezifikationskarte für das ausgewählte Modell mit aktivem Logging."""
    with output_log:
        print("[INFO] Starte Rendern der Modell-Spezifikationskarte...")    
        if not model_item:
            print("[HINWEIS] Kein Modell für die Spezifikationskarte übergeben. Rendere Leer-Zustand.")
            return "<div style='padding: 8px 10px; color: #6B7280; font-size: 12px;'>Kein Modell ausgewählt.</div>"
        model_id = model_item.get("id", "-")
        size = model_item.get("size", "-")
        category = model_item.get("category", "-")
        popularity = model_item.get("popularity", "-")
        platform_name = model_item.get("platform", "").upper()
        print(f"[DEBUG] Generiere Spec-Card für Modell: {model_id!r} (Plattform: {platform_name})")
        html = f"""
        <div style='background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 6px; padding: 10px; margin-top: 4px;'>
            <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;'>
                <span style='background-color: #3B82F6; color: white; font-weight: bold; padding: 2px 8px; border-radius: 4px; font-size: 11px;'>{platform_name}</span>
                <span style='font-weight: bold; font-size: 13px; color: #111827;'>{model_id}</span>
                <span style='background-color: #10B981; color: white; padding: 2px 8px; border-radius: 4px; font-size: 11px;'>RAM verfügbar: {TOTAL_RAM_GB} GB</span>
            </div>
            <div style='display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; background: #F9FAFB; padding: 6px; border-radius: 4px; font-size: 12px; color: #374151;'>
                <div><b>Größe:</b> {size}</div>
                <div><b>Schwerpunkt/Task:</b> {category}</div>
                <div><b>Downloads/Pulls:</b> {popularity}</div>
            </div>
        </div>
        """
        print("[✓] Spezifikationskarte erfolgreich gerendert.")
        return html


def on_search_query_changed(change):
    """Wird aufgerufen, wenn sich der Suchbegriff ändert, mit aktivem Logging."""
    with output_log:
        query_val = change.new if change.new else ""
        print(f"[INFO] Suchfeld-Eingabe geändert. Neuer Suchbegriff: {query_val!r}")
        filter_model_options(query_val)

def on_platform_confirm_clicked(b):
    """Wird aufgerufen, wenn die Plattform-Auswahl bestätigt wird, mit aktivem Logging."""
    global CURRENT_LOADED_MODELS
    with output_log:
        platform_type = dropdown_platform.value
        print(f"[INFO] Plattform-Bestätigung ausgelöst. Gewählte Plattform: {platform_type!r}")
        
        label_status.value = f"Lade Live-Modelle für '{platform_type}'..."
        btn_confirm_platform.disabled = True
        dropdown_model.disabled = True
        text_model_search.value = ""
        
        try:
            if platform_type == "ollama":
                print("[INFO] Rufe Modelle für Ollama ab (Limit: 80)...")
                CURRENT_LOADED_MODELS = ollama_backend.fetch_models(limit=80)
                dropdown_gguf_file.layout.display = "none"
                text_custom_tag.layout.display = "none"
                custom_hf_row.layout.display = "none"
                print("[✓] Ollama-spezifische UI-Elemente ausgeblendet.")
            else:
                print("[INFO] Rufe GGUF-Modelle für Hugging Face ab (Limit: 50)...")
                CURRENT_LOADED_MODELS = hf_backend.fetch_models(limit=50)
                dropdown_gguf_file.layout.display = "block"
                text_custom_tag.layout.display = "none"
                custom_hf_row.layout.display = "none"
                print("[✓] Hugging-Face-spezifische UI-Elemente angepasst (GGUF-Dropdown eingeblendet).")
            
            print(f"[INFO] {len(CURRENT_LOADED_MODELS)} Modelle geladen. Starte Aktualisierung der Filteroptionen...")
            filter_model_options("")
            label_status.value = f"{len(CURRENT_LOADED_MODELS)} Live-Modelle für '{platform_type.upper()}' bereit."
            print("[✓] Plattform-Wechsel erfolgreich abgeschlossen.")
            
        except Exception as err:
            print(f"[FEHLER] Fehler beim Laden der Live-Modelle für '{platform_type}': {err}")
            label_status.value = f"Fehler beim Laden: {err}"
        finally:
            btn_confirm_platform.disabled = False
            print("[DEBUG] Bestätigungs-Button für Plattformwechsel wieder aktiviert.")

def update_hf_file_dropdown(repo_id: str):
    """Aktualisiert die GGUF-Auswahl und bewertet jede Variante mit ✅ oder ❌ mit aktivem Logging."""
    with output_log:
        print(f"[INFO] Starte Aktualisierung des GGUF-Dateidropdowns für Repository: {repo_id!r}")
        try:
            options = hf_backend.fetch_gguf_files_with_fit(repo_id)
            if options:
                print(f"[✓] {len(options)} GGUF-Optionen für Repo '{repo_id}' ermittelt. Aktualisiere Dropdown...")
                dropdown_gguf_file.options = options
                dropdown_gguf_file.disabled = False
                print("[✓] GGUF-Dropdown erfolgreich aktualisiert und aktiviert.")
            else:
                print(f"[WARNUNG] Keine .gguf-Dateien für Repository '{repo_id}' gefunden.")
                dropdown_gguf_file.options = [("Keine .gguf-Dateien gefunden", "")]
                dropdown_gguf_file.disabled = True
        except Exception as e:
            print(f"[FEHLER] Fehler beim Aktualisieren des GGUF-Dateidropdowns für '{repo_id}': {e}")
            dropdown_gguf_file.options = [("Fehler beim Laden der Dateien", "")]
            dropdown_gguf_file.disabled = True
            raise

# DOWNLOAD EXECUTION
def on_model_selection_changed(change):
    """Wird aufgerufen, wenn sich die Modellauswahl ändert, mit aktivem Logging."""
    if not change.new:
        return
    with output_log:
        selected_id = change.new
        print(f"[INFO] Modellauswahl geändert. Neuer Wert: {selected_id!r}")
        
        if selected_id == "CUSTOM_OLLAMA":
            text_custom_tag.layout.display = "block"
            custom_hf_row.layout.display = "none"
            dropdown_gguf_file.layout.display = "none"
            print("[INFO] Benutzerdefiniertes Ollama-Tag-Feld eingeblendet.")
        elif selected_id == "CUSTOM_HF":
            text_custom_tag.layout.display = "none"
            custom_hf_row.layout.display = "flex"
            dropdown_gguf_file.layout.display = "none"
            print("[INFO] Benutzerdefinierte Hugging-Face-Eingabefelder eingeblendet.")
        else:
            text_custom_tag.layout.display = "none"
            custom_hf_row.layout.display = "none"
            if dropdown_platform.value == "huggingface":
                dropdown_gguf_file.layout.display = "block"
                print("[INFO] GGUF-Dateidropdown für Hugging-Face-Modell eingeblendet.")
                update_hf_file_dropdown(selected_id)
            else:
                dropdown_gguf_file.layout.display = "none"
                
            matched = next((m for m in CURRENT_LOADED_MODELS if m['id'] == selected_id), None)
            if matched:
                html_spec_card.value = render_spec_card(matched)
                print("[✓] Spezifikationskarte für das ausgewählte Modell aktualisiert.")

def on_start_download_clicked(b):
    """Wird aufgerufen, wenn der Download-Button geklickt wird, und startet den Hintergrund-Thread mit Logging."""
    with output_log:
        print("[INFO] Start-Button geklickt. Starte Download-Prozess im Hintergrund-Thread...")
        t = threading.Thread(target=run_download_process)
        t.daemon = True
        t.start()



# --- GLOBALE LAYOUT- & WIDGET-HELPER ---
LABEL_WIDTH = "200px"
FULL_WIDTH = "100%"
MAX_WIDTH = "100%"
DROPDOWN_MAX_WIDTH = "480px"


_DEFAULT_TEXT_LAYOUT = widgets.Layout(width=FULL_WIDTH, max_width=MAX_WIDTH, margin="0 0 8px 0")
_DEFAULT_STYLE = {"description_width": LABEL_WIDTH}

def _create_text(placeholder: str, description: str, display: str = "block") -> widgets.Text:
    """Erstellt standardisierte Text-Widgets ohne Überlappung."""
    return widgets.Text(
        placeholder=placeholder,
        description=description,
        style=_DEFAULT_STYLE,
        layout=widgets.Layout(
            width=FULL_WIDTH, 
            max_width=MAX_WIDTH, 
            margin="0 0 8px 0", 
            display=display,
            flex="1 1 auto"
        )
    )

def _create_dropdown(description: str, options=None, disabled=False, display="block") -> widgets.Dropdown:
    """Erstellt standardisierte Dropdown-Widgets mit einheitlicher Maximalbreite."""
    return widgets.Dropdown(
        options=options or [],
        description=description,
        style=_DEFAULT_STYLE,
        layout=widgets.Layout(
            width=FULL_WIDTH, 
            max_width=DROPDOWN_MAX_WIDTH, 
            margin="0 0 8px 0", 
            display=display,
            flex="1 1 auto"
        ),
        disabled=disabled
    )

def _create_section(title: str, subtitle: str, children: list) -> widgets.VBox:
    """Erstellt einen sauberen Sektionen-Container mit automatischem Wrapping."""
    return widgets.VBox(
        [
            widgets.HTML(f"<div style='font-size: 13px; font-weight: 700; color: #1E293B; margin-bottom: 2px;'>{title}</div>"),
            widgets.HTML(f"<div style='font-size: 11px; color: #64748B; margin-bottom: 6px;'>{subtitle}</div>"),
            *children
        ],
        layout=widgets.Layout(
            width=FULL_WIDTH, 
            max_width=MAX_WIDTH, 
            padding="12px 14px", 
            margin="0 0 10px 0",
            border="1px solid #E2E8F0", 
            border_radius="8px", 
            background_color="#F8FAFC",
            overflow_x="auto"
        )
    )

# --- SEKTION 1 WIDGETS (PLATTFORM-AUSWAHL) ---
dropdown_platform = widgets.Dropdown(
    options=[
        ("🦙 Ollama (Offizielle Library & Live-Registry)", "ollama"),
        ("🤗 Hugging Face (GGUF Community Modelle - Top Downloads)", "huggingface")
    ],
    value="ollama",
    description="Plattform:",
    style=_DEFAULT_STYLE,
    layout=widgets.Layout(flex="1 1 auto", min_width="300px", max_width=DROPDOWN_MAX_WIDTH)
)

btn_confirm_platform = widgets.Button(
    description="OK - Plattform bestätigen",
    button_style="info",
    icon="check",
    layout=widgets.Layout(width="210px", height="36px")
)

platform_row = widgets.HBox(
    [dropdown_platform, btn_confirm_platform],
    layout=widgets.Layout(width=FULL_WIDTH, align_items="center", justify_content="flex-start", gap="12px", margin="6px 0 0 0")
)

section_platform = _create_section(
    "📍 Sektion 1: Plattform & Registry auswählen",
    "Wähle die Quelle aus und lade die Live-Modelle mit dem Bestätigungs-Button.",
    [platform_row]
)

# --- SEKTION 2 WIDGETS (SUCHE & MODELL-AUSWAHL - CHIRURGISCH KORRIGIERT) ---
text_model_search = _create_text("Suchbegriff eingeben (z.B. coder, vision, 8b, qwen, llama, math...)", "Modell suchen:")
dropdown_model = _create_dropdown("Modell wählen:", disabled=True)
dropdown_gguf_file = _create_dropdown("GGUF-Datei:", display="none")
text_custom_tag = _create_text("z.B. deepseek-coder:6.7b oder mistral-nemo", "Ollama Tag:", display="none")

text_custom_hf_repo = widgets.Text(placeholder="z.B. TheBloke/Mistral-7B-Instruct-v0.2-GGUF", description="HF Repo ID:", style=_DEFAULT_STYLE, layout=widgets.Layout(flex="1 1 auto", min_width="260px"))
text_custom_hf_file = widgets.Text(placeholder="z.B. mistral-7b-instruct-v0.2.Q4_K_M.gguf", description="HF Dateiname:", style=_DEFAULT_STYLE, layout=widgets.Layout(flex="1 1 auto", min_width="260px"))

custom_hf_row = widgets.VBox(
    [text_custom_hf_repo, text_custom_hf_file],
    layout=widgets.Layout(width=FULL_WIDTH, max_width=MAX_WIDTH, gap="10px", margin="0 0 8px 0", display="none")
)

# Optimierte Spec-Card ohne unsichtbare Container-Überlappung
html_spec_card = widgets.HTML(
    value="<div style='padding: 12px; border-left: 4px solid #3B82F6; background-color: #F1F5F9; border-radius: 6px; font-size: 12px; color: #475569; height: 100%; box-sizing: border-box;'>Wähle eine Plattform in Sektion 1, um Live-Modelle anzuzeigen.</div>",
    layout=widgets.Layout(width=FULL_WIDTH, height="100%", margin="0")
)

# Saubere Aufteilung in zwei gleichberechtigte Spalten ohne Wrapping-Fehler
col_widgets_left = widgets.VBox(
    [text_model_search, dropdown_model, dropdown_gguf_file, text_custom_tag, custom_hf_row],
    layout=widgets.Layout(flex="3 1 55%", min_width="280px")
)

col_specs_right = widgets.VBox(
    [html_spec_card],
    layout=widgets.Layout(flex="2 1 40%", min_width="240px")
)

section_2_hbox = widgets.HBox(
    [col_widgets_left, col_specs_right],
    layout=widgets.Layout(width=FULL_WIDTH, display="flex", flex_wrap="nowrap", gap="16px", align_items="stretch")
)

section_model = _create_section(
    "🔍 Sektion 2: Echtzeit-Suche & Modell-Auswahl",
    "Filtere die Live-Modelle nach Stichworten und wähle die gewünschte Variante.",
    [section_2_hbox]
)

# --- SEKTION 3 WIDGETS (SPEICHERORT, DOWNLOAD & INTEGRATION) ---
dropdown_target_disk = _create_dropdown("Ziel-Laufwerk:", options=get_system_drives())
text_custom_storage_path = _create_text("z.B. D:\\AI_Models oder /mnt/ext_drive/models", "Pfad (Custom):", display="none")

# Gespeicherten Pfad beim Start laden und vorauswählen
saved_path = load_last_storage_path()
if saved_path:
    matching_option = next((opt[1] for opt in dropdown_target_disk.options if opt[1] == saved_path), None)
    if matching_option:
        dropdown_target_disk.value = matching_option
    else:
        dropdown_target_disk.value = "CUSTOM_PATH"
        text_custom_storage_path.value = saved_path
        text_custom_storage_path.layout.display = "block"

btn_start_download = widgets.Button(
    description="OK - Download & In Ollama einbinden",
    button_style="success",
    icon="cloud-download",
    layout=widgets.Layout(width="300px", height="38px", margin="0 0 8px 0"),
    disabled=True
)

progress_bar = widgets.IntProgress(
    value=0, min=0, max=100, description="Fortschritt:", bar_style="info",
    style={"description_width": LABEL_WIDTH, "bar_color": "#10B981"},
    layout=widgets.Layout(width=FULL_WIDTH, max_width=MAX_WIDTH, margin="0 0 4px 0", display="none")
)

label_status = widgets.Label(value="Warte auf Konfiguration...", layout=widgets.Layout(margin="0 0 6px 0"))

output_log = widgets.Output(
    layout=widgets.Layout(
        width=FULL_WIDTH, max_width=MAX_WIDTH, height="150px",
        border="1px solid #CBD5E1", border_radius="6px", padding="8px",
        overflow="auto", background_color="#0F172A"
    )
)

section_download = _create_section(
    "🚀 Sektion 3: Speicherort, Download & Einbindung",
    "Wähle das Ziellaufwerk, starte den Download und registriere das Modell in Ollama.",
    [
        dropdown_target_disk, 
        text_custom_storage_path,
        progress_bar,          # Fortschriftsbalken in den Sektionen-Container integriert
        label_status,          # Statuslabel ebenfalls direkt integriert
        btn_start_download, 

        widgets.HTML("<div style='font-size: 11px; font-weight: 700; color: #475569; margin: 4px 0;'>Live-Prozessprotokoll:</div>"), 
        output_log
    ]
)

section_download.layout.background_color = "#FFFFFF"

# MASTER DASHBOARD CONTAINER
master_dashboard = widgets.VBox([
    widgets.HTML(
        "<div style='display: flex; align-items: center; justify-content: space-between; border-bottom: 2px solid #E2E8F0; padding-bottom: 8px; margin-bottom: 12px;'>"
        "<h3 style='margin: 0; color: #0F172A; font-family: sans-serif; font-size: 16px;'>🎛️ Manuelles Modell-Management & Download-Utility</h3>"
        "<span style='background-color: #3B82F6; color: white; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: bold;'>Mai_AI Local</span>"
        "</div>"
    ),
    section_platform,
    section_model,
    section_download
], layout=widgets.Layout(
    width=FULL_WIDTH, max_width="800px", padding="16px", margin="10px auto",
    border="1px solid #CBD5E1", border_radius="10px", background_color="#FFFFFF"
))

dropdown_target_disk.observe(on_disk_selection_changed, names='value')
text_custom_storage_path.observe(on_custom_path_submitted, names='value')
text_model_search.observe(on_search_query_changed, names='value')
btn_confirm_platform.on_click(on_platform_confirm_clicked)
dropdown_model.observe(on_model_selection_changed, names='value')
btn_start_download.on_click(on_start_download_clicked)

# Erste Initialisierung der Plattform
on_platform_confirm_clicked(None)
display(master_dashboard)