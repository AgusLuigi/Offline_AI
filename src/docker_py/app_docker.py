import docker
import os
import sys
import time
import threading
import multiprocessing
import ipywidgets as widgets
from IPython.display import display, clear_output, HTML

# =============================================================================
# 0. GLOBAL CONFIGURATION & FALLBACKS
# =============================================================================
CONFIG = {
    "DEFAULT_IMAGE": "python:3.11-slim",
    "CONTAINER_WORK_DIR": "/docker",
    "RESOURCES": {
        "MIN_CPUS": 1,
        "KEEP_FREE_CPU_PERCENT": 20
    }
}

# Try to discover project root folder index if present
try:
    from folder_index import FOLDER_STRUCTURE, PROJECT_ROOT
except ImportError:
    PROJECT_ROOT = os.path.abspath(os.getcwd())
    FOLDER_STRUCTURE = {"root": PROJECT_ROOT}

# State variables
docker_client = None
live_monitor_thread = None
live_monitor_active = False
monitor_session_id = 0
# =============================================================================
# 1. CUSTOM STYLING (PREMIUM UI BRANDING)
# =============================================================================
UI_STYLE = """
<style>
    .controller-title { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #1e293b; margin-bottom: 5px; }
    .status-badge { padding: 4px 8px; border-radius: 4px; font-weight: bold; font-family: monospace; font-size: 11px; }
    .status-running { background-color: #dcfce7; color: #166534; border: 1px solid #bbf7d0; }
    .status-stopped { background-color: #fee2e2; color: #991b1b; border: 1px solid #fecaca; }
    .status-paused { background-color: #fef9c3; color: #854d0e; border: 1px solid #fef08a; }
    .console-box { font-family: 'Consolas', monospace; font-size: 12px; background-color: #0f172a; color: #38bdf8; padding: 12px; border-radius: 6px; border: 1px solid #1e293b; height: 180px; overflow-y: auto; }
    .warning-card { background-color: #fffbeb; border-left: 5px solid #d97706; padding: 15px; border-radius: 4px; font-family: system-ui; margin-bottom: 10px; }
    .success-card { background-color: #f0fdf4; border-left: 5px solid #16a34a; padding: 15px; border-radius: 4px; font-family: system-ui; margin-bottom: 10px; }
</style>
"""

# =============================================================================
# 2. DOCKER CONNECTION GUARD
# =============================================================================
def connect_docker():
    global docker_client
    try:
        docker_client = docker.from_env(timeout=3.0)
        docker_client.ping()
        return True
    except Exception:
        docker_client = None
        return False

# Initial connection check
is_connected = connect_docker()

# =============================================================================
# 3. UI INITIALIZATION & LAYOUT BUILD
# =============================================================================

# Global Outputs
ui_output_console = widgets.Output()
ui_monitor_panel = widgets.Output(layout=widgets.Layout(border='1px solid #cbd5e1', padding='10px', margin='10px 0', border_radius='6px', background_color='#f8fafc',height='50px'))

# Custom logger helper
def log_to_console(message, type="info"):
    timestamp = time.strftime("%H:%M:%S")
    color_map = {
        "info": "#38bdf8",
        "success": "#4ade80",
        "warning": "#facc15",
        "danger": "#f87171"
    }
    prefix_map = {"info": "ℹ️ [INFO]", "success": "✅ [OK]", "warning": "⚠️ [WARN]", "danger": "❌ [FAIL]"}
    
    prefix = prefix_map.get(type, "")
    color = color_map.get(type, "#f8fafc")
    formatted_line = f"<div style='color: {color}; margin-bottom: 2px;'>[{timestamp}] {prefix} {message}</div>"
    
    with ui_output_console:
        display(HTML(formatted_line))

def clear_console(b=None):
    with ui_output_console:
        clear_output()
    log_to_console("Console cleared.")

# --- 1. Tab widgets & Dropdowns ---
dropdown_containers = widgets.Dropdown(description='📦 Select Target:', style={'description_width': 'initial'}, layout=widgets.Layout(width='100%'))

def populate_containers():
    if not is_connected:
        dropdown_containers.options = [("⚠️ Docker Daemon offline", "none")]
        return
    try:
        containers = docker_client.containers.list(all=True)
        if not containers:
            dropdown_containers.options = [("No containers found", "none")]
        else:
            dropdown_containers.options = [(f"{c.name} ({c.status.upper()})", c.name) for c in containers]
    except Exception as e:
        dropdown_containers.options = [("⚠️ Connection lost", "none")]
        log_to_console(f"Failed to fetch containers: {e}", "danger")

# --- TAB 1: MANAGEMENT & POWER CONTROLS ---
btn_power_start = widgets.Button(description="▶️ Start", button_style="success", layout=widgets.Layout(flex='1 1 auto', height='36px', min_width='80px'))
btn_power_stop = widgets.Button(description="🛑 Stop", button_style="danger", layout=widgets.Layout(flex='1 1 auto', height='36px', min_width='80px'))
btn_power_pause = widgets.Button(description="⏸️ Pause", button_style="warning", layout=widgets.Layout(flex='1 1 auto', height='36px', min_width='80px'))
btn_power_unpause = widgets.Button(description="⏯️ Unpause", button_style="info", layout=widgets.Layout(flex='1 1 auto', height='36px', min_width='80px'))
btn_power_restart = widgets.Button(description="🔄 Restart", layout=widgets.Layout(flex='1 1 auto', height='36px', min_width='80px'))
btn_power_remove = widgets.Button(description="🗑️ Delete", button_style="danger", layout=widgets.Layout(flex='1 1 auto', height='36px', min_width='80px'))
btn_refresh_list = widgets.Button(description="🔄 Reload List", button_style="primary", layout=widgets.Layout(width='120px'))

# Live monitor controls
toggle_monitor = widgets.ToggleButton(value=False, description="📊 Enable Live Monitor", button_style="info", icon='heartbeat', layout=widgets.Layout(width='200px'))
slider_refresh = widgets.IntSlider(value=2, min=1, max=10, description='Rate (Sec):', layout=widgets.Layout(width='250px'))

