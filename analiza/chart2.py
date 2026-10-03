import json, datetime as dt
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.dates as md
J=json.load(open("pnl2.json"));o=J["out"];CAP=2990
x=[dt.date.fromisoformat(r["d"]) for r in o]
pc=lambda k:[r[k]/CAP*100 for r in o]
BG="#fcfcfb";INK="#0b0b0b";SEC="#52514e";GRID="#e6e5e1";B,Or,A="#2a78d6","#eb6834","#1baf7a"
fig,(ax,ax2)=plt.subplots(2,1,figsize=(10,7.4),dpi=160,facecolor=BG,gridspec_kw=dict(height_ratios=[3,1.1],hspace=0.28),sharex=True)
for a in (ax,ax2):
    a.set_facecolor(BG); a.grid(axis="y",color=GRID,lw=.8); a.set_axisbelow(True)
    for s in ["top","right","left"]: a.spines[s].set_visible(False)
    a.spines["bottom"].set_color(GRID); a.tick_params(colors=SEC,length=0,labelsize=9.5)
ax.axhline(0,color=SEC,lw=.8)
ax.plot(x,pc("bench"),color=Or,lw=2,marker="o",ms=3.5,mec=BG,mew=1.2)
ax.plot(x,pc("longs"),color=A,lw=2,ls=(0,(5,3)),marker="s",ms=3.5,mec=BG,mew=1.2)
ax.plot(x,pc("total"),color=B,lw=2.6,marker="o",ms=4.5,mec=BG,mew=1.2)
for k,c,t in [("bench",Or,"Benchmark WIG20"),("longs",A,"Koszyk LONG"),("total",B,"Rachunek")]:
    y=pc(k)[-1]; ax.annotate(f"{t}  {y:+.2f}%".replace(".",","),(x[-1],y),xytext=(8,0),textcoords="offset points",color=INK,fontsize=9.5,va="center",annotation_clip=False)
g0,g1=dt.date(2026,9,18),dt.date(2026,9,21)
for a in (ax,ax2): a.axvspan(g0,g1,color="#eda100",alpha=.14,lw=0)
ax.text(g0+dt.timedelta(days=1.5),-2.62,"18.09 16:13 – 21.09 08:01\nbrak hedge'u (wygasł kontrakt)",fontsize=8,color=SEC,ha="center",va="bottom")
ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v,_:f"{v:+.1f}%".replace(".",",")))
ax.set_title(f"Skumulowany wynik w % kapitału ({CAP:,} PLN), po swapach".replace(","," "),loc="left",fontsize=10,color=SEC,pad=8)
net=[(r["lnot"]-r["hnot"])/CAP*100 for r in o]
cols=[Or if v<0 else B for v in net]
ax2.bar(x,net,color=A,width=.7)
ax2.axhline(0,color=SEC,lw=.8)
ax2.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v,_:f"{v:+.0f}%"))
ax2.set_title("Ekspozycja netto rachunku (LONG − short na indeks), % kapitału",loc="left",fontsize=10,color=SEC,pad=8)
ax2.xaxis.set_major_formatter(md.DateFormatter("%d.%m")); ax2.xaxis.set_major_locator(md.DayLocator(interval=3))
ax.set_xlim(x[0]-dt.timedelta(days=.6),x[-1]+dt.timedelta(days=1))
fig.suptitle("Wynik rachunku vs benchmark WIG20, 26.08 – 02.10.2026",x=.06,ha="left",fontsize=14,fontweight="bold",color=INK,y=.975)
fig.text(.06,.012,"Źródło: historia transakcji Capital.com (2 pliki), data/kursy-cache.json. Benchmark: WIG20 przy stałej ekspozycji 1 251 PLN (średnia ekspozycja koszyka LONG).",fontsize=7,color=SEC)
fig.subplots_adjust(left=.08,right=.80,top=.9,bottom=.07)
fig.savefig("wynik_vs_benchmark_do_2026-10-02.png",facecolor=BG)
