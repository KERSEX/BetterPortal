// BetterPortal – Frontend-Logik
"use strict";

const ELEMENT_COLORS = {
  Luft: "#8fd8e8", Erde: "#c98a3d", Feuer: "#ff6b4a", Wasser: "#4aa3f0",
  Magie: "#b76ee0", Tech: "#f5a623", Leben: "#66cc55", Untot: "#9b8fc4",
  Licht: "#ffe066", Dunkelheit: "#7a5fd0", Kaos: "#58c470",
};
const GAME_SHORT = { 1: "SA", 2: "GI", 3: "SF", 4: "TT", 5: "SC", 6: "IM" };

let DATA = null;      // /api/data
let LIB = [];         // Bibliotheksdateien
let SLOTS = [];       // Portal-Slots
let LOADOUTS = {};
let selTop = null;    // {index, variant{var,name}}
let selBottom = null;

const $ = (sel) => document.querySelector(sel);

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function toast(msg, isError = false) {
  const el = document.createElement("div");
  el.className = "toast" + (isError ? " error" : "");
  el.textContent = msg;
  $("#toast-wrap").appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

// Nach diesen Aktionen kann eine RPCS3-Uebertragung starten -> Ring-Status schnell pruefen
const INJECT_TRIGGER_PATHS = ["/api/portal/", "/api/swapper", "/api/loadouts/apply",
  "/api/hotswap/trigger", "/api/inject/now"];

async function api(path, body) {
  const opts = body
    ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
    : undefined;
  const res = await fetch(path, opts);
  const data = await res.json();
  if (data && data.ok === false) throw new Error(data.error || "Unbekannter Fehler");
  if (opts && INJECT_TRIGGER_PATHS.some((p) => path.startsWith(p))) nudgeInjectPoll();
  return data;
}

function run(fn) {
  return Promise.resolve()
    .then(fn)
    .catch((e) => toast(e.message, true));
}

function chip(label, color) {
  const dot = color ? `<span class="dot" style="background:${color}"></span>` : "";
  return `<span class="chip">${dot}${esc(label)}</span>`;
}

function elemChip(element) {
  return element ? chip(element, ELEMENT_COLORS[element]) : "";
}

/* ================= Tabs ================= */

document.querySelectorAll("#tabs button").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#tabs button").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    btn.classList.add("active");
    $("#tab-" + btn.dataset.tab).classList.add("active");
  });
});

function switchTab(name) {
  document.querySelector(`#tabs button[data-tab="${name}"]`).click();
}

/* ================= Portal ================= */

let PLACEMENT = "p1";

function slotRole(i) {
  if (PLACEMENT === "free") return "";
  const roles = {
    0: "👤 Spieler 1", 1: "👤 P1 · Unterteil", 2: "🧰 Items", 3: "🧰 Items",
    4: "👥 Spieler 2", 5: "👥 P2 · Unterteil",
  };
  return roles[i] || "";
}

function updatePlacementSeg() {
  document.querySelectorAll("#placement-seg button").forEach((b) =>
    b.classList.toggle("active", b.dataset.mode === PLACEMENT));
}

document.querySelectorAll("#placement-seg button").forEach((b) =>
  b.addEventListener("click", () =>
    run(async () => {
      PLACEMENT = b.dataset.mode;
      updatePlacementSeg();
      renderSlots();
      await api("/api/placement", { mode: PLACEMENT });
      toast(PLACEMENT === "free"
        ? "Platzierung: nächster freier Slot."
        : `Platzierung: ${PLACEMENT === "p1" ? "Spieler 1 (Slot 1+2)" : "Spieler 2 (Slot 5+6)"} wird überschrieben, Items → Slot 3+4.`);
    })));

async function refreshPortal() {
  SLOTS = (await api("/api/portal")).slots;
  renderSlots();
}

