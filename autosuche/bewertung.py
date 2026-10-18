"""Schätzt anhand des Anzeigentexts, ob ein Auto fahrbar ist und was es grob kostet,
es wieder fit zu machen. Das ist eine Faustregel, kein Gutachten."""

import re
from datetime import date

# Treffer hier => Auto fliegt raus (nicht fahrbar oder Reparatur klar über 2.000 €)
AUSSCHLUSS = {
    r"motor\s?schaden|motor (ist )?(defekt|kaputt)|kolbenfresser|pleuel": "Motorschaden",
    r"getriebe\s?schaden|getriebe (ist )?(defekt|kaputt)|getriebe rutscht": "Getriebeschaden",
    r"nicht fahrbereit|nicht fahrbar|nicht fahrtüchtig|springt nicht an|läuft nicht\b(?! unrund)": "nicht fahrbereit",
    r"\bbastler|bastlerfahrzeug|teileträger|ausschlacht": "Bastlerfahrzeug",
    r"totalschaden|wasserschaden|brandschaden|hagelschaden": "schwerer Schaden",
    r"rahmen\s?schaden|achsschaden|unfallwagen|unfall ?fahrzeug|unfallauto|unfallschaden": "Unfallwagen",
    r"nur (für )?export|nur gewerbe|export only": "nur Export/Gewerbe",
    r"kopfdichtung|wasser im öl|öl im wasser": "Zylinderkopfdichtung",
    r"steuerkette (ist )?(gerissen|übersprungen)|kette gerissen|zahnriemen gerissen": "Steuerkette/Zahnriemen gerissen",
}

# Bekannte Mängel mit grob geschätzten Werkstattkosten (freie Werkstatt / Teile online)
MAENGEL = [
    (r"ohne tüv|kein tüv|tüv abgelaufen|tüv fällig|ohne hu|hu abgelaufen|tüv (ist )?abgelaufen|tüv überzogen", 500, "TÜV fällig"),
    (r"rost|durchgerostet", 600, "Rost"),
    (r"kupplung (rutscht|defekt|fällig|kommt (hoch|spät)|muss|schleift)|kupplung bald", 800, "Kupplung"),
    (r"steuerkette (rasselt|defekt|fällig|muss|laut|gelängt)|kettenrasseln|kette rasselt", 1500, "Steuerkette"),
    (r"injektor(en)? (defekt|undicht|fällig|muss)|einspritzdüse(n)? defekt", 900, "Injektoren"),
    (r"turbo(lader)? (defekt|pfeift|kaputt|fällig)|ladedruck", 1200, "Turbolader"),
    (r"(dpf|partikelfilter) (defekt|voll|zu|fällig)", 800, "Partikelfilter"),
    (r"agr(-ventil)? (defekt|fällig)", 400, "AGR-Ventil"),
    (r"\bsbc\b", 1000, "SBC-Bremse"),
    (r"(airmatic|luftfeder\w*) (defekt|undicht|senkt|sackt|fällig)|airmatic fehler", 700, "Luftfederung"),
    (r"vanos (defekt|fällig|rasselt)|vanosfehler", 600, "Vanos"),
    (r"klima(anlage)? (defekt|geht nicht|kühlt nicht|ohne funktion|muss)", 400, "Klimaanlage"),
    (r"ölverlust|verliert öl|öl ?undicht|ölfeucht|schwitzt öl", 300, "Ölverlust"),
    (r"wasserpumpe (defekt|undicht|fällig)|kühlwasserverlust|verliert wasser|überhitzt", 500, "Kühlsystem"),
    (r"bremsen (sind )?(fällig|runter|verschlissen|machen)|bremse fällig", 300, "Bremsen"),
    (r"(querlenker|fahrwerk|stoßdämpfer|koppelstange|traggelenk)\w* (defekt|fällig|ausgeschlagen|poltert|klappert)|poltert|klappert", 400, "Fahrwerk"),
    (r"zündspule (defekt|fällig)|läuft unrund|ruckelt|zündaussetzer", 250, "Zündung/unrunder Lauf"),
    (r"motorkontrollleuchte|mkl leuchtet|motorleuchte|fehler im speicher|fehlerspeicher", 300, "Motorleuchte"),
    (r"(auspuff|endtopf|mittelschalldämpfer|krümmer) (defekt|undicht|laut|durch)", 250, "Auspuff"),
    (r"(lichtmaschine|anlasser) (defekt|fällig)|batterie (leer|defekt)", 300, "Elektrik/Starter"),
    (r"automatik(getriebe)? (ruckelt|schlägt|defekt)|getriebe ruckelt|schaltruck|schaltet hart", 1500, "Automatikgetriebe"),
    (r"delle|kratzer|beule|lackschaden|gebrauchsspuren", 0, "Optische Mängel (nicht eingerechnet)"),
]

