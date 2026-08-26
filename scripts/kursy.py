#!/usr/bin/env python3
"""Pobiera dzienne kursy zamkniecia z Yahoo Finance chart API (GPW: tickery z sufiksem .WA).

Uzycie: python3 scripts/kursy.py WIG20.WA DNP.WA KGH.WA ...
Wypisuje po 10 ostatnich wierszy data;close per ticker. Ostatni wiersz z dzisiejsza
data przy otwartej sesji GPW to kurs srodsesyjny, nie zamkniecie.
"""
import json, subprocess, sys, time

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36")
HOSTS = ("query2.finance.yahoo.com", "query1.finance.yahoo.com")


def fetch(sym):
    for _ in range(5):
        for host in HOSTS:
            url = f"https://{host}/v8/finance/chart/{sym}?range=1mo&interval=1d"
            try:
                out = subprocess.run(
                    ["curl", "-sS", "--max-time", "20", "-A", UA, url],
                    capture_output=True, text=True, timeout=30).stdout
                j = json.loads(out)
                if j.get("chart", {}).get("result"):
                    return j["chart"]["result"][0]
            except Exception:
                pass
        time.sleep(4)
    return None


def main():
    for sym in sys.argv[1:]:
        data = fetch(sym)
        if not data:
            print(f"=== {sym}: FAIL")
            continue
        ts = data.get("timestamp", [])
        closes = data["indicators"]["quote"][0].get("close", [])
        rows = [(time.strftime("%Y-%m-%d", time.gmtime(t)), c)
                for t, c in zip(ts, closes) if c is not None]
        print(f"=== {sym} ({data['meta'].get('currency')})")
        for d, c in rows[-10:]:
            print(f"{d};{c:.4f}")
        time.sleep(1.5)


if __name__ == "__main__":
    main()