# Layout Tab 1
controls_box = widgets.HBox([btn_power_start, btn_power_stop, btn_power_pause, btn_power_unpause, btn_power_restart, btn_power_remove], layout=widgets.Layout(justify_content='space-between', margin='10px 0'))
monitor_controls_box = widgets.HBox([toggle_monitor, slider_refresh], layout=widgets.Layout(align_items='center', margin='5px 0'))
tab_management = widgets.VBox([
    widgets.HTML("<h4>🎚️ Active Container Controls</h4>"),
    widgets.HBox([dropdown_containers, btn_refresh_list], layout=widgets.Layout(align_items='center', margin='5px 0')),
    controls_box,
    widgets.HTML("<hr style='border-color: #e2e8f0; margin: 10px 0;'/>"),
    widgets.HTML("<h4>📈 Resource & Status Stream</h4>"),
    monitor_controls_box,
    ui_monitor_panel
])

def get_available_python_images():
    standard_versions = [
        "python:3.12-slim",
        "python:3.11-slim",
        "python:3.10-slim",
        "python:3.9-slim",
        "python:3.12",
        "python:3.11",
        "python:3.10",
        "python:3.9"
    ]
    if not is_connected or docker_client is None:
        return standard_versions
    try:
        images = docker_client.images.list()
        python_tags = []
        for img in images:
            if img.tags:
                for tag in img.tags:
                    if "python" in tag.lower():
                        python_tags.append(tag)
        # Combine, preserve order, deduplicate
        all_tags = []
        for tag in python_tags:
            if tag not in all_tags:
                all_tags.append(tag)
        for tag in standard_versions:
            if tag not in all_tags:
                all_tags.append(tag)
        return all_tags
    except Exception:
        return standard_versions

# --- TAB 2: PRO-GRADE CONTAINER CREATOR ---
input_create_name = widgets.Text(value='mai_ai', description='Name:', placeholder='container_name')
input_create_image = widgets.Combobox(
    value=CONFIG["DEFAULT_IMAGE"],
    options=get_available_python_images(),
    placeholder='Choose or type image (e.g. python:3.11-slim)',
    description='Docker Image:',
    ensure_option=False,
    style={'description_width': 'initial'},
    layout=widgets.Layout(width='100%')
)
input_host_port = widgets.IntText(value=8000, description='Host Port:')
input_container_port = widgets.IntText(value=8000, description='Target Port:')

# Resource limiters
cpu_limit = widgets.FloatSlider(value=1.0, min=0.5, max=float(multiprocessing.cpu_count()), step=0.5, description='CPU Limit:', style={'description_width': 'initial'})
ram_limit = widgets.SelectionSlider(
    options=[('128 MB', '128m'), ('256 MB', '256m'), ('512 MB', '512m'), ('1 GB', '1024m'), ('2 GB', '2048m'), ('4 GB', '4096m'), ('8 GB', '8192m')],
    value='512m',
    description='RAM Limit:',
    style={'description_width': 'initial'}
)

# Volume mount options
input_host_volume = widgets.Text(value=FOLDER_STRUCTURE["root"], description='Host Dir (Bind):', style={'description_width': 'initial'})
input_target_volume = widgets.Text(value=CONFIG["CONTAINER_WORK_DIR"], description='Container Dir:', style={'description_width': 'initial'})
checkbox_volume = widgets.Checkbox(value=True, description='Mount project workspace volume', style={'description_width': 'initial'})
checkbox_tty = widgets.Checkbox(value=True, description='Allocate Pseudo-TTY (Interactive / keep alive)', style={'description_width': 'initial'})

btn_launch_container = widgets.Button(description="🚀 Launch New Container", button_style="success", layout=widgets.Layout(height='40px', font_weight='bold'))

# Form design layout
form_column_left = widgets.VBox([input_create_name, input_create_image, input_host_port, input_container_port], layout=widgets.Layout(flex='1 1 50%', padding='10px'))
form_column_right = widgets.VBox([cpu_limit, ram_limit, input_host_volume, input_target_volume, checkbox_volume, checkbox_tty], layout=widgets.Layout(flex='1 1 50%', padding='10px'))
tab_creator = widgets.VBox([
    widgets.HTML("<h4>🛠️ Configure New Container Deployment</h4>"),
    widgets.HBox([form_column_left, form_column_right]),
    widgets.HTML("<hr style='border-color: #e2e8f0; margin: 10px 0;'/>"),
    btn_launch_container
])

# --- TAB 3: LIVE LOG MONITOR ---
log_num_lines = widgets.IntSlider(value=20, min=5, max=100, step=5, description='Tail Lines:', layout=widgets.Layout(width='300px'))
log_search_filter = widgets.Text(value='', description='Filter Logs:', placeholder='e.g., Error, Connection', layout=widgets.Layout(width='300px'))
btn_refresh_logs = widgets.Button(description="📋 Refresh Logs", button_style="info", layout=widgets.Layout(width='150px'))
ui_logs_area = widgets.Output(layout=widgets.Layout(border='1px solid #1e293b', background_color='#0f172a', padding='10px', height='300px', overflow_y='auto', border_radius='4px'))

tab_logs = widgets.VBox([
    widgets.HTML("<h4>📋 Container Log Streams</h4>"),
    widgets.HBox([log_num_lines, log_search_filter, btn_refresh_logs], layout=widgets.Layout(align_items='center', justify_content='space-between', margin='5px 0')),
    widgets.HTML("<div style='margin-bottom: 5px; font-size:11px; color:#64748b;'>Scrollable container live-output dashboard:</div>"),
    ui_logs_area
])

# --- TAB 4: SYSTEM RESOURCES OVERVIEW ---
ui_system_area = widgets.Output()
btn_refresh_system = widgets.Button(description="🔌 Query System Stats", button_style="primary", layout=widgets.Layout(width='200px'))

tab_system = widgets.VBox([
    widgets.HTML("<h4>⚙️ Docker Host Environment Overview</h4>"),
    btn_refresh_system,
    widgets.HTML("<hr style='border-color: #e2e8f0; margin: 10px 0;'/>"),
    ui_system_area
])

