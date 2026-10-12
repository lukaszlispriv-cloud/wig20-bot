# -*- coding: utf-8 -*-
"""Testy skryptów konektora TradingView (bez sieci, sam stdlib).

Uruchomienie:   python3 tests/test_tv.py

Zakres: waliduj_signals.py (bramka przed commitem signals.json),
tv_porownaj.py (zgodność TV vs kursy.py), tv_merge.py (backfill cache
tylko brakujących sesji po walidacji D0 i teście ex-date).
"""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = [sys.executable, "-I"]
SK = lambda n: os.path.join(REPO, "scripts", n)  # noqa: E731

LONG = ["PGE", "LPP", "TAURONPE", "CDPROJEKT", "KETY"]
SHORT = ["ALIOR", "PKOBP", "MBANK", "PEKAO", "KRUK"]
EPICS = {"ALIOR": "ALRR", "ALLEGRO": "ALEP", "BUDIMEX": "BDXP", "CDPROJEKT": "CDRP",
         "DINOPL": "DNPP", "ERSTEPL": "EBPP", "KETY": "KTYP", "KGHM": "KGHP", "KRUK": "KRUP",
         "LPP": "LPPP", "MBANK": "MBKP", "MODIVO": "MDVP", "PEKAO": "PEOP", "PEPCO": "PCOP",
         "PGE": "PGEP", "PKNORLEN": "PKNP", "PKOBP": "PKOP", "PZU": "PZUP", "TAURONPE": "TPEP",
         "ZABKA": "ZABP"}
HIST = {"week": "2026-W8", "long_vs_index_pp": -0.5, "long_abs_pct": 1.0, "spread_pp": 0.3,
        "rozjazd_pp": 0.8, "hit_top": "2/5", "hit_bottom": "3/5", "tactical_pp": None,
        "managed_pp": -0.5, "reaction_pp": 0.0, "base_rate": 0.45, "spearman": 0.1,
        "brier": 0.25, "data_quality": [], "metoda": "v1.1 (momentum mechaniczne)",
        "benchmark_momentum_pp": 0.2}
SYMBOLE = {"_indeks": "GPW:WIG20", "koszyk": {"LPP": "GPW:LPP", "PZU": "GPW:PZU", "PKOBP": "GPW:PKO",
                                             "PGE": "GPW:PGE", "ALIOR": "GPW:ALR"}, "taktyczne": {}}


def sig():
    return {"_instrukcja": "test", "d0": {"date": "2026-10-09", "wig20": 4185.52,
                                          "prices": {t: 100.0 for t in LONG + SHORT}},
            "epics": dict(EPICS), "exclude": [], "generated": "2026-10-10",
            "history": [dict(HIST, week="2026-W7")], "last_daily": "2026-10-12",
            "long": list(LONG), "short": list(SHORT), "status": "AKTUALNA",
            "tactical": [], "version": "2026-W9"}


def zapisz(p, obj):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f)
    return p


