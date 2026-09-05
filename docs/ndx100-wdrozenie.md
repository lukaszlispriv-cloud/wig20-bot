# Wdrożenie metryk i reguł metody do rutyn NDX100 (Raport NDX100 + Puls NDX100)

Instrukcja do wklejenia w sesji Claude Code pracującej na repo rutyn NDX100. Wersja z 5.09.2026,
przeniesiona z wdrożenia w `wig20-bot` (commit 8162dc3) i dostosowana do rynku USA.
Wykonaj kroki po kolei. Nie zmieniaj nic w opublikowanych rankingach ani rozliczeniach z poprzednich tygodni.

## 0. Po co i na jakich zasadach

- Wagi kategorii rankingu (Momentum 25 / Katalizatory 20 / Makro 15 / DM 15 / Rewizje 10 / Przepływy 10 / Wycena 5)
  i przekształcenie p = 50% + 0,5·(wynik−50), obcięte do 38–62%, są zamrożone. Jeśli rutyna NDX100 używa innych wag lub
  innego obcięcia, ZOSTAW jej wartości i tylko je zapisz w `docs/metoda.md` (nie ujednolicaj z WIG20 na siłę).
- Dotychczasowe punkty były nadawane uznaniowo. To ma być powiedziane wprost w `docs/metoda.md`. Od wdrożenia
  momentum liczy skrypt, a pozostałe kategorie mają zapisane uzasadnienie i rejestr zdarzeń.
- Rankingi z poprzednich tygodni odtwarzasz do `rankings/` z opublikowanych raportów HTML BEZ zmian
  (pole `momentum_method: "uznaniowe"`). Metryki wstecz liczysz tylko wtedy, gdy masz kursy D0 i D+5 dla spółek
  z cache; brakujące oznaczasz w `data_quality`.
- Wyniki pojedynczych tygodni nie dowodzą przewagi. Cel metryk: po ≥20 tygodniach ocenić, które kategorie dodają wartość.

## 1. Rozpoznanie repo (zrób PRZED zmianami i wypisz wynik w wiadomości)

1. `signals.json`: jakie pola istnieją (version, long, short, d0.date/d0.index/d0.prices, exclude, tactical, history, epics),
   jak nazywa się indeks (NDX, ^NDX, QQQ?) i ile spółek liczy ranking (100 czy skrót).
2. Cache kursów: czy istnieje `data/kursy-cache.json` w formacie `{"kursy": {TICKER: {"RRRR-MM-DD": close}}, "aktualizacja": {...}}`
   i czy zawiera indeks. Jeśli nie ma cache, utwórz go w tym formacie ze źródła kursów, którego używa Puls, i dopisuj przy każdym biegu
   (maks. 40 sesji na ticker). Bez cache momentum mechaniczne nie działa.
3. Źródło kursów: przetestuj JEDNYM zapytaniem, co działa z tego środowiska dla tickerów USA (Yahoo chart API `query2.finance.yahoo.com/v8/finance/chart/AAPL?range=1mo&interval=1d`,
   konektor FMP `mcp__FMP__*` — `chart` bywa zablokowany planem, `quote`/`batch-quote-short` sprawdź, Stooq `stooq.com/q/d/l/?s=aapl.us&i=d`). Nie strzelaj seriami do Yahoo.
   Wynik zapisz w `CLAUDE.md` sekcja „Źródło kursów".
4. Godziny biegów rutyn (czas polski) względem sesji USA (9:30–16:00 ET = 15:30–22:00 CEST / 16:30–23:00 CET). Ostatnia ZAKOŃCZONA sesja
   dla biegu porannego w Polsce to wczorajsza sesja USA. Reakcje pre-market na wyniki po zamknięciu NIE wchodzą do zwrotów.

## 2. Pliki do dodania

### 2a. `scripts/metryki.py` — pełny kod w sekcji 7 (skopiuj 1:1)

Uruchamianie z kluczem indeksu takim, jak w cache, np. `--index NDX`:

```bash
python3 scripts/metryki.py --index NDX momentum --d0 RRRR-MM-DD          # momentum 0–25 pkt dla wszystkich tickerów w cache
python3 scripts/metryki.py --index NDX rozlicz --week 2026-Wn --d0 … --d5 …   # metryki całego rankingu
```

Jeśli klucz indeksu w cache to inny napis, podaj go w `--index`. Skrypt szuka `signals.json` w katalogu bieżącym lub nadrzędnym,
cache w `data/kursy-cache.json` (albo `--cache ŚCIEŻKA`), rankingi w `rankings/<week>.json`.