# --- TAB 5: DOCKER DESKTOP ---
ui_desktop_area = widgets.Output(layout=widgets.Layout(height='500px', overflow_y='auto'))
btn_refresh_desktop = widgets.Button(description="🔄 Refresh Desktop Data", button_style="primary", layout=widgets.Layout(width='200px'))

# Global desktop interaction widgets (Erstellen & Laden)
input_pull_image = widgets.Text(placeholder="z.B. redis:alpine, node:18", description="Pull Image:", style={'description_width': 'initial'}, layout=widgets.Layout(width='220px'))
btn_pull_image = widgets.Button(description="📥 Pull Image", button_style="info", layout=widgets.Layout(width='120px'))

input_create_vol = widgets.Text(placeholder="vol_name", description="Create Vol:", style={'description_width': 'initial'}, layout=widgets.Layout(width='220px'))
btn_create_vol = widgets.Button(description="➕ Create Volume", button_style="success", layout=widgets.Layout(width='140px'))

btn_system_prune = widgets.Button(description="🧹 Clean System (Prune)", button_style="danger", icon="trash", layout=widgets.Layout(width='220px'))

# Global desktop interaction widgets (Rückgängig machen / Löschen)
dropdown_delete_image = widgets.Dropdown(style={'description_width': 'initial'}, layout=widgets.Layout(width='220px'))
btn_delete_image = widgets.Button(description="🗑️ Delete Image", button_style="danger", layout=widgets.Layout(width='130px'))

dropdown_delete_vol = widgets.Dropdown(style={'description_width': 'initial'}, layout=widgets.Layout(width='220px'))
btn_delete_vol = widgets.Button(description="🗑️ Delete Volume", button_style="danger", layout=widgets.Layout(width='140px'))

dropdown_delete_net = widgets.Dropdown(style={'description_width': 'initial'}, layout=widgets.Layout(width='220px'))
btn_delete_net = widgets.Button(description="🗑️ Delete Network", button_style="danger", layout=widgets.Layout(width='140px'))

def pull_image_desktop(b=None):
    img_name = input_pull_image.value.strip()
    if not img_name:
        log_to_console("Bitte ein Image zum Herunterladen angeben!", "warning")
        return
    log_to_console(f"Lade Image '{img_name}' aus der Registry herunter (Pull)...", "info")
    def run_pull():
        try:
            docker_client.images.pull(img_name)
            log_to_console(f"Image '{img_name}' erfolgreich heruntergeladen!", "success")
            refresh_desktop_panel()
        except Exception as e:
            log_to_console(f"Fehler beim Herunterladen von '{img_name}': {e}", "danger")
    threading.Thread(target=run_pull, daemon=True).start()

def create_volume_desktop(b=None):
    vol_name = input_create_vol.value.strip()
    if not vol_name:
        log_to_console("Bitte einen Volume-Namen angeben!", "warning")
        return
    try:
        docker_client.volumes.create(name=vol_name)
        log_to_console(f"Volume '{vol_name}' erfolgreich erstellt!", "success")
        refresh_desktop_panel()
    except Exception as e:
        log_to_console(f"Fehler beim Erstellen des Volumes: {e}", "danger")

def delete_image_desktop(b=None):
    target = dropdown_delete_image.value
    if not target or target == "none":
        log_to_console("Kein Image zum Löschen ausgewählt!", "warning")
        return
    log_to_console(f"Lösche Image '{target}'...", "info")
    try:
        docker_client.images.remove(image=target, force=True)
        log_to_console(f"Image '{target}' erfolgreich gelöscht!", "success")
        refresh_desktop_panel()
    except Exception as e:
        log_to_console(f"Fehler beim Löschen des Images (evtl. noch von Container verwendet): {e}", "danger")

def delete_volume_desktop(b=None):
    target = dropdown_delete_vol.value
    if not target or target == "none":
        log_to_console("Kein Volume zum Löschen ausgewählt!", "warning")
        return
    log_to_console(f"Lösche Volume '{target}'...", "info")
    try:
        vol = docker_client.volumes.get(target)
        vol.remove(force=True)
        log_to_console(f"Volume '{target}' erfolgreich gelöscht!", "success")
        refresh_desktop_panel()
    except Exception as e:
        log_to_console(f"Fehler beim Löschen des Volumes (evtl. noch von Container verwendet): {e}", "danger")

def delete_network_desktop(b=None):
    target = dropdown_delete_net.value
    if not target or target == "none":
        log_to_console("Kein Netzwerk zum Löschen ausgewählt!", "warning")
        return
    log_to_console(f"Lösche Netzwerk '{target}'...", "info")
    try:
        net = docker_client.networks.get(target)
        net.remove()
        log_to_console(f"Netzwerk '{target}' erfolgreich gelöscht!", "success")
        refresh_desktop_panel()
    except Exception as e:
        log_to_console(f"Fehler beim Löschen des Netzwerks (evtl. noch von Container verwendet): {e}", "danger")

def system_prune_desktop(b=None):
    log_to_console("Starte Docker Systembereinigung (Prune)...", "info")
    def run_prune():
        try:
            res_c = docker_client.containers.prune()
            res_i = docker_client.images.prune()
            res_n = docker_client.networks.prune()
            res_v = docker_client.volumes.prune()
            
            cleaned_mb = 0
            cleaned_mb += res_c.get('SpaceReclaimed', 0) or 0
            cleaned_mb += res_i.get('SpaceReclaimed', 0) or 0
            cleaned_mb += res_v.get('SpaceReclaimed', 0) or 0
            cleaned_mb = cleaned_mb / (1024**2)
            
            log_to_console(f"Systembereinigung abgeschlossen! {cleaned_mb:.1f} MB Speicherplatz freigegeben.", "success")
            refresh_desktop_panel()
        except Exception as e:
            log_to_console(f"Fehler bei der Systembereinigung: {e}", "danger")
    threading.Thread(target=run_prune, daemon=True).start()

