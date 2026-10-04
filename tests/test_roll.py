# -*- coding: utf-8 -*-
"""Testy poprawek wykonawczych app.py z 3.10.2026 (commit 022f660).

Uruchomienie (bez pytest, sam stdlib):   python3 tests/test_roll.py

Pokrycie:
  1. kalendarz kontraktów FW2020 (trzeci piątek H/M/U/Z, przejście roczne);
  2. przejście hedge'u na kolejny kontrakt (sync) — w dniu przejścia, po
     wygaśnięciu, z fallbackiem, bez podwójnego shorta;
  3. przeskalowanie pozycji dopiero, gdy nowa wielkość jest wykonalna;
  4. pomijanie weekendów;
  5. ponowienia sieci (GET/logowanie) i brak wyjątków przy POST/DELETE;
  6. pokrycie koszyka LONG (przypadek LPP);
  7. HEDGE_TOL 0.10 wobec 0.30 (28.09-1.10.2026: longi 888 vs hedge 1136).

Brokerem jest atrapa; żadne zapytanie nie wychodzi do sieci. Konfigurację
środowiska ustawiamy PRZED importem app (moduł czyta env na poziomie modułu),
tak samo jak test_hedge.py, a każdy bieg sync() dodatkowo wymusza potrzebne
wartości przez mock.patch.object — testy nie zależą od kolejności importu.
"""
import calendar
import contextlib
import datetime as dt
import json
import math
import os
import re
import sys
import unittest
from unittest import mock
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.update({
    "DRY_RUN": "true", "CAPITAL_DEMO": "true", "RUN_TOKEN": "test-token",
    "HEDGE_EPIC": "FW2020U2026", "HEDGE_RATIO": "1.0", "HEDGE_TOL": "0.30",
    "ALLOC_PCT": "0.10", "TACTICAL_ALLOC_PCT": "0.05", "SIZE_TOL": "0.35",
    "START_EQUITY": "1000", "KILL_LEVEL": "0.75", "TELEGRAM_BOT_TOKEN": "",
    "SKIP_WEEKEND_RUNS": "false", "HEDGE_AUTO_ROLL": "false",
})
import requests  # noqa: E402
import app  # noqa: E402

WAW = ZoneInfo("Europe/Warsaw")
EQUITY = 2931.11

U26, Z26, H27 = "FW2020U2026", "FW2020Z2026", "FW2020H2027"

# Daty (2026-09-18 to trzeci piątek września = wygaśnięcie U2026).
D_PRZED = dt.date(2026, 9, 15)      # wtorek, kontrakt U jeszcze obowiązuje
D_ROLL = dt.date(2026, 9, 16)       # środa, dzień przejścia (wygaśnięcie − 2 dni)
D_WYGAS = dt.date(2026, 9, 18)      # piątek, dzień wygaśnięcia U2026
D_PO = dt.date(2026, 9, 21)         # poniedziałek po wygaśnięciu
D_SOBOTA = dt.date(2026, 10, 3)     # sobota (data piaskownicy)
D_PO2 = dt.date(2026, 10, 5)        # poniedziałek

SYGNALY = {
    "version": "2026-W8", "status": "AKTUALNA",
    "long": ["PKNORLEN", "PGE", "PEKAO", "PZU", "MBANK"],
    "short": ["KRUK", "PEPCO", "CDPROJEKT", "KETY", "MODIVO"],
    "exclude": [], "tactical": [],
    "epics": {"PKNORLEN": "PKN", "PGE": "PGE", "PEKAO": "PEO", "PZU": "PZU",
              "MBANK": "MBK", "KRUK": "KRU", "PEPCO": "PCOP",
              "CDPROJEKT": "CDR", "KETY": "KTY", "MODIVO": "MDVP",
              "LPP": "LPP"},
}
SYGNALY_LPP = dict(SYGNALY,
                   long=["PKNORLEN", "PGE", "PEKAO", "PZU", "LPP"])

CENY = {"PKN": 159.26, "PGE": 12.96, "PEO": 264.10, "PZU": 76.34,
        "MBK": 1420.50, "LPP": 24700.0,
        U26: 4116.17, Z26: 4130.00, H27: 4150.00}


def poz(epic, direction, size, deal=None):
    return {"dealId": deal or f"d-{epic}", "epic": epic, "name": epic,
            "direction": direction, "size": size, "upl": 0.0}


def pelny_koszyk():
    """Pięć nóg LONG w wielkości docelowej (~293 PLN każda, razem ~1465)."""
    return [poz("PKN", "BUY", 1.84), poz("PGE", "BUY", 22.6),
            poz("PEO", "BUY", 1.11), poz("PZU", "BUY", 3.84),
            poz("MBK", "BUY", 0.206)]


def hedge_stan(cap):
    """Pozycje SELL z rodziny FW2020 FAKTYCZNIE na rachunku atrapy."""
    return [p for p in cap.stan
            if p["epic"].startswith("FW2020") and p["direction"] == "SELL"]


class FakeCapital:
    """Broker-atrapa ze stanem: open/close zmieniają listę pozycji.

    blad_rynku  — {epic: wyjątek}, który zgłasza market(epic);
    status      — {epic: status rynku}; zlecenie na nietradeable odrzucane;
    zamkniecie_odrzucone / otwarcie_odrzucone — deal-id / epiki odrzucane.
    """

    def __init__(self, pozycje, ceny=None, min_deal=None, status=None,
                 blad_rynku=None, zamkniecie_odrzucone=(),
                 otwarcie_odrzucone=()):
        self.stan = [dict(p) for p in pozycje]
        self._ceny = dict(CENY)
        self._ceny.update(ceny or {})
        self._min = min_deal or {}
        self._status = status or {}
        self._blad = blad_rynku or {}
        self._zamk_odrz = set(zamkniecie_odrzucone)
        self._otw_odrz = set(otwarcie_odrzucone)
        self.switch_error = None
        self.otwarte = []        # WSZYSTKIE próby otwarcia (także odrzucone)
        self.zamkniete = []      # WSZYSTKIE próby zamknięcia
        self._n = 0

    def login(self):
        pass

    def equity(self):
        return EQUITY, "PLN", "acc-1"

    def accounts(self):
        return [{"accountId": "acc-1", "accountName": "demo", "currency": "PLN",
                 "balance": {"balance": EQUITY, "profitLoss": 0.0},
                 "preferred": True}]

    def positions(self):
        return [dict(p) for p in self.stan]

    def market(self, epic, odswiez=False):
        if epic in self._blad:
            raise self._blad[epic]
        if epic not in self._ceny:
            raise requests.HTTPError(f"404 nie ma rynku {epic}")
        return {"epic": epic, "name": epic, "currency": "PLN",
                "status": self._status.get(epic, "TRADEABLE"),
                "mid": self._ceny[epic],
                "min": self._min.get(
                    epic, 0.01 if epic.startswith("FW2020") else 0.1)}

    def fx_rate(self, a, b):
        return 1.0

    def open(self, epic, direction, size):
        self.otwarte.append((epic, direction, size))
        if (epic in self._otw_odrz
                or self._status.get(epic, "TRADEABLE") != "TRADEABLE"):
            return False, None, "ODRZUCONO przez brokera: rynek zamknięty"
        self._n += 1
        self.stan.append(poz(epic, direction, size, deal=f"nowy-{self._n}"))
        return True, f"ref-{self._n}", "potwierdzono"

    def close(self, deal_id):
        self.zamkniete.append(deal_id)
        if deal_id in self._zamk_odrz:
            return False, "odrzucono zamknięcie"
        self.stan = [p for p in self.stan if p["dealId"] != deal_id]
        return True, "ok"


def o_godz(data, g=9, m=15):
    return dt.datetime(data.year, data.month, data.day, g, m, tzinfo=WAW)


def uruchom(cap, data=D_PRZED, sygnaly=None, auto_roll=False,
            hedge_epic=U26, tol=0.10, dry_run=False, skip_weekend=False):
    """Jeden bieg sync() z wymuszoną konfiguracją; zwraca (rep, powiadomienia)."""
    powiadomienia = []

    def _notify(tekst, poziom="info"):
        powiadomienia.append((poziom, tekst))

    sygn = dict(sygnaly or SYGNALY)
    with contextlib.ExitStack() as st:
        for nazwa, wartosc in (("HEDGE_AUTO_ROLL", auto_roll),
                               ("HEDGE_EPIC", hedge_epic),
                               ("HEDGE_TOL", tol),
                               ("HEDGE_ROLL_DAYS", 2),
                               ("DRY_RUN", dry_run),
                               ("SKIP_WEEKEND_RUNS", skip_weekend)):
            st.enter_context(mock.patch.object(app, nazwa, wartosc))
        st.enter_context(mock.patch.object(app, "Capital", lambda: cap))
        st.enter_context(mock.patch.object(
            app, "load_signals", lambda: (dict(sygn), "sha")))
        st.enter_context(mock.patch.object(app, "notify", _notify))
        st.enter_context(mock.patch.object(
            app, "teraz_warszawa", lambda: o_godz(data)))
        st.enter_context(mock.patch.object(app.time, "sleep", lambda *_: None))
        rep = app.sync()
    return rep, powiadomienia


