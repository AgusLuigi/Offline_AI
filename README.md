PROJEKT-SPEZIFIKATION: MAI_AI / MAIOMNI PLATFORM
Ziel des Dokuments: Zusammenfassung der Systemarchitektur, des Datenflusses und 
der Sicherheits-Infrastruktur für ein lokales, datenschutzkonformes 
Multi-User-KI-System (analog zum Konzept von nexttoken.co, eine form von javes).

1. DIE VISION & DAS MAI-PRINZIP (OFFLINE-FIRST AI)
Das Projekt "Mai_AI" (oder "MaiOmni") ist eine private, hochperformante und 
vollständig selbstgehostete KI-Plattform. Der Fokus liegt auf absoluter 
Datensouveränität und Unabhängigkeit von Cloud-Anbietern.

Kern-Eigenschaften:
* Lokale Berechnung: Alle KI-Modelle (z. B. Ollama / Codestral) laufen lokal 
  auf der eigenen Hardware (NVIDIA-Infrastruktur).
* Datenschutz: Keine Übermittlung von sensiblen, privaten Daten an externe 
  Server. Das System arbeitet im Kern "Offline-First".
* Best-Practice-Entwicklung: Das System wird über Jupyter Notebooks geplant 
  und mittels Python, Docker und Streamlit modular aufgebaut.

2. MULTI-USER ARCHITEKTUR & OBERFLÄCHE (NEXTTOKEN-STYLE)
Die Plattform soll eine Benutzeroberfläche bieten, die funktional und visuell 
an "nexttoken.co" angelehnt ist. Mehrere Benutzer müssen gleichzeitig auf der 
Plattform arbeiten können, ohne sich gegenseitig zu beeinflussen.

Isolations-Prinzip (Sandbox):
* Jeder Benutzer, der sich auf der Webseite anmeldet (z. B. via Google OAuth2 
  Schnittstelle), bekommt vom System dynamisch eine komplett isolierte 
  Docker-Container-Instanz zugewiesen (z. B. `ai_user_benutzername`).
* Jeder Container läuft auf einem eigenen, separaten Port und ist strikt vom 
  Rest des Netzwerks getrennt.
* Die Benutzer arbeiten parallel, können jedoch niemals die Daten, Sessions 
  oder Chat-Verläufe der anderen Benutzer einsehen oder stören.

3. REVERSE PROXY & ONLINE-ZUGANG (DUCK DNS & TRAEFIK)
Damit die Plattform sicher aus dem Internet erreichbar ist, ohne den Host-Rechner 
angreifbar zu machen, wird eine strikte Netzwerk-Infrastruktur vorgeschaltet:

* Dynamische DNS (Duck DNS): Ermöglicht die Erreichbarkeit der lokalen Webseite 
  über eine feste Domain von außen.
* Reverse Proxy (Traefik / Nginx): Der Proxy nimmt alle Anfragen aus dem Internet 
  entgegen. Er ist der *einzige* Punkt, der nach außen geöffnet ist.
* Google-Authentifizierung: Ein vorgeschalteter "OAuth2-Proxy" fängt Anfragen ab 
  und zwingt den Nutzer zum Google-Login. Erst nach erfolgreicher Erkennung 
  reicht Traefik den Traffic mit dem Header `X-Forwarded-User` an den passenden 
  User-Container weiter.

4. DATENFLUSS, KOMMUNIKATION & RECHTE-STRUKTUR
Der Datenfluss ist so konzipiert, dass die KI selbst keine unkontrollierten 
Rechte auf dem Host-System besitzt.

Kommunikations-Schritte:
1. Der Benutzer gibt Text/Anweisungen in der Docker-Weboberfläche ein.
2. Die Oberfläche schreibt die Eingabe/Daten in eine Datei innerhalb des 
   isolierten Benutzer-Verzeichnisses.
3. Die lokale KI-Logik (Python) erkennt die Änderung, liest die Datei, bereitet 
   die Daten vor und kommuniziert intern (über `host.docker.internal`) mit dem 
   lokalen Ollama-Programm.
4. Die KI berechnet die Antwort/das Projekt auf der lokalen Hardware und 
   schreibt das Ergebnis in das Benutzerverzeichnis zurück.
5. Der Docker-Container liest das Ergebnis und visualisiert es für den Benutzer 
   auf der Webseite.

Datenhoheit des Hauptbenutzers:
* Obwohl die Benutzer isoliert arbeiten, liegen alle Daten physikalisch auf dem 
  Rechner des Hauptbenutzers (Host-System) im Verzeichnis `/app/users/{username}/`.
* Der Hauptbenutzer hat somit die volle Kontrolle und Einsicht in alle 
  generierten Daten, während die einzelnen Docker-Container untereinander 
  gesperrt sind (Data Residency).
* Ein integriertes Sicherheits-Wächter-Modul im Docker-Orchestrator überwacht 
  alle Dateizugriffe, um "Path Traversal" (Ausbrechen aus dem Ordner) zu verhindern.

5. TECHNISCHER STACK & RESSOURCEN-KONTROLLE
* Backend & Steuerung: Python Docker SDK (zur dynamischen Container-Verwaltung).
* Frontend: Streamlit / Web-Oberfläche im Docker-Image verpackt.
* Modell-Schnittstelle: Ollama (lokal auf dem Host-Rechner installiert, Zugriff 
  aus Docker nur über gesicherte interne Brücken).
* Ressourcen-Limits: Um den Host-Rechner vor Überlastung zu schützen, wird 
  jeder User-Container streng limitiert (z. B. max. 512MB RAM, max. 0.5 CPU-Kerne).
  Die schwere KI-Rechenarbeit (Inferenz) wird ohnehin zentral auf der Host-GPU 
  ausgeführt und blockiert nicht die Container.
STATUS: Planungsstruktur in Jupyter Notebook (`.ipynb`) integriert. 
Nächster Schritt: Bereitstellung der `orchestrator.py` und der 
zentralen `docker-compose.yml` für Traefik- und Proxy-Infrastruktur.