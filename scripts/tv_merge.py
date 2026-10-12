#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tv_merge.py — dopisuje do data/kursy-cache.json WYŁĄCZNIE brakujące sesje
z odpowiedzi get_ohlcv (TradingView MCP), po walidacji D0 i teście ex-date.

Użycie (w katalogu repo):
  python3 -I scripts/tv_merge.py --ohlcv lpp.json pzu.json ... \
      [--cache data/kursy-cache.json] [--d0 signals.json] --tylko-brakujace \
      [--teraz RRRR-MM-DDTHH:MM] [--dry-run] [--json]

Wejście: pliki z dosłowną odpowiedzią get_ohlcv ({"symbol": "GPW:LPP",
"bars": [{"t": unix s UTC, "c": close}, ...]}). Data sesji = data UTC z `t`
(GPW: 07:00 UTC). Świeca bieżącej sesji (data = dziś, przed 17:10
Europe/Warsaw) jest odrzucana.

Reguły (docs/tradingview.md §5):
1. Mapa symbol → ticker z data/tv-symbole.json; symbol spoza mapy = pomijany.
2. WALIDACJA D0: jeśli ticker ma kurs w d0.prices (WIG20: d0.wig20) i TV ma
   świecę z d0.date, |Δ| musi być ≤ 0,5% — inaczej cała seria ODRZUCONA
   (kod TV_DANE_ROZBIEZNE).
3. TEST EX-DATE / KOREKTY SERII: każda sesja obecna w cache I w TV musi
   zgadzać się ≤ 0,1%; jedna rozbieżność = seria przesunięta (korekta
   o dywidendę/split) → ODRZUCONA (TV_DANE_ROZBIEZNE), nic nie dopisujemy.
4. Dopisywane są tylko sesje, których ticker NIE ma w cache, nie starsze niż
   najstarsza sesja indeksu w cache; sesji obecnych nigdy nie nadpisujemy.
   Cache trzyma maks. 40 sesji na ticker (jak kursy.py).
5. `aktualizacja[ticker]` dostaje znacznik "RRRR-MM-DD HH:MM (TV)".

Wyjście: tabela per ticker (dopisane sesje, odrzucenia z kodem) + podsumowanie
do --backfill w tv_porownaj.py; --json = struktura maszynowa. Kod wyjścia 0,
gdy wejście dało się odczytać (odrzucenie serii to adnotacja, nie błąd).
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

WAW = ZoneInfo("Europe/Warsaw")
KONIEC_SESJI = (17, 10)
TOL_D0 = 0.005
TOL_ZGODNOSC = 0.001
MAKS_SESJI = 40