function renderSlots() {
  const grid = $("#slots");
  grid.innerHTML = "";
  SLOTS.forEach((s, i) => {
    const card = document.createElement("div");
    const role = slotRole(i) ? `<div class="slot-role">${slotRole(i)}</div>` : "";
    if (s) {
      card.className = "slot-card filled";
      card.innerHTML = `
        <div class="slot-num">${i + 1}</div>
        ${role}
        <div class="slot-name">${esc(s.display)}</div>
        <div class="slot-chips">${elemChip(s.element)}${s.category ? chip(s.category) : ""}</div>
        <div class="slot-foot">
          <button data-act="clear">✖ Leeren</button>
        </div>`;
      card.querySelector('[data-act="clear"]').addEventListener("click", () =>
        run(async () => {
          SLOTS = (await api("/api/portal/clear", { slot: i })).slots;
          renderSlots();
        }));
    } else {
      card.className = "slot-card empty";
      card.innerHTML = `
        <div class="slot-num">${i + 1}</div>
        ${role}
        <button class="slot-empty-btn" data-act="fill">＋ Belegen</button>`;
      card.querySelector('[data-act="fill"]').addEventListener("click", () => openSlotPicker(i));
    }
    grid.appendChild(card);
  });
}

$("#btn-clear-all").addEventListener("click", () =>
  run(async () => {
    if (!SLOTS.some(Boolean)) return;
    if (!confirm("Wirklich alle Portal-Slots leeren? (Bibliotheksdateien bleiben erhalten)")) return;
    SLOTS = (await api("/api/portal/clear", {})).slots;
    renderSlots();
    toast("Portal geleert.");
  }));

/* ---------- Loadouts ---------- */

async function refreshLoadouts() {
  LOADOUTS = (await api("/api/loadouts")).loadouts;
  renderHotswap(); // Figuren-Anzahl / Warnungen auf den Hot-Swap-Kacheln aktuell halten
  const sel = $("#loadout-select");
  sel.innerHTML = "";
  const names = Object.keys(LOADOUTS);
  if (!names.length) {
    sel.innerHTML = `<option value="">– keine gespeichert –</option>`;
  } else {
    names.forEach((n) => {
      const o = document.createElement("option");
      o.value = n;
      o.textContent = `${n} (${LOADOUTS[n].length} Figuren)`;
      sel.appendChild(o);
    });
  }
}

$("#btn-loadout-save").addEventListener("click", () =>
  run(async () => {
    const name = prompt("Name für das Loadout (z. B. 'Swap Force Story'):");
    if (!name) return;
    await api("/api/loadouts/save", { name });
    await refreshLoadouts();
    $("#loadout-select").value = name;
    toast(`Loadout „${name}" gespeichert.`);
  }));

$("#btn-loadout-apply").addEventListener("click", () =>
  run(async () => {
    const name = $("#loadout-select").value;
    if (!name) return toast("Kein Loadout ausgewählt.", true);
    const r = await api("/api/loadouts/apply", { name });
    SLOTS = r.slots;
    renderSlots();
    toast(r.recreated.length
      ? `Loadout geladen – ${r.recreated.length} Figur(en) neu erstellt.`
      : `Loadout „${name}" geladen.`);
  }));

$("#btn-loadout-delete").addEventListener("click", () =>
  run(async () => {
    const name = $("#loadout-select").value;
    if (!name) return;
    if (!confirm(`Loadout „${name}" löschen?`)) return;
    await api("/api/loadouts/delete", { name });
    await refreshLoadouts();
    toast("Loadout gelöscht.");
  }));

/* ---------- Slot-Auswahl-Modal ---------- */

let modalMode = null;   // "slot" | "hotswap"
let modalTarget = null; // Slot-Index bzw. F-Tasten-Nummer

function openModal(title) {
  $("#modal-title").textContent = title;
  $("#modal-search").value = "";
  $("#modal-elem").value = "";
  $("#modal-cat").value = "";
  // Element-/Kategorie-Filter nur bei Figuren-Auswahl sinnvoll
  const figureMode = modalMode !== "rpcs3";
  $("#modal-elem").style.display = figureMode ? "" : "none";
  $("#modal-cat").style.display = figureMode ? "" : "none";
  renderModalList();
  $("#modal").classList.remove("hidden");
  $("#modal-search").focus();
}

function openSlotPicker(slot) {
  modalMode = "slot";
  modalTarget = slot;
  openModal(`Slot ${slot + 1} belegen`);
}

function openHotswapPicker(key) {
  modalMode = "hotswap";
  modalTarget = key;
  openModal(`${hotkeyLabel(key)} belegen`);
}

let RPCS3GAMES = [];

