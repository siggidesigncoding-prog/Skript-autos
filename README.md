# Autosuche NRW – W211, E90 & E46

Sucht automatisch die **billigsten fahrbaren** Mercedes W211, BMW E90 und BMW E46 in
**NRW** auf Kleinanzeigen.de und AutoScout24.de. Autos mit Motorschaden, Getriebeschaden,
„für Bastler", Unfallwagen usw. fliegen raus. Für die übrigen wird aus dem Anzeigentext
grob geschätzt, was die Reparatur kostet (z. B. TÜV fällig ~500 €, Rost ~600 €,
Steuerkette ~1.500 €). Alles über **2.000 €** wird aussortiert. Sortiert wird nach
*Preis + geschätzte Reparatur*.

Autos, die dir gefallen, kannst du **merken** (Favoriten). Bei jeder neuen Suche wird
der Preis deiner Favoriten aktualisiert und du siehst, wenn er gesenkt wurde.

## Einrichten (einmalig)

Python 3.9+ installieren, dann im Ordner:

```bash
pip install -r requirements.txt
```

## Benutzen

```bash
python suche.py                       # Suche starten
python suche.py suche --modell e46    # nur E46
python suche.py suche --max-preis 3000 --max-reparatur 1000

python suche.py merken 3              # Treffer #3 der letzten Suche merken
python suche.py merken 3 --notiz "Probefahrt Samstag"
python suche.py merken https://www.kleinanzeigen.de/s-anzeige/...   # beliebiges Auto per Link
python suche.py favoriten             # gemerkte Autos (mit Preisverlauf)
python suche.py entfernen 1           # Favorit F1 entfernen

python suche.py web                   # Übersicht im Browser, Autos per ♥ merken
```

Nach jeder Suche liegt außerdem `bericht.html` im Ordner (ohne ♥-Funktion, dafür
`python suche.py web` nehmen). Neue Anzeigen seit der letzten Suche sind mit 🆕 markiert.

## Auf dem Handy ansehen

Das Skript läuft auf deinem Computer, das Handy zeigt nur die Übersicht an:

1. Am Computer: `python suche.py` (Suche) und dann `python suche.py web --handy`
2. Es erscheint eine Adresse wie `http://192.168.178.23:8765`
3. Handy ins **gleiche WLAN** wie der Computer, die Adresse im Browser eingeben
4. Dort kannst du Autos per ♥ merken. Tipp: im Browser „Zum Startbildschirm hinzufügen"

Fragt Windows nach der Firewall, „Private Netzwerke" erlauben. Der Computer muss
dabei an bleiben und das Fenster offen.

## Einstellungen – `config.json`

| Feld | Bedeutung |
|---|---|
| `preis_min` / `preis_max` | Preisspanne in € (min. 500 filtert 1-€-Lockangebote) |
| `max_reparatur` | max. geschätzte Reparaturkosten (Standard 2000) |
| `max_km` | max. Kilometerstand |
| `details_laden_pro_modell` | wie viele der billigsten Anzeigen komplett gelesen werden (für die Mängel-Prüfung) |
| `treffer_pro_modell` | wie viele Autos pro Modell angezeigt werden |
| `quellen` | `kleinanzeigen`, `autoscout24` |

Die Mängel-Liste und Kosten stehen in `autosuche/bewertung.py` und lassen sich leicht anpassen.

## Automatisch laufen lassen

**Windows** (Aufgabenplanung): Neue Aufgabe → Trigger „täglich" (oder alle 3 Stunden) →
Aktion „Programm starten": `python`, Argumente `suche.py`, Starten in: dein Ordner.

**Mac/Linux** (cron, jeden Tag um 8 und 18 Uhr):

```
0 8,18 * * * cd /pfad/zu/Skript-autos && python3 suche.py >> daten/log.txt 2>&1
```

## Wichtig

- Die Reparatur-Schätzung liest nur, was der Verkäufer schreibt. Verschwiegene Mängel
  findet sie nicht – vor dem Kauf immer Probefahrt und am besten Gebrauchtwagen-Check.
- Kleinanzeigen und AutoScout24 ändern manchmal ihre Seiten. Liefert eine Quelle
  plötzlich 0 Treffer, müssen die Selektoren in `autosuche/quellen.py` angepasst werden.
- Das Skript fragt langsam ab (2 s Pause) und ist nur für den privaten Gebrauch gedacht.
- mobile.de ist nicht dabei, weil die Seite automatische Abfragen blockiert.

## Tests

```bash
pip install pytest && python -m pytest
```
