"use strict";

/* ---------- helpers ---------- */
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const el = (tag, attrs = {}, ...children) => {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === undefined || v === null || v === false) continue;
    if (k === "class") node.className = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else if (k === "html") node.innerHTML = v;
    else node.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) if (c !== null && c !== undefined && c !== false) node.append(c);
  return node;
};

async function api(path, opts = {}) {
  const init = { ...opts, headers: { "X-PF-Lang": LANG, ...(opts.headers || {}) } };
  if (opts.json !== undefined) {
    init.body = JSON.stringify(opts.json);
    init.headers["Content-Type"] = "application/json";
    delete init.json;
  }
  const r = await fetch(path, init);
  if (r.status === 401 && !path.startsWith("api/login")) {
    location.href = "login";
    throw new Error(t("Anmeldung erforderlich"));
  }
  let data = null;
  try { data = await r.json(); } catch { /* no body */ }
  if (!r.ok) {
    const msg = data?.detail || data?.errors?.join(", ") || t("Fehler {0}", r.status);
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return data;
}

function toast(text, kind = "") {
  const node = el("div", { class: `toast ${kind}` }, text);
  $("#toasts").append(node);
  setTimeout(() => node.remove(), kind === "bad" ? 9000 : 4500);
}

const STATE_LABEL = {
  offline: t("Offline"), idle: t("Bereit"), preparing: t("Vorbereitung"), printing: t("Druckt"),
  paused: t("Pausiert"), finished: t("Fertig"), failed: t("Fehlgeschlagen"), cancelled: t("Abgebrochen"),
  error: t("Fehler"), unknown: t("Unbekannt"), running: t("Läuft"), off: t("Ausgeschaltet"),
};
const ACTIVE = ["preparing", "printing", "paused"];
const TEMP_LABEL = { nozzle: t("Düse"), bed: t("Bett"), chamber: t("Kammer") };
const tempLabel = (key) => TEMP_LABEL[key] || key;
const MAINT_NAME = { clean: "Drucker reinigen", lube: "Schmieren" };
const maintName = (id) => t(MAINT_NAME[id] || id);

function fmtDuration(s) {
  if (s === null || s === undefined) return "–";
  s = Math.max(0, Math.round(s));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  if (h) return `${h} h ${String(m).padStart(2, "0")} min`;
  if (m) return `${m} min`;
  return `${s} s`;
}
function fmtClock(date) {
  return date.toLocaleTimeString(LOCALE, { hour: "2-digit", minute: "2-digit" });
}
function fmtEta(remaining) {
  const end = new Date(Date.now() + remaining * 1000);
  const today = new Date();
  const dayDiff = Math.round((new Date(end.toDateString()) - new Date(today.toDateString())) / 86400000);
  const prefix = dayDiff === 0 ? "" : dayDiff === 1 ? t("morgen ") : end.toLocaleDateString(LOCALE, { weekday: "short" }) + " ";
  return prefix + fmtClock(end);
}
function fmtCost(cost) {
  if (!cost) return "";
  return fmtMoney(cost, lastState?.costs?.currency);
}
function fmtFilament(g, m, cost) {
  if (!g && !m) return "";
  return [g ? `${Math.round(g)} g` : "", m ? `${m.toFixed(1)} m` : "", fmtCost(cost)].filter(Boolean).join(" · ");
}
function fmtMaterials(list) {
  return (list || []).map((x) => `${x.type} ${Math.round(x.g)} g`).join(" · ");
}
function fmtDate(ts) {
  const d = new Date(ts * 1000);
  return d.toLocaleDateString(LOCALE, { day: "2-digit", month: "2-digit", year: "2-digit" }) + " " + fmtClock(d);
}
const icon = (path) => {
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("viewBox", "0 0 24 24");
  s.innerHTML = `<path d="${path}"/>`;
  return s;
};
// Spool symbol: grey flange, coloured filament ring (fill level optional), hub with holes
function spoolIcon(color, { size = 22, fill = 1, empty = false } = {}) {
  const safe = /^#([0-9a-f]{3}|[0-9a-f]{6}|[0-9a-f]{8})$/i.test(color || "");
  const c = empty || !safe ? "transparent" : color;
  const f = Math.max(0.08, Math.min(1, Number.isFinite(fill) ? fill : 1));
  const rOuter = 8 + 12 * f;            // filament ring radius 8..20 (of 24)
  const holes = [0, 72, 144, 216, 288].map((a) => {
    const r = (a * Math.PI) / 180;
    return `<circle cx="${(24 + 4.3 * Math.cos(r)).toFixed(1)}" cy="${(24 + 4.3 * Math.sin(r)).toFixed(1)}" r="1.1" fill="var(--panel)"/>`;
  }).join("");
  const wrap = document.createElement("span");
  wrap.className = "spool-icon";
  wrap.style.width = wrap.style.height = `${size}px`;
  wrap.innerHTML = `<svg viewBox="0 0 48 48" width="${size}" height="${size}" aria-hidden="true">
    <circle cx="24" cy="24" r="23" fill="#5b6370"/>
    <circle cx="24" cy="24" r="21.5" fill="#3a414b"/>
    ${empty ? `<circle cx="24" cy="24" r="19" fill="none" stroke="#5b6370" stroke-width="1" stroke-dasharray="2 3"/>`
      : `<circle cx="24" cy="24" r="${rOuter.toFixed(1)}" fill="${c}" stroke="rgba(0,0,0,.25)" stroke-width="0.8"/>
         <circle cx="24" cy="24" r="${(rOuter - 2.5).toFixed(1)}" fill="none" stroke="rgba(255,255,255,.18)" stroke-width="0.8"/>`}
    <circle cx="24" cy="24" r="6.8" fill="#cfd5dc"/>
    ${holes}
    <circle cx="24" cy="24" r="2" fill="var(--panel)"/>
  </svg>`;
  return wrap;
}

const ICONS = {
  pause: "M14 19h4V5h-4M6 19h4V5H6z",
  play: "M8 5.14v14l11-7z",
  stop: "M18 18H6V6h12z",
  light: "M12 2a7 7 0 0 0-7 7c0 2.38 1.19 4.47 3 5.74V17a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1v-2.26c1.81-1.27 3-3.36 3-5.74a7 7 0 0 0-7-7M9 21a1 1 0 0 0 1 1h4a1 1 0 0 0 1-1v-1H9z",
  upload: "M9 16v-6H5l7-7 7 7h-4v6zm-4 4v-2h14v2z",
  power: "M16.56 5.44l-1.45 1.45A5.97 5.97 0 0 1 18 12a6 6 0 0 1-12 0c0-2.17 1.16-4.06 2.88-5.12L7.44 5.44A7.96 7.96 0 0 0 4 12a8 8 0 0 0 16 0c0-2.72-1.36-5.12-3.44-6.56M13 3h-2v10h2z",
};

/* ---------- camera streams over WebSocket ---------- */
// One WebSocket per visible camera. Avoids the browser's 6-connection limit
// that plain MJPEG <img> streams run into.
const camStreams = new Set();

function wsUrl(path) {
  const u = new URL(path, location.href);
  u.protocol = u.protocol === "https:" ? "wss:" : "ws:";
  return u.toString();
}

function attachCamera(container, camId) {
  container.querySelectorAll("img, .cam-msg").forEach((n) => n.remove());
  const img = el("img", { alt: "" });
  const msg = el("div", { class: "cam-msg" }, t("Verbinde Kamera …"));
  container.prepend(img);
  container.append(msg);
  const stream = { container, closed: false, ws: null, url: null, timer: null };
  let gotFrame = false;
  const connect = () => {
    if (stream.closed) return;
    const ws = new WebSocket(wsUrl(`api/camera/${encodeURIComponent(camId)}/ws`));
    ws.binaryType = "blob";
    stream.ws = ws;
    ws.onmessage = (ev) => {
      const url = URL.createObjectURL(ev.data);
      img.onload = () => { if (stream.url && stream.url !== url) URL.revokeObjectURL(stream.url); stream.url = url; };
      img.src = url;
      if (!gotFrame) { gotFrame = true; msg.hidden = true; }
    };
    ws.onclose = () => {
      if (stream.closed) return;
      const camInfo = (lastState?.cameras || []).find((c) => c.id === camId);
      msg.hidden = false;
      msg.textContent = camInfo?.error ? t("Kamera: {0}", camInfo.error) : t("Kamera getrennt – verbinde neu …");
      stream.timer = setTimeout(connect, 3000);
    };
  };
  connect();
  // Show a hint if no frame arrives after a while
  setTimeout(() => {
    if (!gotFrame && !stream.closed) {
      const camInfo = (lastState?.cameras || []).find((c) => c.id === camId);
      msg.textContent = camInfo?.error ? t("Kamera: {0}", camInfo.error) : t("Warte auf Bild …");
    }
  }, 8000);
  stream.close = () => {
    stream.closed = true;
    clearTimeout(stream.timer);
    if (stream.ws) stream.ws.close();
    if (stream.url) URL.revokeObjectURL(stream.url);
    camStreams.delete(stream);
  };
  camStreams.add(stream);
  return stream;
}

function detachCameras(root = document) {
  for (const s of [...camStreams]) if (root.contains(s.container)) s.close();
}

function openCamOverlay(camId, title) {
  const ov = $("#cam-overlay");
  // keep the overlay visible when the detail view is in browser full screen
  const fs = document.fullscreenElement;
  if (fs && !fs.contains(ov)) fs.append(ov);
  else if (!fs && ov.parentElement !== document.body) document.body.append(ov);
  $("#cam-overlay-title").textContent = title;
  ov.hidden = false;
  const info = (lastState?.cameras || []).find((x) => x.id === camId);
  showCamera($(".overlay-cam", ov), (lastState?.printers || []).find((x) => x.id === info?.printer_id), camId);
}
function openImageOverlay(src, title) {
  const ov = $("#cam-overlay");
  const fs = document.fullscreenElement;
  if (fs && !fs.contains(ov)) fs.append(ov);
  $("#cam-overlay-title").textContent = title;
  const box = $(".overlay-cam", ov);
  box.querySelectorAll("img, .cam-msg").forEach((n) => n.remove());
  box.prepend(el("img", { src, alt: "" }));
  ov.hidden = false;
}
function closeOverlay() {
  const ov = $("#cam-overlay");
  detachCameras(ov);
  ov.hidden = true;
}
$("#cam-overlay").addEventListener("click", (e) => {
  if (e.target.closest("[data-close]") || e.target === e.currentTarget) closeOverlay();
});
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  if (!$("#cam-overlay").hidden) closeOverlay();
  else if (detail) closeDetail();
});

/* ---------- navigation ---------- */
let currentView = "overview";
function showView(name) {
  detachCameras($(`#view-${currentView}`));
  currentView = name;
  $$(".tabs button").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  $$(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${name}`));
  history.replaceState(null, "", `#${name}`);
  if (name === "overview") { cards.clear(); $("#printer-grid").innerHTML = ""; renderOverview(); }
  renderSysbar();
  if (name === "cameras") renderCameras();
  if (name === "history") loadHistory();
  if (name === "filament") loadFilament();
  if (name === "settings") loadSettings();
}
$$(".tabs button").forEach((b) => b.addEventListener("click", () => showView(b.dataset.view)));
document.addEventListener("click", (e) => {
  const go = e.target.closest("[data-goto]");
  if (go) showView(go.dataset.goto);
});
document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    detachCameras();
  } else if (detail) {
    const id = detail.id; closeDetail(); openDetail(id);
  } else {
    showView(currentView);
  }
});

/* ---------- state polling ---------- */
let lastState = null;
async function poll() {
  try {
    lastState = await api("api/state");
    syncLanguage(lastState.language);
    renderSysbar();
    renderPasswordBanner();
    if (currentView === "cameras" && camerasStateKey() !== camerasKey) renderCameras();
    if (detail) renderDetail();
    else if (currentView === "overview") renderOverview();
  } catch (e) {
    /* keep last state; next poll will retry */
  } finally {
    setTimeout(poll, 2000);
  }
}

/* ---------- warning: direct access without a password ---------- */
function renderPasswordBanner() {
  const b = $("#nopw-banner");
  const a = lastState?.auth;
  const show = !!a && !a.enabled && !a.ingress;
  b.hidden = !show;
  if (show && !b.childElementCount) {
    b.append(el("span", {}, t("⚠️ Direkter Zugriff ohne Passwort: Jedes Gerät in deinem Netzwerk kann Drucker steuern und Kameras sehen.")),
      el("button", { class: "btn mini", onclick: () => showView("settings") }, t("Passwort setzen")));
  }
}

/* ---------- system load bar (bottom of the overview) ---------- */
function fmtBytes(b) {
  const gb = b / 1024 ** 3;
  return gb >= 100 ? `${Math.round(gb)} GB` : `${gb.toFixed(1)} GB`;
}
function renderSysbar() {
  const bar = $("#sysbar");
  const s = lastState?.system;
  const show = !!s && currentView === "overview" && !detail;
  bar.hidden = !show;
  document.body.classList.toggle("sysbar-on", show);
  if (!show) return;
  const level = (v, warn, bad) => (v == null ? "" : v >= bad ? " bad" : v >= warn ? " warn" : "");
  const item = (cls, label, value, title = "") => el("span", { class: `sys-item${cls}`, title }, el("b", {}, label), " ", value);
  const temps = s.temps || [];
  const cpuT = temps.find((x) => x.kind === "cpu");
  const items = [];
  if (s.cpu != null || cpuT) {
    const worst = Math.max(level(s.cpu, 80, 95) ? (s.cpu >= 95 ? 2 : 1) : 0, cpuT ? (cpuT.temp >= 90 ? 2 : cpuT.temp >= 80 ? 1 : 0) : 0);
    items.push(item(["", " warn", " bad"][worst], "CPU",
      [s.cpu != null ? `${Math.round(s.cpu)} %` : null, cpuT ? `${Math.round(cpuT.temp)} °C` : null].filter(Boolean).join(" · "),
      s.cores ? t("{0} Kerne", s.cores) : ""));
  }
  if (s.memory) {
    items.push(item(level(s.memory.percent, 85, 95), "RAM", `${fmtBytes(s.memory.used)} / ${fmtBytes(s.memory.total)}`,
      t("{0} % belegt", Math.round(s.memory.percent))));
  }
  if (s.disk) {
    const freePct = 100 - s.disk.percent;
    items.push(item(freePct <= 5 ? " bad" : freePct <= 15 ? " warn" : "", t("Speicher"), t("{0} frei", fmtBytes(s.disk.free)),
      t("{0} % belegt von {1}", Math.round(s.disk.percent), fmtBytes(s.disk.total))));
  }
  const KIND = { gpu: "GPU", disk: "SSD", board: t("Mainboard") };
  for (const x of temps) {
    if (x.kind === "cpu") continue;
    items.push(item(level(x.temp, x.kind === "disk" ? 60 : 80, x.kind === "disk" ? 70 : 90), KIND[x.kind] || x.name,
      `${Math.round(x.temp)} °C`, x.name));
  }
  bar.replaceChildren(el("span", { class: "sys-title" }, lastState.addon ? "Home Assistant" : t("System")), ...items);
}

/* ---------- overview ---------- */
const cards = new Map(); // printer id -> {node, camId, ...}

function renderOverview() {
  if (!lastState) return;
  const grid = $("#printer-grid");
  const printers = lastState.printers;
  $("#empty-overview").hidden = printers.length > 0;
  const ids = new Set(printers.map((p) => p.id));
  for (const [id, c] of cards) {
    if (!ids.has(id)) { detachCameras(c.node); c.node.remove(); cards.delete(id); }
  }
  for (const p of printers) {
    let c = cards.get(p.id);
    if (!c) {
      c = buildCard(p);
      cards.set(p.id, c);
      grid.append(c.node);
    }
    updateCard(c, p);
  }
}

function buildCard(p) {
  const node = el("article", { class: "card", "data-id": p.id });
  const cam = el("div", { class: "cam" });
  const extras = el("div", { class: "cam-extras", hidden: true });
  const c = {
    node, cam, extras, camId: null, camKey: "",
    badge: el("span", { class: "badge" }),
    file: el("div", { class: "file" }),
    thumb: el("img", { class: "job-thumb", alt: "", hidden: true }),
    bar: el("div", { class: "bar" }),
    progress: null,
    time: el("div", { class: "time-row" }),
    temps: el("div", { class: "chips" }),
    fils: el("div", { class: "chips" }),
    alerts: el("div", {}),
    actions: el("div", { class: "actions" }),
  };
  c.progress = el("div", { class: "progress" }, c.bar);
  node.addEventListener("click", (e) => {
    if (e.target.closest("button, a, select, input")) return;
    openDetail(p.id);
  });
  node.append(
    cam,
    extras,
    el("div", { class: "card-body" },
      el("div", { class: "card-head" }, el("h2", {}, p.name), c.badge),
      el("div", { class: "file-row" }, c.thumb, c.file), c.progress, c.time, c.temps, c.fils, c.alerts, c.actions),
  );
  return c;
}