# ----------------------------------------------------------------------------
# 1. KALENDARZ KONTRAKTÓW
# ----------------------------------------------------------------------------
class TestKalendarzKontraktow(unittest.TestCase):

    def test_trzeci_piatek_wrzesnia_2026(self):
        # 18.09.2026 — dzień wygaśnięcia FW2020U2026 z logów produkcyjnych
        self.assertEqual(app.trzeci_piatek(2026, 9), dt.date(2026, 9, 18))

    def test_trzeci_piatek_grudnia_2026(self):
        self.assertEqual(app.trzeci_piatek(2026, 12), dt.date(2026, 12, 18))

    def test_trzeci_piatek_marca_2027(self):
        self.assertEqual(app.trzeci_piatek(2027, 3), dt.date(2027, 3, 19))

    def test_trzeci_piatek_gdy_pierwszy_dzien_miesiaca_to_piatek(self):
        # 1.01.2027 to piątek => trzeci piątek to 15., nie 22.
        self.assertEqual(dt.date(2027, 1, 1).weekday(), 4)
        self.assertEqual(app.trzeci_piatek(2027, 1), dt.date(2027, 1, 15))

    def test_trzeci_piatek_zgodny_z_kalendarzem_dla_wszystkich_miesiecy(self):
        for rok in range(2026, 2033):
            for mies in range(1, 13):
                piatki = [tyg[calendar.FRIDAY]
                          for tyg in calendar.monthcalendar(rok, mies)
                          if tyg[calendar.FRIDAY]]
                self.assertEqual(app.trzeci_piatek(rok, mies),
                                 dt.date(rok, mies, piatki[2]),
                                 f"{rok}-{mies:02d}")

    def test_wygasniecie_i_parsowanie(self):
        self.assertEqual(app.parsuj_kontrakt(U26), ("FW2020", 9, 2026))
        self.assertEqual(app.wygasniecie_kontraktu(U26), dt.date(2026, 9, 18))
        self.assertIsNone(app.parsuj_kontrakt("WIG20"))
        self.assertIsNone(app.wygasniecie_kontraktu("OFF"))
        self.assertIsNone(app.parsuj_kontrakt(""))
        self.assertIsNone(app.parsuj_kontrakt(None))

    def test_nastepny_kontrakt_w_cyklu_HMUZ_z_przejsciem_roku(self):
        self.assertEqual(app.nastepny_kontrakt("FW2020H2027"), "FW2020M2027")
        self.assertEqual(app.nastepny_kontrakt("FW2020M2027"), "FW2020U2027")
        self.assertEqual(app.nastepny_kontrakt(U26), Z26)
        self.assertEqual(app.nastepny_kontrakt(Z26), H27)

    def test_kontrakt_obowiazujacy_na_granicy_przejscia(self):
        # dzis < wygasniecie − 2 dni => stary; od środy 16.09 => nowy
        with mock.patch.object(app, "HEDGE_ROLL_DAYS", 2):
            self.assertEqual(app.kontrakt_obowiazujacy(U26, dt.date(2026, 9, 14)),
                             (U26, None))
            self.assertEqual(app.kontrakt_obowiazujacy(U26, D_PRZED),
                             (U26, None))
            self.assertEqual(app.kontrakt_obowiazujacy(U26, D_ROLL), (Z26, U26))
            self.assertEqual(app.kontrakt_obowiazujacy(U26, D_WYGAS), (Z26, U26))
            self.assertEqual(app.kontrakt_obowiazujacy(U26, D_PO), (Z26, U26))
            self.assertEqual(app.kontrakt_obowiazujacy(U26, D_SOBOTA), (Z26, U26))

    def test_kontrakt_bazowy_juz_aktualny_nie_zwraca_poprzedniego(self):
        with mock.patch.object(app, "HEDGE_ROLL_DAYS", 2):
            self.assertEqual(app.kontrakt_obowiazujacy(Z26, dt.date(2026, 10, 5)),
                             (Z26, None))
            self.assertEqual(app.kontrakt_obowiazujacy(Z26, dt.date(2026, 12, 15)),
                             (Z26, None))

    def test_kontrakt_obowiazujacy_przez_granice_roku(self):
        with mock.patch.object(app, "HEDGE_ROLL_DAYS", 2):
            # Z2026 wygasa 18.12.2026: 15.12 jeszcze Z, od 16.12 H2027 (rok+1)
            self.assertEqual(app.kontrakt_obowiazujacy(U26, dt.date(2026, 12, 15)),
                             (Z26, U26))
            self.assertEqual(app.kontrakt_obowiazujacy(U26, dt.date(2026, 12, 16)),
                             (H27, U26))
            self.assertEqual(app.kontrakt_obowiazujacy(Z26, dt.date(2026, 12, 16)),
                             (H27, Z26))
            # config nigdy nieaktualizowany: styczeń 2027 => H2027
            self.assertEqual(app.kontrakt_obowiazujacy(U26, dt.date(2027, 1, 10)),
                             (H27, U26))
            # H2027 wygasa 19.03.2027: od 17.03 M2027
            self.assertEqual(app.kontrakt_obowiazujacy(Z26, dt.date(2027, 3, 16)),
                             (H27, Z26))
            self.assertEqual(app.kontrakt_obowiazujacy(Z26, dt.date(2027, 3, 17)),
                             ("FW2020M2027", Z26))

    def test_parametr_dni_przed_i_HEDGE_ROLL_DAYS(self):
        self.assertEqual(app.kontrakt_obowiazujacy(U26, dt.date(2026, 9, 17), 0),
                         (U26, None))
        self.assertEqual(app.kontrakt_obowiazujacy(U26, D_WYGAS, 0), (Z26, U26))
        with mock.patch.object(app, "HEDGE_ROLL_DAYS", 5):
            self.assertEqual(app.kontrakt_obowiazujacy(U26, dt.date(2026, 9, 12)),
                             (U26, None))
            self.assertEqual(app.kontrakt_obowiazujacy(U26, dt.date(2026, 9, 13)),
                             (Z26, U26))

    def test_epic_nie_bedacy_kontraktem_zostaje_bez_zmian(self):
        self.assertEqual(app.kontrakt_obowiazujacy("WIG20", D_PO), ("WIG20", None))
        self.assertEqual(app.kontrakt_obowiazujacy("OFF", D_PO), ("OFF", None))


