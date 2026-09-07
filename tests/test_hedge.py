# -*- coding: utf-8 -*-
"""Testy synchronizacji portfela — regresja błędu z 7.09.2026.

Uruchomienie (bez pytest, sam stdlib):   python3 tests/test_hedge.py

Sedno: hedge indeksowy musi wynikać z pozycji FAKTYCZNIE otwartych, a nie
z koszyka docelowego. 7.09.2026 bieg rotacyjny zamknął stary koszyk, trzy
z pięciu nowych longów nie weszły, a hedge policzył się od pełnych pięciu —
rachunek został per saldo krótki na rosnącym WIG20.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Konfiguracja MUSI stanąć przed importem app (czyta env na poziomie modułu).
os.environ.update({
    "DRY_RUN": "true", "CAPITAL_DEMO": "true", "RUN_TOKEN": "test-token",
    "HEDGE_EPIC": "FW2020U2026", "HEDGE_RATIO": "1.0", "HEDGE_TOL": "0.30",
    "ALLOC_PCT": "0.10", "TACTICAL_ALLOC_PCT": "0.05", "SIZE_TOL": "0.35",
    "START_EQUITY": "1000", "KILL_LEVEL": "0.75", "TELEGRAM_BOT_TOKEN": "",
})
import app  # noqa: E402

EQUITY = 2931.11

SYGNALY = {
    "version": "2026-W4", "status": "AKTUALNA",
    "long": ["PKNORLEN", "PGE", "PEKAO", "PZU", "MBANK"],
    "short": ["KRUK", "PEPCO", "CDPROJEKT", "KETY", "MODIVO"],
    "exclude": [], "tactical": [],
    "epics": {"PKNORLEN": "PKN", "PGE": "PGE", "PEKAO": "PEO", "PZU": "PZU",
              "MBANK": "MBK", "KRUK": "KRU", "PEPCO": "PCOP",
              "CDPROJEKT": "CDR", "KETY": "KTY", "MODIVO": "MDVP"},
}

CENY = {"PKN": 159.26, "PGE": 12.96, "PEO": 264.10, "PZU": 76.34,
        "MBK": 1420.50, "FW2020U2026": 4116.17}


class FakeCapital:
    """Broker-atrapa. `nietradeable` odtwarza longi, które nie weszły."""

    def __init__(self, pozycje, nietradeable=(), min_deal=None):
        self._pozycje = list(pozycje)
        self._nietradeable = set(nietradeable)
        self._min = min_deal or {}
        self.switch_error = None
        self.otwarte = []
        self.zamkniete = []

    def login(self):
        pass

    def equity(self):
        return EQUITY, "PLN", "acc-1"

    def accounts(self):
        return [{"accountId": "acc-1", "accountName": "demo", "currency": "PLN",
                 "balance": {"balance": EQUITY, "profitLoss": 0.0},
                 "preferred": True}]

    def positions(self):
        return [dict(p) for p in self._pozycje]

    def market(self, epic):
        return {"epic": epic, "name": epic, "currency": "PLN",
                "status": "CLOSED" if epic in self._nietradeable else "TRADEABLE",
                "mid": CENY[epic], "min": self._min.get(epic, 0.1)}

    def fx_rate(self, a, b):
        return 1.0

    def open(self, epic, direction, size):
        self.otwarte.append((epic, direction, size))
        return True, "ref", "potwierdzono"

    def close(self, deal_id):
        self.zamkniete.append(deal_id)
        return True, "ok"


def poz(epic, direction, size, deal=None):
    return {"dealId": deal or f"d-{epic}", "epic": epic, "name": epic,
            "direction": direction, "size": size, "upl": 0.0}


def uruchom(cap):
    with mock.patch.object(app, "Capital", lambda: cap), \
         mock.patch.object(app, "load_signals", lambda: (dict(SYGNALY), "sha")), \
         mock.patch.object(app, "notify", lambda *a, **k: None):
        return app.sync()


class TestHedgeZFaktycznychPozycji(unittest.TestCase):

    def test_pominiete_longi_nie_powiekszaja_hedgeu(self):
        """Scenariusz 7.09.2026: zostają PEO i PGE, PKN/PZU/MBK nie wchodzą.

        Przed poprawką hedge celował w 5 × 293 = 1466 PLN. Teraz musi celować
        w to, co realnie jest: PEO (291) + PGE po korekcie do pełnej nogi.
        """
        cap = FakeCapital(
            pozycje=[poz("PEO", "BUY", 1.1),
                     poz("PGE", "BUY", 12),
                     poz("FW2020U2026", "SELL", 0.37)],
            nietradeable={"PKN", "PZU", "MBK"})
        rep = uruchom(cap)

        dlugie = rep["ekspozycja_dluga"]["razem"]
        hedge_cel = rep["hedge"]["cel"]

        self.assertAlmostEqual(hedge_cel, dlugie, places=2,
                               msg="hedge musi równać się ekspozycji długiej")
        self.assertLess(dlugie, 700,
                        "realne longi to PEO + PGE, nie pięć nóg")
        # Regresja: stara formuła dawała 5 × equity × ALLOC_PCT.
        self.assertNotAlmostEqual(hedge_cel, 5 * EQUITY * 0.10, places=0)
        for t in ("PKNORLEN", "PZU", "MBANK"):
            self.assertTrue(any(t in x for x in rep["pominiete"]),
                            f"{t} powinien trafić do pominiętych z powodem")

    def test_ekspozycja_netto_bliska_zeru_gdy_wszystko_wejdzie(self):
        """Komplet longów → rachunek faktycznie neutralny."""
        cap = FakeCapital(
            pozycje=[poz("PEO", "BUY", 1.1), poz("FW2020U2026", "SELL", 0.37)])
        rep = uruchom(cap)
        netto = rep["ekspozycja_dluga"]["razem"] - rep["hedge"]["po_korekcie"]
        self.assertLess(abs(netto) / EQUITY, 0.10,
                        f"ekspozycja netto {netto:.0f} PLN to za dużo")

    def test_brak_longow_zamyka_hedge(self):
        """Status NIEAKTUALNA nie zostawia samotnego shorta indeksu."""
        sygn = dict(SYGNALY, status="NIEAKTUALNA")
        cap = FakeCapital(pozycje=[poz("PEO", "BUY", 1.1),
                                   poz("FW2020U2026", "SELL", 0.37)])
        with mock.patch.object(app, "Capital", lambda: cap), \
             mock.patch.object(app, "load_signals", lambda: (sygn, "sha")), \
             mock.patch.object(app, "notify", lambda *a, **k: None):
            rep = app.sync()
        self.assertTrue(any("ZAMKNIJ" in a or "ZAMKNIĘTO" in a
                            for a in rep["akcje"]))


class TestPrzeskalowanie(unittest.TestCase):

    def test_pozycja_taktyczna_urosla_do_pelnej_nogi(self):
        """PGE weszło 3.09 jako taktyczna (156 PLN); w W4 to pełny long (293)."""
        cap = FakeCapital(pozycje=[poz("PGE", "BUY", 12),
                                   poz("FW2020U2026", "SELL", 0.37)])
        rep = uruchom(cap)
        akcje = " ".join(rep["akcje"])
        self.assertIn("PRZESKALUJ", akcje)
        self.assertIn("PGE", akcje)
        cel = rep["ekspozycja_dluga"]["pozycje"]["PGE"]
        self.assertAlmostEqual(cel, EQUITY * 0.10, delta=1.0)

    def test_pozycja_w_dobrej_wielkosci_nie_jest_ruszana(self):
        """Bez tego bot płaciłby dwa spready przy każdym biegu."""
        cap = FakeCapital(pozycje=[poz("PEO", "BUY", 1.1),
                                   poz("FW2020U2026", "SELL", 0.37)])
        rep = uruchom(cap)
        self.assertNotIn("PRZESKALUJ PEKAO",
                         " ".join(rep["akcje"]).replace("[DRY] ", ""))

    def test_koszyk_short_pomijany_przy_hedgeu_indeksowym(self):
        cap = FakeCapital(pozycje=[poz("FW2020U2026", "SELL", 0.37)])
        rep = uruchom(cap)
        self.assertTrue(any("koszyk SHORT" in x for x in rep["pominiete"]))


class TestDiagnostykaInstrumentow(unittest.TestCase):
    """Odpowiedź na „czemu ten long nie wszedł" bez czekania na kolejny bieg."""

    def test_za_duza_minimalna_wielkosc_jest_nazwana_wprost(self):
        # MBANK ~1420 zł przy minDealSize 0,5 => 710 PLN, a tolerancja to
        # 293 × 1,6 = 469 PLN. Taka noga nie ma prawa wejść.
        cap = FakeCapital(pozycje=[], min_deal={"MBK": 0.5})
        d = app.diagnostyka_instrumentow(cap, SYGNALY, EQUITY, "PLN")
        mbk = next(w for w in d if w["ticker"] == "MBANK")
        self.assertIn("NIE WEJDZIE", mbk["werdykt"])
        self.assertGreater(mbk["min_wartosc_pozycji"], mbk["tolerancja"])

    def test_normalna_spolka_przechodzi(self):
        cap = FakeCapital(pozycje=[])
        d = app.diagnostyka_instrumentow(cap, SYGNALY, EQUITY, "PLN")
        self.assertEqual(next(w for w in d if w["ticker"] == "PZU")["werdykt"], "OK")

    def test_zamkniety_rynek_jest_odrozniony_od_za_duzej_pozycji(self):
        cap = FakeCapital(pozycje=[], nietradeable={"PKN"})
        d = app.diagnostyka_instrumentow(cap, SYGNALY, EQUITY, "PLN")
        self.assertIn("rynek CLOSED",
                      next(w for w in d if w["ticker"] == "PKNORLEN")["werdykt"])

    def test_koszyk_short_opisany_jako_niehandlowany(self):
        cap = FakeCapital(pozycje=[])
        d = app.diagnostyka_instrumentow(cap, SYGNALY, EQUITY, "PLN")
        kru = next(w for w in d if w["ticker"] == "KRUK")
        self.assertIn("NIE HANDLOWANE", kru["werdykt"])


