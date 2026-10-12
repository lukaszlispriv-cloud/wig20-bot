#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tv_porownaj.py — deterministyczne porównanie kursów z TradingView MCP
z kursami ze scripts/kursy.py (Yahoo → bankier → cache) i wiersz do
data/tv-log.jsonl. Rutyna NIE liczy liczb w głowie: surowe odpowiedzi
narzędzi TV zapisuje do plików w scratchpadzie sesji (NIE do repo).

Użycie (w katalogu repo):
  python3 scripts/kursy.py --json > /tmp/kursy.json
  python3 -I scripts/tv_porownaj.py --tv batch.json [screener.json] \
      [--ohlcv lpp.json pzu.json ...] --kursy /tmp/kursy.json --d0 signals.json \
      [--tylko-koszyk] [--log data/tv-log.jsonl --rutyna puls-wig20 \
       --wywolania 3 --czas-s 60 --stan OK --faza 1]

Formaty wejścia (dosłownie to, co zwracają narzędzia):
  --tv      get_symbol_data_batch: {"data": {"GPW:PKO": {"close":..}}, "missing":[...]}
            albo run_screener: {"data": {"rows": [{"symbol":"GPW:PKO","close":..}], "totalCount": N}}
  --ohlcv   get_ohlcv: {"symbol": "GPW:LPP", "bars": [{"t":..,"c":..}, ...]} — data sesji
            = data UTC znacznika t (GPW: 07:00 UTC); świeca bieżącej sesji odrzucana
            przed 17:10 Europe/Warsaw
  --kursy   wynik `kursy.py --json`: {"kursy": {"PKOBP": {"data","close","zrodlo"}}}