// Cameras that belong to a printer (built-in or assigned in the settings) only connect while
// the printer is on: otherwise show why instead of a technical error. Cameras without a printer
// keep running as before.
function camPausedText(p, id) {
  const printer = p || {};
  const cam = (lastState?.cameras || []).find((x) => x.id === id);
  const belongs = id && (cam ? cam.printer_id === printer.id : id.startsWith(`${printer.id}-cam`));
  if (!printer.id || !belongs) return "";
  if (printer.state === "off") return t("Drucker ist ausgeschaltet");
  if (!printer.online) return t("Drucker nicht erreichbar");
  return "";
}
function showCamera(box, p, id) {
  const why = camPausedText(p, id);
  if (!why) { attachCamera(box, id); return; }
  box.querySelectorAll("img, .cam-msg").forEach((n) => n.remove());
  box.append(el("div", { class: "cam-msg" }, why));
}

function setCameras(c, p) {
  detachCameras(c.cam);
  detachCameras(c.extras);
  c.extras.innerHTML = "";
  const [main, ...rest] = p.cameras;
  c.camId = main || null;
  c.cam.querySelectorAll("img, .cam-msg, .cam-label").forEach((n) => n.remove());
  if (!main) {
    c.cam.append(el("div", { class: "cam-msg" }, t("Keine Kamera")));
  } else {
    showCamera(c.cam, p, main);
  }
  // assigned external cameras: each one live in its own small tile
  for (const id of rest) {
    const info = lastState.cameras.find((x) => x.id === id);
    const tile = el("div", { class: "cam mini", title: info?.name || "" });
    c.extras.append(tile);
    showCamera(tile, p, id);
    tile.append(el("span", { class: "cam-label" }, info?.name || t("Kamera")));
  }
  c.extras.hidden = rest.length === 0;
  c.extras.dataset.count = String(Math.min(rest.length, 3));
}

function updateCard(c, p) {
  c.node.className = `${c.baseClass || "card"} state-${p.state}`;
  c.badge.className = `badge ${p.state}`;
  c.badge.textContent = STATE_LABEL[p.state] || p.state;

  // cameras
  const camKey = p.cameras.join("|") + "|" + camPausedText(p, p.cameras[0]);
  if (!c.noCams && camKey !== c.camKey) {
    c.camKey = camKey;
    setCameras(c, p);
  }

  // file + progress
  c.file.textContent = p.state === "off" ? t("Drucker ist ausgeschaltet")
    : p.filename || (p.online ? t("Kein Druckauftrag") : (p.power?.on ? t("Startet / verbindet …") : t("Drucker nicht erreichbar")));
  c.file.title = p.filename || "";
  if (c.thumb) {
    const src = p.job?.thumb ? `api/printers/${p.id}/thumbnail?k=${encodeURIComponent(p.job.key)}` : "";
    if (c.thumb.dataset.src !== src) { c.thumb.dataset.src = src; if (src) c.thumb.src = src; }
    c.thumb.hidden = !src;
  }
  const showProgress = p.progress !== null && p.progress !== undefined;
  c.progress.hidden = !showProgress;
  if (showProgress) c.bar.style.width = `${Math.min(100, Math.max(0, p.progress))}%`;

  // time row
  c.time.innerHTML = "";
  if (ACTIVE.includes(p.state)) {
    c.time.append(el("span", { class: "big" }, `${p.progress ?? 0} %`));
    if (p.remaining_s !== null && p.remaining_s !== undefined) {
      c.time.append(
        el("span", {}, el("span", { class: "big" }, fmtDuration(p.remaining_s)), el("span", { class: "small" }, t(" übrig"))),
        el("span", { class: "small" }, t("fertig ca. {0}", fmtEta(p.remaining_s))),
      );
    }
    if (p.total_layers) c.time.append(el("span", { class: "small" }, t("Schicht {0}/{1}", p.layer ?? 0, p.total_layers)));
    const fil = fmtFilament(p.job?.weight_g, null, p.job?.cost);
    if (fil) c.time.append(el("span", { class: "small", title: t("Filament für diesen Druck (laut Slicer)") }, `≈ ${fil}`));
  }
  c.time.hidden = !c.time.childElementCount;

  // temps
  c.temps.innerHTML = "";
  for (const tp of p.temps) {
    const target = tp.target ? el("span", { class: "muted" }, ` / ${Math.round(tp.target)}°`) : "";
    c.temps.append(el("span", { class: `chip${tp.active ? " active" : ""}` }, `${tempLabel(tp.label)} ${tp.cur === null ? "–" : Math.round(tp.cur)}°`, target));
  }
  for (const a of p.ams || []) {
    const parts = [];
    const humMax = Number(p.ams_hum_max) || 30;
    const own = a.src === "ha";
    const show = (k) => own ? a.configured?.[k] : a[k] != null;
    if (show("temp")) parts.push(el("span", {}, `🌡 ${a.temp != null ? a.temp.toFixed(1) + "°" : "–"}`));
    if (show("hum")) parts.push(el("span", { class: a.hum != null && a.hum > humMax ? "bad" : "", title: t("Warnung ab {0} %", humMax) },
      `💧 ${a.hum != null ? Math.round(a.hum) + " %" : "–"}`));
    else if (!own && a.hum_level) parts.push(el("span", { title: t("Feuchtigkeitsstufe vom AMS (1–5)") }, t("💧 Stufe {0}", a.hum_level)));
    if (show("bat")) parts.push(el("span", { class: a.bat != null && a.bat < 20 ? "bad" : "", title: t("Batterie des Sensors") },
      `${a.bat != null && a.bat < 20 ? "🪫" : "🔋"} ${a.bat != null ? Math.round(a.bat) + " %" : "–"}`));
    if (!parts.length) continue;
    c.temps.append(el("span", { class: "chip ams", title: `${a.name} · ${own ? t("eigener Sensor (Home Assistant)") : t("Werte vom AMS")}` },
      el("b", {}, a.name), ...parts));
  }
  c.temps.hidden = !c.temps.childElementCount;

  // filaments (AMS)
  c.fils.innerHTML = "";
  for (const f of p.filaments) {
    c.fils.append(el("span", { class: `chip${f.active ? " active" : ""}`, title: [f.vendor, f.remain != null ? t("{0} % übrig", f.remain) : ""].filter(Boolean).join(" · ") },
      spoolIcon(f.color, { size: 18, empty: !f.type, fill: f.remain != null ? f.remain / 100 : 1 }),
      `${f.slot} ${f.type || t("leer")}`));
  }
  c.fils.hidden = !p.filaments.length;

  // alerts
  c.alerts.innerHTML = "";
  if (p.error) c.alerts.append(el("div", { class: "alert" }, p.error));
  for (const h of p.hms) {
    c.alerts.append(el("div", { class: `alert ${h.severity === "info" ? "warn" : ""}` },
      "HMS ", el("a", { href: h.url, target: "_blank", rel: "noopener" }, h.code)));
  }
  if (p.cmd_message) c.alerts.append(el("div", { class: "alert warn" }, p.cmd_message));
  const dueTasks = (p.maintenance || []).filter((m) => m.due);
  if (dueTasks.length) c.alerts.append(el("div", { class: "alert warn" }, t("🔧 Wartung fällig: {0}", dueTasks.map((m) => maintName(m.id)).join(", "))));

  // actions
  const key = `${p.state}|${p.online}|${p.light}|${p.power?.on}|${p.power?.available}`;
  if (c.actionKey !== key) {
    c.actionKey = key;
    c.actions.innerHTML = "";
    const canControl = p.online && p.state !== "off";
    if (p.power) c.actions.append(powerBtn(p));
    if (p.state === "off") return;
    if (p.control === "monitor") {
      c.actions.append(el("button", {
        class: "btn", disabled: !canControl, onclick: () => openPrintDialog(p.id),
      }, icon(ICONS.upload), t("Datei hochladen")));
      c.actions.append(el("span", { class: "note monitor-note" }, t("Steuerung über Bambu Handy / Studio")));
      return;
    }
    if (p.state === "paused") {
      c.actions.append(actionBtn(p, "resume", t("Fortsetzen"), ICONS.play, "primary"));
    } else {
      c.actions.append(actionBtn(p, "pause", t("Pause"), ICONS.pause, "", !canControl || p.state !== "printing"));
    }
    c.actions.append(actionBtn(p, "stop", t("Stopp"), ICONS.stop, "danger", !canControl || !ACTIVE.includes(p.state)));
    if (p.light !== null) {
      c.actions.append(actionBtn(p, p.light ? "light_off" : "light_on", t("Licht"), ICONS.light, p.light ? "on" : "", !canControl));
    }
    c.actions.append(el("button", {
      class: "btn", disabled: !canControl,
      onclick: () => openPrintDialog(p.id),
    }, icon(ICONS.upload), t("Datei drucken")));
  }
}

function powerBtn(p) {
  const on = p.power.on;
  return el("button", {
    class: `btn ${on ? "" : "primary"}`,
    disabled: !p.power.available,
    title: p.power.error || p.power.entity,
    onclick: async (e) => {
      const btn = e.currentTarget;
      if (on && !confirm(t("„{0}“ ausschalten?", p.name))) return;
      btn.disabled = true;
      try {
        await api(`api/printers/${p.id}/power`, { method: "POST", json: { on: !on } });
      } catch (err) {
        if (err.message.includes("druckt gerade") &&
            confirm(t("{0}.\n\nTrotzdem ausschalten?", err.message))) {
          try { await api(`api/printers/${p.id}/power`, { method: "POST", json: { on: false, force: true } }); }
          catch (err2) { toast(err2.message, "bad"); }
        } else {
          toast(err.message, "bad");
        }
      } finally {
        btn.disabled = false;
      }
    },
  }, icon(ICONS.power), on ? t("Ausschalten") : on === false ? t("Einschalten") : t("Steckdose ?"));
}

function actionBtn(p, action, label, path, cls = "", disabled = false) {
  return el("button", {
    class: `btn ${cls}`, disabled,
    onclick: async (e) => {
      if (action === "stop" && !confirm(t("Druck auf „{0}“ wirklich abbrechen?", p.name))) return;
      const btn = e.currentTarget;
      btn.disabled = true;
      try {
        await api(`api/printers/${p.id}/command`, { method: "POST", json: { action } });
      } catch (err) {
        toast(err.message, "bad");
      } finally {
        setTimeout(() => { btn.disabled = false; }, 1500);
      }
    },
  }, icon(path), label);
}

/* ---------- print dialog ---------- */
function openPrintDialog(printerId) {
  const p = lastState.printers.find((x) => x.id === printerId);
  if (!p) return;
  const dlg = $("#print-dialog");
  $("#print-title").textContent = t("Datei drucken – {0}", p.name);
  const content = $("#print-content");
  content.innerHTML = "";
  const input = el("input", { type: "file", accept: p.file_types.join(","), hidden: true });
  const zone = el("div", { class: "dropzone" },
    el("div", {}, t("Datei hierher ziehen oder klicken")),
    el("div", { class: "note" }, t("Erlaubt: {0}", p.file_types.join(", ")) +
      (p.type === "bambu" ? t(" (in Bambu Studio / OrcaSlicer: „Druckplatte geslict exportieren“)") : "")));
  const progress = el("div", { class: "upload-bar", hidden: true }, el("div"));
  zone.addEventListener("click", () => input.click());
  zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("drag"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("drag"));
  zone.addEventListener("drop", (e) => {
    e.preventDefault(); zone.classList.remove("drag");
    if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
  });
  input.addEventListener("change", () => input.files[0] && handleFile(input.files[0]));
  content.append(zone, input, progress);
  dlg.showModal();

  function handleFile(file) {
    const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
    if (!p.file_types.includes(ext)) { toast(t("{0} kann keine {1}-Dateien drucken", p.name, ext), "bad"); return; }
    zone.hidden = true;
    progress.hidden = false;
    const fd = new FormData();
    fd.append("file", file);
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "api/uploads");
    xhr.setRequestHeader("X-PF-Lang", LANG);
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) progress.firstChild.style.width = `${(e.loaded / e.total) * 100}%`; };
    xhr.onload = () => {
      progress.hidden = true;
      if (xhr.status >= 300) {
        let msg = t("Upload fehlgeschlagen");
        try { msg = JSON.parse(xhr.responseText).detail || msg; } catch { /* keep */ }
        toast(msg, "bad"); zone.hidden = false; return;
      }
      showPrintOptions(p, JSON.parse(xhr.responseText), content, dlg);
    };
    xhr.onerror = () => { toast(t("Upload fehlgeschlagen"), "bad"); zone.hidden = false; progress.hidden = true; };
    xhr.send(fd);
  }
}

function showPrintOptions(p, info, content, dlg) {
  content.innerHTML = "";
  content.append(el("div", {}, el("strong", {}, info.name), el("span", { class: "note" }, `  ${(info.size / 1048576).toFixed(1)} MB`)));
  if (info.error) content.append(el("div", { class: "alert" }, info.error));
  const opts = { plate: 1, use_ams: p.filaments.some((f) => f.slot !== "Ext"), timelapse: false, bed_leveling: true, ams_map: {} };
  let mappingBox = null;

  if (info.kind === "3mf") {
    const sliced = info.plates.filter((pl) => pl.sliced);
    if (!sliced.length) {
      content.append(el("div", { class: "alert" }, t("Diese .3mf enthält keinen G-Code. Bitte im Slicer „Druckplatte geslict exportieren“ (Export plate sliced file) verwenden.")));
    } else {
      opts.plate = sliced[0].index;
      const plates = el("div", { class: "plates" });
      for (const pl of info.plates) {
        const node = el("div", { class: `plate${pl.sliced ? "" : " disabled"}${pl.index === opts.plate ? " active" : ""}` },
          pl.thumb ? el("img", { src: `api/uploads/${info.token}/thumb/${pl.index}`, alt: "" }) : null,
          el("div", {}, t("Platte {0}", pl.index)),
          pl.prediction_s ? el("div", { class: "note" }, fmtDuration(pl.prediction_s)) : null);
        if (pl.sliced) node.addEventListener("click", () => {
          opts.plate = pl.index;
          $$(".plate", plates).forEach((n) => n.classList.remove("active"));
          node.classList.add("active");
          renderMapping();
        });
        plates.append(node);
      }
      content.append(el("div", { class: "note" }, t("Platte wählen")), plates);
      mappingBox = el("div", { class: "mapping" });
      content.append(mappingBox);
    }
  }

  function renderMapping() {
    if (!mappingBox) return;
    mappingBox.innerHTML = "";
    opts.ams_map = {};
    const plate = info.plates.find((pl) => pl.index === opts.plate);
    if (!opts.use_ams || !plate?.filaments.length) return;
    const slots = p.filaments;
    mappingBox.append(el("div", { class: "note" }, t("Filament-Zuordnung (Slicer → AMS-Slot)")));
    for (const f of plate.filaments) {
      // default: same slot number, or the first slot with matching type
      let def = slots.find((s) => s.slot === f.id && s.type === f.type) || slots.find((s) => s.type === f.type && s.color?.toLowerCase() === f.color?.slice(0, 7).toLowerCase()) || slots.find((s) => s.type === f.type) || slots[f.id - 1];
      const sel = el("select", {}, slots.map((s) => el("option", { value: s.slot === "Ext" ? "ext" : s.slot, selected: def === s }, `${s.slot === "Ext" ? t("Extern") : t("Slot ") + s.slot}: ${s.type || t("leer")}`)));
      opts.ams_map[f.id] = sel.value;
      sel.addEventListener("change", () => { opts.ams_map[f.id] = sel.value; });
      mappingBox.append(el("div", { class: "map-row" },
        el("span", { class: "swatch", style: `background:${f.color || "transparent"}` }),
        el("span", {}, `${f.id}: ${f.type || "?"}${f.used_g ? ` (${Math.round(f.used_g)} g)` : ""}`), "→", sel));
    }
  }

  // AMS options only if the printer has an AMS ("AMS vorhanden"; older settings: not set = show)
  const hasAms = p.has_ams !== false && (p.has_ams || p.filaments.some((f) => /^\d+$/.test(String(f.slot))));
  if (!hasAms) opts.use_ams = false;
  if (p.type === "bambu" && info.kind === "3mf") {
    const check = (label, key) => {
      const cb = el("input", { type: "checkbox", checked: opts[key] });
      cb.addEventListener("change", () => { opts[key] = cb.checked; if (key === "use_ams") renderMapping(); });
      return el("label", { class: "check" }, cb, label);
    };
    content.append(el("div", { class: "fields" },
      hasAms ? check(t("AMS verwenden"), "use_ams") : null, check(t("Bett nivellieren"), "bed_leveling"), check(t("Zeitraffer"), "timelapse")));
    renderMapping();
  }

  if (ACTIVE.includes(p.state)) content.append(el("div", { class: "alert warn" }, t("{0} druckt gerade. Du kannst die Datei nur hochladen.", p.name)));
  if (p.control === "monitor") content.append(el("div", { class: "note" }, t("Nur Überwachung eingestellt: Die Datei wird auf den Drucker geladen. Starten kannst du sie in Bambu Studio oder der Bambu Handy App.")));

  const send = async (start, btn) => {
    btn.disabled = true;
    try {
      const res = await api(`api/printers/${p.id}/print`, { method: "POST", json: { token: info.token, start, ...opts } });
      toast(res.message, "ok");
      dlg.close();
    } catch (err) {
      toast(err.message, "bad");
      btn.disabled = false;
    }
  };
  const canPrint = p.control !== "monitor" && !(info.kind === "3mf" && !info.plates.some((pl) => pl.sliced));
  content.append(el("div", { class: "dialog-actions" },
    el("button", { class: "btn", type: "button", onclick: (e) => send(false, e.currentTarget) }, t("Nur hochladen")),
    el("button", { class: "btn primary", type: "button", disabled: !canPrint || ACTIVE.includes(p.state), onclick: (e) => send(true, e.currentTarget) }, t("Hochladen & drucken"))));
}

