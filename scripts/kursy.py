#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kursy.py — zamknięcia GPW dla systemu WIG20 (Yahoo chart API).

Użycie (w katalogu repo):  python3 scripts/kursy.py [--json]

Co robi:
1. Pobiera dzienne świece z query2.finance.yahoo.com (v8/finance/chart)
   dla 20 spółek WIG20 (tickery GPW z sufiksem .WA) oraz indeksu WIG20.
2. Do tabel podaje zamknięcie OSTATNIEJ ZAKOŃCZONEJ sesji: jeśli dziś
   jest dzień sesyjny, a zegar (Europe/Warsaw) nie minął 17:10, ostatnia
   świeca (dzisiejsza, niedokończona) jest odrzucana.
3. WALIDACJA D0: jeżeli w katalogu bieżącym lub nadrzędnym jest
   signals.json, porównuje zamknięcia z dnia d0.date z d0.prices
   (tolerancja 0,5%) i raportuje OK / RÓŻNICA / BRAK.
4. Symbole-kandydaci: dla spółek o niepewnym kodzie próbuje kolejno
   kilku symboli; braki wypisuje jawnie — wtedy użyj rezerwy (Stooq/PAP)
   i oznacz źródło w raporcie.
5. CACHE: każde udane pobranie dopisuje zamknięcia do data/kursy-cache.json
   (obok signals.json). Gdy Yahoo zawodzi (np. HTTP 429), skrypt sięga do
   cache i podaje kursy z ostatniego udanego pobrania, oznaczając je jako
   ŹRÓDŁO: cache (z datą aktualizacji) — dane są wtedy zwalidowane, ale
   mogą nie obejmować najnowszej sesji.

