#!/usr/bin/env python3
"""Günstige, fahrbare W211, E90 und E46 in NRW finden und Favoriten merken.

  python suche.py                  Suche starten (Ergebnisse + bericht.html)
  python suche.py merken 3         Treffer Nr. 3 der letzten Suche merken
  python suche.py merken <URL>     beliebige Anzeige per Link merken
  python suche.py favoriten        gemerkte Autos anzeigen
  python suche.py entfernen 3      Favorit entfernen (Nr., ID oder URL)
  python suche.py web              Übersicht im Browser, mit ♥-Knopf zum Merken
  python suche.py web --handy      dasselbe, aber vom Handy im WLAN aufrufbar
"""

import argparse
import json
import re
import socket
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from autosuche import bericht, speicher
from autosuche.bewertung import bewerte
from autosuche.modelle import MODELLE, passt_zum_modell
from autosuche.quellen import QUELLEN, ist_nrw

HIER = Path(__file__).resolve().parent
BERICHT = HIER / "bericht.html"
GESUCH = re.compile(r"^\s*(suche|gesucht|tausche?|ankauf|kaufe)\b|\bankauf\b|wir kaufen", re.I)


def lade_config():
    return json.loads((HIER / "config.json").read_text(encoding="utf-8"))


def euro(x):
    return f"{x:,}".replace(",", ".") + " €" if x is not None else "? €"


# ------------------------------------------------------------------ Suche --- #
def filtere(anzeigen, modell_key, cfg):
    """Grobfilter ohne Detailseite: richtiges Modell, NRW, Preis vorhanden, kein Gesuch."""
    gut = []
    for a in anzeigen:
        if not a.get("preis") or not (cfg["preis_min"] <= a["preis"] <= cfg["preis_max"]):
            continue
        if GESUCH.search(a["titel"]):
            continue
        if a["quelle"] == "AutoScout24" and not ist_nrw(a["plz"]):
            continue
        if not passt_zum_modell(modell_key, a["titel"], a["beschreibung"], a.get("baujahr")):
            continue
        if a.get("km") and a["km"] > cfg["max_km"]:
            continue
        gut.append(a)
    return gut


def suche_modell(modell_key, cfg, quellen):
    modell = MODELLE[modell_key]
    kandidaten = []
    for q in quellen:
        try:
            roh = q.suche(modell, cfg["preis_min"], cfg["preis_max"], cfg["seiten_pro_suche"])
        except Exception as fehler:  # eine Quelle down -> mit der anderen weitermachen
            print(f"  ! {q.name}: {fehler}", file=sys.stderr)
            continue
        gefiltert = filtere(roh, modell_key, cfg)
        print(f"  {q.name}: {len(roh)} Anzeigen, {len(gefiltert)} passen")
        for a in gefiltert:
            a["_quelle"] = q
        kandidaten += gefiltert

    # doppelte raus, billigste zuerst
    eindeutig = {a["id"]: a for a in kandidaten}
    kandidaten = sorted(eindeutig.values(), key=lambda a: a["preis"])

    ergebnis = []
    for i, a in enumerate(kandidaten):
        q = a.pop("_quelle")
        if i < cfg["details_laden_pro_modell"]:
            try:
                q.details(a)
            except Exception as fehler:
                print(f"  ! Details {a['id']}: {fehler}", file=sys.stderr)
        b = bewerte(f"{a['titel']} {a['beschreibung']}", km=a.get("km"))
        if not b["fahrbar"] or b["kosten"] > cfg["max_reparatur"]:
            continue
        if a.get("km") and a["km"] > cfg["max_km"]:
            continue
        a["bewertung"] = b
        a["gesamt"] = a["preis"] + b["kosten"]
        a["modell"] = modell_key
        ergebnis.append(a)

    ergebnis.sort(key=lambda a: (a["gesamt"], a["preis"]))
    return ergebnis[: cfg["treffer_pro_modell"]]