/* ---------- cameras view ---------- */
let camerasKey = "";
function camerasStateKey() {
  return (lastState?.cameras || []).map((cam) => cam.id + ":" +
    camPausedText(lastState.printers.find((p) => p.id === cam.printer_id), cam.id)).join("|");
}
function renderCameras() {
  camerasKey = camerasStateKey();
  const grid = $("#camera-grid");
  detachCameras(grid);
  grid.innerHTML = "";
  const cams = lastState?.cameras || [];
  $("#empty-cameras").hidden = cams.length > 0;
  for (const cam of cams) {
    const box = el("div", { class: "cam" });
    box.addEventListener("click", () => openCamOverlay(cam.id, cam.name));
    const printer = lastState.printers.find((p) => p.id === cam.printer_id);
    grid.append(el("div", { class: "cam-tile" }, box,
      el("div", { class: "label" }, el("strong", {}, cam.name),
        printer && printer.name !== cam.name ? el("span", {}, printer.name) : null)));
    showCamera(box, printer, cam.id);
  }
}

/* ---------- history ---------- */
async function loadHistory() {
  const filter = $("#history-filter");
  const selected = filter.value;
  filter.innerHTML = "";
  filter.append(el("option", { value: "" }, t("Alle Drucker")));
  for (const p of lastState?.printers || []) filter.append(el("option", { value: p.id, selected: p.id === selected }, p.name));
  let jobs = [];
  try {
    jobs = await api(`api/history${filter.value ? `?printer_id=${encodeURIComponent(filter.value)}` : ""}`);
  } catch (e) { toast(e.message, "bad"); }

  $("#history-csv").href = `api/history.csv?lang=${LANG}${filter.value ? `&printer_id=${encodeURIComponent(filter.value)}` : ""}`;
  const done = jobs.filter((j) => j.status !== "running");
  const ok = done.filter((j) => j.status === "finished").length;
  const failed = done.filter((j) => j.status === "failed").length;
  const total = done.reduce((s, j) => s + (j.duration_s || 0), 0);
  const grams = done.reduce((s, j) => s + (j.filament_g || 0), 0);
  const money = done.reduce((s, j) => s + (j.cost || 0), 0);
  const stats = $("#history-stats");
  stats.innerHTML = "";
  const stat = (v, l) => el("div", { class: "stat" }, el("b", {}, v), el("span", {}, l));
  stats.append(stat(done.length, t("Drucke")), stat(done.length ? `${Math.round((ok / done.length) * 100)} %` : "–", t("erfolgreich")),
    stat(failed, t("fehlgeschlagen")), stat(fmtDuration(total), t("Druckzeit")),
    stat(grams >= 1000 ? `${(grams / 1000).toFixed(2)} kg` : `${Math.round(grams)} g`, t("Filament")),
    ...(money ? [stat(fmtCost(money), t("Filamentkosten"))] : []));

  const list = $("#history-list");
  list.innerHTML = "";
  if (!jobs.length) list.append(el("div", { class: "empty" }, t("Noch keine Drucke aufgezeichnet.")));
  for (const j of jobs) {
    const thumb = el("div", { class: "thumb" });
    if (j.preview) {
      const psrc = `api/history/${j.id}/preview`;
      thumb.append(el("img", { class: "preview", src: psrc, loading: "lazy", alt: "", title: t("Vorschau"),
        onclick: () => openImageOverlay(psrc, j.filename || "") }));
    }
    if (j.snapshot) {
      const src = `api/history/${j.id}/snapshot.jpg`;
      thumb.append(el("img", { src, loading: "lazy", alt: "", onclick: () => openImageOverlay(src, j.filename || "") }));
    }
    list.append(el("div", { class: "job" },
      thumb,
      el("div", {},
        el("div", { class: "title", title: j.filename || "" }, j.filename || t("Unbekannte Datei")),
        el("div", { class: "sub" }, [`${j.printer_name}`, fmtDate(j.started_at),
          j.status === "running" ? t("läuft seit ") + fmtDuration(Date.now() / 1000 - j.started_at) : fmtDuration(j.duration_s),
          fmtFilament(j.filament_g, j.filament_m, j.cost)].filter(Boolean).join(" · ")),
        j.materials?.length > 1 ? el("div", { class: "sub" }, fmtMaterials(j.materials)) : null,
        j.deducted?.length ? el("div", { class: "sub" }, t("🧵 abgezogen: {0}",
          j.deducted.map((d) => t("{0} {1} g (noch {2} g)", d.label, Math.round(d.g), Math.round(d.left))).join(", "))) : null,
        j.error ? el("div", { class: "err" }, j.error) : null),
      el("div", { class: "right" },
        el("span", { class: `badge ${j.status === "running" ? "printing" : j.status}` }, STATE_LABEL[j.status] || j.status),
        el("button", {
          class: "icon-btn", title: t("Eintrag löschen"), "aria-label": t("Eintrag löschen"),
          onclick: async () => {
            if (!confirm(t("Eintrag löschen?"))) return;
            await api(`api/history/${j.id}`, { method: "DELETE" });
            loadHistory();
          },
        }, "🗑"))));
  }
}
$("#history-filter").addEventListener("change", () => { loadHistory(); if (!$("#history-statpanel").hidden) loadStats(); });

/* statistics: per month, printer and material (all prints, not only the last 300) */
$("#history-stats-btn").addEventListener("click", () => {
  const panel = $("#history-statpanel");
  panel.hidden = !panel.hidden;
  if (!panel.hidden) loadStats();
});
async function loadStats() {
  const panel = $("#history-statpanel");
  const pid = $("#history-filter").value;
  let jobs = [];
  try { jobs = await api(`api/history?limit=10000000${pid ? `&printer_id=${encodeURIComponent(pid)}` : ""}`); }
  catch (e) { toast(e.message, "bad"); return; }
  jobs = jobs.filter((j) => j.status !== "running");
  if (!jobs.length) { panel.replaceChildren(el("p", { class: "note" }, t("Noch keine Drucke aufgezeichnet."))); return; }
  const add = (map, key, j, label) => {
    const r = map.get(key) || { label: label ?? key, n: 0, ok: 0, s: 0, g: 0, cost: 0 };
    r.n++; if (j.status === "finished") r.ok++;
    r.s += j.duration_s || 0; r.g += j.filament_g || 0; r.cost += j.cost || 0;
    map.set(key, r);
  };
  // last 12 months
  const months = new Map();
  const now = new Date();
  for (let i = 11; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    months.set(key, { label: d.toLocaleDateString(LOCALE, { month: "short", year: "2-digit" }), n: 0, ok: 0, s: 0, g: 0, cost: 0 });
  }
  const printers = new Map();
  const materials = new Map();
  for (const j of jobs) {
    const d = new Date(j.started_at * 1000);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    if (months.has(key)) add(months, key, j);
    add(printers, j.printer_id, j, j.printer_name);
    for (const m of j.materials || []) {
      const r = materials.get(m.type) || { label: m.type, g: 0, n: 0 };
      r.g += m.g || 0; r.n++;
      materials.set(m.type, r);
    }
  }
  const maxS = Math.max(1, ...[...months.values()].map((m) => m.s));
  const hours = (s) => `${(s / 3600).toFixed(s >= 36000 ? 0 : 1)} h`;
  const grams = (g) => (g >= 1000 ? `${(g / 1000).toFixed(2)} kg` : `${Math.round(g)} g`);
  const bars = el("div", { class: "month-bars" }, [...months.values()].map((m) => el("div", { class: "month",
    title: `${m.label}: ${tn(m.n, "{0} Druck", "{0} Drucke")}, ${hours(m.s)}, ${grams(m.g)}${m.cost ? ", " + fmtCost(m.cost) : ""}` },
    el("span", { class: "val" }, m.s ? hours(m.s) : ""),
    el("div", { class: "col" }, el("div", { class: "fill", style: `height:${(m.s / maxS) * 100}%` })),
    el("span", { class: "lbl" }, m.label))));
  const table = (head, rows) => el("table", { class: "stat-table" },
    el("thead", {}, el("tr", {}, head.map((h) => el("th", {}, h)))),
    el("tbody", {}, rows.map((r) => el("tr", {}, r.map((c) => el("td", {}, c))))));
  const prRows = [...printers.values()].sort((a, b) => b.s - a.s).map((r) => [r.label, String(r.n),
    `${Math.round((r.ok / r.n) * 100)} %`, hours(r.s), grams(r.g), r.cost ? fmtCost(r.cost) : "–"]);
  const totalG = [...materials.values()].reduce((s, m) => s + m.g, 0) || 1;
  const matRows = [...materials.values()].sort((a, b) => b.g - a.g).map((m) => [m.label, grams(m.g),
    `${Math.round((m.g / totalG) * 100)} %`, m.g ? fmtCost(m.g / 1000 * priceFor(m.label)) : "–"]);
  panel.replaceChildren(
    el("h4", { class: "sub-head" }, t("Druckzeit pro Monat")), bars,
    el("div", { class: "stat-grid" },
      el("div", {}, el("h4", { class: "sub-head" }, t("Pro Drucker")),
        table([t("Drucker"), t("Drucke"), t("erfolgreich"), t("Druckzeit"), t("Filament"), t("Kosten")], prRows)),
      matRows.length ? el("div", {}, el("h4", { class: "sub-head" }, t("Pro Material")),
        table([t("Material"), t("Menge"), t("Anteil"), t("Kosten (heutige Preise)")], matRows)) : null));
}

/* ---------- settings ---------- */
let draft = null;
let haServices = null;
let haEntities = { available: false, entities: [] };

async function loadSettings() {
  try {
    draft = await api("api/config");
    if (haServices === null) haServices = await api("api/notify/services").catch(() => ({ available: false, services: [] }));
    haEntities = await api("api/ha/entities").catch(() => ({ available: false, entities: [] }));
  } catch (e) { toast(e.message, "bad"); return; }
  renderSettings();
}

function field(label, obj, key, { type = "text", placeholder = "", hint = "", wide = false, options = null, onchange = null } = {}) {
  let input;
  if (type === "checkbox") {
    input = el("input", { type: "checkbox", checked: !!obj[key] });
    input.addEventListener("change", () => { obj[key] = input.checked; onchange?.(); });
    if (hint) return el("div", { class: "field wide" }, el("label", { class: "check" }, input, label), el("small", {}, hint));
    return el("label", { class: `check${wide ? " field wide" : ""}` }, input, label);
  }
  if (options) {
    input = el("select", {}, options.map(([v, l]) => el("option", { value: v, selected: String(obj[key] ?? "") === String(v) }, l)));
  } else {
    input = el("input", { type, placeholder, value: obj[key] ?? "", autocomplete: "off" });
  }
  input.addEventListener("input", () => { obj[key] = type === "number" ? Number(input.value) : input.value; });
  input.addEventListener("change", () => { obj[key] = type === "number" ? Number(input.value) : input.value; onchange?.(); });
  return el("label", { class: `field${wide ? " wide" : ""}` }, label, input, hint ? el("small", {}, hint) : null);
}

function renderSettings() {
  const root = $("#settings");
  root.innerHTML = "";

  /* printers */
  const pSec = el("div", { class: "settings-section" },
    el("h3", {}, t("Drucker|Abschnitt")),
    el("p", { class: "hint" }, t("Die Drucker werden direkt im Netzwerk angesprochen. Home-Assistant-Integrationen werden nicht benötigt.")));
  for (const p of draft.printers) pSec.append(printerItem(p));
  pSec.append(el("div", { class: "row-btns" },
    el("button", { class: "btn", onclick: () => { draft.printers.push({ id: "", type: "bambu", name: "Bambu Lab", host: "", serial: "", access_code: "", camera: true }); renderSettings(); } }, "+ Bambu Lab"),
    el("button", { class: "btn", onclick: () => { draft.printers.push({ id: "", type: "moonraker", name: "Klipper", url: "", api_key: "", light_object: "", light_on_gcode: "", light_off_gcode: "", camera_url: "" }); renderSettings(); } }, "+ Klipper / Moonraker")));
  root.append(pSec);

  /* cameras */
  const cSec = el("div", { class: "settings-section" },
    el("h3", {}, t("Externe Kameras")),
    el("p", { class: "hint" }, t("RTSP-, RTSPS- oder MJPEG-Kameras. Ordnest du eine Kamera einem Drucker zu, erscheint sie zusätzlich auf dessen Karte und wird für Benachrichtigungsbilder verwendet.")));
  const printerOptions = [["", t("– keinem Drucker –")], ...draft.printers.filter((p) => p.id).map((p) => [p.id, p.name])];
  for (const cam of draft.cameras) {
    cSec.append(el("div", { class: "item" },
      el("div", { class: "item-head" }, el("span", {}, cam.name || t("Kamera")),
        el("button", { class: "btn danger", onclick: () => { draft.cameras.splice(draft.cameras.indexOf(cam), 1); renderSettings(); } }, t("Entfernen"))),
      el("div", { class: "fields" },
        field(t("Name"), cam, "name"),
        field(t("Stream-URL"), cam, "url", { placeholder: "rtsp://benutzer:passwort@192.168.1.50:554/stream1", wide: true }),
        field(t("Drucker"), cam, "printer_id", { options: printerOptions }),
        field(t("Einzelbild-URL (JPEG) statt Stream"), cam, "snapshot", { type: "checkbox" }))));
  }
  cSec.append(el("div", { class: "row-btns" },
    el("button", { class: "btn", onclick: () => { draft.cameras.push({ id: "", name: "Kamera", url: "", printer_id: "", snapshot: false }); renderSettings(); } }, t("+ Kamera"))));
  root.append(cSec);

  /* notifications */
  const n = draft.notify;
  const nSec = el("div", { class: "settings-section" }, el("h3", {}, t("Benachrichtigungen")),
    el("p", { class: "hint" }, t("Mit Kamerabild, über einen notify-Dienst von Home Assistant (z. B. die Companion-App).")));
  nSec.append(el("div", { class: "fields" },
    field(t("Bei Fehlern und Warnungen"), n, "on_error", { type: "checkbox" }),
    field(t("Wenn ein Druck fertig ist"), n, "on_finish", { type: "checkbox" }),
    field(t("Wenn ein Druck abgebrochen wird"), n, "on_cancel", { type: "checkbox" }),
    field(t("Wenn ein Trockner fertig ist"), n, "on_dryer", { type: "checkbox" }),
    field(t("Wenn Filament knapp wird"), n, "on_low_filament", { type: "checkbox" }),
    field(t("Wenn eine Wartung fällig ist"), n, "on_maintenance", { type: "checkbox" }),
    field(t("Wenn ein Druck pausiert"), n, "on_pause", { type: "checkbox" }),
    field(t("Kamerabild anhängen"), n, "with_snapshot", { type: "checkbox" })));
  const haFields = el("div", { class: "fields", style: "margin-top:12px" });
  if (haServices?.available) {
    const opts = [["", t("– aus –")], ...haServices.services.map((s) => [s, `notify.${s}`])];
    if (n.ha_service && !haServices.services.includes(n.ha_service)) opts.push([n.ha_service, `notify.${n.ha_service}`]);
    haFields.append(field(t("Home Assistant App"), n, "ha_service", { options: opts, hint: t("z. B. notify.mobile_app_dein_handy") }));
  } else {
    haFields.append(field(t("Home Assistant notify-Dienst"), n, "ha_service", { placeholder: "mobile_app_dein_handy", hint: t("Nur als HA-Add-on oder mit HA_URL/HA_TOKEN verfügbar") }));
  }
  nSec.append(haFields, el("div", { class: "row-btns" },
    el("button", { class: "btn", onclick: async (e) => {
      e.currentTarget.disabled = true;
      try { await saveSettings(false); await api("api/notify/test", { method: "POST" }); toast(t("Testbenachrichtigung gesendet"), "ok"); }
      catch (err) { toast(err.message, "bad"); }
      finally { e.target.disabled = false; }
    } }, t("Speichern & Test senden"))));
  root.append(nSec);

  /* general */
  root.append(filamentSettings());
  root.append(priceSection());
  const g = el("div", { class: "settings-section" }, el("h3", {}, t("Allgemein")),
    el("div", { class: "fields" },
      field(t("Kamera-Bilder pro Sekunde"), draft.camera, "fps", { type: "number" }),
      field(t("Kamera max. Breite (px)"), draft.camera, "width", { type: "number" }),
      field(t("Passwort für direkten Zugriff"), draft.ui, "password", { type: "password", placeholder: t("leer = kein Passwort"), hint: t("Mind. 6 Zeichen. Gilt für den direkten Zugriff über http://<ip>:<port> – dort erscheint dann eine Anmeldeseite (30 Tage angemeldet bleiben). Über die HA-Seitenleiste schützt bereits der HA-Login.") }),
      field("Sprache / Language", draft.ui, "language", { options: [["", t("Automatisch (Browsersprache)")],
        ...Object.entries(LANGUAGES)], hint: t("Gilt auch für Benachrichtigungen.") }),
      field(t("Systemauslastung unten in der Übersicht anzeigen"), draft.ui, "show_system", { type: "checkbox",
        hint: t("CPU, RAM, freier Speicher und Temperaturen des Rechners, auf dem 3D-PrintDash läuft.") })));
  root.append(g);
  root.append(backupSection());

  if (lastState?.auth?.enabled && !lastState?.auth?.ingress) {
    g.append(el("div", { class: "row-btns" }, el("button", { class: "btn", onclick: async () => {
      await fetch("api/logout", { method: "POST" });
      location.href = "login";
    } }, t("Abmelden"))));
  }
  root.append(el("div", { class: "savebar" },
    el("button", { class: "btn primary", onclick: () => saveSettings(true) }, t("Speichern")),
    el("span", { class: "note" }, t("Beim Speichern werden alle Verbindungen neu aufgebaut."))));
}

