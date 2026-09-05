#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
metryki.py — metryki całego rankingu WIG20 i mechaniczne momentum.

Użycie (w katalogu repo):
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
      hit rate TOP5/BOTTOM5 wobec oczekiwania losowego (5·ȳ, 5·(1−ȳ));
      Brier (binarny, skala 0–1) wobec baseline stałego 0,50 (ex ante)
      i ȳ(1−ȳ) (ex post); Spearman między opublikowaną rangą a rangą alfy
      (rangi średnie przy remisach; +1 = idealny ranking).

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


def _baza():
    for b in (".", ".."):
        if os.path.exists(os.path.join(b, "signals.json")):
            return b
    return "."


def wczytaj_cache():
    p = os.path.join(_baza(), "data", "kursy-cache.json")
    return json.load(open(p, encoding="utf-8"))["kursy"]


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


# ---------------------------------------------------------------- momentum

def momentum(d0, cache):
    sesje = sorted(cache["WIG20"])
    if d0 not in sesje:
        sys.exit(f"brak sesji {d0} dla WIG20 w cache")
    i0 = sesje.index(d0)
    d5 = sesje[i0 - 5] if i0 >= 5 else None
    d20 = sesje[i0 - 20] if i0 >= 20 else None
    wig = cache["WIG20"]
    tick = sorted(t for t in cache if t != "WIG20")
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


# ---------------------------------------------------------------- rozlicz

def rozlicz(week, d0, d5, cache):
    p = os.path.join(_baza(), "rankings", f"{week}.json")
    rk = json.load(open(p, encoding="utf-8"))
    wig = cache["WIG20"]
    if d0 not in wig or d5 not in wig:
        sys.exit(f"brak WIG20 dla {d0}/{d5} w cache")
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
        wiersze.append({"rank": w["rank"], "ticker": t, "p": w["p"],
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
    return {"week": week, "d0": d0, "d5": d5, "wig20_zwrot_pct": round(rb * 100, 2),
            "n": n, "braki": braki,
            "baza_tygodnia": round(ybar, 3),
            "hit_top5": f"{hit_top}/5", "hit_top5_losowo": round(5 * ybar, 2),
            "hit_bottom5": f"{hit_bot}/5", "hit_bottom5_losowo": round(5 * (1 - ybar), 2),
            "brier": round(brier, 4), "brier_stale_050": round(brier_05, 4),
            "brier_expost": round(brier_expost, 4),
            "spearman": round(rho, 3), "trafnosc_kierunku_20": round(kier, 2),
            "wiersze": wiersze}


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("momentum"); m.add_argument("--d0", required=True); m.add_argument("--json", action="store_true")
    r = sub.add_parser("rozlicz"); r.add_argument("--week", required=True); r.add_argument("--d0", required=True)
    r.add_argument("--d5", required=True); r.add_argument("--json", action="store_true")
    a = ap.parse_args()
    cache = wczytaj_cache()
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
        print(f"ROZLICZENIE {out['week']} ({out['d0']} → {out['d5']}), WIG20 {out['wig20_zwrot_pct']:+.2f}%, n={out['n']}"
              + (f", BRAKI: {', '.join(out['braki'])}" if out["braki"] else ""))
        print(f"{'#':>2} {'TICKER':10} {'p':>5} {'D0':>9} {'D+5':>9} {'zwrot%':>8} {'alfa pp':>8} y")
        for w in sorted(out["wiersze"], key=lambda w: w["rank"]):
            print(f"{w['rank']:>2} {w['ticker']:10} {w['p']:>5.2f} {w['d0']:>9} {w['d5']:>9} "
                  f"{w['zwrot_pct']:>+8.2f} {w['alfa_pp']:>+8.2f} {w['y']}")
        print(f"\nbaza tygodnia ȳ = {out['baza_tygodnia']:.2f} (spółek bijących indeks)")
        print(f"hit TOP5 {out['hit_top5']} (losowo {out['hit_top5_losowo']}), "
              f"hit BOTTOM5 {out['hit_bottom5']} (losowo {out['hit_bottom5_losowo']})")
        print(f"Brier {out['brier']:.4f} | baseline 0,50: {out['brier_stale_050']:.4f} | ex post ȳ(1−ȳ): {out['brier_expost']:.4f}")
        print(f"Spearman (ranga publ. vs ranga alfy) {out['spearman']:+.3f}; trafność kierunku 20/20: {out['trafnosc_kierunku_20']:.2f}")


if __name__ == "__main__":
    main()
