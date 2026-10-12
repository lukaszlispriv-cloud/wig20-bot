#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
waliduj_signals.py — ostatnia bramka PRZED commitem signals.json przez rutynę (wig20-bot).

Użycie (w katalogu repo):
  python3 -I scripts/waliduj_signals.py --diff HEAD --rutyna puls
  python3 -I scripts/waliduj_signals.py --diff HEAD --rutyna sobota
  python3 -I scripts/waliduj_signals.py --base <plik_poprzedni.json> --rutyna puls [--plik signals.json] [--bez-git]

Kod wyjścia 0 = wolno commitować; 1 = NIE commituj (uruchom FALLBACK).

Reguły:
  obie   — zestaw kluczy top-level DOKŁADNIE: _instrukcja, d0, epics, exclude,
           generated, history, last_daily, long, short, status, tactical, version;
           epics NIETKNIĘTE; tickery wyłącznie z listy 20 dozwolonych; podstawowa
           spójność (5/5, rozłączność, pola wpisów exclude/tactical, d0)
  puls   — wobec bazy zmienione tylko: status, exclude, tactical, last_daily;
           w rankings/ zmieniony co najwyżej plik bieżącej version (git)
  sobota — zmienione tylko: version, status, long, short, d0, generated,
           exclude (=[]), tactical (=[]), history (+1 wpis z polami metody);
           w rankings/ zmieniony/nowy co najwyżej plik NOWEJ version (git)
