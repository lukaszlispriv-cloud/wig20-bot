# wig20-bot — instrukcje dla sesji automatycznych

## Źródło kursów (priorytet dla rutyny „Puls WIG20")

Dzienne kursy zamknięcia pobieraj z Yahoo Finance chart API — gotowym skryptem:

```bash
python3 scripts/kursy.py WIG20.WA DNP.WA KGH.WA BDX.WA PKO.WA ALE.WA TPE.WA PKN.WA PGE.WA MDV.WA MBK.WA
```

Zasady:

- Endpoint: `https://query2.finance.yahoo.com/v8/finance/chart/TICKER.WA?range=1mo&interval=1d` (zapasowo host `query1`). Tickery GPW mają sufiks `.WA`; mapowanie nazw z `signals.json` na tickery: DINOPL→DNP, KGHM→KGH, BUDIMEX→BDX, PKOBP→PKO, ALLEGRO→ALE, TAURONPE→TPE, PKNORLEN→PKN, PGE→PGE, MODIVO→MDV, MBANK→MBK; indeks: WIG20.WA.
- W JSON bierz pary `timestamp` + `indicators.quote[0].close`. Ostatni wiersz z dzisiejszą datą przy otwartej sesji GPW to kurs śródsesyjny — do tabel raportu bierz zamknięcie OSTATNIEJ ZAKOŃCZONEJ sesji.
- WALIDACJA OBOWIĄZKOWA: zamknięcia z dnia D0 muszą zgadzać się z polem `d0.prices` w `signals.json`. Przy niezgodności traktuj serię jako niepewną (`b.d.` + opis problemu w raporcie).
- Dla indeksu WIG20 Yahoo bywa niekompletne — wtedy wartość indeksu bierz z depesz PAP/Strefa Inwestorów (przez WebSearch).
- CACHE KURSÓW: `scripts/kursy.py` po każdym udanym pobraniu dopisuje zamknięcia do `data/kursy-cache.json`, a przy błędach Yahoo (typowo HTTP 429 z IP chmury) automatycznie podaje kursy z cache, oznaczając je w kolumnie SYMBOL jako `cache` i w sekcji PROBLEMY. Kursy z cache są zwalidowane, ale mogą nie obejmować ostatniej sesji — zawsze sprawdź kolumnę SESJA. Po biegu, w którym cache się zmienił, COMMITUJ zaktualizowany `data/kursy-cache.json` razem z raportem (to jedyna trwałość między sesjami — kontener jest efemeryczny).
- Stooq (`stooq.pl`/`stooq.com`) jest w allowliście sieci środowiska, ale z IP chmury zwykle resetuje połączenia i limituje pobrania CSV („Odmowa dostępu") — traktuj go wyłącznie jako rezerwę i nie trać czasu, gdy odmawia.
- Bezpośrednie strony serwisów notowań (Bankier, GPW, TradingView, Google Finance, investing.com) są blokowane przez politykę sieciową — nie próbuj ich fetchować; research newsowy prowadź przez WebSearch.
