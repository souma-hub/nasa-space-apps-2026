# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx", "python-dotenv", "numpy"]
# ///
"""発表用デモ画面 docs/demo/index.html を作る（1 ファイル完結、オフラインで file:// で開ける）。

係数（results/unified_model.json）・過去 23 台風（results/unified_kanto_loo.csv）を
HTML に JSON として埋め込む。係数を学習し直したら、これを実行し直す。検証は check_demo.py。
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import nasa_common  # noqa: E402,F401  出力の UTF-8 固定のため

from lodging_unified import FORECAST_FACTOR, VARIETY_JA, VARIETY_RAIN_FACTOR  # noqa: E402

MODEL = ROOT / "results/unified_model.json"
TYPHOONS = ROOT / "results/unified_kanto_loo.csv"
OUT = ROOT / "docs/demo/index.html"


def build_data():
    model = json.loads(MODEL.read_text(encoding="utf-8"))
    typhoons = []
    with TYPHOONS.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            typhoons.append({
                "name": r["台風"], "date": r["最接近"],
                "rain": float(r["雨IMERG"]), "wind": float(r["風POWER"]), "gdd": float(r["コシ出穂後"]),
                "damage_ha": float(r["被害ha"]), "damaged": r["被害あり"] == "True",
                "p_unified": float(r["p_unified"]),
            })
    return {"model": model, "forecast_factor": FORECAST_FACTOR, "variety_rain_factor": VARIETY_RAIN_FACTOR,
            "variety_ja": VARIETY_JA, "typhoons": typhoons}


def main():
    data = build_data()
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.replace("__DATA__", blob)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8", newline="\n")
    print(f"書き出し: {OUT}（{len(html) / 1024:.0f} KB、台風 {len(data['typhoons'])} 個）")


TEMPLATE = r'''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>刈り取り判断モデル（デモ用）</title>
<!-- このファイルは make_demo.py が自動で作る。手で直さない。 -->
<style>
:root{--bg:#f5f6f8;--panel:#fff;--ink:#1f2933;--sub:#52606d;--line:#d9dee3;--accent:#1f5fa8;--red:#c0392b;--redbg:#fbeceb;--green:#2e7d32;--greenbg:#e8f3e9}
*{box-sizing:border-box}
html{font-size:min(1.1vw,1.9vh)}
body{margin:0;background:var(--bg);color:var(--ink);font-family:system-ui,"Hiragino Sans","Yu Gothic UI","Meiryo",sans-serif;height:100vh;overflow:hidden;display:grid;grid-template-rows:auto 1fr auto;font-variant-numeric:tabular-nums}
header{display:flex;align-items:baseline;padding:.4rem 1rem;background:#fff;border-bottom:1px solid var(--line)}
header h1{margin:0;font-size:1.5rem;font-weight:700}
main{display:grid;grid-template-columns:5fr 7fr;grid-template-rows:auto 1fr;gap:.6rem;min-height:0;padding:.6rem 1rem}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:4px;padding:.6rem .8rem;min-height:0}
#inputs{grid-row:1/3;overflow:auto;display:flex;flex-direction:column;justify-content:flex-start;gap:1.6rem;padding:.8rem}
#result{display:grid;grid-template-columns:auto 1fr;gap:1rem;align-items:stretch}
#scatterbox{position:relative;display:flex;flex-direction:column}
h2{margin:0 0 .35rem;font-size:.95rem;color:var(--sub);font-weight:700}
.row{display:grid;grid-template-columns:1fr 1fr;gap:.6rem;margin-bottom:.4rem}
label{display:block;font-size:.85rem;color:var(--sub)}
select{width:100%;font:inherit;font-size:1rem;padding:.2rem;color:var(--ink)}
.sl{margin:.2rem 0 .4rem}
.sl .top{display:flex;justify-content:space-between;align-items:baseline;font-size:.9rem}
.sl .top .v{font-size:1.25rem;font-weight:700}
.sl .top .unit{font-size:.8rem;color:var(--sub)}
input[type=range]{width:100%;margin:.1rem 0;accent-color:var(--accent)}
.sl.off{opacity:.45}
.sl .note{font-size:.8rem;color:var(--sub);min-height:1em}
#card{min-width:13rem;border-radius:4px;display:flex;flex-direction:column;justify-content:center;align-items:center;padding:.5rem 1rem;border:1px solid}
#card.h{background:var(--redbg);border-color:var(--red);color:var(--red)}
#card.w{background:var(--greenbg);border-color:var(--green);color:var(--green)}
#card .big{font-size:3.2rem;font-weight:700;line-height:1.15}
#detail{min-width:0}
.prob{font-size:1rem;margin-bottom:.1rem}
.prob b{font-size:1.8rem}
#bar{width:100%;height:3.2rem;display:block}
#scatter{flex:1;min-height:0;width:100%}
#tip{position:absolute;pointer-events:none;background:var(--ink);color:#fff;font-size:.85rem;padding:.25rem .5rem;border-radius:4px;display:none;white-space:nowrap;z-index:5}
footer{font-size:.8rem;color:var(--sub);display:flex;gap:1.2rem;flex-wrap:wrap;align-items:baseline;padding:.4rem 1rem;border-top:1px solid var(--line);background:#fff}
footer .msg{font-weight:700;color:var(--ink);font-size:.9rem}
</style>
</head>
<body>
<header><h1>刈り取り判断モデル（デモ用）</h1></header>
<main>
<section class="panel" id="inputs">
  <h2>入力</h2>
  <div class="row">
    <div><label for="pref">都道府県</label><select id="pref"></select></div>
    <div><label for="variety">品種</label><select id="variety"></select></div>
  </div>
  <div class="sl"><div class="top"><span>過去 2 日の雨</span><span><span class="v" id="v_past"></span> <span class="unit">mm</span></span></div><input type="range" id="past" min="0" max="200" step="1"></div>
  <div class="sl"><div class="top"><span>これから 2 日の予報の雨</span><span><span class="v" id="v_fc"></span> <span class="unit">mm</span></span></div><input type="range" id="fc" min="0" max="300" step="1"></div>
  <div class="sl"><div class="top"><span>10 m 最大風速</span><span><span class="v" id="v_wind"></span> <span class="unit">m/s</span></span></div><input type="range" id="wind" min="0" max="40" step="0.1"></div>
  <div class="sl" id="gddbox"><div class="top"><span>出穂後積算気温</span><span><span class="v" id="v_gdd"></span> <span class="unit">℃</span></span></div><input type="range" id="gdd" min="0" max="2000" step="1"><div class="note" id="gddnote"></div></div>
</section>
<section class="panel" id="result">
  <div id="card"><div class="big" id="dec"></div></div>
  <div id="detail">
    <div class="prob">被害が出る確率の目安 <b id="pv"></b>　<span style="color:var(--sub);font-size:.9rem">閾値 <span id="tv"></span></span></div>
    <svg id="bar" role="img" aria-label="確率と閾値"></svg>
  </div>
</section>
<section class="panel" id="scatterbox">
  <h2>過去の台風（茨城・千葉の検証 23 個）と今の入力</h2>
  <svg id="scatter"></svg>
  <div id="tip"></div>
</section>
</main>
<footer>
  <span class="msg">判断するのは農家です。</span>
  <span>データ: GPM IMERG・NASA POWER</span>
</footer>

<script id="data" type="application/json">__DATA__</script>
<script id="core">
// 判定ロジック。lodging_unified.py の decide() の忠実な移植（DOM に触れない。check_demo.py が node で検証する）
function sgn2(x){return (x<0?"-":"+")+Math.abs(x).toFixed(2);}
function localFor(pref,P){
  for(const name of Object.keys(P.local)){ if(P.local[name].prefs.indexOf(pref)>=0) return [name,P.local[name]]; }
  return [null,null];
}
function decide(D,pref,rainPast,rainForecast,wind,gdd,variety){
  const P=D.model;
  if(!(pref in P.pref)) throw new Error("学習にない都道府県です: "+pref);
  const vf=D.variety_rain_factor[variety];
  const rain=(rainPast+D.forecast_factor*rainForecast)/vf;
  let z=P.intercept
    +P.rain.coef*(Math.log1p(rain)-P.rain.mu)/P.rain.sd
    +P.wind.coef*(wind-P.wind.mu)/P.wind.sd
    +P.pref[pref];
  const lf=localFor(pref,P), name=lf[0], loc=lf[1];
  const useLocal=loc!==null&&gdd!==null&&gdd!==undefined;
  let pc=P.pref[pref];
  if(useLocal){ pc=loc.prefs.reduce((a,q)=>a+P.pref[q],0)/loc.prefs.length; }
  z+=pc-P.pref[pref];
  const reasons=[
    "雨 "+rainPast.toFixed(0)+" mm（過去）＋ "+rainForecast.toFixed(0)+" mm（予報、安全側に 1.5 倍）"
      +(vf!==1?"、"+D.variety_ja[variety]+"は倒れにくいので "+String(vf)+" で割る":""),
    "風 "+wind.toFixed(1)+" m/s（NASA の 10 m 最大風速）",
    (useLocal?name+"の補正 "+sgn2(pc):pref+"の補正 "+sgn2(pc))+"（同じ雨風でも被害の出やすさが地域で違う）"
  ];
  let thr;
  if(useLocal){
    const lo=loc.gdd_window[0], hi=loc.gdd_window[1];
    const ripe=(lo<=gdd&&gdd<hi)?1:0;
    z+=loc.d+loc.e_ripe*ripe;
    thr=loc.threshold;
    if(gdd<lo) reasons.push("稲がまだ青い（出穂後 "+gdd.toFixed(0)+"℃ < "+lo.toFixed(0)+"℃）ので倒れにくい［"+name+"の地域の知見］");
    else if(gdd>=hi) reasons.push("出穂後 "+gdd.toFixed(0)+"℃ で、収穫の時期を過ぎている［"+name+"の地域の知見］");
    else reasons.push("稲が実って倒れやすい時期（出穂後 "+gdd.toFixed(0)+"℃）［"+name+"の地域の知見］");
  }else{
    thr=P.threshold_national;
    reasons.push("実り具合はこの県では使わない（品種・作付け時期の前提がないため、全国の部分だけで判断）");
  }
  const p=1/(1+Math.exp(-z));
  const harvest=p>=thr; // 閾値は保存時に 0.999 倍済み（unified_model.py）。境界の確率とは離れている
  return {harvest:harvest,decision:harvest?"刈る":"待ってよい",probability:p,threshold:thr,reasons:reasons,effRain:rain,useLocal:useLocal};
}
</script>
<script id="ui">
(function(){
if(typeof document==="undefined") return;
const D=JSON.parse(document.getElementById("data").textContent);
const P=D.model;
const $=id=>document.getElementById(id);
const NS="http://www.w3.org/2000/svg";
function el(tag,attrs,parent,text){const e=document.createElementNS(NS,tag);for(const k in attrs)e.setAttribute(k,attrs[k]);if(text!==undefined)e.textContent=text;if(parent)parent.appendChild(e);return e;}
const LOCAL_PREFS=[].concat(...Object.values(P.local).map(l=>l.prefs));
const LOC=Object.values(P.local)[0];
const gw=LOC.gdd_window;
function kf(){return parseFloat(getComputedStyle(document.documentElement).fontSize)/14;}
const INK="#1f2933",SUB="#52606d",ACC="#1f5fa8",RED="#c0392b",GREEN="#2e7d32";

Object.keys(P.pref).forEach(k=>{const o=document.createElement("option");o.value=o.textContent=k;$("pref").appendChild(o);});
Object.keys(D.variety_ja).forEach(k=>{const o=document.createElement("option");o.value=k;o.textContent=D.variety_ja[k];$("variety").appendChild(o);});

function setInputs(o){
  $("pref").value=o.pref;$("variety").value=o.variety;
  $("past").value=o.past;$("fc").value=o.forecast;$("wind").value=o.wind;
  if(o.gdd!==null&&o.gdd!==undefined)$("gdd").value=o.gdd;
}
["pref","variety","past","fc","wind","gdd"].forEach(id=>$(id).addEventListener("input",update));

let last=null;
function update(){
  const pref=$("pref").value, variety=$("variety").value;
  const past=+$("past").value, fc=+$("fc").value, wind=+$("wind").value, gddv=+$("gdd").value;
  const local=LOCAL_PREFS.indexOf(pref)>=0;
  $("gdd").disabled=!local;$("gddbox").classList.toggle("off",!local);
  $("gddnote").textContent=local?"":"この県では使わない";
  $("v_past").textContent=past.toFixed(0);$("v_fc").textContent=fc.toFixed(0);$("v_wind").textContent=wind.toFixed(1);
  $("v_gdd").textContent=local?gddv.toFixed(0):"―";
  const g=local?gddv:null;
  const r=decide(D,pref,past,fc,wind,g,variety);
  last={r:r,gdd:local?gddv:null};
  $("card").className=r.harvest?"h":"w";
  $("dec").textContent=r.decision;
  $("pv").textContent=(r.probability*100).toFixed(1)+"%";
  $("tv").textContent=(r.threshold*100).toFixed(1)+"%";
  drawBar(r);drawScatter();
}

// 横棒（平方根目盛り。小さい確率が見えるように）
function drawBar(r){
  const K=kf();
  const svg=$("bar");svg.textContent="";
  const W=svg.clientWidth||600,H=svg.clientHeight||50;
  const m=8,w=W-2*m,y=H*0.4,h=H*0.27;
  const sx=p=>m+Math.sqrt(Math.min(1,Math.max(0,p)))*w;
  el("rect",{x:m,y:y,width:w,height:h,fill:"#eceff2",stroke:"#bcc4cc"},svg);
  el("rect",{x:m,y:y,width:sx(r.probability)-m,height:h,fill:r.harvest?RED:GREEN},svg);
  const tx=sx(r.threshold);
  el("line",{x1:tx,x2:tx,y1:y-4,y2:y+h+4,stroke:INK,"stroke-width":2.5},svg);
  el("text",{x:tx,y:y-7,"text-anchor":"middle","font-size":13*K,"font-weight":700,fill:INK},svg,"閾値");
  [0,0.1,0.25,0.5,1].forEach(p=>{const x=sx(p);el("line",{x1:x,x2:x,y1:y+h,y2:y+h+4,stroke:SUB},svg);
    el("text",{x:x,y:H-2,"text-anchor":p===0?"start":p===1?"end":"middle","font-size":12*K,fill:SUB},svg,(p*100)+"%");});
}

// 散布図
const XMAX=Math.max(300,Math.ceil(Math.max(...D.typhoons.map(t=>t.rain))/50)*50), YMAX=2000;
const tip=$("tip");
function starPts(x,y,ro,ri){const pts=[];for(let k=0;k<10;k++){const rr=k%2?ri:ro,ang=-Math.PI/2+k*Math.PI/5;pts.push((x+rr*Math.cos(ang)).toFixed(1)+","+(y+rr*Math.sin(ang)).toFixed(1));}return pts.join(" ");}
function drawScatter(){
  const K=kf();
  const svg=$("scatter");svg.textContent="";
  const box=$("scatterbox");
  const W=svg.clientWidth||800,H=svg.clientHeight||200;
  const ml=62*K,mr=14,mt=8,mb=38*K;
  const w=W-ml-mr,h=H-mt-mb;
  const sx=v=>ml+Math.log1p(Math.min(Math.max(v,0),XMAX))/Math.log1p(XMAX)*w;
  const sy=v=>mt+h-Math.min(Math.max(v,0),YMAX)/YMAX*h;
  el("rect",{x:ml,y:mt,width:w,height:h,fill:"#fff",stroke:"#9aa5b1"},svg);
  el("rect",{x:ml,y:sy(gw[1]),width:w,height:sy(gw[0])-sy(gw[1]),fill:"#e6eef8"},svg);
  el("text",{x:ml+6,y:sy(gw[1])+15,"font-size":12*K,fill:ACC},svg,"実って倒れやすい時期（"+gw[0]+"〜"+gw[1]+"℃）");
  [0,5,10,20,50,100,200,300].filter(v=>v<=XMAX).forEach(v=>{const x=sx(v);
    el("line",{x1:x,x2:x,y1:mt,y2:mt+h,stroke:"#eceff2"},svg);
    el("line",{x1:x,x2:x,y1:mt+h,y2:mt+h+4,stroke:SUB},svg);
    el("text",{x:x,y:mt+h+17*K,"text-anchor":"middle","font-size":12*K,fill:SUB},svg,String(v));});
  [0,500,1000,1500,2000].forEach(v=>{const y=sy(v);
    el("line",{x1:ml,x2:ml+w,y1:y,y2:y,stroke:"#eceff2"},svg);
    el("line",{x1:ml-4,x2:ml,y1:y,y2:y,stroke:SUB},svg);
    el("text",{x:ml-7,y:y+4,"text-anchor":"end","font-size":12*K,fill:SUB},svg,String(v));});
  el("text",{x:ml+w/2,y:H-4,"text-anchor":"middle","font-size":13*K,fill:INK},svg,"雨（mm、GPM IMERG、対数軸）");
  el("text",{x:13*K,y:mt+h/2,"text-anchor":"middle","font-size":13*K,fill:INK,transform:"rotate(-90 "+13*K+" "+(mt+h/2)+")"},svg,"出穂後積算気温（℃、コシヒカリ）");
  D.typhoons.forEach((t,i)=>{
    const x=sx(t.rain),y=sy(t.gdd);
    let s;
    if(t.damaged) s=el("rect",{x:x-6,y:y-6,width:12,height:12,fill:RED,stroke:"#7b241c","stroke-width":1.5,transform:"rotate(45 "+x+" "+y+")"},svg);
    else s=el("circle",{cx:x,cy:y,r:6,fill:"#fff",stroke:INK,"stroke-width":2},svg);
    s.style.cursor="pointer";
    const show=ev=>{const b=box.getBoundingClientRect();tip.style.display="block";
      tip.textContent=t.name+"　"+(t.damaged?"被害あり "+t.damage_ha.toFixed(0)+" ha":"被害なし")+"　雨 "+t.rain.toFixed(0)+" mm・"+t.gdd.toFixed(0)+"℃";
      let L=ev.clientX-b.left+12;if(L+tip.offsetWidth>b.width)L=ev.clientX-b.left-tip.offsetWidth-12;
      tip.style.left=L+"px";tip.style.top=(ev.clientY-b.top-30)+"px";};
    s.addEventListener("mousemove",show);s.addEventListener("mouseenter",show);s.addEventListener("mouseleave",()=>{tip.style.display="none";});
  });
  if(last){
    const x=sx(last.r.effRain);
    if(last.gdd===null){
      el("line",{x1:x,x2:x,y1:mt,y2:mt+h,stroke:ACC,"stroke-width":2,"stroke-dasharray":"6 4"},svg);
      el("text",{x:x-6,y:mt+16,"text-anchor":"end","font-size":12*K,fill:ACC},svg,"今の雨（この県は気温を使わない）");
    }else{
      el("polygon",{points:starPts(x,sy(last.gdd),13,5.5),fill:ACC,stroke:INK,"stroke-width":1.5},svg);
    }
  }
  const lx=ml+16,ly=mt+h-64*K+2;
  el("rect",{x:lx-8,y:ly-6,width:130*K,height:64*K,fill:"#fff",stroke:"#bcc4cc"},svg);
  el("rect",{x:lx+1,y:ly+4*K,width:11,height:11,fill:RED,stroke:"#7b241c","stroke-width":1.5,transform:"rotate(45 "+(lx+6.5)+" "+(ly+9.5)+")"},svg);
  el("text",{x:lx+22*K,y:ly+14*K,"font-size":13*K,fill:INK},svg,"被害あり");
  el("circle",{cx:lx+6.5,cy:ly+30*K,r:6,fill:"#fff",stroke:INK,"stroke-width":2},svg);
  el("text",{x:lx+22*K,y:ly+34*K,"font-size":13*K,fill:INK},svg,"被害なし");
  el("polygon",{points:starPts(lx+6.5,ly+49*K,8,3.5),fill:ACC,stroke:INK},svg);
  el("text",{x:lx+22*K,y:ly+53*K,"font-size":13*K,fill:INK},svg,"今の入力");
}
window.addEventListener("resize",update);
// URL クエリで初期値を渡せる（例: ?pref=茨城&variety=koshihikari&past=40&forecast=80&wind=18&gdd=900）。不正値は既定値のまま
const q=new URLSearchParams(location.search);
function qnum(k,def,id){const s=q.get(k);if(s===null||s.trim()==="")return def;const v=Number(s),e=$(id);return(isFinite(v)&&v>=+e.min&&v<=+e.max)?v:def;}
const qp=q.get("pref"),qv=q.get("variety");
setInputs({pref:(qp&&qp in P.pref)?qp:"茨城",variety:(qv&&qv in D.variety_ja)?qv:"koshihikari",
  past:qnum("past",40,"past"),forecast:qnum("forecast",80,"fc"),wind:qnum("wind",18,"wind"),gdd:qnum("gdd",900,"gdd")});
update();
})();
</script>
</body>
</html>
'''

if __name__ == "__main__":
    main()
