# GoalAlert Updates

Update-Kanal für **GoalAlert** auf der Vu+ Zero 4K mit OpenATV.

## Status

- GitHub-Schreibzugriff eingerichtet.
- Update-Client in GoalAlert integriert.
- Version **6.13.4** lokal gebaut und auf Paket-/Prüfsummenebene geprüft.
- **Noch kein öffentliches IPK-Binary auf GitHub hochgeladen.**
- Deshalb gibt es bis zur Veröffentlichung **noch keine aktive `latest.json`**. Die Online-Suche kann bis dahin keine Version installieren.

## Version 6.13.4 – geplanter Erst-Upload

Dateiname: `enigma2-plugin-extensions-goalalert_6.13.4_all.ipk`

SHA-256: `fc3168c8a89b20cf06c53566dc5559bd3a9f952f9d7515d4336c6a52544f59be`

Die IPK wurde vor der Veröffentlichung bereinigt: **Keine privaten IPTV-Senderdaten oder Zugangsdaten** sind enthalten. Ein vorhandener Index wird beim Upgrade lokal auf die Vu+ gesichert.

**Bekannte offene Fehler:** Torjubel, Vereinswappen in Tor-Popups und automatische IPTV-Suche sind auf der Zielhardware noch nicht nachweislich repariert.

## Ablauf der ersten Veröffentlichung

1. Die oben genannte IPK in die oberste Ebene dieses Repositories hochladen.
2. Den heruntergeladenen Dateiinhalt anhand der SHA-256-Prüfsumme gegen die lokale IPK prüfen.
3. Erst dann `latest.json` mit Version, HTTPS-URL, SHA-256 und Hinweisen erstellen.
4. GoalAlert prüft vor dem Update Versionsnummer und SHA-256; eine Installation erfordert Bestätigung am TV.

Feste Update-Adresse (erst nach Veröffentlichung aktiv):

`https://raw.githubusercontent.com/piscitellilopes-apps/GoalAlert-Updates/main/latest.json`

Andere Projekte (Nova-IPTV, PlayerTrack-AI) bleiben getrennt.
