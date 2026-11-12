"""Outputs: a self-contained HTML review queue, plus CSV export."""
from __future__ import annotations

import csv
import html
import json
from datetime import date
from pathlib import Path

from .models import Lead

STAGE_LABEL = {"permit_applied": "Permit applied", "permit_granted": "Permit granted",
               "announced": "Opening soon", "opened": "Recently opened", "unknown": "Unknown"}


def write_csv(leads: list[Lead], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "score", "tier", "status", "name", "city", "address", "category", "stage",
                    "event_date", "email", "phone", "website", "subject", "body", "reasons", "sources"])
        for l in leads:
            w.writerow([l.id, l.score, l.tier, l.status, l.name, l.city, l.address, l.category, l.stage,
                        l.event_date, l.email, l.phone, l.website, l.email_subject, l.email_body,
                        " | ".join(l.score_reasons), " ".join(s["url"] for s in l.sources)])


def write_html(leads: list[Lead], path: Path, seller: dict) -> None:
    data = [{
        "id": l.id, "name": l.name, "city": l.city, "address": l.address, "category": l.category,
        "stage": STAGE_LABEL.get(l.stage, l.stage), "date": l.event_date, "score": l.score, "tier": l.tier,
        "reasons": l.score_reasons, "evidence": l.evidence, "tech": l.detected_tech, "email": l.email,
        "phone": l.phone, "website": l.website, "subject": l.email_subject, "body": l.email_body,
        "generator": l.email_generator, "status": l.status, "sources": l.sources,
    } for l in leads]
    page = TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/")) \
                   .replace("__TITLE__", html.escape(f"{seller['company']} lead queue")) \
                   .replace("__DATE__", date.today().isoformat())
    path.write_text(page, encoding="utf-8")


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--bg:#f6f5f2;--card:#fff;--ink:#1d1d1b;--muted:#6b6a66;--line:#e4e2dc;--accent:#1f6f5c;--accent-ink:#fff;
--hot:#b4401f;--warm:#b07a10;--cold:#5f6b7a;--chip:#efede7;--field:#fbfaf8}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#141413;--card:#1e1e1c;--ink:#ecebe7;--muted:#9e9c95;--line:#2f2e2b;
--accent:#4fb39a;--accent-ink:#0d1a16;--hot:#ef7d5b;--warm:#e0b04a;--cold:#93a0b0;--chip:#2a2927;--field:#181816}}
:root[data-theme="dark"]{--bg:#141413;--card:#1e1e1c;--ink:#ecebe7;--muted:#9e9c95;--line:#2f2e2b;
--accent:#4fb39a;--accent-ink:#0d1a16;--hot:#ef7d5b;--warm:#e0b04a;--cold:#93a0b0;--chip:#2a2927;--field:#181816}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
header{padding:20px 16px 8px;max-width:980px;margin:0 auto}h1{font-size:22px;margin:0 0 4px}
.sub{color:var(--muted);font-size:13px}
.bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;max-width:980px;margin:8px auto 0;padding:0 16px}
.bar button,.bar select{font:inherit;font-size:13px;border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:8px;padding:6px 10px;cursor:pointer}
.bar button[aria-pressed=true]{background:var(--ink);color:var(--bg);border-color:var(--ink)}
main{max-width:980px;margin:0 auto;padding:12px 16px 60px;display:grid;gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;display:grid;gap:12px}
.card.done{opacity:.55}
.top{display:flex;gap:12px;align-items:flex-start}
.score{min-width:52px;height:52px;border-radius:10px;display:grid;place-items:center;font-weight:700;font-size:20px;color:#fff}
.hot{background:var(--hot)}.warm{background:var(--warm)}.cold{background:var(--cold)}
.title{flex:1;min-width:0}.title h2{font-size:17px;margin:0;overflow-wrap:anywhere}
.meta{color:var(--muted);font-size:13px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}.chip{background:var(--chip);border-radius:999px;padding:2px 9px;font-size:12px}
.cols{display:grid;grid-template-columns:1fr 1.4fr;gap:16px}@media (max-width:720px){.cols{grid-template-columns:1fr}}
h3{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);margin:0 0 6px}
ul{margin:0;padding-left:18px;font-size:13px}li{margin:2px 0}
.contact{font-size:13px;overflow-wrap:anywhere}a{color:var(--accent)}
input,textarea{width:100%;font:inherit;font-size:14px;color:var(--ink);background:var(--field);border:1px solid var(--line);border-radius:8px;padding:8px}
textarea{min-height:230px;resize:vertical}
.actions{display:flex;flex-wrap:wrap;gap:8px}
.actions button,.actions a{font:inherit;font-size:13px;border-radius:8px;padding:7px 12px;cursor:pointer;text-decoration:none;border:1px solid var(--line);background:var(--card);color:var(--ink)}
.actions .primary{background:var(--accent);color:var(--accent-ink);border-color:var(--accent)}
.gen{font-size:11px;color:var(--muted)}
.empty{color:var(--muted);text-align:center;padding:40px}
</style></head><body>
<header><h1>__TITLE__</h1><div class="sub">Generated __DATE__ · <span id="count"></span> · Review each draft, edit it if needed, then open it in your email app and send.</div></header>
<div class="bar" role="toolbar">
  <button data-f="todo" aria-pressed="true">To do</button><button data-f="hot" aria-pressed="false">Hot only</button>
  <button data-f="all" aria-pressed="false">All</button><button data-f="done" aria-pressed="false">Sent / skipped</button>
  <span style="flex:1"></span><button id="export">Export decisions</button>
