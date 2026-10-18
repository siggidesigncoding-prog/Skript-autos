"""Erzeugt eine HTML-Übersicht der Ergebnisse (zum Öffnen im Browser)."""

import html

STIL = """
:root{--bg:#f6f6f4;--karte:#fff;--text:#1d1d1b;--grau:#6b6b66;--linie:#e3e3de;--akzent:#1f6feb;--gut:#1a7f37;--warn:#9a6700}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--karte:#21211f;--text:#ececea;--grau:#a0a09a;--linie:#33332f;--akzent:#58a6ff;--gut:#3fb950;--warn:#d29922}}
body{margin:0;background:var(--bg);color:var(--text);font:15px/1.45 system-ui,sans-serif}
main{max-width:960px;margin:0 auto;padding:16px}
h1{font-size:22px;margin:8px 0 4px}h2{font-size:18px;margin:28px 0 8px}
.klein{color:var(--grau);font-size:13px}
.auto{background:var(--karte);border:1px solid var(--linie);border-radius:10px;padding:12px 14px;margin:8px 0;display:flex;gap:12px;align-items:flex-start}
.auto .info{flex:1;min-width:0}.auto a{color:var(--akzent);text-decoration:none;font-weight:600}
.preis{font-size:18px;font-weight:700;white-space:nowrap;text-align:right}
.gut{color:var(--gut)}.warn{color:var(--warn)}
.neu{background:var(--akzent);color:#fff;border-radius:4px;padding:1px 6px;font-size:12px;margin-left:6px}
button.herz{border:0;background:none;font-size:22px;cursor:pointer;line-height:1;padding:0}
"""

SKRIPT = """
async function umschalten(knopf){
  const id=knopf.dataset.id, an=knopf.dataset.fav==='1';
  const r=await fetch(an?'/entfernen':'/merken',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})});
  if(r.ok){knopf.dataset.fav=an?'0':'1';knopf.textContent=an?'♡':'♥';}
  else alert('Merken geht nur, wenn die Seite mit "python suche.py web" geöffnet wurde.');
}
"""


def _e(x):
    return html.escape(str(x if x is not None else ""))


def _karte(a, nr, fav_ids):
    fav = a["id"] in fav_ids
    b = a.get("bewertung", {})
    gruende = ", ".join(b.get("gruende", [])) or "keine Mängel im Text"
    plus = ", ".join(b.get("plus", []))
    km = f"{a['km']:,} km".replace(",", ".") if a.get("km") else "km ?"
    bj = a.get("baujahr") or "Bj ?"
    neu = '<span class="neu">neu</span>' if a.get("neu") else ""
    return f"""
<div class="auto">
  <button class="herz" data-id="{_e(a['id'])}" data-fav="{1 if fav else 0}" onclick="umschalten(this)" title="merken">{'♥' if fav else '♡'}</button>
  <div class="info">
    <a href="{_e(a['url'])}" target="_blank" rel="noopener">{_e(nr)} {_e(a["titel"])}</a>{neu}
    <div class="klein">{_e(bj)} · {_e(km)} · {_e(a.get('ort'))} · {_e(a['quelle'])} · ID {_e(a['id'])}</div>
    <div class="warn">Reparatur geschätzt: ~{b.get('kosten', 0)} € ({_e(gruende)})</div>
    {f'<div class="gut">+ {_e(plus)}</div>' if plus else ''}
    {f'<div class="klein">Notiz: {_e(a["notiz"])}</div>' if a.get("notiz") else ''}
  </div>
  <div class="preis">{_e(a.get('preis'))} €{' VB' if a.get('vb') else ''}
    <div class="klein">gesamt ~{_e(a.get('gesamt', a.get('preis')))} €</div></div>
</div>"""


def erstelle(ergebnisse, favoriten, modelle, stand):
    fav_ids = set(favoriten)
    teile = [f"<!doctype html><html lang='de'><head><meta charset='utf-8'>"
             f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
             f"<title>Autosuche NRW</title><style>{STIL}</style><script>{SKRIPT}</script></head><body><main>",
             f"<h1>Günstige W211, E90 &amp; E46 in NRW</h1><div class='klein'>Stand: {_e(stand)} · "
             f"sortiert nach Preis + geschätzter Reparatur</div>"]
    if favoriten:
        teile.append(f"<h2>♥ Meine Favoriten ({len(favoriten)})</h2>")
        for nr, a in enumerate(favoriten.values(), 1):
            teile.append(_karte(a, f"F{nr}", fav_ids))
    nr = 0
    for key, liste in ergebnisse.items():
        teile.append(f"<h2>{_e(modelle[key]['name'])} – {len(liste)} Treffer</h2>"
                     f"<div class='klein'>Typische Schwachstellen: {_e(modelle[key]['schwachstellen'])}</div>")
        for a in liste:
            nr += 1
            teile.append(_karte(a, f"#{nr}", fav_ids))
    teile.append("</main></body></html>")
    return "\n".join(teile)