class TestOgraniczeniaRachunku(unittest.TestCase):

    def test_zapisane_jawnie_ze_short_na_akcjach_jest_niemozliwy(self):
        o = app.OGRANICZENIA_RACHUNKU
        self.assertIs(o["short_na_akcjach"], False)
        self.assertTrue(any("classic" in s for s in o["skutek"]))

    def test_status_zwraca_ograniczenia_i_ekspozycje(self):
        cap = FakeCapital(pozycje=[poz("PEO", "BUY", 1.1),
                                   poz("FW2020U2026", "SELL", 0.37)])
        with mock.patch.object(app, "Capital", lambda: cap), \
             mock.patch.object(app, "load_signals", lambda: (dict(SYGNALY), "sha")):
            klient = app.app.test_client()
            r = klient.get("/status", headers={"X-Run-Token": "test-token"})
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertIs(j["ograniczenia_rachunku"]["short_na_akcjach"], False)
        # PEO 290,51 długie vs hedge 1522,98 krótkie => rachunek per saldo krótki
        self.assertLess(j["ekspozycja"]["netto"], 0)
        self.assertTrue(any("NIE WEJDZIE" in w["werdykt"] or w["werdykt"] == "OK"
                            for w in j["diagnostyka_instrumentow"]))


class TestRaportowanieBezTelegrama(unittest.TestCase):

    def test_notify_nie_wychodzi_do_sieci(self):
        with mock.patch.object(app.requests, "post") as posted:
            app.notify("test")
            posted.assert_not_called()

    def test_poziom_bledu_trafia_do_logu_jako_error(self):
        with self.assertLogs(app.log, level="ERROR") as zapis:
            app.notify("awaria", "error")
        self.assertTrue(any("awaria" in x for x in zapis.output))

    def test_wieloliniowy_komunikat_nie_gubi_linii(self):
        with self.assertLogs(app.log, level="INFO") as zapis:
            app.notify("pierwsza\ndruga\ntrzecia")
        self.assertEqual(len(zapis.output), 3)