# ----------------------------------------------------------------------------
# 2. PRZEJŚCIE HEDGE'U NA KOLEJNY KONTRAKT
# ----------------------------------------------------------------------------
class TestPrzejscieNaKolejnyKontrakt(unittest.TestCase):

    def _cap(self, **kw):
        return FakeCapital(
            pelny_koszyk() + [poz(U26, "SELL", 0.35, deal="d-hedge-U")], **kw)

    def test_dzien_przejscia_stary_zamkniety_nowy_otwarty_bez_podwojnego_hedgeu(self):
        cap = self._cap()
        rep, _ = uruchom(cap, data=D_ROLL, auto_roll=True)

        self.assertEqual(cap.zamkniete, ["d-hedge-U"])
        self.assertEqual(cap.otwarte, [(Z26, "SELL", 0.35)])
        self.assertEqual([(p["epic"], p["size"]) for p in hedge_stan(cap)],
                         [(Z26, 0.35)], "na rachunku ma zostać JEDEN short")
        info = rep["hedge_kontrakt"]
        self.assertEqual(info["epic"], Z26)
        self.assertEqual(info["rolowany_z"], U26)
        self.assertEqual(info["konfiguracja"], U26)
        self.assertEqual(rep["hedge"]["epic"], Z26)
        self.assertEqual(rep["błędy"], [])

    def test_dzien_przejscia_tryb_dry_run(self):
        cap = self._cap()
        rep, _ = uruchom(cap, data=D_ROLL, auto_roll=True, dry_run=True)
        akcje = " | ".join(rep["akcje"])
        self.assertIn(f"[DRY] ZAMKNIJ SELL {U26}", akcje)
        self.assertIn(f"przejście na kontrakt {Z26}", akcje)
        self.assertIn(f"[DRY] HEDGE SELL {Z26} size 0.35", akcje)
        self.assertEqual((cap.otwarte, cap.zamkniete), ([], []),
                         "DRY_RUN nie rusza brokera")

    def test_dzien_przed_przejsciem_nic_sie_nie_dzieje(self):
        cap = self._cap()
        rep, _ = uruchom(cap, data=D_PRZED, auto_roll=True)
        self.assertEqual((cap.otwarte, cap.zamkniete), ([], []))
        self.assertEqual(rep["hedge"]["epic"], U26)
        self.assertNotIn("rolowany_z", rep["hedge_kontrakt"])

    def test_kolejne_biegi_sa_stabilne_przez_wygasniecie_i_po_nim(self):
        """Dzień przejścia → wygaśnięcie → poniedziałek → październik: jeden hedge."""
        cap = self._cap()
        uruchom(cap, data=D_ROLL, auto_roll=True)
        po_pierwszym = (len(cap.otwarte), len(cap.zamkniete))
        for dzien in (D_ROLL, dt.date(2026, 9, 17), D_WYGAS, D_PO, D_PO2):
            with self.subTest(dzien=str(dzien)):
                uruchom(cap, data=dzien, auto_roll=True)
                self.assertEqual((len(cap.otwarte), len(cap.zamkniete)),
                                 po_pierwszym, "powtórny bieg nie ma handlować")
                self.assertEqual([p["epic"] for p in hedge_stan(cap)], [Z26])

    def test_przejscie_na_przelomie_roku_Z2026_na_H2027(self):
        cap = FakeCapital(
            pelny_koszyk() + [poz(Z26, "SELL", 0.35, deal="d-hedge-Z")])
        rep, _ = uruchom(cap, data=dt.date(2026, 12, 16), auto_roll=True)
        self.assertEqual(cap.zamkniete, ["d-hedge-Z"])
        self.assertEqual(cap.otwarte, [(H27, "SELL", 0.35)])
        self.assertEqual([p["epic"] for p in hedge_stan(cap)], [H27])
        self.assertEqual(rep["hedge_kontrakt"]["rolowany_z"], U26)

    # ---- fallback ----------------------------------------------------------
    def test_nowy_kontrakt_niedostepny_w_api_fallback_na_stary_dopoki_zyje(self):
        bledy = {
            "HTTPError 404": requests.HTTPError("404 not found"),
            "ReadTimeout (po wyczerpaniu ponowień)":
                requests.exceptions.ReadTimeout("t"),
            "ConnectionError": requests.exceptions.ConnectionError("c"),
        }
        for opis, wyjatek in bledy.items():
            for dzien in (D_ROLL, dt.date(2026, 9, 17)):
                with self.subTest(blad=opis, dzien=str(dzien)):
                    cap = self._cap(blad_rynku={Z26: wyjatek})
                    rep, _ = uruchom(cap, data=dzien, auto_roll=True)
                    self.assertEqual((cap.zamkniete, cap.otwarte), ([], []),
                                     "hedge na starym kontrakcie ma zostać")
                    self.assertEqual(rep["hedge"]["epic"], U26)
                    self.assertEqual(rep["hedge_kontrakt"]["fallback"], U26)
                    self.assertIn(Z26, rep["hedge_kontrakt"]["odrzucone"])
                    self.assertTrue(
                        any(Z26 in b and "niedostępny" in b
                            for b in rep["błędy"]),
                        f"fallback musi być głośny: {rep['błędy']}")
                    self.assertEqual([p["epic"] for p in hedge_stan(cap)], [U26])

    def test_nowy_kontrakt_bez_ceny_to_tez_fallback(self):
        cap = self._cap(ceny={Z26: None})
        rep, _ = uruchom(cap, data=D_ROLL, auto_roll=True)
        self.assertEqual((cap.zamkniete, cap.otwarte), ([], []))
        self.assertEqual(rep["hedge_kontrakt"]["fallback"], U26)
        self.assertEqual(rep["hedge_kontrakt"]["odrzucone"][Z26], "brak ceny")

    def test_oba_kontrakty_niedostepne_hedge_nietkniety_i_blad_zgloszony(self):
        cap = self._cap(blad_rynku={Z26: requests.HTTPError("404"),
                                    U26: requests.HTTPError("404")})
        rep, pow_ = uruchom(cap, data=D_ROLL, auto_roll=True)
        self.assertEqual((cap.zamkniete, cap.otwarte), ([], []))
        self.assertEqual([p["dealId"] for p in hedge_stan(cap)], ["d-hedge-U"])
        self.assertIsNone(rep["hedge_kontrakt"]["epic"])
        self.assertNotIn("hedge", rep)
        self.assertTrue(any("brak dostępnego kontraktu" in b
                            and "NIETKNIĘTE" in b for b in rep["błędy"]),
                        rep["błędy"])
        self.assertEqual(pow_[-1][0], "warning", "bieg z błędem = WARNING")

    def test_po_wygasnieciu_stary_nie_jest_kandydatem_gdy_nowy_niedostepny(self):
        # 21.09: U2026 już nie istnieje, Z2026 chwilowo bez rynku. Nie wolno
        # wracać do wygasłego kontraktu — brak hedge'u ma być zgłoszony.
        cap = FakeCapital(pelny_koszyk(), blad_rynku={Z26: requests.HTTPError("404")})
        rep, _ = uruchom(cap, data=D_PO, auto_roll=True)
        self.assertEqual(cap.otwarte, [])
        self.assertNotIn("fallback", rep["hedge_kontrakt"])
        self.assertTrue(any("brak dostępnego kontraktu" in b
                            for b in rep["błędy"]))

    def test_nowy_kontrakt_niehandlowalny_nie_kasuje_zywego_hedgeu(self):
        """Zamknięcie U ma sens tylko, gdy Z da się otworzyć.

        Rynek Z jest w API i ma cenę, ale status ≠ TRADEABLE (broker odrzuci
        zlecenie). Zamknięcie U przed próbą otwarcia Z zostawia rachunek bez
        zabezpieczenia — ten sam mechanizm co przy przeskalowaniu pozycji
        (zamknij+otwórz bez sprawdzenia wykonalności)."""
        cap = self._cap(status={Z26: "CLOSED"})
        uruchom(cap, data=D_ROLL, auto_roll=True)
        self.assertEqual(
            len(hedge_stan(cap)), 1,
            f"rachunek ma mieć dokładnie jeden hedge; zamknięcia={cap.zamkniete} "
            f"próby otwarcia={cap.otwarte}")

    # ---- po wygaśnięciu ----------------------------------------------------
    def test_po_wygasnieciu_config_nadal_U2026_bez_hedgeu_otwiera_hedge_na_Z2026(self):
        for dzien, dni in ((D_SOBOTA, 76), (D_PO2, 74)):
            with self.subTest(dzien=str(dzien)):
                cap = FakeCapital(pelny_koszyk())      # broker zamknął U sam
                rep, _ = uruchom(cap, data=dzien, auto_roll=True)
                self.assertEqual(cap.zamkniete, [])
                self.assertEqual(cap.otwarte, [(Z26, "SELL", 0.35)])
                self.assertEqual(rep["hedge_kontrakt"]["epic"], Z26)
                self.assertEqual(rep["hedge_kontrakt"]["rolowany_z"], U26)
                self.assertEqual(rep["hedge_kontrakt"]["dni_do_wygasniecia"], dni)
                self.assertEqual(rep["błędy"], [])
                self.assertEqual(rep["hedge"]["biezacy"], 0.0)

    def test_auto_roll_wylaczony_ostrzega_i_zostaje_przy_konfiguracji(self):
        cap = self._cap()
        rep, _ = uruchom(cap, data=D_ROLL, auto_roll=False)
        self.assertEqual((cap.zamkniete, cap.otwarte), ([], []))
        info = rep["hedge_kontrakt"]
        self.assertEqual(info["epic"], U26)
        self.assertIn("wygasa 2026-09-18", info["ostrzezenie"])
        self.assertTrue(any("HEDGE_AUTO_ROLL=false" in b for b in rep["błędy"]))

    def test_auto_roll_wylaczony_ostrzezenie_dopiero_blisko_wygasniecia(self):
        # próg: dni <= HEDGE_ROLL_DAYS + 3 = 5
        for dzien, ostrzega in ((dt.date(2026, 9, 10), False),
                                (dt.date(2026, 9, 13), True)):
            with self.subTest(dzien=str(dzien)):
                rep, _ = uruchom(self._cap(), data=dzien, auto_roll=False)
                self.assertEqual("ostrzezenie" in rep["hedge_kontrakt"], ostrzega)

    def test_epic_indeksu_bez_terminu_nie_jest_rolowany(self):
        cap = FakeCapital(pelny_koszyk() + [poz("WIG20", "SELL", 0.35)],
                          ceny={"WIG20": 4000.0})
        rep, _ = uruchom(cap, data=D_PO2, auto_roll=True, hedge_epic="WIG20")
        self.assertEqual(rep["hedge_kontrakt"]["epic"], "WIG20")
        self.assertNotIn("rolowany_z", rep["hedge_kontrakt"])
        self.assertEqual(cap.otwarte, [])

    # ---- błędy zamykania i otwierania ---------------------------------------
    def test_nieudane_zamkniecie_starego_hedgeu_nowego_nie_otwiera(self):
        cap = self._cap(zamkniecie_odrzucone={"d-hedge-U"})
        rep, pow_ = uruchom(cap, data=D_ROLL, auto_roll=True)
        self.assertEqual(cap.zamkniete, ["d-hedge-U"])
        self.assertEqual(cap.otwarte, [], "nie wolno otworzyć drugiego shorta")
        self.assertEqual([p["epic"] for p in hedge_stan(cap)], [U26])
        self.assertTrue(any("nie udało się zamknąć starego kontraktu" in b
                            and "obecnego nie ruszam" in b
                            for b in rep["błędy"]), rep["błędy"])
        self.assertEqual(pow_[-1][0], "warning")

    def test_w_dniu_wygasniecia_bez_nowego_kontraktu_hedge_nietkniety(self):
        """Kontrakt wygasający DZIŚ nie jest fallbackiem (broker zamknie go
        o 16:13 UTC); gdy następca niedostępny, hedge zostaje nietknięty
        i błąd jest głośny."""
        cap = self._cap(blad_rynku={Z26: requests.HTTPError("404")})
        rep, _ = uruchom(cap, data=D_WYGAS, auto_roll=True)
        self.assertEqual((cap.zamkniete, cap.otwarte), ([], []))
        self.assertIsNone(rep["hedge_kontrakt"]["epic"])
        self.assertTrue(any("brak dostępnego kontraktu" in b
                            for b in rep["błędy"]), rep["błędy"])

    def test_nieudane_zamkniecie_potem_udane_w_nastepnym_biegu(self):
        cap = self._cap(zamkniecie_odrzucone={"d-hedge-U"})
        uruchom(cap, data=D_ROLL, auto_roll=True)
        cap._zamk_odrz.clear()                    # broker już działa
        uruchom(cap, data=D_ROLL, auto_roll=True)
        self.assertEqual([(p["epic"], p["size"]) for p in hedge_stan(cap)],
                         [(Z26, 0.35)])

    def test_czesciowo_nieudane_zamkniecie_dwoch_pozycji_tego_samego_epica(self):
        """Dwa shorty na tym samym kontrakcie (np. po ręcznej dokładce).

        Zamknięcie pierwszego się udaje, drugiego nie. `zamkniete` jest kluczowane
        EPICIEM, więc blok `nie_zamkniete` uznaje obie pozycje za zamknięte
        i otwiera nowy hedge przy żywym starym => podwójny short."""
        cap = FakeCapital(
            pelny_koszyk() + [poz(U26, "SELL", 0.20, deal="d-h1"),
                              poz(U26, "SELL", 0.20, deal="d-h2")],
            zamkniecie_odrzucone={"d-h2"})
        uruchom(cap)       # 0.40 × 4116 = 1646 wobec 1465 => korekta
        lacznie = sum(p["size"] for p in hedge_stan(cap))
        self.assertLessEqual(
            lacznie, 0.35 + 1e-9,
            f"po biegu hedge = {lacznie} kontraktu "
            f"({lacznie * CENY[U26]:.0f} PLN) wobec longów ~1465 PLN: "
            f"nowy short otwarty mimo żywej starej pozycji "
            f"({[(p['dealId'], p['size']) for p in hedge_stan(cap)]})")

    def test_nieudane_otwarcie_nowego_hedgeu_jest_glosne_a_nastepny_bieg_naprawia(self):
        cap = self._cap(otwarcie_odrzucone={Z26})
        rep, pow_ = uruchom(cap, data=D_ROLL, auto_roll=True)
        self.assertEqual(hedge_stan(cap), [])
        self.assertTrue(any("NIEZABEZPIECZONY" in b for b in rep["błędy"]),
                        rep["błędy"])
        self.assertEqual(rep["hedge"]["po_korekcie"], 0.0)
        self.assertEqual(pow_[-1][0], "warning")
        cap._otw_odrz.clear()
        uruchom(cap, data=D_ROLL, auto_roll=True)
        self.assertEqual([(p["epic"], p["size"]) for p in hedge_stan(cap)],
                         [(Z26, 0.35)])