async function openRpcs3Picker() {
  const d = await api("/api/rpcs3/games");
  if (!d.exe) {
    toast("rpcs3.exe nicht gefunden – Pfad in settings.json unter 'rpcs3_path' eintragen.", true);
    return;
  }
  RPCS3GAMES = d.games.slice();
  if (!RPCS3GAMES.length) {
    toast("Keine Skylanders-Spiele in RPCS3 gefunden.", true);
    return;
  }
  if (!INJECT.rpcs3_running) {
    // Ganz oben (ueber Spyro's Adventure): RPCS3 ohne Spiel starten
    RPCS3GAMES.unshift({ title: "Nur RPCS3 starten (ohne Spiel)", title_id: "", boot: "none", icon: null, bare: true });
  }
  modalMode = "rpcs3";
  modalTarget = null;
  openModal(INJECT.rpcs3_running ? "Spiel wechseln (RPCS3 startet neu)" : "RPCS3 starten – womit?");
}

function libRow(f, onClick) {
  const row = document.createElement("div");
  row.className = "row";
  row.style.cursor = "pointer";
  row.innerHTML = `
    <span class="name">${esc(f.display)}</span>
    ${elemChip(f.element)}
    <span class="grow"></span>
    <span class="sub">${esc(f.folder || "Bibliothek")}</span>`;
  row.addEventListener("click", onClick);
  return row;
}

function renderModalList() {
  const q = $("#modal-search").value.toLowerCase();
  const elem = $("#modal-elem").value;
  const cat = $("#modal-cat").value;
  const list = $("#modal-list");
  list.innerHTML = "";

  // RPCS3-Spieleauswahl (Ring-Klick)
  if (modalMode === "rpcs3") {
    RPCS3GAMES.filter((g) => g.title.toLowerCase().includes(q)).forEach((g) => {
      const row = document.createElement("div");
      row.className = "row";
      row.style.cursor = "pointer";
      const icon = g.icon
        ? `<img class="game-icon" src="/api/rpcs3/icon/${esc(g.title_id)}" alt="">`
        : (g.bare ? `<img class="game-icon rpcs3-icon" src="/static/icon-small.png" alt="">` : "🎮");
      row.innerHTML = `
        ${icon}
        <span class="name">${esc(g.title)}</span>
        <span class="grow"></span>
        <span class="sub">${esc(g.title_id)}</span>`;
      row.addEventListener("click", () =>
        run(async () => {
          const r = await api("/api/rpcs3/launch", { boot: g.boot });
          closeModal();
          toast(`🎮 ${r.message}`);
          nudgeInjectPoll();
        }));
      list.appendChild(row);
    });
    if (!list.children.length) {
      list.innerHTML = `<div class="empty-state">Keine Treffer.</div>`;
    }
    return;
  }

  // Hot-Swap: zusaetzlich Loadouts anbieten (nur ohne Element-/Kategorie-Filter sinnvoll)
  if (modalMode === "hotswap" && !elem && !cat) {
    const loadouts = Object.keys(LOADOUTS).filter((n) => n.toLowerCase().includes(q));
    if (loadouts.length) {
      const h = document.createElement("div");
      h.className = "group-title";
      h.textContent = "💾 Loadouts (ganzes Portal)";
      list.appendChild(h);
      loadouts.forEach((name) => {
        const row = document.createElement("div");
        row.className = "row";
        row.style.cursor = "pointer";
        row.innerHTML = `
          <span class="name">${esc(name)}</span>
          <span class="chip">${LOADOUTS[name].length} Figuren</span>
          <span class="grow"></span>`;
        row.addEventListener("click", () =>
          run(async () => {
            await api("/api/hotswap/set", { key: modalTarget, binding: { type: "loadout", name } });
            await refreshHotswap();
            closeModal();
            toast(`Loadout „${name}" liegt auf ${hotkeyLabel(modalTarget)}.`);
          }));
        list.appendChild(row);
      });
    }
  }

  const files = LIB.filter((f) =>
    (f.display.toLowerCase().includes(q) || (f.folder || "").toLowerCase().includes(q)) &&
    (!elem || f.element === elem) &&
    (!cat || f.category === cat));
  if (files.length && modalMode === "hotswap") {
    const h = document.createElement("div");
    h.className = "group-title";
    h.textContent = "📚 Einzelfigur (in nächsten freien Slot)";
    list.appendChild(h);
  }

  files.forEach((f) => {
    if (modalMode === "slot") {
      list.appendChild(libRow(f, () =>
        run(async () => {
          const r = await api("/api/portal/assign", { slot: modalTarget, relpath: f.relpath });
          SLOTS = r.slots;
          renderSlots();
          closeModal();
          toast(`${f.display} → Slot ${modalTarget + 1}`);
        })));
    } else {
      list.appendChild(libRow(f, () =>
        run(async () => {
          const binding = { type: "figure", relpath: f.relpath, id: f.id, var: f.var,
                            display: f.display, element: f.element };
          await api("/api/hotswap/set", { key: modalTarget, binding });
          await refreshHotswap();
          closeModal();
          toast(`${f.display} liegt auf ${hotkeyLabel(modalTarget)}.`);
        })));
    }
  });

  if (!list.children.length) {
    list.innerHTML = `<div class="empty-state">Nichts gefunden. Neue Figuren gibt's unter „Alle Figuren".</div>`;
  }
}

