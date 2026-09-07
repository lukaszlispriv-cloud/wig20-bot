# Wdrożenie v1.8.0 — co trzeba zrobić ręcznie

Zmiany w kodzie wchodzą same przy najbliższym deployu na Renderze. Poniższe kroki
wymagają Twojej ręki — bez nich część poprawek nie zadziała.

## 1. Pilne: wyrównanie ekspozycji na rachunku

Stan zastany 7.09.2026 po biegu 9:15 (z `leveraged_trades_history` i logu Rendera):

| pozycja | wielkość | wartość |
|---|---|---|
| PEKAO (PEO) | +1,1 | ~291 PLN |
| PGE | +12 | ~156 PLN (rozmiar taktyczny, powinno być ~293) |
| WIG20 (FW2020U2026) | −0,37 | ~1 523 PLN |
| **ekspozycja netto** | | **−1 077 PLN = −36,7% kapitału** |

Bot uznawał to za pozycję neutralną, bo hedge liczył od koszyka docelowego (5 × 293 = 1 466 PLN),
a nie od tego, co realnie weszło. Po deployu **pierwszy `/run` sam to naprawi**: policzy ekspozycję
długą z faktycznych pozycji i dotnie hedge do jej wielkości.

Zanim to zrobisz, zajrzyj do `/status` — jeśli WIG20 zdąży się cofnąć, domknięcie shorta na spadku
kosztuje mniej. To jedyna decyzja, której kod za Ciebie nie podejmie.

## 2. Dlaczego PKNORLEN, PZU i MBANK nie weszły

Log podaje tylko licznik (`pominięte: 4` = koszyk SHORT + trzy longi). Od v1.8.0 powody idą
w treści powiadomienia na Telegramie i do logu (`RAPORT /run: {...}`), więc następny bieg
sam powie, co się stało. Najbardziej prawdopodobne dwa powody:

- **minimalna wielkość transakcji ponad tolerancję** — przy celu 293 PLN i `MAX_OVERSHOOT=1.6`
  próg to 469 PLN; MBANK po ~1 420 zł wymaga kroku ≥0,33, więc jeśli Capital.com ma tam
  `minDealSize` np. 0,5 (≈710 PLN), pozycja jest odrzucana z automatu;
- **rynek nie `TRADEABLE` o 9:15** — bieg wypada 15 minut po otwarciu GPW.

Jeśli okaże się to pierwsze, masz trzy wyjścia: podnieść `ALLOC_PCT`, podnieść `MAX_OVERSHOOT`
albo świadomie zostawić te spółki poza koszykiem — ale wtedy hedge (już poprawny) będzie
odpowiednio mniejszy i strategia stanie się węższa, niż zakłada ranking.

## 3. Token poza URL

Dziś `RUN_TOKEN` jedzie w query stringu i **ląduje w logach Rendera w postaci jawnej** —
każdy z dostępem do logów przejmuje kontrolę nad botem. Kolejność działań:

1. Zmień `RUN_TOKEN` na Renderze na nową wartość (stary uznaj za spalony — był w logach,
   które trafiły też poza Render).
2. W cron-job.org, w każdym zadaniu (`/generate?mode=daily`, `/generate?mode=weekly`, `/run`),
   usuń `?token=...` z URL i dodaj nagłówek:
   `X-Run-Token: <nowy token>`
   (zakładka „Headers" w edycji zadania; alternatywnie `Authorization: Bearer <token>`).
3. Sprawdź, że biegi przechodzą (Telegram + `/health`).
4. Dopiero wtedy ustaw na Renderze `ALLOW_TOKEN_IN_URL=false` — od tego momentu wariant
   z URL jest odrzucany.

Kroki 1–3 i 4 muszą iść w tej kolejności, inaczej bot zamilknie w locie.

## 4. Nowe zmienne środowiskowe

| zmienna | domyślnie | znaczenie |
|---|---|---|
| `SIZE_TOL` | `0.35` | dopuszczalne odchylenie wielkości otwartej pozycji od celu, zanim bot ją przeskaluje (zamknij+otwórz, drugi spread) |
| `ALLOW_TOKEN_IN_URL` | `true` | czy `?token=` jest jeszcze akceptowany; ustaw `false` po kroku 3 |

Żadnej nie trzeba ustawiać od razu — domyślne wartości są bezpieczne.

## 5. Czego v1.8.0 NIE naprawia

- **Częściowe zamknięcie pozycji nie istnieje w API Capital.com.** `DELETE /positions/{dealId}`
  nie przyjmuje rozmiaru, `PUT` zmienia tylko stop/limit (sprawdzone w oficjalnej kolekcji
  Postman `capital-com-sv/capital-api-postman`). Każda zmiana wielkości — `REDUCE` i korekta
  roli — to zamknij+otwórz i drugi spread. Dlatego bot rusza pozycję dopiero przy odchyleniu
  ponad `SIZE_TOL`, a nie przy każdym biegu.
- **Koszyk SHORT nie jest handlowany i nie będzie.** Rachunek Capital.com nie pozwala
  otwierać pozycji krótkich na CFD na akcje (potwierdzone 7.09.2026), więc tryb `classic`
  jest niedostępny — to ograniczenie rachunku, nie ustawienie do przełączenia. Konsekwencja:
  rachunek zbiera wyłącznie alfę strony długiej, a spread LONG−SHORT jest metryką z definicji
  nieosiągalną. Za W3 to była różnica między +1,32 p.p. na papierze a −1,61 p.p. na rachunku.
  Jedyną otwartą decyzją konstrukcyjną zostaje `HEDGE_RATIO` — reguła jej zmiany jest
  zadeklarowana z góry w `docs/metoda.md`, sekcja 10, żeby nie tuningować na szumie.
- **Luka rotacyjna.** Raport liczy od zamknięcia piątku, bot rotuje w poniedziałek 9:15.
  Poniedziałkowa luka otwarcia jest kosztem, którego model nie widzi.
