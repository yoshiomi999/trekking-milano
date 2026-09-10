#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
genera_trek.py
--------------
Trasforma il testo dei trek incollato da Telegram nell'array TREKS
usato da index.html, e aggiorna il file automaticamente.

USO:
    python3 genera_trek.py testo.txt
        -> legge il testo da un file e aggiorna index.html (stessa cartella)

    python3 genera_trek.py
        -> incolla il testo nel terminale, poi:
           - Mac/Linux: INVIO poi CTRL+D
           - Windows:   INVIO poi CTRL+Z e INVIO

Il testo può contenere i soliti "artefatti" dell'export Telegram
(link in formato markdown, caratteri strani, numerini dei blocchi):
lo script li ripulisce da solo. Deve solo rispettare l'ordine dei
campi che usi di solito: giorno, titolo, Organizzatore, Lunghezza,
Dislivello, Difficoltà, Pranzo, la riga "Il trek ... km da Milano",
Iscrizione, Youtube.
"""

import json
import re
import sys
import datetime
from pathlib import Path

HTML_PATH = Path(__file__).parent / "index.html"
ARCHIVIO_JSON_PATH = Path(__file__).parent / "archivio_trek.json"

MESI_IT = {
    "gen": 1, "feb": 2, "mar": 3, "apr": 4, "mag": 5, "giu": 6,
    "lug": 7, "ago": 8, "set": 9, "ott": 10, "nov": 11, "dic": 12,
}

GIORNO_RE = r"(?:Lun|Mar|Mer|Gio|Ven|Sab|Dom)\.?\s+\d{1,2}\s+\S+"

CONNETTIVI = {
    "di", "da", "del", "della", "dei", "delle", "al", "allo", "alla",
    "agli", "alle", "sul", "sulla", "sullo", "sui", "sugli", "in", "e",
    "col", "con", "per", "a", "il", "lo", "la", "i", "gli", "le",
}

BLOCCO_RE = re.compile(
    r"(?P<giorno>" + GIORNO_RE + r")\s*\n"
    r"(?P<titolo_completo>[^\n]+)\n"
    r"-\s*Organizzatore:\s*(?P<organizzatore>[^\n]+?)\s*\n"
    r"-\s*Lunghezza:\s*(?P<lunghezza>[^\n]+?)\s*\n"
    r"-\s*Dislivello:\s*(?P<dislivello>\d+)\s*m[^\n]*\n"
    r"-\s*Difficolt[àa]:\s*(?P<difficolta>[^\n]+?)\s*\n"
    r"-\s*(?P<pranzo>Pranzo[^\n]*?)\.?\s*\n"
    r"Il trek\s*(?:è\s*)?in\s*(?:prov\.\s*di\s*(?P<provincia>[^,\n]+)|(?P<altro_luogo>[^,\n]+)),\s*a\s*(?P<distanza>[\d.,]+\s*km da Milano)\.?\s*\n"
    r"Iscrizione\s*(?P<iscrizione>.+?)\s*\n"
    r"Youtube\s*(?P<youtube>https?://\S+)",
    re.IGNORECASE,
)


def title_case_it(s: str) -> str:
    parole = s.strip().lower().split()
    out = []
    for i, w in enumerate(parole):
        if i > 0 and w in CONNETTIVI:
            out.append(w)
        else:
            out.append(w[:1].upper() + w[1:] if w else w)
    return " ".join(out)


def pulisci_testo(raw: str) -> str:
    # [testo](url) -> testo   (rimuove i link markdown, tiene solo il testo visibile)
    raw = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", raw)
    # rimuove caratteri della Private Use Area (icone rotte dall'export Telegram)
    raw = "".join(
        ch for ch in raw
        if not (0xE000 <= ord(ch) <= 0xF8FF
                or 0xF0000 <= ord(ch) <= 0xFFFFD
                or 0x100000 <= ord(ch) <= 0x10FFFD)
    )
    raw = re.sub(r"\n{2,}", "\n\n", raw)
    return raw


def split_titolo_monte(line: str):
    line = line.strip()
    quota_match = re.search(r"([\d.,]+\s?m(?:\s?\([A-Za-zÀ-ù]{2,3}\))?)\s*$", line)
    quota = quota_match.group(1) if quota_match else ""
    prefisso = line[: quota_match.start()].strip() if quota_match else line

    if "." in prefisso:
        titolo_raw, monte_raw = prefisso.split(".", 1)
        monte_raw = re.sub(r"\.\s*", " · ", monte_raw)
    elif re.search(r"\bda\b", prefisso, flags=re.IGNORECASE):
        titolo_raw, dopo_da = re.split(r"\bda\b", prefisso, maxsplit=1, flags=re.IGNORECASE)
        monte_raw = "Da " + dopo_da.strip()
    else:
        titolo_raw, monte_raw = prefisso, ""

    titolo = title_case_it(titolo_raw)

    if monte_raw.lower().startswith("da "):
        monte_txt = "Da " + title_case_it(monte_raw[3:])
    else:
        monte_txt = title_case_it(monte_raw) if monte_raw else ""

    monte = " · ".join(p for p in [monte_txt, quota] if p)
    return titolo, monte


def js_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def giorno_a_data(giorno_str: str, oggi=None):
    """Converte 'Dom 30 Ago' in una data reale, per poter ordinare l'archivio."""
    oggi = oggi or datetime.date.today()
    m = re.search(r"(\d{1,2})\s+([A-Za-zà-ù]+)", giorno_str)
    if not m:
        return None
    giorno_num = int(m.group(1))
    mese_num = MESI_IT.get(m.group(2)[:3].lower())
    if not mese_num:
        return None
    try:
        data = datetime.date(oggi.year, mese_num, giorno_num)
    except ValueError:
        return None
    # se la data cade troppo nel futuro, probabilmente si riferisce all'anno scorso
    if (data - oggi).days > 250:
        data = data.replace(year=data.year - 1)
    return data