Wynik: tabela ZGODNOŚĆ (ticker | kursy.py (źródło) | data | TV | Δ%), listy
|Δ| > 0,1% i > 0,5%, missing, lista name ze screenera vs 20 dozwolonych,
JEDEN wiersz JSON logu (bez liczb z rachunku). Rozjazd to adnotacja, nie błąd.
"""
import argparse
import json
import os
import statistics
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

WAW = ZoneInfo("Europe/Warsaw")
KONIEC_SESJI = (17, 10)
PROG_ADNOTACJA = 0.1
PROG_ROZJAZD = 0.5
DOZWOLONE = ["ALIOR", "ALLEGRO", "BUDIMEX", "CDPROJEKT", "DINOPL", "ERSTEPL", "KETY", "KGHM",
             "KRUK", "LPP", "MBANK", "MODIVO", "PEKAO", "PEPCO", "PGE", "PKNORLEN", "PKOBP",
             "PZU", "TAURONPE", "ZABKA"]


def wczytaj(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def mapa_symboli(sciezka):
    odwr = {}
    if sciezka and os.path.exists(sciezka):
        m = wczytaj(sciezka)
        for sekcja in ("koszyk", "taktyczne", "subindeksy", "surowce_fx"):
            for t, s in (m.get(sekcja) or {}).items():
                if isinstance(s, str):
                    odwr[s] = t
        if m.get("_indeks"):
            odwr[m["_indeks"]] = "WIG20"
    return odwr


def ticker_z(sym, odwr):
    if sym in odwr:
        return odwr[sym]
    gielda_ticker = sym.split(":", 1)[-1]
    for s, t in odwr.items():
        if s.split(":", 1)[-1] == gielda_ticker:
            return t
    return gielda_ticker


def wiersze_tv(pliki, odwr):
    out, missing, nazwy = {}, [], []
    for p in pliki:
        d = wczytaj(p)
        if d.get("success") is False:
            missing.append(f"{os.path.basename(p)}: success=false ({d.get('error', 'b.d.')})")
            continue
        dane = d.get("data", d)
        if isinstance(dane, dict) and "rows" in dane:
            for r in dane["rows"]:
                sym = r.get("symbol") or f"GPW:{r.get('name')}"
                nazwy.append(r.get("name") or sym)
                out[ticker_z(sym, odwr)] = dict(r, symbol=sym)
            out.setdefault("_totalCount", dane.get("totalCount"))
        elif isinstance(dane, dict):
            for sym, r in dane.items():
                if isinstance(r, dict):
                    out[ticker_z(sym, odwr)] = dict(r, symbol=sym)
        for m in d.get("missing") or []:
            missing.append(m.get("symbol", str(m)) if isinstance(m, dict) else str(m))
        if d.get("partial"):
            missing.append(f"{os.path.basename(p)}: partial=true")
    return out, missing, nazwy


def swiece(pliki, odwr, teraz):
    out = {}
    dzis = teraz.strftime("%Y-%m-%d")
    po_sesji = (teraz.hour, teraz.minute) >= KONIEC_SESJI
    for p in pliki:
        d = wczytaj(p)
        bary = [(datetime.fromtimestamp(b["t"], tz=timezone.utc).strftime("%Y-%m-%d"), b["c"])
                for b in d.get("bars") or []]
        if bary and bary[-1][0] == dzis and not po_sesji:
            bary = bary[:-1]
        if bary:
            out[ticker_z(d.get("symbol", "?"), odwr)] = bary[-1]
    return out


def delta(a, b):
    try:
        return (float(a) / float(b) - 1) * 100
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tv", nargs="*", default=[])
    ap.add_argument("--ohlcv", nargs="*", default=[])
    ap.add_argument("--kursy")
    ap.add_argument("--d0", default="signals.json")
    ap.add_argument("--symbole", default="data/tv-symbole.json")
    ap.add_argument("--tylko-koszyk", action="store_true")
    ap.add_argument("--teraz", help="RRRR-MM-DDTHH:MM czasu Europe/Warsaw (domyślnie teraz)")
    ap.add_argument("--log")
    ap.add_argument("--rutyna", default="puls-wig20")
    ap.add_argument("--wywolania", type=int, default=0)
    ap.add_argument("--czas-s", type=int, default=0)
    ap.add_argument("--stan", default="OK", choices=("OK", "brak", "401", "429", "wyłączony", "częściowy"))
    ap.add_argument("--faza", type=int, default=1)
    ap.add_argument("--werdykt-zmieniony", default="nie", choices=("tak", "nie"))
    ap.add_argument("--backfill", default="", help="podsumowanie tv_merge.py do logu, np. 'LPP:2,PZU:1'")
    ap.add_argument("--prefix", default="mcp__TradingView__mcp-tv-")
    args = ap.parse_args()

    teraz = (datetime.strptime(args.teraz, "%Y-%m-%dT%H:%M").replace(tzinfo=WAW)
             if args.teraz else datetime.now(WAW))
    odwr = mapa_symboli(args.symbole)
    sig = wczytaj(args.d0) if args.d0 and os.path.exists(args.d0) else {}
    nogi = list(sig.get("long") or []) + list(sig.get("short") or [])
    takt = [t.get("ticker") for t in sig.get("tactical") or []]
    koszyk = set(nogi) | set(takt) | {"WIG20"}

    tv, missing, nazwy = wiersze_tv(args.tv, odwr)
    total = tv.pop("_totalCount", None)
    for t, (data, c) in swiece(args.ohlcv, odwr, teraz).items():
        tv.setdefault(t, {})
        tv[t]["close_ohlcv"], tv[t]["data_ohlcv"] = c, data
    kursy = (wczytaj(args.kursy).get("kursy") if args.kursy else {}) or {}
    tickery = sorted(set(tv) | set(kursy))
    if args.tylko_koszyk:
        tickery = [t for t in tickery if t in koszyk]

    w_sesji = (9, 0) <= (teraz.hour, teraz.minute) < KONIEC_SESJI and teraz.weekday() < 5
    print("ZGODNOŚĆ ŹRÓDEŁ (Δ% = TV / kursy.py − 1; TV = ostatnia zakończona świeca ohlcv, "
          "a gdy jej brak — close z batcha" + (" [W SESJI: close z batcha to kurs opóźniony, nie zamknięcie]" if w_sesji else "") + ")")
    print(f"{'TICKER':10} {'kursy.py':>10} {'źródło':9} {'data':11} {'TV':>10} {'Δ% TV':>8}  uwagi")
    delty, adnot, rozj = [], [], []
    for t in tickery:
        y = kursy.get(t) or {}
        r = tv.get(t) or {}
        tvc = r.get("close_ohlcv")
        uwagi = []
        if tvc is None and r.get("close") is not None:
            tvc = r["close"]
            if w_sesji:
                uwagi.append("batch w sesji — orientacyjnie, nie liczone")
        d = None
        if tvc is not None and y.get("close") and not (w_sesji and "close_ohlcv" not in r):
            d = delta(tvc, y["close"])
        if r.get("data_ohlcv") and y.get("data") and r["data_ohlcv"] != y["data"]:
            uwagi.append(f"inna data świecy: TV {r['data_ohlcv']} vs kursy.py {y['data']}")
        if d is not None:
            delty.append(abs(d))
            if abs(d) > PROG_ROZJAZD:
                rozj.append(t); uwagi.append("ROZJAZD >0,5% — bankier/Yahoo wygrywa, TV = b.d.")
            elif abs(d) > PROG_ADNOTACJA:
                adnot.append(t); uwagi.append("odnotuj (>0,1%)")
        zr = (y.get("zrodlo") or "")[:9]
        print(f"{('*' if t in koszyk else ' ')}{t:9} {str(y.get('close', 'b.d.')):>10} {zr:9} "
              f"{str(y.get('data', '')):11} {str(tvc if tvc is not None else 'b.d.'):>10} "
              f"{(f'{d:+.2f}' if d is not None else 'b.d.'):>8}  {'; '.join(uwagi)}")
    if delty:
        print(f"\nn = {len(delty)}; max |Δ| = {max(delty):.2f}%; mediana |Δ| = {statistics.median(delty):.2f}%")
    else:
        print("\nn = 0 porównań")
    print(f"|Δ| > 0,1%: {', '.join(adnot) or 'brak'}")
    print(f"|Δ| > 0,5% (ROZJAZD): {', '.join(rozj) or 'brak'}")
    print(f"missing / błędy TV: {', '.join(missing) or 'brak'}")
    brak_tv = [t for t in nogi + takt + ["WIG20"] if t not in tv]
    if brak_tv:
        print(f"bez odczytu TV: {', '.join(brak_tv)}")
    komplet = sum(1 for t in DOZWOLONE + ["WIG20"] if t in tv and t in kursy)
    print(f"komplet 21/21 z dwóch źródeł: {komplet}/21")
    if nazwy:
        mapa_tv = {ticker_z(f"GPW:{n}", odwr) for n in nazwy}
        print(f"\nSKŁAD WIG20 wg screenera: totalCount={total}, nazw={len(nazwy)}; "
              f"spoza listy 20 dozwolonych: {sorted(mapa_tv - set(DOZWOLONE)) or 'brak'}; "
              f"brak w screenerze: {sorted(set(DOZWOLONE) - mapa_tv) or 'brak'}")

    wiersz = {"data": teraz.strftime("%Y-%m-%d"), "rutyna": args.rutyna,
              "narzedzia_prefix": args.prefix, "stan": args.stan,
              "wywolania": args.wywolania, "czas_s": args.czas_s,
              "n_porownan": len(delty), "komplet_21": komplet,
              "max_delta_pct": round(max(delty), 3) if delty else None,
              "mediana_delta_pct": round(statistics.median(delty), 3) if delty else None,
              "rozjazdy_gt_0_5": rozj, "adnotacje_gt_0_1": adnot, "missing": missing,
              "backfill": args.backfill, "faza": args.faza,
              "werdykt_zmieniony": args.werdykt_zmieniony}
    print("\nWIERSZ LOGU (data/tv-log.jsonl):")
    print(json.dumps(wiersz, ensure_ascii=False))
    if args.log:
        with open(args.log, "a", encoding="utf-8") as f:
            f.write(json.dumps(wiersz, ensure_ascii=False) + "\n")
        print(f"dopisano do {args.log}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
