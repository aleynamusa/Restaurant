"""Outputs: a self-contained HTML review page (lead list + map), plus CSV export."""
from __future__ import annotations

import csv
import html
import json
from datetime import date
from pathlib import Path

from .models import Lead

STAGE_LABEL = {"permit_applied": "Permit applied", "permit_granted": "Permit granted",
               "announced": "Opening soon", "opened": "Recently opened", "unknown": "Stage unknown"}


def write_csv(leads: list[Lead], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "score", "tier", "status", "name", "city", "address", "category", "stage",
                    "event_date", "expected_opening", "opening_basis", "email", "phone", "website",
                    "lat", "lon", "geo_precision",
                    "subject", "body", "reasons", "sources"])
        for l in leads:
            w.writerow([l.id, l.score, l.tier, l.status, l.name, l.city, l.address, l.category, l.stage,
                        l.event_date, *l.expected_opening(), l.email, l.phone, l.website,
                        l.lat, l.lon, l.geo_precision,
                        l.email_subject, l.email_body,
                        " | ".join(l.score_reasons), " ".join(s["url"] for s in l.sources)])


def write_html(leads: list[Lead], path: Path, seller: dict) -> None:
    data = [{
        "stage_key": l.stage, "opening": l.expected_opening()[0], "opening_basis": l.expected_opening()[1],
        "id": l.id, "name": l.name, "city": l.city, "address": l.address, "category": l.category,
        "stage": STAGE_LABEL.get(l.stage, l.stage), "date": l.event_date, "score": l.score, "tier": l.tier,
        "reasons": l.score_reasons, "evidence": l.evidence, "tech": l.detected_tech, "email": l.email,
        "phone": l.phone, "website": l.website, "subject": l.email_subject, "body": l.email_body,
        "generator": l.email_generator, "status": l.status, "sources": l.sources,
        "lat": l.lat, "lon": l.lon, "geo": l.geo_precision,
    } for l in leads]
    page = TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/")) \
                   .replace("__TITLE__", html.escape(f"{seller['company']} lead review")) \
                   .replace("__DATE__", date.today().isoformat())
    path.write_text(page, encoding="utf-8")


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
  integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin="">
