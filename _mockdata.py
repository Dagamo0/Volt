"""Generate a realistic data.json matching the real pipeline schema, WITHOUT network.
Used to build/preview the dashboard. The live pipeline produces the identical shape."""
import json, random, datetime as dt, math
import config, universe as uni

random.seed(7)

def spark(base):
    out, p = [], base
    for _ in range(30):
        p *= (1 + random.uniform(-0.02, 0.022)); out.append(round(p, 4))
    return out

def ohlc_chart(base):
    """Generate 90 days of plausible OHLC bars + Turtle channel overlays."""
    import datetime as _dt
    bars=[]; p=base*0.85
    start=_dt.date.today()-_dt.timedelta(days=125)  # ~90 trading days back
    d=start
    closes=[]
    while len(bars)<90:
        if d.weekday()<5:  # weekdays only
            o=p
            c=o*(1+random.uniform(-0.025,0.027))
            hi=max(o,c)*(1+random.uniform(0,0.015))
            lo=min(o,c)*(1-random.uniform(0,0.015))
            bars.append({"time":d.isoformat(),"open":round(o,2),"high":round(hi,2),"low":round(lo,2),"close":round(c,2)})
            closes.append(c); p=c
        d+=_dt.timedelta(days=1)
    def chan(n,kind):
        out=[]
        for i,b in enumerate(bars):
            if i<n: continue
            window=bars[i-n:i]
            v=max(x["high"] for x in window) if kind=="high" else min(x["low"] for x in window)
            out.append({"time":b["time"],"value":round(v,2)})
        return out
    return {"bars":bars,"ch20High":chan(20,"high"),"ch20Low":chan(20,"low"),
            "ch55High":chan(55,"high"),"ch55Low":chan(55,"low")}

def make(meta, focus):
    base = random.uniform(20, 600) if meta["category"] in ("equity","ai","momentum","index") else \
           random.uniform(30000,110000) if meta["category"]=="crypto" else random.uniform(1,3500)
    price = round(base, 2)
    change = round(random.uniform(-7, 7), 2)
    atr = round(price*random.uniform(0.01,0.05), 4)
    atr_pct = round(atr/price*100, 2)
    rsi = round(random.uniform(20, 85), 1)
    vscore = min(100, max(5, round(atr_pct*14)))
    vlabel, vcolor = (("Very High","#ff3366") if vscore>=75 else ("High","#ffaa00") if vscore>=60
                      else ("Moderate","#4488ff") if vscore>=40 else ("Low","#4488ff"))
    # Randomly fire scanners on ~12% of names
    turtle=swing=snap=None
    r=random.random()
    if r<0.05:
        d=random.choice(["long","short"]); ch=random.choice(["20-day","55-day"])
        shares=round((config.DEFAULT_ACCOUNT_SIZE*0.01)/(atr*2),2)
        turtle={"type":"turtle","direction":d,"channel":ch,"trigger_level":price,
                "entry":price,"stop":round(price-(atr*2 if d=="long" else -atr*2),4),"atr":atr,
                "size":{"shares":shares,"dollar_risk":round(config.DEFAULT_ACCOUNT_SIZE*0.01,2),
                        "stop_distance":round(atr*2,4),"notional":round(shares*price,2)},
                "note":f"{ch} {'breakout' if d=='long' else 'breakdown'}"}
    elif r<0.09 and meta["category"] in ("ai","index","momentum"):
        d=random.choice(["long","short"])
        snap={"type":"snapback","direction":d,"move_mult":round(random.uniform(2,3.5),2),
              "rsi":rsi,"vol_x":round(random.uniform(1.5,4),1),
              "note":f"{'Spiked' if d=='short' else 'Dropped'} {random.uniform(2,3):.1f}x ADR"}
    elif r<0.12:
        d=random.choice(["long","short"])
        swing={"type":"swing","direction":d,"weekly_trend":"up" if d=="long" else "down",
               "note":"Pullback complete, momentum turning","rsi":rsi,"ref_level":round(price*0.98,2)}
    # ~3% of names: stack a confirming second/third scanner (real confluence) for a hot play
    if turtle and random.random()<0.35:
        d=turtle["direction"]
        swing={"type":"swing","direction":d,"weekly_trend":"up" if d=="long" else "down",
               "note":"Trend pullback aligning with breakout","rsi":rsi,"ref_level":round(price*0.98,2)}
        if meta["category"] in ("ai","index","momentum") and random.random()<0.5:
            snap={"type":"snapback","direction":d,"move_mult":round(random.uniform(2,3.5),2),
                  "rsi":rsi,"vol_x":round(random.uniform(2.5,4),1),
                  "note":f"Volume surge confirming the break"}
    fired=bool(turtle or swing or snap)
    longs=sum(1 for s in(turtle,swing,snap) if s and s["direction"]=="long")
    shorts=sum(1 for s in(turtle,swing,snap) if s and s["direction"]=="short")
    sgnl=("bullish" if longs and not shorts else "bearish" if shorts and not longs
          else "watch" if (longs and shorts) or rsi>68 or rsi<32 else "neutral")
    # Build a synthetic df just for conviction scoring (needs rsi + macd_hist cols)
    import pandas as _pd
    _wk = random.choice(["up","down","sideways"])
    _df = _pd.DataFrame({"rsi":[rsi]*2, "macd_hist":[random.uniform(-1,1), random.uniform(-1,1)]})
    import signals as _sig
    conv, reasons = _sig.conviction_score(_df, turtle, swing, snap, _wk)
    tier = _sig.conviction_tier(conv)
    return {"id":meta["yf"].lower().replace("=","").replace("^","").replace("-",""),
            "ticker":meta["ticker"],"name":meta["name"],"category":meta["category"],
            "icon":meta["icon"],"color":meta["color"],"focus":focus,"error":None,
            "price":price,"change":change,"vol":vscore,"volLabel":vlabel,"volColor":vcolor,
            "sparkline":spark(price),"signal":sgnl,"fired":fired,
            "conviction":conv,"convictionTier":tier,"convictionReasons":reasons,
            "metrics":{"rsi":rsi,"atr":atr,"atrPct":atr_pct,
                       "macd":random.choice(["Bullish cross","Bullish","Bearish","Flat","Bearish cross"]),
                       "support":round(price*0.95,4),"resistance":round(price*1.06,4),
                       "volRatio":f"{random.uniform(0.8,3.5):.1f}x avg",
                       "weeklyTrend":_wk},
            "scanners":{"turtle":turtle,"swing":swing,"snapback":snap},
            "earnings":(dt.date.today()+dt.timedelta(days=random.randint(2,70))).isoformat() if random.random()<0.3 else None,
            "headlines":([{"title":h,"publisher":random.choice(["Reuters","Bloomberg","CNBC","Barron's"]),"link":"https://finance.yahoo.com","published":(dt.date.today()-dt.timedelta(days=random.randint(0,3))).strftime("%b %d")} for h in random.sample(["Analyst raises price target on strong demand","Chip sector rallies on AI capex guidance","Options activity spikes ahead of earnings","Macro headwinds weigh on the tape","Insider buying disclosed in filing","Upgrade cites margin expansion"], k=random.randint(1,3))] if (focus or fired) else []),
            "chart":(ohlc_chart(price) if (focus or fired) else None)}

