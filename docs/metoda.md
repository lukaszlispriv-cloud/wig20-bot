# Metoda rankingu WIG20 — reguły punktowania i rozliczania (od 2026-W5)

Wagi kategorii są zamrożone: **Momentum 25 / Katalizatory 20 / Makro 15 / DM 15 / Rewizje 10 / Przepływy 10 / Wycena 5**.
p = 50% + 0,5×(wynik−50), obcięte do **38–62%**. TOP5 = pozycje 1–5, BOTTOM5 = pozycje 16–20.
Ten dokument doprecyzowuje, **jak** nadawane są punkty, tak żeby jak najwięcej dało się odtworzyć z danych.
Zmiany wprowadzono 5.09.2026 po audycie porównawczym z równoległym systemem (ChatGPT); rankingi W2–W4 pozostają
opublikowane bez zmian ex post (pole `momentum_method: "uznaniowe"` w `rankings/`).

## 1. Momentum (0–25) — MECHANICZNE

`python3 scripts/metryki.py momentum --d0 RRRR-MM-DD`

- rel5 = zwrot spółki z 5 sesji do D0 − zwrot WIG20 z tych samych sesji; rel20 analogicznie z 20 sesji.
- Ranga po rel5 (waga 2/3) i po rel20 (waga 1/3); ranga 1 → 25 pkt, ranga 20 → 0 pkt, liniowo; rangi średnie przy remisach.
- Brak 20 sesji w cache → tylko rel5 i flaga `BRAK_20S` w rankingu (cache buduje się od 21.08.2026, komplet 20 sesji ok. 18.09).
- Punktów momentum NIE koryguje się uznaniowo. Argument „spółka po korekcie odbije" nie jest sygnałem momentum.

## 2. DM / portfele (0–15) — bazowo 7,5, ±3 za udokumentowane sygnały

- +3 / −3 wyłącznie za rekomendację lub wpis na listę portfelową domu maklerskiego **z datą w ostatnich 30 dniach**, ze źródłem.
- Starsze rekomendacje = 7,5 (neutralnie). Maksymalny zakres 4,5–10,5.

## 3. Katalizatory (0–20) — rejestr zdarzeń

- Każde zdarzenie trafia do `rankings/<tydzień>.json → katalizatory` z polami: ticker, data, `dn` (numer sesji od D0), opis, `wklad_pkt`.
- Punkty tylko za zdarzenia w oknie **D+1…D+10**. Zdarzenie po D+10 ma `wklad_pkt = 0`.
- Zdarzenie w oknie wyniku (D+1…D+5) może dostać pełny wkład; w D+6…D+10 co najwyżej połowę (działa tylko oczekiwanie, nie reakcja).
- **Brak zdarzeń = 10/20 (neutralnie)**, nie 0/20. Skala symetryczna: 10 + suma wkładów, obcięte do 0–20.
- Wynik już opublikowany (np. szacunki przed pełnym raportem) liczy się jako zdarzenie „znane", pełny raport wtedy `wklad_pkt` ≤ 1.

## 4. Makro, Rewizje, Przepływy, Wycena — uznaniowe z uzasadnieniem

Każda spółka ma w `rankings/<tydzień>.json` jednozdaniowe `uzasadnienie` punktów. Rewizje: tylko udokumentowana zmiana
konsensusu lub zaskoczenie wynikowe z liczbami (vs konsensus PAP), nie „pozytywne sygnały". Przepływy: rejestr KNF
(zmiany ≥0,1 p.p.), zmiany indeksów (MSCI, STOXX, cap GPW), skupy akcji; przy braku danych 5/10.

## 5. Rozstrzyganie remisów

Przy równym wyniku wyżej spółka o **mniejszej wadze w WIG20** (wagi z profilu WIG20 na bankier.pl w dniu D0). Reguła działa tylko
przy remisie, nie jako tilt punktowy.

## 6. Odwrócenie tezy

Twarde zdarzenie łamiące tezę (wynik istotnie poniżej/powyżej konsensusu, zmiana regulacyjna, wezwanie) **plus** momentum przeciw
tezie (rel5 przeciwnego znaku) → spółka jest oceniana od zera w nowym rankingu, bez „kotwiczenia" na poprzedniej pozycji.
Nie ma automatycznego przerzutu do przeciwnego koszyka; ma być tylko brak kotwicy.

## 7. Rozliczenie tygodnia — metryki całego rankingu

`python3 scripts/metryki.py rozlicz --week 2026-Wn --d0 … --d5 …`

- alfa_i = zwrot spółki − zwrot WIG20 (D0→D+5); y_i = 1 gdy alfa_i > 0. Korekta dywidendowa: dzień prawa do dywidendy w oknie →
  do kursu D+5 dodaje się dywidendę (ręcznie, z adnotacją w raporcie i `data_quality`).
- **Baza tygodnia ȳ** = odsetek spółek bijących indeks. Hit rate TOP5/BOTTOM5 podaje się **obok** oczekiwania losowego 5·ȳ i 5·(1−ȳ).
- **Brier** (binarny, 0–1) modelu wobec dwóch baseline'ów: stałe 0,50 (ex ante) i ȳ(1−ȳ) (ex post; nazywać go tak jawnie).
- **Spearman** między opublikowaną rangą (1 = najlepsza) a rangą alfy (rangi średnie). +1 = ranking idealny.
- Wpis `history` w `signals.json` dostaje pola: `base_rate`, `spearman`, `brier`, `data_quality` (lista kodów).
- Spread, managed_pp, reaction_pp, tactical_pp — bez zmian (definicje w promptach rutyn).

## 8. Kody `data_quality`

`RPP_DATE_ERROR` (błędna data posiedzenia), `OKNO_SKROCONE_Dn`, `BRAK_PELNEGO_RANKINGU`, `METRYKI_Nk_Z_20` (metryki z k spółek),
`DYWIDENDA_KOREKTA_<TICKER>`, `KURS_ZRODLO_REZERWA` (kurs D0/D+5 spoza bankier/Yahoo), `KALENDARZ_NIEPOTWIERDZONY`.

## 9. Lista kontrolna dat makro (przed scoringiem i w każdym Pulsie)

1. Termin posiedzeń RPP / EBC / Fed i publikacji GUS/BLS sprawdzany w **źródle pierwotnym lub datowanym kalendarzu z bieżącego tygodnia**
   (bankier.pl „Ważny tydzień…", biznes.pap.pl), nigdy z rocznego harmonogramu z pamięci. NBP przesunął posiedzenie wrześniowe 2026
   komunikatem z 9.07 — takie zmiany trzeba wychwytywać.
2. Osobno: data ogłoszenia, godzina zdarzenia (Europe/Warsaw; BLS podaje ET), sesja, do której zdarzenie należy (po 17:00 = następna sesja).
3. Konflikt źródeł → `b.d.` + `KALENDARZ_NIEPOTWIERDZONY`, deklaracja makro nie może się na nim opierać.
4. Deklaracje falsyfikowalne z warunkiem makro mają w treści źródło i datę weryfikacji terminu.

## 10. Uczciwość statystyczna

Przy 5 pozycjach 95-proc. przedział Wilsona dla 2/5 to ok. 12–77%. Wyniki pojedynczych tygodni nie dowodzą przewagi.
Ocena kategorii (które dodają wartość) dopiero po ≥20 tygodniach z pełnymi rankingami w `rankings/`.