btn_pull_image.on_click(pull_image_desktop)
btn_create_vol.on_click(create_volume_desktop)
btn_delete_image.on_click(delete_image_desktop)
btn_delete_vol.on_click(delete_volume_desktop)
btn_delete_net.on_click(delete_network_desktop)
btn_system_prune.on_click(system_prune_desktop)

def refresh_desktop_panel(b=None):
    with ui_desktop_area:
        clear_output()
        if not docker_client:
            print("Docker Client nicht verbunden.")
            return
            
        images = get_images(docker_client)
        res = get_volumes_and_networks(docker_client)
        compose = get_compose_projects(docker_client)
        k8s = get_kubernetes_status()
        
        k8s_active = k8s.get('active')
        
        # Dynamisch die Dropdown-Optionen befüllen
        img_opts = []
        for img in images:
            if img.tags:
                img_opts.extend(img.tags)
        dropdown_delete_image.options = img_opts if img_opts else [("Keine Images vorhanden", "none")]
        
        vol_opts = [vol.name for vol in res.get('volumes', [])]
        dropdown_delete_vol.options = vol_opts if vol_opts else [("Keine Volumes vorhanden", "none")]
        
        default_nets = ["bridge", "host", "none"]
        net_opts = [net.name for net in res.get('networks', []) if net.name not in default_nets]
        dropdown_delete_net.options = net_opts if net_opts else [("Keine benutzerdefinierten Netzwerke", "none")]
        
        # 1. Overview and System Actions Layout
        overview_html = f"""
        <div style='font-family: system-ui; background-color: #f1f5f9; padding: 15px; border-radius: 6px; border: 1px solid #cbd5e1; margin-bottom: 15px;'>
            <h4 style='margin-top: 0; color: #0f172a;'>📊 Docker Desktop Status & System Control</h4>
            <b>📦 Images:</b> {len(images)} lokal verfügbar | 
            <b>💾 Volumes:</b> {len(res['volumes'])} | 
            <b>🌐 Netzwerke:</b> {len(res['networks'])}<br>
            <b>🏗️ Compose Projekte:</b> {', '.join(compose) if compose else 'Keine aktiven Projekte gefunden'}<br>
            <b>☸️ Kubernetes:</b> {'✅ Aktiv' if k8s_active else '❌ Inaktiv'}
        </div>
        """
        display(HTML(overview_html))
        
        # Display Action Buttons (Prune and Kubernetes Fix)
        sys_buttons = [btn_system_prune]
        if not k8s_active:
            btn_fix_k8s = widgets.Button(
                description="🔧 Auto-Fix & Start Kubernetes",
                button_style="warning",
                icon="wrench",
                layout=widgets.Layout(width='250px')
            )
            btn_fix_k8s.on_click(auto_fix_kubernetes)
            sys_buttons.append(btn_fix_k8s)
            
        display(widgets.HBox(sys_buttons, layout=widgets.Layout(margin='0 0 20px 0')))
        
        # 2. Detailed Images Table
        images_html = "<h4>📦 Local Images (Standardmäßig gelistet)</h4>"
        if not images:
            images_html += "<div style='color: #64748b;'>Keine Images vorhanden.</div>"
        else:
            images_html += """
            <table style='width: 100%; border-collapse: collapse; font-family: system-ui; margin-bottom: 10px; font-size: 12px; border: 1px solid #cbd5e1;'>
                <tr style='background-color: #f8fafc; border-bottom: 2px solid #cbd5e1;'>
                    <th style='padding: 6px; text-align: left;'>Repository/Tag</th>
                    <th style='padding: 6px; text-align: left;'>ID</th>
                    <th style='padding: 6px; text-align: left;'>Größe</th>
                    <th style='padding: 6px; text-align: left;'>Erstellt</th>
                </tr>
            """
            for img in images[:15]:  # Limit to first 15 for space
                tags = ", ".join(img.tags) if img.tags else "<none>"
                img_id = img.short_id.replace("sha256:", "")[:12]
                size_mb = img.attrs.get('Size', 0) / (1024**2)
                created = img.attrs.get('Created', '')[:10]
                images_html += f"""
                <tr style='border-bottom: 1px solid #cbd5e1;'>
                    <td style='padding: 6px; font-weight: bold;'>{tags}</td>
                    <td style='padding: 6px; font-family: monospace;'>{img_id}</td>
                    <td style='padding: 6px;'>{size_mb:.1f} MB</td>
                    <td style='padding: 6px;'>{created}</td>
                </tr>
                """
            images_html += "</table>"
        display(HTML(images_html))
        
        # Pull / Delete Row
        display(widgets.HBox([
            widgets.VBox([widgets.HTML("<b>📥 Pull Image:</b>"), widgets.HBox([input_pull_image, btn_pull_image])]),
            widgets.VBox([widgets.HTML("<b>🗑️ Delete Image (Rückgängig):</b>"), widgets.HBox([dropdown_delete_image, btn_delete_image])])
        ], layout=widgets.Layout(grid_gap='20px', margin='0 0 25px 0')))
        
        # 3. Detailed Volumes Table
        vols_html = "<h4>💾 Docker Volumes (Standardmäßig gelistet)</h4>"
        vols_list = res.get('volumes', [])
        if not vols_list:
            vols_html += "<div style='color: #64748b;'>Keine Volumes vorhanden.</div>"
        else:
            vols_html += """
            <table style='width: 100%; border-collapse: collapse; font-family: system-ui; margin-bottom: 10px; font-size: 12px; border: 1px solid #cbd5e1;'>
                <tr style='background-color: #f8fafc; border-bottom: 2px solid #cbd5e1;'>
                    <th style='padding: 6px; text-align: left;'>Volume-Name</th>
                    <th style='padding: 6px; text-align: left;'>Treiber</th>
                    <th style='padding: 6px; text-align: left;'>Mountpoint</th>
                </tr>
            """
            for vol in vols_list[:10]:
                name = vol.name if len(vol.name) < 40 else vol.name[:37] + "..."
                driver = vol.attrs.get('Driver', '')
                mount = vol.attrs.get('Mountpoint', '')
                mount = mount if len(mount) < 60 else mount[:57] + "..."
                vols_html += f"""
                <tr style='border-bottom: 1px solid #cbd5e1;'>
                    <td style='padding: 6px; font-weight: bold; font-family: monospace;'>{name}</td>
                    <td style='padding: 6px;'>{driver}</td>
                    <td style='padding: 6px; font-family: monospace; font-size: 11px; color: #475569;'>{mount}</td>
                </tr>
                """
            vols_html += "</table>"
        display(HTML(vols_html))
        
        # Create / Delete Row
        display(widgets.HBox([
            widgets.VBox([widgets.HTML("<b>➕ Create Volume:</b>"), widgets.HBox([input_create_vol, btn_create_vol])]),
            widgets.VBox([widgets.HTML("<b>🗑️ Delete Volume (Rückgängig):</b>"), widgets.HBox([dropdown_delete_vol, btn_delete_vol])])
        ], layout=widgets.Layout(grid_gap='20px', margin='0 0 25px 0')))
        
        # 4. Detailed Networks Table
        nets_html = "<h4>🌐 Docker Networks (Standardmäßig gelistet)</h4>"
        nets_list = res.get('networks', [])
        if not nets_list:
            nets_html += "<div style='color: #64748b;'>Keine Netzwerke vorhanden.</div>"
        else:
            nets_html += """
            <table style='width: 100%; border-collapse: collapse; font-family: system-ui; margin-bottom: 10px; font-size: 12px; border: 1px solid #cbd5e1;'>
                <tr style='background-color: #f8fafc; border-bottom: 2px solid #cbd5e1;'>
                    <th style='padding: 6px; text-align: left;'>Netzwerk-Name</th>
                    <th style='padding: 6px; text-align: left;'>ID</th>
                    <th style='padding: 6px; text-align: left;'>Treiber</th>
                    <th style='padding: 6px; text-align: left;'>Bereich</th>
                </tr>
            """
            for net in nets_list[:10]:
                net_id = net.short_id[:12]
                driver = net.attrs.get('Driver', '')
                scope = net.attrs.get('Scope', '')
                nets_html += f"""
                <tr style='border-bottom: 1px solid #cbd5e1;'>
                    <td style='padding: 6px; font-weight: bold;'>{net.name}</td>
                    <td style='padding: 6px; font-family: monospace;'>{net_id}</td>
                    <td style='padding: 6px;'>{driver}</td>
                    <td style='padding: 6px;'>{scope}</td>
                </tr>
                """
            nets_html += "</table>"
        display(HTML(nets_html))
        
        # Delete Custom Network Row
        display(widgets.HBox([
            widgets.VBox([widgets.HTML("<b>🗑️ Delete Custom Network (Rückgängig):</b>"), widgets.HBox([dropdown_delete_net, btn_delete_net])])
        ], layout=widgets.Layout(margin='10px 0 25px 0')))