function closeModal() { $("#modal").classList.add("hidden"); }
$("#modal-close").addEventListener("click", closeModal);
$("#modal").addEventListener("click", (e) => { if (e.target.id === "modal") closeModal(); });
$("#modal-search").addEventListener("input", renderModalList);
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });

/* ================= Swapper-Studio ================= */

function renderSwapperGrids() {
  const tops = $("#swap-tops");
  const bottoms = $("#swap-bottoms");
  tops.innerHTML = "";
  bottoms.innerHTML = "";

  DATA.swappers.forEach((sw) => {
    const color = ELEMENT_COLORS[sw.element];

    const t = document.createElement("button");
    t.className = "swap-tile";
    t.style.setProperty("--el", color);
    t.dataset.index = sw.index;
    t.innerHTML = `<span class="big">${esc(sw.name_top)}</span><span class="sub">${esc(sw.name)} · ${esc(sw.element)}</span>`;
    t.addEventListener("click", () => selectSwapper("top", sw.index));
    tops.appendChild(t);

    const b = document.createElement("button");
    b.className = "swap-tile";
    b.style.setProperty("--el", color);
    b.dataset.index = sw.index;
    b.innerHTML = `<span class="big">${esc(sw.name_bottom)}</span><span class="sub">${sw.move_icon} ${esc(sw.move)} · ${esc(sw.element)}</span>`;
    b.addEventListener("click", () => selectSwapper("bottom", sw.index));
    bottoms.appendChild(b);
  });
}

function selectSwapper(side, index) {
  const sw = DATA.swappers[index];
  const variants = side === "top" ? sw.tops : sw.bottoms;
  const sel = { index, variant: variants[0] };
  if (side === "top") selTop = sel; else selBottom = sel;

  // Kachel-Markierung
  const grid = side === "top" ? "#swap-tops" : "#swap-bottoms";
  document.querySelectorAll(`${grid} .swap-tile`).forEach((el) =>
    el.classList.toggle("selected", Number(el.dataset.index) === index));

  // Varianten-Dropdown
  const wrap = $(side === "top" ? "#top-variant-wrap" : "#bottom-variant-wrap");
  const dd = $(side === "top" ? "#top-variant" : "#bottom-variant");
  dd.innerHTML = "";
  variants.forEach((v, i) => {
    const o = document.createElement("option");
    o.value = i;
    o.textContent = v.name;
    dd.appendChild(o);
  });
  wrap.classList.toggle("hidden", variants.length < 2);

  renderSwapPreview();
}

$("#top-variant").addEventListener("change", (e) => {
  selTop.variant = DATA.swappers[selTop.index].tops[Number(e.target.value)];
  renderSwapPreview();
});
$("#bottom-variant").addEventListener("change", (e) => {
  selBottom.variant = DATA.swappers[selBottom.index].bottoms[Number(e.target.value)];
  renderSwapPreview();
});

function renderSwapPreview() {
  const box = $("#swap-preview");
  $("#btn-swap-build").disabled = !(selTop && selBottom);

  if (!selTop && !selBottom) {
    box.innerHTML = `<div class="placeholder">Wähle links ein Oberteil<br>und rechts ein Unterteil</div>`;
    return;
  }
  const t = selTop ? DATA.swappers[selTop.index] : null;
  const b = selBottom ? DATA.swappers[selBottom.index] : null;
  const name = `${t ? t.name_top : "…"} ${b ? b.name_bottom : "…"}`;

  box.innerHTML = `
    <div style="font-size:36px">${t && b ? (t.index === b.index ? "🧩" : "🔀") : "🧩"}</div>
    <div class="combo-name">${esc(name)}</div>
    <div class="parts">
      ${t ? `⬆️ ${esc(selTop.variant.name)}` : "⬆️ –"}<br>
      ${b ? `⬇️ ${esc(selBottom.variant.name)}` : "⬇️ –"}
    </div>
    <div class="combo-chips">
      ${t ? elemChip(t.element) : ""}
      ${b && (!t || b.element !== t.element) ? elemChip(b.element) : ""}
      ${b ? chip(`${b.move_icon} Swap-Zone: ${b.move}`) : ""}
    </div>`;
}

