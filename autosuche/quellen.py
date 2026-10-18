"""Holt Anzeigen von Kleinanzeigen.de und AutoScout24.de.

Beide Seiten ändern ihr HTML ab und zu. Wenn eine Quelle plötzlich 0 Treffer
liefert, ist meist hier ein Selektor anzupassen.
"""

import json
import re
import time
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

KOPFZEILEN = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept-Language": "de-DE,de;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Postleitzahl-Anfänge, die (fast komplett) zu NRW gehören. Nur grob, wird nur
# für AutoScout24 gebraucht (Kleinanzeigen filtert selbst nach Bundesland).
NRW_PLZ = (
    "32", "33", "40", "41", "42", "44", "45", "46", "47", "48",
    "50", "51", "52", "53", "57", "58", "59",
    "344", "376", "4947", "4948", "4949", "4950",  # Warburg, Höxter, Ibbenbüren/Mettingen
)
# Anfänge innerhalb dieser Bereiche, die zu Rheinland-Pfalz gehören
NICHT_NRW_PLZ = ("534", "535", "575", "576", "577", "578", "579")


def ist_nrw(plz):
    plz = (plz or "").strip()
    if len(plz) != 5 or not plz.isdigit():
        return False
    return plz.startswith(NRW_PLZ) and not plz.startswith(NICHT_NRW_PLZ)


def zahl(text):
    """'12.345 km' -> 12345, '3.900 € VB' -> 3900"""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return int(text)
    ziffern = re.sub(r"[^\d]", "", str(text))
    return int(ziffern) if ziffern else None


def baujahr_aus(text):
    m = re.search(r"(?:ez|erstzulassung|bj\.?|baujahr)?\s*(?:\d{1,2}[/.-])?((?:19|20)\d{2})\b", text or "", re.I)
    return int(m.group(1)) if m else None


def km_aus(text):
    m = re.search(r"(\d{1,3}(?:\.\d{3})+|\d{4,7})\s?km\b", text or "", re.I)
    return zahl(m.group(1)) if m else None


class Quelle:
    name = "?"

    def __init__(self, pause=2.0, sitzung=None):
        self.pause = pause
        self.sitzung = sitzung or requests.Session()
        self.sitzung.headers.update(KOPFZEILEN)

    def hole(self, url):
        time.sleep(self.pause)  # Seiten nicht fluten
        antwort = self.sitzung.get(url, timeout=25)
        antwort.raise_for_status()
        return antwort.text


# --------------------------------------------------------------------------- #
# Kleinanzeigen.de
# --------------------------------------------------------------------------- #
class Kleinanzeigen(Quelle):
    name = "Kleinanzeigen"
    BASIS = "https://www.kleinanzeigen.de"
    # c216 = Autos, l928 = Nordrhein-Westfalen
    KATEGORIE_ORT = "k0c216l928"

    def such_url(self, suchbegriff, preis_min, preis_max, seite=1):
        teile = ["s-autos", "nordrhein-westfalen", "sortierung:preis",
                 f"preis:{preis_min}:{preis_max}"]
        if seite > 1:
            teile.append(f"seite:{seite}")
        teile += [quote(suchbegriff.replace(" ", "-")), self.KATEGORIE_ORT]
        return f"{self.BASIS}/" + "/".join(teile)

    @staticmethod
    def parse_liste(html):
        soup = BeautifulSoup(html, "lxml")
        anzeigen = []
        for art in soup.select("article.aditem"):
            ad_id = art.get("data-adid")
            link = art.get("data-href") or (art.select_one("a[href*='/s-anzeige/']") or {}).get("href")
            titel_el = art.select_one("h2 a, a.ellipsis, .text-module-begin a")
            preis_el = art.select_one(".aditem-main--middle--price-shipping--price, .aditem-main--middle--price")
            ort_el = art.select_one(".aditem-main--top--left")
            text_el = art.select_one(".aditem-main--middle--description")
            tags = " ".join(t.get_text(" ", strip=True) for t in art.select(".simpletag, .text-module-end span"))
            if not ad_id or not titel_el:
                continue
            ort = ort_el.get_text(" ", strip=True) if ort_el else ""
            plz = (re.search(r"\b(\d{5})\b", ort) or [None, ""])[1]
            preis_text = preis_el.get_text(" ", strip=True) if preis_el else ""
            anzeigen.append({
                "id": f"ka-{ad_id}",
                "quelle": "Kleinanzeigen",
                "titel": titel_el.get_text(" ", strip=True),
                "preis": zahl(preis_text),
                "vb": "VB" in preis_text,
                "plz": plz,
                "ort": ort,
                "km": km_aus(tags),
                "baujahr": baujahr_aus(tags),
                "beschreibung": text_el.get_text(" ", strip=True) if text_el else "",
                "url": (Kleinanzeigen.BASIS + link) if link and link.startswith("/") else link,
            })
        return anzeigen

    @staticmethod
    def parse_detail(html):
        soup = BeautifulSoup(html, "lxml")
        beschreibung = soup.select_one("#viewad-description-text")
        details = {}
        for li in soup.select(".addetailslist--detail"):
            wert = li.select_one(".addetailslist--detail--value")
            if wert:
                schluessel = li.get_text(" ", strip=True).replace(wert.get_text(" ", strip=True), "").strip()
                details[schluessel.lower()] = wert.get_text(" ", strip=True)
        return {
            "beschreibung": beschreibung.get_text(" ", strip=True) if beschreibung else "",
            "km": zahl(details.get("kilometerstand")),
            "baujahr": baujahr_aus(details.get("erstzulassung", "")),
            "hu": details.get("hu bis", ""),
        }

    def suche(self, modell, preis_min, preis_max, seiten=2):
        alle = []
        for seite in range(1, seiten + 1):
            treffer = self.parse_liste(self.hole(self.such_url(modell["kleinanzeigen_suche"],
                                                               preis_min, preis_max, seite)))
            alle += treffer
            if len(treffer) < 20:
                break
        return alle

    def details(self, anzeige):
        d = self.parse_detail(self.hole(anzeige["url"]))
        anzeige["beschreibung"] = d["beschreibung"] or anzeige["beschreibung"]
        anzeige["km"] = d["km"] or anzeige["km"]
        anzeige["baujahr"] = d["baujahr"] or anzeige["baujahr"]
        if d["hu"]:
            anzeige["beschreibung"] += f" HU bis {d['hu']}"
        return anzeige