# Verneinte Angaben vorher entfernen ("kein Rost", "rostfrei", "unfallfrei" ...)
VERNEINT = r"\b(kein|keine|keinen|ohne)\s+(?!tüv|hu\b)[\wäöüß-]+|\w*(rost|unfall)frei\w*|nicht (rostig|verunfallt)"

GUT = [
    (r"tüv neu|hu neu|neuer tüv|tüv frisch|frischer tüv", "TÜV neu"),
    (r"fahrbereit|fährt einwandfrei|fährt super|fährt gut|läuft einwandfrei", "fährt gut"),
    (r"scheckheft|checkheft|serviceheft", "Scheckheft"),
    (r"inspektion (neu|gemacht)|ölwechsel neu|service neu", "frischer Service"),
    (r"steuerkette (neu|getauscht|gewechselt)", "Steuerkette neu"),
    (r"kupplung (neu|getauscht|gewechselt)", "Kupplung neu"),
]

# Ein Mangel, der als "neu/gemacht/getauscht" erwähnt wird, zählt nicht als Mangel.
REPARIERT = r"(neu|erneuert|getauscht|gewechselt|gemacht|repariert|behoben|ersetzt|frisch)"


def _hu_monate_rest(text, heute=None):
    """Liest 'TÜV bis 05/2027' o.ä. und gibt verbleibende Monate zurück (oder None)."""
    heute = heute or date.today()
    m = re.search(r"(?:tüv|hu)[^\d]{0,15}(\d{1,2})[./](\d{2,4})", text)
    if not m:
        return None
    monat, jahr = int(m.group(1)), int(m.group(2))
    if jahr < 100:
        jahr += 2000
    if not (1 <= monat <= 12):
        return None
    return (jahr - heute.year) * 12 + (monat - heute.month)


def bewerte(text, km=None, heute=None):
    """Gibt ein Dict mit fahrbar, kosten, gruende, plus zurück."""
    t = re.sub(VERNEINT, " ", text.lower())
    ergebnis = {"fahrbar": True, "kosten": 0, "gruende": [], "plus": [], "ausschluss": None}

    for muster, grund in AUSSCHLUSS.items():
        if re.search(muster, t):
            ergebnis["fahrbar"] = False
            ergebnis["ausschluss"] = grund
            return ergebnis

    for muster, kosten, name in MAENGEL:
        treffer = re.search(muster, t)
        if not treffer:
            continue
        # "Kupplung neu" / "Rost gemacht" o.ä. nicht als Mangel zählen
        umfeld = t[max(0, treffer.start() - 25): treffer.end() + 25]
        if re.search(REPARIERT, umfeld) and not re.search(r"muss|fällig|defekt|bald", umfeld):
            continue
        ergebnis["kosten"] += kosten
        ergebnis["gruende"].append(f"{name} (~{kosten} €)" if kosten else name)

    hu = _hu_monate_rest(t, heute)
    if hu is not None and hu < 3 and "TÜV fällig" not in " ".join(ergebnis["gruende"]):
        ergebnis["kosten"] += 500
        ergebnis["gruende"].append("TÜV läuft bald ab (~500 €)")

    if km and km > 300_000:
        ergebnis["kosten"] += 300
        ergebnis["gruende"].append("über 300.000 km (~300 € Puffer)")

    for muster, name in GUT:
        if re.search(muster, t):
            ergebnis["plus"].append(name)

    return ergebnis