btn_refresh_desktop.on_click(refresh_desktop_panel)
tab_desktop = widgets.VBox([widgets.HTML("<h4>🖥️ Docker Desktop Übersicht</h4>"), btn_refresh_desktop, ui_desktop_area])

# --- COMBINE INTO MAIN TABS INTERFACE ---
main_tabs = widgets.Tab()
main_tabs.children = [tab_management, tab_desktop, tab_creator, tab_logs, tab_system]
main_tabs.set_title(0, '📦 Container Manager')
main_tabs.set_title(1, '🖥️ Desktop')
main_tabs.set_title(2, '🛠️ Creator Studio')
main_tabs.set_title(3, '📋 Log Streams')
main_tabs.set_title(4, '🖥️ System Overview')

btn_clear_console = widgets.Button(description="🧹 Clear Console Logs", layout=widgets.Layout(width='180px', margin='5px 0'))
btn_clear_console.on_click(clear_console)

ui_footer_and_console = widgets.VBox([
    widgets.HTML("<h4>📟 Action Output Feed</h4>"),
    ui_output_console,
    btn_clear_console
])

# Container UI Frame wrapper
main_dashboard = widgets.VBox([
    widgets.HTML("<h2 class='controller-title'>🐳📦 Docker</h2>"),
    main_tabs,
    widgets.HTML("<hr style='border-color: #cbd5e1; margin: 15px 0;'/>"),
    ui_footer_and_console
], layout=widgets.Layout(border='1px solid #94a3b8', padding='15px', max_width='800px', border_radius='8px', background_color='#f8fafc'))


# =============================================================================
# 4. BUSINESS LOGIC & INTERACTION CONTROLLERS
# =============================================================================

def handle_container_action(b):
    target = dropdown_containers.value
    if not target or target == "none":
        log_to_console("Please select a valid container first!", "warning")
        return
        
    action = b.description
    log_to_console(f"Executing '{action}' action on container '{target}'...", "info")
    
    try:
        c = docker_client.containers.get(target)
        
        if "Start" in action:
            c.start()
            log_to_console(f"Container '{target}' started successfully.", "success")
        elif "Stop" in action:
            c.stop()
            log_to_console(f"Container '{target}' stopped safely.", "success")
        elif "Pause" in action:
            c.pause()
            log_to_console(f"Container '{target}' paused.", "success")
        elif "Unpause" in action:
            c.unpause()
            log_to_console(f"Container '{target}' unpaused.", "success")
        elif "Restart" in action:
            c.restart()
            log_to_console(f"Container '{target}' restarted cleanly.", "success")
        elif "Delete" in action:
            c.remove(force=True)
            log_to_console(f"Container '{target}' force-removed.", "success")
            
        populate_containers()
        refresh_logs_panel()
    except Exception as e:
        log_to_console(f"Action failed: {e}", "danger")