def _valore_js_a_python(val: str):
    val = val.strip().rstrip(",").strip()
    if val == "null":
        return None
    if val.startswith('"') and val.endswith('"'):
        return val[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    try:
        return int(val)
    except ValueError:
        return val


def estrai_treks_da_html(html: str):
    """Rilegge l'array TREKS già presente in un index.html, per poterlo archiviare."""
    m = re.search(r"const TREKS = \[(.*?)\];", html, re.DOTALL)
    if not m:
        return []
    blocchi = re.findall(r"\{(.*?)\}", m.group(1), re.DOTALL)
    treks = []
    for blocco in blocchi:
        obj = {}
        for riga in blocco.strip().splitlines():
            rm = re.match(r"\s*(\w+):\s*(.*)$", riga)
            if not rm:
                continue
            obj[rm.group(1)] = _valore_js_a_python(rm.group(2))
        if obj.get("titolo"):
            treks.append(obj)
    return treks


def carica_archivio():
    if ARCHIVIO_JSON_PATH.exists():
        try:
            return json.loads(ARCHIVIO_JSON_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return []
    return []


def archivia_treks_vecchi(treks_vecchi: list):
    if not treks_vecchi:
        return carica_archivio()

    archivio = carica_archivio()
    chiavi_esistenti = {
        (t.get("titolo"), t.get("organizzatore"), t.get("giorno")) for t in archivio
    }

    aggiunti = 0
    for t in treks_vecchi:
        chiave = (t.get("titolo"), t.get("organizzatore"), t.get("giorno"))
        if chiave in chiavi_esistenti:
            continue
        data = giorno_a_data(t.get("giorno", ""))
        t["data_iso"] = data.isoformat() if data else None
        archivio.append(t)
        chiavi_esistenti.add(chiave)
        aggiunti += 1

    archivio.sort(key=lambda t: t.get("data_iso") or "0000-00-00", reverse=True)
    ARCHIVIO_JSON_PATH.write_text(json.dumps(archivio, ensure_ascii=False, indent=2), encoding="utf-8")

    if aggiunti:
        print(f"🗄  Archiviati {aggiunti} trek della settimana precedente in archivio_trek.json.")
    return archivio


def parse(raw_text: str):
    testo = pulisci_testo(raw_text)
    treks = []
    for m in BLOCCO_RE.finditer(testo):
        d = m.groupdict()
        titolo, monte = split_titolo_monte(d["titolo_completo"])

        difficolta_raw = d["difficolta"].strip()
        nota_match = re.search(r"\(([^)]+)\)", difficolta_raw)
        nota = nota_match.group(1).strip() if nota_match else None
        difficolta = re.sub(r"\s*\([^)]*\)", "", difficolta_raw).strip()

        if d.get("provincia"):
            provincia_field = "Prov. di " + d["provincia"].strip()
        else:
            provincia_field = (d.get("altro_luogo") or "").strip()

        iscr_raw = d["iscrizione"].strip()
        if iscr_raw.lower().startswith("http"):
            iscrizione_url = iscr_raw
            iscrizione_testo = None
        else:
            iscrizione_url = None
            # ripulisce le freccette tipo "-->testo<--" lasciando solo il messaggio
            iscrizione_testo = re.sub(r"-+>|<-+", "", iscr_raw).strip() or "Iscrizioni chiuse"

        treks.append({
            "giorno": d["giorno"].strip(),
            "anno": datetime.date.today().year,
            "titolo": titolo,
            "monte": monte,
            "organizzatore": d["organizzatore"].strip(),
            "lunghezza": d["lunghezza"].strip(),
            "dislivello": int(d["dislivello"]),
            "difficolta": difficolta,
            "note": nota,
            "pranzo": d["pranzo"].strip().rstrip("."),
            "provincia": provincia_field,
            "distanza": d["distanza"].strip(),
            "iscrizione": iscrizione_url,
            "iscrizioneTesto": iscrizione_testo,
            "youtube": d["youtube"].strip(),
        })
    return treks


def to_js_array(treks):
    righe = ["const TREKS = ["]
    for t in treks:
        righe.append("  {")
        righe.append(f'    giorno: "{js_escape(t["giorno"])}",')
        righe.append(f'    anno: {t["anno"]},')
        righe.append(f'    titolo: "{js_escape(t["titolo"])}",')
        righe.append(f'    monte: "{js_escape(t["monte"])}",')
        righe.append(f'    organizzatore: "{js_escape(t["organizzatore"])}",')
        righe.append(f'    lunghezza: "{js_escape(t["lunghezza"])}",')
        righe.append(f'    dislivello: {t["dislivello"]},')
        righe.append(f'    difficolta: "{js_escape(t["difficolta"])}",')
        if t["note"]:
            righe.append(f'    note: "{js_escape(t["note"])}",')
        righe.append(f'    pranzo: "{js_escape(t["pranzo"])}",')
        righe.append(f'    provincia: "{js_escape(t["provincia"])}",')
        righe.append(f'    distanza: "{js_escape(t["distanza"])}",')
        if t["iscrizione"]:
            righe.append(f'    iscrizione: "{js_escape(t["iscrizione"])}",')
        else:
            righe.append('    iscrizione: null,')
            righe.append(f'    iscrizioneTesto: "{js_escape(t["iscrizioneTesto"])}",')
        righe.append(f'    youtube: "{js_escape(t["youtube"])}"')
        righe.append("  },")
    righe.append("];")
    return "\n".join(righe)


def aggiorna_html(nuovo_array_js: str, dislivelli):
    if not HTML_PATH.exists():
        print(f"⚠️  Non trovo {HTML_PATH}. Salvo solo l'array in trek_array.js")
        Path("trek_array.js").write_text(nuovo_array_js, encoding="utf-8")
        return

    html = HTML_PATH.read_text(encoding="utf-8")
    pattern = re.compile(r"const TREKS = \[.*?\];", re.DOTALL)
    if not pattern.search(html):
        print("⚠️  Non trovo l'array TREKS in index.html: salvo l'array in trek_array.js, incollalo tu a mano.")
        Path("trek_array.js").write_text(nuovo_array_js, encoding="utf-8")
        return

    treks_vecchi = estrai_treks_da_html(html)
    archivia_treks_vecchi(treks_vecchi)

    nuovo_max = max(800, ((max(dislivelli) // 100) + 1) * 100) if dislivelli else 1200

    html = pattern.sub(lambda _: nuovo_array_js, html)
    html = re.sub(r"const MAX_DISLIVELLO = \d+;", f"const MAX_DISLIVELLO = {nuovo_max};", html)

    HTML_PATH.write_text(html, encoding="utf-8")
    print(f"✅ index.html aggiornato con {len(dislivelli)} trek. MAX_DISLIVELLO impostato a {nuovo_max}.")


def main():
    if len(sys.argv) > 1:
        percorso = Path(sys.argv[1])
        if not percorso.exists():
            print(f"❌ Non trovo il file '{sys.argv[1]}' in questa cartella.\n")
            cartella = Path.cwd()
            txt_trovati = sorted(p.name for p in cartella.glob("*.txt"))
            if txt_trovati:
                print("   File .txt presenti in questa cartella:")
                for nome in txt_trovati:
                    print(f"     - {nome}")
                print(f"\n   Prova con: python3 genera_trek.py {txt_trovati[0]}")
            else:
                print(f"   In questa cartella ({cartella}) non c'è nessun file .txt.")
                print("   Controlla di aver salvato il testo dei trek qui vicino a genera_trek.py,")
                print("   e di essere nella cartella giusta nel Terminale (comando: ls per vedere cosa c'è).")
            sys.exit(1)
        raw = percorso.read_text(encoding="utf-8")
    else:
        print("Incolla il testo dei trek, poi INVIO e CTRL+D (Mac/Linux) o CTRL+Z (Windows):")
        raw = sys.stdin.read()

    treks = parse(raw)
    if not treks:
        print("❌ Nessun trek riconosciuto. Controlla che il testo segua l'ordine solito dei campi "
              "(Organizzatore, Lunghezza, Dislivello, Difficoltà, Pranzo, la riga \"Il trek... km da Milano\", "
              "Iscrizione, Youtube).")
        sys.exit(1)

    js_array = to_js_array(treks)
    print(f"\n🏔  Trovati {len(treks)} trek:\n")
    for t in treks:
        print(f"  - {t['giorno']}: {t['titolo']} ({t['organizzatore']})")
    print()

    aggiorna_html(js_array, [t["dislivello"] for t in treks])


if __name__ == "__main__":
    main()