def befehl_suche(args):
    cfg = lade_config()
    if args.max_preis:
        cfg["preis_max"] = args.max_preis
    if args.max_reparatur:
        cfg["max_reparatur"] = args.max_reparatur
    modelle = [m.upper() for m in (args.modell or cfg["modelle"])]
    quellen = [QUELLEN[n](pause=cfg["pause_sekunden"]) for n in cfg["quellen"]]

    gesehen = set(speicher.lade("gesehen.json", []))
    ergebnisse = {}
    schon_drin = set()  # Baujahr 2005/2006 kann bei E46 und E90 auftauchen
    for key in modelle:
        print(f"\n🔎 {MODELLE[key]['name']} …")
        liste = [a for a in suche_modell(key, cfg, quellen) if a["id"] not in schon_drin]
        for a in liste:
            schon_drin.add(a["id"])
            a["neu"] = a["id"] not in gesehen
            gesehen.add(a["id"])
        ergebnisse[key] = liste

    alle = [a for liste in ergebnisse.values() for a in liste]
    gesenkt = speicher.favoriten_aktualisieren(alle)
    speicher.speichere("gesehen.json", sorted(gesehen))
    stand = speicher.jetzt()
    speicher.speichere("ergebnisse.json", {"stand": stand, "ergebnisse": ergebnisse})
    BERICHT.write_text(bericht.erstelle(ergebnisse, speicher.favoriten(), MODELLE, stand), encoding="utf-8")

    zeige_ergebnisse(ergebnisse)
    for a, alt in gesenkt:
        print(f"💸 Preis gesenkt: {a['titel']} {euro(alt)} → {euro(a['preis'])}  {a['url']}")
    print(f"\nBericht: {BERICHT}")
    print("Gefällt dir eins? ->  python suche.py merken <Nr>")


def zeige_ergebnisse(ergebnisse):
    nr = 0
    for key, liste in ergebnisse.items():
        print(f"\n━━ {MODELLE[key]['name']} ({len(liste)}) ━━")
        if not liste:
            print("  nichts Passendes gefunden")
        for a in liste:
            nr += 1
            b = a["bewertung"]
            neu = " 🆕" if a.get("neu") else ""
            km = f"{a['km']:,}".replace(",", ".") + " km" if a.get("km") else "km ?"
            print(f"#{nr:<3}{euro(a['preis']):>9}{' VB' if a.get('vb') else '   '}  "
                  f"{a['titel'][:55]}{neu}")
            print(f"      {a.get('baujahr') or 'Bj ?'} · {km} · {a.get('ort', '')} · {a['quelle']}")
            print(f"      Reparatur ~{euro(b['kosten'])}"
                  f"{' (' + ', '.join(b['gruende']) + ')' if b['gruende'] else ''}"
                  f"{'  ✔ ' + ', '.join(b['plus']) if b['plus'] else ''}")
            print(f"      {a['url']}")


# -------------------------------------------------------------- Favoriten --- #
def finde_anzeige(ref):
    """Nr. aus der letzten Suche, ID oder URL -> Anzeige (oder None)."""
    letzte = speicher.lade("ergebnisse.json", {}).get("ergebnisse", {})
    alle = [a for liste in letzte.values() for a in liste]
    if ref.isdigit() and 1 <= int(ref) <= len(alle):
        return alle[int(ref) - 1]
    for a in alle + list(speicher.favoriten().values()):
        if ref in (a["id"], a["url"]):
            return a
    return None


def befehl_merken(args):
    a = finde_anzeige(args.ref)
    if a is None:
        if not args.ref.startswith("http"):
            sys.exit(f"Nicht gefunden: {args.ref} (Nummer aus der letzten Suche, ID oder Link angeben)")
        a = {"id": args.ref, "url": args.ref, "titel": args.titel or args.ref, "quelle": "manuell",
             "preis": args.preis}
    speicher.merken({k: v for k, v in a.items() if k != "neu"}, args.notiz or "")
    print(f"♥ gemerkt: {a['titel']}")


def befehl_entfernen(args):
    favs = list(speicher.favoriten().values())
    if args.ref.isdigit() and 1 <= int(args.ref) <= len(favs):
        ziel = favs[int(args.ref) - 1]
    else:
        ziel = next((f for f in favs if args.ref in (f["id"], f["url"])), None)
    if not ziel:
        sys.exit(f"Kein Favorit gefunden: {args.ref}")
    speicher.entfernen(ziel["id"])
    print(f"entfernt: {ziel['titel']}")


