# GoalAlert Updates

**Offizieller Update-Kanal für GoalAlert auf der Vu+ Zero 4K mit OpenATV.**

## Aktuell online

- **6.13.4**: Das IPK ist öffentlich hochgeladen.
- `latest.json` wird durch GitHub Actions aus dem geprüften Paket erzeugt.
- Feste Adresse: `https://raw.githubusercontent.com/piscitellilopes-apps/GoalAlert-Updates/main/latest.json`
- GoalAlert prüft HTTPS, Paketname, Versionsnummer und SHA-256 vor Installation.

## Nächste Version: 6.13.5 — Sport Studio

- Status: **IPK lokal erstellt und geprüft, aber noch nicht auf GitHub hochgeladen**.
- Kompakte, modernisierte Tor- und Torschützen-Popups; Größenauswahl Mini/Kompakt/Normal.
- Premium-Sport-Studio-Grafiken und kompaktere Spiel-Listen.
- Lokaler IPTV-Live-Index kann in den Einstellungen separat aktualisiert werden. Keine Vollscans beim Zappen.
- Details und Prüfsumme in [releases/6.13.5.md](releases/6.13.5.md).

Erst wenn `enigma2-plugin-extensions-goalalert_6.13.5_all.ipk` ins Repository hochgeladen ist und die GitHub-Prüfung durchläuft, wechselt die Online-Update-Version auf 6.13.5.

## Sicherheitsregeln

- Keine IPTV-Login-Daten, privaten Bouquets oder privaten Senderindex-Dateien veröffentlichen.
- Ein Update benötigt die ausdrückliche Bestätigung am TV.
- Nova-IPTV und PlayerTrack-AI bleiben separate Projekte.
- Offene Hardware-Tests: Tor-Audio, Originalwappen, realer IPTV-Senderwechsel.

## Automatischer Quellcode-Build (neu eingerichtet)

Der Workflow [build-from-source.yml](.github/workflows/build-from-source.yml) und das [Build-Skript](scripts/build_ipk.py) sind veröffentlicht. Sobald `source/GoalAlert/` mit der vollständigen Plugin-Quelle inklusive Grafiken und `source/VERSION` vorhanden ist, kann GitHub IPKs **ohne lokalen Binär-Upload** aus dem Repository erzeugen, prüfen und zusammen mit `latest.json` committen.

**Der Quellcode ist noch nicht vollständig im Repository.** Deshalb ist diese Pipeline vorbereitet, aber noch nicht für 6.13.5 einsatzbereit. Bitte keine automatische Installationsfreigabe behaupten, bevor die GitHub-IPK existiert und ihre Prüfsumme stimmt.
