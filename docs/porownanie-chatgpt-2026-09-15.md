# Porównanie z systemem równoległym (ChatGPT) — stan na 15.09.2026

Materiał wejściowy: `PODSUMOWANIE_DO_INNEGO_MODELU.md` przekazane przez właściciela 15.09.2026,
opisujące serię „WIG20 8:30 Ranking" (okna W01–W04, autor: ChatGPT/OpenAI).
Strona nasza: `rankings/2026-W2..W5.json`, `signals.json → history`, `data/kursy-cache.json`.

**Weryfikacja niezależna.** Odtworzyłem obie serie na naszym cache kursów. Liczby drugiej strony zgadzają się
co do trzeciego miejsca po przecinku (ich alfa TOP W03 `+3,838921` → moje `+3,84`; ich benchmark naiwnego
momentum `+5,395` → moje `+5,40`; ich przedziały Wilsona 8/15 `30,12–75,19%` → moje `0,3012–0,7519`).
Arytmetyka po stronie ChatGPT jest rzetelna. Nie audytowałem ich punktacji kategorii ani okna W01
(nasz cache zaczyna się 21.08.2026 i nie ma 5 sesji przed ich D0 = 21.08).

## 1. Okna się pokrywają — porównanie jest 1:1

| Okno | D0 → D+5 | u nas | u ChatGPT |
|---|---|---|---|
| A | 28.08 → 04.09.2026 | W3 | W02 |
| B | 04.09 → 11.09.2026 | W4 | W03 |
| C (otwarte) | 11.09 → 18.09.2026 | W5 | W04 |

Identyczne uniwersum (20 spółek WIG20), identyczne D0/D+5, identyczna definicja alfy i koszyki równoważone.

## 2. Wynik: ChatGPT lepszy w obu zamkniętych oknach

| Miara | Okno A (my / oni) | Okno B (my / oni) |
|---|---|---|
| **alfa LONG − WIG20** (to gra rachunek) | **−1,61** / **+1,76** p.p. | **+2,70** / **+3,84** p.p. |
| spread papierowy LONG−SHORT | +1,33 / +3,96 p.p. | +5,54 / +7,20 p.p. |
| hit TOP5 | 1/5 / 2/5 | 4/5 / 4/5 |
| hit BOTTOM5 | 4/5 / 4/5 | 4/5 / 5/5 |
| Spearman | 0,143 / 0,236 | 0,635 / 0,771 |
| Brier | 0,2529 / 0,2537 | 0,2263 / 0,2087 |

Średnio na metryce, którą rachunek faktycznie handluje: **ChatGPT +2,80 p.p./tydzień, my +0,55 p.p./tydzień.**

## 3. Cała różnica to dwie spółki, nie mechanika punktowania

- **Okno A:** ich TOP miał **PGE +15,2%** i PKN +6,1%. Same te dwie pozycje dają **+3,30 p.p. z 3,37 p.p.**
  całej przewagi okna. My byliśmy w tym oknie **SHORT na TAURONIE** (+2,8%, czyli strata na nodze krótkiej)
  i bez PGE w koszyku długim.
- **Okno B:** ich TOP miał **TAURON +9,0%**, my zamiast tego PZU +0,4%. Po odjęciu pozostałych różnic
  (nasz mBANK +3,9% vs ich LPP +1,0%) wychodzi dokładnie **+1,14 p.p.** — cała różnica okna.

**Test koncentracji:** usunięcie PGE z ich koszyka w oknie A zmienia ich alfę z **+1,76** na **−0,99 p.p.**,
czyli poniżej naszej (−1,61 to nadal mniej, ale przewaga znika). Przewaga siedzi w jednej spółce.

**Zarzut look-ahead — odrzucony.** Ich raport W02 powstał 31.08 przy D0 28.08. Sprawdziłem ścieżkę kursu:
do 31.08 PGE urosło dopiero +1,93%, główny ruch (+7,8%) przyszedł 02–04.09. Ich trafienie było prawdziwe,
nie wsteczne.