# ----------------------------------------------------------------------------
# 3. PRZESKALOWANIE: NAJPIERW WYKONALNOŚĆ, POTEM ZAMKNIĘCIE
# ----------------------------------------------------------------------------
class TestPrzeskalowanieWykonalnosc(unittest.TestCase):

    def _cap(self, pozycje=None, **kw):
        poz_ = pozycje if pozycje is not None else (
            pelny_koszyk() + [poz(U26, "SELL", 0.35, deal="d-hedge-U")])
        return FakeCapital(poz_, **kw)

    def test_redukcja_niewykonalna_gdy_polowa_ponizej_minimalnej_wielkosci(self):
        # PEKAO: min 1 szt. = 264 PLN > 146,6 × 1,6 = 234,5 PLN => połowy nie ma
        sygn = dict(SYGNALY, exclude=[{"ticker": "PEKAO", "action": "REDUCE",
                                       "reason": "test"}])
        for dry in (False, True):
            with self.subTest(dry_run=dry):
                cap = self._cap(min_deal={"PEO": 1.0})
                rep, _ = uruchom(cap, sygnaly=sygn, dry_run=dry)
                self.assertNotIn("d-PEO", cap.zamkniete)
                self.assertEqual(cap.otwarte, [])
                self.assertEqual(cap.zamkniete, [])
                wpis = [x for x in rep["pominiete"]
                        if "PEKAO" in x and "NIEWYKONALNE" in x]
                self.assertEqual(len(wpis), 1, rep["pominiete"])
                self.assertIn("pozycja bez zmian", wpis[0])
                self.assertFalse(any("PRZESKAL" in a for a in rep["akcje"]))
                # pozycja zostaje w ekspozycji (nie wypada z hedge'u)
                self.assertAlmostEqual(
                    rep["ekspozycja_dluga"]["pozycje"]["PEKAO"], 293.15, delta=0.5)

    def test_korekta_wielkosci_niewykonalna_gdy_rynek_nie_jest_tradeable(self):
        cap = FakeCapital([poz("PGE", "BUY", 12),    # 155 PLN wobec celu 293
                           poz(U26, "SELL", 0.05, deal="d-hedge-U")],
                          status={"PGE": "CLOSED"})
        rep, _ = uruchom(cap)
        self.assertNotIn("d-PGE", cap.zamkniete)
        self.assertEqual([o for o in cap.otwarte if o[0] == "PGE"], [])
        self.assertTrue(any("PGE" in x and "NIEWYKONALNE" in x and "CLOSED" in x
                            for x in rep["pominiete"]), rep["pominiete"])

    def test_korekta_wielkosci_niewykonalna_gdy_minimalna_wielkosc_za_duza(self):
        # PGE: min 40 szt. × 12,96 = 518 PLN > 293,1 × 1,6 = 469 PLN
        cap = FakeCapital([poz("PGE", "BUY", 12),
                           poz(U26, "SELL", 0.05, deal="d-hedge-U")],
                          min_deal={"PGE": 40})
        rep, _ = uruchom(cap)
        self.assertNotIn("d-PGE", cap.zamkniete)
        self.assertEqual([o for o in cap.otwarte if o[0] == "PGE"], [])
        self.assertTrue(any("PGE" in x and "NIEWYKONALNE" in x
                            and "min. wielkość" in x for x in rep["pominiete"]),
                        rep["pominiete"])

    def test_rynek_niedostepny_w_trakcie_sprawdzania_wykonalnosci(self):
        # Gałąź obronna: wartosc_pozycji dostaje cenę (1. odczyt), a calc_size
        # nie (2. odczyt). Prawdziwy Capital.market ma cache, więc w produkcji
        # to się nie zdarza — test pilnuje tylko, że wyjątek nie ucieka.
        cap = FakeCapital([poz("PGE", "BUY", 12),
                           poz(U26, "SELL", 0.05, deal="d-hedge-U")])
        oryg = cap.market
        wywolania = {"PGE": 0}

        def market(epic, odswiez=False):
            if epic == "PGE":
                wywolania["PGE"] += 1
                if wywolania["PGE"] == 2:
                    raise requests.exceptions.ConnectionError("zerwane")
            return oryg(epic, odswiez)

        cap.market = market
        rep, _ = uruchom(cap)
        self.assertNotIn("d-PGE", cap.zamkniete)
        self.assertTrue(any("PGE" in x and "odłożone" in x
                            for x in rep["pominiete"]), rep["pominiete"])

    def test_kontrola_pozytywna_wykonalna_korekta_zamyka_i_otwiera(self):
        cap = FakeCapital([poz("PGE", "BUY", 12),
                           poz(U26, "SELL", 0.05, deal="d-hedge-U")])
        rep, _ = uruchom(cap)
        self.assertIn("d-PGE", cap.zamkniete)
        otw = [o for o in cap.otwarte if o[0] == "PGE"]
        self.assertEqual(len(otw), 1)
        self.assertAlmostEqual(otw[0][2], 22.6, places=2)
        self.assertTrue(any("PRZESKALOWANO PGE" in a for a in rep["akcje"]))
        self.assertEqual(len([p for p in cap.stan if p["epic"] == "PGE"]), 1)

    def test_nieudane_otwarcie_po_zamknieciu_jest_zglaszane(self):
        cap = FakeCapital([poz("PGE", "BUY", 12),
                           poz(U26, "SELL", 0.05, deal="d-hedge-U")],
                          otwarcie_odrzucone={"PGE"})
        rep, _ = uruchom(cap)
        self.assertTrue(any("BŁĄD korekty PGE" in a for a in rep["akcje"]))
        self.assertTrue(rep["błędy"])


# ----------------------------------------------------------------------------
# 4. WEEKENDY
# ----------------------------------------------------------------------------
def _nie_dotykac(*a, **k):
    raise AssertionError("weekendowy bieg dotknął Capital/GitHub")


class TestPomijanieWeekendow(unittest.TestCase):

    def _bieg_pomijany(self, data):
        with mock.patch.object(app, "SKIP_WEEKEND_RUNS", True), \
             mock.patch.object(app, "Capital", _nie_dotykac), \
             mock.patch.object(app, "load_signals", _nie_dotykac), \
             mock.patch.object(app, "teraz_warszawa", lambda: o_godz(data)):
            return app.sync()

    def test_sobota_i_niedziela_nie_dotykaja_brokera(self):
        for dzien in (D_SOBOTA, dt.date(2026, 10, 4)):
            with self.subTest(dzien=str(dzien)):
                rep = self._bieg_pomijany(dzien)
                self.assertIn("pominięto", rep)
                self.assertIn("weekend", rep["pominięto"])
                self.assertNotIn("akcje", rep)

    def test_dzien_roboczy_nie_jest_pomijany(self):
        cap = FakeCapital(pelny_koszyk() + [poz(U26, "SELL", 0.35)])
        rep, _ = uruchom(cap, data=dt.date(2026, 10, 2), skip_weekend=True,
                         dry_run=True)
        self.assertNotIn("pominięto", rep)
        self.assertIn("akcje", rep)

    def test_flaga_wylaczona_weekend_jest_obslugiwany(self):
        cap = FakeCapital(pelny_koszyk() + [poz(U26, "SELL", 0.35)])
        rep, _ = uruchom(cap, data=D_SOBOTA, skip_weekend=False, dry_run=True)
        self.assertNotIn("pominięto", rep)
        self.assertIn("hedge", rep)

    def test_weekend_liczony_wg_czasu_warszawskiego_nie_UTC(self):
        class FakeDT(dt.datetime):
            teraz = None

            @classmethod
            def now(cls, tz=None):
                return cls.teraz.astimezone(tz) if tz else cls.teraz

        utc = dt.timezone.utc
        # piątek 22:30 UTC = sobota 00:30 w Warszawie (CEST) => pomijamy
        FakeDT.teraz = dt.datetime(2026, 10, 2, 22, 30, tzinfo=utc)
        with mock.patch.object(app, "SKIP_WEEKEND_RUNS", True), \
             mock.patch.object(app, "datetime", FakeDT), \
             mock.patch.object(app, "Capital", _nie_dotykac), \
             mock.patch.object(app, "load_signals", _nie_dotykac):
            self.assertIn("pominięto", app.sync())
        # niedziela 22:30 UTC = poniedziałek 00:30 w Warszawie => działamy
        FakeDT.teraz = dt.datetime(2026, 10, 4, 22, 30, tzinfo=utc)
        cap = FakeCapital(pelny_koszyk() + [poz(U26, "SELL", 0.35)])
        with mock.patch.object(app, "SKIP_WEEKEND_RUNS", True), \
             mock.patch.object(app, "DRY_RUN", True), \
             mock.patch.object(app, "datetime", FakeDT), \
             mock.patch.object(app, "Capital", lambda: cap), \
             mock.patch.object(app, "load_signals",
                               lambda: (dict(SYGNALY), "sha")), \
             mock.patch.object(app, "notify", lambda *a, **k: None), \
             mock.patch.object(app.time, "sleep", lambda *_: None):
            self.assertNotIn("pominięto", app.sync())