### 2b. `rankings/<week>.json` — pełny ranking tygodnia

Format (opisany też w docstringu skryptu):

```json
{"week": "2026-W4", "d0": "2026-09-04", "generated": "2026-09-05",
 "momentum_method": "mechaniczne",
 "long": ["…"], "short": ["…"],
 "ranking": [{"rank": 1, "ticker": "NVDA", "score": 70.5, "p": 0.60,
              "pts": {"momentum": 20, "katalizatory": 13, "makro": 11, "dm": 10.5, "rewizje": 7, "przeplywy": 6, "wycena": 3},
              "uzasadnienie": "jedno zdanie: skąd punkty w kategoriach uznaniowych"}],
 "katalizatory": [{"ticker": "NVDA", "data": "2026-09-10", "dn": 4, "sesja_reakcji": "2026-09-11",
                   "opis": "wyniki Q2 po sesji (AMC)", "wklad_pkt": 2, "zrodlo": "IR spółki, URL"}],
 "data_quality": []}
```

- Raport tygodniowy tworzy plik dla nowej wersji. Puls DOPISUJE do `katalizatory` i `data_quality`, nie rusza `ranking`/`long`/`short`.
- Dla bieżącego tygodnia odtwórz plik z ostatniego opublikowanego raportu HTML (rank, ticker, score, p; `pts: null`, `momentum_method: "uznaniowe"`).
  Jeśli raport nie zawiera pełnej tabeli, zapisz co jest i dodaj `BRAK_PELNEGO_RANKINGU`.

### 2c. `history` w `signals.json` — nowe pola we wpisach

`base_rate` (ȳ), `spearman`, `brier`, `data_quality` (lista kodów). Do istniejących wpisów dopisz pola z wartością `null`
i `data_quality: ["BRAK_PELNEGO_RANKINGU"]`, chyba że da się policzyć metryki wstecz (wtedy policz i wpisz).

### 2d. `docs/metoda.md` — pełny tekst w sekcji 8 (dostosuj tylko nazwy pól, jeśli repo używa innych)

### 2e. `CLAUDE.md` — dopisz na górze sekcję „Metoda i metryki" (wzór w sekcji 9)

## 3. Reguły dostosowane do rynku USA (to jest treść `docs/metoda.md`, sekcja 8; tu skrót decyzji)

| Obszar | WIG20 | NDX100 |
|---|---|---|
| Momentum | mechaniczne, rel5 2/3 + rel20 1/3 vs WIG20 | to samo vs indeks NDX (nie QQQ; QQQ tylko jako proxy z flagą `INDEKS_PROXY_QQQ`) |
| DM ±3 | rekomendacja z datą ≤30 dni | ZMIANA zalecenia (upgrade/downgrade) lub ceny docelowej o ≥10% w ostatnich 10 sesjach przez dom z listy: GS, MS, JPM, BofA, Citi, UBS, Barclays, Jefferies, Bernstein, Evercore, Wedbush, Piper Sandler, Wells Fargo, Deutsche. Samo podtrzymanie = 0. Więcej niż jedna zmiana w tę samą stronę nie sumuje się ponad ±3 |
| Katalizatory | rejestr D+1…D+10, brak = 10/20 | to samo; obowiązkowe pole `sesja_reakcji`: komunikat po 16:00 ET należy do NASTĘPNEJ sesji; wyniki BMO = ta sama sesja. Typowe zdarzenia: wyniki kwartalne (data + BMO/AMC z IR spółki), eventy produktowe, FOMC/CPI/NFP, rebalans Nasdaq-100 (kwartalny: 3. piątek III/VI/IX/XII; rekonstytucja roczna ogłaszana na pocz. XII, skuteczna po 3. piątku XII), OPEX (3. piątek), wykluczenia/włączenia do indeksu |
| Przepływy | rejestr KNF, MSCI/STOXX, skupy | short interest FINRA (publikacja co ~2 tyg., opóźniona; zmiana ≥1 p.p. free float), napływy do QQQ (tygodniowe), insider Form 4 (klastry ≥3 transakcji), ogłoszenia skupów, zmiany składu indeksów. 13F tylko jako tło (±1 maks.), bo spóźnione o kwartał |
| Makro | RPP, CIT, miedź, ropa, FX | FOMC (kalendarz federalreserve.gov), CPI/NFP z BLS (godziny w ET → przelicz), PCE/PKB z BEA, ISM, rentowność 10Y, DXY, ropa, SOX (półprzewodniki), narracja AI capex; regulacje (FTC/DoJ, cła, eksport chipów) jako wyzwalacze tez |
| Dywidendy | korekta przy dniu prawa w oknie | marginalne; sprawdzaj tylko dla spółek z DY >1,5% (np. PEP, KDP, MDLZ, CSCO, AMGN, GILD) i oznaczaj `DYWIDENDA_KOREKTA_<TICKER>` |
| Remis | mniejsza waga w WIG20 | mniejsza waga w NDX (wagi z nasdaq.com lub karty QQQ); tylko przy remisie, nie jako tilt. W NDX top-10 to ~50% indeksu, więc reguła częściej decyduje |
| Odwrócenie tezy | zdarzenie + rel5 przeciw tezie → ocena od zera | to samo; w USA dodatkowo: gap >8% na wynikach zawsze uruchamia ocenę od zera |
| Uniwersum | 20 spółek, wszystko uznaniowe | jeśli rankowane jest 100: momentum mechaniczne dla WSZYSTKICH, kategorie uznaniowe punktowane tylko dla shortlisty (20 najwyższych + 20 najniższych po momentum + katalizatorach), reszta dostaje wartości neutralne (10/7,5/7,5/5/5/2,5); metryki podawaj z jawnym `n` |
| Czas | sesja 9:00–17:00, Puls rano | sesja 15:30–22:00 CEST; ostatnia zakończona sesja dla porannego biegu = wczoraj; pre-market NIE liczy się do zwrotów |

