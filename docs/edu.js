/* Section 04: "Why does this period matter?" + "Did you know?" (sourced, plain language). */
(() => {
"use strict";
let EDU = null, FACTS = null, factPos = 0;
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const cite = p => `<small>Source: <a href="${esc(p.source_url)}" target="_blank" rel="noopener">${esc(p.source_name)}</a></small>`;
const DAY = 864e5, EPOCH = Date.UTC(2000, 0, 1);
const MONTHS_LONG = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

Promise.all([fetch("data/education.json").then(r => r.json()), fetch("data/facts.json").then(r => r.json())])
  .then(([e, f]) => { EDU = e; FACTS = f.facts.slice().sort(() => Math.random() - 0.5); showFacts(); if (window.HSH) update(window.HSH); })
  .catch(err => console.warn("education layer unavailable", err));

function showFacts() {
  if (!FACTS || !FACTS.length) return;
  const box = document.getElementById("facts"), pick = [];
  for (let i = 0; i < 3; i++) pick.push(FACTS[(factPos + i) % FACTS.length]);
  box.innerHTML = pick.map(f => `<div class="fact"><p class="mono kicker">Did you know?</p><p>${esc(f.text)}</p>${cite(f)}</div>`).join("") +
    `<a href="#" class="more" id="nextFact">Three more</a>`;
  document.getElementById("nextFact").addEventListener("click", e => { e.preventDefault(); factPos = (factPos + 3) % FACTS.length; showFacts(); });
}

function update(S) {
  const box = document.getElementById("why");
  if (!EDU || S.week == null || !S.wk) {
    box.innerHTML = `<p class="muted">Select an outlined week in Fig. 1 for notes on that period.</p>`; return; }
  const y = S.year, w = S.week, d = new Date(EPOCH + S.day * DAY), mo = d.getUTCMonth() + 1;
  const s = S.wk.W[y] && S.wk.W[y][w];
  const unusual = s && s.unusual, risky = S.wk.risky[w];
  const med = S.region === "TR" || S.region === "rect" || EDU.mediterranean_provinces.includes(S.region);
  const agri = S.region === "TR" || S.region === "rect" || EDU.agricultural_provinces.includes(S.region);
  const blk = mo >= 6 && mo <= 10 && med ? EDU.dry_season : EDU.off_season;
  const flags = [unusual ? `unusual for the time of year (${s.mean > 0 ? (s.x / s.mean >= 100 ? Math.round(s.x / s.mean) : (s.x / s.mean).toFixed(1)) + "× the average" : "no usual activity"})` : "",
                 risky ? "historically one of the busiest weeks" : ""].filter(Boolean).join(" · ");
  let html = `<h3>${esc(blk.title)}</h3><p class="flags">${MONTHS_LONG[mo - 1]} ${y}${flags ? " · " + flags : ""}</p>`;
  html += blk.points.map(p => `<p>${esc(p.text)}<br>${cite(p)}</p>`).join("");
  html += `<p class="mono kicker" style="margin-top:16px">What you can do</p>` + blk.prevention.map(p => `<p>${esc(p.text)}<br>${cite(p)}</p>`).join("");
  if (agri && ((mo >= 6 && mo <= 7) || (mo >= 9 && mo <= 11)))
    html += `<p class="mono kicker" style="margin-top:16px">${esc(EDU.stubble.title)}</p><p>${esc(EDU.stubble.text)}<br>${cite(EDU.stubble)}</p>`;
  html += `<p class="muted" style="margin-top:16px">${esc(EDU.caveat.text)}<br>${cite(EDU.caveat)}</p>`;
  box.innerHTML = html;
}
window.HSH_EDU = { update };
})();