# ----------------------------------------------------------------------------
# 5. SIEĆ: PONOWIENIA GET/LOGOWANIA, BRAK WYJĄTKÓW PRZY POST/DELETE
# ----------------------------------------------------------------------------
class Odp:
    """Minimalna odpowiedź requests."""

    def __init__(self, status=200, dane=None, naglowki=None):
        self.status_code = status
        self._dane = {} if dane is None else dane
        self.headers = naglowki or {}
        self.ok = status < 400
        self.text = json.dumps(self._dane)

    def json(self):
        return self._dane

    def raise_for_status(self):
        if not self.ok:
            raise requests.HTTPError(f"{self.status_code} błąd", response=self)


class FakeSesja:
    """Sztuczna sesja HTTP: prawdziwa klasa Capital + sztuczna sieć."""

    def __init__(self, pozycje=(), ceny=None, timeouty_get=None,
                 timeout_post=(), timeout_delete=False, brak_rynku=()):
        self.headers = {}
        self.stan = [dict(p) for p in pozycje]
        self.ceny = dict(CENY)
        self.ceny.update(ceny or {})
        self.timeouty_get = dict(timeouty_get or {})
        self.timeout_post = set(timeout_post)
        self.timeout_delete = timeout_delete
        self.brak_rynku = set(brak_rynku)
        self.wywolania = []
        self._n = 0

    @staticmethod
    def _sc(url):
        return url[len(app.BASE_URL):]

    def licz(self, metoda, prefiks):
        return len([1 for m, sc in self.wywolania
                    if m == metoda and sc.startswith(prefiks)])

    def get(self, url, timeout=None, **kw):
        sc = self._sc(url)
        self.wywolania.append(("GET", sc))
        if self.timeouty_get.get(sc, 0) > 0:
            self.timeouty_get[sc] -= 1
            raise requests.exceptions.ReadTimeout("Read timed out")
        if sc == "/api/v1/accounts":
            return Odp(200, {"accounts": [{
                "accountId": "acc-1", "currency": "PLN", "preferred": True,
                "balance": {"balance": EQUITY, "profitLoss": 0.0}}]})
        if sc == "/api/v1/positions":
            return Odp(200, {"positions": [
                {"position": {"dealId": p["dealId"], "direction": p["direction"],
                              "size": p["size"], "upl": 0.0},
                 "market": {"epic": p["epic"], "instrumentName": p["epic"]}}
                for p in self.stan]})
        if sc.startswith("/api/v1/markets/"):
            epic = sc.rsplit("/", 1)[1]
            if epic in self.brak_rynku or epic not in self.ceny:
                return Odp(404, {"errorCode": "error.prices.not-found"})
            c = self.ceny[epic]
            return Odp(200, {
                "instrument": {"name": epic, "currency": "PLN"},
                "snapshot": {"bid": c, "offer": c, "marketStatus": "TRADEABLE"},
                "dealingRules": {"minDealSize": {
                    "value": 0.01 if epic.startswith("FW2020") else 0.1}}})
        if sc.startswith("/api/v1/confirms/"):
            return Odp(200, {"dealStatus": "ACCEPTED"})
        raise AssertionError(f"nieobsłużone GET {sc}")

    def post(self, url, json=None, timeout=None, **kw):
        sc = self._sc(url)
        self.wywolania.append(("POST", sc))
        if sc == "/api/v1/session":
            return Odp(200, {}, {"CST": "c", "X-SECURITY-TOKEN": "t"})
        if sc == "/api/v1/positions":
            if json["epic"] in self.timeout_post:
                raise requests.exceptions.ReadTimeout("POST timed out")
            self._n += 1
            self.stan.append(poz(json["epic"], json["direction"], json["size"],
                                 deal=f"s-{self._n}"))
            return Odp(200, {"dealReference": f"ref-{self._n}"})
        raise AssertionError(f"nieobsłużone POST {sc}")

    def delete(self, url, timeout=None, **kw):
        sc = self._sc(url)
        self.wywolania.append(("DELETE", sc))
        if self.timeout_delete:
            raise requests.exceptions.ReadTimeout("DELETE timed out")
        deal = sc.rsplit("/", 1)[1]
        self.stan = [p for p in self.stan if p["dealId"] != deal]
        return Odp(200, {})


def capital_z_sesja(sesja):
    cap = app.Capital()          # prawdziwa klasa; requests.Session bez sieci
    cap.s = sesja
    return cap


class TestSiecJednostkowo(unittest.TestCase):

    def _cap(self):
        cap = app.Capital.__new__(app.Capital)
        cap.switch_error = None
        cap._rynki = {}
        cap.s = mock.Mock()
        return cap

    def test_siec_ponawia_po_read_timeout_i_poddaje_sie_po_NET_RETRIES(self):
        cap = self._cap()
        fn = mock.Mock(side_effect=requests.exceptions.ReadTimeout("t"))
        with mock.patch.object(app.time, "sleep") as spij, \
             mock.patch.object(app, "NET_RETRIES", 3):
            with self.assertRaises(requests.exceptions.ReadTimeout):
                cap._siec(fn, "test")
        self.assertEqual(fn.call_count, 3)
        self.assertEqual(spij.call_args_list, [mock.call(2.0), mock.call(4.0)],
                         "pauzy rosną i nie ma pauzy po ostatniej próbie")

    def test_siec_zwraca_wynik_po_przejsciowym_timeoucie(self):
        cap = self._cap()
        fn = mock.Mock(side_effect=[requests.exceptions.ReadTimeout("t"),
                                    requests.exceptions.ConnectionError("c"),
                                    "OK"])
        with mock.patch.object(app.time, "sleep"), \
             mock.patch.object(app, "NET_RETRIES", 3):
            self.assertEqual(cap._siec(fn, "test"), "OK")
        self.assertEqual(fn.call_count, 3)

    def test_siec_respektuje_NET_RETRIES(self):
        cap = self._cap()
        for ile, oczekiwane in ((1, 1), (2, 2), (5, 5), (0, 1)):
            with self.subTest(NET_RETRIES=ile):
                fn = mock.Mock(side_effect=requests.exceptions.ReadTimeout("t"))
                with mock.patch.object(app.time, "sleep"), \
                     mock.patch.object(app, "NET_RETRIES", ile):
                    with self.assertRaises(requests.exceptions.ReadTimeout):
                        cap._siec(fn, "test")
                self.assertEqual(fn.call_count, oczekiwane)

    def test_siec_nie_ponawia_bledow_innych_niz_timeout_i_polaczenie(self):
        cap = self._cap()
        for wyjatek in (requests.HTTPError("500"), ValueError("x")):
            with self.subTest(wyjatek=type(wyjatek).__name__):
                fn = mock.Mock(side_effect=wyjatek)
                with mock.patch.object(app.time, "sleep") as spij:
                    with self.assertRaises(type(wyjatek)):
                        cap._siec(fn, "test")
                self.assertEqual(fn.call_count, 1)
                spij.assert_not_called()

    def test_get_ponawia_po_read_timeout(self):
        cap = self._cap()
        ok = Odp(200, {"ok": True})
        cap.s.get.side_effect = [requests.exceptions.ReadTimeout("t"), ok]
        with mock.patch.object(app.time, "sleep"):
            self.assertEqual(cap._get("/api/v1/positions"), {"ok": True})
        self.assertEqual(cap.s.get.call_count, 2)

    def test_get_poddaje_sie_po_NET_RETRIES_timeoutach(self):
        cap = self._cap()
        cap.s.get.side_effect = requests.exceptions.ReadTimeout("t")
        with mock.patch.object(app.time, "sleep"), \
             mock.patch.object(app, "NET_RETRIES", 3):
            with self.assertRaises(requests.exceptions.ReadTimeout):
                cap._get("/api/v1/positions")
        self.assertEqual(cap.s.get.call_count, 3)

    def test_logowanie_ponawia_po_timeoucie(self):
        cap = self._cap()
        cap.s.headers = {}
        cap.s.post.side_effect = [
            requests.exceptions.ReadTimeout("t"),
            Odp(200, {}, {"CST": "c1", "X-SECURITY-TOKEN": "t1"})]
        with mock.patch.object(app.time, "sleep"), \
             mock.patch.object(app, "ACCOUNT_ID", ""):
            cap.login()
        self.assertEqual(cap.s.post.call_count, 2)
        self.assertEqual(cap.s.headers,
                         {"CST": "c1", "X-SECURITY-TOKEN": "t1"})

    def test_open_timeout_POST_zwraca_False_zamiast_wyjatku_i_nie_ponawia(self):
        for wyjatek in (requests.exceptions.ReadTimeout("t"),
                        requests.exceptions.ConnectionError("c"),
                        requests.exceptions.RequestException("r")):
            with self.subTest(wyjatek=type(wyjatek).__name__):
                cap = self._cap()
                cap.s.post.side_effect = wyjatek
                with mock.patch.object(app.time, "sleep") as spij:
                    ok, ref, msg = cap.open("PKN", "BUY", 1.0)
                self.assertFalse(ok)
                self.assertIsNone(ref)
                self.assertIn("BŁĄD SIECI", msg)
                self.assertEqual(cap.s.post.call_count, 1,
                                 "POST nie może być ponawiany (podwójna pozycja)")
                spij.assert_not_called()

    def test_close_timeout_DELETE_zwraca_False_zamiast_wyjatku(self):
        for wyjatek in (requests.exceptions.ReadTimeout("t"),
                        requests.exceptions.ConnectionError("c")):
            with self.subTest(wyjatek=type(wyjatek).__name__):
                cap = self._cap()
                cap.s.delete.side_effect = wyjatek
                ok, msg = cap.close("deal-1")
                self.assertFalse(ok)
                self.assertIn("BŁĄD SIECI", msg)
                self.assertEqual(cap.s.delete.call_count, 1)

    def test_open_sciezka_szczesliwa_dziala_jak_dawniej(self):
        cap = self._cap()
        cap.s.post.return_value = Odp(200, {"dealReference": "r1"})
        with mock.patch.object(app.time, "sleep"), \
             mock.patch.object(cap, "_get", return_value={"dealStatus": "ACCEPTED"}):
            self.assertEqual(cap.open("PKN", "BUY", 1.0),
                             (True, "r1", "potwierdzono"))

    def test_open_brak_potwierdzenia_przy_awarii_sieci_nie_rzuca(self):
        cap = self._cap()
        cap.s.post.return_value = Odp(200, {"dealReference": "r1"})
        cap.s.get.side_effect = requests.exceptions.ConnectionError("c")
        with mock.patch.object(app.time, "sleep"):
            ok, ref, msg = cap.open("PKN", "BUY", 1.0)
        self.assertFalse(ok)
        self.assertEqual(ref, "r1")
        self.assertIn("BRAK POTWIERDZENIA", msg)

    def test_close_sciezka_szczesliwa(self):
        cap = self._cap()
        cap.s.delete.return_value = Odp(200, {})
        self.assertEqual(cap.close("d1")[0], True)


