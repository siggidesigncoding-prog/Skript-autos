import json
from datetime import date

import pytest

import suche
from autosuche import speicher
from autosuche.bewertung import bewerte
from autosuche.modelle import MODELLE, passt_zum_modell
from autosuche.quellen import AutoScout24, Kleinanzeigen, ist_nrw

KA_LISTE = """
<ul>
<li><article class="aditem" data-adid="111" data-href="/s-anzeige/bmw-e90-320i/111-216-1">
  <div class="aditem-main--top--left">44135 Dortmund</div>
  <h2><a class="ellipsis" href="/s-anzeige/bmw-e90-320i/111-216-1">BMW E90 320i TÜV neu</a></h2>
  <p class="aditem-main--middle--description">Fährt einwandfrei, kleine Kratzer.</p>
  <p class="aditem-main--middle--price-shipping--price">2.900 € VB</p>
  <span class="simpletag">189.000 km</span><span class="simpletag">EZ 04/2007</span>
</article></li>
<li><article class="aditem" data-adid="222" data-href="/s-anzeige/bmw-e90/222-216-1">
  <div class="aditem-main--top--left">50667 Köln</div>
  <h2><a class="ellipsis" href="/s-anzeige/bmw-e90/222-216-1">BMW E90 318d Motorschaden</a></h2>
  <p class="aditem-main--middle--price-shipping--price">900 €</p>
</article></li>
</ul>"""

KA_DETAIL = """
<ul><li class="addetailslist--detail">Kilometerstand<span class="addetailslist--detail--value">190.500 km</span></li>
<li class="addetailslist--detail">Erstzulassung<span class="addetailslist--detail--value">April 2007</span></li>
<li class="addetailslist--detail">HU bis<span class="addetailslist--detail--value">03/2028</span></li></ul>
<p id="viewad-description-text">Fährt gut, Ölverlust am Ventildeckel, sonst rostfrei.</p>"""

AS_DATEN = {"props": {"pageProps": {"listings": [
    {"id": "abc", "url": "/angebote/mercedes-e-220-abc",
     "vehicle": {"make": "Mercedes-Benz", "model": "E 220", "modelVersionInput": "CDI Avantgarde"},
     "location": {"zip": "40210", "city": "Düsseldorf"},
     "tracking": {"price": "3490", "mileage": "245000", "firstRegistration": "06-2006"},
     "vehicleDetails": [{"data": "245.000 km"}, {"data": "Diesel"}]},
    {"id": "def", "url": "/angebote/mercedes-e-def",
     "vehicle": {"make": "Mercedes-Benz", "model": "E 200"},
     "location": {"zip": "60311", "city": "Frankfurt"},
     "tracking": {"price": "2500", "mileage": "200000", "firstRegistration": "01-2005"}},
]}}}
AS_LISTE = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(AS_DATEN)}</script>'


def test_kleinanzeigen_liste():
    a = Kleinanzeigen.parse_liste(KA_LISTE)
    assert len(a) == 2
    assert a[0]["id"] == "ka-111" and a[0]["preis"] == 2900 and a[0]["vb"]
    assert a[0]["km"] == 189000 and a[0]["baujahr"] == 2007 and a[0]["plz"] == "44135"
    assert a[0]["url"].startswith("https://www.kleinanzeigen.de/s-anzeige/")


def test_kleinanzeigen_detail():
    d = Kleinanzeigen.parse_detail(KA_DETAIL)
    assert d["km"] == 190500 and d["baujahr"] == 2007 and d["hu"] == "03/2028"
    assert "Ölverlust" in d["beschreibung"]


def test_kleinanzeigen_url():
    url = Kleinanzeigen().such_url("bmw e90", 500, 5000, seite=2)
    assert url == ("https://www.kleinanzeigen.de/s-autos/nordrhein-westfalen/sortierung:preis/"
                   "preis:500:5000/seite:2/bmw-e90/k0c216l928")


def test_autoscout_liste():
    a = AutoScout24.parse_liste(AS_LISTE)
    assert a[0]["preis"] == 3490 and a[0]["km"] == 245000 and a[0]["baujahr"] == 2006
    assert a[0]["plz"] == "40210" and a[0]["url"] == "https://www.autoscout24.de/angebote/mercedes-e-220-abc"