def deploy_new_container(b):
    if not is_connected:
        log_to_console("Docker Daemon is disconnected. Cannot create container.", "danger")
        return
        
    name = input_create_name.value.strip()
    image = input_create_image.value.strip()
    host_p = input_host_port.value
    target_p = input_container_port.value
    
    if not name or not image:
        log_to_console("Container name and image template must be supplied!", "warning")
        return
        
    total_cpus = multiprocessing.cpu_count()
    max_recommended = float(total_cpus * (1 - CONFIG["RESOURCES"]["KEEP_FREE_CPU_PERCENT"]/100))
    if cpu_limit.value > max_recommended:
        log_to_console(f"Resource Warning: Restricting CPU limit to recommended max ({max_recommended:.1f} Cores) to prevent host lockup.", "warning")
    
    log_to_console(f"Pulling image '{image}' if not present locally...", "info")
    
    try:
        ports = {f"{target_p}/tcp": host_p} if (host_p > 0 and target_p > 0) else None
        
        volumes = None
        if checkbox_volume.value:
            h_dir = input_host_volume.value.strip()
            t_dir = input_target_volume.value.strip()
            if h_dir and t_dir:
                volumes = {h_dir: {'bind': t_dir, 'mode': 'rw'}}
                
        nano_cpus = int(cpu_limit.value * 1e9)
        
        new_c = docker_client.containers.run(
            image=image,
            name=name,
            detach=True,
            tty=checkbox_tty.value,
            ports=ports,
            volumes=volumes,
            nano_cpus=nano_cpus,
            mem_limit=ram_limit.value,
            working_dir=input_target_volume.value if volumes else None
        )
        
        log_to_console(f"Container '{new_c.name}' successfully deployed and online!", "success")
        populate_containers()
        dropdown_containers.value = new_c.name
    except Exception as e:
        log_to_console(f"Deployment aborted: {e}", "danger")

def refresh_logs_panel(b=None):
    target = dropdown_containers.value
    with ui_logs_area:
        clear_output()
        if not target or target == "none":
            print("No container targeted for streaming logs.")
            return
        try:
            c = docker_client.containers.get(target)
            lines = log_num_lines.value
            logs_raw = c.logs(tail=lines).decode("utf-8", errors='replace')
            
            if not logs_raw.strip():
                print("[EMPTY STREAM] Log storage has no lines yet.")
                return
                
            keyword = log_search_filter.value.strip().lower()
            if keyword:
                filtered_lines = [line for line in logs_raw.splitlines() if keyword in line.lower()]
                if filtered_lines:
                    print(f"--- FILTERED LOGS (Keyword: '{keyword}') ---")
                    print("\n".join(filtered_lines))
                else:
                    print(f"--- FILTERED LOGS (Keyword: '{keyword}') ---\n[No matches found]")
            else:
                print(logs_raw)
        except Exception as e:
            print(f"Failed to load log stream: {e}")

def refresh_system_panel(b=None):
    with ui_system_area:
        clear_output()
        if not is_connected:
            display(HTML("<div class='warning-card'>⚠️ Docker Daemon offline.</div>"))
            return
        try:
            sys_info = docker_client.info()
            vols = docker_client.volumes.list()
            nets = docker_client.networks.list()
            
            html_stats = f"""
            <table style='width: 100%; border-collapse: collapse; font-family: system-ui;'>
                <tr style='border-bottom: 1px solid #cbd5e1; padding: 6px;'>
                    <td><b>Docker Version:</b></td><td>{sys_info.get('ServerVersion', 'Unknown')}</td>
                </tr>
                <tr style='border-bottom: 1px solid #cbd5e1; padding: 6px;'>
                    <td><b>Operating System:</b></td><td>{sys_info.get('OperatingSystem', 'Unknown')} ({sys_info.get('Architecture', '')})</td>
                </tr>
                <tr style='border-bottom: 1px solid #cbd5e1; padding: 6px;'>
                    <td><b>Total CPUs Allocated:</b></td><td>{sys_info.get('NCPU', 0)} / {multiprocessing.cpu_count()} Host Cores</td>
                </tr>
                <tr style='border-bottom: 1px solid #cbd5e1; padding: 6px;'>
                    <td><b>Total Memory Available:</b></td><td>{sys_info.get('MemTotal', 0) / (1024**3):.2f} GB</td>
                </tr>
                <tr style='border-bottom: 1px solid #cbd5e1; padding: 6px;'>
                    <td><b>Containers Count:</b></td><td>{sys_info.get('Containers', 0)} Total | 🟢 {sys_info.get('ContainersRunning', 0)} Active</td>
                </tr>
                <tr style='border-bottom: 1px solid #cbd5e1; padding: 6px;'>
                    <td><b>Active Volumes:</b></td><td>{len(vols)} mounts</td>
                </tr>
                <tr style='border-bottom: 1px solid #cbd5e1; padding: 6px;'>
                    <td><b>Active Networks:</b></td><td>{len(nets)} bridges</td>
                </tr>
            </table>
            """
            display(HTML(html_stats))
            log_to_console("System details queried successfully.", "success")
        except Exception as e:
            display(HTML(f"<div class='warning-card'>⚠️ Error querying system details: {e}</div>"))


# =============================================================================
# 5. LIVE MONITOR THREAD CONTROLLER
# =============================================================================