**Wniosek merytoryczny:** to nie była wyższość ich aparatu punktowego, tylko **jedna teza makro odczytana
dwa tygodnie wcześniej**. Oni potraktowali rajd gazowo-energetyczny jako pozytyw dla PGE/TAURONU; my te same
nazwy trzymaliśmy po stronie krótkiej, przeważając ryzyko CIT 30%/2027. W W5 mamy już ich tezę
(uzasadnienie PGE: „gaz TTF +12% t/t i drogie EUA… ale CIT wisi") — skonwergowaliśmy, spóźnieni o dwa okna.

## 4. Najważniejsza liczba: nasz model nie bije naiwnego momentum

Benchmark przeniesiony od nich, policzony teraz przez `scripts/metryki.py rozlicz` (okno B):

| | spread | alfa LONG |
|---|---:|---:|
| naiwne momentum (sam rel5 na D0) | +5,40 p.p. | +2,68 p.p. |
| **nasz model (7 kategorii)** | +5,54 p.p. | **+2,70 p.p.** |
| model ChatGPT | +7,20 p.p. | +3,84 p.p. |

**Nasz siedmiokategoryjny aparat dodał +0,02 p.p. ponad jednolinijkowy sort po rel5.** Ich dodał +1,16 p.p.
W oknie A benchmark jest niedostępny (cache za krótki). To jedna obserwacja, ale dotąd nie mieliśmy jej wcale —
i to jest główny powód, dla którego ten pomiar wchodzi do `rozlicz` na stałe.

Kalibracja wielkości alfy (diagnostyka): okno A MAE 2,74 p.p. wobec 2,72 p.p. prognozy zerowej, korelacja +0,019;
okno B MAE 2,49 wobec 2,62, korelacja +0,532. Czyli w oknie A wynik nie przewidywał nawet wielkości, w oknie B
przewidywał słabo.

## 5. Bieżące okno: różnica już się zamknęła

Koszyki W5 (my) vs W04 (oni), oba D0 = 11.09.2026, WIG20 4139,25:

- **SHORT identyczny 5/5**: DINOPL, KRUK, KETY, PEPCO, MODIVO.
- **LONG 4/5**: PGE, PKNORLEN, TAURONPE, PEKAO. Jedyna różnica — nasz **mBANK** vs ich **PKO BP**.

Po D+1 (14.09): ich TOP −0,860%, nasz LONG −0,818%. Jesteśmy o 0,04 p.p. z przodu, bo mBANK (−0,27%)
spisał się lepiej niż PKO BP (−0,48%). Od tego okna oba systemy będą dawać prawie identyczne wyniki,
więc dalsze porównanie selekcji przestaje różnicować.

## 6. Czego strona przeciwna nie mierzy

Ich dokument stwierdza wprost: brak bota, brak zleceń, brak cen wykonania, brak kosztów, „nie wolno
utożsamiać alfy z zyskiem portfela", a suma spreadów nie jest zyskiem portfela. Ich +5,58 p.p. średniego
spreadu to liczba, której nikt nie zainkasował.

Po naszej stronie jedyną liczbą w pieniądzach jest wynik rachunku Capital.com: **−43,1 PLN od 26.08.2026**
(zrealizowane −29,77, swap −9,06, niezrealizowane −4,29; kapitał 2 940,89 PLN na 15.09). Przy koszcie
utrzymania ok. 0,45 PLN/dobę swapu (≈5,6% kapitału rocznie) i ok. 0,14% spreadu na jedną wymianę nogi
istotna część ich papierowej przewagi i tak zostałaby na wykonaniu.

## 7. Co przeniesiono (15.09.2026)

Wdrożone w tym commicie — wyłącznie pomiary i dokumentacja, **bez dotykania zamrożonej punktacji**:

1. **Benchmark naiwnego momentum** w `scripts/metryki.py rozlicz` (`benchmark_momentum`,
   `przewaga_long_vs_indeks_pp`, `przewaga_spread_pp`).
2. **Przedziały Wilsona 95%** przy hit rate TOP5/BOTTOM5 (`wilson`, `hit_top5_wilson`, `hit_bottom5_wilson`),
   z jawnym komunikatem, że przedział obejmujący 50% nie dowodzi przewagi.
3. **Kalibracja wielkości alfy** (`alfa_prognozowana_pp`, `kalibracja_alfy`) — MAE prognozy wobec MAE prognozy
   zerowej i korelacja. Mapa `0,08 × (wynik − 50)` obcięta do ±2,5 p.p. jest przeniesiona od nich
   i **nie była kalibrowana na naszych danych** — służy tylko jako punkt odniesienia.
4. **Znakowanie wersji metody** — `metoda` w każdym wpisie `signals.json → history` (W1–W4 = v1.0, momentum
   uznaniowe; od W5 = v1.1, momentum mechaniczne) plus zakaz uśredniania metryk przez wersje (`docs/metoda.md` §7b).
5. **Sprostowanie godziny rotacji** w `docs/metoda.md` §7a: 10:01 czasu warszawskiego, nie 9:15.

## 8. Czego świadomie NIE przeniesiono

- **Warstwy LIVE.** Ich własny dokument mówi „brak rozliczenia" — brak cen wejścia, brak reguł REDUCE/CLOSE,
  brak P&L. Nasz protokół `exclude` z polami `trigger`, `price_before`, `move_from_d0_pct` jest ściślejszy
  i to jedyny obszar, w którym mamy przewagę metodologiczną, a nie tylko wykonawczą.
- **Ich mapy p** (nachylenie 0,6, obcięcie 35–68% wobec naszych 0,5 i 38–62%). Ich Brier nie jest
  systematycznie lepszy, więc obie mapy są tak samo arbitralne. Zmiana i tak byłaby zmianą metody.
- **Reversal cap na momentum** (ograniczenie do 20/25, gdy bezwzględny zwrot 5-sesyjny ≥ +10%).
  Reguła jest sensowna i konkretna — w bieżącym oknie PGE miało +11,9% w 5 sesjach, my daliśmy pełne 25,0,
  oni 20, a PGE spadło na D+1 o 1,85%. **To jednak zmiana punktacji, więc zgodnie z §10 wraca do decyzji
  dopiero po 12 zamkniętych oknach.** Zapisane tutaj, żeby nie zginęło.

## 9. Wspólna słabość obu systemów

Oba trafiają **znacznie lepiej po stronie krótkiej** niż długiej:

| | hit TOP | hit BOTTOM |
|---|---|---|
| my (W1–W4) | 8/20 = 40% | 14/20 = 70% |
| ChatGPT (W01–W03) | 8/15 = 53% | 11/15 = 73% |

To jest dokładnie ta strona, której rachunek Capital.com **nie pozwala handlować** (brak SELL na CFD na akcje).
Cała mierzalna przewaga obu modeli koncentruje się w koszyku, którego nie da się otworzyć. Przedziały Wilsona
dla obu (nasz BOTTOM 14/20 → 48–85%, ich 11/15 → 48–89%) wciąż obejmują 50%, więc to nawet nie jest
udowodniona umiejętność — ale kierunek jest zgodny w obu niezależnych seriach i wart obserwacji.

---

*Materiał analityczno-edukacyjny, nie stanowi rekomendacji inwestycyjnej. Zapis audytu wykonanego
automatycznie 15.09.2026; liczby drugiej strony pochodzą z dokumentu przekazanego przez właściciela
i zostały przeliczone na naszym cache kursów, nie pobrane niezależnie ze źródeł.*