def test_nrw_plz():
    assert ist_nrw("44135") and ist_nrw("50667") and ist_nrw("57072") and ist_nrw("32423")
    assert not ist_nrw("60311") and not ist_nrw("53474") and not ist_nrw("30159")


def test_modell_erkennung():
    assert passt_zum_modell("E90", "BMW 320d E90", baujahr=2008)
    assert not passt_zum_modell("E90", "BMW 320d Touring", baujahr=2008)
    assert not passt_zum_modell("E90", "BMW 320d F30", baujahr=2012)
    assert not passt_zum_modell("E46", "BMW 318i", baujahr=2010)
    assert passt_zum_modell("W211", "Mercedes-Benz E 220 CDI", baujahr=2006)
    assert not passt_zum_modell("W211", "Mercedes E 220 W212", baujahr=2009)
    assert not passt_zum_modell("W211", "BMW E90 320i", baujahr=2007)
    assert not passt_zum_modell("E90", "Mercedes-Benz E 220 CDI", baujahr=2006)


@pytest.mark.parametrize("text, grund", [
    ("BMW E46 Motorschaden", "Motorschaden"),
    ("springt nicht an", "nicht fahrbereit"),
    ("Für Bastler", "Bastlerfahrzeug"),
    ("Getriebe defekt", "Getriebeschaden"),
])
def test_ausschluss(text, grund):
    b = bewerte(text)
    assert not b["fahrbar"] and b["ausschluss"] == grund


def test_verneinung_und_reparatur_zaehlen_nicht():
    b = bewerte("Unfallfrei, rostfrei, kein Ölverlust, Kupplung neu, Sportfahrwerk")
    assert b["fahrbar"] and b["kosten"] == 0


def test_maengel_werden_summiert():
    b = bewerte("TÜV abgelaufen, etwas Rost, Klima defekt", heute=date(2026, 10, 1))
    assert b["fahrbar"] and b["kosten"] == 500 + 600 + 400


def test_tuev_laeuft_ab():
    assert bewerte("TÜV bis 11/2026", heute=date(2026, 10, 1))["kosten"] == 500
    assert bewerte("TÜV bis 11/2028", heute=date(2026, 10, 1))["kosten"] == 0


class FakeQuelle:
    def __init__(self, name, liste, details=None):
        self.name, self.liste, self.detail = name, liste, details or {}

    def suche(self, modell, *_):
        return [dict(a) for a in self.liste]

    def details(self, a):
        a["beschreibung"] += " " + self.detail.get(a["id"], "")
        return a


def test_suche_ende_zu_ende():
    cfg = json.loads(open(suche.HIER / "config.json").read())
    ka = FakeQuelle("Kleinanzeigen", Kleinanzeigen.parse_liste(KA_LISTE),
                    {"ka-111": "Steuerkette rasselt, Injektoren defekt"})
    as24 = FakeQuelle("AutoScout24", AutoScout24.parse_liste(AS_LISTE))
    # E90: Motorschaden fliegt raus, 2.900er hat 2.400 € Reparatur > 2.000 -> auch raus
    assert suche.suche_modell("E90", cfg, [ka]) == []
    # W211: Frankfurt fliegt raus (nicht NRW), Düsseldorf bleibt
    w211 = suche.suche_modell("W211", cfg, [as24])
    assert [a["id"] for a in w211] == ["as-abc"]
    assert w211[0]["gesamt"] == 3490


def test_favoriten(tmp_path, monkeypatch):
    monkeypatch.setattr(speicher, "ORDNER", tmp_path)
    a = {"id": "ka-1", "url": "u", "titel": "E46", "preis": 2000}
    speicher.merken(a, "anrufen")
    gesenkt = speicher.favoriten_aktualisieren([{**a, "preis": 1800}])
    assert gesenkt and gesenkt[0][1] == 2000
    f = speicher.favoriten()["ka-1"]
    assert f["notiz"] == "anrufen" and [p for _, p in f["preis_verlauf"]] == [2000, 1800]
    speicher.entfernen("ka-1")
    assert speicher.favoriten() == {}