class TestLimitZapytan(unittest.TestCase):
    """Regresja: 429 z Capital.com w środku pętli wygląda jak „long nie wszedł"."""

    def _capital(self):
        cap = app.Capital.__new__(app.Capital)
        cap.switch_error = None
        cap._rynki = {}
        return cap

    def test_ten_sam_epic_odpytany_raz(self):
        cap = self._capital()
        odpowiedz = {"instrument": {"name": "ORLEN", "currency": "PLN"},
                     "snapshot": {"bid": 159.0, "offer": 159.2,
                                  "marketStatus": "TRADEABLE"},
                     "dealingRules": {"minDealSize": {"value": 0.1}}}
        with mock.patch.object(cap, "_get", return_value=odpowiedz) as g:
            a = cap.market("PKN")
            b = cap.market("PKN")
        self.assertEqual(g.call_count, 1, "drugie wywołanie ma iść z cache")
        self.assertEqual(a, b)
        self.assertAlmostEqual(a["mid"], 159.1)

    def test_odswiez_wymusza_ponowne_pobranie(self):
        cap = self._capital()
        odpowiedz = {"instrument": {}, "snapshot": {"bid": 1, "offer": 1},
                     "dealingRules": {}}
        with mock.patch.object(cap, "_get", return_value=odpowiedz) as g:
            cap.market("X")
            cap.market("X", odswiez=True)
        self.assertEqual(g.call_count, 2)

    def test_429_jest_ponawiane_a_nie_wywala_biegu(self):
        cap = self._capital()
        cap.s = mock.Mock()
        ok = mock.Mock(status_code=200)
        ok.json.return_value = {"ok": True}
        ok.raise_for_status.return_value = None
        cap.s.get.side_effect = [mock.Mock(status_code=429), ok]
        with mock.patch.object(app.time, "sleep"):
            self.assertEqual(cap._get("/api/v1/markets/PKN"), {"ok": True})
        self.assertEqual(cap.s.get.call_count, 2)


class TestToken(unittest.TestCase):

    def test_naglowek_dziala_a_zly_token_nie(self):
        with app.app.test_request_context("/run",
                                          headers={"X-Run-Token": "test-token"}):
            self.assertTrue(app.auth_ok())
        with app.app.test_request_context("/run",
                                          headers={"X-Run-Token": "zle"}):
            self.assertFalse(app.auth_ok())

    def test_url_dziala_dopoki_dozwolony(self):
        with app.app.test_request_context("/run?token=test-token"):
            self.assertTrue(app.auth_ok())
        with mock.patch.object(app, "ALLOW_TOKEN_IN_URL", False):
            with app.app.test_request_context("/run?token=test-token"):
                self.assertFalse(app.auth_ok())

    def test_domyslny_token_nie_przechodzi(self):
        with mock.patch.object(app, "RUN_TOKEN", "zmien-ten-token"):
            with app.app.test_request_context("/run?token=zmien-ten-token"):
                self.assertFalse(app.auth_ok())


if __name__ == "__main__":
    unittest.main(verbosity=2)
