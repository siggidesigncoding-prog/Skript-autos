"""Welche Autos gesucht werden und woran man sie erkennt."""

import re

MODELLE = {
    "W211": {
        "name": "Mercedes E-Klasse W211 / S211",
        "baujahre": (2002, 2009),
        "marke": r"mercedes|benz|\bmb\b",
        "kleinanzeigen_suche": "mercedes w211",
        "autoscout_pfad": "mercedes-benz/e-klasse-(alle)",
        # Andere Generationen, die bei der Suche mit auftauchen können
        "ausschluss": r"\b(w|s|c|a)?21[023]\b|\bw124\b|\bc207\b|\ba207\b|\bcls\b",
        # Typische Schwachstellen (nur Info, fließt nicht in die Kosten ein)
        "schwachstellen": "SBC-Bremse (bis ~2006), Airmatic, Rost an Türen/Radläufen, "
                          "Injektoren beim CDI, Ausgleichswellen beim M272 (bis ~2008)",
    },
    "E90": {
        "name": "BMW 3er E90 (Limousine)",
        "baujahre": (2005, 2012),
        "marke": r"\bbmw\b",
        "kleinanzeigen_suche": "bmw e90",
        "autoscout_pfad": "bmw/3er-(alle)",
        "autoscout_extra": "&body=6",  # nur Limousinen
        "ausschluss": r"\b(e9[123]|e46|f3[0145]|g2[01])\b|touring|coup[eé]|cabrio",
        "schwachstellen": "Steuerkette beim N47-Diesel (318d/320d bis ~2010), Ölverlust "
                          "Ventildeckel/Ölfiltergehäuse, Wasserpumpe (elektrisch), Injektoren N43/N53",
    },
    "E46": {
        "name": "BMW 3er E46",
        "baujahre": (1998, 2006),  # Limousine bis 2005, Coupé/Cabrio bis 2006
        "marke": r"\bbmw\b",
        "kleinanzeigen_suche": "bmw e46",
        "autoscout_pfad": "bmw/3er-(alle)",
        "ausschluss": r"\b(e3[06]|e9[0-3]|f3[0145])\b",
        "schwachstellen": "Rost (Schweller, Wagenheberaufnahmen, Radläufe), Vanos, "
                          "Hinterachsaufnahme beim Compact/Touring, Kühlsystem, Ölverlust",
    },
}


def passt_zum_modell(modell_key, titel, beschreibung="", baujahr=None):
    """Prüft, ob eine Anzeige wirklich zum gesuchten Modell gehört."""
    m = MODELLE[modell_key]
    text = f"{titel} {beschreibung}".lower()
    titel_l = titel.lower()

    # Falsche Marke (z.B. BMW in der Mercedes-Suche) sofort raus
    if not re.search(m["marke"], text):
        return False
    # Steht das Modell-Kürzel direkt im Titel, ist es eindeutig.
    if modell_key.lower() in titel_l.replace(" ", ""):
        return True
    if m["ausschluss"] and re.search(m["ausschluss"], titel_l):
        return False
    if baujahr is not None:
        von, bis = m["baujahre"]
        if not (von <= baujahr <= bis):
            return False
    # Ohne Baujahr und ohne Kürzel im Text ist es zu unsicher.
    if baujahr is None and modell_key.lower() not in text.replace(" ", ""):
        return False
    return True