class TestSiecWBiegu(unittest.TestCase):
    """Prawdziwy Capital + sztuczna sesja HTTP: cały sync() przez warstwę sieci."""

    def _bieg(self, sesja, **kw):
        kw.setdefault("auto_roll", True)
        return uruchom(capital_z_sesja(sesja), **kw)

    def test_timeouty_POST_i_DELETE_nie_przerywaja_biegu_przed_blokiem_hedgeu(self):
        # Rotacja: brak longów na rachunku, stary hedge. Każde otwarcie longa
        # kończy się timeoutem POST, zamknięcie hedge'u timeoutem DELETE.
        # 9.09.2026 taki wyjątek przerwał cały /run PRZED blokiem hedge'u.
        sesja = FakeSesja(pozycje=[poz(U26, "SELL", 0.35, deal="d-hedge-U")],
                          timeout_post={"PKN", "PGE", "PEO", "PZU", "MBK"},
                          timeout_delete=True)
        rep, pow_ = self._bieg(sesja, data=dt.date(2026, 9, 14))
        self.assertIn("hedge", rep, "blok hedge'u musi się wykonać")
        self.assertEqual(sesja.licz("POST", "/api/v1/positions"), 5,
                         "jedna próba na pozycję — bez ponowień POST")
        self.assertEqual(sesja.licz("DELETE", "/api/v1/positions"), 1)
        self.assertGreaterEqual(len(rep["błędy"]), 6)
        self.assertTrue(any("BŁĄD SIECI" in b for b in rep["błędy"]))
        self.assertEqual(pow_[-1][0], "warning")

    def test_przejsciowy_timeout_GET_rynku_jest_ponawiany_i_bieg_przechodzi(self):
        sesja = FakeSesja(pozycje=[],
                          timeouty_get={"/api/v1/markets/PKN": 1})
        rep, _ = self._bieg(sesja, data=dt.date(2026, 9, 14))
        self.assertEqual(rep["błędy"], [])
        self.assertTrue(any(s["epic"] == "PKN" for s in sesja.stan),
                        "PKN powinien się otworzyć po ponowieniu")
        self.assertEqual(sesja.licz("GET", "/api/v1/markets/PKN"), 2)

    def test_przejsciowy_timeout_GET_pozycji_nie_wywala_biegu(self):
        sesja = FakeSesja(pozycje=pelny_koszyk() + [poz(U26, "SELL", 0.35)],
                          timeouty_get={"/api/v1/positions": 2})
        rep, _ = self._bieg(sesja, data=dt.date(2026, 9, 14))
        self.assertIn("hedge", rep)

    def test_przejscie_hedgeu_przez_prawdziwy_Capital_404_na_nowym_kontrakcie(self):
        sesja = FakeSesja(
            pozycje=pelny_koszyk() + [poz(U26, "SELL", 0.35, deal="d-hedge-U")],
            brak_rynku={Z26})
        rep, _ = self._bieg(sesja, data=D_ROLL, auto_roll=True)
        self.assertEqual(rep["hedge_kontrakt"]["fallback"], U26)
        self.assertEqual(sesja.licz("DELETE", "/api/v1/positions"), 0)
        self.assertEqual(sesja.licz("POST", "/api/v1/positions"), 0)

    def test_przejscie_hedgeu_przez_prawdziwy_Capital_sciezka_szczesliwa(self):
        sesja = FakeSesja(
            pozycje=pelny_koszyk() + [poz(U26, "SELL", 0.35, deal="d-hedge-U")])
        self._bieg(sesja, data=D_ROLL, auto_roll=True)
        self.assertEqual([(p["epic"], p["size"]) for p in sesja.stan
                          if p["epic"].startswith("FW2020")], [(Z26, 0.35)])

    def test_timeouty_GET_po_wyczerpaniu_ponowien_dla_nowego_longa_nie_przerywaja_biegu(self):
        """Po NET_RETRIES nieudanych GET /markets/PZU _siec rzuca Timeout.

        Pętla otwierania nowych longów łapie tylko requests.HTTPError, więc ten
        wyjątek ucieka z sync() — dokładnie ten sam objaw co 9.09.2026
        (przerwany /run, brak bloku hedge'u), tylko po trzech próbach."""
        sesja = FakeSesja(
            pozycje=[p for p in pelny_koszyk() if p["epic"] != "PZU"]
                    + [poz(U26, "SELL", 0.28, deal="d-hedge-U")],
            timeouty_get={"/api/v1/markets/PZU": 99})
        rep, _ = self._bieg(sesja, data=dt.date(2026, 9, 14))
        self.assertIn("hedge", rep)
        self.assertTrue(any("PZU" in b for b in rep["błędy"]), rep["błędy"])

    def test_timeouty_GET_po_wyczerpaniu_ponowien_dla_otwartej_pozycji_nie_przerywaja_biegu(self):
        """To samo dla `wartosc_pozycji` (łapie tylko HTTPError)."""
        sesja = FakeSesja(
            pozycje=pelny_koszyk() + [poz(U26, "SELL", 0.35, deal="d-hedge-U")],
            timeouty_get={"/api/v1/markets/PGE": 99})
        rep, _ = self._bieg(sesja, data=dt.date(2026, 9, 14))
        self.assertIn("ekspozycja_dluga", rep, "bieg musi dojść do bloku hedge'u")
        self.assertTrue(any("PGE" in b for b in rep["błędy"]), rep["błędy"])