"""
import argparse
import json
import re
import subprocess
import sys

KLUCZE = {"_instrukcja", "d0", "epics", "exclude", "generated", "history",
          "last_daily", "long", "short", "status", "tactical", "version"}
DOZWOLONE_TICKERY = {"ALIOR", "ALLEGRO", "BUDIMEX", "CDPROJEKT", "DINOPL", "ERSTEPL",
                     "KETY", "KGHM", "KRUK", "LPP", "MBANK", "MODIVO", "PEKAO", "PEPCO",
                     "PGE", "PKNORLEN", "PKOBP", "PZU", "TAURONPE", "ZABKA"}
DOZWOLONE = {
    "puls": {"status", "exclude", "tactical", "last_daily"},
    "sobota": {"version", "status", "long", "short", "d0", "generated",
               "exclude", "tactical", "history"},
}
TRIGGERY = {"PRICE_4_8", "PRICE_8", "RECOMMENDATION", "KNF_SHORT", "NEWS", "SHOCK",
            "TENDER", "SUSPENSION"}
HISTORY_POLA = {"week", "long_vs_index_pp", "long_abs_pct", "spread_pp", "rozjazd_pp",
                "hit_top", "hit_bottom", "tactical_pp", "managed_pp", "reaction_pp",
                "base_rate", "spearman", "brier", "data_quality", "metoda",
                "benchmark_momentum_pp"}
DATA_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
WERSJA_RE = re.compile(r"^\d{4}-W\d{1,2}$")


def git(*args):
    out = subprocess.run(["git", *args], capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(f"git {' '.join(args)}: {out.stderr.strip()}")
    return out.stdout


def wczytaj_baze(args):
    if args.base:
        with open(args.base, encoding="utf-8") as f:
            return json.load(f)
    return json.loads(git("show", f"{args.diff}:{args.plik}"))


def spojnosc(sig, problemy):
    L, S = list(sig.get("long") or []), list(sig.get("short") or [])
    if len(L) != 5 or len(S) != 5:
        problemy.append("koszyki muszą mieć po 5 spółek")
    if set(L) & set(S):
        problemy.append("long i short się pokrywają")
    for t in L + S:
        if t not in DOZWOLONE_TICKERY:
            problemy.append(f"ticker spoza listy 20 dozwolonych: {t}")
        if t not in (sig.get("epics") or {}):
            problemy.append(f"ticker bez wpisu w epics: {t}")
    if str(sig.get("status", "")).upper()[:6] not in ("AKTUAL", "NIEAKT"):
        problemy.append(f"nieznany status: {sig.get('status')}")
    for e in sig.get("exclude") or []:
        for pole in ("ticker", "action", "date", "reason", "price_before",
                     "move_from_d0_pct", "trigger"):
            if pole not in e:
                problemy.append(f"wpis exclude bez pola {pole}: {e.get('ticker')}")
        if e.get("action") not in ("CLOSE", "REDUCE"):
            problemy.append(f"złe action w exclude: {e}")
        if e.get("trigger") not in TRIGGERY:
            problemy.append(f"nieznany trigger w exclude: {e.get('trigger')}")
        if e.get("ticker") not in L + S:
            problemy.append(f"exclude dla spółki spoza koszyków: {e.get('ticker')}")
    for t in sig.get("tactical") or []:
        if t.get("direction") not in ("BUY", "SELL"):
            problemy.append(f"zły kierunek taktycznej: {t}")
        if t.get("ticker") not in DOZWOLONE_TICKERY:
            problemy.append(f"taktyczna spoza listy 20 dozwolonych: {t.get('ticker')}")
        if not DATA_RE.match(str(t.get("entry_date", ""))):
            problemy.append(f"taktyczna bez entry_date RRRR-MM-DD: {t}")
    if len(sig.get("tactical") or []) > 2:
        problemy.append("więcej niż 2 pozycje taktyczne")
    d0 = sig.get("d0")
    if d0:
        if not DATA_RE.match(str(d0.get("date", ""))):
            problemy.append("d0.date nie jest datą RRRR-MM-DD")
        if set((d0.get("prices") or {}).keys()) != set(L + S):
            problemy.append("d0.prices nie ma dokładnie 10 nazw koszyków")
        try:
            if float(d0.get("wig20")) <= 0:
                raise ValueError
            for t, c in (d0.get("prices") or {}).items():
                if float(c) <= 0:
                    raise ValueError
        except (TypeError, ValueError):
            problemy.append("d0.wig20 / d0.prices muszą być dodatnimi liczbami")
    if not WERSJA_RE.match(str(sig.get("version", ""))):
        problemy.append(f"version nie ma formatu RRRR-Wn: {sig.get('version')}")
    for pole in ("last_daily", "generated"):
        if sig.get(pole) and not DATA_RE.match(str(sig[pole])):
            problemy.append(f"{pole} nie jest datą RRRR-MM-DD")


def porownaj(baza, sig, rutyna, problemy):
    zmienione = {k for k in KLUCZE if baza.get(k) != sig.get(k)}
    if "epics" in zmienione:
        problemy.append("epics NIETKNIĘTE — rutyny nie zmieniają mapy epiców")
    obce = zmienione - DOZWOLONE[rutyna] - {"epics"}
    for k in sorted(obce):
        problemy.append(f"pole {k} zmienione, a rutyna {rutyna} nie ma do niego prawa")
    if rutyna == "sobota":
        if sig.get("exclude") != [] or sig.get("tactical") != []:
            problemy.append("sobota zapisuje exclude=[] i tactical=[]")
        h0, h1 = baza.get("history") or [], sig.get("history") or []
        if "history" in zmienione:
            if len(h1) != len(h0) + 1 or h1[:-1] != h0:
                problemy.append("history: wolno DOPISAĆ dokładnie jeden wpis na końcu")
            else:
                brak = HISTORY_POLA - set(h1[-1].keys())
                if brak:
                    problemy.append(f"nowy wpis history bez pól: {sorted(brak)}")
                if h1[-1].get("week") != baza.get("version"):
                    problemy.append("nowy wpis history.week ≠ rozliczana version")
                if not str(h1[-1].get("metoda", "")).startswith("v1.1"):
                    problemy.append("nowy wpis history.metoda musi być v1.1 (momentum mechaniczne)")
                if not isinstance(h1[-1].get("data_quality"), list):
                    problemy.append("history.data_quality musi być listą kodów (może być pusta)")
            if len(h1) > 26:
                problemy.append("history dłuższe niż 26 wpisów")
        if "version" in zmienione and sig.get("d0") == baza.get("d0"):
            problemy.append("nowa version bez nowego d0")
        if "version" not in zmienione and "d0" in zmienione:
            problemy.append("d0 zmienione bez zmiany version")
    return zmienione


def rankings_git(baza, sig, rutyna, problemy):
    """Zmienione/nowe pliki w rankings/ (wobec HEAD) tylko dla jednej version."""
    try:
        zmien = git("diff", "--name-only", "HEAD", "--", "rankings/").split()
        nowe = git("ls-files", "--others", "--exclude-standard", "--", "rankings/").split()
    except SystemExit as e:
        problemy.append(f"nie mogę sprawdzić rankings/: {e}")
        return
    dozw = f"rankings/{sig.get('version')}.json" if rutyna == "sobota" \
        else f"rankings/{baza.get('version')}.json"
    for p in sorted(set(zmien) | set(nowe)):
        if p != dozw:
            problemy.append(f"rankings: zmieniony plik {p} — rutyna {rutyna} może dotknąć tylko {dozw}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rutyna", choices=("puls", "sobota"), required=True)
    ap.add_argument("--diff", default="HEAD")
    ap.add_argument("--base", help="plik JSON z wersją bazową zamiast rewizji gita")
    ap.add_argument("--plik", default="signals.json")
    ap.add_argument("--bez-git", action="store_true", help="pomiń kontrolę rankings/ przez git")
    args = ap.parse_args()

    with open(args.plik, encoding="utf-8") as f:
        try:
            sig = json.load(f)
        except json.JSONDecodeError as e:
            print(f"ŹLE: {args.plik} nie jest poprawnym JSON: {e}")
            return 1
    problemy = []
    klucze = set(sig.keys())
    if klucze - KLUCZE:
        problemy.append(f"OBCE klucze top-level: {sorted(klucze - KLUCZE)} (bot ich nie odrzuca — usuń)")
    if KLUCZE - klucze:
        problemy.append(f"BRAK kluczy top-level: {sorted(KLUCZE - klucze)}")
    spojnosc(sig, problemy)
    baza = wczytaj_baze(args)
    zmienione = porownaj(baza, sig, args.rutyna, problemy)
    if not args.bez_git and not args.base:
        rankings_git(baza, sig, args.rutyna, problemy)

    print(f"waliduj_signals: rutyna={args.rutyna}, baza={args.base or args.diff}, "
          f"zmienione pola: {sorted(zmienione) or 'brak'}")
    if problemy:
        print("NIE COMMITUJ — problemy:")
        for p in problemy:
            print(" -", p)
        return 1
    print("OK — wolno commitować signals.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
