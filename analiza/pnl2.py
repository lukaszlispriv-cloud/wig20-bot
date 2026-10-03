import csv, json, datetime as dt, glob
from collections import defaultdict
UP="/root/.claude/uploads/0b350679-6ecf-5114-b35e-7c90e90355cc/"
files=[glob.glob(UP+"ad092914-*.csv")[0],glob.glob(UP+"4ad8ed11-*.csv")[0]]
cache=json.load(open("/home/user/wig20-bot/data/kursy-cache.json"))["kursy"]
MAP={"PKN":"PKNORLEN","MBK":"MBANK","PEO":"PEKAO","PGE":"PGE","TPE":"TAURONPE","PZU":"PZU","ALEP":"ALLEGRO","DNP":"DINOPL","KGH":"KGHM","BDXP":"BUDIMEX","KRU":"KRUK","ALRR":"ALIOR","CDR":"CDPROJEKT","PKO":"PKOBP","KTY":"KETY","PCOP":"PEPCO"}
HEDGES={"FW2020U2026","FW2020Z2026"}
seen={};
for f in files:
    for r in csv.DictReader(open(f)):
        seen[r["Exec Id"]]=r
rows=sorted(seen.values(),key=lambda r:r["Timestamp (UTC)"])
for r in rows: r["ts"]=dt.datetime.strptime(r["Timestamp (UTC)"][:19],"%Y-%m-%d %H:%M:%S")
print(len(rows),"unikalnych zdarzen", rows[0]["ts"], rows[-1]["ts"])
fut={}
opens={};realized=[];swaps=[]
for r in rows:
    s=r["Status"];q=float(r["Quantity"]);p=float(r["Price"]);sym=r["Instrument Symbol"]
    if s=="SWAP":
        swaps.append((r["ts"],float(r["Swap Converted"]),sym))
        if sym in HEDGES: fut[(sym,r["ts"].date())]=p
    elif s=="OPENED": opens[r["Trade Id"]+("@%s"%r["ts"].date() if r["Trade Id"] in opens else "")]=dict(sym=sym,q=q,p=p,t=r["ts"],closed=None,tid=r["Trade Id"])
    elif s=="CLOSED":
        # close the currently open position with this trade id
        cand=[o for o in opens.values() if o["tid"]==r["Trade Id"] and o["closed"] is None]
        o=cand[0]; o["closed"]=r["ts"]; o["cp"]=p
        realized.append((r["ts"],float(r["Rpl Converted"]),sym))
days=[];d=dt.date(2026,8,26)
while d<=dt.date(2026,10,2):
    if d.weekday()<5: days.append(d)
    d+=dt.timedelta(1)
def price(sym,d):
    if sym in HEDGES: return fut[(sym,d)]
    return cache[MAP[sym]][d.isoformat()]
W=cache["WIG20"]
out=[]
for d in days:
    end=dt.datetime.combine(d,dt.time(23,59))
    real=sum(x for t,x,_ in realized if t<=end)
    real_h=sum(x for t,x,s in realized if t<=end and s in HEDGES)
    sw=sum(x for t,x,_ in swaps if t<=end)
    sw_h=sum(x for t,x,s in swaps if t<=end and s in HEDGES)
    unr=unr_h=0;lnot=0;hnot=0
    for o in opens.values():
        if o["t"]<=end and (o["closed"] is None or o["closed"]>end):
            pr=price(o["sym"],d); u=o["q"]*(pr-o["p"]); unr+=u
            if o["sym"] in HEDGES: unr_h+=u; hnot+=abs(o["q"])*pr
            else: lnot+=o["q"]*pr
    out.append(dict(d=d.isoformat(),total=real+sw+unr,real=real,swap=sw,unr=unr,hedge_gross=real_h+unr_h,hedge_swap=sw_h,lnot=lnot,hnot=hnot,wig=W[d.isoformat()]))
Navg=sum(o["lnot"] for o in out)/len(out)
w0=W["2026-08-26"]
for o in out:
    o["longs"]=o["total"]-o["hedge_gross"]-o["hedge_swap"]
    o["bench"]=Navg*(o["wig"]/w0-1)
json.dump(dict(out=out,Navg=Navg),open("pnl2.json","w"),indent=1)
CAP=2960
for o in out[::1]: print(o["d"],f'tot {o["total"]:7.2f} longs {o["longs"]:7.2f} bench {o["bench"]:7.2f} hedgeGross {o["hedge_gross"]:7.2f} Lnot {o["lnot"]:6.0f} Hnot {o["hnot"]:6.0f} net {o["lnot"]-o["hnot"]:6.0f}')
last=out[-1]
print("Navg",round(Navg),"WIG20",w0,"->",out[-1]["wig"],round((out[-1]["wig"]/w0-1)*100,2),"%")
print({k:round(last[k],2) for k in ["total","real","swap","unr","longs","bench","hedge_gross","hedge_swap"]})
rp=defaultdict(float)
for t,x,s in realized: rp[s]+=x
print({k:round(v,2) for k,v in sorted(rp.items(),key=lambda kv:kv[1])})
sp=defaultdict(float)
for t,x,s in swaps: sp[s]+=x
print("swaps",{k:round(v,2) for k,v in sp.items()})
print("OPEN:",[(o["sym"],o["q"],o["p"],round(o["q"]*(price(o["sym"],days[-1])-o["p"]),2)) for o in opens.values() if o["closed"] is None])
# weekend 18->21.09 unhedged gap
print("W 18.09 close",W["2026-09-18"],"21.09",W["2026-09-21"])