<style>
:root{--bg:#f4f3ef;--panel:#fff;--ink:#1c1c1a;--muted:#6b6a65;--line:#e4e2db;--soft:#efede7;--hover:#f7f6f2;
--sel:#e7f1ee;--accent:#1f6f5c;--accent-ink:#fff;--hot:#c2410c;--warm:#b7791f;--cold:#64748b;--plus:#2f7d4f;
--minus:#b4401f;--field:#fbfaf7;--shadow:0 1px 2px rgba(0,0,0,.06),0 4px 14px rgba(0,0,0,.06);color-scheme:light}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#121211;--panel:#1c1c1a;--ink:#ecebe6;
--muted:#9d9b94;--line:#2e2d2a;--soft:#262523;--hover:#22211f;--sel:#1b2e29;--accent:#4fb39a;--accent-ink:#0b1714;
--hot:#f07b52;--warm:#e2b04c;--cold:#94a3b8;--plus:#6cc28f;--minus:#ef8a6b;--field:#171715;
--shadow:0 1px 2px rgba(0,0,0,.4),0 4px 14px rgba(0,0,0,.3);color-scheme:dark}}
:root[data-theme="dark"]{--bg:#121211;--panel:#1c1c1a;--ink:#ecebe6;--muted:#9d9b94;--line:#2e2d2a;--soft:#262523;
--hover:#22211f;--sel:#1b2e29;--accent:#4fb39a;--accent-ink:#0b1714;--hot:#f07b52;--warm:#e2b04c;--cold:#94a3b8;
--plus:#6cc28f;--minus:#ef8a6b;--field:#171715;--shadow:0 1px 2px rgba(0,0,0,.4),0 4px 14px rgba(0,0,0,.3);color-scheme:dark}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
button,input,select,textarea{font:inherit;color:inherit}
a{color:var(--accent)}
.app{display:grid;grid-template-rows:auto auto auto 1fr;height:100vh}
/* header */
.top{display:flex;flex-wrap:wrap;align-items:center;gap:10px 18px;padding:14px 20px;background:var(--panel);border-bottom:1px solid var(--line)}
.brand h1{font-size:18px;margin:0;letter-spacing:-.01em}
.brand .sub{color:var(--muted);font-size:12.5px}
.stats{display:flex;gap:8px;flex-wrap:wrap;margin-left:auto}
.stat{background:var(--soft);border-radius:8px;padding:4px 10px;font-size:12.5px;color:var(--muted)}
.stat b{color:var(--ink);font-size:14px;margin-right:3px}
.btn{border:1px solid var(--line);background:var(--panel);border-radius:8px;padding:7px 12px;cursor:pointer;font-size:13px;text-decoration:none;color:var(--ink);display:inline-flex;align-items:center;gap:6px}
.btn:hover{background:var(--hover)}
.btn.primary{background:var(--accent);border-color:var(--accent);color:var(--accent-ink);font-weight:600}
.btn.primary:hover{filter:brightness(1.06)}
.btn.ghost{border-color:transparent;background:transparent;padding:6px 8px}
/* toolbar */
.tools{display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:10px 20px;border-bottom:1px solid var(--line);background:var(--bg)}
.seg{display:inline-flex;background:var(--soft);border-radius:9px;padding:3px}
.seg button{border:0;background:transparent;border-radius:7px;padding:5px 11px;cursor:pointer;font-size:13px;color:var(--muted)}
.seg button[aria-pressed=true]{background:var(--panel);color:var(--ink);box-shadow:var(--shadow);font-weight:600}
.seg .n{font-size:11px;margin-left:4px;opacity:.75}
.search{flex:1;min-width:160px;max-width:320px;border:1px solid var(--line);background:var(--panel);border-radius:8px;padding:7px 10px;font-size:13px}
.tools select{border:1px solid var(--line);background:var(--panel);border-radius:8px;padding:6px 8px;font-size:13px}
.spacer{flex:1}
.fgroup{display:flex;flex-wrap:wrap;align-items:center;gap:6px}
.flabel{font-size:12px;color:var(--muted);margin-right:2px}
.tchip{border:1px solid var(--line);background:var(--panel);border-radius:999px;padding:4px 11px;font-size:12.5px;cursor:pointer}
.tchip:hover{background:var(--hover)}
.tchip[aria-pressed=true]{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.tchip .n{font-size:11px;margin-left:4px;opacity:.7}
.check{display:inline-flex;align-items:center;gap:5px;font-size:12.5px;color:var(--muted);cursor:pointer}
.tools2{padding-top:0}
.tools.row1{border-bottom:0}
.linkbtn{border:0;background:none;color:var(--accent);cursor:pointer;padding:0;font-size:13px;text-decoration:underline}
.chip.open-reported{background:var(--sel);color:var(--accent);font-weight:600}
/* main split */
.main{display:grid;grid-template-columns:minmax(340px,460px) 1fr;min-height:0}
.side{overflow:auto;border-right:1px solid var(--line);background:var(--panel)}
.mapwrap{position:relative;min-height:0}
#map{position:absolute;inset:0;background:var(--soft)}
.mapmsg{position:absolute;inset:0;display:grid;place-items:center;text-align:center;color:var(--muted);padding:24px}
/* list */
.row{display:flex;gap:12px;align-items:center;width:100%;text-align:left;border:0;border-bottom:1px solid var(--line);background:transparent;padding:12px 18px;cursor:pointer}
.row:hover,.row.hl{background:var(--hover)}
.row.sel{background:var(--sel)}
.row.done{opacity:.55}
.badge{flex:none;width:40px;height:40px;border-radius:10px;display:grid;place-items:center;color:#fff;font-weight:700;font-size:15px}
.badge.hot{background:var(--hot)}.badge.warm{background:var(--warm)}.badge.cold{background:var(--cold)}
.rbody{flex:1;min-width:0}
.rname{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rmeta{color:var(--muted);font-size:12.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rflag{flex:none;font-size:11px;color:var(--muted);border:1px solid var(--line);border-radius:999px;padding:1px 8px}
.empty{color:var(--muted);text-align:center;padding:48px 20px}
/* detail */
.dnav{position:sticky;top:0;z-index:2;display:flex;align-items:center;gap:6px;padding:10px 14px;background:var(--panel);border-bottom:1px solid var(--line)}
.dnav .pos{color:var(--muted);font-size:12.5px;margin-left:auto;margin-right:4px}
.detail{padding:16px 18px 40px;display:grid;gap:14px}
.hero{display:flex;gap:14px;align-items:flex-start}
.hero .badge{width:56px;height:56px;font-size:21px;border-radius:12px;flex-direction:column;line-height:1}
.hero .badge small{font-size:9.5px;font-weight:600;text-transform:uppercase;letter-spacing:.06em;margin-top:3px;opacity:.9}
.hero h2{margin:0;font-size:19px;line-height:1.25;overflow-wrap:anywhere}
.addr{color:var(--muted);font-size:13px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.chip{background:var(--soft);border-radius:999px;padding:2px 9px;font-size:12px}
.chip.status-sent{background:var(--sel);color:var(--accent)}.chip.status-skipped{color:var(--muted)}
.card{border:1px solid var(--line);border-radius:12px;padding:14px;background:var(--panel)}
.card h3{font-size:11.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:0 0 10px;display:flex;justify-content:space-between;gap:8px}
.card h3 span{text-transform:none;letter-spacing:0;font-weight:400}
label.f{display:block;font-size:12px;color:var(--muted);margin:8px 0 3px}
input.in,textarea.in{width:100%;font-size:14px;background:var(--field);border:1px solid var(--line);border-radius:8px;padding:8px 10px}
input.in:focus,textarea.in:focus,.search:focus{outline:2px solid var(--accent);outline-offset:-1px;border-color:transparent}
textarea.in{min-height:240px;resize:vertical;line-height:1.5}
.actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
.reasons{list-style:none;margin:0;padding:0;display:grid;gap:6px}
.reasons li{display:flex;gap:10px;align-items:baseline;font-size:13px}
.pts{flex:none;min-width:38px;text-align:right;font-weight:700;font-variant-numeric:tabular-nums}
.pts.plus{color:var(--plus)}.pts.minus{color:var(--minus)}
.ev{margin:0;padding-left:18px;font-size:13px;display:grid;gap:4px}
.kv{display:grid;grid-template-columns:auto 1fr;gap:4px 12px;font-size:13px}
.kv dt{color:var(--muted)}.kv dd{margin:0;overflow-wrap:anywhere}
.warn{color:var(--minus)}
.hint{color:var(--muted);font-size:12px}
/* map pins */
.pin{width:32px;height:32px;border-radius:50%;display:grid;place-items:center;color:#fff;font-weight:700;font-size:12px;
border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.35);transition:transform .12s}
.pin.hot{background:var(--hot)}.pin.warm{background:var(--warm)}.pin.cold{background:var(--cold)}
.pin.approx{border-style:dashed;opacity:.8}
.pin.done{filter:grayscale(1);opacity:.55}
.pin.sel,.pin.hl{transform:scale(1.3);border-color:var(--ink);opacity:1;z-index:1000}
.legend{position:absolute;left:12px;bottom:22px;z-index:500;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:8px 12px;font-size:12px;box-shadow:var(--shadow);display:grid;gap:4px}
.legend i{display:inline-block;width:11px;height:11px;border-radius:50%;margin-right:6px;vertical-align:-1px}
.legend .dash{border:1.5px dashed var(--muted);background:transparent}
.leaflet-container{font:inherit}
#map.dark .leaflet-tile-pane{filter:invert(1) hue-rotate(180deg) brightness(.9) contrast(.9) saturate(.6)}
.leaflet-tooltip{font-size:12.5px}
/* phones / narrow */
@media (max-width:880px){
 .app{height:auto;display:block}
 .main{display:flex;flex-direction:column}
 .mapwrap{order:-1;height:46vh;min-height:280px}
 .side{border-right:0;overflow:visible}
 .top,.tools{padding-left:16px;padding-right:16px}
 .stats{margin-left:0}
 .search{max-width:none;flex-basis:100%;order:1}
 .tools select{flex:1}
}
</style></head><body>
<div class="app">
 <header class="top">
  <div class="brand"><h1>__TITLE__</h1><div class="sub">Generated __DATE__ · New and soon-to-open restaurants ranked by how likely they need a POS</div></div>
  <div class="stats" id="stats"></div>
 </header>
 <div class="tools row1" role="toolbar" aria-label="Filters">
  <div class="seg" id="seg">
   <button data-f="todo" aria-pressed="true">To do<span class="n"></span></button>
   <button data-f="hot" aria-pressed="false">Hot<span class="n"></span></button>
   <button data-f="all" aria-pressed="false">All<span class="n"></span></button>
   <button data-f="done" aria-pressed="false">Sent &amp; skipped<span class="n"></span></button>
  </div>
  <input class="search" id="q" type="search" placeholder="Search name, city or street" aria-label="Search">
  <select id="sort" aria-label="Sort by"><option value="score">Sort: score</option><option value="opening">Sort: opening soonest</option><option value="date">Sort: newest signal</option><option value="city">Sort: city</option></select>
  <span class="spacer"></span>
  <button class="btn" id="export" title="Download your statuses and edited drafts as decisions.json">Export decisions</button>
 </div>
 <div class="tools tools2" role="toolbar" aria-label="Type and opening filters">
  <div class="fgroup" id="types"><span class="flabel">Type</span>
   <button class="tchip" data-t="restaurant" aria-pressed="false">Restaurants<span class="n"></span></button>
   <button class="tchip" data-t="cafe" aria-pressed="false">Cafés<span class="n"></span></button>
   <button class="tchip" data-t="bar" aria-pressed="false">Bars<span class="n"></span></button>
   <button class="tchip" data-t="fast_food" aria-pressed="false">Fast food<span class="n"></span></button>
   <button class="tchip" data-t="other" aria-pressed="false">Other<span class="n"></span></button>
  </div>
  <div class="fgroup"><span class="flabel">Opening</span>
   <select id="when" aria-label="Filter by when the place opens">
    <option value="any">Any time</option><option value="soon">Opening within 30 days</option>
    <option value="months">Opening in 1–3 months</option><option value="later">Opening in 3+ months</option>
    <option value="open">Already open</option><option value="unknown">Opening date unknown</option></select>
   <label class="check" title="Ignore estimated dates and only use opening dates a source actually reported"><input type="checkbox" id="reportedOnly"> Reported dates only</label>
  </div>
 </div>
 <div class="main">
  <aside class="side" id="side" aria-live="polite"></aside>
  <section class="mapwrap" aria-label="Map of leads"><div id="map"></div>
   <div class="legend" id="legend" hidden>
    <div><i style="background:var(--hot)"></i>Hot (70+)</div><div><i style="background:var(--warm)"></i>Warm (45–69)</div>
    <div><i style="background:var(--cold)"></i>Cold (&lt;45)</div><div><i class="dash"></i>Approximate (city centre)</div>
    <div class="hint" id="unmapped"></div>
   </div></section>
 </div>
</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
  integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
<script>
const LEADS=__DATA__;
const BY_ID=Object.fromEntries(LEADS.map(l=>[l.id,l]));
const KEY="horeca-leads-state";
let state={};try{state=JSON.parse(localStorage.getItem(KEY)||"{}")}catch(e){}
const save=()=>{try{localStorage.setItem(KEY,JSON.stringify(state))}catch(e){}};
const st=l=>(state[l.id]||{});
const statusOf=l=>st(l).status||l.status;
const isDone=l=>["sent","skipped"].includes(statusOf(l));
let filter="todo",query="",sort="score",selected=null,types=new Set(),when="any",reportedOnly=false;

const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const safeUrl=u=>/^https?:\/\//i.test(u||"")?u:"";
const CAT={restaurant:"Restaurant",cafe:"Café",bar:"Bar",fast_food:"Fast food"};
const SRC={bekendmakingen:"Municipal gazette",osm:"OpenStreetMap",news:"News",csv:"Imported list"};
const TECH={pos:"POS",ordering:"Ordering",reservations:"Reservations",delivery:"Delivery"};
const TIER={hot:"Hot",warm:"Warm",cold:"Cold"};
const cap=s=>s.replace(/_/g," ").replace(/\b\w/g,c=>c.toUpperCase());
const techLabel=t=>{const[k,v]=t.split(":");return v==="OWN_PRODUCT"?"Already our customer":`${TECH[k]||cap(k)}: ${cap(v||"")}`};
const fmtDate=d=>{if(!d)return"";const x=new Date(d+"T00:00:00");return isNaN(x)?d:x.toLocaleDateString("en-GB",{day:"numeric",month:"short",year:"numeric"})};

const pad=n=>String(n).padStart(2,"0");
const now=new Date(),TODAY=`${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())}`;
const daysUntil=iso=>Math.round((new Date(iso+"T00:00:00")-new Date(TODAY+"T00:00:00"))/864e5);
const fmtMonth=d=>new Date(d+"T00:00:00").toLocaleDateString("en-GB",{month:"short",year:"numeric"});
const typeOf=l=>CAT[l.category]?l.category:"other";
// the opening date we go by: reported, or estimated from the permit stage unless "reported only" is on
const openingOf=l=>(l.opening&&(l.opening_basis==="reported"||!reportedOnly))?l.opening:"";
function whenOf(l){
  if(l.stage_key==="opened")return"open";
  const d=openingOf(l);if(!d)return"unknown";
  const n=daysUntil(d);return n<=0?"open":n<=30?"soon":n<=90?"months":"later";
}
function openingText(l,short){
  const d=openingOf(l);
  if(l.stage_key==="opened")return short?"":"Already open";
  if(!d)return short?"":"Opening date not known yet";
  const est=l.opening_basis==="estimated";
  if(whenOf(l)==="open")return est?(short?"Probably open":"Probably open by now (estimate)"):`Opened ${fmtDate(d)}`;
  return est?`Opens ~${fmtMonth(d)}${short?" (est.)":" (estimate)"}`:`Opens ${fmtDate(d)}`;
}
function passesExtra(l,skip){
  if(skip!=="types"&&types.size&&!types.has(typeOf(l)))return false;
  if(skip!=="when"&&when!=="any"&&whenOf(l)!==when)return false;
  return true;
}
const filtersActive=()=>types.size||when!=="any"||query;
function inFilter(l,f){const done=isDone(l);if(f==="all")return true;if(f==="done")return done;return !done&&(f!=="hot"||l.tier==="hot")}
function matchesQuery(l){if(!query)return true;return [l.name,l.city,l.address].join(" ").toLowerCase().includes(query)}
function shown(){
  const out=LEADS.filter(l=>inFilter(l,filter)&&matchesQuery(l)&&passesExtra(l));
  if(sort==="opening")out.sort((a,b)=>(openingOf(a)||"9999").localeCompare(openingOf(b)||"9999")||b.score-a.score);
  else if(sort==="date")out.sort((a,b)=>(b.date||"").localeCompare(a.date||"")||b.score-a.score);
  else if(sort==="city")out.sort((a,b)=>(a.city||"~").localeCompare(b.city||"~")||b.score-a.score);
  else out.sort((a,b)=>b.score-a.score);
  return out;
}

/* ---------- header + filters ---------- */
function renderChrome(){
  const todo=LEADS.filter(l=>!isDone(l)).length,hot=LEADS.filter(l=>l.tier==="hot"&&!isDone(l)).length;
  const sent=LEADS.filter(l=>statusOf(l)==="sent").length;
  document.getElementById("stats").innerHTML=
    `<span class="stat"><b>${LEADS.length}</b>leads</span><span class="stat"><b>${hot}</b>hot to do</span><span class="stat"><b>${sent}</b>sent</span>`;
  document.querySelectorAll("#seg button").forEach(b=>{
    b.setAttribute("aria-pressed",b.dataset.f===filter);
    b.querySelector(".n").textContent=LEADS.filter(l=>inFilter(l,b.dataset.f)&&matchesQuery(l)&&passesExtra(l)).length;
  });
  const base=LEADS.filter(l=>inFilter(l,filter)&&matchesQuery(l));
  document.querySelectorAll("#types .tchip").forEach(b=>{
    b.setAttribute("aria-pressed",types.has(b.dataset.t));
    b.querySelector(".n").textContent=base.filter(l=>typeOf(l)===b.dataset.t&&passesExtra(l,"types")).length;
  });
  const LBL={any:"Any time",soon:"Opening within 30 days",months:"Opening in 1–3 months",later:"Opening in 3+ months",open:"Already open",unknown:"Opening date unknown"};
  for(const o of document.getElementById("when").options){
    const pool=base.filter(l=>passesExtra(l,"when"));
    o.textContent=`${LBL[o.value]} (${o.value==="any"?pool.length:pool.filter(l=>whenOf(l)===o.value).length})`;
  }
}

/* ---------- sidebar: list ---------- */
function renderList(){
  const side=document.getElementById("side"),list=shown();
  if(!list.length){side.innerHTML=`<div class="empty">${filtersActive()?`No leads match these filters.<br><button class="linkbtn" data-act="clear">Clear type, opening and search filters</button>`:filter==="done"?"Nothing sent or skipped yet.":"All done here. Nice work."}</div>`;return}
  side.innerHTML=list.map(l=>{
    const meta=[l.city,CAT[l.category],l.stage,openingText(l,true)||fmtDate(l.date)].filter(Boolean).join(" · ");
    const flag=isDone(l)?`<span class="rflag">${esc(statusOf(l))}</span>`:(l.lat==null?`<span class="rflag" title="No location found">not on map</span>`:"");
    return `<button class="row ${isDone(l)?"done":""}" data-id="${l.id}">
      <span class="badge ${l.tier}" aria-label="score ${l.score}">${l.score}</span>
      <span class="rbody"><div class="rname">${esc(l.name)}</div><div class="rmeta">${esc(meta)}</div></span>${flag}</button>`}).join("");
}

/* ---------- sidebar: detail ---------- */
function renderDetail(){
  const l=BY_ID[selected],s=st(l),list=shown(),i=list.findIndex(x=>x.id===l.id);
  const done=isDone(l),status=statusOf(l);
  const reasons=l.reasons.map(r=>{const m=r.match(/^([+-]?\d+)\s+(.*)$/);const n=m?+m[1]:0;
    return `<li><span class="pts ${n<0?"minus":"plus"}">${m?(n>0?"+"+n:n):""}</span><span>${esc(m?m[2]:r)}</span></li>`}).join("");
  const sources=l.sources.map(x=>{const u=safeUrl(x.url),label=`${SRC[x.source]||cap(x.source)}: ${x.title||x.url}`;
    return `<li>${u?`<a href="${esc(u)}" target="_blank" rel="noopener" title="${esc(x.original_title||"")}">${esc(label)}</a>`:esc(label)}</li>`}).join("");
  const web=safeUrl(l.website&&!/^https?:/i.test(l.website)?"https://"+l.website:l.website);
  const where=l.geo==="city"?`<span class="hint">Shown at the ${esc(l.city)} city centre; exact address not found.</span>`
    :l.lat==null?`<span class="hint">No map location found.</span>`:"";
  document.getElementById("side").innerHTML=`
  <div class="dnav"><button class="btn ghost" data-act="back">← All leads</button>
    <span class="pos">${i>=0?`${i+1} of ${list.length}`:""}</span>
    <button class="btn" data-act="prev" ${i<=0?"disabled":""} aria-label="Previous lead">↑</button>
    <button class="btn" data-act="next" ${i<0||i>=list.length-1?"disabled":""} aria-label="Next lead">↓</button></div>
  <div class="detail" data-id="${l.id}">
   <div class="hero"><div class="badge ${l.tier}">${l.score}<small>${TIER[l.tier]||""}</small></div>
    <div style="min-width:0"><h2>${esc(l.name)}</h2><div class="addr">${esc([l.address,l.city].filter(Boolean).join(", "))}</div>
     <div class="chips"><span class="chip">${esc(l.stage)}${l.date?" · "+esc(fmtDate(l.date)):""}</span>
      ${l.category?`<span class="chip">${esc(CAT[l.category]||cap(l.category))}</span>`:""}
      <span class="chip status-${esc(status)}">Status: ${esc(status)}</span></div>
     <div class="chips"><span class="chip ${l.opening_basis==="reported"&&l.stage_key!=="opened"?"open-reported":""}">${esc(openingText(l,false))}</span></div>
     ${l.opening_basis==="estimated"&&l.stage_key!=="opened"?`<div class="hint" style="margin-top:4px">Estimate: ${l.stage_key==="permit_granted"?"venues usually open a few weeks after the permit is granted":"municipalities usually decide on a permit within about 8 weeks of the application"}. No source has reported a date yet.</div>`:""}
     ${where?`<div style="margin-top:6px">${where}</div>`:""}</div></div>

   <section class="card"><h3>Draft email <span>${l.generator==="claude"?"Written by Claude":l.generator?"From template":""}</span></h3>
    ${l.body||s.body?`
    <label class="f" for="to">To</label><input class="in to" id="to" value="${esc(s.to??l.email)}" placeholder="No email found yet: look one up before sending">
    <label class="f" for="subj">Subject</label><input class="in subj" id="subj" value="${esc(s.subject??l.subject)}">
    <label class="f" for="body">Message</label><textarea class="in body" id="body">${esc(s.body??l.body)}</textarea>
    <div class="actions"><button class="btn primary" data-act="mail">Open in email app</button><button class="btn" data-act="copy">Copy</button>
     <span class="spacer"></span>
     ${done?`<button class="btn" data-act="mark" data-s="new">Move back to to do</button>`
       :`<button class="btn" data-act="mark" data-s="sent">Mark sent</button><button class="btn" data-act="mark" data-s="skipped">Skip</button>`}</div>
    <div class="hint" style="margin-top:8px">Edits are saved in this browser. Shortcuts: J / K next / previous, Esc back to list.</div>`
    :`<div class="hint">No draft: this lead scored below the drafting threshold.</div>
      <div class="actions">${done?`<button class="btn" data-act="mark" data-s="new">Move back to to do</button>`:`<button class="btn" data-act="mark" data-s="skipped">Skip</button>`}</div>`}
   </section>

   <section class="card"><h3>Why this score <span>${l.score} / 100</span></h3><ul class="reasons">${reasons}</ul></section>

   <section class="card"><h3>Evidence</h3><ul class="ev">${l.evidence.map(e=>`<li>${esc(e)}</li>`).join("")}${sources}</ul></section>

   <section class="card"><h3>Contact</h3><dl class="kv">
    <dt>Email</dt><dd>${l.email?esc(l.email):`<span class="warn">Not found. Look one up before sending.</span>`}</dd>
    ${l.phone?`<dt>Phone</dt><dd>${esc(l.phone)}</dd>`:""}
    ${web?`<dt>Website</dt><dd><a href="${esc(web)}" target="_blank" rel="noopener">${esc(l.website)}</a></dd>`:""}
    ${l.tech.length?`<dt>Uses</dt><dd><div class="chips" style="margin:0">${l.tech.map(t=>`<span class="chip">${esc(techLabel(t))}</span>`).join("")}</div></dd>`:""}
   </dl></section>
  </div>`;
}

function renderSide(){selected&&BY_ID[selected]?renderDetail():renderList()}

/* ---------- map ---------- */
let map=null,layer=null,tiles=null,markers={};
function isDark(){const t=document.documentElement.dataset.theme;return t?t==="dark":matchMedia("(prefers-color-scheme: dark)").matches}
function setTiles(){if(!map)return;
  document.getElementById("map").classList.toggle("dark",isDark());
  if(!tiles)useProvider(0)}
// Tile providers in order of preference. OpenStreetMap's own servers answer 403 to pages opened from
// disk (file:// sends no Referer), so they're only a fallback. If a provider keeps failing, switch.
const PROVIDERS=[
  {url:"https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",maxZoom:19,
   attribution:'Tiles &copy; <a href="https://www.esri.com">Esri</a> &mdash; Esri, HERE, Garmin, &copy; OpenStreetMap contributors'},
  {url:"https://tile.openstreetmap.org/{z}/{x}/{y}.png",maxZoom:19,
   attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'},
];
let provider=0,tileErrors=0,tileLoads=0;
function useProvider(i){
  if(tiles)tiles.remove();
  provider=i;tileErrors=0;tileLoads=0;
  const p=PROVIDERS[i];
  tiles=L.tileLayer(p.url,{maxZoom:p.maxZoom,attribution:p.attribution,referrerPolicy:"strict-origin-when-cross-origin"});
  tiles.on("tileload",()=>tileLoads++);
  tiles.on("tileerror",()=>{
    if(++tileErrors<4||tileLoads>tileErrors)return;
    if(provider+1<PROVIDERS.length)useProvider(provider+1);
    else if(!document.getElementById("tilewarn"))document.getElementById("legend").insertAdjacentHTML("beforeend",
      '<div class="warn" id="tilewarn">Map tiles could not be loaded (blocked or offline). Pins still work.</div>');
  });
  tiles.addTo(map);
}
function initMap(){
  const el=document.getElementById("map");
  if(!window.L){el.innerHTML='<div class="mapmsg">The map needs an internet connection to load.<br>Everything else on this page works offline.</div>';return}
  map=L.map(el,{zoomControl:true,attributionControl:true}).setView([52.15,5.3],7);
  setTiles();layer=L.layerGroup().addTo(map);
  document.getElementById("legend").hidden=false;
  matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change",setTiles);
  new MutationObserver(setTiles).observe(document.documentElement,{attributes:true,attributeFilter:["data-theme"]});
}
// leads placed at a city centre would sit on top of each other; spread them slightly, stable per id
function jitter(l){if(l.geo!=="city")return[l.lat,l.lon];let h=0;for(const c of l.id)h=(h*31+c.charCodeAt(0))|0;
  const a=(h%360)*Math.PI/180,r=.004+(Math.abs(h)%5)*.0015;return[l.lat+r*Math.sin(a),l.lon+r*Math.cos(a)*1.6]}
function renderMarkers(fit){
  const list=shown(),onMap=list.filter(l=>l.lat!=null),missing=list.length-onMap.length;
  document.getElementById("unmapped").textContent=missing?`${missing} lead${missing>1?"s":""} without a location`:"";
  if(!map)return;
  layer.clearLayers();markers={};
  for(const l of onMap){
    const cls=`pin ${l.tier}${l.geo==="city"?" approx":""}${isDone(l)?" done":""}${l.id===selected?" sel":""}`;
    const m=L.marker(jitter(l),{icon:L.divIcon({className:"",html:`<div class="${cls}">${l.score}</div>`,iconSize:[32,32],iconAnchor:[16,16]}),
      title:l.name,riseOnHover:true,zIndexOffset:l.id===selected?1000:l.score,keyboard:true});
    m.bindTooltip(`<b>${esc(l.name)}</b><br>${esc(l.stage)} · ${esc(l.city)}${l.geo==="city"?"<br><i>Approximate location</i>":""}`,{direction:"top",offset:[0,-16]});
    m.on("click",()=>select(l.id,false));
    m.addTo(layer);markers[l.id]=m;
  }
  if(fit&&onMap.length){const b=L.latLngBounds(onMap.map(jitter));map.fitBounds(b,{padding:[50,50],maxZoom:14})}
}
function highlight(id,on){const m=markers[id];const el=m&&m.getElement()?.querySelector(".pin");if(el)el.classList.toggle("hl",on)}

/* ---------- actions ---------- */
function select(id,fly=true){
  selected=id;renderSide();renderMarkers(false);
  document.getElementById("side").scrollTop=0;
  const l=BY_ID[id];
  if(map&&l&&l.lat!=null){const p=jitter(l);fly?map.flyTo(p,Math.max(map.getZoom(),13),{duration:.6}):map.panTo(p)}
  if(matchMedia("(max-width:880px)").matches)document.getElementById("side").scrollIntoView({behavior:"smooth"});
}
function back(){selected=null;renderSide();renderMarkers(false)}
function step(d){const list=shown(),i=list.findIndex(x=>x.id===selected);const n=list[i+d];if(n)select(n.id)}
function refresh(fit){renderChrome();renderSide();renderMarkers(fit)}
function field(sel){return document.querySelector(".detail "+sel)?.value??""}
function copyText(t,btn){
  const done=()=>{btn.textContent="Copied";setTimeout(()=>btn.textContent="Copy",1500)};
  if(navigator.clipboard?.writeText)navigator.clipboard.writeText(t).then(done,()=>fallback());else fallback();
  function fallback(){const ta=document.createElement("textarea");ta.value=t;document.body.appendChild(ta);ta.select();
    try{document.execCommand("copy");done()}catch(e){}ta.remove()}
}

document.getElementById("seg").addEventListener("click",e=>{const b=e.target.closest("button[data-f]");if(!b)return;filter=b.dataset.f;selected=null;refresh(true)});
document.getElementById("q").addEventListener("input",e=>{query=e.target.value.trim().toLowerCase();selected=null;refresh(true)});
document.getElementById("sort").addEventListener("change",e=>{sort=e.target.value;refresh(false)});
document.getElementById("types").addEventListener("click",e=>{const b=e.target.closest(".tchip");if(!b)return;
  types.has(b.dataset.t)?types.delete(b.dataset.t):types.add(b.dataset.t);selected=null;refresh(true)});
document.getElementById("when").addEventListener("change",e=>{when=e.target.value;selected=null;refresh(true)});
document.getElementById("reportedOnly").addEventListener("change",e=>{reportedOnly=e.target.checked;refresh(true)});
const side=document.getElementById("side");
side.addEventListener("mouseover",e=>{const r=e.target.closest(".row");if(r)highlight(r.dataset.id,true)});
side.addEventListener("mouseout",e=>{const r=e.target.closest(".row");if(r)highlight(r.dataset.id,false)});
side.addEventListener("input",e=>{if(!selected)return;const s=state[selected]=state[selected]||{};
  if(e.target.classList.contains("to"))s.to=e.target.value;
  if(e.target.classList.contains("subj"))s.subject=e.target.value;
  if(e.target.classList.contains("body"))s.body=e.target.value;save()});
side.addEventListener("click",e=>{
  const row=e.target.closest(".row");if(row){select(row.dataset.id);return}
  const b=e.target.closest("[data-act]");if(!b)return;const act=b.dataset.act;
  if(act==="back")back();
  else if(act==="clear"){types.clear();when="any";query="";document.getElementById("when").value="any";document.getElementById("q").value="";refresh(true)}
  else if(act==="prev")step(-1);
  else if(act==="next")step(1);
  else if(act==="mail")location.href=`mailto:${encodeURIComponent(field(".to"))}?subject=${encodeURIComponent(field(".subj"))}&body=${encodeURIComponent(field(".body"))}`;
  else if(act==="copy")copyText(`Subject: ${field(".subj")}\n\n${field(".body")}`,b);
  else if(act==="mark"){
    const before=shown(),i=before.findIndex(x=>x.id===selected);
    (state[selected]=state[selected]||{}).status=b.dataset.s;save();
    const after=shown();
    if(after.some(x=>x.id===selected)){refresh(false);return}
    const next=before.slice(i+1).find(x=>after.some(y=>y.id===x.id));
    renderChrome();next?select(next.id):back();
  }
});
document.getElementById("export").addEventListener("click",()=>{
  const out=LEADS.map(l=>({id:l.id,status:statusOf(l),to:st(l).to??l.email,subject:st(l).subject??l.subject,body:st(l).body??l.body}));
  const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([JSON.stringify(out,null,2)],{type:"application/json"}));
  a.download="decisions.json";a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)});
document.addEventListener("keydown",e=>{
  if(e.target.matches("input,textarea,select"))return;
  if(e.key==="Escape"&&selected)back();
  else if(e.key==="j"||e.key==="ArrowDown"&&selected){e.preventDefault();selected?step(1):shown()[0]&&select(shown()[0].id)}
  else if(e.key==="k"||e.key==="ArrowUp"&&selected){e.preventDefault();step(-1)}
});

initMap();refresh(true);
// deep link: review.html#lead=<id> opens that lead
const m=location.hash.match(/lead=([\w-]+)/);if(m&&BY_ID[m[1]]){filter="all";refresh(true);select(m[1])}
</script></body></html>"""
