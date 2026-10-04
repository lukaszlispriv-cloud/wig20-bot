import csv, json, datetime as dt
from collections import defaultdict
CSV="/root/.claude/uploads/0b350679-6ecf-5114-b35e-7c90e90355cc/ad092914-leveraged_trades_history_16.08.2026.csv"
cache=json.load(open("/home/user/wig20-bot/data/kursy-cache.json"))["kursy"]
MAP={"PKN":"PKNORLEN","MBK":"MBANK","PEO":"PEKAO","PGE":"PGE","TPE":"TAURONPE","PZU":"PZU","ALEP":"ALLEGRO","DNP":"DINOPL","KGH":"KGHM","BDXP":"BUDIMEX","KRU":"KRUK"}
HEDGE="FW2020U2026"
rows=list(csv.DictReader(open(CSV)))
for r in rows: r["ts"]=dt.datetime.strptime(r["Timestamp (UTC)"][:19],"%Y-%m-%d %H:%M:%S")
rows.sort(key=lambda r:r["ts"])
fut={}  # date -> futures price (swap rows 21:00)
for r in rows:
    if r["Status"]=="SWAP" and r["Instrument Symbol"]==HEDGE: fut[r["ts"].date()]=float(r["Price"])
opens={}; events=[]
realized=[];swaps=[]
for r in rows:
    s=r["Status"];q=float(r["Quantity"]);p=float(r["Price"])
    if s=="OPENED": opens[r["Trade Id"]]=dict(sym=r["Instrument Symbol"],q=q,p=p,t=r["ts"],closed=None)
    elif s=="CLOSED":
        o=opens[r["Trade Id"]]; o["closed"]=r["ts"]; o["cp"]=p
        realized.append((r["ts"],float(r["Rpl Converted"]),r["Instrument Symbol"]))
    elif s=="SWAP": swaps.append((r["ts"],float(r["Swap Converted"]),r["Instrument Symbol"]))
days=[]; d=dt.date(2026,8,26)
while d<=dt.date(2026,9,14):
    if d.weekday()<5: days.append(d)
    d+=dt.timedelta(1)
def price(sym,d):
    if sym==HEDGE: return fut[d]
    return cache[MAP[sym]][d.isoformat()]
CAP=2960.0
out=[]
for d in days:
    end=dt.datetime.combine(d,dt.time(23,59))
    real=sum(x for t,x,_ in realized if t<=end)
    sw=sum(x for t,x,_ in swaps if t<=end)
    unr=0;unr_long=0;unr_h=0
    for o in opens.values():
        if o["t"]<=end and (o["closed"] is None or o["closed"]>end):
            u=o["q"]*(price(o["sym"],d)-o["p"])
            unr+=u
            if o["sym"]==HEDGE: unr_h+=u
            else: unr_long+=u
    hedge_real=0
    # hedge realized: none (still open)
    out.append(dict(d=d.isoformat(),real=real,swap=sw,unr=unr,unr_h=unr_h,unr_long=unr_long,total=real+sw+unr,fut=fut[d]))
H0=[o for o in opens.values() if o["sym"]==HEDGE][0]
for o in out:
    o["bench_pct"]=(o["fut"]/H0["p"]-1)*100
    o["acct_pct"]=o["total"]/CAP*100
    o["unhedged"]=o["total"]-o["unr_h"]   # same longs, no hedge leg (swap of hedge kept; approx)
    o["unh_pct"]=o["unhedged"]/CAP*100
    # excess: acct vs benchmark scaled to avg gross long
json.dump(dict(out=out,H0=H0["p"],cap=CAP),open("/home/user/wig20-bot/analiza/pnl.json","w"),default=str,indent=1)
for o in out: print(o["d"],f'real {o["real"]:7.2f} swap {o["swap"]:6.2f} unrLong {o["unr_long"]:7.2f} unrHedge {o["unr_h"]:7.2f} TOTAL {o["total"]:7.2f} ({o["acct_pct"]:+.2f}%) bench {o["bench_pct"]:+.2f}% unhedged {o["unh_pct"]:+.2f}%')
# per-position
print()
pp=defaultdict(float)
for t,x,s in realized: pp[s]+=x
print("realized by sym",{k:round(v,2) for k,v in pp.items()}, round(sum(pp.values()),2))
ps=defaultdict(float)
for t,x,s in swaps: ps[s]+=x
print("swaps by sym",{k:round(v,2) for k,v in ps.items()}, round(sum(ps.values()),2))
last=days[-1]
for o in opens.values():
    if o["closed"] is None: print("OPEN",o["sym"],o["q"],o["p"],"->",price(o["sym"],last),round(o["q"]*(price(o["sym"],last)-o["p"]),2),"notional",round(abs(o["q"])*o["p"],0))
# sizing at entry
print()
for o in sorted(opens.values(),key=lambda o:o["t"]):
    print(o["t"],o["sym"],o["q"],o["p"],"notional",round(abs(o["q"])*o["p"]),"closed",o["closed"])
