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
- Wpis `history` w `signals.json` dostaje pola: `base_rate`, `spearman`, `brier`, `data_quality` (lista kodów), `metoda`.
- Spread, managed_pp, reaction_pp, tactical_pp — bez zmian (definicje w promptach rutyn).

## 7a. Papier a rachunek — DWIE różne liczby (od 7.09.2026)

To jest najważniejsze rozróżnienie w całej metodzie i przed 7.09.2026 go nie było, przez co raporty pokazywały zysk,
gdy rachunek tracił.

Bot handluje na Capital.com z `HEDGE_MODE=index`: **kupuje 5 spółek z koszyka LONG i sprzedaje kontrakt na WIG20**.
Koszyka SHORT jako akcji **nie handluje wcale** (`desired_book()` w `app.py` pomija go, gdy tryb ≠ `classic`).
Stąd dwie metryki, obie liczone przez `scripts/metryki.py rozlicz` w sekcji KOSZYKI:

| metryka | wzór | co opisuje |
|---|---|---|
| **wynik rachunku** | średnia LONG − indeks | to, co realnie zarabia lub traci konto (brutto, przed spreadem i swapem) |
| spread papierowy | średnia LONG − średnia SHORT | jakość selekcji obu koszyków; **nie jest wynikiem rachunku** |
| rozjazd | spread papierowy − wynik rachunku | alfa strony krótkiej, której rachunek NIE zbiera |

**W raportach nagłówkową liczbą jest wynik rachunku (LONG − indeks).** Spread papierowy wolno podawać wyłącznie
obok niego i wyłącznie z etykietą „papierowy”. Przykład z W3 (28.08→4.09): spread papierowy **+1,32 p.p.**,
wynik rachunku **−1,61 p.p.**, rozjazd **+2,93 p.p.** — cała przewaga tygodnia powstała na koszyku SHORT,
którego rachunek nie miał.

Do wyniku rachunku **brutto** dochodzą jeszcze koszty, które w raporcie należy wymienić, a nie pomijać:
spread bid/ask przy każdym wejściu i wyjściu (a przy `REDUCE` i korekcie wielkości — dwa razy, bo Capital.com
nie ma częściowego zamknięcia), punkty swapowe za każdą dobę utrzymania i luka między zamknięciem D0 a ceną
realizacji. **Uwaga, sprostowanie z 15.09.2026:** ten dokument podawał wcześniej rotację „w poniedziałek o 9:15”.
Log Rendera i historia transakcji Capital.com pokazują, że `/run` odpala się o **08:01 UTC, czyli 10:01 czasu
warszawskiego** — godzinę po otwarciu GPW, nie kwadrans. Raport liczy od zamknięcia piątku, więc luka realizacji
obejmuje pełną pierwszą godzinę poniedziałkowej sesji. Rząd wielkości tej luki (rotacja W5, 14.09): TAURON wszedł
po 9,298 przy zamknięciu D0 9,40 (−1,09% na korzyść), mBANK po 1469,015 przy 1463,50 (+0,38% na niekorzyść) —
czyli ok. ±1% na nogę, porównywalnie z całą tygodniową przewagą.

