import json, csv, datetime as dt
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.dates as md
J=json.load(open("pnl.json")); out=J["out"]; CAP=J["cap"]
# hedge swaps cumulative
import re
CSV="/root/.claude/uploads/0b350679-6ecf-5114-b35e-7c90e90355cc/ad092914-leveraged_trades_history_16.08.2026.csv"
hs=[]
for r in csv.DictReader(open(CSV)):
    if r["Status"]=="SWAP" and r["Instrument Symbol"]=="FW2020U2026":
        hs.append((dt.datetime.strptime(r["Timestamp (UTC)"][:19],"%Y-%m-%d %H:%M:%S"),float(r["Swap Converted"])))
x=[dt.date.fromisoformat(o["d"]) for o in out]
acct=[o["total"] for o in out]
bench=[-o["unr_h"] for o in out]                      # 0,37 kontraktu LONG na WIG20 = ta sama ekspozycja co koszyk
hsw=[sum(v for t,v in hs if t<=dt.datetime.combine(dd,dt.time(23,59))) for dd in x]
longs=[o["total"]-o["unr_h"]-h for o,h in zip(out,hsw)]   # koszyk LONG bez hedge'u (z jego swapami)
pct=lambda v:[a/CAP*100 for a in v]
BG="#fcfcfb";INK="#0b0b0b";SEC="#52514e";GRID="#e6e5e1"
B,O,A="#2a78d6","#eb6834","#1baf7a"
fig,ax=plt.subplots(figsize=(10,5.6),dpi=160,facecolor=BG); ax.set_facecolor(BG)
ax.axhline(0,color=SEC,lw=0.8)
ax.plot(x,pct(bench),color=O,lw=2,marker="o",ms=4,mec=BG,mew=1.5,label="Benchmark: WIG20 (0,37 kontraktu long, ta sama ekspozycja)")
ax.plot(x,pct(longs),color=A,lw=2,ls=(0,(5,3)),marker="s",ms=4,mec=BG,mew=1.5,label="Koszyk LONG bez hedge'u")
ax.plot(x,pct(acct),color=B,lw=2.6,marker="o",ms=5,mec=BG,mew=1.5,label="Rachunek (LONG + short na indeks, po swapach)")
for y,c,t,dy in [(pct(bench)[-1],O,"Benchmark WIG20",0.12),(pct(longs)[-1],A,"Koszyk LONG",0.12),(pct(acct)[-1],B,"Rachunek",-0.25)]:
    ax.annotate(f"{t}  {y:+.2f}%".replace(".",","),(x[-1],y),xytext=(8,0),textcoords="offset points",color=INK,fontsize=9.5,va="center",annotation_clip=False)
ax.set_xlim(x[0],x[-1]+dt.timedelta(days=3.2))
ax.xaxis.set_major_formatter(md.DateFormatter("%d.%m")); ax.xaxis.set_major_locator(md.DayLocator(interval=2))
ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v,_:f"{v:+.1f}%".replace(".",",")))
ax.grid(axis="y",color=GRID,lw=0.8); ax.set_axisbelow(True)
for s in ["top","right","left"]: ax.spines[s].set_visible(False)
ax.spines["bottom"].set_color(GRID); ax.tick_params(colors=SEC,length=0,labelsize=9.5)
fig.suptitle("Wynik rachunku vs benchmark WIG20, 26.08 – 14.09.2026",x=0.06,ha="left",fontsize=14,fontweight="bold",color=INK)
ax.set_title(f"Skumulowany wynik w % kapitału ({CAP:,.0f} PLN), po swapach; otwarte pozycje wg zamknięć".replace(","," "),loc="left",fontsize=10,color=SEC,pad=10)
ax.legend(loc="upper left",frameon=False,fontsize=9,labelcolor=SEC)
fig.text(0.06,0.015,"Źródło: leveraged_trades_history (Capital.com), data/kursy-cache.json. Benchmark = −(niezrealizowany wynik shorta indeksu). Rachunek = LONG − benchmark − swapy.",fontsize=7,color=SEC)
fig.tight_layout(rect=(0,0.03,1,0.95)); fig.savefig("wynik_vs_benchmark.png",facecolor=BG)
f=lambda v:f"{v[-1]:+.2f} PLN ({v[-1]/CAP*100:+.2f}%)"
print("acct",f(acct),"| longs",f(longs),"| bench",f(bench),"| hedge swaps",hsw[-1])
# REDUCE counterfactual
cf={"KRU":(0.6*(403.396-443.804)+0, None)}