def stream_live_metrics(session_id):
    global live_monitor_active, monitor_session_id
    
    # 1. Absicherung: Thread startet nur, wenn wirklich aktiv
    while live_monitor_active and monitor_session_id == session_id:
        if docker_client is None: # Schutz vor unerwartetem Verlust der Verbindung
            break
        target = dropdown_containers.value
        
        # 2. Checkpoint: Abbruch direkt VOR dem UI-Update
        if monitor_session_id != session_id:
            break
        
        with ui_monitor_panel:
            if not target or target == "none":
                clear_output(wait=True)
                display(HTML("<div class='status-badge status-stopped'>⚠️ Wähle einen Container...</div>"))
            else:
                try:
                    c = docker_client.containers.get(target)
                    c.reload()
                    status = c.status.upper()
                    
                    # 3. Checkpoint: Abbruch VOR der Stats-Abfrage
                    if monitor_session_id != session_id:
                        break
                    
                    if status != "RUNNING":
                        clear_output(wait=True)
                        badge_class = "status-paused" if status == "PAUSED" else "status-stopped"
                        display(HTML(f"""
                        <div style='font-family: system-ui;'>
                            <div>🎯 <b>{c.name}</b> | Status: <span class='status-badge {badge_class}'>{status}</span></div>
                            <div style='margin-top: 5px; color: #64748b;'>Keine Live-Metriken (Container läuft nicht).</div>
                        </div>
                        """))
                    else:
                        stats = c.stats(stream=False)
                        
                        # 4. Checkpoint: Abbruch VOR der Stats-Auswertung
                        if monitor_session_id != session_id:
                            break
                        
                        # RAM & CPU Logik mit .get() Absicherung gegen KeyErrors
                        memory_stats = stats.get('memory_stats', {})
                        mem_use = memory_stats.get('usage', 0) / (1024**2)
                        max_lim = memory_stats.get('limit', 1) / (1024**2)
                        mem_pct = (mem_use / max_lim) * 100 if max_lim > 0 else 0
                        
                        cpu_stats = stats.get('cpu_stats', {})
                        cpu_usage = cpu_stats.get('cpu_usage', {})
                        precpu = stats.get('precpu_stats', {})
                        pre_cpu_usage = precpu.get('cpu_usage', {})
                        
                        cpu_delta = cpu_usage.get('total_usage', 0) - pre_cpu_usage.get('total_usage', 0)
                        sys_delta = cpu_stats.get('system_cpu_usage', 0) - precpu.get('system_cpu_usage', 0)
                        online_cpus = cpu_stats.get('online_cpus', multiprocessing.cpu_count())
                        cpu_pct = (cpu_delta / sys_delta) * online_cpus * 100.0 if sys_delta > 0 else 0.0
                        
                        clear_output(wait=True)
                        display(HTML(f"""
                        <div style='font-family: system-ui;'>
                            <div>🎯 <b>{c.name}</b> | Status: <span class='status-badge status-running'>{status}</span></div>
                            <div style='margin-top: 5px;'>🧠 RAM: {mem_use:.2f} MB ({mem_pct:.1f}%)</div>
                            <div>⚙️ CPU: {cpu_pct:.2f} %</div>
                        </div>
                        """))
                except docker.errors.NotFound:
                    if monitor_session_id == session_id:
                        clear_output(wait=True)
                        display(HTML("<div class='status-badge status-stopped'>⚠️ Container nicht gefunden (gelöscht?)</div>"))
                except docker.errors.APIError as e:
                    if monitor_session_id == session_id:
                        clear_output(wait=True)
                        display(HTML(f"<div class='status-badge status-stopped'>⚠️ Docker API Fehler: {e}</div>"))
                except Exception as e:
                    # Stille Ausnahmebehandlung beim Abbruch
                    if monitor_session_id == session_id:
                        clear_output(wait=True)
                        display(HTML(f"<div style='color:#b91c1c;'>⚠️ Verbindung wird geladen... ({e})</div>"))
        
        # 5. Schlafphase mit kontinuierlicher Abbruchprüfung
        sleep_time = slider_refresh.value if (slider_refresh.value is not None and slider_refresh.value > 0) else 2
        slept = 0.0
        while slept < sleep_time:
            if monitor_session_id != session_id or not live_monitor_active:
                break
            time.sleep(0.1)
            slept += 0.1
            
    # Sauberes Ende
    if monitor_session_id == session_id:
        live_monitor_active = False
        
def handle_monitor_toggle(change):
    global live_monitor_active, live_monitor_thread, monitor_session_id
    
    # Chirurgische Absicherung: Wir reagieren nur, wenn sich der Wert tatsächlich ändert
    # 'old' ist manchmal None beim ersten Initialisieren, daher der check
    if change.get('old') is not None and change['new'] == change['old']:
        return

    if change['new']:
        # Session ID erhöhen, um alle früheren Threads sofort zu invalidieren
        monitor_session_id += 1
        live_monitor_active = True
        
        # UI-Status hart setzen
        toggle_monitor.description = "⏹️ Stop Live Monitor"
        toggle_monitor.button_style = "danger"
        
        # Neuen Thread sauber starten
        live_monitor_thread = threading.Thread(
            target=stream_live_metrics, 
            args=(monitor_session_id,), 
            daemon=True
        )
        live_monitor_thread.start()
        log_to_console("Active Background Monitor thread launched.", "info")
    else:
        # Signalisierung zum sofortigen Abbruch der Schleife
        live_monitor_active = False
        monitor_session_id += 1 # Invaldiert den aktuellen Thread sofort
        
        toggle_monitor.description = "📊 Enable Live Monitor"
        toggle_monitor.button_style = "info"
        
        with ui_monitor_panel:
            clear_output(wait=True)
            display(HTML("<div style='color: #64748b;'>Monitor offline. Press enable to start streaming.</div>"))
        
        log_to_console("Background Monitor thread stopped.", "info")
toggle_monitor.unobserve_all()
toggle_monitor.observe(handle_monitor_toggle, names='value')


# =============================================================================
# 6. EVENT HOOKS & LAUNCH HANDLERS
# =============================================================================

def start_watchdog():
    def watchdog_loop():
        global is_connected, docker_client
        while True:
            time.sleep(10)  # Prüfintervall: Alle 10 Sekunden
            if not is_connected:
                log_to_console("Watchdog: Docker Daemon offline, versuche Reconnect...", "warning")
                if connect_docker():
                    is_connected = True
                    log_to_console("Watchdog: Reconnect erfolgreich!", "success")
            
            # Beispiel für Container-Heilung:
            # Wenn du spezifische Container wie 'mai_ai' überwachen willst:
            try:
                if is_connected:
                    c = docker_client.containers.get('mai_ai')
                    if c.status != 'running':
                        log_to_console("Watchdog: 'mai_ai' gestoppt, starte neu...", "warning")
                        c.start()
            except:
                pass # Container existiert vielleicht nicht

    threading.Thread(target=watchdog_loop, daemon=True).start()

# Button Click Handlers Mapping
for btn in [btn_power_start, btn_power_stop, btn_power_pause, btn_power_unpause, btn_power_restart, btn_power_remove]:
    btn.on_click(handle_container_action)
    
btn_refresh_list.on_click(lambda b: [populate_containers(), log_to_console("Container list populated cleanly.", "success")])
btn_launch_container.on_click(deploy_new_container)
btn_refresh_logs.on_click(refresh_logs_panel)
btn_refresh_system.on_click(refresh_system_panel)