/* backup, restore, import from another installation */
function backupSection() {
  const KEY = { access_code: t("LAN-Zugangscode"), api_key: "API-Key", host: t("IP-Adresse"), serial: t("Seriennummer"),
    url: "URL", camera_url: t("Kamera-URL (optional)") };
  const done = (r) => {
    let msg = t("Übernommen: {0} Drucker, {1} Spulen, {2} Drucke.", r.printers, r.spools, r.jobs);
    if (r.todo?.length) {
      msg += "\n\n" + t("Bitte in den Einstellungen neu eintragen:") + "\n" +
        r.todo.map((x) => { const [n, k] = x.split(": "); return `• ${n}: ${KEY[k] || k}`; }).join("\n");
    }
    alert(msg);
    location.reload();
  };
  const ask = () => confirm(t("Alle aktuellen Daten (Einstellungen, Filament, Historie) werden ersetzt. Der jetzige Stand wird vorher automatisch gesichert. Fortfahren?"));
  const file = el("input", { type: "file", accept: ".zip,application/zip", hidden: true });
  file.addEventListener("change", async () => {
    const f = file.files[0];
    file.value = "";
    if (!f || !ask()) return;
    const fd = new FormData();
    fd.append("file", f);
    toast(t("Wird wiederhergestellt …"));
    try {
      const r = await fetch("api/backup/restore", { method: "POST", body: fd, headers: { "X-PF-Lang": LANG } });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.detail || t("Fehler {0}", r.status));
      done(d);
    } catch (e) { toast(e.message, "bad"); }
  });
  const imp = { url: "", password: "" };
  const impBtn = el("button", { class: "btn", type: "button", onclick: async () => {
    if (!imp.url.trim()) { toast(t("Bitte die Adresse der anderen Installation angeben"), "bad"); return; }
    if (!ask()) return;
    impBtn.disabled = true;
    toast(t("Daten werden geholt, das kann einen Moment dauern …"));
    try { done(await api("api/backup/import", { method: "POST", json: imp })); }
    catch (e) { toast(e.message, "bad"); }
    finally { impBtn.disabled = false; }
  } }, t("Übernehmen"));
  return el("div", { class: "settings-section" },
    el("h3", {}, t("Datensicherung")),
    el("p", { class: "hint" }, t("Sichert Einstellungen, Filamentbestand, Wartung und Historie mit Bildern in eine Zip-Datei. Die Datei enthält auch Zugangscodes, bitte sicher aufbewahren.")),
    el("div", { class: "row-btns" },
      el("a", { class: "btn primary", href: "api/backup", download: "" }, t("Backup herunterladen")),
      el("button", { class: "btn", type: "button", onclick: () => file.click() }, t("Backup wiederherstellen …")), file),
    el("h4", { class: "sub-head", style: "margin-top:18px" }, t("Von anderer Installation übernehmen")),
    el("p", { class: "hint" }, t("Holt alle Daten direkt von einer laufenden Installation, z. B. einer älteren Version. Zugangscodes werden dabei nicht übertragen und müssen danach neu eingetragen werden.")),
    el("div", { class: "fields" },
      field(t("Adresse"), imp, "url", { placeholder: "http://192.168.1.10:8090", hint: t("Direkter Zugriff mit Port, nicht über die HA-Seitenleiste") }),
      field(t("Passwort"), imp, "password", { type: "password", placeholder: t("falls gesetzt") })),
    el("div", { class: "row-btns" }, impBtn));
}

function filamentSettings() {
  const f = draft.filament = draft.filament || { deduct_usage: false, low_warn_g: 100 };
  return el("div", { class: "settings-section" },
    el("h3", {}, t("Filament")),
    el("div", { class: "fields" },
      field(t("Verbrauch nach jedem Druck vom Bestand abziehen"), f, "deduct_usage", { type: "checkbox",
        hint: t("Zieht die Gramm laut Slicer von den Spulen ab, die während des Drucks aktiv waren (bei Abbruch anteilig). Eine neue Spule wird dabei zu „angefangen“. Funktioniert nur für Spulen, die im Bestand erfasst und im Drucker erkannt sind.") }),
      field(t("Als knapp markieren unter (g)"), f, "low_warn_g", { type: "number", placeholder: "100",
        hint: t("Angefangene Spulen mit weniger Restgewicht werden im Bestand markiert. 0 = aus.") })));
}

function priceSection() {
  const c = draft.costs = draft.costs || {};
  if (c.default_price_per_kg === undefined) c.default_price_per_kg = c.filament_price_per_kg ?? 25;
  c.currency = c.currency || "";   // "" = automatic from the browser's region
  if (!c.materials || typeof c.materials !== "object") {
    c.materials = { PLA: 25, PETG: 25, "PETG-CF": 40, ABS: 25, "ABS-CF": 45, ASA: 30, "ASA-CF": 45, TPU: 40 };
  }
  // edit as a list so names can be changed, then write back as an object
  const rows = Object.entries(c.materials).map(([name, price]) => ({ name, price }));
  const sync = () => {
    c.materials = {};
    for (const r of rows) if (r.name.trim()) c.materials[r.name.trim().toUpperCase()] = Number(r.price) || 0;
  };
  const list = el("div", { class: "price-list" });
  const render = () => {
    list.innerHTML = "";
    for (const r of rows) {
      const name = el("input", { value: r.name, placeholder: t("z. B. PA-CF"), "aria-label": t("Material") });
      const price = el("input", { type: "number", step: "0.5", min: "0", value: r.price, "aria-label": t("Preis pro kg") });
      name.addEventListener("input", () => { r.name = name.value; sync(); });
      price.addEventListener("input", () => { r.price = price.value; sync(); });
      list.append(el("div", { class: "price-row" }, name, price, el("span", { class: "note" }, `${c.currency || guessCurrency()}/kg`),
        el("button", { class: "icon-btn", title: t("Entfernen"), "aria-label": t("Entfernen"),
          onclick: () => { rows.splice(rows.indexOf(r), 1); sync(); render(); } }, "✕")));
    }
  };
  render();
  return el("div", { class: "settings-section" },
    el("h3", {}, t("Filamentpreise")),
    el("p", { class: "hint" }, t("Preis pro kg je Material. Varianten wie „PLA Basic“ oder „PETG HF“ zählen zum Grundmaterial, „PETG CF“ zu PETG-CF. Alles andere nutzt den Standardpreis. Die Kosten werden beim Druckende gespeichert.")),
    list,
    el("div", { class: "row-btns" },
      el("button", { class: "btn", onclick: () => { rows.push({ name: "", price: c.default_price_per_kg }); render(); $$("input", list).at(-2)?.focus(); } }, t("+ Material"))),
    el("div", { class: "fields", style: "margin-top:12px" },
      field(t("Standardpreis pro kg (andere Materialien)"), c, "default_price_per_kg", { type: "number" }),
      currencyField(c, render)));
}

// currency: automatic, a common one from the list, or any other text
function currencyField(c, onchange) {
  const OTHER = "__other__";
  const known = !c.currency || CURRENCIES.includes(c.currency);
  const sel = el("select", {},
    el("option", { value: "" }, t("Automatisch ({0})", guessCurrency())),
    CURRENCIES.map((x) => el("option", { value: x }, x)),
    el("option", { value: OTHER }, t("Andere …")));
  sel.value = known ? c.currency : OTHER;
  const txt = el("input", { value: known ? "" : c.currency, placeholder: t("z. B. HUF oder Fr."), maxlength: "8", hidden: known });
  const example = el("small", {});
  const upd = () => { example.textContent = `${t("Beispiel")}: ${fmtMoney(12.5, c.currency)}`; onchange?.(); };
  sel.addEventListener("change", () => {
    txt.hidden = sel.value !== OTHER;
    c.currency = sel.value === OTHER ? txt.value.trim() : sel.value;
    if (sel.value === OTHER) txt.focus();
    upd();
  });
  txt.addEventListener("input", () => { c.currency = txt.value.trim(); upd(); });
  example.textContent = `${t("Beispiel")}: ${fmtMoney(12.5, c.currency)}`;
  return el("label", { class: "field" }, t("Währung"), el("div", { class: "pick-or-type" }, sel, txt), example);
}

let haBambu = null;

function bambuControlFields(p) {
  p.ha_entities = p.ha_entities || {};
  const box = el("div", { class: "fields", style: "margin-top:12px" });
  const wrap = el("div", {}, box);
  const LABELS = { pause: t("Pause-Knopf"), resume: t("Fortsetzen-Knopf"), stop: t("Stopp-Knopf"), light: t("Kammerlicht") };
  const render = () => {
    box.innerHTML = "";
    const imgs = haBambu?.images || [];
    const coverOpts = [["", t("Automatisch{0}", imgs.length ? ` (${(imgs.find((i) => i.cover) || imgs[0]).entity_id})` : "")], ["off", t("Aus")],
      ...imgs.map((i) => [i.entity_id, `${i.name} (${i.entity_id})`])];
    if (p.ha_cover && !coverOpts.some(([v]) => v === p.ha_cover)) coverOpts.push([p.ha_cover, p.ha_cover]);
    box.append(field(t("Vorschaubild-Ersatz aus HA"), p, "ha_cover", { options: coverOpts,
      hint: t("Titelbild der Bambu-Integration, falls der Drucker keins liefert") }));
    box.append(field(t("Steuerung (Pause, Stopp, Licht)"), p, "control", {
      options: [["monitor", t("Nur überwachen (Steuerung über Bambu Handy/Studio)")], ["direct", t("Direkt – nur mit Developer Mode")], ["ha", t("Über Home Assistant (Bambu-Integration)")]],
      onchange: render,
    }));
    if (p.control !== "ha") return;
    if (!haBambu?.available) {
      box.append(el("p", { class: "note field wide" }, haBambu?.error || t("Home Assistant nicht verbunden.")));
      return;
    }
    const guess = haBambu.guess || {};
    for (const key of ["pause", "resume", "stop", "light"]) {
      const list = key === "light" ? (haBambu.lights || []) : (haBambu.buttons || []);
      if (key === "light" && !p.ha_entities.light) p.ha_entities.light = "direct";
      if (!p.ha_entities[key] && guess[key]) p.ha_entities[key] = guess[key];
      // free text with suggestions: any entity id can be typed in
      const listId = `dl-${p.id || "new"}-${key}`;
      const dl = el("datalist", { id: listId },
        key === "light" ? el("option", { value: "direct" }, t("Direkt über den Drucker (wie bisher)")) : null,
        list.map((c) => el("option", { value: c.entity_id }, c.name)));
      const input = el("input", { list: listId, value: p.ha_entities[key] || "", autocomplete: "off",
        placeholder: key === "light" ? t("direct oder light.…") : t("button.…") });
      input.addEventListener("input", () => { p.ha_entities[key] = input.value.trim(); });
      box.append(el("label", { class: "field" }, LABELS[key], input, dl,
        el("small", {}, key === "light" ? t("„direct“ = direkt über den Drucker") : t("Entitäts-ID aus Home Assistant"))));
    }
    if (!(haBambu.buttons || []).length) {
      box.append(el("p", { class: "note field wide" }, t("Keine Knöpfe der Bambu-Integration automatisch gefunden. Trag die Entitäts-IDs von Hand ein (Einstellungen → Geräte & Dienste → Bambu Lab → Entitäten). Deaktivierte Knöpfe musst du dort zuerst aktivieren.")));
    }
  };
  p.control = p.control || "monitor";
  if (haBambu === null) {
    api("api/ha/bambu").then((r) => { haBambu = r; render(); }).catch(() => { haBambu = { available: false }; render(); });
  }
  render();
  return wrap;
}

function amsSensorFields(p) {
  const wrap = el("div", { class: "ams-box" });
  if (!p.ams_source) p.ams_source = (p.ams_temp_entity || p.ams_hum_entity || p.ams_bat_entity) ? "ha" : "ams";
  const render = () => {
    const opt = (list, cur) => {
      const o = [["", t("– keiner –")], ...list.map((x) => [x.entity_id, `${x.name}${x.state != null ? ` (${x.state}${x.unit ? " " + x.unit : ""})` : ""}`])];
      if (cur && !o.some(([v]) => v === cur)) o.push([cur, cur]);
      return o;
    };
    const fields = el("div", { class: "fields" },
      field(t("Quelle"), p, "ams_source", {
        options: [["ams", t("Werte vom AMS selbst")], ["ha", t("Eigener Sensor (Home Assistant)")]], onchange: render }));
    if (p.ams_source === "ha") {
      fields.append(
        field(t("Temperatur"), p, "ams_temp_entity", { options: opt(climate?.temperature || [], p.ams_temp_entity) }),
        field(t("Luftfeuchtigkeit"), p, "ams_hum_entity", { options: opt(climate?.humidity || [], p.ams_hum_entity) }),
        field(t("Batterie"), p, "ams_bat_entity", { options: opt(climate?.battery || [], p.ams_bat_entity),
          hint: t("Listet auch andere %-Sensoren") }),
        field(t("Anzeigename"), p, "ams_sensor_name", { placeholder: "AMS" }));
    }
    fields.append(field(t("Warnung ab Feuchte (%)"), p, "ams_hum_max", { type: "number", placeholder: "30" }));
    const extra = [];
    if (p.ams_source === "ha") {
      if (!climate?.available) extra.push(el("p", { class: "note" }, t("Home Assistant nicht verbunden – Sensoren nicht verfügbar.")));
      extra.push(el("div", { class: "row-btns" }, el("button", { class: "btn", type: "button", onclick: async () => {
        try {
          const f = filData || await api("api/filament");
          const hasSensor = (l) => l.temp_entity || l.hum_entity || l.bat_entity;
          const loc = (f.locations || []).find((l) => l.printer_id === p.id && hasSensor(l))
            || (f.locations || []).find((l) => l.in_printer && hasSensor(l)) || (f.locations || []).find(hasSensor);
          if (!loc) { toast(t("Im Filament-Tab hat kein Lagerort Sensoren"), "bad"); return; }
          p.ams_temp_entity = loc.temp_entity || ""; p.ams_hum_entity = loc.hum_entity || ""; p.ams_bat_entity = loc.bat_entity || "";
          render(); toast(t("Übernommen – bitte unten speichern"), "ok");
        } catch (e) { toast(e.message, "bad"); }
      } }, t("Sensoren vom Filament-Tab übernehmen"))));
    }
    wrap.replaceChildren(el("h4", { class: "sub-head" }, t("AMS-Klima")), fields, ...extra);
  };
  if (climate === null) {
    api("api/ha/climate").then((r) => { climate = r; render(); }).catch(() => { climate = { available: false, temperature: [], humidity: [], battery: [] }; render(); });
  }
  render();
  return wrap;
}