$("#btn-swap-random").addEventListener("click", () => {
  const i = Math.floor(Math.random() * DATA.swappers.length);
  let j = Math.floor(Math.random() * DATA.swappers.length);
  if (j === i) j = (j + 1) % DATA.swappers.length;
  selectSwapper("top", i);
  selectSwapper("bottom", j);
});

$("#btn-swap-build").addEventListener("click", () =>
  run(async () => {
    const t = DATA.swappers[selTop.index];
    const b = DATA.swappers[selBottom.index];
    const r = await api("/api/swapper", {
      top: { id: t.top_id, var: selTop.variant.var },
      bottom: { id: b.bottom_id, var: selBottom.variant.var },
    });
    SLOTS = r.slots;
    renderSlots();
    await refreshLibrary(false);
    const [s1, s2] = r.slots_used;
    toast(`${t.name_top} ${b.name_bottom} liegt in Slot ${s1 + 1} + ${s2 + 1}. 🔀`);
    switchTab("portal");
  }));

/* ================= Hot-Swap ================= */

let HOTSWAP = { places: 9, bindings: {} };
let lastEventSeq = 0;

function hotkeyLabel(key) {
  return `Platz ${key}`;
}

async function refreshHotswap() {
  const d = await api("/api/hotswap");
  HOTSWAP = { places: d.places, bindings: d.bindings };
  renderHotswap();
}

function renderHotswap() {
  const grid = $("#hotswap-grid");
  grid.innerHTML = "";
  for (let i = 1; i <= HOTSWAP.places; i++) {
    const b = HOTSWAP.bindings[String(i)];
    const tile = document.createElement("div");
    tile.className = "slot-card hs-tile " + (b ? "filled" : "empty");

    if (b) {
      const isLoadout = b.type === "loadout";
      const count = isLoadout && LOADOUTS[b.name] ? `${LOADOUTS[b.name].length} Figuren` : null;
      const missing = isLoadout && !LOADOUTS[b.name];
      tile.innerHTML = `
        <div class="hs-key">${i}</div>
        <div class="hs-actions">
          <button data-act="assign" class="ghost" title="Ändern">✏️</button>
          <button data-act="clear" class="ghost" title="Platz leeren">✖</button>
        </div>
        <div class="slot-name">${isLoadout ? "💾 " : ""}${esc(isLoadout ? b.name : b.display)}</div>
        <div class="slot-chips">
          ${isLoadout
            ? (missing ? `<span class="chip">⚠ Loadout gelöscht</span>` : `<span class="chip">${count}</span>`)
            : elemChip(b.element)}
        </div>
        <div class="hs-hint mini-note">Tippen zum Laden ⚡</div>`;
      // Ganze Kachel = auslösen (ausser man trifft einen der kleinen Buttons)
      tile.addEventListener("click", (e) => {
        if (e.target.closest("button")) return;
        run(async () => {
          tile.classList.add("firing");
          const r = await api("/api/hotswap/trigger", { key: i });
          SLOTS = r.slots;
          renderSlots();
          await refreshLibrary(false);
          toast(`⚡ ${r.message}`);
        });
      });
      tile.querySelector('[data-act="assign"]').addEventListener("click", () => openHotswapPicker(i));
      tile.querySelector('[data-act="clear"]').addEventListener("click", () =>
        run(async () => {
          await api("/api/hotswap/clear", { key: i });
          await refreshHotswap();
        }));
    } else {
      tile.innerHTML = `
        <div class="hs-key">${i}</div>
        <button class="slot-empty-btn" data-act="assign">＋ Belegen</button>`;
      tile.querySelector('[data-act="assign"]').addEventListener("click", () => openHotswapPicker(i));
    }
    grid.appendChild(tile);
  }

  // Plätze hinzufügen / entfernen
  const ctrl = document.createElement("div");
  ctrl.className = "slot-card empty hs-controls";
  ctrl.innerHTML = `
    <button class="ghost" data-act="more">＋ Platz</button>
    <button class="ghost" data-act="less" ${HOTSWAP.places <= 1 ? "disabled" : ""}>− Platz</button>`;
  ctrl.querySelector('[data-act="more"]').addEventListener("click", () =>
    run(async () => {
      HOTSWAP.places = (await api("/api/hotswap/places", { count: HOTSWAP.places + 1 })).places;
      renderHotswap();
    }));
  ctrl.querySelector('[data-act="less"]').addEventListener("click", () =>
    run(async () => {
      HOTSWAP.places = (await api("/api/hotswap/places", { count: HOTSWAP.places - 1 })).places;
      renderHotswap();
    }));
  grid.appendChild(ctrl);
}