def befehl_favoriten(_args):
    favs = speicher.favoriten()
    if not favs:
        print("Noch keine Favoriten. Merken mit: python suche.py merken <Nr>")
        return
    for nr, f in enumerate(favs.values(), 1):
        verlauf = f.get("preis_verlauf", [])
        preise = " → ".join(euro(p) for _, p in verlauf) or euro(f.get("preis"))
        print(f"F{nr:<3}{f['titel'][:60]}")
        print(f"      Preis: {preise} · gemerkt {f.get('gemerkt_am', '')}"
              f"{' · Notiz: ' + f['notiz'] if f.get('notiz') else ''}")
        if f.get("bewertung"):
            print(f"      Reparatur ~{euro(f['bewertung']['kosten'])}")
        print(f"      {f['url']}")
    print("\nEntfernen mit: python suche.py entfernen <Nr>  (Nr. aus dieser Liste)")


# -------------------------------------------------------------------- Web --- #
class WebHandler(BaseHTTPRequestHandler):
    def _seite(self):
        letzte = speicher.lade("ergebnisse.json", {})
        return bericht.erstelle(letzte.get("ergebnisse", {}), speicher.favoriten(), MODELLE,
                                letzte.get("stand", "noch keine Suche"))

    def do_GET(self):
        inhalt = self._seite().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(inhalt)

    def do_POST(self):
        laenge = int(self.headers.get("Content-Length", 0))
        anzeige_id = json.loads(self.rfile.read(laenge) or b"{}").get("id", "")
        if self.path == "/merken" and (a := finde_anzeige(anzeige_id)):
            speicher.merken({k: v for k, v in a.items() if k != "neu"})
        elif self.path == "/entfernen":
            speicher.entfernen(anzeige_id)
        else:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(204)
        self.end_headers()

    def log_message(self, *_):
        pass


def eigene_ip():
    """IP-Adresse dieses Computers im WLAN (z.B. 192.168.178.23)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.168.0.1", 80))  # es wird nichts gesendet, nur die Route bestimmt
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def befehl_web(args):
    if args.handy:
        adresse = f"http://{eigene_ip()}:{args.port}"
        print(f"Auf dem Handy (gleiches WLAN) im Browser öffnen:  {adresse}")
        print("Beenden mit Strg+C")
        HTTPServer(("0.0.0.0", args.port), WebHandler).serve_forever()
    adresse = f"http://localhost:{args.port}"
    print(f"Übersicht läuft auf {adresse}  (beenden mit Strg+C)")
    webbrowser.open(adresse)
    HTTPServer(("127.0.0.1", args.port), WebHandler).serve_forever()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    unter = p.add_subparsers(dest="befehl")

    s = unter.add_parser("suche", help="Suche starten (Standard)")
    s.add_argument("--modell", nargs="+", choices=list(MODELLE) + [m.lower() for m in MODELLE])
    s.add_argument("--max-preis", type=int)
    s.add_argument("--max-reparatur", type=int)

    m = unter.add_parser("merken", help="Auto zu Favoriten hinzufügen")
    m.add_argument("ref", help="Nummer aus der letzten Suche, Anzeigen-ID oder Link")
    m.add_argument("--notiz")
    m.add_argument("--titel", help="nur bei manuell per Link gemerkten Autos")
    m.add_argument("--preis", type=int, help="nur bei manuell per Link gemerkten Autos")

    e = unter.add_parser("entfernen", help="Favorit entfernen")
    e.add_argument("ref")

    unter.add_parser("favoriten", help="Favoriten anzeigen")

    w = unter.add_parser("web", help="Übersicht im Browser mit ♥-Knopf")
    w.add_argument("--port", type=int, default=8765)
    w.add_argument("--handy", action="store_true", help="auch vom Handy im selben WLAN erreichbar")

    args = p.parse_args()
    befehle = {"merken": befehl_merken, "entfernen": befehl_entfernen,
               "favoriten": befehl_favoriten, "web": befehl_web}
    if args.befehl in befehle:
        befehle[args.befehl](args)
    else:
        if args.befehl is None:
            args = s.parse_args([])
        befehl_suche(args)


if __name__ == "__main__":
    main()