metas=[]
for a in config.WATCHLIST:
    metas.append(({"yf":a["yf"],"ticker":a["ticker"],"name":a["name"],"category":a["category"],
                   "icon":a["icon"],"color":a["color"]}, True))
for m in uni.curated_non_equity():
    metas.append(({"yf":m["yf"],"ticker":m["ticker"],"name":m["ticker"],"category":m["category"],
                   "icon":m["ticker"][:2].upper(),"color":"#5a5a78"}, False))
for s in uni.SP500_FALLBACK:
    metas.append(({"yf":s,"ticker":s,"name":s,"category":uni.equity_category(s),
                   "icon":s[:2].upper(),"color":"#5a5a78"}, False))

seen=set(); assets=[]
for meta,focus in metas:
    if meta["yf"] in seen: continue
    seen.add(meta["yf"]); assets.append(make(meta,focus))

import catalysts as cat
today=dt.date.today(); end=today+dt.timedelta(days=21)
macro=cat.macro_events(today,end)
earn=[{"date":a["earnings"],"text":f"{a['ticker']} earnings","tag":"earnings","scope":a["ticker"]}
      for a in assets if a["earnings"] and a["earnings"]<=(end+dt.timedelta(days=75)).isoformat()]
calf=sorted(macro+earn,key=lambda x:x["date"])
import sentiment as _sm
_sv, _cv = random.randint(20,80), random.randint(20,80)
sent_block={"stock":{"value":_sv,"label":_sm.label_from_value(_sv)},
            "crypto":{"value":_cv,"label":_sm.label_from_value(_cv)},
            "asOf":dt.datetime.utcnow().isoformat()+"Z"}
ok=len(assets); fired=sum(1 for a in assets if a["fired"])
payload={"generated":dt.datetime.utcnow().isoformat()+"Z","sensitivity":config.SENSITIVITY,
         "defaultAccountSize":config.DEFAULT_ACCOUNT_SIZE,"riskPerTradePct":config.RISK_PER_TRADE_PCT,
         "atrStopMultiple":config.ATR_STOP_MULTIPLE,
         "focus":[a for a in assets if a["focus"]],"universe":assets,"calendar":calf,
         "sentiment":sent_block,
         "stats":{"ok":ok,"failed":0,"total":len(assets),"fired":fired}}
json.dump(payload,open("data.json","w"),indent=2,default=str)
print(f"Wrote data.json: {len(assets)} assets, {fired} fired, {len(calf)} calendar events")
