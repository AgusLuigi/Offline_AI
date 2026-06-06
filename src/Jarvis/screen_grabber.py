import platform
import subprocess
import os
import sys

def capture_screen(output_filename="temp/current_screen.png"):
    """
    Selbstheilender Screenshot-Greifer für Jarvis.
    Unterstützt Windows, macOS, Linux und Android (via adb) und fällt
    bei fehlenden Abhängigkeiten automatisch auf eine simulierte Schnittstelle zurück.
    """
    os.makedirs("temp", exist_ok=True)
    current_os = platform.system()
    
    print(f"[i] VisionGuard: Versuche Bildschirmaufnahme für {current_os}...")

    # 1. macOS Integration
    if current_os == "Darwin":
        try:
            # Nutzt das native macOS Dienstprogramm screencapture (keine Python-Module nötig!)
            subprocess.run(["screencapture", "-x", output_filename], check=True)
            print(f"[✓] Screenshot erfolgreich erstellt (macOS Native): {output_filename}")
            return output_filename
        except Exception as e:
            print(f"[!] Fehler bei nativer macOS Aufnahme: {e}")

    # 2. Linux Integration (X11 / Wayland)
    elif current_os == "Linux":
        # Versuche gnome-screenshot, scrot oder xwd
        for tool in [["gnome-screenshot", "-f", output_filename], ["scrot", output_filename]]:
            try:
                subprocess.run(tool, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print(f"[✓] Screenshot erfolgreich erstellt (Linux Native - {tool[0]}): {output_filename}")
                return output_filename
            except Exception:
                continue

    # 3. Windows / Allgemeiner Fallback via Pillow (PIL ImageGrab)
    try:
        # Import erst zur Laufzeit, um import-Fehler abzufangen
        from PIL import ImageGrab
        img = ImageGrab.grab()
        img.save(output_filename)
        print(f"[✓] Screenshot erfolgreich erstellt (Pillow): {output_filename}")
        return output_filename
    except Exception as e:
        print(f"[!] Pillow-Bildschirmerfassung fehlgeschlagen (z.B. Headless Linux ohne X11): {e}")

    # 4. Android Fallback (falls ADB-Verbindung steht)
    try:
        adb_check = subprocess.run(["adb", "devices"], capture_output=True, text=True)
        if "device" in adb_check.stdout.splitlines()[1]:
            print("[i] Android Gerät via ADB erkannt. Erstelle Android-Screenshot...")
            subprocess.run(["adb", "shell", "screencap", "-p", "/sdcard/screen.png"], check=True)
            subprocess.run(["adb", "pull", "/sdcard/screen.png", output_filename], check=True)
            print(f"[✓] Android Screenshot erfolgreich übertragen nach: {output_filename}")
            return output_filename
        else:
            print("[i] Kein Android-Gerät über ADB verbunden.")
    except Exception:
        pass

    # 5. Simulierte Schnittstelle (Fallback-Sicherheit)
    print("[!] Keine nativer Screengrabber verfügbar. Erstelle ein simuliertes Bild für Jarvis...")
    try:
        # Erstelle eine einfache Dummy-Bilddatei als Text-Fallback oder kleines Dummy-PNG
        with open(output_filename, "wb") as f:
            # Ein transparentes 1x1 Pixel PNG-Dummy-Bild
            dummy_png = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x01\x00\x00\x0c\x00\x01\x07\x01\xd5\x18\x00\x00\x00\x00IEND\xaeB`\x82'
            f.write(dummy_png)
        print(f"[✓] Simulierte Ansicht erstellt unter: {output_filename}")
        return output_filename
    except Exception as dummy_err:
        print(f"[!] Fehler beim Erstellen des Dummy-Bildes: {dummy_err}")
        return None

if __name__ == "__main__":
    capture_screen()