# ----------------------------------------------------------------------------
# 6. POKRYCIE KOSZYKA (LPP)
# ----------------------------------------------------------------------------
class TestPokrycieKoszyka(unittest.TestCase):

    def _cap_bez_lpp(self, **kw):
        # cztery nogi na rachunku (LPP nie wejdzie: min. 0,1 szt. = 2470 PLN)
        nogi = [p for p in pelny_koszyk() if p["epic"] != "MBK"]
        return FakeCapital(nogi + [poz(U26, "SELL", 0.28, deal="d-hedge-U")],
                           **kw)

    def test_funkcja_pelny_koszyk(self):
        pk = app.pokrycie_koszyka(SYGNALY, {"PKN", "PGE", "PEO", "PZU", "MBK"},
                                  1464.86, EQUITY)
        self.assertEqual(pk["nogi_koszyka"], 5)
        self.assertEqual(pk["nogi_na_rachunku"], 5)
        self.assertEqual(pk["brakujace"], [])
        self.assertEqual(pk["cel_pct"], 50.0)
        self.assertEqual(pk["ekspozycja_dluga_pct"], 50.0)

    def test_funkcja_brakujace_nogi_i_zerowy_kapital(self):
        pk = app.pokrycie_koszyka(SYGNALY_LPP, {"PKN", "PGE"}, 586.0, 0)
        self.assertEqual(pk["brakujace"], ["PEKAO", "PZU", "LPP"])
        self.assertEqual(pk["nogi_na_rachunku"], 2)
        self.assertIsNone(pk["ekspozycja_dluga_pct"])

    def test_LPP_nie_wchodzi_i_pokrycie_to_zglasza(self):
        for dry in (False, True):
            with self.subTest(dry_run=dry):
                cap = self._cap_bez_lpp()
                rep, pow_ = uruchom(cap, sygnaly=SYGNALY_LPP, dry_run=dry)
                pk = rep["pokrycie_koszyka"]
                self.assertEqual(pk["nogi_koszyka"], 5)
                self.assertEqual(pk["nogi_na_rachunku"], 4)
                self.assertEqual(pk["brakujace"], ["LPP"])
                self.assertAlmostEqual(pk["ekspozycja_dluga"], 1172.24, delta=0.5)
                self.assertEqual(pk["ekspozycja_dluga_pct"], 40.0)
                self.assertEqual(pk["cel_pct"], 50.0)
                self.assertTrue(any(x.startswith("LPP:") and "min. wielkość" in x
                                    for x in rep["pominiete"]), rep["pominiete"])
                self.assertEqual([o for o in cap.otwarte if o[0] == "LPP"], [])
                tekst = pow_[-1][1]
                self.assertIn("pokrycie koszyka LONG: 4/5", tekst)
                self.assertIn("brak: LPP", tekst)
                self.assertIn("40.0% kapitału wobec celu 50.0%", tekst)

    def test_pelny_koszyk_nie_wywoluje_ostrzezenia(self):
        cap = FakeCapital(pelny_koszyk() + [poz(U26, "SELL", 0.35)])
        rep, pow_ = uruchom(cap)
        self.assertEqual(rep["pokrycie_koszyka"]["brakujace"], [])
        self.assertNotIn("pokrycie koszyka", pow_[-1][1])

    def test_nogi_otwierane_w_tym_biegu_licza_sie_do_pokrycia(self):
        cap = FakeCapital([poz(U26, "SELL", 0.35)])        # pusty koszyk long
        rep, _ = uruchom(cap)
        self.assertEqual(rep["pokrycie_koszyka"]["nogi_na_rachunku"], 5)
        self.assertEqual(rep["pokrycie_koszyka"]["brakujace"], [])

    def test_noga_zamknieta_i_nieotwarta_wypada_z_pokrycia(self):
        cap = FakeCapital(pelny_koszyk() + [poz(U26, "SELL", 0.35)],
                          otwarcie_odrzucone={"PZU"})
        # PZU leży na rachunku jako SELL (zły kierunek): bot zamyka go i próbuje
        # otworzyć BUY, ale broker odrzuca => noga nie wchodzi do pokrycia.
        cap.stan = [p for p in cap.stan if p["epic"] != "PZU"] + [
            poz("PZU", "SELL", 3.84, deal="d-PZU-short")]
        rep, _ = uruchom(cap)
        self.assertIn("PZU", " ".join(rep["akcje"]))
        self.assertEqual(rep["pokrycie_koszyka"]["brakujace"], ["PZU"])

    def test_status_zwraca_pokrycie_koszyka(self):
        cap = self._cap_bez_lpp()
        with mock.patch.object(app, "Capital", lambda: cap), \
             mock.patch.object(app, "load_signals",
                               lambda: (dict(SYGNALY_LPP), "sha")), \
             mock.patch.object(app, "teraz_warszawa", lambda: o_godz(D_PO2)):
            r = app.app.test_client().get(
                "/status", headers={"X-Run-Token": "test-token"})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        pk = r.get_json()["pokrycie_koszyka"]
        self.assertEqual(pk["brakujace"], ["LPP"])
        self.assertEqual(pk["nogi_na_rachunku"], 4)


# ----------------------------------------------------------------------------
# 7. HEDGE_TOL: 0.10 WOBEC 0.30 (28.09-1.10.2026: longi 888 PLN vs hedge 1136 PLN)
# ----------------------------------------------------------------------------
class TestHedgeTolerancja(unittest.TestCase):

    CENY_888 = {"PKN": 100.0, "PGE": 100.0, "PEO": 100.0, U26: 4000.0}

    def _cap(self):
        # trzy nogi po 296 PLN = 888; PZU i MBK nie wejdą (rynek CLOSED)
        return FakeCapital(
            [poz("PKN", "BUY", 2.96), poz("PGE", "BUY", 2.96),
             poz("PEO", "BUY", 2.96),
             poz(U26, "SELL", 0.284, deal="d-hedge-U")],     # 0,284 × 4000 = 1136
            ceny=self.CENY_888, status={"PZU": "CLOSED", "MBK": "CLOSED"})

    def test_domyslna_tolerancja_w_kodzie_to_0_10(self):
        # env testów wymusza 0.30, więc domyślną wartość czytamy ze źródła
        zrodlo = open(os.path.join(os.path.dirname(app.__file__), "app.py"),
                      encoding="utf-8").read()
        m = re.search(r'HEDGE_TOL\s*=\s*float\(os\.environ\.get\("HEDGE_TOL",\s*'
                      r'"([0-9.]+)"\)\)', zrodlo)
        self.assertIsNotNone(m)
        self.assertEqual(float(m.group(1)), 0.10)

    def test_tol_030_zostawia_netto_minus_8_5_procent_kapitalu(self):
        cap = self._cap()
        rep, pow_ = uruchom(cap, tol=0.30)
        self.assertEqual(rep["ekspozycja_dluga"]["razem"], 888.0)
        self.assertEqual(rep["hedge"]["biezacy"], 1136.0)
        self.assertEqual((cap.zamkniete, cap.otwarte), ([], []),
                         "odchyłka 27,9% mieści się w 30%")
        netto = rep["ekspozycja_dluga"]["razem"] - rep["hedge"]["po_korekcie"]
        self.assertEqual(netto, -248.0)
        self.assertAlmostEqual(netto / EQUITY * 100, -8.46, places=1)
        self.assertIn("netto -248", pow_[-1][1])

    def test_tol_010_koryguje_hedge_do_okolo_888(self):
        cap = self._cap()
        rep, pow_ = uruchom(cap, tol=0.10)
        self.assertEqual(cap.zamkniete, ["d-hedge-U"])
        self.assertEqual(cap.otwarte, [(U26, "SELL", 0.22)])
        self.assertEqual(rep["hedge"]["po_korekcie"], 880.0)
        netto = rep["ekspozycja_dluga"]["razem"] - rep["hedge"]["po_korekcie"]
        self.assertLess(abs(netto) / EQUITY, 0.01)
        self.assertIn("netto +8", pow_[-1][1])

    def test_granica_tolerancji_odchylka_27_9_procent(self):
        # |1136 − 888| / 888 = 0,2793
        for tol, koryguje in ((0.28, False), (0.279, True), (0.27, True)):
            with self.subTest(tol=tol):
                cap = self._cap()
                uruchom(cap, tol=tol)
                self.assertEqual(bool(cap.zamkniete), koryguje)

    def test_brak_wyceny_jednej_trzymanej_nogi_nie_zmniejsza_hedgeu(self):
        """Noga JEST na rachunku, ale jej rynek zwraca błąd (np. HTTP 429 po
        trzech próbach). `wartosc_pozycji` daje None, więc noga wypada z podstawy
        hedge'u: longi 1465 → 1172 PLN, odchyłka 22,9% przekracza TOL 0,10
        (przy dawnym 0,30 szum mieścił się w normie) i bot zamyka oraz otwiera
        hedge mniejszy o 20% — rachunek zostaje w 0,5 nogi długi, a następny
        bieg odwraca to kolejnym zamknij+otwórz. Brak danych ≠ brak ekspozycji."""
        cap = FakeCapital(
            pelny_koszyk() + [poz(U26, "SELL", 0.35, deal="d-hedge-U")],
            blad_rynku={"PGE": requests.HTTPError("429 Too Many Requests")})
        uruchom(cap, tol=0.10)
        self.assertEqual(
            (cap.zamkniete, cap.otwarte), ([], []),
            f"hedge ruszony mimo braku wyceny jednej nogi: "
            f"zamknięcia={cap.zamkniete} otwarcia={cap.otwarte}")

    def test_hedge_po_wlasnej_korekcie_nie_jest_ruszany_ponownie(self):
        """Kwantyzacja do kroku 0,01 kontraktu nie może przekraczać TOL 0,10
        — inaczej każdy bieg płaciłby dwa spready indeksu (zamknij+otwórz)."""
        for nogi in (2, 3, 4, 5):
            with self.subTest(nogi=nogi):
                koszyk = pelny_koszyk()[:nogi]
                cap = FakeCapital(
                    koszyk,
                    status={e: "CLOSED" for e in
                            ("PKN", "PGE", "PEO", "PZU", "MBK")
                            if e not in [p["epic"] for p in koszyk]})
                uruchom(cap, tol=0.10)                 # pierwszy bieg: otwiera
                self.assertEqual(len(hedge_stan(cap)), 1)
                otw, zam = len(cap.otwarte), len(cap.zamkniete)
                for _ in range(3):
                    uruchom(cap, tol=0.10)
                self.assertEqual((len(cap.otwarte), len(cap.zamkniete)),
                                 (otw, zam), "churn hedge'u przy kolejnych biegach")


# ----------------------------------------------------------------------------
# 12. POPRAWKI PO PRZEGLĄDZIE: niejednoznaczne zlecenia, zakres własności
#     kontraktów, krok kontraktu, pokrycie koszyka
# ----------------------------------------------------------------------------
class FakeCapitalNiepewne(FakeCapital):
    """Otwarcie wskazanych epików kończy się wynikiem NIEJEDNOZNACZNYM."""

    def __init__(self, *a, niepewne_epiki=(), **kw):
        super().__init__(*a, **kw)
        self.niepewne = set()
        self._niep_epiki = set(niepewne_epiki)

    def open(self, epic, direction, size):
        if epic in self._niep_epiki:
            self.otwarte.append((epic, direction, size))
            self.niepewne.add(epic)
            return False, None, "BŁĄD SIECI — stan NIEPEWNY"
        return super().open(epic, direction, size)


