# wig20-bot — instrukcje dla sesji automatycznych

## Metoda i metryki (od 5.09.2026)

- Reguły punktowania i rozliczania: `docs/metoda.md` (obowiązują obie rutyny). Wagi kategorii zamrożone; momentum liczone MECHANICZNIE skryptem, DM ±3 tylko za sygnały z 30 dni, katalizatory jako rejestr zdarzeń (D+1…D+10, brak = 10/20), remis → mniejsza waga w WIG20.
- `scripts/metryki.py momentum --d0 RRRR-MM-DD` — punkty momentum 0–25 z `data/kursy-cache.json` (rel5 2/3 + rel20 1/3; flaga `BRAK_20S`, dopóki cache nie ma 20 sesji).
- `scripts/metryki.py rozlicz --week 2026-Wn --d0 … --d5 …` — metryki całego rankingu: baza tygodnia ȳ, hit rate obok oczekiwania losowego **i z przedziałem Wilsona 95%**, Brier (baseline 0,50 i ȳ(1−ȳ)), Spearman, **benchmark naiwnego momentum z przewagą modelu** oraz kalibracja wielkości alfy. Wymaga `rankings/<week>.json`.
- **Benchmark naiwnego momentum jest testem wartości dodanej modelu i raportuje się go zawsze**, także gdy wypada niekorzystnie: przewaga bliska zeru = siedem kategorii nie wnosi nic ponad sort po rel5. Kontekst i wynik pierwszego pomiaru: `docs/porownanie-chatgpt-2026-09-15.md` (okno 04.09→11.09: przewaga +0,02 p.p.).
- Metryk z różnych wersji metody NIE wolno uśredniać — każdy wpis `history` niesie pole `metoda` (W1–W4 = v1.0 momentum uznaniowe, od W5 = v1.1 mechaniczne).
- `rankings/<week>.json` — pełny ranking tygodnia (20 spółek, punkty per kategoria, p, uzasadnienie), rejestr katalizatorów, `data_quality`. Raport tygodniowy tworzy nowy plik; Puls DOPISUJE katalizatory i kody jakości. Plików z poprzednich tygodni NIE zmieniać ex post.
- `history` w `signals.json` ma dodatkowo pola `base_rate`, `spearman`, `brier`, `data_quality`.
- Aktualne prompty rutyn: `docs/routine-raport-tygodniowy-prompt.txt`, `docs/routine-puls-wig20-prompt.txt` (wersje do wklejenia w claude.ai → Routines).
- `scripts/metryki.py` przyjmuje `--index` i `--cache`, więc działa też dla innych uniwersów; pakiet wdrożeniowy dla rutyn NDX100: `docs/ndx100-wdrozenie.md`.

## Wynik rachunku vs spread papierowy (OBOWIĄZKOWE od 7.09.2026)

Bot handluje na Capital.com z `HEDGE_MODE=index`: kupuje 5 spółek koszyka LONG i sprzedaje kontrakt na WIG20.
**Koszyka SHORT nie handluje wcale** — `desired_book()` w `app.py` pomija go, gdy tryb ≠ `classic`, a tryb `classic` jest NIEDOSTĘPNY: rachunek Capital.com nie pozwala otwierać pozycji krótkich na CFD na akcje (potwierdzone 7.09.2026). Spread LONG−SHORT jest więc metryką z definicji nieosiągalną. Dlatego:

- **Liczba nagłówkowa w każdym raporcie i powiadomieniu = WYNIK RACHUNKU = średnia LONG − WIG20.**
- Spread LONG−SHORT wolno podawać wyłącznie obok, z etykietą „papierowy (miara selekcji, nie wynik rachunku)".
- Rozjazd = spread papierowy − wynik rachunku; podawaj go, gdy przekracza 0,5 p.p.
- Nie nazywaj spreadu papierowego zyskiem i nie pisz o zysku, gdy wynik rachunku jest ujemny.