Wyjście: czytelna tabela; z flagą --json — struktura maszynowa.
"""
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

WAW = ZoneInfo("Europe/Warsaw")
KONIEC_SESJI = (17, 10)          # po tej godzinie dzisiejsza świeca = zakończona
TOLERANCJA_D0 = 0.005            # 0,5%

# Ticker systemowy -> lista symboli Yahoo do spróbowania (pierwszy trafiony wygrywa)
SYMBOLE = {
    "ALIOR":     ["ALR.WA"],
    "ALLEGRO":   ["ALE.WA"],
    "BUDIMEX":   ["BDX.WA"],
    "CDPROJEKT": ["CDR.WA"],
    "DINOPL":    ["DNP.WA"],
    "ERSTEPL":   ["EBP.WA", "SPL.WA"],
    "KETY":      ["KTY.WA"],
    "KGHM":      ["KGH.WA"],
    "KRUK":      ["KRU.WA"],
    "LPP":       ["LPP.WA"],
    "MBANK":     ["MBK.WA"],
    "MODIVO":    ["MDV.WA", "CCC.WA"],
    "PEKAO":     ["PEO.WA"],
    "PEPCO":     ["PCO.WA"],
    "PGE":       ["PGE.WA"],
    "PKNORLEN":  ["PKN.WA"],
    "PKOBP":     ["PKO.WA"],
    "PZU":       ["PZU.WA"],
    "TAURONPE":  ["TPE.WA"],
    "ZABKA":     ["ZAB.WA"],
    "WIG20":     ["WIG20.WA", "^WIG20"],
}

URL = ("https://query2.finance.yahoo.com/v8/finance/chart/{sym}"
       "?range=15d&interval=1d")
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def pobierz(sym):
    """Zwraca listę (data 'YYYY-MM-DD', close) albo [] przy braku danych."""
    req = urllib.request.Request(URL.format(sym=sym), headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            dane = json.load(r)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
            json.JSONDecodeError, OSError) as e:
        return [], f"błąd sieci/odpowiedzi: {e}"
    try:
        res = dane["chart"]["result"][0]
        ts = res["timestamp"]
        closes = res["indicators"]["quote"][0]["close"]
    except (KeyError, IndexError, TypeError):
        return [], "brak danych w odpowiedzi"
    bary = []
    for t, c in zip(ts, closes):
        if c is None:
            continue
        d = datetime.fromtimestamp(t, tz=timezone.utc).astimezone(WAW)
        bary.append((d.strftime("%Y-%m-%d"), round(float(c), 4)))
    return bary, None


def ostatnia_zakonczona(bary, teraz=None):
    """(data, close, poprz_data, poprz_close) ostatniej ZAKOŃCZONEJ sesji."""
    if not bary:
        return None
    teraz = teraz or datetime.now(WAW)
    dzis = teraz.strftime("%Y-%m-%d")
    po_sesji = (teraz.hour, teraz.minute) >= KONIEC_SESJI
    if bary[-1][0] == dzis and not po_sesji:
        bary = bary[:-1]
    if not bary:
        return None
    d, c = bary[-1]
    pd, pc = bary[-2] if len(bary) >= 2 else (None, None)
    return d, c, pd, pc


def znajdz_signals():
    for p in ("signals.json", os.path.join("..", "signals.json")):
        if os.path.exists(p):
            try:
                return json.load(open(p, encoding="utf-8")), p
            except json.JSONDecodeError:
                pass
    return None, None


# ---------- cache ostatnich udanych pobrań (data/kursy-cache.json) ----------

MAKS_SESJI_CACHE = 40   # ile ostatnich sesji trzymać na ticker


def sciezka_cache(sig_path):
    baza = os.path.dirname(os.path.abspath(sig_path)) if sig_path else os.getcwd()
    return os.path.join(baza, "data", "kursy-cache.json")


def wczytaj_cache(path):
    try:
        c = json.load(open(path, encoding="utf-8"))
        if isinstance(c.get("kursy"), dict):
            return c
    except (OSError, json.JSONDecodeError):
        pass
    return {"kursy": {}, "aktualizacja": {}}


def zapisz_cache(path, cache):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=1, sort_keys=True)
        os.replace(tmp, path)
        return True
    except OSError:
        return False


def cache_dopisz(cache, ticker, bary, teraz):
    kursy = cache["kursy"].setdefault(ticker, {})
    for d, c in bary:
        kursy[d] = c
    for d in sorted(kursy)[:-MAKS_SESJI_CACHE]:
        del kursy[d]
    cache["aktualizacja"][ticker] = teraz.strftime("%Y-%m-%d %H:%M")


def cache_odczytaj(cache, ticker):
    """Zwraca (bary posortowane po dacie, znacznik aktualizacji) albo ([], None)."""
    kursy = cache["kursy"].get(ticker) or {}
    if not kursy:
        return [], None
    bary = sorted((d, float(c)) for d, c in kursy.items())
    return bary, cache["aktualizacja"].get(ticker, "b.d.")


def main():
    tryb_json = "--json" in sys.argv
    sig, sig_path = znajdz_signals()
    d0_date = (sig or {}).get("d0", {}).get("date")
    d0_prices = (sig or {}).get("d0", {}).get("prices", {}) or {}

    teraz = datetime.now(WAW)
    cache_path = sciezka_cache(sig_path)
    cache = wczytaj_cache(cache_path)
    cache_zmieniony = False

    wynik, problemy = {}, []
    for ticker, kandydaci in SYMBOLE.items():
        bary, blad, uzyty, zrodlo = [], "nie próbowano", None, "yahoo"
        for sym in kandydaci:
            bary, blad = pobierz(sym)
            if bary:
                uzyty = sym
                break
        if bary:
            cache_dopisz(cache, ticker, bary, teraz)
            cache_zmieniony = True
        else:
            bary, akt = cache_odczytaj(cache, ticker)
            if bary:
                uzyty, zrodlo = "cache", f"cache z {akt}"
                problemy.append(f"{ticker}: Yahoo bez danych ({blad}) — użyto "
                                f"CACHE z {akt}; sprawdź, czy obejmuje "
                                f"ostatnią sesję")
            else:
                problemy.append(f"{ticker}: brak danych ({', '.join(kandydaci)}; "
                                f"{blad}) i brak wpisu w cache — użyj rezerwy "
                                f"(Stooq/PAP) i oznacz źródło")
                continue
        oz = ostatnia_zakonczona(bary)
        if not oz:
            problemy.append(f"{ticker}: brak zakończonej sesji w danych")
            continue
        d, c, pd, pc = oz
        dd = round((c / pc - 1) * 100, 2) if pc else None
        # walidacja D0
        d0_close = dict(bary).get(d0_date) if d0_date else None
        ref = d0_prices.get(ticker)
        if ticker == "WIG20" and sig:
            ref = (sig.get("d0") or {}).get("wig20")
        if ref and d0_close:
            odch = abs(d0_close / float(ref) - 1)
            d0_status = ("OK" if odch <= TOLERANCJA_D0
                         else f"RÓŻNICA {odch*100:.2f}% (Yahoo {d0_close} vs D0 {ref})")
        elif ref:
            d0_status = "BRAK świecy z D0 w Yahoo"
        else:
            d0_status = "—"
        wynik[ticker] = {"symbol": uzyty, "data": d, "close": c,
                         "poprzednia": pd, "zmiana_dd_pct": dd,
                         "walidacja_d0": d0_status, "zrodlo": zrodlo}

    if cache_zmieniony and not zapisz_cache(cache_path, cache):
        problemy.append(f"cache: nie udało się zapisać {cache_path}")

    if tryb_json:
        print(json.dumps({"wygenerowano": teraz.isoformat(timespec="minutes"),
                          "d0": d0_date, "signals": sig_path,
                          "cache": cache_path,
                          "kursy": wynik, "problemy": problemy},
                         ensure_ascii=False, indent=2))
        return

    print(f"KURSY GPW — ostatnia zakończona sesja (stan: "
          f"{teraz.strftime('%Y-%m-%d %H:%M')} CET/CEST)")
    if sig_path:
        print(f"Walidacja D0 ({d0_date}) względem {sig_path}, tolerancja "
              f"{TOLERANCJA_D0*100:.1f}%")
    print(f"{'TICKER':10} {'SYMBOL':9} {'SESJA':11} {'CLOSE':>10} "
          f"{'d/d %':>7}  WALIDACJA D0")
    for t, w in wynik.items():
        dd = f"{w['zmiana_dd_pct']:+.2f}" if w["zmiana_dd_pct"] is not None else "b.d."
        print(f"{t:10} {w['symbol']:9} {w['data']:11} {w['close']:>10} "
              f"{dd:>7}  {w['walidacja_d0']}")
    if problemy:
        print("\nPROBLEMY:")
        for p in problemy:
            print(" -", p)
    rozjazdy = [t for t, w in wynik.items()
                if w["walidacja_d0"].startswith("RÓŻNICA")]
    if rozjazdy:
        print(f"\nUWAGA: rozjazd z d0.prices dla: {', '.join(rozjazdy)} — "
              f"sprawdź symbol/split/dywidendę zanim użyjesz tych kursów.")
    z_cache = [t for t, w in wynik.items() if w["zrodlo"] != "yahoo"]
    if z_cache:
        print(f"\nŹRÓDŁO CACHE (Yahoo niedostępne): {', '.join(z_cache)} — "
              f"kursy z ostatniego udanego pobrania (data/kursy-cache.json); "
              f"upewnij się, że kolumna SESJA wskazuje właściwą sesję.")


if __name__ == "__main__":
    main()