## 4. Dopiski do promptu „Puls NDX100" (wstaw w odpowiednich krokach, oznacz [NOWE 5.09])

**KROK 0 (wczytaj stan):** „Odczytaj też `rankings/<version>.json` (pełny ranking tygodnia, rejestr katalizatorów, data_quality) — jeśli istnieje."

**KROK 1 (research):** „[NOWE 5.09] DATY MAKRO I WYNIKÓW: każdą datę potwierdzaj w datowanym źródle pierwotnym (FOMC: kalendarz federalreserve.gov;
CPI/NFP: harmonogram BLS z godziną ET; wyniki spółek: strona IR spółki z oznaczeniem BMO/AMC), nigdy z pamięci ani z rocznego harmonogramu.
Godziny przeliczaj z ET na czas polski (ET+6 h latem, +6 h zimą — sprawdź DST obu stref). Jeśli data z raportu tygodniowego jest błędna,
napisz to w raporcie i dodaj kod (np. FOMC_DATE_ERROR, EARNINGS_DATE_ERROR) do data_quality w `rankings/<version>.json`."

**KROK 2 (werdykt, reakcje):** „[NOWE 5.09] Każdy wpis exclude ma oprócz ticker/action/date/reason pola liczbowe: `price_before`
(zamknięcie sesji sprzed reakcji — od niego liczy się waga 50% lub zamknięcie), `move_from_d0_pct` (ruch od D0 w dniu reakcji, ze znakiem)
i `trigger` (jeden z: PRICE_4_8, PRICE_8, RATING_CHANGE, SHORT_INTEREST, NEWS, SHOCK, GUIDANCE_CUT, REGULATORY, TENDER, SUSPENSION).
Reakcja na wyniki opublikowane po sesji (AMC) może być wpisana dopiero po zamknięciu sesji reakcji — nie na podstawie pre-marketu."

**KROK 4 (zapis):** „[NOWE 5.09] (c) `rankings/<version>.json`: DOPISZ (nie nadpisuj) do listy `katalizatory` nowe zdarzenia z 24h dla spółek
koszykowych, taktycznych i makro — {ticker, data, dn (numer sesji od D0), sesja_reakcji, opis, wklad_pkt: null, zrodlo} — a do `data_quality`
kody z docs/metoda.md. Pól ranking/long/short/score/p NIE zmieniaj. (d) `data/kursy-cache.json` — commituj, jeśli się zmienił."

## 5. Dopiski do promptu „Raport NDX100" (tygodniowy)

**KROK 0:** „Odczytaj też `rankings/<version>.json` oraz `docs/metoda.md` (reguły punktowania i rozliczania — obowiązują)."