def odczytaj(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def uruchom(skrypt, *args):
    return subprocess.run(PY + [SK(skrypt), *args], capture_output=True, text=True)


class Walidator(unittest.TestCase):
    def waliduj(self, baza, nowy, rutyna):
        with tempfile.TemporaryDirectory() as d:
            pb, pn = os.path.join(d, "b.json"), os.path.join(d, "n.json")
            zapisz(pb, baza); zapisz(pn, nowy)
            out = uruchom("waliduj_signals.py", "--base", pb, "--plik", pn, "--rutyna", rutyna)
            return out.returncode, out.stdout

    def test_bez_zmian_przechodzi(self):
        self.assertEqual(self.waliduj(sig(), sig(), "puls")[0], 0)

    def test_puls_dozwolone_pola(self):
        n = sig(); n["status"] = "NIEAKTUALNA"; n["last_daily"] = "2026-10-13"
        n["exclude"] = [{"ticker": "PGE", "action": "REDUCE", "date": "2026-10-13", "reason": "x",
                         "price_before": 16.7, "move_from_d0_pct": -4.2, "trigger": "PRICE_4_8"}]
        kod, out = self.waliduj(sig(), n, "puls")
        self.assertEqual(kod, 0, out)

    def test_exclude_bez_trigger_odrzucony(self):
        n = sig(); n["exclude"] = [{"ticker": "PGE", "action": "REDUCE", "date": "2026-10-13", "reason": "x"}]
        kod, out = self.waliduj(sig(), n, "puls")
        self.assertEqual(kod, 1); self.assertIn("trigger", out)

    def test_obcy_klucz_odrzucony(self):
        n = sig(); n["fills"] = {}
        kod, out = self.waliduj(sig(), n, "puls")
        self.assertEqual(kod, 1); self.assertIn("OBCE", out)

    def test_epics_nietkniete(self):
        n = sig(); n["epics"]["LPP"] = "LPP"
        kod, out = self.waliduj(sig(), n, "puls")
        self.assertEqual(kod, 1); self.assertIn("epics", out)

    def test_puls_nie_zmienia_koszyka(self):
        n = sig(); n["long"] = ["PZU", "LPP", "TAURONPE", "CDPROJEKT", "KETY"]
        self.assertEqual(self.waliduj(sig(), n, "puls")[0], 1)

    def test_ticker_spoza_listy(self):
        n = sig(); n["long"][0] = "CCC"; n["d0"]["prices"]["CCC"] = n["d0"]["prices"].pop("PGE")
        n["epics"]["CCC"] = "CCCP"
        b = sig(); b["epics"]["CCC"] = "CCCP"
        kod, out = self.waliduj(b, n, "sobota")
        self.assertEqual(kod, 1); self.assertIn("spoza listy", out)

    def sobota(self):
        s = sig()
        s.update({"version": "2026-W10", "generated": "2026-10-17", "long": ["PZU", "LPP", "KGHM", "DINOPL", "KETY"],
                  "short": ["ALIOR", "PKOBP", "MBANK", "PEKAO", "KRUK"],
                  "d0": {"date": "2026-10-16", "wig20": 4200.0,
                         "prices": {t: 100.0 for t in ["PZU", "LPP", "KGHM", "DINOPL", "KETY",
                                                        "ALIOR", "PKOBP", "MBANK", "PEKAO", "KRUK"]}}})
        s["history"] = sig()["history"] + [dict(HIST, week="2026-W9")]
        return s

    def test_sobota_rotacja_ok(self):
        kod, out = self.waliduj(sig(), self.sobota(), "sobota")
        self.assertEqual(kod, 0, out)

    def test_sobota_jako_puls_odrzucona(self):
        self.assertEqual(self.waliduj(sig(), self.sobota(), "puls")[0], 1)

    def test_history_bez_metody(self):
        n = self.sobota(); n["history"][-1].pop("metoda")
        kod, out = self.waliduj(sig(), n, "sobota")
        self.assertEqual(kod, 1); self.assertIn("metoda", out)

    def test_history_zla_metoda(self):
        n = self.sobota(); n["history"][-1]["metoda"] = "v1.0 (momentum uznaniowe)"
        self.assertEqual(self.waliduj(sig(), n, "sobota")[0], 1)

    def test_history_dwa_wpisy(self):
        n = self.sobota(); n["history"].append(dict(HIST, week="2026-W9"))
        self.assertEqual(self.waliduj(sig(), n, "sobota")[0], 1)

    def test_nowa_version_bez_d0(self):
        n = self.sobota(); n["d0"] = sig()["d0"]
        kod, out = self.waliduj(sig(), n, "sobota")
        self.assertEqual(kod, 1); self.assertIn("d0", out)


class Porownaj(unittest.TestCase):
    def test_tabela_i_log(self):
        with tempfile.TemporaryDirectory() as d:
            def z(n, o):
                p = os.path.join(d, n); zapisz(p, o); return p
            sg = z("signals.json", sig())
            sym = z("sym.json", SYMBOLE)
            kursy = z("kursy.json", {"kursy": {
                "LPP": {"data": "2026-10-09", "close": 25040.0, "zrodlo": "bankier"},
                "PGE": {"data": "2026-10-09", "close": 16.7, "zrodlo": "cache z 2026-10-10"},
                "PKOBP": {"data": "2026-10-09", "close": 113.94, "zrodlo": "Yahoo"},
                "WIG20": {"data": "2026-10-09", "close": 4185.52, "zrodlo": "bankier"}}})
            batch = z("batch.json", {"success": True, "data": {
                "GPW:LPP": {"name": "LPP", "close": 25040.0, "change": 0.0, "update_mode": "delayed_streaming_900"},
                "GPW:PGE": {"name": "PGE", "close": 16.9, "change": 1.0, "update_mode": "delayed_streaming_900"},
                "GPW:PKO": {"name": "PKO", "close": 114.0, "change": 0.1, "update_mode": "delayed_streaming_900"},
                "GPW:WIG20": {"name": "WIG20", "close": 4185.52, "change": 0.0, "update_mode": "delayed_streaming_900"}},
                "missing": [{"symbol": "GPW:XXX", "reason": "Quote data not found"}]})
            # świece: 9.10 (07:00 UTC) i 12.10 (niedokończona o 08:15)
            ohl = z("lpp.json", {"symbol": "GPW:LPP", "bars": [{"t": 1791270000, "c": 24400.0},
                                                               {"t": 1791529200, "c": 25040.0},
                                                               {"t": 1791788400, "c": 25500.0}]})
            log = os.path.join(d, "log.jsonl")
            out = uruchom("tv_porownaj.py", "--tv", batch, "--ohlcv", ohl, "--kursy", kursy, "--d0", sg,
                          "--symbole", sym, "--teraz", "2026-10-12T08:15", "--log", log,
                          "--rutyna", "puls-wig20", "--wywolania", "2", "--czas-s", "30")
            self.assertEqual(out.returncode, 0, out.stderr)
            t = out.stdout
            self.assertIn("LPP", t)
            self.assertIn("|Δ| > 0,5% (ROZJAZD): PGE", t)            # 16,9 vs 16,7 = 1,2%
            self.assertIn("GPW:XXX", t)
            self.assertIn("+0.00", t)                                   # LPP świeca 9.10 = bankier
            with open(log, encoding="utf-8") as f:
                w = json.loads(f.read().strip())
            self.assertEqual(w["rozjazdy_gt_0_5"], ["PGE"])
            self.assertEqual(w["stan"], "OK")
            self.assertFalse(any(k in w for k in ("kapital", "saldo", "upl")))

    def test_w_sesji_batch_nie_liczony(self):
        with tempfile.TemporaryDirectory() as d:
            def z(n, o):
                p = os.path.join(d, n); zapisz(p, o); return p
            sg = z("signals.json", sig()); sym = z("sym.json", SYMBOLE)
            kursy = z("kursy.json", {"kursy": {"LPP": {"data": "2026-10-09", "close": 25040.0, "zrodlo": "bankier"}}})
            batch = z("batch.json", {"success": True, "data": {"GPW:LPP": {"name": "LPP", "close": 25500.0, "change": 1.8,
                                                                            "update_mode": "delayed_streaming_900"}}})
            out = uruchom("tv_porownaj.py", "--tv", batch, "--kursy", kursy, "--d0", sg, "--symbole", sym,
                          "--teraz", "2026-10-12T10:30")
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertIn("n = 0", out.stdout)
            self.assertIn("orientacyjnie", out.stdout)


class Merge(unittest.TestCase):
    LPP = {"2026-09-25": 24000.0, "2026-09-28": 24100.0, "2026-09-29": 24250.0, "2026-09-30": 24300.0,
           "2026-10-01": 24500.0, "2026-10-02": 24600.0, "2026-10-05": 24700.0, "2026-10-06": 24750.0,
           "2026-10-07": 24800.0, "2026-10-08": 24400.0, "2026-10-09": 25040.0}   # ex-date 8.10, 500 zł
    T0 = 1790751600  # 2026-09-25 07:00 UTC (piątek)
    DNI = ["2026-09-25", "2026-09-28", "2026-09-29", "2026-09-30", "2026-10-01", "2026-10-02",
           "2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08", "2026-10-09"]

    def t(self, data):
        from datetime import datetime, timezone
        return int(datetime.strptime(data + "T07:00", "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc).timestamp())

    def srodowisko(self, d, lpp_cache):
        cache = {"aktualizacja": {"WIG20": "2026-10-10 08:30", "LPP": "2026-10-10 08:30"},
                 "kursy": {"WIG20": {k: 4000.0 + i for i, k in enumerate(self.DNI)}, "LPP": lpp_cache}}
        pc = os.path.join(d, "cache.json"); zapisz(pc, cache)
        s = sig(); s["d0"]["prices"]["LPP"] = 25040.0
        ps = os.path.join(d, "signals.json"); zapisz(ps, s)
        pm = os.path.join(d, "sym.json"); zapisz(pm, SYMBOLE)
        return pc, ps, pm

    def ohlcv(self, d, seria, nazwa="lpp.json"):
        p = os.path.join(d, nazwa)
        zapisz(p, {"symbol": "GPW:LPP", "bars": [{"t": self.t(k), "c": v} for k, v in sorted(seria.items())]})
        return p

    def test_dopisuje_tylko_brakujace(self):
        with tempfile.TemporaryDirectory() as d:
            niepelny = {k: v for k, v in self.LPP.items() if k not in ("2026-10-06", "2026-10-07")}
            pc, ps, pm = self.srodowisko(d, niepelny)
            out = uruchom("tv_merge.py", "--ohlcv", self.ohlcv(d, self.LPP), "--cache", pc, "--d0", ps,
                          "--symbole", pm, "--tylko-brakujace", "--teraz", "2026-10-12T08:15", "--json")
            self.assertEqual(out.returncode, 0, out.stderr)
            w = json.loads(out.stdout)
            self.assertEqual(w["wyniki"][0]["dopisane"], ["2026-10-06", "2026-10-07"])
            self.assertEqual(w["backfill"], "LPP:2")
            c = odczytaj(pc)
            self.assertEqual(c["kursy"]["LPP"]["2026-10-07"], 24800.0)
            self.assertEqual(c["kursy"]["LPP"]["2026-10-09"], 25040.0)   # istniejąca nie nadpisana
            self.assertTrue(c["aktualizacja"]["LPP"].endswith("(TV)"))

    def test_seria_skorygowana_odrzucona(self):
        with tempfile.TemporaryDirectory() as d:
            niepelny = {k: v for k, v in self.LPP.items() if k != "2026-10-06"}
            pc, ps, pm = self.srodowisko(d, niepelny)
            skoryg = {k: (v - 500.0 if k < "2026-10-08" else v) for k, v in self.LPP.items()}
            out = uruchom("tv_merge.py", "--ohlcv", self.ohlcv(d, skoryg), "--cache", pc, "--d0", ps,
                          "--symbole", pm, "--tylko-brakujace", "--teraz", "2026-10-12T08:15", "--json")
            w = json.loads(out.stdout)
            self.assertEqual(w["wyniki"][0]["kod"], "TV_DANE_ROZBIEZNE")
            self.assertEqual(w["wyniki"][0]["dopisane"], [])
            self.assertNotIn("2026-10-06", odczytaj(pc)["kursy"]["LPP"])

    def test_rozjazd_d0_odrzuca(self):
        with tempfile.TemporaryDirectory() as d:
            pc, ps, pm = self.srodowisko(d, {k: v for k, v in self.LPP.items() if k != "2026-10-06"})
            zly = dict(self.LPP); zly["2026-10-09"] = 25400.0       # +1,4% vs d0.prices
            # usuń 9.10 z cache, żeby test ex-date nie złapał tego pierwszy
            c = odczytaj(pc); c["kursy"]["LPP"].pop("2026-10-09"); zapisz(pc, c)
            out = uruchom("tv_merge.py", "--ohlcv", self.ohlcv(d, zly), "--cache", pc, "--d0", ps,
                          "--symbole", pm, "--tylko-brakujace", "--teraz", "2026-10-12T08:15", "--json")
            w = json.loads(out.stdout)
            self.assertEqual(w["wyniki"][0]["kod"], "TV_DANE_ROZBIEZNE")
            self.assertIn("D0", w["wyniki"][0]["uwaga"])

    def test_niedokonczona_swieca_i_dry_run(self):
        with tempfile.TemporaryDirectory() as d:
            pc, ps, pm = self.srodowisko(d, dict(self.LPP))
            seria = dict(self.LPP); seria["2026-10-12"] = 25500.0
            out = uruchom("tv_merge.py", "--ohlcv", self.ohlcv(d, seria), "--cache", pc, "--d0", ps,
                          "--symbole", pm, "--tylko-brakujace", "--teraz", "2026-10-12T08:15", "--json", "--dry-run")
            w = json.loads(out.stdout)
            self.assertEqual(w["wyniki"][0]["dopisane"], [])             # 12.10 odrzucona (sesja trwa)
            out = uruchom("tv_merge.py", "--ohlcv", self.ohlcv(d, seria), "--cache", pc, "--d0", ps,
                          "--symbole", pm, "--tylko-brakujace", "--teraz", "2026-10-12T17:30", "--json", "--dry-run")
            w = json.loads(out.stdout)
            self.assertEqual(w["wyniki"][0]["dopisane"], ["2026-10-12"])  # po 17:10 = zakończona
            self.assertNotIn("2026-10-12", odczytaj(pc)["kursy"]["LPP"])  # dry-run nie zapisał

    def test_symbol_spoza_mapy_pominiety(self):
        with tempfile.TemporaryDirectory() as d:
            pc, ps, pm = self.srodowisko(d, dict(self.LPP))
            p = os.path.join(d, "x.json"); zapisz(p, {"symbol": "GPW:XYZ", "bars": [{"t": self.t("2026-10-09"), "c": 1.0}]})
            w = json.loads(uruchom("tv_merge.py", "--ohlcv", p, "--cache", pc, "--d0", ps, "--symbole", pm,
                                   "--tylko-brakujace", "--teraz", "2026-10-12T08:15", "--json").stdout)
            self.assertIsNone(w["wyniki"][0]["ticker"])
            self.assertFalse(w["zapisano"])


class PlikiTV(unittest.TestCase):
    def test_json_i_spojnosc(self):
        for p in ("data/tv-config.json", "data/tv-symbole.json", "data/tv-kolumny.json"):
            odczytaj(os.path.join(REPO, p))
        sym = odczytaj(os.path.join(REPO, "data", "tv-symbole.json"))
        s = odczytaj(os.path.join(REPO, "signals.json"))
        self.assertEqual(set(s["epics"]), set(sym["koszyk"]))
        self.assertTrue(all(v.startswith("GPW:") for v in sym["koszyk"].values()))


if __name__ == "__main__":
    unittest.main(verbosity=1)