function printerItem(p) {
  const remove = el("button", { class: "btn danger", onclick: () => {
    if (!confirm(t("„{0}“ entfernen?", p.name))) return;
    draft.printers.splice(draft.printers.indexOf(p), 1);
    renderSettings();
  } }, t("Entfernen"));
  const head = el("div", { class: "item-head" },
    el("span", {}, p.name || t("Drucker"), el("span", { class: "tag" }, p.type === "bambu" ? "Bambu Lab (LAN)" : "Klipper / Moonraker")), remove);
  const fields = el("div", { class: "fields" });
  const item = el("div", { class: "item" }, head, fields);
  // maintenance intervals (print hours / days, 0 = off)
  for (const [k, v] of [["maint_clean_h", 100], ["maint_clean_d", 0], ["maint_lube_h", 300], ["maint_lube_d", 0]]) {
    if (p[k] === undefined || p[k] === null || p[k] === "") p[k] = v;
  }
  const maintFields = () => [
    el("div", { class: "field wide" }, el("h4", { class: "sub-head" }, t("Wartung")),
      el("small", {}, t("Erinnerung nach Druckstunden und/oder Tagen seit dem letzten „Erledigt“. 0 = aus."))),
    field(t("Reinigen alle (Druckstunden)"), p, "maint_clean_h", { type: "number" }),
    field(t("Reinigen alle (Tage)"), p, "maint_clean_d", { type: "number" }),
    field(t("Schmieren alle (Druckstunden)"), p, "maint_lube_h", { type: "number" }),
    field(t("Schmieren alle (Tage)"), p, "maint_lube_d", { type: "number" }),
  ];
  const powerFields = () => {
    const opts = [["", t("– keine –")], ...haEntities.entities.map((e) => [e.entity_id, `${e.name} (${e.entity_id})`])];
    if (p.power_entity && !haEntities.entities.some((e) => e.entity_id === p.power_entity)) opts.push([p.power_entity, p.power_entity]);
    return [
      haEntities.available
        ? field(t("Steckdose (Home Assistant)"), p, "power_entity", { options: opts })
        : field(t("Steckdose (Home Assistant)"), p, "power_entity", { placeholder: "switch.drucker", hint: t("Home Assistant nicht verbunden") }),
      field(t("Nach Druckende ausschalten (Min.)"), p, "auto_off_minutes", { type: "number", placeholder: t("0 = nie"), hint: t("Erst wenn Düse und Bett unter 50 °C sind") }),
    ];
  };
  if (p.type === "bambu") {
    fields.append(
      field(t("Name"), p, "name"),
      field(t("IP-Adresse"), p, "host", { placeholder: "192.168.1.40" }),
      field(t("Seriennummer"), p, "serial", { placeholder: "00M00A000000000", hint: t("Am Drucker: Einstellungen → Gerät") }),
      field(t("LAN-Zugangscode"), p, "access_code", { type: "password", hint: t("Am Drucker: Einstellungen → Netzwerk (WLAN)") }),
      field(t("Eingebaute Kamera verwenden"), p, "camera", { type: "checkbox", hint: "" }),
      field(t("Kamera-Art"), p, "camera_type", { options: [["", t("Automatisch (nach Seriennummer)")],
        ["rtsp", t("Video-Stream (X1, H2)")], ["jpeg", t("Einzelbilder (P1, A1)")]] }),
      field(t("AMS vorhanden"), p, "has_ams", { type: "checkbox",
        hint: t("Legt im Filament-Tab einen Lagerort für dieses AMS an. Spulen, die beim Ausschalten des Druckers im AMS stecken, werden dorthin verschoben. Nimmst du eine Spule bei laufendem Drucker heraus, kommt sie an ihren alten Ort zurück.") }),
      ...powerFields(), ...maintFields());
    item.append(amsSensorFields(p));
    item.append(bambuControlFields(p));
    item.append(el("p", { class: "note" }, t("Für die Kamera muss am Drucker „LAN Only Liveview“ (Einstellungen → Netzwerk) eingeschaltet sein.")));
  } else {
    const result = el("span", { class: "probe-result" });
    const camInfo = el("div", { class: "probe-result", hidden: true, style: "margin-top:6px;word-break:break-all" });
    const lightOpts = [["", t("Automatisch")]];
    if (p.light_object) lightOpts.push([p.light_object, p.light_object]);
    const lightField = field(t("Licht (Klipper-Objekt)"), p, "light_object", { options: lightOpts });
    const chamberOpts = [["", t("Automatisch")], ["none", t("Keiner")]];
    if (p.chamber_sensor && p.chamber_sensor !== "none") chamberOpts.push([p.chamber_sensor, p.chamber_sensor]);
    const chamberField = field(t("Kammer-Temperatur"), p, "chamber_sensor", { options: chamberOpts });
    fields.append(
      field(t("Name"), p, "name"),
      field(t("Moonraker-URL"), p, "url", { placeholder: "http://192.168.1.41:7125" }),
      field("API-Key", p, "api_key", { type: "password", placeholder: t("meist leer") }),
      lightField,
      chamberField,
      field(t("Licht an: eigener G-Code"), p, "light_on_gcode", { placeholder: t("optional, z. B. LIGHT_ON") }),
      field(t("Licht aus: eigener G-Code"), p, "light_off_gcode", { placeholder: t("optional") }),
      ...powerFields(),
      field(t("Kamera-URL (optional)"), p, "camera_url", { placeholder: t("leer = automatisch von Moonraker"), wide: true }),
      ...maintFields());
    item.append(el("div", { class: "row-btns" },
      el("button", { class: "btn", onclick: async () => {
        result.className = "probe-result"; result.textContent = t("Teste …");
        const r = await api("api/probe/moonraker", { method: "POST", json: { id: p.id, url: p.url, api_key: p.api_key } }).catch((e) => ({ ok: false, error: e.message }));
        if (!r.ok) { result.className = "probe-result bad"; result.textContent = t("Nicht erreichbar: {0}", r.error); return; }
        result.className = "probe-result ok";
        result.textContent = t("{0}Verbunden: {1} ({2}) · {3} Extruder · {4} Kamera(s) · {5} Licht-Objekt(e)", r.auto_light ? t("Licht: {0} · ", r.auto_light) : "", r.hostname, r.state, r.extruders.length, r.cameras.length, r.lights.length);
        const cam = r.camera || {};
        const camText = cam.snapmaker
          ? t("Kamera: Snapmaker-Kamera aktiv – Bild: {0}", cam.image || "?")
          : t("Kamera: Snapmaker-Kamera nicht verfügbar ({0}). Moonraker-Webcams: {1}", cam.snapmaker_error || "?", cam.webcams?.length ? cam.webcams.map((w) => `${w.name} [${w.service}] ${w.stream_url || w.snapshot_url}`).join("; ") : t("keine"));
        camInfo.textContent = camText;
        camInfo.hidden = false;
        const sel = $("select", lightField);
        const current = p.light_object || "";
        sel.innerHTML = "";
        sel.append(el("option", { value: "" }, t("Automatisch")));
        for (const l of r.lights) sel.append(el("option", { value: l, selected: l === current }, l));
        if (!current && r.lights.length === 1) { sel.value = r.lights[0]; p.light_object = r.lights[0]; }
        const csel = $("select", chamberField);
        const ccur = p.chamber_sensor || "";
        csel.innerHTML = "";
        csel.append(el("option", { value: "" }, t("Automatisch{0}", r.auto_chamber ? ` (${r.auto_chamber})` : t(" (nichts gefunden)"))),
          el("option", { value: "none", selected: ccur === "none" }, t("Keiner")));
        for (const sn of r.sensors || []) csel.append(el("option", { value: sn, selected: sn === ccur }, sn));
      } }, t("Verbindung testen")), result), camInfo);
  }
  return item;
}

async function saveSettings(notifyUser) {
  try {
    draft = await api("api/config", { method: "PUT", json: draft });
    if (notifyUser) { toast(t("Gespeichert"), "ok"); renderSettings(); }
    lastState = await api("api/state");
    syncLanguage(lastState.language);
  } catch (e) {
    toast(e.message, "bad");
    throw e;
  }
}

/* ---------- start ---------- */
translateStatic();
const startView = location.hash.slice(1);
poll().then(() => showView(["overview", "cameras", "history", "filament", "settings"].includes(startView) ? startView : "overview"));


/* ---------- printer detail (full screen) ---------- */
let detail = null;

function openDetail(pid) {
  const p = lastState?.printers.find((x) => x.id === pid);
  if (!p) return;
  detachCameras($("#view-overview"));
  const root = $("#printer-detail");
  root.innerHTML = "";
  const d = {
    id: pid, node: el("div", {}), baseClass: "detail", noCams: true, camKey: null,
    title: el("h2", {}, p.name),
    badge: el("span", { class: "badge" }),
    file: el("div", { class: "file" }),
    thumb: el("img", { class: "job-thumb big", alt: "", hidden: true }),
    bar: el("div", { class: "bar" }),
    time: el("div", { class: "time-row" }),
    info: el("div", { class: "detail-info" }),
    temps: el("div", { class: "chips" }),
    fils: el("div", { class: "chips" }),
    alerts: el("div", {}),
    actions: el("div", { class: "actions" }),
    cams: el("div", { class: "detail-cams" }),
    jobs: el("div", { class: "detail-jobs" }),
    runningJob: null,
  };
  d.progress = el("div", { class: "progress" }, d.bar);
  const fsBtn = el("button", { class: "btn", onclick: () => {
    if (document.fullscreenElement) document.exitFullscreen();
    else root.requestFullscreen?.().catch(() => {});
  } }, t("⛶ Vollbild"));
  const section = (title, ...kids) => el("section", { class: "detail-sec" }, title ? el("h4", {}, title) : null, ...kids);
  d.node.append(
    el("header", { class: "detail-head" },
      el("button", { class: "btn", onclick: closeDetail }, t("← Übersicht")),
      d.title, d.badge, el("span", { class: "spacer" }), fsBtn,
      el("button", { class: "icon-btn", "aria-label": t("Schliessen"), onclick: closeDetail }, "✕")),
    el("div", { class: "detail-body" },
      d.cams,
      el("aside", { class: "detail-side" },
        section(null, el("div", { class: "file-row" }, d.thumb, d.file), d.progress, d.time, d.info, d.alerts),
        el("section", { class: "detail-sec" }, d.tempsHead = el("h4", {}, t("Temperaturen")), d.temps),
        d.filsSec = section(t("Filament"), d.fils),
        section(t("Steuerung"), d.actions),
        d.maintSec = section(t("Wartung"), d.maint = el("div", { class: "maint-list" })),
        section(t("Letzte Drucke"), d.jobs))),
  );
  root.append(d.node);
  root.hidden = false;
  document.body.classList.add("detail-open");
  detail = d;
  renderDetail();
  loadDetailJobs();
  d.jobTimer = setInterval(loadDetailJobs, 30000);
}

function closeDetail() {
  if (!detail) return;
  clearInterval(detail.jobTimer);
  const root = $("#printer-detail");
  const ov = $("#cam-overlay");
  if (root.contains(ov)) { closeOverlay(); document.body.append(ov); }
  detachCameras(root);
  root.hidden = true;
  root.innerHTML = "";
  document.body.classList.remove("detail-open");
  detail = null;
  if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
  showView(currentView);
}

function renderDetail() {
  const d = detail;
  const p = lastState?.printers.find((x) => x.id === d.id);
  if (!p) { closeDetail(); return; }
  d.title.textContent = p.name;
  updateCard(d, p);
  d.filsSec.hidden = !p.filaments.length;
  d.temps.hidden = false;
  // "AMS" only for printers that report AMS values (Bambu)
  d.tempsHead.textContent = (p.ams || []).length ? t("Temperaturen & AMS") : t("Temperaturen");
  if (!d.temps.childElementCount) d.temps.replaceChildren(el("span", { class: "note" }, "–"));

  // maintenance
  const tasks = p.maintenance || [];
  d.maintSec.hidden = !tasks.length;
  const mkey = JSON.stringify(tasks.map((m) => [m.id, m.progress, m.due]));
  if (d.maintKey !== mkey) {
    d.maintKey = mkey;
    d.maint.replaceChildren(...tasks.map((m) => {
      const parts = [];
      if (m.hours) parts.push(t("{0} / {1} h", Math.round(m.hours_since), m.hours));
      if (m.days) parts.push(t("{0} / {1} Tage", Math.floor(m.days_since), m.days));
      return el("div", { class: `maint${m.due ? " due" : ""}` },
        el("div", { class: "maint-head" }, el("b", {}, maintName(m.id)), el("span", { class: "note" }, parts.join(" · ")),
          el("span", { class: "spacer" }),
          el("button", { class: `btn mini${m.due ? " primary" : ""}`, onclick: async () => {
            if (!confirm(t("„{0}“ als erledigt markieren?", maintName(m.id)))) return;
            try {
              const r = await api(`api/maintenance/${p.id}/${m.id}/done`, { method: "POST" });
              lastState.printers.find((x) => x.id === p.id).maintenance = r.maintenance;
              toast(t("Gespeichert"), "ok"); renderDetail();
            } catch (e) { toast(e.message, "bad"); }
          } }, t("Erledigt"))),
        el("div", { class: "progress" }, el("div", { class: "bar", style: `width:${Math.min(100, m.progress * 100)}%` })),
        el("div", { class: "note" }, t("Zuletzt erledigt: {0}", fmtDate(m.done_at))));
    }));
  }

  // extra info lines
  const rows = [];
  const job = d.runningJob;
  if (ACTIVE.includes(p.state) && job) {
    rows.push([t("Gestartet"), fmtDate(job.started_at)], [t("Läuft seit"), fmtDuration(Date.now() / 1000 - job.started_at)]);
  } else if (p.elapsed_s && ACTIVE.includes(p.state)) {
    rows.push([t("Läuft seit"), fmtDuration(p.elapsed_s)]);
  }
  if (p.job?.weight_g || p.job?.length_m) rows.push([t("Filament (Druck)"), fmtFilament(p.job.weight_g, p.job.length_m, p.job.cost)]);
  if (p.job?.materials?.length) rows.push([t("Materialien"), fmtMaterials(p.job.materials)]);
  if (p.power) rows.push([t("Steckdose"), p.power.on ? t("ein") : p.power.on === false ? t("aus") : t("unbekannt")]);
  if (p.model) rows.push([t("Modell"), p.model]);
  for (const v of p.versions || []) rows.push([t(v.label), v.value]);
  rows.push([t("Verbindung"), p.online ? "online" : "offline"]);
  d.info.replaceChildren(...rows.map(([k, v]) => el("div", {}, el("span", {}, k), el("b", {}, v))));

  // cameras: all of them large
  const key = p.cameras.join("|") + "|" + camPausedText(p, p.cameras[0]);
  if (key !== d.camKey) {
    d.camKey = key;
    detachCameras(d.cams);
    d.cams.innerHTML = "";
    d.cams.dataset.count = String(Math.min(p.cameras.length, 4));
    if (!p.cameras.length) d.cams.append(el("div", { class: "cam" }, el("div", { class: "cam-msg" }, t("Keine Kamera"))));
    for (const id of p.cameras) {
      const info = lastState.cameras.find((x) => x.id === id);
      const tile = el("div", { class: "cam" });
      tile.addEventListener("click", () => openCamOverlay(id, info?.name || p.name));
      d.cams.append(tile);
      showCamera(tile, p, id);
      tile.append(el("span", { class: "cam-label" }, info?.name || p.name));
    }
  }
}