// Hotkey-Ereignisse (von der Tastatur ausgeloest) in der UI anzeigen
setInterval(() => {
  if (document.hidden) return;
  fetch("/api/hotswap/status")
    .then((r) => r.json())
    .then((d) => {
      if (d.event && d.event.seq !== lastEventSeq) {
        lastEventSeq = d.event.seq;
        toast(`⚡ ${d.event.message}`, !d.event.ok);
        refreshPortal().catch(() => {});
        refreshLibrary(false).catch(() => {});
      }
    })
    .catch(() => {});
}, 3000);

/* ================= Bibliothek ================= */

let LIBSOURCES = [];

async function refreshLibrary(render = true) {
  const d = await api("/api/library");
  LIB = d.files;
  LIBSOURCES = d.sources || [];
  renderSources();
  if (render) renderLibrary();
}

function renderSources() {
  const bar = $("#lib-sources");
  bar.innerHTML = "";
  LIBSOURCES.forEach((s) => {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.title = s.path;
    chip.innerHTML = `📁 ${esc(s.label)}`;
    if (s.removable) {
      const x = document.createElement("button");
      x.className = "ghost";
      x.style.cssText = "padding:0 4px;font-size:12px";
      x.textContent = "✕";
      x.title = `Quelle entfernen (Dateien bleiben in ${s.path})`;
      x.addEventListener("click", () =>
        run(async () => {
          await api("/api/library/sources", { remove: s.path });
          await refreshLibrary();
          toast(`Quelle „${s.label}" entfernt (Dateien bleiben erhalten).`);
        }));
      chip.appendChild(x);
    }
    bar.appendChild(chip);
  });
  const add = document.createElement("button");
  add.className = "ghost";
  add.textContent = "＋ Ordner verknüpfen";
  add.title = "Weiteren Ordner mit .sky-Dateien einbinden (ohne Kopieren)";
  add.addEventListener("click", () =>
    run(async () => {
      const p = prompt("Pfad zum Ordner mit .sky-Dateien:");
      if (!p) return;
      await api("/api/library/sources", { add: p });
      await refreshLibrary();
      toast("Ordner eingebunden.");
    }));
  bar.appendChild(add);
}

function renderLibrary() {
  const q = $("#lib-search").value.toLowerCase();
  const elem = $("#lib-elem").value;
  const cat = $("#lib-cat").value;
  const list = $("#lib-list");
  const files = LIB.filter((f) =>
    (f.display.toLowerCase().includes(q) || (f.folder || "").toLowerCase().includes(q)) &&
    (!elem || f.element === elem) &&
    (!cat || f.category === cat));

  if (!files.length) {
    list.innerHTML = `<div class="empty-state">
      ${LIB.length ? "Nichts gefunden." :
        "Noch keine Figuren in der Bibliothek.<br>Erstelle welche unter <b>🗂️ Alle Figuren</b> oder bau eine Kombi im <b>🔄 Swapper-Studio</b>."}
    </div>`;
    return;
  }

  list.innerHTML = "";
  let lastFolder = null;
  files.forEach((f) => {
    if (f.folder !== lastFolder) {
      lastFolder = f.folder;
      const h = document.createElement("div");
      h.className = "group-title";
      h.textContent = f.folder || "Allgemein";
      list.appendChild(h);
    }
    const row = document.createElement("div");
    row.className = "row";
    row.innerHTML = `
      <span class="name">${esc(f.display)}</span>
      ${elemChip(f.element)}${f.category ? chip(f.category) : ""}
      <span class="grow"></span>
      <span class="sub">${esc(f.filename)}</span>
      <span class="actions">
        <button data-act="portal">→ Portal</button>
        <button data-act="del" class="danger">🗑</button>
      </span>`;
    row.querySelector('[data-act="portal"]').addEventListener("click", () =>
      run(async () => {
        const r = await api("/api/portal/assign", { relpath: f.relpath });
        SLOTS = r.slots;
        renderSlots();
        toast(`${f.display} → Slot ${r.slot + 1}`);
      }));
    row.querySelector('[data-act="del"]').addEventListener("click", () =>
      run(async () => {
        if (!confirm(`„${f.display}" wirklich löschen? Spielstand auf der Figur geht verloren!`)) return;
        await api("/api/library/delete", { relpath: f.relpath });
        await refreshLibrary();
        await refreshPortal();
        toast("Gelöscht.");
      }));
    list.appendChild(row);
  });
}