def wczytaj(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def mapa(sciezka):
    odwr = {}
    m = wczytaj(sciezka)
    for t, s in (m.get("koszyk") or {}).items():
        odwr[s] = t
    for t, s in (m.get("taktyczne") or {}).items():
        odwr[s] = t
    if m.get("_indeks"):
        odwr[m["_indeks"]] = "WIG20"
    return odwr


def bary_z_pliku(p, teraz):
    d = wczytaj(p)
    if d.get("success") is False:
        return d.get("symbol", os.path.basename(p)), None, f"success=false ({d.get('error', 'b.d.')})"
    bary = sorted((datetime.fromtimestamp(b["t"], tz=timezone.utc).strftime("%Y-%m-%d"), float(b["c"]))
                  for b in d.get("bars") or [] if b.get("c") is not None)
    dzis = teraz.strftime("%Y-%m-%d")
    if bary and bary[-1][0] == dzis and (teraz.hour, teraz.minute) < KONIEC_SESJI:
        bary = bary[:-1]
    return d.get("symbol", "?"), bary, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ohlcv", nargs="+", required=True)
    ap.add_argument("--cache", default="data/kursy-cache.json")
    ap.add_argument("--d0", default="signals.json")
    ap.add_argument("--symbole", default="data/tv-symbole.json")
    ap.add_argument("--tylko-brakujace", action="store_true",
                    help="(jedyny tryb; flaga dla czytelności w promptach)")
    ap.add_argument("--teraz", help="RRRR-MM-DDTHH:MM Europe/Warsaw")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    teraz = (datetime.strptime(args.teraz, "%Y-%m-%dT%H:%M").replace(tzinfo=WAW)
             if args.teraz else datetime.now(WAW))
    odwr = mapa(args.symbole)
    cache = wczytaj(args.cache) if os.path.exists(args.cache) else {"kursy": {}, "aktualizacja": {}}
    cache.setdefault("kursy", {}); cache.setdefault("aktualizacja", {})
    sig = wczytaj(args.d0) if args.d0 and os.path.exists(args.d0) else {}
    d0 = sig.get("d0") or {}
    d0_date, d0_prices = d0.get("date"), dict(d0.get("prices") or {})
    if d0.get("wig20"):
        d0_prices["WIG20"] = d0["wig20"]
    indeks = cache["kursy"].get("WIG20") or {}
    najstarsza = min(indeks) if indeks else None

    wyniki, zmieniono = [], False
    for p in args.ohlcv:
        sym, bary, blad = bary_z_pliku(p, teraz)
        t = odwr.get(sym)
        w = {"symbol": sym, "ticker": t, "dopisane": [], "kod": None, "uwaga": None}
        wyniki.append(w)
        if blad:
            w["kod"], w["uwaga"] = "TV_MCP_NIEDOSTEPNY", blad
            continue
        if not t:
            w["uwaga"] = "symbol spoza data/tv-symbole.json — pominięty"
            continue
        if not bary:
            w["uwaga"] = "brak zakończonych świec"
            continue
        tv = dict(bary)
        # 2. walidacja D0
        ref = d0_prices.get(t)
        if ref and d0_date and d0_date in tv:
            odch = abs(tv[d0_date] / float(ref) - 1)
            if odch > TOL_D0:
                w["kod"] = "TV_DANE_ROZBIEZNE"
                w["uwaga"] = f"D0 {d0_date}: TV {tv[d0_date]} vs d0.prices {ref} ({odch*100:.2f}% > 0,5%) — seria odrzucona"
                continue
        # 3. test ex-date / korekty serii
        istniejace = cache["kursy"].get(t) or {}
        wspolne = sorted(set(istniejace) & set(tv))
        rozb = [(d, istniejace[d], tv[d]) for d in wspolne
                if abs(tv[d] / float(istniejace[d]) - 1) > TOL_ZGODNOSC]
        if rozb:
            d, a, b = rozb[0]
            w["kod"] = "TV_DANE_ROZBIEZNE"
            w["uwaga"] = (f"{len(rozb)}/{len(wspolne)} wspólnych sesji niezgodnych (np. {d}: cache {a} vs TV {b}) "
                          f"— seria wygląda na skorygowaną o dywidendę/split, nic nie dopisano")
            continue
        # 4. tylko brakujące sesje
        brak = [d for d in sorted(tv) if d not in istniejace and (not najstarsza or d >= najstarsza)]
        if not brak:
            w["uwaga"] = f"komplet — {len(wspolne)} wspólnych sesji zgodnych, nic do dopisania"
            continue
        if not args.dry_run:
            kursy = cache["kursy"].setdefault(t, {})
            for d in brak:
                kursy[d] = tv[d]
            for d in sorted(kursy)[:-MAKS_SESJI]:
                del kursy[d]
            cache["aktualizacja"][t] = teraz.strftime("%Y-%m-%d %H:%M") + " (TV)"
            zmieniono = True
        w["dopisane"] = brak
        w["uwaga"] = f"dopisano {len(brak)} sesji ({brak[0]}…{brak[-1]}); {len(wspolne)} wspólnych zgodnych"

    if zmieniono:
        tmp = args.cache + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=1, sort_keys=True)
        os.replace(tmp, args.cache)

    podsum = ",".join(f"{w['ticker']}:{len(w['dopisane'])}" for w in wyniki if w["dopisane"])
    kody = sorted({w["kod"] for w in wyniki if w["kod"]})
    if args.json:
        print(json.dumps({"wyniki": wyniki, "backfill": podsum, "kody": kody,
                          "zapisano": zmieniono and not args.dry_run}, ensure_ascii=False, indent=1))
        return 0
    print(f"TV_MERGE — cache {args.cache}{' (dry-run)' if args.dry_run else ''}; najstarsza sesja indeksu: {najstarsza or 'b.d.'}")
    for w in wyniki:
        print(f"  {str(w['ticker'] or w['symbol']):10} {w['kod'] or 'OK':20} {w['uwaga']}")
    print(f"BACKFILL: {podsum or 'brak'}; kody data_quality: {', '.join(kody) or 'brak'}; "
          f"cache {'zapisany' if zmieniono and not args.dry_run else 'bez zmian'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
