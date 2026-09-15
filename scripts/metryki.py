#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
metryki.py — metryki całego rankingu (WIG20, NDX100 — dowolny indeks w cache) i mechaniczne momentum.

Użycie (w katalogu repo; opcje wspólne: --index KLUCZ_INDEKSU [domyślnie WIG20,
np. NDX], --cache ŚCIEŻKA [domyślnie data/kursy-cache.json]):
  python3 scripts/metryki.py momentum --d0 2026-09-04 [--json]
      Momentum 0–25 pkt liczone MECHANICZNIE z data/kursy-cache.json:
      ranga po zwrocie relatywnym do WIG20 z 5 sesji (waga 2/3) i 20 sesji
      (waga 1/3), mapowana liniowo na punkty (ranga 1 → 25, ranga 20 → 0).
      Gdy w cache brakuje 20 sesji, składnik 20-sesyjny jest pomijany
      i wiersz dostaje flagę BRAK_20S (momentum tylko z 5 sesji).

  python3 scripts/metryki.py rozlicz --week 2026-W4 --d0 2026-09-04 --d5 2026-09-11 [--json]
      Rozliczenie pełnego rankingu z rankings/<week>.json:
      alfa = zwrot spółki − zwrot WIG20 (D0→D+5, bez korekt dywidendowych —
      ewentualne dni prawa do dywidendy oznacz ręcznie w raporcie);
      y = 1 gdy alfa > 0; baza tygodnia ȳ = odsetek spółek bijących indeks;
      hit rate TOP5/BOTTOM5 wobec oczekiwania losowego (5·ȳ, 5·(1−ȳ))
      i z 95% przedziałem Wilsona (jeśli obejmuje 50%, wynik NIE dowodzi
      przewagi); Brier (binarny, skala 0–1) wobec baseline stałego 0,50
      (ex ante) i ȳ(1−ȳ) (ex post); Spearman między opublikowaną rangą
      a rangą alfy (rangi średnie przy remisach; +1 = idealny ranking);
      BENCHMARK NAIWNEGO MOMENTUM — ten sam tydzień rozegrany koszykami
      z samego rel5 na D0, z różnicą model − momentum (jeśli różnica jest
      bliska zeru, sześć uznaniowych kategorii nie wnosi nic ponad
      „kup zeszłotygodniowych zwycięzców"); kalibracja wielkości alfy
      (prognoza z wyniku vs realizacja) jako MAE i korelacja.

Format rankings/<week>.json:
  {"week": "2026-W4", "d0": "2026-09-04", "generated": "2026-09-05",
   "momentum_method": "mechaniczne" | "uznaniowe",
   "ranking": [{"rank": 1, "ticker": "PKNORLEN", "score": 70.5, "p": 0.60,
                "pts": {"momentum": 20, "katalizatory": 13, "makro": 11,
                        "dm": 10.5, "rewizje": 7, "przeplywy": 6, "wycena": 3}
                        (albo null, gdy nieznane),
                "uzasadnienie": "..."}, ...],
   "katalizatory": [{"ticker": "PGE", "data": "2026-09-15", "dn": 7,
                     "opis": "raport H1", "wklad_pkt": 0}, ...],
   "data_quality": []}
"""
import argparse
import json
import os
import sys

WAGI = {"momentum": 25, "katalizatory": 20, "makro": 15, "dm": 15,
        "rewizje": 10, "przeplywy": 10, "wycena": 5}
P_MIN, P_MAX = 0.38, 0.62


def p_z_wyniku(score):
    """p = 50% + 0,5·(wynik−50), obcięte do 38–62% (metoda zamrożona)."""
    return round(min(P_MAX, max(P_MIN, (50 + 0.5 * (score - 50)) / 100)), 2)


INDEKS = "WIG20"            # klucz indeksu w cache; nadpisywany przez --index (np. NDX)
CACHE = os.path.join("data", "kursy-cache.json")   # nadpisywany przez --cache


def _baza():
    for b in (".", ".."):
        if os.path.exists(os.path.join(b, "signals.json")):
            return b
    return "."


def wczytaj_cache(sciezka=None):
    p = sciezka or os.path.join(_baza(), CACHE)
    cache = json.load(open(p, encoding="utf-8"))["kursy"]
    if INDEKS not in cache:
        sys.exit(f"brak indeksu {INDEKS} w {p} (użyj --index)")
    return cache


def rangi_srednie(wartosci, malejaco=True):
    """Rangi 1..n (1 = największa gdy malejaco), średnie przy remisach."""
    idx = sorted(range(len(wartosci)), key=lambda i: wartosci[i],
                 reverse=malejaco)
    rangi = [0.0] * len(wartosci)
    i = 0
    while i < len(idx):
        j = i
        while j + 1 < len(idx) and wartosci[idx[j + 1]] == wartosci[idx[i]]:
            j += 1
        r = (i + 1 + j + 1) / 2
        for k in range(i, j + 1):
            rangi[idx[k]] = r
        i = j + 1
    return rangi


def pearson(x, y):
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    return sxy / (sxx * syy) ** 0.5 if sxx and syy else 0.0


def wilson(k, n, z=1.96):
    """95% przedział Wilsona dla k trafień z n prób (ułamki 0–1).

    Przy n = 5 (jeden koszyk, jeden tydzień) przedział jest tak szeroki,
    że praktycznie zawsze obejmuje 0,5 — i o to chodzi: hit 4/5 w jednym
    tygodniu nie jest dowodem przewagi. Sensu nabiera dopiero na sumie
    tygodni (k/n liczone łącznie).
    """
    if n <= 0:
        return None, None
    ph = k / n
    d = 1 + z * z / n
    centrum = (ph + z * z / (2 * n)) / d
    polowa = z / d * ((ph * (1 - ph) / n + z * z / (4 * n * n)) ** 0.5)
    return max(0.0, centrum - polowa), min(1.0, centrum + polowa)


# Diagnostyczna mapa wynik → prognozowana alfa, przeniesiona z systemu
# równoległego (ChatGPT) przy audycie 15.09.2026. NIE jest częścią
# zamrożonej metody i NIE wpływa na koszyki: służy wyłącznie do sprawdzenia,
# czy wynik przewiduje WIELKOŚĆ alfy, a nie tylko jej znak. Nachylenie 0,08
# i obcięcie ±2,5 p.p. nie były kalibrowane na naszych danych — dopóki MAE
# nie spadnie poniżej odchylenia samej alfy, mapa jest tylko punktem odniesienia.
ALFA_NACHYLENIE = 0.08
ALFA_CLIP_PP = 2.5


def alfa_prognozowana_pp(score):
    """Prognoza alfy w p.p. z wyniku 0–100 (diagnostyka, nie sygnał)."""
    if score is None:
        return None
    return max(-ALFA_CLIP_PP, min(ALFA_CLIP_PP,
                                  ALFA_NACHYLENIE * (score - 50)))


# ---------------------------------------------------------------- momentum

def momentum(d0, cache):
    sesje = sorted(cache[INDEKS])
    if d0 not in sesje:
        sys.exit(f"brak sesji {d0} dla {INDEKS} w cache")
    i0 = sesje.index(d0)
    d5 = sesje[i0 - 5] if i0 >= 5 else None
    d20 = sesje[i0 - 20] if i0 >= 20 else None
    wig = cache[INDEKS]
    tick = sorted(t for t in cache if t != INDEKS)
    rel5, rel20, flagi = {}, {}, {}
    for t in tick:
        k = cache[t]
        if d5 and d0 in k and d5 in k:
            rel5[t] = (k[d0] / k[d5] - 1) - (wig[d0] / wig[d5] - 1)
        else:
            flagi.setdefault(t, []).append("BRAK_5S")
        if d20 and d0 in k and d20 in k:
            rel20[t] = (k[d0] / k[d20] - 1) - (wig[d0] / wig[d20] - 1)
        else:
            flagi.setdefault(t, []).append("BRAK_20S")

    def pkt(rel):
        if not rel:
            return {}
        ts = list(rel)
        r = rangi_srednie([rel[t] for t in ts])
        n = len(ts)
        return {t: 25 * (n - rr) / (n - 1) for t, rr in zip(ts, r)}

    p5, p20 = pkt(rel5), pkt(rel20)
    wynik = []
    for t in tick:
        if t in p5 and t in p20:
            m = (2 / 3) * p5[t] + (1 / 3) * p20[t]
        elif t in p5:
            m = p5[t]
        else:
            m = None
        wynik.append({"ticker": t, "rel5_pct": None if t not in rel5 else round(rel5[t] * 100, 2),
                      "rel20_pct": None if t not in rel20 else round(rel20[t] * 100, 2),
                      "momentum_pkt": None if m is None else round(m, 1),
                      "flagi": flagi.get(t, [])})
    wynik.sort(key=lambda w: (-1 if w["momentum_pkt"] is None else w["momentum_pkt"]), reverse=True)
    return {"d0": d0, "sesja_minus5": d5, "sesja_minus20": d20, "momentum": wynik}


# ------------------------------------------------- benchmark: naiwne momentum

def _rel5(d0, cache, tickery):
    """Zwrot relatywny do indeksu z 5 sesji do D0, dla podanych tickerów."""
    sesje = sorted(cache[INDEKS])
    if d0 not in sesje:
        return {}, None
    i0 = sesje.index(d0)
    if i0 < 5:
        return {}, None
    dm5 = sesje[i0 - 5]
    wig = cache[INDEKS]
    baza = wig[d0] / wig[dm5] - 1
    rel = {}
    for t in tickery:
        k = cache.get(t, {})
        if d0 in k and dm5 in k:
            rel[t] = (k[d0] / k[dm5] - 1) - baza
    return rel, dm5


def benchmark_momentum(d0, d5, cache, tickery, rb):
    """Ten sam tydzień rozegrany NAIWNYM momentum: TOP5/BOTTOM5 po rel5 na D0.

    To jedyny sposób, żeby odpowiedzieć na pytanie „czy siedem kategorii
    wnosi cokolwiek ponad kupno zeszłotygodniowych zwycięzców". Uniwersum
    jest to samo co w rankingu, żeby porównanie było 1:1.
    """
    rel, dm5 = _rel5(d0, cache, tickery)
    dost = [t for t in rel if d0 in cache[t] and d5 in cache[t]]
    if len(dost) < 10:
        return {"dostepny": False,
                "powod": (f"cache ma za mało sesji przed {d0}"
                          if dm5 is None else
                          f"tylko {len(dost)} spółek z kompletem kursów")}
    ranking = sorted(dost, key=lambda t: rel[t], reverse=True)
    top, bot = ranking[:5], ranking[-5:]

    def zwrot(kosz):
        return sum(cache[t][d5] / cache[t][d0] - 1 for t in kosz) / len(kosz) * 100

    rt, rbm = zwrot(top), zwrot(bot)
    return {"dostepny": True, "sesja_minus5": dm5, "n_uniwersum": len(dost),
            "top5": top, "bottom5": bot,
            "long_pct": round(rt, 2), "short_pct": round(rbm, 2),
            "long_vs_indeks_pp": round(rt - rb * 100, 2),
            "short_vs_indeks_pp": round(rb * 100 - rbm, 2),
            "spread_pp": round(rt - rbm, 2)}


# ---------------------------------------------------------------- rozlicz

def rozlicz(week, d0, d5, cache):
    p = os.path.join(_baza(), "rankings", f"{week}.json")
    rk = json.load(open(p, encoding="utf-8"))
    wig = cache[INDEKS]
    if d0 not in wig or d5 not in wig:
        sys.exit(f"brak {INDEKS} dla {d0}/{d5} w cache")
    rb = wig[d5] / wig[d0] - 1
    wiersze, braki = [], []
    for w in rk["ranking"]:
        t = w["ticker"]
        k = cache.get(t, {})
        if d0 not in k or d5 not in k:
            braki.append(t)
            continue
        r = k[d5] / k[d0] - 1
        alfa = r - rb
        prog = alfa_prognozowana_pp(w.get("score"))
        wiersze.append({"rank": w["rank"], "ticker": t, "p": w["p"],
                        "score": w.get("score"),
                        "alfa_prog_pp": None if prog is None else round(prog, 2),
                        "d0": k[d0], "d5": k[d5], "zwrot_pct": round(r * 100, 2),
                        "alfa_pp": round(alfa * 100, 2), "y": 1 if alfa > 0 else 0})
    n = len(wiersze)
    if n < 2:
        sys.exit(f"za mało danych ({n}); braki: {braki}")
    ybar = sum(w["y"] for w in wiersze) / n
    brier = sum((w["p"] - w["y"]) ** 2 for w in wiersze) / n
    brier_05 = sum((0.5 - w["y"]) ** 2 for w in wiersze) / n
    brier_expost = ybar * (1 - ybar)
    r_pub = [float(w["rank"]) for w in wiersze]
    r_alfa = rangi_srednie([w["alfa_pp"] for w in wiersze])
    rho = pearson([-x for x in r_pub], [-x for x in r_alfa])
    top = sorted(wiersze, key=lambda w: w["rank"])[:5]
    bot = sorted(wiersze, key=lambda w: -w["rank"])[:5]
    hit_top = sum(w["y"] for w in top)
    hit_bot = sum(1 - w["y"] for w in bot)
    kier = sum(1 for w in wiersze if (w["p"] > 0.5) == (w["y"] == 1) or (w["p"] == 0.5)) / n
    wt_lo, wt_hi = wilson(hit_top, len(top))
    wb_lo, wb_hi = wilson(hit_bot, len(bot))

    # --- kalibracja WIELKOŚCI alfy (diagnostyka, patrz alfa_prognozowana_pp) --
    par = [(w["alfa_prog_pp"], w["alfa_pp"]) for w in wiersze
           if w["alfa_prog_pp"] is not None]
    kal = {"n": len(par)}
    if len(par) >= 3:
        kal["mae_pp"] = round(sum(abs(a - b) for a, b in par) / len(par), 2)
        # odchylenie samej alfy od zera — prognoza musi je pobić, żeby cokolwiek wnosić
        kal["mae_prognozy_zerowej_pp"] = round(
            sum(abs(b) for _, b in par) / len(par), 2)
        kal["korelacja"] = round(pearson([a for a, _ in par],
                                         [b for _, b in par]), 3)

    # --- KOSZYKI: spread papierowy vs to, co realnie gra rachunek ---------
    # Bot z HEDGE_MODE=index NIE handluje koszyka SHORT — kupuje 5 longów
    # i sprzedaje indeks. Jego wynik brutto to (LONG − indeks), a nie
    # (LONG − SHORT). Rozjazd tych dwóch liczb był powodem, dla którego
    # raport pokazywał +1,32 p.p. za W3, a rachunek tracił.
    zwroty = {w["ticker"]: w["zwrot_pct"] for w in wiersze}

    def _srednia(kosz):
        v = [zwroty[t] for t in kosz if t in zwroty]
        return (sum(v) / len(v), len(v)) if v else (None, 0)

    kosz = {}
    dl, n_dl = _srednia(rk.get("long", []))
    kr, n_kr = _srednia(rk.get("short", []))
    if dl is not None:
        # long_abs_pct = wariant BEZ hedge'u. Rachunek nie może shortować
        # akcji (Capital.com blokuje SELL na CFD na akcje), więc jedyną
        # otwartą decyzją konstrukcyjną jest hedgować albo nie — obie
        # liczby muszą lecieć obok siebie do history.
        kosz["long_abs_pct"] = round(dl, 2)
        kosz["long_pct"] = round(dl, 2)
        kosz["long_n"] = n_dl
        kosz["long_vs_indeks_pp"] = round(dl - rb * 100, 2)
    if kr is not None:
        kosz["short_pct"] = round(kr, 2)
        kosz["short_n"] = n_kr
        kosz["short_vs_indeks_pp"] = round(rb * 100 - kr, 2)
    if dl is not None and kr is not None:
        kosz["spread_papierowy_pp"] = round(dl - kr, 2)
        kosz["rozjazd_pp"] = round((dl - kr) - (dl - rb * 100), 2)

    # --- BENCHMARK: ten sam tydzień rozegrany naiwnym momentum ------------
    bench = benchmark_momentum(d0, d5, cache, [w["ticker"] for w in wiersze], rb)
    if bench.get("dostepny"):
        if "spread_papierowy_pp" in kosz:
            bench["przewaga_spread_pp"] = round(
                kosz["spread_papierowy_pp"] - bench["spread_pp"], 2)
        if "long_vs_indeks_pp" in kosz:
            bench["przewaga_long_vs_indeks_pp"] = round(
                kosz["long_vs_indeks_pp"] - bench["long_vs_indeks_pp"], 2)

    return {"week": week, "d0": d0, "d5": d5, "indeks": INDEKS, "indeks_zwrot_pct": round(rb * 100, 2),
            "n": n, "braki": braki, "koszyki": kosz,
            "metoda": rk.get("momentum_method"),
            "benchmark_momentum": bench, "kalibracja_alfy": kal,
            "baza_tygodnia": round(ybar, 3),
            "hit_top5": f"{hit_top}/5", "hit_top5_losowo": round(5 * ybar, 2),
            "hit_top5_wilson": [round(wt_lo, 3), round(wt_hi, 3)],
            "hit_bottom5_wilson": [round(wb_lo, 3), round(wb_hi, 3)],
            "hit_bottom5": f"{hit_bot}/5", "hit_bottom5_losowo": round(5 * (1 - ybar), 2),
            "brier": round(brier, 4), "brier_stale_050": round(brier_05, 4),
            "brier_expost": round(brier_expost, 4),
            "spearman": round(rho, 3), "trafnosc_kierunku_20": round(kier, 2),
            "wiersze": wiersze}


def main():
    global INDEKS
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default=INDEKS, help="klucz indeksu w cache (WIG20, NDX, ...)")
    ap.add_argument("--cache", default=None, help="ścieżka do kursy-cache.json (domyślnie data/kursy-cache.json)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("momentum"); m.add_argument("--d0", required=True); m.add_argument("--json", action="store_true")
    r = sub.add_parser("rozlicz"); r.add_argument("--week", required=True); r.add_argument("--d0", required=True)
    r.add_argument("--d5", required=True); r.add_argument("--json", action="store_true")
    a = ap.parse_args()
    INDEKS = a.index
    cache = wczytaj_cache(a.cache)
    if a.cmd == "momentum":
        out = momentum(a.d0, cache)
        if a.json:
            print(json.dumps(out, ensure_ascii=False, indent=1)); return
        print(f"MOMENTUM mechaniczne, D0 {out['d0']} (−5 sesji: {out['sesja_minus5']}, −20 sesji: {out['sesja_minus20']})")
        print(f"{'TICKER':10} {'rel5%':>7} {'rel20%':>7} {'PKT':>5}  FLAGI")
        for w in out["momentum"]:
            f = lambda v: "b.d." if v is None else f"{v:+.2f}"
            print(f"{w['ticker']:10} {f(w['rel5_pct']):>7} {f(w['rel20_pct']):>7} "
                  f"{('b.d.' if w['momentum_pkt'] is None else w['momentum_pkt']):>5}  {' '.join(w['flagi'])}")
    else:
        out = rozlicz(a.week, a.d0, a.d5, cache)
        if a.json:
            print(json.dumps(out, ensure_ascii=False, indent=1)); return
        print(f"ROZLICZENIE {out['week']} ({out['d0']} → {out['d5']}), {out['indeks']} {out['indeks_zwrot_pct']:+.2f}%, n={out['n']}"
              + (f", BRAKI: {', '.join(out['braki'])}" if out["braki"] else ""))
        print(f"{'#':>2} {'TICKER':10} {'p':>5} {'D0':>9} {'D+5':>9} {'zwrot%':>8} {'alfa pp':>8} y")
        for w in sorted(out["wiersze"], key=lambda w: w["rank"]):
            print(f"{w['rank']:>2} {w['ticker']:10} {w['p']:>5.2f} {w['d0']:>9} {w['d5']:>9} "
                  f"{w['zwrot_pct']:>+8.2f} {w['alfa_pp']:>+8.2f} {w['y']}")
        print(f"\nbaza tygodnia ȳ = {out['baza_tygodnia']:.2f} (spółek bijących indeks)"
              + (f"; metoda momentum: {out['metoda']}" if out.get("metoda") else ""))
        wt, wb = out["hit_top5_wilson"], out["hit_bottom5_wilson"]
        print(f"hit TOP5 {out['hit_top5']} (losowo {out['hit_top5_losowo']}; "
              f"Wilson 95% {wt[0]:.0%}–{wt[1]:.0%}), "
              f"hit BOTTOM5 {out['hit_bottom5']} (losowo {out['hit_bottom5_losowo']}; "
              f"Wilson 95% {wb[0]:.0%}–{wb[1]:.0%})")
        print("  (przedział obejmujący 50% = wynik NIE dowodzi przewagi; "
              "przy n=5 obejmuje prawie zawsze)")
        print(f"Brier {out['brier']:.4f} | baseline 0,50: {out['brier_stale_050']:.4f} | ex post ȳ(1−ȳ): {out['brier_expost']:.4f}")
        print(f"Spearman (ranga publ. vs ranga alfy) {out['spearman']:+.3f}; trafność kierunku 20/20: {out['trafnosc_kierunku_20']:.2f}")
        k = out.get("koszyki") or {}
        if k:
            print("\nKOSZYKI")
            if "long_pct" in k:
                print(f"  LONG  ({k['long_n']} spółek) bez hedge'u {k['long_abs_pct']:+.2f}%   "
                      f"(wariant HEDGE_RATIO=0)")
                print(f"  LONG − indeks {k['long_vs_indeks_pp']:+.2f} p.p."
                      f"   <-- WYNIK RACHUNKU (stan obecny, HEDGE_RATIO=1.0)")
            if "short_pct" in k:
                print(f"  SHORT ({k['short_n']} spółek) {k['short_pct']:+.2f}%  "
                      f"vs indeks {k['short_vs_indeks_pp']:+.2f} p.p.   "
                      f"(NIEOSIĄGALNE — rachunek nie shortuje akcji)")
            if "spread_papierowy_pp" in k:
                print(f"  spread papierowy LONG−SHORT: {k['spread_papierowy_pp']:+.2f} p.p. "
                      f"(miara selekcji, nie wynik)")
                print(f"  ROZJAZD papier − rachunek:   {k['rozjazd_pp']:+.2f} p.p.")

        b = out.get("benchmark_momentum") or {}
        print("\nBENCHMARK — ten sam tydzień naiwnym momentum (TOP5/BOTTOM5 po rel5 na D0)")
        if not b.get("dostepny"):
            print(f"  niedostępny: {b.get('powod', 'brak danych')}")
        else:
            print(f"  koszyk momentum LONG:  {', '.join(b['top5'])}")
            print(f"  koszyk momentum SHORT: {', '.join(b['bottom5'])}")
            print(f"  momentum: LONG − indeks {b['long_vs_indeks_pp']:+.2f} p.p., "
                  f"spread {b['spread_pp']:+.2f} p.p. (uniwersum {b['n_uniwersum']})")
            if "przewaga_long_vs_indeks_pp" in b:
                print(f"  PRZEWAGA MODELU NAD MOMENTUM: "
                      f"{b['przewaga_long_vs_indeks_pp']:+.2f} p.p. na wyniku rachunku"
                      + (f", {b['przewaga_spread_pp']:+.2f} p.p. na spreadzie"
                         if "przewaga_spread_pp" in b else ""))
                print("  (blisko zera = sześć uznaniowych kategorii nie wnosi nic "
                      "ponad kupno zeszłotygodniowych zwycięzców)")

        kal = out.get("kalibracja_alfy") or {}
        if "mae_pp" in kal:
            print(f"\nKALIBRACJA WIELKOŚCI ALFY (diagnostyka, mapa spoza zamrożonej metody)")
            print(f"  MAE prognozy {kal['mae_pp']:.2f} p.p. vs MAE prognozy zerowej "
                  f"{kal['mae_prognozy_zerowej_pp']:.2f} p.p.; korelacja {kal['korelacja']:+.3f}")
            if kal["mae_pp"] >= kal["mae_prognozy_zerowej_pp"]:
                print("  MAE nie bije prognozy zerowej — wynik przewiduje najwyżej znak, nie wielkość")


if __name__ == "__main__":
    main()
