/* The Fire Almanac of Türkiye: static front-end (vanilla JS + Leaflet, no build step). */
(() => {
"use strict";

const DAY = 864e5, EPOCH = Date.UTC(2000, 0, 1);
const MODES = ["harmonized", "modis", "viirs"];
const MODE_LABEL = { harmonized: "both satellites, merged", modis: "MODIS only", viirs: "VIIRS only" };
const METRIC = { f: { name: "fire energy", unit: "MW", title: "Fire energy" },
                 e: { name: "active fires", unit: "fires", title: "Active fires" },
                 n: { name: "new fires", unit: "fires", title: "New fires" } };
const AGREE = ["both", "modis_only", "viirs_only"];
const AGREE_LABEL = { both: "Seen by both satellites", modis_only: "MODIS only", viirs_only: "VIIRS only" };
const SATS = ["Terra", "Aqua", "S-NPP", "NOAA-20", "NOAA-21"];
const css = n => getComputedStyle(document.body).getPropertyValue(n).trim();
let COL = { both: css("--both"), modis_only: css("--modis"), viirs_only: css("--viirs"),
              modis: css("--modis"), viirs: css("--viirs"), harmonized: css("--both") };
let RAMP = ["--c0", "--c1", "--c2", "--c3", "--c4", "--c5"].map(css);
function readColors() {
  COL = { both: css("--both"), modis_only: css("--modis"), viirs_only: css("--viirs"), modis: css("--modis"), viirs: css("--viirs"), harmonized: css("--both") };
  RAMP = ["--c0", "--c1", "--c2", "--c3", "--c4", "--c5"].map(css);
}
const Z_THRESH = 1.5, Z_STRONG = 5, MIN_VALUE = { e: 3, n: 3, f: 100 }, RISK_Q = 0.85;
const STALE_HALF_LIFE_H = 24, W_CROSS = 0.30, W_REPEAT = 0.10;

const S = { meta: null, region: "TR", rect: null, mode: "harmonized", metric: "f",
            year: null, week: null, day: null, cal: null, events: {}, eventdays: {}, edLoading: null, sel: null, wk: null };
const $ = id => document.getElementById(id);
const fmt = (v, d = 0) => v == null || isNaN(v) ? "–" : Number(v).toLocaleString("en-US", { maximumFractionDigits: d, minimumFractionDigits: d });
const fmtZ = z => !isFinite(z) ? "–" : z >= 100 ? "> 100" : z.toFixed(1);
const ratioTxt = (x, m) => m > 0 ? (x / m >= 100 ? fmt(x / m) : (x / m).toFixed(1)) + "×" : "–";
const dateOf = idx => new Date(EPOCH + idx * DAY);
const isoOf = idx => dateOf(idx).toISOString().slice(0, 10);
const idxOf = (y, m, d) => Math.round((Date.UTC(y, m, d) - EPOCH) / DAY);
const TZF = new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Istanbul", year: "numeric", month: "2-digit", day: "2-digit" });
const localIdx = ms => { const [y, m, d] = TZF.format(ms).split("-").map(Number); return idxOf(y, m - 1, d); };
const localTime = ms => new Date(ms).toLocaleString("en-GB", { timeZone: "Europe/Istanbul", day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
const dayTxt = (idx, yr = true) => dateOf(idx).toLocaleDateString("en-GB", { day: "numeric", month: "short", ...(yr ? { year: "numeric" } : {}), timeZone: "UTC" });
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MONTHS_LONG = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
function weekOf(idx) { const d = dateOf(idx), y = d.getUTCFullYear();
  const j1 = new Date(Date.UTC(y, 0, 1)), dow1 = (j1.getUTCDay() + 6) % 7;
  return Math.floor((Math.round((d - j1) / DAY) + dow1) / 7); }
function weekRange(y, w) { let d0 = idxOf(y, 0, 1); while (weekOf(d0) < w) d0++;
  let d1 = d0; while (d1 + 1 < idxOf(y + 1, 0, 1) && weekOf(d1 + 1) === w) d1++; return [d0, d1]; }
const getJSON = async url => { const r = await fetch(url); if (!r.ok) throw new Error(url + " " + r.status); return r.json(); };
const status = t => { $("status").textContent = t || ""; };
const svgEl = (tag, attrs = {}, parent) => { const e = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; };
const regionName = () => S.region === "rect" ? "the drawn area" : S.region === "TR" ? "Türkiye" : S.meta.regions[S.region];

// ---------------- tooltip ----------------
const tip = $("tip");
function showTip(ev, html) { tip.innerHTML = html; tip.hidden = false; moveTip(ev); }
function moveTip(ev) { const w = tip.offsetWidth, h = tip.offsetHeight;
  let x = ev.clientX + 14, y = ev.clientY + 14;
  if (x + w > innerWidth - 8) x = ev.clientX - w - 14; if (y + h > innerHeight - 8) y = ev.clientY - h - 14;
  tip.style.left = Math.max(4, x) + "px"; tip.style.top = Math.max(4, y) + "px"; }
const hideTip = () => { tip.hidden = true; };
function hover(el, html) { el.addEventListener("mouseenter", e => showTip(e, typeof html === "function" ? html() : html));
  el.addEventListener("mousemove", moveTip); el.addEventListener("mouseleave", hideTip); }

// ---------------- live map ----------------
const BASE = "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}";
const BASE_ATTR = "Tiles &copy; Esri &mdash; Esri, HERE, Garmin, &copy; OpenStreetMap contributors";
const map = L.map("map", { preferCanvas: true, zoomSnap: 0.25, scrollWheelZoom: false }).setView([39, 35], 5.75);
L.tileLayer(BASE, { attribution: BASE_ATTR, maxZoom: 16 }).addTo(map);
map.on("focus", () => map.scrollWheelZoom.enable()); map.on("blur", () => map.scrollWheelZoom.disable());
const provLayer = L.geoJSON(null, { style: () => ({ color: "#8a8178", weight: 0.6, fill: true, fillOpacity: 0, opacity: .9 }),
  onEachFeature: (f, l) => { l.on("click", () => selectRegion(f.properties.id));
    l.bindTooltip(f.properties.name, { sticky: true }); } }).addTo(map);
const evLayer = L.layerGroup().addTo(map);
let rectLayer = null;
const canvas = L.canvas({ padding: 0.3 });
function styleProvinces() {
  provLayer.eachLayer(l => { const on = l.feature.properties.id === S.region;
    l.setStyle(on ? { color: css("--ink"), weight: 1.8, fillOpacity: 0.04, fillColor: css("--accent") }
                  : { color: "#8a8178", weight: 0.6, fillOpacity: 0 }); if (on) l.bringToFront(); });
}

// rectangle drawing (no plugin)
let drawing = false, drawStart = null;
$("drawBtn").addEventListener("click", () => setDrawing(!drawing));
function setDrawing(on) { drawing = on; $("drawBtn").classList.toggle("on", on); document.body.classList.toggle("drawing", on);
  if (on) { map.dragging.disable(); $("s-map").scrollIntoView({ behavior: "smooth" }); status("Drag on the map to select an area"); }
  else { map.dragging.enable(); } }
map.on("mousedown", e => { if (!drawing) return; drawStart = e.latlng;
  if (rectLayer) map.removeLayer(rectLayer);
  rectLayer = L.rectangle([drawStart, drawStart], { color: css("--accent"), weight: 1.5, fillOpacity: 0.05, dashArray: "4 3" }).addTo(map); });
map.on("mousemove", e => { if (drawing && drawStart) rectLayer.setBounds(L.latLngBounds(drawStart, e.latlng)); });
map.on("mouseup", e => { if (!drawing || !drawStart) return; const b = L.latLngBounds(drawStart, e.latlng); drawStart = null; setDrawing(false);
  if (Math.abs(b.getNorth() - b.getSouth()) < 0.05 || Math.abs(b.getEast() - b.getWest()) < 0.05) { status("Area too small"); return; }
  S.rect = b; S.region = "rect"; $("regionSel").value = "rect"; styleProvinces(); loadRegion(true); });

// ---------------- data ----------------
function colsToMap(col, hasAgree) {
  const m = new Map();
  for (let i = 0; i < col.d.length; i++) m.set(col.d[i], { e: col.e[i], n: col.n[i], f: col.f[i], dm: col.dm[i], dv: col.dv[i],
    b: hasAgree ? col.b[i] : 0, mo: hasAgree ? col.mo[i] : 0, vo: hasAgree ? col.vo[i] : 0 });
  return m;
}
async function loadEventDays() {
  if (S.edLoading) return S.edLoading;
  const years = S.meta.years; let done = 0;
  S.edLoading = Promise.all(years.map(y => getJSON(`data/eventdays/${y}.json`).then(j => { S.eventdays[y] = j.data;
    status(`Loading the archive for your area… ${++done}/${years.length} years`); })));
  await S.edLoading; status(""); return S.edLoading;
}
async function rectCalendar(b) {
  await loadEventDays();
  const s = b.getSouth() * 1000, n = b.getNorth() * 1000, w = b.getWest() * 1000, e = b.getEast() * 1000;
  const cal = { harmonized: new Map(), modis: new Map(), viirs: new Map() };
  for (const y of S.meta.years) {
    const a = S.eventdays[y], y0 = idxOf(y, 0, 1);
    for (let i = 0; i < a.length; i += 7) {
      const la = a[i], lo = a[i + 1]; if (la < s || la > n || lo < w || lo > e) continue;
      const flag = a[i + 4], mode = MODES[flag >> 3], ag = (flag >> 1) & 3, nw = flag & 1, day = y0 + a[i + 2];
      const m = cal[mode]; let r = m.get(day);
      if (!r) { r = { e: 0, n: 0, f: 0, dm: 0, dv: 0, b: 0, mo: 0, vo: 0 }; m.set(day, r); }
      r.e++; r.n += nw; r.f += a[i + 3]; r.dm += a[i + 5]; r.dv += a[i + 6];
      if (mode === "harmonized") { if (ag === 0) r.b++; else if (ag === 1) r.mo++; else r.vo++; }
    }
  }
  return cal;
}
async function loadRegion(fit) {
  status("Loading…");
  if (S.region === "rect") S.cal = await rectCalendar(S.rect);
  else { const j = await getJSON(`data/calendar/${S.region}.json`);
    S.cal = { harmonized: colsToMap(j.modes.harmonized, true), modis: colsToMap(j.modes.modis), viirs: colsToMap(j.modes.viirs) }; }
  status("");
  if (fit !== false) {
    if (S.region === "rect") map.fitBounds(S.rect, { maxZoom: 9 });
    else if (S.region === "TR") map.setView([39, 35], 5.75);
    else provLayer.eachLayer(l => { if (l.feature.properties.id === S.region) map.fitBounds(l.getBounds(), { maxZoom: 9 }); });
  }
  S.week = null; S.day = null; S.sel = null;
  renderAll();
}
async function loadYearEvents(y) {
  if (!S.events[y]) S.events[y] = getJSON(`data/events/${y}.json`).then(j => j.rows.map(r => {
    const t0 = r[3] * 60000, t1 = t0 + r[4] * 60000;
    return { id: r[0], lat: r[1], lon: r[2], t0, t1, d0: localIdx(t0), d1: localIdx(t1), nM: r[5], nV: r[6],
      maxFrp: r[7], sumFrp: r[8], base: r[9], conf: r[10], agree: AGREE[r[11]], region: r[12], tl: r[13] }; }));
  return S.events[y];
}

// ---------------- analytics (mirrors src/harmonize.py weekly_anomalies) ----------------
function baselineYears(mode) { const ys = S.meta.years; return mode === "modis" ? ys : ys.filter(y => y >= 2012); }
const noViirsYet = (mode, y) => mode !== "modis" && y < 2012;
function weekly(mode, metric) {
  const cal = S.cal[mode], years = S.meta.years, W = {};
  for (const y of years) W[y] = new Float64Array(54);
  for (const [d, r] of cal) { const y = dateOf(d).getUTCFullYear(); if (W[y]) W[y][weekOf(d)] += r[metric]; }
  const base = new Set(baselineYears(mode)), out = {};
  const s = new Float64Array(54), ss = new Float64Array(54); let k = 0;
  for (const y of base) { k++; for (let w = 0; w < 54; w++) { s[w] += W[y][w]; ss[w] += W[y][w] ** 2; } }
  const clim = Array.from(s, v => v / k);
  for (const y of years) {
    out[y] = [];
    for (let w = 0; w < 54; w++) {
      const x = W[y][w], inB = base.has(y);
      const kk = inB ? k - 1 : k, sm = inB ? s[w] - x : s[w], sq = inB ? ss[w] - x * x : ss[w];
      const mean = sm / kk, sd = Math.sqrt(Math.max(sq - kk * mean * mean, 0) / Math.max(kk - 1, 1));
      const z = sd > 0 ? (x - mean) / sd : NaN, valid = !noViirsYet(mode, y);
      out[y].push({ x, mean, sd, z, above: valid && x > mean && x > 0, unusual: valid && z > Z_THRESH && x >= MIN_VALUE[metric] });
    }
  }
  const sorted = clim.slice(0, 53).filter(v => v > 0).sort((a, b) => a - b);
  const thr = sorted.length ? sorted[Math.floor(RISK_Q * (sorted.length - 1))] : Infinity;
  return { W: out, clim, risky: clim.map(v => v > 0 && v >= thr), base: baselineYears(mode) };
}
function peakDay(y, w) {
  const [d0, d1] = weekRange(y, w); let best = d0, bv = -1;
  for (let k = d0; k <= d1; k++) { const r = S.cal[S.mode].get(k), v = r ? r[S.metric] : 0; if (v > bv) { bv = v; best = k; } }
  return best;
}
function selectWeek(y, w) { S.year = y; S.week = w; S.day = peakDay(y, w); S.sel = null; renderAll(); }

// ---------------- Figure 1: year × week calendar ----------------
function renderCalendar() {
  const box = $("calendar"); box.innerHTML = "";
  const m = S.metric, wk = weekly(S.mode, m); S.wk = wk;
  const bl = `${wk.base[0]}–${wk.base[wk.base.length - 1]}`;
  $("calTitle").textContent = `Weekly ${METRIC[m].name}, ${regionName()} · ${MODE_LABEL[S.mode]}`;
  const vals = [];
  for (const y of S.meta.years) if (!noViirsYet(S.mode, y)) wk.W[y].forEach(s => { if (s.x > 0) vals.push(s.x); });
  vals.sort((a, b) => a - b);
  const q = p => vals.length ? vals[Math.floor(p * (vals.length - 1))] : 1, qs = [q(0.40), q(0.70), q(0.88), q(0.97)];
  const lv = v => v <= 0 ? 0 : 1 + qs.filter(t => v > t).length;
  const L0 = 48, T0 = 34, RW = 220, years = S.meta.years.slice();
  const P = Math.max(11, Math.min(20, Math.floor((box.clientWidth - L0 - RW) / 54))), C = P - 2;
  const W = L0 + 54 * P + RW, H = T0 + years.length * P + 8;
  const svg = svgEl("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}` }, box);
  for (let mo = 0; mo < 12; mo++) svgEl("text", { x: L0 + weekOf(idxOf(2021, mo, 1)) * P, y: 11, class: "month" }, svg).textContent = MONTHS[mo];
  wk.risky.forEach((r, w) => { if (!r) return; const t = svgEl("rect", { x: L0 + w * P + 2, y: 20, width: C - 4, height: 3, class: "risky" }, svg);
    hover(t, `<b>Historically busy week</b><br><span class="r">On average one of the ${Math.round((1 - RISK_Q) * 100)}% busiest weeks of the year in ${regionName()} (${bl}).</span>`); });
  svgEl("text", { x: L0 + 54 * P + 10, y: 24 }, svg).textContent = "▬ busy week, on average";
  const notes = { 2012: "VIIRS (S-NPP) joins", 2018: "NOAA-20 joins", 2021: "Manavgat, Marmaris fires" };
  years.forEach((y, yi) => {
    const oy = T0 + yi * P, empty = S.mode === "viirs" && y < 2012;
    const yl = svgEl("text", { x: 0, y: oy + C - 2, class: "yl" + (y === S.year ? " sel" : "") + (noViirsYet(S.mode, y) ? " era" : "") }, svg);
    yl.textContent = y; yl.addEventListener("click", () => { S.year = y; S.week = null; S.day = null; renderAll(); });
    if (notes[y]) svgEl("text", { x: L0 + 54 * P + 10, y: oy + C - 2 }, svg).textContent = notes[y];
    if (y === 2011 && S.mode === "harmonized") svgEl("text", { x: L0 + 54 * P + 10, y: oy + C - 2 }, svg).textContent = "↑ MODIS only until here";
    if (empty) { if (y === 2006) svgEl("text", { x: L0 + 4, y: oy + C - 2 }, svg).textContent = "No VIIRS data before 2012"; return; }
    for (let w = 0; w < 54; w++) {
      const [d0] = weekRange(y, w); if (dateOf(d0).getUTCFullYear() !== y || weekOf(d0) !== w) continue;
      const s = wk.W[y][w];
      const r = svgEl("rect", { x: L0 + w * P, y: oy, width: C, height: C, rx: 1, class: "w" + (y === S.year && w === S.week ? " sel" : ""), fill: RAMP[lv(s.x)] }, svg);
      r.dataset.y = y; r.dataset.w = w;
      if (s.unusual) svgEl("rect", { x: L0 + w * P - 1, y: oy - 1, width: C + 2, height: C + 2, rx: 1, class: "unusual" + (s.z >= Z_STRONG ? " strong" : "") }, svg);
    }
  });
  svg.addEventListener("mouseover", e => {
    const t = e.target; if (!t.dataset.w) return;
    const y = +t.dataset.y, w = +t.dataset.w, s = wk.W[y][w], [d0, d1] = weekRange(y, w);
    let h = `<b>${dayTxt(d0, false)} – ${dayTxt(d1)}</b><br><span class="r">${fmt(s.x)} ${METRIC[m].unit === "MW" ? "MW of fire energy" : METRIC[m].name}</span>`;
    if (!noViirsYet(S.mode, y) || S.mode === "modis") {
      if (s.unusual) h += `<br><b style="color:var(--accent)">Unusual activity: ${ratioTxt(s.x, s.mean)} the long-term average</b><span class="r"> for this week (${bl})</span>`;
      else if (s.mean > 0) h += `<br><span class="r">${ratioTxt(s.x, s.mean)} the long-term average for this week (${bl})</span>`;
    } else h += `<br><span class="r">MODIS only: VIIRS was launched in late 2011.</span>`;
    showTip(e, h);
  });
  svg.addEventListener("mousemove", e => { if (!tip.hidden) moveTip(e); });
  svg.addEventListener("mouseleave", hideTip);
  svg.addEventListener("click", e => { const t = e.target; if (t.dataset.w) selectWeek(+t.dataset.y, +t.dataset.w); });

  $("calLegend").innerHTML = `<span class="ramp">less ${RAMP.map(c => `<i style="background:${c}"></i>`).join("")} more</span>
    <span><i style="background:none;border:1px solid var(--unusual)"></i>unusual week (more than 1.5 standard deviations above normal)</span>
    <span><i style="background:none;border:1.8px solid var(--unusual-strong)"></i>exceptional (more than 5)</span>`;

  const ranked = [];
  for (const yy of S.meta.years) wk.W[yy].forEach((s, w) => { if (s.unusual) ranked.push({ y: yy, w, z: s.z, s }); });
  ranked.sort((a, b) => b.z - a.z);
  $("toprank").innerHTML = `<span class="lbl">Most unusual weeks</span>` + (ranked.length ? ranked.slice(0, 5).map((r, i) => {
    const d = weekRange(r.y, r.w)[0];
    return `<button class="chip" data-y="${r.y}" data-w="${r.w}">${dayTxt(d)} <b>${ratioTxt(r.s.x, r.s.mean)}</b></button>`; }).join(" · ") : "none");
  $("toprank").querySelectorAll(".chip").forEach(b => b.addEventListener("click", () => selectWeek(+b.dataset.y, +b.dataset.w)));
  if (box.scrollWidth > box.clientWidth + 4) { // phones: bring the selected week (or midsummer) into view
    const wc = S.week != null ? S.week : 30;
    box.scrollLeft = Math.max(0, L0 + wc * P - box.clientWidth / 2);
  }
}
function focusWeek(y, w) { // brief highlight animation around a week cell
  const svg = $("calendar").querySelector("svg"); if (!svg) return;
  const cell = svg.querySelector(`rect.w[data-y="${y}"][data-w="${w}"]`); if (!cell) return;
  const x = +cell.getAttribute("x"), yy = +cell.getAttribute("y");
  const c = +cell.getAttribute("width");
  svgEl("rect", { x: x - 4, y: yy - 4, width: (c + 2) * 3 + 6, height: c + 8, class: "focus" }, svg);
}

// ---------------- "Is this week normal?" ----------------
function renderNormal() {
  const now = new Date(), today = idxOf(now.getFullYear(), now.getMonth(), now.getDate()), w = weekOf(today);
  const wk = S.wk, years = wk.base, mean = wk.clim[w];
  const vals = years.map(y => ({ y, x: wk.W[y][w].x }));
  const calm = vals.filter(v => v.x <= mean).length, top = vals.reduce((a, b) => (b.x > a.x ? b : a), vals[0]);
  const [d0, d1] = weekRange(now.getFullYear(), w);
  const label = `${dayTxt(d0, false)}–${dayTxt(d1, false)}`;
  const where = S.region === "TR" ? "Across Türkiye" : S.region === "rect" ? "In the drawn area" : `In ${S.meta.regions[S.region]}`;
  if (!vals.length || !(mean > 0)) { $("normalBox").hidden = true; return; }
  $("normalBox").hidden = false;
  // Basis: the selected view's own baseline years (harmonized and VIIRS views start in 2012,
  // when VIIRS joined; before that the merged record is MODIS only and not comparable).
  const since = S.mode === "modis" ? `Since ${years[0]}` : `Since VIIRS joined in ${years[0]}`;
  const n = years.length, share = calm / n;
  const where2 = where.replace(/^In /, "in ").replace(/^Across /, "across ");
  const busiest = `The busiest was ${top.y}, at ${ratioTxt(top.x, mean)} the average.`;
  if (share >= 0.6) $("normalTxt").innerHTML = `${since}, this week (${label}) has usually been calm ${where2}: below its long-term average in <b>${calm} of ${n}</b> years. ${busiest}`;
  else if (share <= 0.4) $("normalTxt").innerHTML = `${since}, this week (${label}) has usually been busy ${where2}: above its long-term average in <b>${n - calm} of ${n}</b> years. ${busiest}`;
  else $("normalTxt").innerHTML = `${since}, this week (${label}) has been mixed ${where2}: below its long-term average in <b>${calm} of ${n}</b> years and above it in ${n - calm}. ${busiest}`;
}

// ---------------- Figure 2: month by month ----------------
function niceMax(v) { // round axis top so the 4 gridlines get round labels
  const raw = v / 4, mag = 10 ** Math.floor(Math.log10(raw)), f = raw / mag;
  return 4 * (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * mag;
}
function renderMonths() {
  const box = $("months"); box.innerHTML = "";
  const cal = S.cal[S.mode], m = S.metric, y = S.year, base = baselineYears(S.mode);
  const tot = {}; for (const yy of S.meta.years) tot[yy] = new Float64Array(12);
  for (const [d, r] of cal) { const dt = dateOf(d), yy = dt.getUTCFullYear(); if (tot[yy]) tot[yy][dt.getUTCMonth()] += r[m]; }
  const mean = Array.from({ length: 12 }, (_, i) => base.reduce((a, yy) => a + tot[yy][i], 0) / base.length);
  const cur = tot[y] || new Float64Array(12);
  const pk = cur.indexOf(Math.max(...cur));
  $("monthTitle").textContent = `Month by month, ${regionName()}, ${y}`;
  $("monthSub").textContent = cur[pk] > 0 ? `In ${y}, ${MONTHS_LONG[pk]} was the busiest month: ${ratioTxt(cur[pk], mean[pk])} its long-term average.` : `No fire activity recorded in ${y}.`;
  const W = Math.max(box.clientWidth, 300), H = 230, pl = 54, pb = 22, pt = 8, pr = 6;
  const max = niceMax(Math.max(1, ...cur, ...mean) * 1.02), sx = (W - pl - pr) / 12, sy = v => H - pb - (H - pb - pt) * v / max;
  const svg = svgEl("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}` }, box), g = svgEl("g", { class: "grid" }, svg);
  for (let i = 0; i <= 4; i++) { const v = max * i / 4; svgEl("line", { x1: pl, x2: W - pr, y1: sy(v), y2: sy(v) }, g);
    svgEl("text", { x: pl - 6, y: sy(v) + 4, "text-anchor": "end" }, svg).textContent = fmt(v, 0); }
  for (let i = 0; i < 12; i++) {
    const x = pl + i * sx, bw = Math.max(4, sx * 0.6), h = Math.max(0, sy(0) - sy(cur[i]));
    svgEl("rect", { x: x + (sx - bw) / 2, y: sy(cur[i]), width: bw, height: h, fill: css("--accent") }, svg);
    svgEl("text", { x: x + sx / 2, y: H - 6, "text-anchor": "middle" }, svg).textContent = MONTHS[i];
    const hit = svgEl("rect", { x, y: pt, width: sx, height: H - pb - pt, fill: "transparent" }, svg);
    hover(hit, () => `<b>${MONTHS_LONG[i]} ${y}</b><br><span class="r">${fmt(cur[i])} ${METRIC[m].unit === "MW" ? "MW" : METRIC[m].name}<br>long-term average (${base[0]}–${base[base.length - 1]}): ${fmt(mean[i])}</span>`);
  }
  svgEl("polyline", { points: mean.map((v, i) => `${pl + i * sx + sx / 2},${sy(v)}`).join(" "), fill: "none", stroke: css("--ink"), "stroke-width": 1.5, "stroke-dasharray": "4 3" }, svg);
}

// ---------------- Figure 3: what each satellite sees ----------------
function renderCompare() {
  const box = $("compare"); box.innerHTML = "";
  const m = S.metric, y = S.year, y0 = idxOf(y, 0, 1), y1 = idxOf(y + 1, 0, 1);
  const series = {}, totals = {};
  for (const mode of ["modis", "viirs", "harmonized"]) {
    const a = new Float64Array(54); let t = 0;
    for (let d = y0; d < y1; d++) { const r = S.cal[mode].get(d); if (r) { a[weekOf(d)] += r[m]; t += r[m]; } }
    series[mode] = a; totals[mode] = t;
  }
  let nn = 0, b = 0, vo = 0; for (let d = y0; d < y1; d++) { const r = S.cal.harmonized.get(d); if (r) { nn += r.n; b += r.b; vo += r.vo; } }
  $("cmpTitle").textContent = `What each satellite sees, ${y}`;
  if (y < 2012) $("cmpSub").textContent = `Before 2012 only MODIS was in orbit, so the merged record equals the MODIS record.`;
  else if (m === "f") $("cmpSub").textContent = `In ${y}, MODIS alone measured ${fmt(totals.modis)} MW of fire energy and VIIRS alone ${fmt(totals.viirs)} MW. The merged line adds both: ${fmt(totals.harmonized)} MW.`;
  else { const both = b + vo > 0 ? Math.round(100 * vo / (b + vo + 1e-9)) : 0;
    $("cmpSub").textContent = `In ${y}, MODIS alone saw ${fmt(series.modis.reduce((a, v) => a + v, 0))} and VIIRS alone ${fmt(series.viirs.reduce((a, v) => a + v, 0))} ${METRIC[m].name} (summed by week). Merged, ${fmt(nn)} fires began that year. Most of the extra ones are small fires that only VIIRS resolves.`; }
  const W = Math.max(box.clientWidth, 300), H = 230, pl = 54, pb = 22, pt = 8, pr = 6;
  const max = niceMax(Math.max(1, ...series.modis, ...series.viirs, ...series.harmonized) * 1.02);
  const sx = (W - pl - pr) / 53, sy = v => H - pb - (H - pb - pt) * v / max;
  const svg = svgEl("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}` }, box), g = svgEl("g", { class: "grid" }, svg);
  for (let i = 0; i <= 4; i++) { const v = max * i / 4; svgEl("line", { x1: pl, x2: W - pr, y1: sy(v), y2: sy(v) }, g);
    svgEl("text", { x: pl - 6, y: sy(v) + 4, "text-anchor": "end" }, svg).textContent = fmt(v, 0); }
  for (let mo = 0; mo < 12; mo += 2) svgEl("text", { x: pl + weekOf(idxOf(y, mo, 1)) * sx, y: H - 6 }, svg).textContent = MONTHS[mo];
  for (const mode of ["modis", "viirs", "harmonized"])
    svgEl("polyline", { points: Array.from(series[mode], (v, w) => `${pl + w * sx},${sy(v)}`).join(" "), fill: "none",
      stroke: COL[mode], "stroke-width": mode === "harmonized" ? 2 : 1.5, "stroke-linejoin": "round" }, svg);
  const cross = svgEl("line", { y1: pt, y2: H - pb, stroke: css("--ink"), "stroke-width": 1, opacity: 0 }, svg);
  const hit = svgEl("rect", { x: pl, y: pt, width: W - pl - pr, height: H - pb - pt, fill: "transparent" }, svg);
  hit.addEventListener("mousemove", e => { const bb = svg.getBoundingClientRect(), sc = W / bb.width;
    const w = Math.max(0, Math.min(53, Math.round(((e.clientX - bb.left) * sc - pl) / sx)));
    cross.setAttribute("x1", pl + w * sx); cross.setAttribute("x2", pl + w * sx); cross.setAttribute("opacity", .5);
    showTip(e, `<b>Week of ${dayTxt(weekRange(y, w)[0])}</b><br>` + ["harmonized", "viirs", "modis"].map(md =>
      `<span class="r"><i style="display:inline-block;width:9px;height:9px;background:${COL[md]};margin-right:6px"></i>${MODE_LABEL[md]}: <span class="m">${fmt(series[md][w])}</span></span>`).join("<br>")); });
  hit.addEventListener("mouseleave", () => { cross.setAttribute("opacity", 0); hideTip(); });
}

// ---------------- Figure 5: live map ----------------
function inRegion(ev) {
  if (S.region === "TR") return !!ev.region;
  if (S.region === "rect") return S.rect.contains([ev.lat, ev.lon]);
  return ev.region === S.region;
}
function modeFilter(ev) { return S.mode === "modis" ? ev.nM > 0 : S.mode === "viirs" ? ev.nV > 0 : true; }
async function renderMap() {
  const y = S.year; evLayer.clearLayers();
  const evs = await loadYearEvents(y); if (y !== S.year) return;
  const rng = S.week == null ? null : weekRange(y, S.week);
  const list = evs.filter(ev => inRegion(ev) && modeFilter(ev) && (!rng || (ev.d0 <= rng[1] && ev.d1 >= rng[0])));
  const tEnd = rng ? EPOCH + (rng[1] + 1) * DAY - 3 * 3600e3 : null;
  list.sort((a, b) => a.sumFrp - b.sumFrp);
  for (const ev of list) {
    let conf = ev.conf; if (tEnd) conf *= Math.pow(0.5, Math.max(0, tEnd - ev.t1) / 3600e3 / STALE_HALF_LIFE_H);
    const r = rng ? Math.max(3, Math.min(18, 2 * Math.log1p(ev.sumFrp))) : Math.max(1.5, Math.min(9, 0.9 * Math.log1p(ev.sumFrp)));
    const c = L.circleMarker([ev.lat, ev.lon], { renderer: canvas, radius: r, weight: ev === S.sel ? 2.5 : 0.7, color: ev === S.sel ? css("--ink") : "#faf7f2",
      fillColor: COL[ev.agree], fillOpacity: 0.3 + 0.6 * conf });
    c.on("click", () => { S.sel = ev; renderDetail(ev); renderMap();
      if (innerWidth < 900) $("detail").scrollIntoView({ behavior: "smooth", block: "start" }); });
    c.bindTooltip(`${AGREE_LABEL[ev.agree]} · Trust Score ${Math.round(100 * ev.conf)}%`, { direction: "top" });
    evLayer.addLayer(c);
  }
  const when = rng ? `week of ${dayTxt(rng[0])}` : `${y}`;
  $("mapTitle").textContent = `Fires in ${regionName()}, ${when}: ${fmt(list.length)}`;
  $("mapLede").textContent = rng ? `${fmt(list.length)} fires burned in ${regionName()} during the week of ${dayTxt(rng[0])}. Fainter circles had not been seen for a while by the end of that week. Click one for its record.`
    : `All ${fmt(list.length)} fires of ${y} in ${regionName()}. Pick a week in Fig. 1 to narrow it down, or click a fire for its record.`;
}

// ---------------- fire record ----------------
// news confirmation (data/news_refs.json): a label and a link only, never part of the Trust Score
let NEWS = {};
getJSON("data/news_refs.json").then(d => { d.refs.forEach(r => { NEWS[r.event_id] = r; }); if (S.sel && NEWS[S.sel.id]) renderDetail(S.sel); }).catch(() => {});
const escH = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
function newsLine(id) {
  const n = NEWS[id]; if (!n) return "";
  return `<p class="news"><span class="mono kicker">Reported in the news</span> ${escH(n.place)}: <a href="${escH(n.url)}" target="_blank" rel="noopener">${escH(n.source)}</a>${n.reported_cause ? ` <span class="tag">reported cause: ${escH(n.reported_cause)}</span>` : ""}</p>`;
}
function renderDetail(ev) {
  const both = ev.nM > 0 && ev.nV > 0, passes = ev.tl.length, doubt = 1 - ev.base;
  const bCross = both ? W_CROSS * doubt : 0, bRep = passes >= 2 ? W_REPEAT * doubt : 0;
  const prov = ev.region ? `${S.meta.regions[ev.region]} province` : "just outside Türkiye's border";
  const days = ev.d1 - ev.d0 + 1, hrs = (ev.t1 - ev.t0) / 3600e3;
  const span = days > 1 ? `for ${days} days, from ${dayTxt(ev.d0, false)} to ${dayTxt(ev.d1)}` : hrs >= 1 ? `for about ${Math.round(hrs)} hours on ${dayTxt(ev.d0)}` : `on ${dayTxt(ev.d0)}`;
  const who = both ? "Both satellites confirmed it" : ev.agree === "viirs_only" ? "Only VIIRS saw it, which usually means a fire too small for MODIS" : "Only MODIS saw it";
  const trustWhy = both ? "confirmed by two satellites" : ev.agree === "viirs_only" ? "seen by VIIRS only" : "seen by MODIS only";
  const big = ev.maxFrp >= 1000 ? " It was one of the most intense fires in the record." : "";
  const pct = Math.round(100 * ev.conf);
  $("detail").innerHTML = `<p class="mono kicker">Fire record · <span style="color:${COL[ev.agree]}">${AGREE_LABEL[ev.agree]}</span></p>
  <h3>${ev.region ? S.meta.regions[ev.region] : "Border area"}, ${dayTxt(ev.d0)}</h3>
  <p class="summary">This fire burned in ${prov} ${span}. ${who}.${big}</p>
  <p class="trust">Trust Score: <b>${pct}%</b> — ${trustWhy}</p><div class="meter"><span style="width:${pct}%"></span></div>
  <p class="trustnote">Every fire event gets a trust score, like a credit score for satellite detections.</p>${newsLine(ev.id)}
  <div class="mono kicker" style="margin-top:14px">Who saw it, when</div><div id="timeline"></div>
  <details class="tech"><summary>Technical details</summary>
  <dl class="kv"><dt>Event</dt><dd>${ev.id}</dd><dt>Centroid</dt><dd>${ev.lat.toFixed(4)}, ${ev.lon.toFixed(4)}</dd>
  <dt>First seen</dt><dd>${localTime(ev.t0)}</dd><dt>Last seen</dt><dd>${localTime(ev.t1)}</dd>
  <dt>Duration</dt><dd>${fmt(hrs, 1)} h, ${passes} overpass${passes > 1 ? "es" : ""}</dd>
  <dt>Detections</dt><dd>${ev.nM} MODIS · ${ev.nV} VIIRS</dd><dt>FRP</dt><dd>max ${fmt(ev.maxFrp, 1)} MW · sum ${fmt(ev.sumFrp)} MW</dd></dl>
  <div class="conf"><b>Trust Score = fused confidence ${ev.conf.toFixed(2)}</b>
    <div class="bar"><span style="width:${100 * ev.base}%;background:var(--c3)"></span><span style="width:${100 * bCross}%;background:var(--both)"></span><span style="width:${100 * bRep}%;background:var(--c5)"></span></div>
    <span class="mono">${ev.base.toFixed(2)} base = mean normalized sensor confidence<br>+ ${bCross.toFixed(2)} cross-sensor bonus = 0.30 × (1 − base)${both ? "" : " × 0"}<br>+ ${bRep.toFixed(2)} repeat-overpass bonus = 0.10 × (1 − base)${passes >= 2 ? "" : " × 0"}<br>staleness on the map: × 0.5 per ${STALE_HALF_LIFE_H} h since last detection</span></div>
  </details>`;
  renderTimeline(ev);
}
function renderTimeline(ev) {
  const box = $("timeline"), W = Math.max(box.clientWidth, 260), rows = SATS.filter((s, i) => ev.tl.some(p => p[1] === i));
  const H = 30 + rows.length * 24, pl = 64, pr = 12, span = Math.max(60, ev.tl[ev.tl.length - 1][0]);
  const svg = svgEl("svg", { width: "100%", height: H, viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: "xMinYMin meet" }, box), sx = m => pl + (W - pl - pr) * m / span;
  const days = span >= 2880, lab = t => t === 0 ? "0" : days ? `+${(t / 1440).toFixed(1)} d` : `+${(t / 60).toFixed(t < 600 ? 1 : 0)} h`;
  const ticks = span <= 180 ? [0, span] : [0, span / 4, span / 2, 3 * span / 4, span];
  ticks.forEach(t => { svgEl("line", { x1: sx(t), x2: sx(t), y1: 6, y2: H - 18, stroke: css("--rule2") }, svg);
    svgEl("text", { x: sx(t), y: H - 4, "text-anchor": t === span ? "end" : t === 0 ? "start" : "middle" }, svg).textContent = lab(t); });
  const maxF = Math.max(...ev.tl.map(p => p[3]), 1);
  rows.forEach((s, ri) => { const yy = 15 + ri * 24; svgEl("text", { x: 0, y: yy + 4 }, svg).textContent = s;
    svgEl("line", { x1: pl, x2: W - pr, y1: yy, y2: yy, stroke: css("--rule") }, svg); });
  ev.tl.forEach(p => { const s = SATS[p[1]], yy = 15 + rows.indexOf(s) * 24, isM = p[1] < 2;
    const c = svgEl("circle", { cx: sx(p[0]), cy: yy, r: 3 + 6 * Math.sqrt(p[3] / maxF), fill: isM ? COL.modis : COL.viirs, "fill-opacity": .85, stroke: css("--paper"), "stroke-width": 1.5 }, svg);
    hover(c, `<b>${s}</b> <span class="r">(${isM ? "MODIS, 1 km pixels" : "VIIRS, 375 m pixels"})</span><br><span class="r">${localTime(ev.t0 + p[0] * 60000)} local<br>${p[2]} pixel${p[2] > 1 ? "s" : ""} · <span class="m">${fmt(p[3], 1)} MW</span></span>`); });
}

// ---------------- Figure 4: what two satellites saw ----------------
async function renderStory() {
  const st = await getJSON("data/story.json").catch(() => null);
  // Totals inside Türkiye's provinces, taken from the national calendar (the download box can
  // also cover neighbouring countries, so the raw meta counts are not used for these sentences).
  const trCal = await getJSON("data/calendar/TR.json"), H = trCal.modes.harmonized, sum = v => v.reduce((p, q) => p + q, 0);
  const nM = sum(H.dm), nV = sum(H.dv), fdBoth = sum(H.b), fdAll = sum(H.b) + sum(H.mo) + sum(H.vo);
  const c = { detections: nM + nV, events: S.meta.counts.harmonized.events_tr ?? S.meta.counts.harmonized.events };
  $("bigNum").innerHTML = `<span class="n">${fmt(c.detections)}</span> detections <span style="color:var(--muted)">→</span> <span class="n to">${fmt(c.events)}</span> fire events
    <small>${S.meta.first_day.slice(0, 4)}–${S.meta.last_day.slice(0, 4)}, inside Türkiye. On average ${(c.detections / c.events).toFixed(1)} detections describe one fire.</small>`;
  $("bothLine").textContent = `Only ${fmt(100 * fdBoth / fdAll, 1)}% of fire-days were recorded by both satellites. Most of the rest are small fires that only VIIRS can resolve, so neither instrument on its own sees the whole season.`;
  $("footNums").textContent = `This almanac holds ${fmt(c.detections)} satellite fire detections over Türkiye from ${S.meta.first_day.slice(0, 4)} to ${S.meta.last_day.slice(0, 4)} (${fmt(nM)} from MODIS, ${fmt(nV)} from VIIRS), merged into ${fmt(c.events)} fire events. Both satellites recorded the fire on ${fmt(100 * fdBoth / fdAll, 1)}% of fire-days.`;
  if (!st) return;
  const date = new Date(st.day + "T00:00:00Z").toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
  $("storyLede").textContent = `${date}, around ${st.name}. Left, every pixel the two instruments flagged that day. Right, the same pixels after merging.`;
  $("storyNote").textContent = `MODIS logged ${fmt(st.n_modis)} hot pixels that day and VIIRS ${fmt(st.n_viirs)}. Most describe the same few hillsides. After merging there are ${fmt(st.events.length)} fire events, each with a location, a duration and a Trust Score.`;
  $("capRaw").textContent = `Raw detections: ${fmt(st.n_modis + st.n_viirs)}`;
  $("capMerged").textContent = `Fire events: ${fmt(st.events.length)}`;
  const pts = st.detections.map(p => [p[0], p[1]]).concat(st.events.map(p => [p[0], p[1]]));
  const bounds = L.latLngBounds(pts).pad(0.12);
  const mk = id => { const m = L.map(id, { zoomControl: false, attributionControl: false, scrollWheelZoom: false, dragging: false, doubleClickZoom: false, boxZoom: false, keyboard: false, touchZoom: false, preferCanvas: true });
    L.tileLayer(BASE, { maxZoom: 16 }).addTo(m); m.fitBounds(bounds); return m; };
  const m1 = mk("mapRaw"), m2 = mk("mapMerged"), cv1 = L.canvas(), cv2 = L.canvas();
  st.detections.forEach(([la, lo, s]) => L.circleMarker([la, lo], { renderer: cv1, radius: s === 0 ? 4 : 2.2, weight: 0, fillColor: s === 0 ? COL.modis : COL.viirs, fillOpacity: s === 0 ? .55 : .7 }).addTo(m1));
  st.events.slice().sort((p, q) => q[3] - p[3]).forEach(([la, lo, ag, frp]) => L.circleMarker([la, lo], { renderer: cv2, radius: Math.max(3, Math.min(26, 2.4 * Math.log1p(frp))), weight: 1, color: "#faf7f2", fillColor: COL[ag], fillOpacity: .75 }).addTo(m2));
  addEventListener("resize", () => { m1.invalidateSize(); m2.invalidateSize(); m1.fitBounds(bounds); m2.fitBounds(bounds); });
}

// ---------------- orchestration ----------------
function renderAll() {
  if (S.year == null) S.year = S.meta.years.includes(2021) ? 2021 : S.meta.years[S.meta.years.length - 1];
  document.querySelectorAll("#modeSeg button").forEach(b => b.classList.toggle("on", b.dataset.mode === S.mode));
  document.querySelectorAll("#metricSeg button").forEach(b => b.classList.toggle("on", b.dataset.metric === S.metric));
  renderCalendar(); renderNormal(); renderMonths(); renderCompare(); renderMap();
  if (window.HSH_EDU) window.HSH_EDU.update(S);
}
function selectRegion(id) { S.region = id; $("regionSel").value = id; if (id !== "rect" && rectLayer) { map.removeLayer(rectLayer); rectLayer = null; }
  styleProvinces(); loadRegion(); }

async function init() {
  S.meta = await getJSON("data/meta.json");
  const sel = $("regionSel"), names = Object.entries(S.meta.regions).filter(([k]) => k !== "TR").sort((a, b) => a[1].localeCompare(b[1], "tr"));
  sel.innerHTML = `<option value="TR">Türkiye, all provinces</option>` + names.map(([k, v]) => `<option value="${k}">${v}</option>`).join("") + `<option value="rect" disabled>Drawn area</option>`;
  sel.addEventListener("change", () => selectRegion(sel.value));
  document.querySelectorAll("#modeSeg button").forEach(b => b.addEventListener("click", () => { S.mode = b.dataset.mode; renderAll(); }));
  document.querySelectorAll("#metricSeg button").forEach(b => b.addEventListener("click", () => { S.metric = b.dataset.metric; renderAll(); }));
  provLayer.addData(await getJSON("data/provinces.geojson"));
  const cb = $("cbMode"); try { cb.checked = localStorage.getItem("almanac-cb") === "1"; } catch (e) {}
  const applyCb = () => { document.body.classList.toggle("cb", cb.checked); readColors(); try { localStorage.setItem("almanac-cb", cb.checked ? "1" : "0"); } catch (e) {} };
  applyCb(); cb.addEventListener("change", () => { applyCb(); renderAll(); });
  const q = new URLSearchParams(location.search);
  if (q.get("region") && S.meta.regions[q.get("region")]) S.region = q.get("region");
  if (q.get("mode") && MODES.includes(q.get("mode"))) S.mode = q.get("mode");
  sel.value = S.region; styleProvinces();
  await loadRegion();
  renderStory();
  // first visit: draw attention to the most unusual week of summer 2021 when the calendar comes into view
  if (S.meta.years.includes(2021) && !q.get("year")) {
    let best = null; S.wk.W[2021].forEach((s, w) => { if (w >= 26 && w <= 35 && s.unusual && (!best || s.z > best.z)) best = { w, z: s.z }; });
    if (best) {
      selectWeek(2021, best.w);
      const io = new IntersectionObserver(es => { if (es.some(e => e.isIntersecting)) { focusWeek(2021, best.w); io.disconnect(); } }, { threshold: 0.4 });
      io.observe($("calendar"));
    }
  } else if (q.get("year")) { S.year = +q.get("year"); renderAll(); }
  let rt; addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => { renderMonths(); renderCompare(); }, 150); });
}
window.HSH = S;
init().catch(e => { console.error(e); status("Failed to load data: " + e.message); });
})();