# --------------------------------------------------------------------------- #
# AutoScout24.de
# --------------------------------------------------------------------------- #
def _finde_schluessel(daten, schluessel):
    """Sucht rekursiv den ersten Wert zu einem Schlüssel in verschachteltem JSON."""
    if isinstance(daten, dict):
        if schluessel in daten:
            return daten[schluessel]
        for wert in daten.values():
            gefunden = _finde_schluessel(wert, schluessel)
            if gefunden is not None:
                return gefunden
    elif isinstance(daten, list):
        for wert in daten:
            gefunden = _finde_schluessel(wert, schluessel)
            if gefunden is not None:
                return gefunden
    return None


def _next_data(html):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    return json.loads(m.group(1)) if m else {}


class AutoScout24(Quelle):
    name = "AutoScout24"
    BASIS = "https://www.autoscout24.de"
    # Mittelpunkt NRW (Raum Hagen/Schwerte), Umkreis deckt NRW ab; danach wird per PLZ gefiltert
    PLZ_MITTE = "58239"
    UMKREIS_KM = 150

    def such_url(self, modell, preis_min, preis_max, seite=1):
        von, bis = modell["baujahre"]
        return (f"{self.BASIS}/lst/{modell['autoscout_pfad']}?atype=C&cy=D&damaged_listing=exclude"
                f"&fregfrom={von}&fregto={bis}&pricefrom={preis_min}&priceto={preis_max}"
                f"&zip={self.PLZ_MITTE}&zipr={self.UMKREIS_KM}&sort=price&desc=0&ustate=N%2CU"
                f"&page={seite}{modell.get('autoscout_extra', '')}")

    @staticmethod
    def parse_liste(html):
        daten = _next_data(html)
        listings = _finde_schluessel(daten, "listings") or []
        anzeigen = []
        for l in listings:
            tracking = l.get("tracking") or {}
            fahrzeug = l.get("vehicle") or {}
            ort = l.get("location") or {}
            preis = tracking.get("price") or (l.get("price") or {}).get("priceFormatted")
            erstzulassung = tracking.get("firstRegistration") or ""
            titel = " ".join(x for x in (fahrzeug.get("make"), fahrzeug.get("model"),
                                         fahrzeug.get("modelVersionInput")) if x)
            url = l.get("url") or ""
            anzeigen.append({
                "id": f"as-{l.get('id')}",
                "quelle": "AutoScout24",
                "titel": titel or "?",
                "preis": zahl(preis),
                "vb": False,
                "plz": str(ort.get("zip") or ""),
                "ort": f"{ort.get('zip', '')} {ort.get('city', '')}".strip(),
                "km": zahl(tracking.get("mileage") or fahrzeug.get("mileageInKm")),
                "baujahr": baujahr_aus(erstzulassung),
                "beschreibung": " ".join(str(d.get("data", "")) for d in (l.get("vehicleDetails") or [])),
                "url": (AutoScout24.BASIS + url) if url.startswith("/") else url,
            })
        return anzeigen

    @staticmethod
    def parse_detail(html):
        beschreibung = _finde_schluessel(_next_data(html), "description") or ""
        return re.sub(r"<[^>]+>", " ", str(beschreibung))

    def suche(self, modell, preis_min, preis_max, seiten=2):
        alle = []
        for seite in range(1, seiten + 1):
            treffer = self.parse_liste(self.hole(self.such_url(modell, preis_min, preis_max, seite)))
            alle += treffer
            if len(treffer) < 19:
                break
        return alle

    def details(self, anzeige):
        anzeige["beschreibung"] += " " + self.parse_detail(self.hole(anzeige["url"]))
        return anzeige


QUELLEN = {"kleinanzeigen": Kleinanzeigen, "autoscout24": AutoScout24}
