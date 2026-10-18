"""Speichert Suchergebnisse, schon gesehene Anzeigen und Favoriten als JSON."""

import json
from datetime import datetime
from pathlib import Path

ORDNER = Path(__file__).resolve().parent.parent / "daten"


def _pfad(name):
    ORDNER.mkdir(exist_ok=True)
    return ORDNER / name


def lade(name, standard):
    p = _pfad(name)
    if not p.exists():
        return standard
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return standard


def speichere(name, daten):
    p = _pfad(name)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(daten, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


def jetzt():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


# ----------------------------- Favoriten ----------------------------------- #
def favoriten():
    return lade("favoriten.json", {})


def merken(anzeige, notiz=""):
    favs = favoriten()
    alt = favs.get(anzeige["id"], {})
    eintrag = {**alt, **anzeige}
    eintrag["notiz"] = notiz or alt.get("notiz", "")
    eintrag["gemerkt_am"] = alt.get("gemerkt_am", jetzt())
    verlauf = alt.get("preis_verlauf", [])
    if anzeige.get("preis") and (not verlauf or verlauf[-1][1] != anzeige["preis"]):
        verlauf.append([jetzt(), anzeige["preis"]])
    eintrag["preis_verlauf"] = verlauf
    favs[anzeige["id"]] = eintrag
    speichere("favoriten.json", favs)
    return eintrag


def entfernen(anzeige_id):
    favs = favoriten()
    weg = favs.pop(anzeige_id, None)
    speichere("favoriten.json", favs)
    return weg


def favoriten_aktualisieren(anzeigen):
    """Trägt neue Preise bei Favoriten ein. Gibt Liste (anzeige, alter_preis) bei Preissenkung zurück."""
    favs = favoriten()
    gesenkt = []
    for a in anzeigen:
        f = favs.get(a["id"])
        if not f or not a.get("preis"):
            continue
        alter = f.get("preis")
        if alter and a["preis"] < alter:
            gesenkt.append((a, alter))
        merken({k: v for k, v in a.items() if k != "neu"})
    return gesenkt