async function loadDetailJobs() {
  const d = detail;
  if (!d) return;
  let jobs = [];
  try { jobs = await api(`api/history?printer_id=${encodeURIComponent(d.id)}&limit=6`); } catch { return; }
  if (detail !== d) return;
  d.runningJob = jobs.find((j) => j.status === "running") || null;
  const done = jobs.filter((j) => j.status !== "running").slice(0, 5);
  d.jobs.replaceChildren(...(done.length ? done.map((j) => el("div", { class: "mini-job" },
    j.snapshot ? el("img", { src: `api/history/${j.id}/snapshot.jpg`, alt: "", loading: "lazy",
      onclick: () => openImageOverlay(`api/history/${j.id}/snapshot.jpg`, j.filename || "") }) : el("div", { class: "noimg" }),
    el("div", {}, el("div", { class: "title", title: j.filename || "" }, j.filename || t("Unbekannt")),
      el("div", { class: "sub" }, `${fmtDate(j.started_at)} · ${fmtDuration(j.duration_s)}`)),
    el("span", { class: `badge ${j.status}` }, STATE_LABEL[j.status] || j.status)))
    : [el("div", { class: "note" }, t("Noch keine Drucke"))]));
}


/* ---------- filament inventory ---------- */
let filData = null;
let climate = null;
let filTimer = null;
const locs = () => filData?.locations || [];
const locById = (id) => locs().find((l) => l.id === id);
const locName = (l) => (l ? l.name || t("Filamentlager") : "");
// first location, or the first one marked "in the printer" (e.g. AMS)
const printerName = (id) => (lastState?.printers || []).find((p) => p.id === id)?.name || "?";
const firstLocId = (inPrinter = false) => ((inPrinter && locs().find((l) => l.in_printer)) || locs()[0])?.id;
const COND_LABEL = { neu: t("Neu"), angefangen: t("Angefangen") };

function priceFor(material) {
  const c = lastState?.costs || {};
  const prices = {};
  for (const [k, v] of Object.entries(c.materials || {})) prices[k.toUpperCase().replace(/[\s_/]+/g, "-")] = Number(v) || 0;
  const norm = String(material || "").toUpperCase().replace(/[\s_/]+/g, "-");
  if (norm in prices) return prices[norm];
  const base = norm.split("-")[0];
  if (/-(CF|GF)/.test(norm) && `${base}-CF` in prices) return prices[`${base}-CF`];
  return base in prices ? prices[base] : Number(c.default_price_per_kg) || 0;
}
function isLow(it) {
  const low = Number(lastState?.filament_low_g) || 0;
  return low > 0 && it.condition === "angefangen" && it.remaining_g != null && Number(it.remaining_g) < low;
}
function itemGrams(it) {
  const per = it.condition === "angefangen" && it.remaining_g != null ? Number(it.remaining_g) : Number(it.spool_g || 1000);
  return per * (Number(it.count) || 0);
}

async function loadFilament() {
  clearTimeout(filTimer);
  try {
    filData = await api("api/filament");
    filData._clientOffset = Date.now() / 1000 - (filData.now || Date.now() / 1000);
    if (climate === null) climate = await api("api/ha/climate").catch(() => ({ available: false, temperature: [], humidity: [] }));
  } catch (e) { toast(e.message, "bad"); return; }
  renderFilament();
  filTimer = setTimeout(() => { if (currentView === "filament" && !document.hidden) loadFilament(); }, 30000);
}

function sensorChip(icon, entity, unit, warn) {
  if (!entity) return null;
  const v = filData.sensors?.[entity];
  const val = v?.state != null && !isNaN(Number(v.state)) ? Number(v.state) : null;
  const text = val === null ? "–" : `${val.toFixed(unit === "%" ? 0 : 1)} ${v.unit || unit}`;
  return el("span", { class: `sensor${warn && val !== null && val > warn ? " warn" : ""}`,
    title: warn ? t("Grenzwert {0} %", warn) : entity }, icon, " ", text);
}

function batteryChip(entity) {
  if (!entity) return null;
  const v = filData.sensors?.[entity];
  const val = v?.state != null && !isNaN(Number(v.state)) ? Number(v.state) : null;
  return el("span", { class: `sensor${val !== null && val < 20 ? " warn" : ""}`, title: t("Batterie des Sensors") },
    val === null ? "🔋 –" : `${val < 20 ? "🪫" : "🔋"} ${Math.round(val)} %`);
}

function renderFilament() {
  const d = filData;
  // summary
  const all = d.items;
  const spools = all.reduce((s, i) => s + (Number(i.count) || 0), 0);
  const neu = all.filter((i) => i.condition === "neu").reduce((s, i) => s + (Number(i.count) || 0), 0);
  const grams = all.reduce((s, i) => s + itemGrams(i), 0);
  const value = all.reduce((s, i) => s + itemGrams(i) / 1000 * priceFor(i.material), 0);
  const stat = (v, l) => el("div", { class: "stat" }, el("b", {}, v), el("span", {}, l));
  $("#filament-summary").replaceChildren(
    stat(spools, t("Spulen")), stat(neu, t("neu")), stat(spools - neu, t("angefangen")),
    stat(`${(grams / 1000).toFixed(1)} kg`, t("Filament")),
    stat(Object.values(d.in_printer || {}).reduce((n, l) => n + l.length, 0), t("im Drucker")),
    ...((d.dryers || []).length ? [stat(Object.values(d.in_dryer || {}).flat().reduce((n, x) => n + x.qty, 0), t("im Trockner"))] : []),
    ...(value ? [stat(fmtMoney(value, lastState?.costs?.currency, 0), t("Wert"))] : []),
    el("button", { class: "btn primary", style: "align-self:center", onclick: () => openSpoolDialog({ location: firstLocId() }) }, t("+ Filament")));

  const wrap = $("#filament-locations");
  wrap.innerHTML = "";
  wrap.append(printerPanel());
  wrap.append(dryerPanel());
  locs().forEach((loc, idx) => wrap.append(locationPanel(loc, idx)));
  wrap.append(el("div", { class: "row-btns" }, el("button", { class: "btn", onclick: async () => {
    const name = prompt(t("Name des neuen Lagerorts"));
    if (!name || !name.trim()) return;
    try { await api("api/filament/locations", { method: "POST", json: { name: name.trim() } }); loadFilament(); }
    catch (e) { toast(e.message, "bad"); }
  } }, t("+ Lagerort"))));
  renderBrands();
  showFilSub(filSub);
}

// -- sub tabs: inventory / brands ---------------------------------------------
let filSub = (() => { try { return localStorage.getItem("pf-filsub") || "bestand"; } catch { return "bestand"; } })();
function showFilSub(sub) {
  filSub = sub;
  try { localStorage.setItem("pf-filsub", sub); } catch { /* ignore */ }
  for (const b of document.querySelectorAll("#filament-subtabs button")) b.classList.toggle("active", b.dataset.sub === sub);
  $("#filament-summary").hidden = sub !== "bestand";
  $("#filament-locations").hidden = sub !== "bestand";
  $("#filament-brands").hidden = sub !== "marken";
}
document.querySelectorAll("#filament-subtabs button").forEach((b) => b.addEventListener("click", () => showFilSub(b.dataset.sub)));

function brandByName(name) {
  const n = String(name || "").trim().toLowerCase();
  return n ? (filData?.brands || []).find((b) => b.name.toLowerCase() === n) : null;
}

function allMaterials() {
  return [...new Set([...Object.keys(lastState?.costs?.materials || {}), ...(filData?.brands || []).flatMap((b) => b.materials),
    ...(filData?.items || []).map((i) => i.material)].filter(Boolean))].sort();
}

function renderBrands() {
  const wrap = $("#filament-brands");
  const brands = filData.brands || [];
  const usage = (b) => filData.items.filter((i) => i.brand === b.name).reduce((s, i) => s + (Number(i.count) || 0), 0);
  wrap.replaceChildren(...[
    el("div", { class: "brands-head" },
      el("p", { class: "note" }, t("Hier erfasste Marken erscheinen beim Hinzufügen von Filament als Auswahl – mit Spulengewicht, Materialien und Farben als Vorschlag.")),
      el("button", { class: "btn primary", onclick: () => openBrandDialog({}) }, t("+ Marke"))),
    brands.length ? null : el("div", { class: "empty" }, el("p", {}, t("Noch keine Marken erfasst."))),
    el("div", { class: "brand-grid" }, brands.map((b) => el("section", { class: "brand-card" },
      el("header", {},
        el("h3", {}, b.name),
        el("span", { class: "note" }, tn(usage(b), "{0} Spule im Bestand", "{0} Spulen im Bestand")),
        el("span", { class: "spacer" }),
        el("button", { class: "icon-btn", title: t("Bearbeiten"), "aria-label": t("Bearbeiten"), onclick: () => openBrandDialog(b) }, "✎"),
        el("button", { class: "icon-btn", title: t("Löschen"), "aria-label": t("Löschen"), onclick: async () => {
          if (!confirm(t("Marke „{0}“ löschen? Der Bestand bleibt erhalten.", b.name))) return;
          try { await api(`api/filament/brands/${b.id}`, { method: "DELETE" }); loadFilament(); } catch (e) { toast(e.message, "bad"); }
        } }, "🗑")),
      el("div", { class: "sub" }, t("Spule {0} g{1}", b.spool_g, b.note ? " · " + b.note : "")),
      b.materials.length ? el("div", { class: "chips" }, b.materials.map((m) => el("span", { class: "chip" }, m))) : null,
      b.colors.length ? el("div", { class: "swatches" }, b.colors.map((c) => el("span", { class: "cswatch", title: [c.name, c.material].filter(Boolean).join(" · ") },
        spoolIcon(c.color, { size: 22 }), el("span", {}, c.name || c.color)))) : null,
      el("div", { class: "row-btns" }, el("button", { class: "btn", onclick: () => openSpoolDialog({ brand: b.name, location: firstLocId() }) }, t("+ Filament dieser Marke"))))))
  ].filter(Boolean));
}

function openBrandDialog(brand) {
  const b = { name: "", spool_g: 1000, materials: [], colors: [], note: "", ...JSON.parse(JSON.stringify(brand)) };
  const dlg = $("#brand-dialog");
  const form = $("#brand-form");
  const inp = (key, attrs = {}) => {
    const i = el("input", { value: b[key] ?? "", ...attrs });
    i.addEventListener("input", () => { b[key] = attrs.type === "number" ? Number(i.value) : i.value; });
    return i;
  };
  // materials: tick the common ones, add others by text
  const matBox = el("div", { class: "mat-picks" });
  const renderMats = () => {
    const list = [...new Set([...allMaterials(), ...b.materials])].sort();
    matBox.replaceChildren(...list.map((m) => {
      const cb = el("input", { type: "checkbox", checked: b.materials.includes(m) });
      cb.addEventListener("change", () => {
        b.materials = cb.checked ? [...b.materials, m] : b.materials.filter((x) => x !== m);
      });
      return el("label", { class: "mat-pick" }, cb, m);
    }));
  };
  const newMat = el("input", { placeholder: t("weiteres Material, z. B. PLA-MATTE") });
  const addMat = () => {
    const m = newMat.value.trim().toUpperCase();
    if (m && !b.materials.includes(m)) b.materials.push(m);
    newMat.value = ""; renderMats();
  };
  newMat.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); addMat(); } });
  // colours
  const colBox = el("div", { class: "color-list" });
  const renderCols = () => {
    colBox.replaceChildren(...b.colors.map((c, idx) => {
      const ci = el("input", { type: "color", value: c.color });
      const ni = el("input", { value: c.name, placeholder: t("Farbname") });
      const mi = el("select", {}, el("option", { value: "" }, t("alle Materialien")),
        [...new Set([...b.materials, c.material].filter(Boolean))].map((m) => el("option", { value: m, selected: c.material === m }, m)));
      ci.addEventListener("input", () => { c.color = ci.value; });
      ni.addEventListener("input", () => { c.name = ni.value; });
      mi.addEventListener("change", () => { c.material = mi.value; });
      return el("div", { class: "color-line" }, ci, ni, mi,
        el("button", { class: "icon-btn", type: "button", "aria-label": t("Entfernen"), onclick: () => { b.colors.splice(idx, 1); renderCols(); } }, "✕"));
    }));
  };
  renderMats(); renderCols();
  form.replaceChildren(
    el("div", { class: "dialog-head" }, el("h3", {}, brand.id ? t("Marke bearbeiten") : t("Marke hinzufügen")),
      el("button", { class: "icon-btn", value: "cancel", "aria-label": t("Schliessen") }, "✕")),
    el("div", { class: "fields" },
      el("label", { class: "field" }, t("Name"), inp("name", { placeholder: t("z. B. Bambu Lab") })),
      el("label", { class: "field" }, t("Spulengewicht (g)"), inp("spool_g", { type: "number", min: "0", step: "50" }),
        el("small", {}, t("Filament pro Spule, wird beim Erfassen vorgeschlagen"))),
      el("div", { class: "field wide" }, t("Materialien dieser Marke"), matBox,
        el("div", { class: "inline-add" }, newMat, el("button", { class: "btn", type: "button", onclick: addMat }, t("Hinzufügen")))),
      el("div", { class: "field wide" }, t("Farben (optional)"), colBox,
        el("div", {}, el("button", { class: "btn", type: "button", onclick: () => { b.colors.push({ name: "", color: "#ffffff", material: "" }); renderCols(); } }, t("+ Farbe"))),
        el("small", {}, t("Farben erscheinen beim Erfassen als Schnellauswahl. Neue Farben werden beim Speichern einer Spule automatisch hier ergänzt."))),
      el("label", { class: "field wide" }, t("Notiz"), inp("note", { placeholder: t("optional") }))),
    el("div", { class: "dialog-actions" },
      el("button", { class: "btn", value: "cancel" }, t("Abbrechen")),
      el("button", { class: "btn primary", type: "button", onclick: async () => {
        if (newMat.value.trim()) addMat();
        b.colors = b.colors.filter((c) => c.name || c.color);
        try { await api("api/filament/brands", { method: "POST", json: b }); dlg.close(); loadFilament(); }
        catch (e) { toast(e.message, "bad"); }
      } }, t("Speichern"))));
  dlg.showModal();
}