</div>
<main id="list"></main>
<script>
const LEADS=__DATA__;
const KEY="horeca-leads-state";
let state={};try{state=JSON.parse(localStorage.getItem(KEY)||"{}")}catch(e){}
const save=()=>{try{localStorage.setItem(KEY,JSON.stringify(state))}catch(e){}};
const st=l=>(state[l.id]||{});
const statusOf=l=>st(l).status||l.status;
let filter="todo";
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function visible(l){const s=statusOf(l);if(filter==="all")return true;if(filter==="done")return s==="sent"||s==="skipped";
  const todo=s!=="sent"&&s!=="skipped";return filter==="hot"?todo&&l.tier==="hot":todo}
function render(){
  const list=document.getElementById("list");const shown=LEADS.filter(visible);
  document.getElementById("count").textContent=`${LEADS.length} leads, ${LEADS.filter(l=>l.tier==="hot").length} hot`;
  if(!shown.length){list.innerHTML='<div class="empty">Nothing here.</div>';return}
  list.innerHTML=shown.map(l=>{const s=st(l);const done=["sent","skipped"].includes(statusOf(l));
  return `<article class="card ${done?"done":""}" data-id="${l.id}">
  <div class="top"><div class="score ${l.tier}" title="POS-need score">${l.score}</div>
   <div class="title"><h2>${esc(l.name)}</h2><div class="meta">${esc([l.address,l.city].filter(Boolean).join(", "))}</div>
   <div class="chips"><span class="chip">${esc(l.stage)}${l.date?" · "+esc(l.date):""}</span>${l.category?`<span class="chip">${esc(l.category)}</span>`:""}
   ${l.tech.map(t=>`<span class="chip">${esc(t)}</span>`).join("")}<span class="chip">status: ${esc(statusOf(l))}</span></div></div></div>
  <div class="cols"><div>
   <h3>Why this score</h3><ul>${l.reasons.map(r=>`<li>${esc(r)}</li>`).join("")}</ul>
   <h3 style="margin-top:12px">Evidence</h3><ul>${l.evidence.map(r=>`<li>${esc(r)}</li>`).join("")}
     ${l.sources.map(x=>`<li><a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.source)}: ${esc(x.title||x.url)}</a></li>`).join("")}</ul>
   <h3 style="margin-top:12px">Contact</h3><div class="contact">
     ${l.email?`✉ ${esc(l.email)}<br>`:"<em>No email found. Look one up before sending.</em><br>"}
     ${l.phone?`☎ ${esc(l.phone)}<br>`:""}${l.website?`<a href="${esc(l.website)}" target="_blank" rel="noopener">${esc(l.website)}</a>`:""}</div>
  </div><div>
   <h3>Draft email <span class="gen">(${esc(l.generator)})</span></h3>
   <input class="to" placeholder="To" value="${esc(s.to??l.email)}" aria-label="To">
   <input class="subj" style="margin-top:6px" value="${esc(s.subject??l.subject)}" aria-label="Subject">
   <textarea class="body" style="margin-top:6px" aria-label="Body">${esc(s.body??l.body)}</textarea>
   <div class="actions" style="margin-top:8px">
    <a class="primary mail" href="#">Open in email app</a><button class="copy">Copy</button>
    <button class="mark" data-s="sent">Mark sent</button><button class="mark" data-s="skipped">Skip</button>
    ${done?'<button class="mark" data-s="new">Undo</button>':""}</div></div></div></article>`}).join("");
}
document.addEventListener("input",e=>{const c=e.target.closest(".card");if(!c)return;const id=c.dataset.id;state[id]=state[id]||{};
  if(e.target.classList.contains("to"))state[id].to=e.target.value;if(e.target.classList.contains("subj"))state[id].subject=e.target.value;
  if(e.target.classList.contains("body"))state[id].body=e.target.value;save()});
document.addEventListener("click",e=>{const c=e.target.closest(".card");const fb=e.target.closest(".bar button[data-f]");
  if(fb){filter=fb.dataset.f;document.querySelectorAll(".bar button[data-f]").forEach(b=>b.setAttribute("aria-pressed",b===fb));render();return}
  if(e.target.id==="export"){const out=LEADS.map(l=>({id:l.id,status:statusOf(l),to:st(l).to??l.email,subject:st(l).subject??l.subject,body:st(l).body??l.body}));
    const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([JSON.stringify(out,null,2)],{type:"application/json"}));a.download="decisions.json";a.click();return}
  if(!c)return;const id=c.dataset.id;const q=s=>c.querySelector(s).value;
  if(e.target.classList.contains("mail")){e.preventDefault();location.href=`mailto:${encodeURIComponent(q(".to"))}?subject=${encodeURIComponent(q(".subj"))}&body=${encodeURIComponent(q(".body"))}`}
  if(e.target.classList.contains("copy")){navigator.clipboard?.writeText(`Subject: ${q(".subj")}\n\n${q(".body")}`);e.target.textContent="Copied"}
  if(e.target.classList.contains("mark")){state[id]=state[id]||{};state[id].status=e.target.dataset.s;save();render()}});
render();
</script></body></html>"""