**Tryb `classic` (realne SELL na akcjach) jest NIEDOSTĘPNY** — rachunek Capital.com nie pozwala otwierać pozycji
krótkich na CFD na akcje (potwierdzone przez właściciela rachunku 7.09.2026; ślad w kodzie: `Capital.open()` ma
pętlę potwierdzenia właśnie pod odrzucenia typu „SELL niedostępny"). To nie jest ustawienie do przełączenia,
tylko trwałe ograniczenie rachunku. Wniosek: **spread LONG−SHORT jest metryką z definicji nieosiągalną** i nie
wolno go stawiać jako celu ani wyniku. Rachunek może zbierać wyłącznie alfę strony długiej wobec indeksu.

Konsekwencja dla rankingu: BOTTOM5 nie trafia na rachunek jako pozycja. Zachowuje sens jako (a) lista, której
nie wolno trzymać długo, i (b) diagnostyka jakości modelu. Krótką ekspozycję na te spółki rachunek ma wyłącznie
pośrednio — w wadze indeksowej, przez shorta na WIG20.

### Trzy warianty, które trzeba raportować równolegle

Skoro strona krótka jest poza zasięgiem, jedyną otwartą decyzją konstrukcyjną zostaje **czy w ogóle hedgować**.
Dlatego `metryki.py rozlicz` podaje trzy liczby i wszystkie trzy idą do `history`:

| wariant | wzór | uwaga |
|---|---|---|
| `long_abs_pct` | średnia LONG (bez hedge'u) | czysta ekspozycja kierunkowa, zbiera beta rynku |
| `long_vs_index_pp` | średnia LONG − indeks | **stan obecny**, `HEDGE_RATIO=1.0` |
| `spread_pp` | średnia LONG − średnia SHORT | papierowy, nieosiągalny — wyłącznie miara selekcji |

Hedge indeksowy ma sens **tylko wtedy, gdy selekcja długa bije indeks**. Jeżeli nie bije, hedge zamienia zwyżkę
rynku w stratę. Decyzji o `HEDGE_RATIO` **nie podejmuje się na kilku tygodniach danych** — patrz sekcja 10.

## 7b. Trzy pomiary dodane 15.09.2026 (audyt porównawczy — `docs/porownanie-chatgpt-2026-09-15.md`)

Wszystkie trzy są POMIAREM, nie zmianą punktacji: nie dotykają wag, wyniku, p ani składu koszyków.

1. **Benchmark naiwnego momentum.** `rozlicz` rozgrywa ten sam tydzień koszykami zbudowanymi wyłącznie
   z rel5 na D0 (TOP5 = 5 najwyższych, BOTTOM5 = 5 najniższych, to samo uniwersum) i podaje
   `przewaga_long_vs_indeks_pp` = model − naiwne momentum. **To jest główny test wartości dodanej.**
   Jeśli przewaga oscyluje wokół zera, sześć uznaniowych kategorii nie robi nic, czego nie zrobiłby
   jednolinijkowy sort po rel5 — i to ma trafić do raportu tygodniowego, a nie zostać przemilczane.
   Benchmark wymaga 5 sesji przed D0 w cache; przy ich braku zwraca `dostepny: false` z powodem.
2. **Przedział Wilsona 95% przy hit rate.** Hit 4/5 daje przedział 38–96%, czyli obejmuje 50% —
   pojedynczy tydzień nigdy nie jest dowodem przewagi. Sens pojawia się dopiero na sumie tygodni.
   Hit rate podaje się odtąd zawsze z przedziałem.
3. **Kalibracja WIELKOŚCI alfy.** Diagnostyczna mapa `alfa_prog = 0,08 × (wynik − 50)`, obcięta do ±2,5 p.p.
   (przeniesiona z systemu równoległego, NIE kalibrowana na naszych danych), porównywana z realizacją:
   MAE prognozy wobec MAE prognozy zerowej i korelacja. Gdy MAE nie bije prognozy zerowej, wynik
   przewiduje najwyżej znak alfy, nie jej wielkość. Mapa nie wpływa na nic poza tym pomiarem.

**Zakaz uśredniania wersji.** Każdy wpis `history` niesie `metoda` (`v1.0 (momentum uznaniowe)` dla W1–W4,
`v1.1 (momentum mechaniczne)` od W5). Metryk z różnych wersji NIE wolno łączyć w jedną średnią ani
przedstawiać jako dorobku jednej strategii; licznik zamkniętych okien z §10 biegnie osobno dla wersji.

## 8. Kody `data_quality`

`RPP_DATE_ERROR` (błędna data posiedzenia), `OKNO_SKROCONE_Dn`, `BRAK_PELNEGO_RANKINGU`, `METRYKI_Nk_Z_20` (metryki z k spółek),
`DYWIDENDA_KOREKTA_<TICKER>`, `KURS_ZRODLO_REZERWA` (kurs D0/D+5 spoza bankier/Yahoo), `KALENDARZ_NIEPOTWIERDZONY`,
`FMP_PLAN_BLOKADA` (konektor w sesji, ale abonament blokuje endpointy), `KNF_SHORT_NIEDOSTEPNY` (rejestr krótkiej sprzedaży
poza zasięgiem sieci), `EBC_KONSENSUS_ROZBIEZNE_ZRODLA`, `EKSPOZYCJA_NIEPELNA` (rachunek nie odwzorował koszyka —
pominięte nogi, patrz `pominiete`/`ekspozycja_dluga` w odpowiedzi `/run`).

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

### Decyzja o `HEDGE_RATIO` — reguła zadeklarowana Z GÓRY (7.09.2026)

Stan na 7.09.2026, dwa pełne okna (W2, W3) — za mało, żeby cokolwiek rozstrzygać, ale dość, żeby ustalić regułę:

| wariant | W2 | W3 | razem |
|---|---|---|---|
| LONG bez hedge'u | −2,38% | +0,81% | **−1,57%** |
| LONG − indeks (stan obecny) | −2,02 p.p. | −1,61 p.p. | **−3,63 p.p.** |
| spread papierowy (nieosiągalny) | −2,31 p.p. | +1,32 p.p. | −0,99 p.p. |

Trafienia TOP5 przez trzy tygodnie: 4/15. Dla W2 i W3, gdzie znamy bazę tygodnia, losowo wypadłoby 3,4 trafienia,
padło 1. BOTTOM5: padło 7 przy 6,6 losowo. **Żadna z tych liczb niczego nie dowodzi** — to trzy tygodnie i n=15
spółkotygodni na stronę. Nie wolno na tej podstawie zmieniać strategii; to byłoby dopasowanie do szumu.

Dlatego reguła jest ustalona teraz, zanim dane ją podpowiedzą:

1. Do **12 zamkniętych okien** `HEDGE_RATIO` zostaje **1.0** i strategii się nie tuninguje. Zbieramy dane.
2. Po 12. oknie porównujemy skumulowane `long_abs_pct` i `long_vs_index_pp` z `history`.
3. Jeżeli `long_vs_index_pp` skumulowane jest ujemne **i** trafienia TOP5 nie przekraczają oczekiwania losowego
   (suma 5·ȳ po wszystkich oknach), to znaczy, że selekcja długa nie bije indeksu, a hedge tylko wycina beta.
   Wtedy — i tylko wtedy — schodzimy z `HEDGE_RATIO` do 0,5 na kolejne 12 okien i zapisujemy to w `history`
   jako zmianę reżimu.
4. Zmiana `HEDGE_RATIO` w środku okna jest zabroniona. Wyłącznie przy sobotniej rotacji.
5. Każda zmiana reżimu jest odnotowana w raporcie tygodniowym wraz z uzasadnieniem i datą — inaczej po roku
   nie da się odróżnić przewagi modelu od przewagi majsterkowania przy parametrach.