function locationPanel(loc, idx) {
  const key = loc.id;
  const loadedN = (it) => (filData.in_printer?.[it.id] || []).length + dryerQty(it.id);
  const homeCount = (it) => Math.max(0, (Number(it.count) || 0) - loadedN(it));
  // spools that are all in a printer / dryer are shown in those sections instead
  const items = filData.items.filter((i) => i.location === key && !(loadedN(i) && homeCount(i) === 0))
    .sort((a, b) => (a.material + a.brand + a.color_name).localeCompare(b.material + b.brand + b.color_name));
  const count = items.reduce((s, i) => s + homeCount(i), 0);
  const settings = el("div", { class: "loc-settings", hidden: true });
  const panel = el("section", { class: "fil-loc" },
    el("header", { class: "fil-head" },
      el("div", {}, el("h3", {}, locName(loc)), el("span", { class: "note" }, tn(count, "{0} Spule", "{0} Spulen"),
        loc.printer_id ? t(" · AMS von {0}", printerName(loc.printer_id)) : "")),
      el("div", { class: "sensors" },
        sensorChip("🌡", loc.temp_entity, "°C"),
        sensorChip("💧", loc.hum_entity, "%", Number(loc.hum_max) || null),
        batteryChip(loc.bat_entity),
        !loc.temp_entity && !loc.hum_entity && !loc.bat_entity ? el("span", { class: "note" }, t("keine Sensoren")) : null,
        el("button", { class: "icon-btn", title: t("Name, Sensoren, Reihenfolge"), "aria-label": t("Einstellungen"),
          onclick: () => { settings.hidden = !settings.hidden; } }, "⚙"))),
    settings);

  // settings: name + sensors + humidity limit
  const draftLoc = { ...loc, name: loc.name || locName(loc) };
  const opt = (list) => [["", t("– keiner –")], ...list.map((x) => [x.entity_id, `${x.name}${x.state != null ? ` (${x.state}${x.unit ? " " + x.unit : ""})` : ""}`])];
  const tOpts = opt(climate?.temperature || []);
  const hOpts = opt(climate?.humidity || []);
  const bOpts = opt(climate?.battery || []);
  if (draftLoc.bat_entity && !bOpts.some(([v]) => v === draftLoc.bat_entity)) bOpts.push([draftLoc.bat_entity, draftLoc.bat_entity]);
  if (draftLoc.temp_entity && !tOpts.some(([v]) => v === draftLoc.temp_entity)) tOpts.push([draftLoc.temp_entity, draftLoc.temp_entity]);
  if (draftLoc.hum_entity && !hOpts.some(([v]) => v === draftLoc.hum_entity)) hOpts.push([draftLoc.hum_entity, draftLoc.hum_entity]);
  settings.append(el("div", { class: "fields" },
    field(t("Name"), draftLoc, "name"),
    field(t("Temperatursensor"), draftLoc, "temp_entity", { options: tOpts }),
    field(t("Feuchtigkeitssensor"), draftLoc, "hum_entity", { options: hOpts }),
    field(t("Batterie des Sensors"), draftLoc, "bat_entity", { options: bOpts }),
    field(t("Warnung ab Feuchte (%)"), draftLoc, "hum_max", { type: "number" })),
    ...(climate?.available ? [] : [el("p", { class: "note" }, t("Home Assistant nicht verbunden – Sensoren nicht verfügbar."))]));
  const move = async (dir) => {
    const ids = locs().map((l) => l.id);
    const j = idx + dir;
    if (j < 0 || j >= ids.length) return;
    [ids[idx], ids[j]] = [ids[j], ids[idx]];
    try { await api("api/filament/locations", { method: "PUT", json: { order: ids } }); loadFilament(); }
    catch (e) { toast(e.message, "bad"); }
  };
  // deleting: spools of this location must go somewhere else
  const stored = filData.items.filter((i) => i.location === key).reduce((s, i) => s + (Number(i.count) || 0), 0);
  const others = locs().filter((l) => l.id !== key);
  const target = el("select", { "aria-label": t("Spulen verschieben nach") }, others.map((l) => el("option", { value: l.id }, locName(l))));
  const delBox = el("div", { class: "row-btns", hidden: true },
    el("span", { class: "note" }, stored ? tn(stored, "{0} Spule verschieben nach", "{0} Spulen verschieben nach") : t("Lagerort wirklich löschen?")),
    stored ? target : null,
    el("button", { class: "btn danger", onclick: async () => {
      const q = stored ? `?move_to=${encodeURIComponent(target.value)}` : "";
      try { await api(`api/filament/locations/${key}${q}`, { method: "DELETE" }); loadFilament(); }
      catch (e) { toast(e.message, "bad"); }
    } }, t("Löschen")),
    el("button", { class: "btn", onclick: () => { delBox.hidden = true; } }, t("Abbrechen")));
  settings.append(
    el("div", { class: "row-btns" },
      el("button", { class: "btn primary", onclick: async () => {
        try { await api(`api/filament/locations/${key}`, { method: "PUT", json: draftLoc }); toast(t("Gespeichert"), "ok"); loadFilament(); }
        catch (e) { toast(e.message, "bad"); }
      } }, t("Speichern")),
      el("button", { class: "btn", disabled: idx === 0, title: t("Nach oben"), onclick: () => move(-1) }, "↑"),
      el("button", { class: "btn", disabled: idx === locs().length - 1, title: t("Nach unten"), onclick: () => move(1) }, "↓"),
      el("span", { class: "spacer" }),
      el("button", { class: "btn danger", disabled: !others.length,
        title: others.length ? "" : t("Der letzte Lagerort kann nicht gelöscht werden"),
        onclick: () => { delBox.hidden = false; } }, t("Lagerort löschen"))),
    delBox);

  const list = el("div", { class: "spools" });
  if (!items.length) list.append(el("div", { class: "note", style: "padding:8px 2px" }, t("Noch kein Filament erfasst.")));
  for (const it of items) list.append(spoolRow(it));
  panel.append(list, el("div", { class: "row-btns" },
    el("button", { class: "btn", onclick: () => openSpoolDialog({ location: key }) }, t("+ Filament"))));
  return panel;
}

function slotName(slot) {
  return /^\d+$/.test(String(slot)) ? `Slot ${slot}` : String(slot);
}

function materialFamily(m) {
  return String(m || "").toUpperCase().split(/[\s_/-]+/)[0];
}

// dropdown on a loaded slot: which stored spool is this?
function assignSelect(pr, f) {
  const fam = materialFamily(f.type);
  const label = (i) => `${[i.material, i.brand, i.color_name].filter(Boolean).join(" · ")}`;
  const same = filData.items.filter((i) => materialFamily(i.material) === fam);
  const other = filData.items.filter((i) => materialFamily(i.material) !== fam);
  const cur = f.manual ? (f.item_id || "none") : "";
  const sel = el("select", { class: "assign-select", title: t("Welche Spule ist das?"), "aria-label": t("Spule zuordnen") },
    el("option", { value: "", selected: cur === "" }, t("Automatisch erkennen")),
    el("option", { value: "none", selected: cur === "none" }, t("Nicht im Bestand")),
    same.length ? el("optgroup", { label: t("{0}-Spulen", fam) }, same.map((i) => el("option", { value: i.id, selected: cur === i.id }, label(i)))) : null,
    other.length ? el("optgroup", { label: t("Andere") }, other.map((i) => el("option", { value: i.id, selected: cur === i.id }, label(i)))) : null);
  sel.addEventListener("change", async () => {
    try {
      await api("api/filament/assign", { method: "PUT", json: { printer_id: pr.printer_id, slot: f.slot, item_id: sel.value } });
      toast(sel.value ? t("Zuordnung gespeichert – gilt bis die Spule entladen wird") : t("Wieder automatisch"), "ok");
      loadFilament();
    } catch (e) { toast(e.message, "bad"); }
  });
  const HOW = { uid: t("Kennung"), color: t("Material + Farbe"), family_color: t("Materialfamilie + Farbe"),
    memory: t("zuletzt in diesem Slot") };
  const how = f.manual ? t("✋ von Hand zugeordnet") : HOW[f.how] ? t("erkannt über {0}", HOW[f.how]) : t("nicht erkannt");
  return el("label", { class: "assign" }, sel, el("span", { class: "how" }, how));
}

function printerPanel() {
  const panel = el("section", { class: "fil-loc printer-loc" },
    el("header", { class: "fil-head" },
      el("div", {}, el("h3", {}, t("🖨 Im Drucker geladen")),
        el("span", { class: "note" }, t("wird automatisch aktualisiert")))));
  const list = el("div", { class: "spools" });
  let n = 0;
  for (const pr of filData.loaded || []) {
    const empties = [];
    for (const f of pr.filaments) {
      if (!f.type) { empties.push(slotName(f.slot)); continue; }
      n++;
      const item = f.item_id && filData.items.find((i) => i.id === f.item_id);
      const where = `${pr.printer} · ${slotName(f.slot)}`;
      const fill = f.remain != null ? f.remain / 100 : 1;
      if (item) {
        const home = locName(locById(item.location)) || item.location;
        list.append(el("div", { class: `spool loaded${f.active ? " active" : ""}` },
          spoolIcon(item.color || f.color, { size: 38, fill }),
          el("div", { class: "spool-main" },
            el("div", { class: "title" }, [item.material, item.brand].filter(Boolean).join(" · ")),
            el("div", { class: "sub" }, `${item.color_name || item.color}${f.remain != null ? t(" · {0} % übrig", f.remain) : ""}`),
            el("div", { class: "loaded-badges" },
              el("span", { class: "loaded-badge" }, `🖨 ${where}`),
              f.active ? el("span", { class: "badge printing mini" }, t("druckt gerade")) : null,
              el("span", { class: "note" }, t("zurück nach: {0}", home))),
            assignSelect(pr, f)),
          el("button", { class: "icon-btn", title: t("Bearbeiten"), "aria-label": t("Bearbeiten"), onclick: () => openSpoolDialog(item) }, "✎")));
      } else {
        const add = () => openSpoolDialog({ location: firstLocId(true), material: (f.type || "").split(" ")[0],
          color: f.color || "#cccccc", uid: f.uid || "", count: 1, condition: "angefangen" });
        list.append(el("div", { class: "spool loaded unknown" },
          spoolIcon(f.color, { size: 38, fill }),
          el("div", { class: "spool-main" },
            el("div", { class: "title" }, f.type),
            el("div", { class: "sub" }, t("{0}nicht im Bestand{1}", f.manual ? t("von Hand: ") : "", f.uid ? t(" · Kennung {0}", f.uid) : "")),
            el("div", { class: "loaded-badges" }, el("span", { class: "loaded-badge" }, `🖨 ${where}`)),
            filData.items.length ? assignSelect(pr, f) : null),
          el("button", { class: "btn", onclick: add }, t("Erfassen"))));
      }
    }
    if (empties.length) list.append(el("div", { class: "note empty-slots" }, t("{0}: leer – {1}", pr.printer, empties.join(", "))));
  }
  if (!(filData.loaded || []).length) list.append(el("div", { class: "note", style: "padding:8px 2px" }, t("Kein Drucker meldet geladenes Filament.")));
  panel.querySelector(".note").textContent = tn(n, "{0} Spule · wird automatisch aktualisiert", "{0} Spulen · wird automatisch aktualisiert");
  panel.append(list);
  return panel;
}

function spoolRow(it) {
  const save = async (changes) => {
    try { await api("api/filament/items", { method: "POST", json: { ...it, ...changes } }); loadFilament(); }
    catch (e) { toast(e.message, "bad"); }
  };
  const move = el("select", { title: t("Verschieben"), "aria-label": t("Verschieben") },
    el("option", { value: "" }, "→ …"),
    locs().filter((l) => l.id !== it.location).map((l) => el("option", { value: l.id }, `→ ${locName(l)}`)));
  const extra = it.condition === "angefangen" && it.remaining_g != null ? ` · ≈ ${Math.round(it.remaining_g)} g` : "";
  const inPrinter = filData.in_printer?.[it.id] || [];
  const inDryer = dryerQty(it.id);
  const here = Math.max(0, (Number(it.count) || 0) - inPrinter.length - inDryer);
  // moving: with several spools you choose how many go (spools in a printer or dryer stay)
  const doMove = async (to, qty) => {
    try { await api(`api/filament/items/${it.id}/move`, { method: "POST", json: { to, qty } }); loadFilament(); }
    catch (e) { toast(e.message, "bad"); }
  };
  const moveBox = el("div", { class: "move-box", hidden: true });
  move.addEventListener("change", () => {
    const to = move.value;
    if (!to) return;
    if (here <= 1) { doMove(to, 1); return; }
    let qty = 1;
    const num = el("b", {}, "1");
    const set = (n) => { qty = Math.max(1, Math.min(here, n)); num.textContent = String(qty); };
    moveBox.replaceChildren(
      el("span", {}, t("Wie viele nach {0}?", locName(locById(to)))),
      el("span", { class: "counter" },
        el("button", { class: "icon-btn", type: "button", "aria-label": t("weniger"), onclick: () => set(qty - 1) }, "−"),
        num,
        el("button", { class: "icon-btn", type: "button", "aria-label": t("mehr"), onclick: () => set(qty + 1) }, "+")),
      el("span", { class: "note" }, t("von {0}", here)),
      el("button", { class: "btn mini", type: "button", onclick: () => set(here) }, t("Alle")),
      el("button", { class: "btn primary mini", type: "button", onclick: () => doMove(to, qty) }, t("Verschieben")),
      el("button", { class: "btn mini", type: "button", onclick: () => { moveBox.hidden = true; move.value = ""; } }, t("Abbrechen")));
    moveBox.hidden = false;
  });
  return el("div", { class: `spool${Number(it.count) ? "" : " empty"}` },
    spoolIcon(it.color, { size: 38, fill: it.condition === "angefangen" && it.remaining_g != null && it.spool_g
      ? Number(it.remaining_g) / Number(it.spool_g) : (it.condition === "angefangen" ? 0.55 : 1) }),
    el("div", { class: "spool-main" },
      el("div", { class: "title", title: [it.material, it.brand].filter(Boolean).join(" · ") },
        [it.material || "?", it.brand].filter(Boolean).join(" · ")),
      el("div", { class: "sub" },
        el("span", { class: `badge mini ${it.condition === "neu" ? "finished" : "paused"}` }, COND_LABEL[it.condition]),
        isLow(it) ? el("span", { class: "badge mini failed", title: t("Weniger als {0} g übrig", lastState?.filament_low_g) }, t("knapp")) : null,
        ` ${it.color_name || it.color}${extra}${it.note ? " · " + it.note : ""}`),
      inPrinter.length || inDryer || it.dried_at || it.return_to ? el("div", { class: "loaded-badges" },
        it.return_to ? el("span", { class: "note", title: t("Kommt an diesen Ort zurück, wenn du die Spule bei laufendem Drucker aus dem AMS nimmst.") },
          t("↩ aus {0}", locName(locById(it.return_to)))) : null,
        inPrinter.length ? el("span", { class: "loaded-badge" }, t("+ {0} im Drucker geladen", inPrinter.length)) : null,
        inDryer ? el("span", { class: "loaded-badge dry" }, t("+ {0} im Trockner", inDryer)) : null,
        it.dried_at ? el("span", { class: "note", title: fmtDate(it.dried_at) }, t("🌀 getrocknet {0}", driedAgo(it.dried_at))) : null) : null,
      moveBox),
    el("div", { class: "counter" },
      el("button", { class: "icon-btn", "aria-label": t("weniger"), onclick: () => save({ count: Math.max(0, (Number(it.count) || 0) - 1) }) }, "−"),
      el("b", { title: inPrinter.length ? t("{0} insgesamt, {1} im Drucker", it.count, inPrinter.length) : "" }, String(here)),
      el("button", { class: "icon-btn", "aria-label": t("mehr"), onclick: () => save({ count: (Number(it.count) || 0) + 1 }) }, "+")),
    move,
    el("button", { class: "icon-btn", title: t("Bearbeiten"), "aria-label": t("Bearbeiten"), onclick: () => openSpoolDialog(it) }, "✎"),
    el("button", { class: "icon-btn", title: t("Löschen"), "aria-label": t("Löschen"), onclick: async () => {
      if (!confirm(t("Eintrag löschen?"))) return;
      await api(`api/filament/items/${it.id}`, { method: "DELETE" }); loadFilament();
    } }, "🗑"));
}

// dropdown with an "other…" entry that switches to free text
function pickOrType(options, value, { placeholder = "", other = t("Andere …"), upper = false, onchange }) {
  const OTHER = "__other__";
  const sel = el("select", {});
  const txt = el("input", { placeholder, value: value || "" });
  const wrap = el("div", { class: "pick-or-type" }, sel, txt);
  const fill = (opts, v) => {
    sel.replaceChildren(el("option", { value: "" }, t("– wählen –")), ...opts.map((o) => el("option", { value: o }, o)), el("option", { value: OTHER }, other));
    const known = v && opts.includes(v);
    sel.value = !v ? "" : known ? v : OTHER;
    txt.value = known ? "" : (v || "");
    txt.hidden = sel.value !== OTHER;
  };
  sel.addEventListener("change", () => {
    txt.hidden = sel.value !== OTHER;
    if (sel.value === OTHER) { txt.focus(); onchange(txt.value); } else onchange(sel.value);
  });
  txt.addEventListener("input", () => { if (upper) txt.value = txt.value.toUpperCase(); onchange(txt.value.trim()); });
  fill(options, value);
  return { node: wrap, fill };
}

