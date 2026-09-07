# Wdrożenie v1.8.x — co trzeba zrobić ręcznie

Stan na 7.09.2026 po wdrożeniu v1.8.1: punkty 1 i 2 są ROZSTRZYGNIĘTE, do zrobienia zostają 3, 4 i przesunięcie porannego crona (punkt 2).

Zmiany w kodzie wchodzą same przy najbliższym deployu na Renderze. Poniższe kroki
wymagają Twojej ręki — bez nich część poprawek nie zadziała.

## 1. Wyrównanie ekspozycji — ZROBIONE 7.09.2026

Po wdrożeniu v1.8.1 `/status` pokazał ekspozycję netto **−79 PLN = −2,7% kapitału**
(było −1 077 PLN = −36,7%). Wszystkie pięć longów jest otwartych, PGE zostało
przeskalowane z 12 na 22,4 szt. (291 PLN, dokładnie cel). Hedge 0,37 kontraktu
= 1 519 PLN naprzeciw 1 439 PLN longów — odchyłka 5,5%, poniżej progu
`HEDGE_TOL`, więc bot słusznie go nie rusza. **Nie ma tu nic do zrobienia ręcznie.**

Stan sprzed poprawki, dla historii (po biegu 9:15, z `leveraged_trades_history` i logu Rendera):

| pozycja | wielkość | wartość |
|---|---|---|
| PEKAO (PEO) | +1,1 | ~291 PLN |
| PGE | +12 | ~156 PLN (rozmiar taktyczny, powinno być ~293) |
| WIG20 (FW2020U2026) | −0,37 | ~1 523 PLN |
| **ekspozycja netto** | | **−1 077 PLN = −36,7% kapitału** |

Bot uznawał to za pozycję neutralną, bo hedge liczył od koszyka docelowego (5 × 293 = 1 466 PLN),
a nie od tego, co realnie weszło.

## 2. Dlaczego PKNORLEN, PZU i MBANK nie weszły — ROZSTRZYGNIĘTE 7.09.2026

Odpowiedź z `/status` po wdrożeniu, przez eliminację:

1. **To nie była minimalna wielkość.** Diagnostyka pokazała `min_wielkosc: 0.1`
   dla wszystkich nóg (min. wartość pozycji 1,3–26 PLN przy tolerancji 466 PLN),
   a MBANK wszedł przy 0,2. Hipoteza o `minDealSize` odpada.
2. **To nie był błąd API.** Gdyby `market()` rzuciło wyjątkiem, wpis trafiłby do
   `błędy`, nie do `pominiete`. Log z 7.09 mówi `pominięte: 4`.
3. Zostaje jedyna ścieżka, która wrzuca do `pominiete` bez wyjątku i bez
   problemu z wielkością: **`status_rynku` inny niż `TRADEABLE`**.

Czyli o 9:15 CEST Capital.com nie miał jeszcze polskich CFD na akcje jako
zbywalnych, mimo że GPW otwiera się o 9:00. Zamknięcia starego koszyka
przeszły (te nie wymagają otwarcia rynku w tym samym sensie), otwarcia nie —
i rachunek został z pełnym hedgem naprzeciw dwóch nóg aż do biegu
doganiającego o 13:05.

**Zalecenie: przesuń poranny `/run` z 9:15 na ok. 10:00 CEST.** Bieg 13:05
zostaje jako siatka bezpieczeństwa. Bez tej zmiany każda poniedziałkowa
rotacja będzie powtarzać ten sam schemat: zamknięcia rano, otwarcia dopiero
po południu, a pomiędzy nimi kilka godzin ekspozycji netto, której nikt nie
zamierzał.

## 3. Token poza URL

Dziś `RUN_TOKEN` jedzie w query stringu i **ląduje w logach Rendera w postaci jawnej** —
każdy z dostępem do logów przejmuje kontrolę nad botem. Kolejność działań:

1. Zmień `RUN_TOKEN` na Renderze na nową wartość (stary uznaj za spalony — był w logach,
   które trafiły też poza Render).
2. W cron-job.org, w każdym zadaniu (`/generate?mode=daily`, `/generate?mode=weekly`, `/run`),
   usuń `?token=...` z URL i dodaj nagłówek:
   `X-Run-Token: <nowy token>`
   (zakładka „Headers" w edycji zadania; alternatywnie `Authorization: Bearer <token>`).
3. Sprawdź, że biegi przechodzą (`/health` + log Rendera, filtr `BOT |`).
4. Dopiero wtedy ustaw na Renderze `ALLOW_TOKEN_IN_URL=false` — od tego momentu wariant
   z URL jest odrzucany.

Kroki 1–3 i 4 muszą iść w tej kolejności, inaczej bot zamilknie w locie.

## 4. Nowe zmienne środowiskowe

| zmienna | domyślnie | znaczenie |
|---|---|---|
| `SIZE_TOL` | `0.35` | dopuszczalne odchylenie wielkości otwartej pozycji od celu, zanim bot ją przeskaluje (zamknij+otwórz, drugi spread) |
| `ALLOW_TOKEN_IN_URL` | `true` | czy `?token=` jest jeszcze akceptowany; ustaw `false` po kroku 3 |

Do **usunięcia** z Rendera (v1.8.1 ich nie czyta): `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.

Żadnej nie trzeba ustawiać od razu — domyślne wartości są bezpieczne.

## 5. Czego v1.8.x NIE naprawia

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
- **Luka rotacyjna.** Raport liczy od zamknięcia piątku, bot rotuje w poniedziałek rano.
  Poniedziałkowa luka otwarcia jest kosztem, którego model nie widzi.
- **Limit zapytań Capital.com.** v1.8.1 dostał pamięć podręczną notowań na czas żądania
  i ponowienia przy HTTP 429, ale broker nadal dławi serie. Nie odpytuj `/status` w pętli.