$("#lib-search").addEventListener("input", renderLibrary);
$("#btn-lib-refresh").addEventListener("click", () => run(() => refreshLibrary()));

$("#btn-backup").addEventListener("click", () =>
  run(async () => {
    toast("💾 Backup läuft…");
    const r = await api("/api/backup", {});
    toast(`💾 ${r.figures} Figuren gesichert (${r.size_mb} MB): ${r.name}`
      + (r.skipped.length ? ` – ${r.skipped.length} übersprungen (gerade in RPCS3 geladen)` : ""));
  }));
$("#btn-backup-open").addEventListener("click", () => run(() => api("/api/backup/open", {})));

/* ================= Alle Figuren ================= */

function initFigureFilters() {
  const gameSel = $("#fig-game");
  Object.entries(DATA.games).forEach(([id, name]) => {
    const o = document.createElement("option");
    o.value = id;
    o.textContent = `Nutzbar in: ${name}`;
    gameSel.appendChild(o);
  });
  const cats = [...new Set(DATA.figures.map((f) => f.category))].sort();
  cats.forEach((c) => {
    const o = document.createElement("option");
    o.value = c;
    o.textContent = c;
    $("#fig-cat").appendChild(o);
  });
  DATA.elements.forEach((e) => {
    const o = document.createElement("option");
    o.value = e;
    o.textContent = e;
    $("#fig-elem").appendChild(o);
  });
  ["#fig-search", "#fig-game", "#fig-cat", "#fig-elem"].forEach((sel) =>
    $(sel).addEventListener("input", renderFigures));

  // Gleiche Filterlisten fuer Belegen-Dialog und Bibliothek
  const fill = (sel, values) => values.forEach((v) => {
    const o = document.createElement("option");
    o.value = v;
    o.textContent = v;
    $(sel).appendChild(o);
  });
  fill("#modal-elem", DATA.elements);
  fill("#modal-cat", cats);
  fill("#lib-elem", DATA.elements);
  fill("#lib-cat", cats);
  ["#modal-elem", "#modal-cat"].forEach((sel) =>
    $(sel).addEventListener("input", renderModalList));
  ["#lib-elem", "#lib-cat"].forEach((sel) =>
    $(sel).addEventListener("input", renderLibrary));
}

function renderFigures() {
  const q = $("#fig-search").value.toLowerCase();
  const game = Number($("#fig-game").value) || null;
  const cat = $("#fig-cat").value;
  const elem = $("#fig-elem").value;

  const hits = DATA.figures.filter((f) =>
    (!q || f.name.toLowerCase().includes(q)) &&
    (!game || f.games.includes(game)) &&
    (!cat || f.category === cat) &&
    (!elem || f.element === elem));

  $("#fig-count").textContent = `${hits.length} von ${DATA.figures.length} Figuren`;
  const list = $("#fig-list");
  list.innerHTML = "";

  if (!hits.length) {
    list.innerHTML = `<div class="empty-state">Keine Treffer.</div>`;
    return;
  }

  hits.forEach((f) => {
    const row = document.createElement("div");
    row.className = "row";
    const games = f.games.map((g) => GAME_SHORT[g]).join(" · ");
    row.innerHTML = `
      <span class="name">${esc(f.name)}</span>
      ${elemChip(f.element)}${chip(f.category)}
      <span class="grow"></span>
      <span class="sub" title="Nutzbar in diesen Spielen">${games}</span>
      <span class="actions">
        <button data-act="lib" title="In die Bibliothek legen">＋ Bibliothek</button>
        <button data-act="portal" title="In den nächsten freien Portal-Slot">→ Portal</button>
      </span>`;
    row.querySelector('[data-act="lib"]').addEventListener("click", () =>
      run(async () => {
        const r = await api("/api/library/create", { id: f.id, var: f.var });
        await refreshLibrary(false);
        renderLibrary();
        toast(`${f.name} in Bibliothek erstellt (${r.file.relpath})`);
      }));
    row.querySelector('[data-act="portal"]').addEventListener("click", () =>
      run(async () => {
        const r = await api("/api/portal/create", { id: f.id, var: f.var });
        SLOTS = r.slots;
        renderSlots();
        await refreshLibrary(false);
        toast(`${f.name} → Slot ${r.slot + 1}`);
      }));
    list.appendChild(row);
  });
}

