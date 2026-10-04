# Poprawki wykonania (3.10.2026) — zmienne i zasady

Źródło: analiza historii transakcji Capital.com 26.08–2.10.2026 i logów Rendera. **Nie zmieniają strategii**
(`HEDGE_RATIO`, selekcja, wagi — patrz `docs/metoda.md`, sekcja 10), tylko wykonanie.

| Problem w danych | Poprawka w `app.py` |
|---|---|
| Kontrakt FW2020U2026 wygasł 18.09 16:13 UTC, nowy hedge dopiero 21.09 08:01 (weekend bez hedge'u) | **Auto-roll**: kontrakt kwartalny H/M/U/Z, wygasa w 3. piątek miesiąca, przejście `HEDGE_ROLL_DAYS`=2 dni wcześniej. Przejście tylko na kontrakt z ceną i statusem TRADEABLE; fallback = poprzedni kwartał (jeśli nie wygasa dziś); hedge stojący na nowym kontrakcie nie wraca na stary |
| Rachunek -8,4% kapitału krótki 28.09–1.10 (odchyłka 28% < `HEDGE_TOL` 0,30) | `HEDGE_TOL` domyślnie **0,10**; korekta tylko gdy zmienia się też liczba kontraktów (krok 0,01 ≈ 40 PLN bywa większy niż 10% celu) |
| Przeskalowanie (REDUCE/korekta) = zamknij+otwórz; nieudane otwarcie zostawiało pozycję zerową | Wykonalność liczona **przed** zamknięciem; gdy nie wejdzie — pozycja bez zmian i wpis w `pominiete` |
| 9.09 ReadTimeout przerwał cały bieg | Ponowienia GET/logowania (`NET_RETRIES`=3, budżet `NET_BUDGET_S`=60 s); wyjątki sieciowe przy `open`/`close`/rynkach nie przerywają biegu |
| Timeout przy zleceniu nie mówi, czy zlecenie doszło | `open`/`close` uzgadniają stan z listą pozycji; gdy się nie da — epic jest „niepewny" i **nie jest ponawiany w tym biegu** (brak duplikatu) |
| Cron 7 dni w tygodniu → odrzucone zlecenia w weekendy | `SKIP_WEEKEND_RUNS`=true: sobota/niedziela (Europe/Warsaw) bez akcji |
| LPP (min. pozycja ~2 470 PLN) nigdy nie wchodzi, brak alarmu | `pokrycie_koszyka` w logu (`⚠ pokrycie koszyka LONG: 3/5 …`, poziom WARNING) i w `/status`; nogi wykluczone przez puls (CLOSE) nie są „brakujące" |
| Token cron-job.org w logu dostępu gunicorna | `gunicorn.conf.py`: log bez query stringu (**token już ujawniony — zmień go**) |

## Własność pozycji hedge'u
Bot zarządza tylko kontraktami od `HEDGE_EPIC` do kontraktu obowiązującego dziś (`rodzina_hedge`). Pozycje na innych
terminach (np. ręczne) nie są ruszane. Hedge nie jest zmieniany, gdy: brakuje wyceny którejś trzymanej nogi, rynek hedge'u
nie jest TRADEABLE, albo stary kontrakt nie dał się zamknąć (unikamy podwójnego shorta).

## Do decyzji właściciela (poza zakresem poprawek wykonania)
* **Filtr wykonalności rankingu.** Spółka, której minimalna pozycja przekracza `ALLOC_PCT × MAX_OVERSHOOT` kapitału, nigdy
  nie wejdzie do portfela, a model i tak jej „kibicuje" (LPP w W6, W7). Wybór TOP5 spośród spółek możliwych do kupienia
  zmienia model, więc wymaga decyzji i zapisu w `docs/metoda.md`.
* Przegląd `HEDGE_RATIO` po 12 zamkniętych oknach — bez zmian (sekcja 10 metody).

## Nowe zmienne środowiskowe
`HEDGE_AUTO_ROLL` (true), `HEDGE_ROLL_DAYS` (2), `SKIP_WEEKEND_RUNS` (true), `NET_RETRIES` (3), `NET_BUDGET_S` (60);
zmieniony domyślny `HEDGE_TOL` (0,10). Testy: `python3 tests/test_hedge.py` i `python3 tests/test_roll.py`.