**KROK A2 — METRYKI CAŁEGO RANKINGU (nowy krok po rozliczeniu koszyków):** „Uruchom `python3 scripts/metryki.py --index <klucz> rozlicz --week <version> --d0 <d0.date> --d5 <data D+5>`.
Do raportu i history wpisz: bazę tygodnia ȳ (odsetek spółek bijących indeks), hit rate TOP5/BOTTOM5 OBOK oczekiwania losowego (5·ȳ, 5·(1−ȳ)),
Brier modelu wobec baseline 0,50 (ex ante) i ȳ(1−ȳ) (ex post, nazwij jawnie), Spearman opublikowanej rangi vs rangi alfy, n. Rozlicz deklaracje z poprzedniego raportu."

**KROK B (nowy ranking) — dopisz:** „REGUŁY Z docs/metoda.md: (1) MOMENTUM LICZ MECHANICZNIE: `python3 scripts/metryki.py --index <klucz> momentum --d0 <D0>`,
punkty ze skryptu bez korekt uznaniowych (flaga BRAK_20S, gdy cache nie ma 20 sesji); (2) KATALIZATORY jako rejestr zdarzeń (ticker, data, dn, sesja_reakcji, opis, wklad_pkt, zrodlo):
punkty tylko za zdarzenia D+1…D+10, brak = 10/20; wyniki AMC należą do następnej sesji; (3) DM ±3 tylko za zmianę zalecenia lub ceny docelowej ≥10% z ostatnich 10 sesji
przez dom z listy w metoda.md, ze źródłem; (4) Makro/Rewizje/Przepływy/Wycena z jednozdaniowym uzasadnieniem; (5) remis → mniejsza waga w NDX (tylko przy remisie);
(6) po twardym zdarzeniu łamiącym tezę (w tym gap >8% na wynikach) spółkę oceniasz od zera. Jeśli uniwersum to 100 spółek: momentum dla wszystkich, kategorie uznaniowe
dla shortlisty 20+20, reszta neutralnie. DATY (FOMC, BLS, BEA, wyniki spółek BMO/AMC) potwierdzaj w datowanym źródle pierwotnym z bieżącego tygodnia; konflikt = b.d. + KALENDARZ_NIEPOTWIERDZONY."

**KROK C (raport HTML) — dopisz:** „sekcja metryk rankingu (baza tygodnia, hit rate obok losowego, Brier, Spearman, n); deklaracje z warunkiem makro tylko ze zweryfikowaną datą i źródłem."

**KROK D (zapis) — dopisz:** „(c) `rankings/<nowa wersja>.json` — pełny nowy ranking w formacie z docstringa scripts/metryki.py: week, d0, generated, momentum_method="mechaniczne",
long, short, ranking[n] (rank, ticker, score, p, pts per kategoria, uzasadnienie), katalizatory[] (rejestr), data_quality[]. Rankingów z poprzednich tygodni NIE zmieniaj ex post.
Wpis history dostaje dodatkowo: base_rate, spearman, brier, data_quality. (d) `data/kursy-cache.json` — commituj razem z raportem."

**KROK E (wiadomość końcowa) — dopisz:** „hit rate'y obok bazy tygodnia, Brier, Spearman."

## 6. Weryfikacja i zapis

1. `python3 -c "import json; json.load(open('signals.json')); json.load(open('rankings/<week>.json'))"`
2. `python3 scripts/metryki.py --index <klucz> momentum --d0 <ostatnia sesja>` — ma wypisać tabelę; flagi BRAK_20S są normalne, dopóki cache nie ma 20 sesji.
3. `python3 scripts/metryki.py --index <klucz> rozlicz --week <ostatni rozliczony tydzień> --d0 … --d5 …` — jeśli brakuje kursów, wypisze BRAKI; nie zgaduj kursów.
4. Commit na `main` (zasada gałęzi jak w promptach rutyn), w wiadomości końcowej: co dodano, co policzono wstecz, czego nie dało się policzyć i dlaczego.
5. Zaktualizowane prompty obu rutyn zapisz w `docs/routine-raport-ndx100-prompt.txt` i `docs/routine-puls-ndx100-prompt.txt` — użytkownik wkleja je ręcznie w claude.ai → Routines.

## 7. `scripts/metryki.py` (skopiuj 1:1)