class TestPoPrzegladzie(unittest.TestCase):

    def test_niejednoznaczne_otwarcie_przy_przeskalowaniu_nie_jest_ponawiane(self):
        """PGE taktyczna 12 szt. -> pełna noga; otwarcie po zamknięciu kończy się
        timeoutem. Druga próba w TYM SAMYM biegu mogłaby podwoić pozycję."""
        koszyk = [p for p in pelny_koszyk() if p["epic"] != "PGE"]
        cap = FakeCapitalNiepewne(
            koszyk + [poz("PGE", "BUY", 12), poz(U26, "SELL", 0.35)],
            niepewne_epiki={"PGE"})
        rep, _ = uruchom(cap)
        pge = [o for o in cap.otwarte if o[0] == "PGE"]
        self.assertEqual(len(pge), 1, f"PGE otwierane {len(pge)}x: {cap.otwarte}")
        self.assertTrue(any("nie ponawiam" in x for x in rep["pominiete"]),
                        rep["pominiete"])

    def _klient(self):
        cap = app.Capital()
        cap.s = mock.Mock()
        return cap

    def test_klient_uzgadnia_timeout_otwarcia_z_lista_pozycji(self):
        cap = self._klient()
        cap.s.post.side_effect = requests.exceptions.ReadTimeout("t")
        cap.positions = mock.Mock(side_effect=[
            [],                                       # przed zleceniem
            [poz("PGE", "BUY", 22.6, deal="nowy")]])  # po timeoucie
        ok, ref, msg = cap.open("PGE", "BUY", 22.6)
        self.assertTrue(ok, msg)
        self.assertEqual(cap.s.post.call_count, 1)    # bez ponowienia POST
        self.assertNotIn("PGE", cap.niepewne)

    def test_klient_gdy_pozycji_na_pewno_nie_ma_to_porazka_bez_niepewnosci(self):
        cap = self._klient()
        cap.s.post.side_effect = requests.exceptions.ReadTimeout("t")
        cap.positions = mock.Mock(side_effect=[[], []])
        ok, _, msg = cap.open("PGE", "BUY", 22.6)
        self.assertFalse(ok)
        self.assertNotIn("PGE", cap.niepewne)
        self.assertIn("nie ma", msg)

    def test_klient_gdy_nie_da_sie_sprawdzic_epic_trafia_do_niepewnych(self):
        cap = self._klient()
        cap.s.post.side_effect = requests.exceptions.ReadTimeout("t")
        cap.positions = mock.Mock(side_effect=requests.exceptions.ReadTimeout("t"))
        ok, _, msg = cap.open("PGE", "BUY", 22.6)
        self.assertFalse(ok)
        self.assertIn("PGE", cap.niepewne)
        self.assertIn("NIEPEWNY", msg)

    def test_klient_5xx_na_otwarciu_jest_niejednoznaczny(self):
        cap = self._klient()
        odp = mock.Mock(ok=False, status_code=504, text="gateway timeout")
        cap.s.post.return_value = odp
        cap.positions = mock.Mock(side_effect=[[], [poz("PGE", "BUY", 22.6,
                                                         deal="nowy")]])
        ok, _, _ = cap.open("PGE", "BUY", 22.6)
        self.assertTrue(ok)

    def test_klient_timeout_na_delete_uzgadniany_z_lista_pozycji(self):
        cap = self._klient()
        cap.s.delete.side_effect = requests.exceptions.ReadTimeout("t")
        cap.positions = mock.Mock(return_value=[])    # pozycja zniknęła
        ok, msg = cap.close("d-1")
        self.assertTrue(ok, msg)
        cap.positions = mock.Mock(return_value=[poz("PGE", "BUY", 1, deal="d-1")])
        ok, msg = cap.close("d-1")
        self.assertFalse(ok)

    def test_pozycje_na_obcych_terminach_nie_naleza_do_bota(self):
        """Ręczny short na kontrakcie spoza łańcucha U->Z (np. czerwiec 2027)
        nie może być zamknięty przez hedge bota."""
        obcy = poz("FW2020M2027", "SELL", 0.10, deal="d-obcy")
        cap = FakeCapital(pelny_koszyk() + [poz(U26, "SELL", 0.35), obcy],
                          ceny={"FW2020M2027": 4200.0})
        uruchom(cap, data=D_ROLL, auto_roll=True)
        self.assertNotIn("d-obcy", cap.zamkniete)
        self.assertIn("d-obcy", [p["dealId"] for p in cap.stan])

    def test_rodzina_hedge_to_lancuch_od_konfiguracji_do_obowiazujacego(self):
        with mock.patch.object(app, "HEDGE_AUTO_ROLL", True), \
             mock.patch.object(app, "HEDGE_EPIC", U26):
            self.assertEqual(app.rodzina_hedge(D_PRZED), {U26})
            self.assertEqual(app.rodzina_hedge(D_ROLL), {U26, Z26})
            self.assertEqual(app.rodzina_hedge(dt.date(2026, 12, 16)),
                             {U26, Z26, H27})
            self.assertFalse(app.jest_hedge("FW2020M2027"))
            self.assertFalse(app.jest_hedge("PKN"))

    def test_maly_hedge_nie_jest_zamykany_i_otwierany_na_ta_sama_wielkosc(self):
        """Hedge ~146 PLN przy kroku 0,01 (~41 PLN): docelowo 0,03 kontraktu,
        a odchyłka wobec celu to 15% > TOL 10%. Wcześniej hedge kasował się
        i otwierał na 0,03 przy KAŻDYM biegu (dwa spready za nic)."""
        sygn = dict(SYGNALY, long=[], short=[],
                    tactical=[{"ticker": "PGE", "direction": "BUY"}])
        cap = FakeCapital([poz("PGE", "BUY", 11.3), poz(U26, "SELL", 0.03)])
        rep, _ = uruchom(cap, sygnaly=sygn)
        self.assertEqual((cap.zamkniete, cap.otwarte), ([], []), rep["akcje"])

    def test_rynek_hedge_nietradeable_odklada_korekte_bez_zamykania(self):
        cap = FakeCapital(pelny_koszyk() + [poz(U26, "SELL", 0.20)],
                          status={U26: "CLOSED"})
        rep, _ = uruchom(cap)
        self.assertEqual((cap.zamkniete, cap.otwarte), ([], []))
        self.assertTrue(any("korekta odłożona" in x for x in rep["pominiete"]),
                        rep["pominiete"])

    def test_pokrycie_nie_liczy_nog_wykluczonych_przez_puls_jako_brakujacych(self):
        sygn = dict(SYGNALY, exclude=[{"ticker": "PKNORLEN", "action": "CLOSE",
                                       "date": "2026-10-01"}])
        koszyk = [p for p in pelny_koszyk() if p["epic"] != "PKN"]
        cap = FakeCapital(koszyk + [poz(U26, "SELL", 0.28)])
        rep, pow_ = uruchom(cap, sygnaly=sygn)
        pk = rep["pokrycie_koszyka"]
        self.assertEqual(pk["nogi_koszyka"], 4)
        self.assertEqual(pk["brakujace"], [])
        self.assertEqual(pk["wykluczone_przez_puls"], ["PKNORLEN"])
        self.assertEqual(pk["cel_pct"], 40.0)
        self.assertNotIn("pokrycie koszyka", pow_[-1][1])

    def test_pokrycie_cel_uwzglednia_redukcje(self):
        sygn = dict(SYGNALY, exclude=[{"ticker": "PGE", "action": "REDUCE",
                                       "date": "2026-10-01"}])
        pk = app.pokrycie_koszyka(sygn, {"PKN", "PEO", "PZU", "MBK", "PGE"},
                                  1300.0, 2931.11)
        self.assertEqual(pk["cel_pct"], 45.0)         # 4×10% + 5%
        self.assertEqual(pk["brakujace"], [])

    def test_niepelne_pokrycie_podnosi_poziom_powiadomienia_do_warning(self):
        cap = FakeCapital(pelny_koszyk()[:4] + [poz(U26, "SELL", 0.28)],
                          min_deal={"LPP": 0.1})
        _, pow_ = uruchom(cap, sygnaly=SYGNALY_LPP)
        self.assertEqual(pow_[-1][0], "warning")
        self.assertIn("pokrycie koszyka LONG", pow_[-1][1])

    def test_dwie_pozycje_buy_na_jednym_instrumencie_sa_zglaszane(self):
        cap = FakeCapital(pelny_koszyk() + [poz("PGE", "BUY", 22.6, deal="d-dup"),
                                            poz(U26, "SELL", 0.35)])
        rep, _ = uruchom(cap)
        self.assertTrue(any("osobne pozycje BUY" in b for b in rep["błędy"]),
                        rep["błędy"])

    def test_brak_bazy_stref_czasowych_nie_przewraca_importu(self):
        """Fallback na UTC zamiast ZoneInfoNotFoundError przy imporcie."""
        import importlib
        with mock.patch("zoneinfo.ZoneInfo", side_effect=KeyError("brak")):
            m = importlib.reload(app)
            self.assertIs(m._WARSZAWA, dt.timezone.utc)
        importlib.reload(app)                          # przywróć stan modułu


if __name__ == "__main__":
    unittest.main(verbosity=2)