/* ================= RPCS3 Auto-Inject ================= */

let INJECT = { available: false, rpcs3_running: false, auto_inject: false, busy: false };

function setRing(state) {
  const ring = document.querySelector(".portal-ring");
  if (!ring) return;
  ring.classList.toggle("off", state === "off");
  ring.classList.toggle("busy", state === "busy");
  ring.title = state === "busy" ? "Sende Skylander an RPCS3…"
    : state === "on" ? "RPCS3 verbunden – klicken zum Spielwechsel"
    : "RPCS3 läuft nicht – klicken zum Starten";
}

document.querySelector(".portal-ring").addEventListener("click", () =>
  run(() => openRpcs3Picker()));

async function refreshInjectStatus() {
  try {
    INJECT = await api("/api/inject/status");
  } catch {
    return;
  }
  setRing(!INJECT.available || !INJECT.rpcs3_running ? "off" : (INJECT.busy ? "busy" : "on"));
  if (INJECT.placement && INJECT.placement !== PLACEMENT) {
    PLACEMENT = INJECT.placement;
    updatePlacementSeg();
    renderSlots();
  }
  const st = $("#rpcs3-status");
  const cb = $("#auto-inject");
  cb.checked = INJECT.auto_inject;

  if (!INJECT.available) {
    st.className = "chip offline";
    st.innerHTML = `<span class="dot"></span> RPCS3-Steuerung aus (pywinauto fehlt)`;
    cb.disabled = true;
    $("#btn-inject-now").disabled = true;
    return;
  }
  cb.disabled = false;
  if (INJECT.rpcs3_running) {
    st.className = "chip online";
    st.innerHTML = `<span class="dot"></span> RPCS3 verbunden`;
    $("#btn-inject-now").disabled = false;
  } else {
    st.className = "chip offline";
    st.innerHTML = `<span class="dot"></span> RPCS3 nicht gefunden`;
    $("#btn-inject-now").disabled = true;
  }
}

$("#auto-inject").addEventListener("change", (e) =>
  run(async () => {
    const on = e.target.checked;
    await api("/api/inject/settings", { auto_inject: on });
    INJECT.auto_inject = on;
    toast(on
      ? "⚡ Direkt-Laden aktiv – Auswahl geht jetzt live nach RPCS3."
      : "Direkt-Laden aus – es wird nur der Portal-Ordner vorbereitet.");
  }));

$("#btn-inject-now").addEventListener("click", () =>
  run(async () => {
    const r = await api("/api/inject/now", {});
    toast(`⚡ ${r.message}`);
  }));

// RPCS3-Status pollen: schnell waehrend gesendet wird (Ring blinkt), sonst entspannt
let injectPollTimer = null;

async function pollInject() {
  if (!document.hidden) await refreshInjectStatus();
  clearTimeout(injectPollTimer);
  injectPollTimer = setTimeout(pollInject, INJECT.busy ? 700 : 3000);
}

function nudgeInjectPoll() {
  clearTimeout(injectPollTimer);
  injectPollTimer = setTimeout(pollInject, 300);
}

/* ================= Kopfzeile ================= */

$("#btn-open-portal").addEventListener("click", () => run(() => api("/api/open", { which: "portal" })));
$("#btn-open-lib").addEventListener("click", () => run(() => api("/api/open", { which: "library" })));

/* ================= Init ================= */

run(async () => {
  DATA = await api("/api/data");
  await Promise.all([refreshLibrary(false), refreshPortal(), refreshLoadouts()]);
  const status = await api("/api/hotswap/status");
  lastEventSeq = status.event ? status.event.seq : 0;
  await refreshHotswap();
  await pollInject();
  updatePlacementSeg();
  renderSlots();
  renderLibrary();
  renderSwapperGrids();
  renderSwapPreview();
  initFigureFilters();
  renderFigures();
});