```python
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
    return {"week": week, "d0": d0, "d5": d5, "indeks": INDEKS, "indeks_zwrot_pct": round(rb * 100, 2),
            "n": n, "braki": braki,
            "baza_tygodnia": round(ybar, 3),
            "hit_top5": f"{hit_top}/5", "hit_top5_losowo": round(5 * ybar, 2),
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
        print(f"\nbaza tygodnia ȳ = {out['baza_tygodnia']:.2f} (spółek bijących indeks)")
        print(f"hit TOP5 {out['hit_top5']} (losowo {out['hit_top5_losowo']}), "
              f"hit BOTTOM5 {out['hit_bottom5']} (losowo {out['hit_bottom5_losowo']})")
        print(f"Brier {out['brier']:.4f} | baseline 0,50: {out['brier_stale_050']:.4f} | ex post ȳ(1−ȳ): {out['brier_expost']:.4f}")
        print(f"Spearman (ranga publ. vs ranga alfy) {out['spearman']:+.3f}; trafność kierunku 20/20: {out['trafnosc_kierunku_20']:.2f}")


if __name__ == "__main__":
    main()
```

## 8. `docs/metoda.md` dla NDX100 (skopiuj, dostosuj nazwy pól, jeśli repo używa innych)

```markdown
# Metoda rankingu NDX100 — reguły punktowania i rozliczania (od wdrożenia 2026-09)

Wagi kategorii są zamrożone: **Momentum 25 / Katalizatory 20 / Makro 15 / DM 15 / Rewizje 10 / Przepływy 10 / Wycena 5**
(jeśli rutyna używa innych — wpisz je tutaj i nie zmieniaj). p = 50% + 0,5×(wynik−50), obcięte do **38–62%**.
TOP5 = pozycje 1–5, BOTTOM5 = ostatnie 5. Dotychczasowe punkty były nadawane uznaniowo; od tego wdrożenia momentum liczy skrypt,
a pozostałe kategorie mają zapisane uzasadnienie i rejestr zdarzeń. Rankingi z poprzednich tygodni pozostają bez zmian ex post.

## 1. Momentum (0–25) — MECHANICZNE
`python3 scripts/metryki.py --index NDX momentum --d0 RRRR-MM-DD`
- rel5 = zwrot spółki z 5 sesji do D0 − zwrot indeksu; rel20 analogicznie z 20 sesji. Ranga po rel5 (2/3) i rel20 (1/3), ranga 1 → 25 pkt,
  ostatnia → 0, liniowo; rangi średnie przy remisach. Brak 20 sesji w cache → tylko rel5 + flaga `BRAK_20S`.
- Bez korekt uznaniowych. „Spółka po korekcie odbije" nie jest sygnałem momentum. Indeks odniesienia = NDX (QQQ tylko jako proxy z flagą `INDEKS_PROXY_QQQ`).

## 2. DM (0–15) — bazowo 7,5, ±3 wyłącznie za udokumentowaną ZMIANĘ
- +3/−3 za upgrade/downgrade lub zmianę ceny docelowej o ≥10% w ostatnich 10 sesjach przez: GS, MS, JPM, BofA, Citi, UBS, Barclays, Jefferies,
  Bernstein, Evercore, Wedbush, Piper Sandler, Wells Fargo, Deutsche — ze źródłem i datą. Podtrzymanie = 0. Kilka zmian w tę samą stronę nie sumuje się ponad ±3.

## 3. Katalizatory (0–20) — rejestr zdarzeń
- Każde zdarzenie w `rankings/<tydzień>.json → katalizatory`: ticker, data, `dn` (numer sesji od D0), `sesja_reakcji` (komunikat po 16:00 ET → następna sesja;
  BMO → ta sama), opis, `wklad_pkt`, zrodlo. Punkty tylko za D+1…D+10; po D+10 `wklad_pkt = 0`. W D+6…D+10 co najwyżej połowa wkładu (działa oczekiwanie, nie reakcja).
- **Brak zdarzeń = 10/20**, nie 0/20. Skala 10 + suma wkładów, obcięte do 0–20.
- Zdarzenia indeksowe: rebalans Nasdaq-100 (3. piątek III/VI/IX/XII), rekonstytucja roczna (ogłoszenie na pocz. XII, skuteczna po 3. piątku XII), OPEX (3. piątek).

## 4. Makro, Rewizje, Przepływy, Wycena — uznaniowe z jednozdaniowym uzasadnieniem
- Makro: FOMC, CPI/NFP (BLS, ET), PCE/PKB (BEA), ISM, 10Y, DXY, ropa, SOX, regulacje (FTC/DoJ, cła, eksport chipów).
- Rewizje: tylko udokumentowane zaskoczenie vs konsensus (EPS/przychody, guidance) lub zmiana konsensusu z liczbami; „pozytywne sygnały" = 5/10.
- Przepływy: short interest FINRA (zmiana ≥1 p.p. free float), napływy QQQ, insider Form 4 (klastry ≥3), skupy, zmiany indeksów; 13F tylko tło (±1). Brak danych = 5/10.
- Wycena: mnożniki vs sektor i własna historia; bez danych = 2,5/5.

## 5. Remis → wyżej spółka o mniejszej wadze w NDX (wagi z nasdaq.com/karty QQQ w dniu D0). Tylko przy remisie.

## 6. Odwrócenie tezy
Twarde zdarzenie łamiące tezę (wynik/guidance istotnie poza konsensusem, decyzja regulacyjna, wezwanie/fuzja, gap >8% na wynikach) plus rel5 przeciw tezie
→ ocena od zera, bez kotwiczenia na poprzedniej pozycji. Bez automatycznego przerzutu do przeciwnego koszyka.

## 7. Uniwersum 100 spółek
Momentum mechaniczne dla wszystkich; kategorie uznaniowe dla shortlisty (20 najwyższych + 20 najniższych po momentum + katalizatorach);
reszta neutralnie (10 / 7,5 / 7,5 / 5 / 5 / 2,5). Metryki z jawnym `n`.

## 8. Rozliczenie tygodnia — metryki całego rankingu
`python3 scripts/metryki.py --index NDX rozlicz --week 2026-Wn --d0 … --d5 …`
- alfa_i = zwrot spółki − zwrot indeksu (D0→D+5, zamknięcia; pre-market nie liczy się); y_i = 1 gdy alfa_i > 0.
- Baza tygodnia ȳ = odsetek spółek bijących indeks; hit rate TOP5/BOTTOM5 OBOK oczekiwania losowego 5·ȳ i 5·(1−ȳ).
- Brier (binarny, 0–1) wobec baseline 0,50 (ex ante) i ȳ(1−ȳ) (ex post; nazywać jawnie). Spearman: opublikowana ranga vs ranga alfy (rangi średnie).
- Wpis `history`: `base_rate`, `spearman`, `brier`, `data_quality`. Spread, managed_pp, reaction_pp, tactical_pp — bez zmian.

## 9. Kody `data_quality`
`FOMC_DATE_ERROR`, `EARNINGS_DATE_ERROR`, `KALENDARZ_NIEPOTWIERDZONY`, `OKNO_SKROCONE_Dn`, `BRAK_PELNEGO_RANKINGU`, `METRYKI_Nk_Z_n`,
`DYWIDENDA_KOREKTA_<TICKER>`, `KURS_ZRODLO_REZERWA`, `INDEKS_PROXY_QQQ`, `PREMARKET_WYKLUCZONY`.

## 10. Lista kontrolna dat (przed scoringiem i w każdym Pulsie)
1. FOMC z kalendarza federalreserve.gov; CPI/NFP z harmonogramu BLS (godzina ET); PCE/PKB z BEA; wyniki spółek ze strony IR z BMO/AMC. Nigdy z pamięci.
2. Osobno: data ogłoszenia, godzina (ET → Europe/Warsaw z uwzględnieniem DST obu stref), sesja reakcji.
3. Konflikt źródeł → b.d. + `KALENDARZ_NIEPOTWIERDZONY`; deklaracja makro nie może się na nim opierać.

## 11. Uczciwość statystyczna
Przy 5 pozycjach 95-proc. przedział Wilsona dla 2/5 to ok. 12–77%. Ocena kategorii dopiero po ≥20 tygodniach z pełnymi rankingami.
```

## 9. Wzór sekcji do `CLAUDE.md`

```markdown
## Metoda i metryki (od 2026-09)
- Reguły: `docs/metoda.md` (obowiązują obie rutyny). Wagi zamrożone; momentum MECHANICZNE ze skryptu; DM ±3 tylko za zmianę zalecenia/ceny docelowej z 10 sesji;
  katalizatory jako rejestr zdarzeń (D+1…D+10, brak = 10/20, AMC → następna sesja); remis → mniejsza waga w NDX.
- `scripts/metryki.py --index NDX momentum --d0 …` i `… rozlicz --week … --d0 … --d5 …` (baza tygodnia, hit rate obok losowego, Brier, Spearman). Wymaga `data/kursy-cache.json` z indeksem.
- `rankings/<week>.json` — pełny ranking, rejestr katalizatorów, data_quality. Raport tworzy; Puls dopisuje. Bez zmian ex post.
- `history` w `signals.json`: dodatkowo `base_rate`, `spearman`, `brier`, `data_quality`.
- Prompty rutyn: `docs/routine-raport-ndx100-prompt.txt`, `docs/routine-puls-ndx100-prompt.txt`.
```