Trzy warianty (bez hedge'u / z hedge'em / papierowy) wypisuje `scripts/metryki.py rozlicz` w sekcji KOSZYKI — bierz je stamtąd, nie licz ręcznie. Reguła zmiany `HEDGE_RATIO` jest zadeklarowana z góry w `docs/metoda.md` sekcja 10: do 12 zamkniętych okien NIE zmieniamy strategii, żeby nie dopasowywać jej do szumu.
Tło i przykład (W3: papier +1,32 p.p., rachunek −1,61 p.p.) w `docs/metoda.md`, sekcja 7a.

Do wyniku brutto dopisuj koszty: spread bid/ask przy wejściu i wyjściu (przy REDUCE i korekcie wielkości dwa razy —
Capital.com nie ma częściowego zamknięcia), punkty swapowe za dobę utrzymania, luka między zamknięciem D0
a realizacją (rotacja w poniedziałek o 10:01 Warszawy — `/run` o 08:01 UTC, sprostowanie z 15.09.2026 w `docs/metoda.md` §7a — raport liczy od zamknięcia piątku).

Testy logiki portfela: `python3 tests/test_hedge.py` i `python3 tests/test_roll.py` (stdlib, bez pytest; wymagają `pip install -r requirements.txt`). Uruchom oba po każdej zmianie w `app.py`. Testy skryptów rutyn (walidator `signals.json`, `tv_porownaj.py`, `tv_merge.py`): `python3 tests/test_tv.py` — uruchom po każdej zmianie w `scripts/` lub `data/tv-*.json`. Zmiany wykonania z 3.10.2026 (auto-roll hedge'u, uzgadnianie zleceń, pokrycie koszyka): `docs/poprawki-wykonania-2026-10-03.md`.

**Raportowanie bota: wyłącznie log Rendera** (Telegram odcięty w v1.8.1 — nigdy nie był podłączony).
Filtruj po prefiksie `BOT |`; awarie lecą jako ERROR, bieg z błędami jako WARNING. Nie dodawaj wysyłki
do zewnętrznych serwisów bez wyraźnej decyzji właściciela — to wynoszenie stanu rachunku na zewnątrz.

**Ograniczenia rachunku są zapisane w kodzie** (`OGRANICZENIA_RACHUNKU` w `app.py`, widoczne w `/status`):
rachunek Capital.com NIE pozwala shortować CFD na akcje, a API nie ma pola, które by o tym mówiło.
Nie próbuj „naprawiać" `HEDGE_MODE` na `classic`. `/status` zwraca też `diagnostyka_instrumentow`
(czy każda noga koszyka może wejść w docelowej wielkości) i `ekspozycja` (netto; ujemne = rachunek per saldo krótki).
**Wyjątek minimalnej wielkości (od 12.10.2026):** `MIN_SIZE_EXCEPTIONS` (domyślnie `LPPP`) pozwala otworzyć nogę w minimalnej wielkości brokera ponad tolerancję `ALLOC_PCT × MAX_OVERSHOOT` — LPP wchodzi jako 0,1 akcji (ok. 2 500 PLN, ~2/3 koszyka LONG przy kapitale ~3 000 PLN). Hedge rośnie razem z ekspozycją, REDUCE takiej nogi nic nie zmienia (poniżej minimum nie ma nic), pozycja na minimum nie jest przeskalowywana. W raportach pisz wprost o tej koncentracji; rozliczenie modelowe (równe wagi) zostaje bez zmian.

## Kontrola rachunku przez `/status` (od 12.10.2026 — rutyny mają dostęp)

Środowisko rutyn ma zmienną `BOT_URL` (adres bota na Renderze) oraz network secret, który dokłada nagłówek
`X-Run-Token` do żądań na ten host — token NIE jest w zmiennych sesji i nie wolno go szukać ani wypisywać.
Wywołuj WYŁĄCZNIE endpoint tylko do odczytu:

```bash
curl -sS -m 120 "$BOT_URL/status"
```

- NIGDY nie wołaj `/run`, `/generate`, `/close_all` ani `/search` — `/run` uruchamia bieg bota ze zleceniami.
- Brak `BOT_URL` w sesji = brak dostępu: napisz to w PROBLEMY i pomiń kontrolę (nie wymyślaj liczb).
- Pierwsza odpowiedź po dłuższej przerwie może trwać do minuty (Render usypia serwis); `{"error":"zły token"}` = network secret nie dokłada nagłówka — zgłoś w PROBLEMY.
- Z odpowiedzi bierz: `konto.kapital` (equity), `konta_wszystkie[aktywne_dla_bota].saldo` (różnica equity − saldo = otwarty wynik pozycji), `pozycje` (epic, direction, size, upl), `ekspozycja` (dlugie, krotkie, netto, netto_pct_kapitalu), `pokrycie_koszyka` (nogi_na_rachunku/nogi_koszyka, brakujace, ekspozycja_dluga_pct wobec cel_pct), `diagnostyka_instrumentow` (werdykt per noga), `hedge_kontrakt` (epic, dni_do_wygasniecia).
- Kod `EKSPOZYCJA_NIEPELNA` dopisz do `data_quality`, gdy |`ekspozycja.netto_pct_kapitalu`| > 10 albo `pokrycie_koszyka.brakujace` zawiera nogę LONG, której nie wyklucza protokół (`wykluczone_przez_puls`). Noga z werdyktem „NIE WEJDZIE: minimalna pozycja … > tolerancja” to ograniczenie wielkości rachunku (`ALLOC_PCT × MAX_OVERSHOOT`), nie awaria — opisz ją w PROBLEMY jako nogę nieobecną na rachunku; rozliczenie modelowe liczysz dalej z pełnego koszyka.
- Rotacja (`/run`) odpala się o 08:01 UTC = 10:01 Warszawy; bieg Pulsu ok. 8:15 i raport sobotni widzą jeszcze stary koszyk — pisz, którego tygodnia pozycje widzisz (porównaj `pozycje` z `sygnaly.long`).
- Stan rachunku nie opuszcza repozytorium: w raportach podawaj kapitał i wynik w PLN tylko w sekcji PROBLEMY/kontrola pokrycia, nie w powiadomieniach push.

## TradingView MCP (od 12.10.2026 — faza 1, CIEŃ)

Właściciel 12.10.2026 wyraził zgodę na wdrożenie konektora TradingView MCP w czterech rutynach (plan:
`WDROZENIE-TRADINGVIEW-2026-10-12.md` w repo ndx100-bot, sekcje 6.3, 6.4, 7). Pełne zasady dla rutyn WIG20:
**`docs/tradingview.md`** — rutyny czytają go na starcie. Skrót:

- Narzędzia `mcp__TradingView__mcp-tv-*` (odczyt + alerty) i `mcp__TradingView__mcp-watchlist-*`; schematy
  ładuje `ToolSearch` zapytaniem `select:<pełna nazwa>`. W rutynach WYŁĄCZNIE allowlista odczytu; ZAKAZ
  wszystkich narzędzi zapisu (alerty, watchlisty) i `get-active-watchlist` — rutyna nie dostaje pytania o zgodę.
- Pliki: `data/tv-config.json` (`enabled`, `faza`, budżety: puls ≤20 wywołań / 8 min / przed 10:01 Warszawy,
  sobota ≤25 / 15 min; flagi — wszystkie `false`), `data/tv-symbole.json` (jedyne źródło symboli: ticker
  systemowy → `GPW:<ticker giełdowy>`, subindeksy, surowce/FX, `ECONOMICS:PL*`), `data/tv-kolumny.json`
  (jedyne źródło nazw kolumn), `data/tv-log.jsonl` (wiersz na bieg). Bez liczb z rachunku.
- Skrypty: `scripts/waliduj_signals.py --diff HEAD --rutyna puls|sobota` (obowiązkowy PRZED każdym commitem
  `signals.json`: 12 kluczy, `epics` nietknięte, pola per rutyna, wpisy `exclude` z polami liczbowymi, `history` +1
  z metodą v1.1, `rankings/` tylko plik bieżącej/nowej version — bot NIE odrzuca obcych pól), `scripts/tv_porownaj.py`
  (TV vs `kursy.py --json`, tabela ZGODNOŚĆ 21/21, wiersz logu), `scripts/tv_merge.py --tylko-brakujace` (backfill
  cache: walidacja D0 0,5%, test korekty serii 0,1% → `TV_DANE_ROZBIEZNE`, tylko brakujące sesje). Testy: `tests/test_tv.py`.
- Faza 1 (cień, do raportu `reports/tv-cien-2026-10.html` ok. 31.10): `kursy.py` nadal źródłem tabel, progów
  4%/8% i `d0.prices`; TV = drugie źródło (kontrola 21/21), bezpośrednia świeca D0 i backfill luk cache po
  walidacji, kalendarze (makro z `min_importance=-1`, dywidendy `market='poland'`, daty wyników z kolumny
  `earnings_release_next_date`). Żaden werdykt nie zależy od TV. Faza 2 (TV nr 1 kursów) po kryteriach z
  `docs/tradingview.md` §9 i decyzji właściciela.
- Decyzje właściciela 12.10.2026: Puls o 8:15 (przed otwarciem); backfill zostaje w metodzie v1.1 z kodem
  `KURS_ZRODLO_TV`, bez korekty ex-div w momentum (v1.2 tylko po decyzji); flagi `event_blokada_taktycznej`,
  `wstrzymanie_przy_rozjezdzie`, `konsensus_tv_do_punktacji`, `korekta_exdiv_momentum_v1_2` = `false`.
- Fakty z inwentaryzacji 12.10 (`docs/tradingview.md` §4): GPW 20/20 w screenerze `market='poland'` i w batchu;
  `get-ohlcv` bez korekty dywidendowej (LPP przez ex-date 8.10); `get-news`, `get-earnings-calendar(symbols)` i
  `get-dividends-calendar(symbols)` dla GPW puste; `get-forecasts` dla GPW z celami o złej skali (tylko liczba
  analityków i rozkład); kalendarz PL ma `importance = -1`.
- Nowe kody `data_quality` (`docs/metoda.md` §8): `KURS_ZRODLO_TV`, `TV_MCP_NIEDOSTEPNY`, `TV_DANE_ROZBIEZNE`;
  `KURS_ZRODLO_REZERWA` = kurs z bankier/cache; `FMP_PLAN_BLOKADA` nie jest już dopisywany.

## Źródło kursów (priorytet dla rutyny „Puls WIG20")

KOLEJNOŚĆ ŹRÓDEŁ (od 12.10.2026): (1) skrypt `kursy.py` (Yahoo → bankier.pl → cache) ZAWSZE i RAZ na bieg →
(2) TradingView MCP jako drugie źródło, bezpośrednia świeca D0 i backfill luk cache (`docs/tradingview.md` §5.1).
Konektor FMP NIE jest już źródłem kursów: na obecnym planie odmawia końcówek cenowych (`FMP_PLAN_BLOKADA` W4–W9)
— nie wołaj `mcp__FMP__chart` ani `quote`, kodu nie dopisuj. Historyczny opis FMP (wersja z 27.08–7.09.2026)
usunięty 12.10.2026; tickery `.WA` i mapowanie nazw: `scripts/kursy.py` (`SYMBOLE`).

### Skrypt `kursy.py` (Yahoo chart API → bankier.pl → cache)

Dzienne kursy zamknięcia pobieraj gotowym skryptem:

```bash
python3 scripts/kursy.py WIG20.WA DNP.WA KGH.WA BDX.WA PKO.WA ALE.WA TPE.WA PKN.WA PGE.WA MDV.WA MBK.WA
```

Zasady:

- Endpoint: `https://query2.finance.yahoo.com/v8/finance/chart/TICKER.WA?range=1mo&interval=1d` (zapasowo host `query1`). Tickery GPW mają sufiks `.WA`; mapowanie nazw z `signals.json` na tickery: DINOPL→DNP, KGHM→KGH, BUDIMEX→BDX, PKOBP→PKO, ALLEGRO→ALE, TAURONPE→TPE, PKNORLEN→PKN, PGE→PGE, MODIVO→MDV, MBANK→MBK; indeks: WIG20.WA.
- W JSON bierz pary `timestamp` + `indicators.quote[0].close`. Ostatni wiersz z dzisiejszą datą przy otwartej sesji GPW to kurs śródsesyjny — do tabel raportu bierz zamknięcie OSTATNIEJ ZAKOŃCZONEJ sesji.
- WALIDACJA OBOWIĄZKOWA: zamknięcia z dnia D0 muszą zgadzać się z polem `d0.prices` w `signals.json`. Przy niezgodności traktuj serię jako niepewną (`b.d.` + opis problemu w raporcie).
- Dla indeksu WIG20 Yahoo bywa niekompletne — wtedy wartość indeksu bierz z depesz PAP/Strefa Inwestorów (przez WebSearch).
- CACHE KURSÓW: `scripts/kursy.py` po każdym udanym pobraniu dopisuje zamknięcia do `data/kursy-cache.json`, a przy błędach Yahoo (typowo HTTP 429 z IP chmury) automatycznie podaje kursy z cache, oznaczając je w kolumnie SYMBOL jako `cache` i w sekcji PROBLEMY. Kursy z cache są zwalidowane, ale mogą nie obejmować ostatniej sesji — zawsze sprawdź kolumnę SESJA. Po biegu, w którym cache się zmienił, COMMITUJ zaktualizowany `data/kursy-cache.json` razem z raportem (to jedyna trwałość między sesjami — kontener jest efemeryczny).
- LIMITER YAHOO: z IP chmury Yahoo dławi SERIE zapytań (HTTP 429) — pojedyncze przechodzą, seria ~25 pod rząd blokuje IP na długo (kwadranse–godziny). `kursy.py` ma wbudowaną ochronę (pauzy 3 s, ponowienia z budżetem czasu, priorytet dla spółek koszykowych, po pierwszym 429 spółki spoza koszyków nie strzelają do Yahoo). NIE uruchamiaj skryptu wielokrotnie pod rząd i nie odpytuj Yahoo ręcznie seriami — każda seria ponownie uzbraja limiter.
- REZERWA BANKIER (od 27.08.2026 `www.bankier.pl` jest w allowliście sieci): `kursy.py` automatycznie sięga do serwerowo renderowanych tabel `https://www.bankier.pl/gielda/notowania/akcje` i `.../indeksy-gpw` (kurs, zmiana %, zmiana absolutna, znacznik czasu; symbole zgodne z tickerami z `signals.json`, w tym WIG20). W trakcie sesji zamknięcie poprzedniej sesji = kurs − zmiana absolutna. Endpoint wykresów `bankier.pl/new-charts/get-data` jest przestarzały (dane do stycznia 2026) — nie używaj go.
- Stooq (`stooq.pl`/`stooq.com`) jest w allowliście sieci środowiska, ale z IP chmury resetuje połączenia albo zwraca atrapę „strona nie istnieje" — nie trać na niego czasu.
- Od 27.08.2026 w allowliście są też `biznes.pap.pl` i `strefainwestorow.pl` (depesze PAP — działają, dobre do wartości WIG20 i newsów) oraz `www.gpw.pl` (formalnie odblokowany, ale serwer ucina połączenia z IP chmury — „Empty reply" — nie trać na niego czasu). Pozostałe serwisy notowań (TradingView, Google Finance, investing.com, money.pl, wnp.pl) są blokowane przez politykę sieciową — nie próbuj ich fetchować; research newsowy prowadź przez WebSearch.