function openSpoolDialog(item) {
  const it = { brand: "", material: "PLA", color: "#ffffff", color_name: "", count: 1, condition: "neu",
    spool_g: 1000, remaining_g: null, note: "", location: firstLocId(), ...item };
  const isNew = !item.id;
  if (isNew && item.brand && brandByName(item.brand) && item.spool_g == null) it.spool_g = brandByName(item.brand).spool_g;
  const dlg = $("#spool-dialog");
  const form = $("#spool-form");
  form.innerHTML = "";
  const input = (label, key, attrs = {}) => {
    const inp = el("input", { value: it[key] ?? "", ...attrs });
    inp.addEventListener("input", () => { it[key] = attrs.type === "number" ? (inp.value === "" ? null : Number(inp.value)) : inp.value; });
    return el("label", { class: "field" }, label, inp);
  };
  const colorInp = el("input", { type: "color", value: it.color });
  const nameInp = el("input", { value: it.color_name, placeholder: t("z. B. Jade White") });
  nameInp.addEventListener("input", () => { it.color_name = nameInp.value; });
  const preview = el("span", {}, spoolIcon(it.color, { size: 34 }));
  const setColor = (hex, name) => {
    it.color = hex; colorInp.value = hex;
    preview.replaceChildren(spoolIcon(hex, { size: 34 }));
    if (name !== undefined) { it.color_name = name; nameInp.value = name; }
    renderSwatches();
  };
  colorInp.addEventListener("input", () => setColor(colorInp.value));
  const spoolG = input(t("Spulengewicht (g)"), "spool_g", { type: "number", min: "0", step: "50" });

  // brand -> materials -> colour swatches
  const swatches = el("div", { class: "swatches pick" });
  const renderSwatches = () => {
    const b = brandByName(it.brand);
    const cols = (b?.colors || []).filter((c) => !c.material || !it.material || c.material === it.material);
    swatches.replaceChildren(...cols.map((c) => el("button", {
      type: "button", class: `cswatch${c.color.toLowerCase() === String(it.color).toLowerCase() && (c.name || "") === (it.color_name || "") ? " sel" : ""}`,
      title: [c.name, c.material].filter(Boolean).join(" · "),
      onclick: () => setColor(c.color, c.name || ""),
    }, spoolIcon(c.color, { size: 22 }), el("span", {}, c.name || c.color))));
    swatches.hidden = !cols.length;
  };
  const matOptions = () => {
    const b = brandByName(it.brand);
    return b?.materials?.length ? b.materials : allMaterials();
  };
  const matPick = pickOrType(matOptions(), it.material, { placeholder: t("z. B. PLA-MATTE"), upper: true,
    onchange: (v) => { it.material = v.toUpperCase(); renderSwatches(); } });
  const brandPick = pickOrType((filData.brands || []).map((b) => b.name), it.brand, { placeholder: t("Neue Marke"), other: t("Andere / neue Marke …"),
    onchange: (v) => {
      it.brand = v;
      const b = brandByName(v);
      if (b && isNew) { it.spool_g = b.spool_g; $("input", spoolG).value = b.spool_g; }
      const opts = matOptions();
      if (b?.materials?.length && !opts.includes(it.material)) it.material = opts.length === 1 ? opts[0] : (opts.includes("PLA") ? "PLA" : opts[0]);
      matPick.fill(opts, it.material);
      renderSwatches();
    } });
  renderSwatches();

  const remaining = input(t("Restgewicht (g, optional)"), "remaining_g", { type: "number", min: "0", step: "10" });
  const cond = el("select", {}, Object.entries(COND_LABEL).map(([v, l]) => el("option", { value: v, selected: it.condition === v }, l)));
  cond.addEventListener("change", () => { it.condition = cond.value; remaining.hidden = cond.value !== "angefangen"; });
  remaining.hidden = it.condition !== "angefangen";
  if (!locById(it.location)) it.location = firstLocId();
  const loc = el("select", {}, locs().map((l) => el("option", { value: l.id, selected: it.location === l.id }, locName(l))));
  loc.addEventListener("change", () => { it.location = loc.value; });
  form.append(
    el("div", { class: "dialog-head" }, el("h3", {}, item.id ? t("Filament bearbeiten") : t("Filament hinzufügen")),
      el("button", { class: "icon-btn", value: "cancel", "aria-label": t("Schliessen") }, "✕")),
    el("div", { class: "fields" },
      el("label", { class: "field" }, t("Marke"), brandPick.node,
        (filData.brands || []).length ? null : el("small", {}, t("Tipp: Marken unter Filament → Marken erfassen"))),
      el("label", { class: "field" }, t("Material"), matPick.node),
      el("div", { class: "field wide" }, t("Farbe"), swatches, el("div", { class: "color-row" }, preview, colorInp, nameInp)),
      input(t("Anzahl Spulen"), "count", { type: "number", min: "0", step: "1" }),
      el("label", { class: "field" }, t("Zustand"), cond),
      spoolG,
      remaining,
      el("label", { class: "field" }, t("Ort"), loc),
      input(t("Notiz"), "note", { placeholder: t("optional") }),
      el("label", { class: "field wide" }, t("Kennung / Seriennummer (optional)"),
        (() => { const u = el("input", { value: it.uid || "", placeholder: t("z. B. RFID-Nummer der Bambu-Spule") });
          u.addEventListener("input", () => { it.uid = u.value.trim(); }); return u; })(),
        el("small", {}, t("Leer = Erkennung im Drucker über Material + Farbe.")))),
    el("div", { class: "dialog-actions" },
      el("button", { class: "btn", value: "cancel" }, t("Abbrechen")),
      el("button", { class: "btn primary", type: "button", onclick: async () => {
        if (!it.material) { toast(t("Bitte Material angeben"), "bad"); return; }
        try {
          await api("api/filament/items", { method: "POST", json: it });
          await rememberInBrand(it).catch(() => {});
          dlg.close(); loadFilament();
        } catch (e) { toast(e.message, "bad"); }
      } }, t("Speichern"))));
  dlg.showModal();
}

// new brand / material / colour from a saved spool is added to the brand list
async function rememberInBrand(it) {
  const name = String(it.brand || "").trim();
  if (!name) return;
  const existing = brandByName(name);
  const b = existing ? JSON.parse(JSON.stringify(existing)) : { name, spool_g: it.spool_g || 1000, materials: [], colors: [] };
  let changed = !existing;
  const mat = String(it.material || "").toUpperCase();
  if (mat && !b.materials.includes(mat)) { b.materials.push(mat); changed = true; }
  const cname = String(it.color_name || "").trim();
  if (cname && !b.colors.some((c) => c.name.toLowerCase() === cname.toLowerCase() && (!c.material || c.material === mat))) {
    b.colors.push({ name: cname, color: it.color, material: mat }); changed = true;
  }
  if (changed) await api("api/filament/brands", { method: "POST", json: b });
}


// -- filament dryers -------------------------------------------------------------
function dryerQty(itemId) {
  return (filData?.in_dryer?.[itemId] || []).reduce((n, x) => n + x.qty, 0);
}
function serverNow() {
  return Date.now() / 1000 - (filData?._clientOffset || 0);
}
function driedAgo(ts) {
  const days = Math.floor((serverNow() - ts) / 86400);
  return days <= 0 ? t("heute") : days === 1 ? t("gestern") : t("vor {0} Tagen", days);
}
function fmtClockTs(ts) {
  return fmtClock(new Date(ts * 1000));
}
function itemLabel(it) {
  return [it.material, it.brand, it.color_name].filter(Boolean).join(" · ") || t("Spule");
}

let dryerTick = null;
function dryerPanel() {
  const dryers = filData.dryers || [];
  const panel = el("section", { class: "fil-loc dryer-loc" });
  const countSel = el("select", { "aria-label": t("Anzahl Trockner") },
    [0, 1, 2, 3, 4].map((n) => el("option", { value: n, selected: n === dryers.length }, n === 0 ? t("keine") : String(n))));
  countSel.addEventListener("change", async () => {
    try { await api("api/filament/dryers", { method: "PUT", json: { count: Number(countSel.value) } }); loadFilament(); }
    catch (e) { toast(e.message, "bad"); countSel.value = dryers.length; }
  });
  const running = dryers.filter((d) => d.job).length;
  panel.append(el("header", { class: "fil-head" },
    el("div", {}, el("h3", {}, t("🌀 Trockner")),
      el("span", { class: "note" }, dryers.length ? t("{0} von {1} in Betrieb", running, dryers.length) : t("Anzahl Trockner wählen"))),
    el("label", { class: "dryer-count" }, t("Anzahl"), countSel)));
  if (!dryers.length) return panel;
  const grid = el("div", { class: "dryer-grid" });
  for (const d of dryers) grid.append(dryerCard(d));
  panel.append(grid);
  clearInterval(dryerTick);
  if (running) dryerTick = setInterval(() => {
    if (currentView !== "filament") return;
    document.querySelectorAll("[data-dryer-end]").forEach((n) => updateDryerTime(n));
  }, 15000);
  return panel;
}

function updateDryerTime(node) {
  const end = Number(node.dataset.dryerEnd), start = Number(node.dataset.dryerStart);
  const left = Math.max(0, end - serverNow());
  node.querySelector(".dryer-left").textContent = left > 0 ? t("noch {0}", fmtDuration(left)) : t("fertig – wird abgeschlossen …");
  node.querySelector(".bar").style.width = `${Math.min(100, (serverNow() - start) / (end - start) * 100)}%`;
}

function dryerCard(d) {
  const byId = Object.fromEntries(filData.items.map((i) => [i.id, i]));
  const act = async (path, json) => {
    try { await api(`api/filament/dryers/${d.id}/${path}`, { method: "POST", json }); loadFilament(); }
    catch (e) { toast(e.message, "bad"); }
  };
  const rename = el("button", { class: "icon-btn", title: t("Umbenennen"), "aria-label": t("Umbenennen"), onclick: async () => {
    const name = prompt(t("Name des Trockners"), d.name);
    if (!name) return;
    try { await api(`api/filament/dryers/${d.id}`, { method: "PUT", json: { name } }); loadFilament(); } catch (e) { toast(e.message, "bad"); }
  } }, "✎");
  const card = el("div", { class: `dryer${d.job ? " running" : ""}` },
    el("div", { class: "dryer-head" }, el("b", {}, d.name), rename, el("span", { class: "spacer" }),
      el("span", { class: `badge ${d.job ? "printing" : "idle"}` }, d.job ? t("trocknet") : t("frei"))));
  if (d.job) {
    const j = d.job;
    const time = el("div", { class: "dryer-time", "data-dryer-end": j.end, "data-dryer-start": j.start },
      el("div", { class: "time-row" }, el("span", { class: "big dryer-left" }), el("span", { class: "small" }, t("fertig um {0}", fmtClockTs(j.end))),
        j.temp ? el("span", { class: "chip" }, `${j.temp} °C`) : null),
      el("div", { class: "progress" }, el("div", { class: "bar" })));
    updateDryerTime(time);
    card.append(time,
      el("div", { class: "dryer-items" }, j.items.map((e) => {
        const it = byId[e.item_id];
        return el("div", { class: "dryer-item" }, spoolIcon(it?.color || "#ccc", { size: 26 }),
          el("span", {}, `${e.qty > 1 ? e.qty + "× " : ""}${it ? itemLabel(it) : "?"}`),
          it ? el("span", { class: "note" }, `↩ ${locName(locById(it.location))}`) : null);
      })),
      el("div", { class: "row-btns" },
        el("button", { class: "btn", onclick: () => act("extend", { minutes: 30 }) }, "+30 min"),
        el("button", { class: "btn", onclick: () => act("extend", { minutes: 60 }) }, "+1 h"),
        el("button", { class: "btn primary", onclick: () => act("stop", { done: true }) }, t("Jetzt fertig")),
        el("button", { class: "btn danger", onclick: () => { if (confirm(t("Trocknung abbrechen? Die Spulen kehren zurück, ohne als getrocknet markiert zu werden."))) act("stop", { done: false }); } }, t("Abbrechen"))));
  } else {
    if (d.last) card.append(el("div", { class: "note" },
      t("Zuletzt: {0} · {1}{2}", fmtDate(d.last.start), fmtDuration((d.last.end - d.last.start)), d.last.done ? "" : t(" (abgebrochen)"))));
    card.append(el("div", { class: "row-btns" },
      el("button", { class: "btn primary", onclick: () => openDryerDialog(d) }, t("Spulen einlegen & starten")),
      d.last ? el("button", { class: "btn", title: t("Gleiche Spulen und Zeit nochmals"), onclick: () => openDryerDialog(d, d.last) }, t("Wie zuletzt")) : null));
  }
  return card;
}

function openDryerDialog(d, preset = null) {
  const dlg = $("#dryer-dialog");
  const form = $("#dryer-form");
  const guide = filData.dry_guide || {};
  // spools available at home (not in a printer or another dryer)
  const avail = filData.items.map((it) => ({ it,
    free: (Number(it.count) || 0) - (filData.in_printer?.[it.id] || []).length - dryerQty(it.id) }))
    .filter((x) => x.free > 0)
    .sort((a, b) => locs().findIndex((l) => l.id === a.it.location) - locs().findIndex((l) => l.id === b.it.location)
      || itemLabel(a.it).localeCompare(itemLabel(b.it)));
  const chosen = new Map();
  for (const e of preset?.items || []) {
    const a = avail.find((x) => x.it.id === e.item_id);
    if (a) chosen.set(e.item_id, Math.min(e.qty, a.free));
  }
  let manual = !!preset;
  const hours = el("input", { type: "number", min: "0", step: "0.5", value: preset ? (preset.minutes || 0) / 60 : 6 });
  const temp = el("input", { type: "number", min: "0", step: "5", value: preset?.temp ?? "", placeholder: t("optional") });
  const tip = el("small", {});
  [hours, temp].forEach((i) => i.addEventListener("input", () => { manual = true; }));
  const suggest = () => {
    const mats = [...new Set([...chosen.keys()].map((id) => materialFamily(filData.items.find((i) => i.id === id)?.material)))].filter(Boolean);
    const g = mats.map((m) => [m, guide[m]]).filter(([, v]) => v);
    if (!g.length) { tip.textContent = t("Richtwerte: Angaben des Herstellers beachten."); return; }
    const tMin = Math.min(...g.map(([, v]) => v[0])), h = Math.max(...g.map(([, v]) => v[1]));
    tip.textContent = t("Richtwert: {0}{1}. Herstellerangaben haben Vorrang.", g.map(([m, v]) => `${m} ${v[0]} °C / ${v[1]} h`).join(" · "), g.length > 1 ? t(" → gemischt: {0} °C, {1} h", tMin, h) : "");
    if (!manual) { hours.value = h; temp.value = tMin; }
  };
  const list = el("div", { class: "dryer-pick" });
  let curLoc = null;
  for (const { it, free } of avail) {
    if (it.location !== curLoc) { curLoc = it.location; list.append(el("div", { class: "pick-loc" }, locName(locById(curLoc)) || curLoc)); }
    const cb = el("input", { type: "checkbox", checked: chosen.has(it.id) });
    const qty = el("input", { type: "number", min: "1", max: String(free), value: String(chosen.get(it.id) || 1), class: "qty", hidden: free < 2 });
    const sync = () => { if (cb.checked) chosen.set(it.id, Math.max(1, Math.min(free, Number(qty.value) || 1))); else chosen.delete(it.id); suggest(); };
    cb.addEventListener("change", sync); qty.addEventListener("input", sync);
    list.append(el("label", { class: "pick-row" }, cb, spoolIcon(it.color, { size: 24 }),
      el("span", { class: "pick-name" }, itemLabel(it), el("small", {}, ` ${COND_LABEL[it.condition] || ""}${it.dried_at ? t(" · getrocknet {0}", driedAgo(it.dried_at)) : ""}`)),
      free > 1 ? el("span", { class: "note" }, t("von {0}", free)) : null, qty));
  }
  if (!avail.length) list.append(el("p", { class: "note" }, t("Keine freien Spulen im Bestand.")));
  suggest();
  form.replaceChildren(
    el("div", { class: "dialog-head" }, el("h3", {}, t("{0}: Trocknung starten", d.name)),
      el("button", { class: "icon-btn", value: "cancel", "aria-label": t("Schliessen") }, "✕")),
    el("div", { class: "field wide" }, t("Spulen einlegen"), list),
    el("div", { class: "fields" },
      el("label", { class: "field" }, t("Dauer (Stunden)"), hours),
      el("label", { class: "field" }, t("Temperatur (°C, nur zur Info)"), temp),
      el("div", { class: "field wide" }, tip)),
    el("div", { class: "dialog-actions" },
      el("button", { class: "btn", value: "cancel" }, t("Abbrechen")),
      el("button", { class: "btn primary", type: "button", onclick: async () => {
        const minutes = Math.round((Number(hours.value) || 0) * 60);
        try {
          await api(`api/filament/dryers/${d.id}/start`, { method: "POST", json: {
            items: [...chosen].map(([item_id, qty]) => ({ item_id, qty })), minutes, temp: temp.value === "" ? null : Number(temp.value) } });
          dlg.close(); toast(t("{0} läuft – fertig um {1}", d.name, fmtClockTs(serverNow() + minutes * 60)), "ok"); loadFilament();
        } catch (e) { toast(e.message, "bad"); }
      } }, t("Starten"))));
  dlg.showModal();
}