def run_controller():
    start_watchdog()
    display(HTML(UI_STYLE))
    if is_connected:
        populate_containers()
        refresh_logs_panel()
        refresh_system_panel()
        
        # Stop keydowns from triggering Jupyter shortcuts
        js_fix = widgets.HTML("""
        <script>
        document.querySelectorAll('textarea, input').forEach(el => {
            el.addEventListener('keydown', e => e.stopPropagation(), true);
        });
        </script>
        """)
        display(js_fix)
        display(main_dashboard)
        log_to_console("Mai AI Container Controller Initialized successfully. Ready to run.", "success")
    else:
        btn_retry = widgets.Button(description="🔄 Retry Connection", button_style="warning")
        
        def retry_conn(b):
            global is_connected
            is_connected = connect_docker()
            clear_output()
            if is_connected:
                populate_containers()
                refresh_logs_panel()
                refresh_system_panel()
                display(widgets.HTML("""
                <script>
                document.querySelectorAll('textarea, input').forEach(el => {
                    el.addEventListener('keydown', e => e.stopPropagation(), true);
                });
                </script>
                """))
                display(main_dashboard)
                log_to_console("Successfully re-established Docker Daemon connection!", "success")
            else:
                display(HTML("""
                <div class='warning-card'>
                    <h3>⚠️ Docker Daemon Connection Unreachable</h3>\n                    <p>Could not initialize Docker client. Please verify Docker Desktop is running locally and active, then press the retry button below.</p>
                </div>
                """))
                display(btn_retry)
                
        btn_retry.on_click(retry_conn)
        
        display(HTML("""
        <div class='warning-card'>
            <h3>⚠️ Docker Daemon Connection Unreachable</h3>
            <p>Could not initialize Docker client. Please verify Docker Desktop is running locally and active, then press the retry button below.</p>
        </div>
        """))
        display(btn_retry)

if __name__ == "__main__":
    run_controller()

# =============================================================================
#  Docker UI Desktop
# =============================================================================

# Stelle sicher, dass dein Logging-System importiert oder definiert ist
# Beispiel: from docker_start import log_to_console

def get_images(docker_client):
    if not docker_client:
        return []
    try:
        return docker_client.images.list()
    except Exception as e:
        # log_to_console(f"Fehler beim Laden der Images: {e}", "danger")
        return []

def get_volumes_and_networks(docker_client):
    if not docker_client:
        return {"volumes": [], "networks": []}
    try:
        volumes = docker_client.volumes.list()
        networks = docker_client.networks.list()
        return {"volumes": volumes, "networks": networks}
    except Exception as e:
        # log_to_console(f"Fehler beim Abrufen der Systemressourcen: {e}", "danger")
        return {"volumes": [], "networks": []}

def get_compose_projects(docker_client):
    if not docker_client:
        return []
    try:
        containers = docker_client.containers.list(all=True)
        projects = []
        for c in containers:
            project_name = c.labels.get('com.docker.compose.project')
            if project_name and project_name not in projects:
                projects.append(project_name)
        return projects
    except Exception as e:
        # log_to_console(f"Fehler beim Abrufen der Compose-Projekte: {e}", "danger")
        return []

def get_kubernetes_status():
    try:
        from kubernetes import client, config
        config.load_kube_config()
        v1 = client.CoreV1Api()
        nodes = v1.list_node().items
        return {"active": True, "nodes": len(nodes)}
    except Exception as e:
        return {"active": False, "error": str(e)}

def auto_fix_kubernetes(b=None):
    log_to_console("Starte Auto-Fix / Aktivierung von Kubernetes...", "info")
    
    def run_fix():
        import subprocess
        # 1. Versuche Minikube zu starten
        try:
            log_to_console("Prüfe auf Minikube...", "info")
            res = subprocess.run(["minikube", "status"], capture_output=True, text=True)
            log_to_console("Minikube gefunden. Starte Minikube-Cluster...", "info")
            proc = subprocess.Popen(["minikube", "start"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in proc.stdout:
                log_to_console(f"[Minikube] {line.strip()}", "info")
            proc.wait()
            if proc.returncode == 0:
                log_to_console("Minikube wurde erfolgreich gestartet!", "success")
                refresh_desktop_panel()
                return
        except FileNotFoundError:
            pass
            
        # 2. Versuche k3d zu starten
        try:
            log_to_console("Prüfe auf k3d...", "info")
            res = subprocess.run(["k3d", "cluster", "list"], capture_output=True, text=True)
            log_to_console("k3d gefunden. Erstelle/Starte k3d-Cluster...", "info")
            proc = subprocess.Popen(["k3d", "cluster", "create", "mai-cluster"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in proc.stdout:
                log_to_console(f"[k3d] {line.strip()}", "info")
            proc.wait()
            if proc.returncode == 0:
                log_to_console("k3d-Cluster wurde erfolgreich gestartet!", "success")
                refresh_desktop_panel()
                return
        except FileNotFoundError:
            pass
            
        # 3. Versuche kind zu starten
        try:
            log_to_console("Prüfe auf kind...", "info")
            res = subprocess.run(["kind", "get", "clusters"], capture_output=True, text=True)
            log_to_console("kind gefunden. Erstelle/Starte kind-Cluster...", "info")
            proc = subprocess.Popen(["kind", "create", "cluster"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in proc.stdout:
                log_to_console(f"[kind] {line.strip()}", "info")
            proc.wait()
            if proc.returncode == 0:
                log_to_console("kind-Cluster wurde erfolgreich gestartet!", "success")
                refresh_desktop_panel()
                return
        except FileNotFoundError:
            pass
            
        # 4. Fallback: Anleitung für Docker Desktop
        log_to_console("Kein lokaler K8s-Provider (Minikube, k3d, kind) gefunden. Bitte aktivieren Sie Kubernetes direkt in den Docker Desktop Einstellungen unter 'Settings -> Kubernetes -> Enable Kubernetes'.", "warning")

    threading.Thread(target=run_fix, daemon=True).start()