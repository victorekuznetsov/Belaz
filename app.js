/* Каталог запасных частей БЕЛАЗ — оболочка каталога.
   Данные: data/models.js (реестр), data/models/<id>.js (каталог машины),
   data/prices.js (цены по площадкам), data/fleet.js (парк машин).
   Внешних библиотек нет, всё работает и по file://. */
(function () {
"use strict";

var LIST    = window.MODEL_LIST || [];
var DOCS    = window.MODEL_DOCS || {};
var COMMON  = window.COMMON_DOCS || [];
var PRICES  = window.PRICES || { columns: [], okp: {}, des: {}, currency: "USD" };
var FLEET   = window.FLEET || [];
var DOCTOC  = window.DOCTOC || {};
var XREF    = window.XREF || {};
var COLS    = PRICES.columns || [];

var LS_CART  = "belaz_cart";
var LS_THEME = "belaz_theme";
var LS_MODEL = "belaz_model";
var LS_COL   = "belaz_price_col";

var state = {
  model: null,        // id текущей машины
  figure: null,       // код текущего рисунка
  sheet: 0,           // лист чертежа
  priceCol: 0,        // площадка, по которой считается заказ
  cart: {},           // ключ -> позиция заказа
  overrides: {},      // цены, загруженные пользователем из файла
  checkRows: []
};

/* ---------- мелкие помощники ---------- */
function $(id) { return document.getElementById(id); }
function el(tag, cls, text) {
  var n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
}
function show(node, on) { node.classList.toggle("hidden", !on); }
function esc(s) { return (s == null ? "" : String(s)); }
function normNo(s) { return esc(s).replace(/\s+/g, "").toUpperCase(); }
function fmtPrice(v) {
  if (v == null) return "—";
  return v.toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function partKey(p) { return (p.okp || "") + "|" + normNo(p.des); }

/* ---------- цены ---------- */
function priceRow(p) {
  var a = p.okp ? PRICES.okp[p.okp] : null;
  var b = p.des ? PRICES.des[normNo(p.des)] : null;
  var ov = state.overrides[p.okp] != null ? state.overrides[p.okp]
         : state.overrides[normNo(p.des)];
  if (!a && !b && ov == null) return null;
  var out = [];
  for (var i = 0; i < COLS.length; i++) {
    var v = (a && a[i] != null) ? a[i] : (b && b[i] != null ? b[i] : null);
    out.push(v);
  }
  if (ov != null) out[state.priceCol] = ov;
  return out;
}
function priceOf(p) {
  var row = priceRow(p);
  return row ? row[state.priceCol] : null;
}

/* ---------- загрузка каталогов ---------- */
function modelInfo(id) {
  for (var i = 0; i < LIST.length; i++) if (LIST[i].id === id) return LIST[i];
  return null;
}
function loadModel(id, cb) {
  if (window.MODELS && window.MODELS[id]) return cb(window.MODELS[id]);
  var s = document.createElement("script");
  s.src = "data/models/" + id + ".js";
  s.onload = function () { cb(window.MODELS[id]); };
  s.onerror = function () { cb(null); };
  document.head.appendChild(s);
}
function loadAll(cb) {
  var left = LIST.length;
  if (!left) return cb();
  LIST.forEach(function (m) {
    loadModel(m.id, function () { if (--left === 0) cb(); });
  });
}
function cur() { return (window.MODELS || {})[state.model] || null; }

/* индекс всех деталей всех загруженных машин */
function eachPart(fn) {
  var M = window.MODELS || {};
  Object.keys(M).forEach(function (id) {
    M[id].figures.forEach(function (f) {
      f.parts.forEach(function (p) { fn(p, f, M[id]); });
    });
  });
}

/* ---------- шапка и переключатель машин ---------- */
function buildModelSelect() {
  var sel = $("model-select");
  sel.innerHTML = "";
  var groups = [];
  LIST.forEach(function (m) {
    var g = groups.filter(function (x) { return x.name === m.group; })[0];
    if (!g) { g = { name: m.group, items: [] }; groups.push(g); }
    g.items.push(m);
  });
  groups.forEach(function (g) {
    var og = document.createElement("optgroup");
    og.label = g.name;
    g.items.forEach(function (m) {
      var o = document.createElement("option");
      o.value = m.id;
      o.textContent = m.name + " — " + m.subtitle;
      og.appendChild(o);
    });
    sel.appendChild(og);
  });
  sel.value = state.model;
  sel.onchange = function () { selectModel(sel.value); };
}

function renderPassport() {
  var m = cur(), info = modelInfo(state.model);
  var box = $("passport");
  box.innerHTML = "";
  if (!m) return;
  var parts = 0, sheets = 0;
  m.figures.forEach(function (f) { parts += f.parts.length; sheets += f.sheets.length; });
  var pairs = [
    ["Машина", info ? info.name : m.name],
    ["Разделов", m.sections.length],
    ["Рисунков", m.figures.length],
    ["Чертежей", sheets],
    ["Позиций", parts],
    ["Источник", m.source]
  ];
  pairs.forEach(function (kv) {
    var b = el("span", "pp");
    b.appendChild(el("span", "pp-k", kv[0] + ": "));
    b.appendChild(el("b", null, String(kv[1])));
    box.appendChild(b);
  });
  var sel = el("span", "pp pp-col");
  sel.appendChild(el("span", "pp-k", "Цены для заказа: "));
  var s = document.createElement("select");
  s.id = "price-col";
  COLS.forEach(function (c, i) {
    var o = document.createElement("option");
    o.value = String(i);
    o.textContent = c.label + " — " + c.title;
    s.appendChild(o);
  });
  s.value = String(state.priceCol);
  s.onchange = function () {
    state.priceCol = +s.value;
    try { localStorage.setItem(LS_COL, s.value); } catch (e) {}
    if (state.figure) openFigure(state.figure);
    renderCart();
  };
  sel.appendChild(s);
  box.appendChild(sel);
}

/* ---------- дерево разделов ---------- */
function buildTree() {
  var m = cur(), tree = $("tree");
  tree.innerHTML = "";
  if (!m) return;
  m.sections.forEach(function (sec) {
    var figs = m.figures.filter(function (f) { return f.section === sec.code; });
    if (!figs.length) return;
    var wrap = el("div", "tree-sys");
    var head = el("div", "tree-sys-head");
    head.appendChild(el("span", null, sec.code + "  " + (sec.ru || sec.en)));
    head.appendChild(el("span", "cnt", figs.length + " рис."));
    var body = el("div", "tree-opts");
    head.onclick = function () { wrap.classList.toggle("open"); };
    figs.forEach(function (f) {
      var a = el("div", "tree-opt");
      a.appendChild(el("span", null, f.ru || f.en));
      a.appendChild(el("span", "no", (m.figureWord || "Рисунок").toLowerCase() +
                                     " " + f.code + (f.desig ? " · " + f.desig : "")));
      a.dataset.code = f.code;
      a.onclick = function (e) { e.stopPropagation(); openFigure(f.code); };
      body.appendChild(a);
    });
    wrap.appendChild(head);
    wrap.appendChild(body);
    tree.appendChild(wrap);
  });
}
function highlightTree(code) {
  Array.prototype.forEach.call(document.querySelectorAll(".tree-opt"), function (n) {
    n.classList.toggle("active", n.dataset.code === code);
  });
  var active = document.querySelector(".tree-opt.active");
  if (active) {
    active.parentNode.parentNode.classList.add("open");
    active.scrollIntoView({ block: "nearest" });
  }
}

/* ---------- вид «рисунок» ---------- */
function views(which) {
  show($("view-welcome"), which === "welcome");
  show($("view-search"), which === "search");
  show($("view-figure"), which === "figure");
}
function figureBy(code) {
  var m = cur();
  if (!m) return null;
  return m.figures.filter(function (f) { return f.code === code; })[0] || null;
}
function partsHead() {
  var tr = $("parts-head");
  tr.innerHTML = "";
  [["c-pos", "№"], ["c-no", "Обозначение"], ["c-no", "Код ОКП"], ["c-name", "Наименование"]]
    .forEach(function (c) { var th = el("th", c[0], c[1]); tr.appendChild(th); });
  COLS.forEach(function (c, i) {
    var th = el("th", "c-price" + (i === state.priceCol ? " c-price-active" : ""), c.label);
    th.title = c.title + " · " + (c.note || "");
    tr.appendChild(th);
  });
  tr.appendChild(el("th", "c-qty", "Кол-во"));
  tr.appendChild(el("th", "c-need", "Нужно"));
  tr.appendChild(el("th", "c-add", ""));
}
function openFigure(code) {
  var m = cur(), f = figureBy(code);
  if (!f) return;
  state.figure = code;
  state.sheet = 0;
  views("figure");
  highlightTree(code);

  var sec = m.sections.filter(function (s) { return s.code === f.section; })[0];
  var word = m.figureWord || "Рисунок";
  $("fig-name").textContent = word + " " + f.code + ". " + (f.ru || f.en);
  var meta = [];
  if (f.desig) meta.push("Обозначение узла: " + f.desig);
  if (sec) meta.push("Раздел " + sec.code + " · " + (sec.ru || sec.en));
  if (f.en) meta.push(f.en);
  $("fig-meta").textContent = meta.join("  ·  ");

  renderFigureLinks(f.section);

  renderSheets(f);
  partsHead();
  var body = $("parts-body");
  body.innerHTML = "";
  f.parts.forEach(function (p) { body.appendChild(partRow(p, f)); });
}
/* Сноски на техническую документацию: раздел каталога -> глава руководства */
function renderFigureLinks(section) {
  var box = $("fig-links");
  box.innerHTML = "";
  var links = ((XREF[state.model] || {})[section]) || [];
  links.forEach(function (l) {
    var b = el("button", "btn-tool", "📖 " + shortDoc(l.label) + ": гл. " + l.chapter);
    b.title = l.label + " · глава " + l.chapter + " «" + l.title + "», стр. " + l.page;
    b.onclick = function () { openViewer(l.label, l.doc, l.page); };
    box.appendChild(b);
  });
  if (!links.length && (DOCS[state.model] || []).length) {
    var d = el("button", "btn-tool", "📖 Документация машины");
    d.onclick = openDocs;
    box.appendChild(d);
  }
}
function shortDoc(label) {
  if (/ремонт/i.test(label)) return "Руководство по ремонту";
  if (/эксплуатац/i.test(label)) return "Руководство по эксплуатации";
  return label;
}

function renderSheets(f) {
  var img = $("drawing"), car = $("carousel"), pane = $("drawing-pane");
  if (!f.sheets.length) {
    img.removeAttribute("src");
    pane.classList.add("no-drawing");
    $("drawing-hint").textContent = "Чертёж для этого рисунка в каталоге отсутствует";
    show(car, false);
    return;
  }
  pane.classList.remove("no-drawing");
  img.src = f.sheets[state.sheet];
  img.alt = "Чертёж: " + (f.ru || f.en);
  show(car, f.sheets.length > 1);
  $("sheet-label").textContent = "Лист " + (state.sheet + 1) + " из " + f.sheets.length;
  $("drawing-hint").textContent = "Номер на чертеже = номер позиции в таблице. Щелчок по чертежу — открыть в полном размере.";
  img.onclick = function () { window.open(f.sheets[state.sheet], "_blank"); };
  $("sheet-prev").onclick = function () {
    state.sheet = (state.sheet - 1 + f.sheets.length) % f.sheets.length; renderSheets(f);
  };
  $("sheet-next").onclick = function () {
    state.sheet = (state.sheet + 1) % f.sheets.length; renderSheets(f);
  };
}
function partRow(p, f) {
  var tr = el("tr");
  tr.appendChild(el("td", "c-pos", p.pos));

  var tdDes = el("td", "c-no");
  if (p.des) {
    var a = el("span", "pn pn-link", p.des);
    a.onclick = function () { openPart(p, f); };
    tdDes.appendChild(a);
  } else tdDes.appendChild(el("span", "dim", "—"));
  if (p.x) {
    var ch = el("span", "chip-sup", "взаимозам.");
    ch.title = "Взаимозаменяемая деталь (отмечена «*» в заводском каталоге)";
    tdDes.appendChild(ch);
  }
  tr.appendChild(tdDes);

  var tdOkp = el("td", "c-no");
  if (p.okp) {
    var b = el("span", "pn pn-link", p.okp);
    b.onclick = function () { openPart(p, f); };
    tdOkp.appendChild(b);
  } else tdOkp.appendChild(el("span", "dim", "—"));
  tr.appendChild(tdOkp);

  var tdName = el("td", "c-name");
  tdName.appendChild(el("div", null, p.ru || p.en));
  if (p.ru && p.en) tdName.appendChild(el("div", "sub", p.en));
  tr.appendChild(tdName);

  var row = priceRow(p);
  COLS.forEach(function (c, i) {
    var td = el("td", "c-price", row && row[i] != null ? fmtPrice(row[i]) : "—");
    if (row && row[i] != null) td.title = c.title + ", " + PRICES.currency;
    if (i === state.priceCol) td.classList.add("c-price-active");
    tr.appendChild(td);
  });

  tr.appendChild(el("td", "c-qty", p.qty || "—"));

  var tdNeed = el("td", "c-need");
  var inp = document.createElement("input");
  inp.type = "number"; inp.min = "1"; inp.value = p.qty && /^\d+$/.test(p.qty) ? p.qty : "1";
  inp.className = "need-input";
  tdNeed.appendChild(inp);
  tr.appendChild(tdNeed);

  var tdAdd = el("td", "c-add");
  var btn = el("button", "btn-add", "＋");
  btn.title = "Добавить в заказ";
  btn.onclick = function () { addToCart(p, f, Math.max(1, +inp.value || 1)); };
  tdAdd.appendChild(btn);
  tr.appendChild(tdAdd);
  return tr;
}

/* ---------- карточка детали ---------- */
function whereUsed(p) {
  var out = [];
  eachPart(function (q, f, m) {
    if (partKey(q) === partKey(p)) {
      out.push({ model: m, fig: f, pos: q.pos, qty: q.qty });
    }
  });
  return out;
}
function openPart(p, f) {
  $("pc-title").textContent = p.des || p.okp || "Деталь";
  $("pc-name").textContent = (p.ru || "") + (p.en ? " · " + p.en : "");

  var nos = $("pc-nos-body");
  nos.innerHTML = "";
  [["Обозначение БЕЛАЗ", p.des || "—"], ["Код ОКП", p.okp || "—"],
   ["Кол-во на рисунке", p.qty || "—"],
   ["Взаимозаменяемая", p.x ? "да" : "нет"]].forEach(function (kv) {
    var tr = el("tr");
    tr.appendChild(el("td", "pc-k", kv[0]));
    tr.appendChild(el("td", null, kv[1]));
    nos.appendChild(tr);
  });

  var row = priceRow(p), pb = $("pc-prices-body");
  pb.innerHTML = "";
  show($("pc-prices"), !!row);
  if (row) {
    COLS.forEach(function (c, i) {
      var tr = el("tr");
      tr.appendChild(el("td", "pc-k", c.label + " · " + c.title));
      tr.appendChild(el("td", null, row[i] != null ? fmtPrice(row[i]) + " " + PRICES.currency : "—"));
      pb.appendChild(tr);
    });
  }

  var used = whereUsed(p), ub = $("pc-used-body");
  ub.innerHTML = "";
  show($("pc-used"), used.length > 0);
  used.forEach(function (u) {
    var a = el("div", "r-where",
      u.model.name + " · " + (u.model.figureWord || "рисунок").toLowerCase() + " " +
      u.fig.code + " «" + (u.fig.ru || u.fig.en) + "», поз. " + u.pos);
    a.onclick = function () {
      closePart();
      selectModel(u.model.id, function () { openFigure(u.fig.code); });
    };
    ub.appendChild(a);
  });

  show($("part-card"), true);
  show($("part-overlay"), true);
}
function closePart() { show($("part-card"), false); show($("part-overlay"), false); }

/* ---------- поиск ---------- */
function runSearch(q) {
  q = q.trim();
  if (!q) { views(state.figure ? "figure" : "welcome"); return; }
  var needle = q.toLowerCase(), nno = normNo(q);
  var hits = [];
  eachPart(function (p, f, m) {
    var hit = (p.okp && p.okp.indexOf(nno) >= 0)
           || (p.des && normNo(p.des).indexOf(nno) >= 0)
           || (p.ru && p.ru.toLowerCase().indexOf(needle) >= 0)
           || (p.en && p.en.toLowerCase().indexOf(needle) >= 0);
    if (hit) hits.push({ p: p, f: f, m: m });
  });
  views("search");
  $("search-title").textContent = "Найдено позиций: " + hits.length + " по запросу «" + q + "»";
  var box = $("search-results");
  box.innerHTML = "";
  hits.slice(0, 400).forEach(function (h) {
    var r = el("div", "search-hit");
    var head = el("div");
    head.appendChild(el("b", "pn", h.p.des || h.p.okp));
    if (h.p.des && h.p.okp) head.appendChild(el("span", "dim", "  ОКП " + h.p.okp));
    head.appendChild(el("span", null, "  " + (h.p.ru || h.p.en)));
    r.appendChild(head);
    var pr = priceOf(h.p);
    r.appendChild(el("div", "sub",
      h.m.name + " · рисунок " + h.f.code + " «" + (h.f.ru || h.f.en) + "», поз. " + h.p.pos +
      (pr != null ? "  ·  " + COLS[state.priceCol].label + " " + fmtPrice(pr) + " " + PRICES.currency : "")));
    r.onclick = function () { selectModel(h.m.id, function () { openFigure(h.f.code); }); };
    box.appendChild(r);
  });
  if (hits.length > 400) box.appendChild(el("div", "sub", "Показаны первые 400 совпадений — уточните запрос."));
}

/* ---------- заказ ---------- */
function loadCart() {
  try { state.cart = JSON.parse(localStorage.getItem(LS_CART) || "{}"); }
  catch (e) { state.cart = {}; }
}
function saveCart() {
  try { localStorage.setItem(LS_CART, JSON.stringify(state.cart)); } catch (e) {}
}
function addToCart(p, f, n) {
  var k = partKey(p);
  var it = state.cart[k];
  if (it) it.n += n;
  else state.cart[k] = { des: p.des, okp: p.okp, name: p.ru || p.en, n: n,
                         model: state.model, fig: f.code, pos: p.pos };
  saveCart(); renderCart();
}
function renderCart() {
  var body = $("cart-body"), keys = Object.keys(state.cart);
  body.innerHTML = "";
  $("cart-count").textContent = String(keys.length);
  show($("cart-empty"), keys.length === 0);
  var total = 0, known = false;
  keys.forEach(function (k) {
    var it = state.cart[k];
    var price = priceOf({ okp: it.okp, des: it.des });
    var sum = price != null ? price * it.n : null;
    if (sum != null) { total += sum; known = true; }
    var tr = el("tr");
    tr.appendChild(el("td", "pn", it.des || "—"));
    tr.appendChild(el("td", "pn", it.okp || "—"));
    tr.appendChild(el("td", null, it.name));
    var tdn = el("td");
    var inp = document.createElement("input");
    inp.type = "number"; inp.min = "1"; inp.value = it.n; inp.className = "need-input";
    inp.onchange = function () { it.n = Math.max(1, +inp.value || 1); saveCart(); renderCart(); };
    tdn.appendChild(inp);
    tr.appendChild(tdn);
    tr.appendChild(el("td", null, sum != null ? fmtPrice(sum) : "—"));
    var tdx = el("td");
    var x = el("button", "btn-plain", "✕");
    x.onclick = function () { delete state.cart[k]; saveCart(); renderCart(); };
    tdx.appendChild(x);
    tr.appendChild(tdx);
    body.appendChild(tr);
  });
  $("cart-total").textContent = known ? fmtPrice(total) : "—";
  $("cart-total-cur").textContent = PRICES.currency;
  $("cart-total-col").textContent = COLS.length ? COLS[state.priceCol].label : "";
  var info = modelInfo(state.model);
  $("cart-model").textContent = info ? info.name : "";
}

/* ---------- выгрузка ---------- */
function download(name, text) {
  var blob = new Blob(["﻿" + text], { type: "text/csv;charset=utf-8;" });
  var a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
}
function csvCell(v) {
  var s = esc(v);
  return /[";\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
}
function csv(rows) {
  return rows.map(function (r) { return r.map(csvCell).join(";"); }).join("\r\n");
}
function exportParts(models, fname) {
  var head = ["Машина", "Раздел", "Рисунок", "Наименование рисунка", "Поз.",
              "Обозначение", "Код ОКП", "Кол-во", "Наименование", "Наименование (англ.)"];
  COLS.forEach(function (c) { head.push(c.label + ", " + PRICES.currency); });
  var rows = [head];
  models.forEach(function (m) {
    m.figures.forEach(function (f) {
      f.parts.forEach(function (p) {
        var pr = priceRow(p) || [];
        var r = [m.name, f.section, f.code, f.ru || f.en, p.pos, p.des, p.okp,
                 p.qty, p.ru, p.en];
        COLS.forEach(function (_c, i) { r.push(pr[i] != null ? String(pr[i]).replace(".", ",") : ""); });
        rows.push(r);
      });
    });
  });
  download(fname, csv(rows));
}

/* ---------- проверка списка ---------- */
function runCheck() {
  var raw = $("check-input").value || "";
  var tokens = raw.split(/[\s,;]+/).map(normNo).filter(Boolean);
  var index = {};
  eachPart(function (p, f, m) {
    [p.okp, normNo(p.des)].forEach(function (k) {
      if (!k) return;
      (index[k] = index[k] || []).push({ p: p, f: f, m: m });
    });
  });
  var rows = [], found = 0;
  tokens.forEach(function (t) {
    var hit = index[t];
    if (hit) found++;
    rows.push({ q: t, hits: hit || [] });
  });
  state.checkRows = rows;
  $("check-summary").textContent =
    "Проверено номеров: " + tokens.length + " · найдено в каталоге: " + found +
    " · не найдено: " + (tokens.length - found);
  var box = $("check-results");
  box.innerHTML = "";
  rows.forEach(function (r) {
    var d = el("div", "search-hit" + (r.hits.length ? "" : " miss"));
    d.appendChild(el("b", "pn", r.q));
    if (r.hits.length) {
      var h = r.hits[0];
      d.appendChild(el("span", null, "  " + (h.p.ru || h.p.en)));
      d.appendChild(el("div", "sub", h.m.name + " · рисунок " + h.f.code + ", поз. " + h.p.pos +
        (r.hits.length > 1 ? "  (и ещё " + (r.hits.length - 1) + " применений)" : "")));
      d.onclick = function () { selectModel(h.m.id, function () { openFigure(h.f.code); }); };
    } else {
      d.appendChild(el("span", "dim", "  — в каталоге не найден"));
    }
    box.appendChild(d);
  });
  $("check-dl").disabled = rows.length === 0;
}
function exportCheck() {
  var head = ["Запрошенный номер", "Найден", "Машина", "Рисунок", "Поз.",
              "Обозначение", "Код ОКП", "Наименование"];
  COLS.forEach(function (c) { head.push(c.label + ", " + PRICES.currency); });
  var rows = [head];
  state.checkRows.forEach(function (r) {
    if (!r.hits.length) { rows.push([r.q, "нет", "", "", "", "", "", ""]); return; }
    r.hits.forEach(function (h) {
      var pr = priceRow(h.p) || [];
      var row = [r.q, "да", h.m.name, h.f.code, h.p.pos, h.p.des, h.p.okp, h.p.ru];
      COLS.forEach(function (_c, i) { row.push(pr[i] != null ? String(pr[i]).replace(".", ",") : ""); });
      rows.push(row);
    });
  });
  download("belaz-check-list.csv", csv(rows));
}

/* ---------- цены из файла ---------- */
function applyPriceFile(text) {
  var lines = text.split(/\r?\n/), n = 0;
  lines.forEach(function (line) {
    if (!line.trim()) return;
    var cells = line.split(/[;\t,]/);
    if (cells.length < 2) return;
    var key = normNo(cells[0]);
    var val = parseFloat(String(cells[cells.length - 1]).replace(/\s/g, "").replace(",", "."));
    if (!key || isNaN(val)) return;
    state.overrides[key] = val;
    n++;
  });
  alert("Загружено цен: " + n + ".\nОни подставлены в колонку «" +
        (COLS[state.priceCol] || {}).label + "».");
  if (state.figure) openFigure(state.figure);
  renderCart();
}

/* ---------- парк машин ---------- */
function renderFleet(q) {
  q = (q || "").trim().toLowerCase();
  var rows = FLEET.filter(function (m) {
    if (!q) return true;
    var hay = [m.owner, m.park, m.brand, m.model, m.type, m.gar, m.vin, m.year]
      .concat(m.engines.map(function (e) { return e.model + " " + e.sn; })).join(" ").toLowerCase();
    return hay.indexOf(q) >= 0;
  });
  $("fleet-summary").textContent = "Машин: " + rows.length + " из " + FLEET.length;
  var box = $("fleet-results");
  box.innerHTML = "";
  rows.forEach(function (m) {
    var d = el("div", "search-hit");
    var head = el("div");
    head.appendChild(el("b", null, m.brand + "-" + m.model + " №" + m.gar));
    head.appendChild(el("span", "dim", "  " + m.type));
    d.appendChild(head);
    var line = m.owner + (m.park ? " · " + m.park : "");
    if (m.vin) line += " · зав. № " + m.vin;
    if (m.year) line += " · " + m.year + " г.";
    if (m.engines.length) {
      line += " · ДВС " + m.engines.map(function (e) {
        return e.model + (e.sn ? " №" + e.sn : "");
      }).join(", ");
    }
    d.appendChild(el("div", "sub", line));
    var target = catalogFor(m);
    if (target) {
      var go = el("button", "btn", "Каталог " + (modelInfo(target) || {}).name);
      go.onclick = function () {
        closePanels();
        selectModel(target);
        $("serial").value = m.vin || m.gar;
      };
      d.appendChild(go);
    } else {
      d.appendChild(el("div", "dim", "Каталога на эту модель в подборке нет"));
    }
    box.appendChild(d);
  });
}
function catalogFor(m) {
  var key = (m.brand + "-" + m.model).toUpperCase();
  var map = {
    "БЕЛАЗ-7513Т": "belaz7513t",
    "БЕЛАЗ-7555В": "belaz7555b",
    "БЕЛАЗ-76131": "belaz76131",
    "ПЩК-7547": "pshk7547",
    "БЕЛАЗ-7547": "pshk7547"
  };
  var id = map[key];
  return id && modelInfo(id) ? id : null;
}

/* ---------- документы ---------- */
function openDocs() {
  var box = $("docs-body");
  box.innerHTML = "";
  var info = modelInfo(state.model);
  var own = DOCS[state.model] || [];
  box.appendChild(el("p", "check-hint",
    "Руководства по эксплуатации и ремонту. PDF открываются во встроенном просмотрщике."));
  function group(title, items) {
    if (!items.length) return;
    box.appendChild(el("div", "sidebar-head", title));
    items.forEach(function (d) {
      var r = el("div", "search-hit");
      r.appendChild(el("b", null, d.label));
      r.appendChild(el("div", "sub", d.kind === "pdf" ? "PDF · открыть в просмотрщике"
                                                      : "Файл · скачать"));
      r.onclick = function () {
        if (d.kind === "pdf") openViewer(d.label, d.file);
        else window.open(d.file, "_blank");
      };
      box.appendChild(r);
    });
  }
  group("По машине " + (info ? info.name : ""), own);
  group("Прочие руководства БЕЛАЗ", COMMON);
  if (!own.length && !COMMON.length) box.appendChild(el("p", "dim", "Документов нет."));
  closePanels();
  show($("docs-panel"), true);
  show($("docs-overlay"), true);
}
function openViewer(title, file, page) {
  $("viewer-title").textContent = title;
  $("viewer-frame").src = file + (page ? "#page=" + page : "");
  $("viewer-open").href = file;
  var sel = $("viewer-toc"), toc = DOCTOC[file] || [];
  sel.innerHTML = "";
  sel.parentNode.style.display = toc.length ? "" : "none";
  toc.forEach(function (c) {
    var o = document.createElement("option");
    o.value = String(c.page);
    o.textContent = c.n + ". " + c.title;
    sel.appendChild(o);
  });
  if (page) sel.value = String(page);
  sel.onchange = function () { $("viewer-frame").src = file + "#page=" + sel.value; };
  closePanels();
  show($("viewer"), true);
}

/* ---------- панели ---------- */
function closePanels() {
  ["part-card", "check-panel", "fleet-panel", "docs-panel", "cart"].forEach(function (id) {
    show($(id), false);
  });
  ["part-overlay", "check-overlay", "fleet-overlay", "docs-overlay", "cart-overlay"]
    .forEach(function (id) { show($(id), false); });
}
/* Заказ живёт в <aside id="cart">, остальные панели — в <aside id="<имя>-panel"> */
function panelNode(name) { return $(name === "cart" ? "cart" : name + "-panel"); }
function panel(name, on) {
  closePanels();
  if (on) { show(panelNode(name), true); show($(name + "-overlay"), true); }
}

/* ---------- выбор машины ---------- */
function selectModel(id, cb) {
  loadModel(id, function (m) {
    if (!m) { alert("Каталог машины не загрузился."); return; }
    state.model = id;
    state.figure = null;
    try { localStorage.setItem(LS_MODEL, id); } catch (e) {}
    $("model-select").value = id;
    renderPassport();
    buildTree();
    views("welcome");
    renderCart();
    if (cb) cb();
  });
}

/* ---------- запуск ---------- */
function init() {
  if (!LIST.length) { document.body.innerHTML = "<p>Каталог пуст.</p>"; return; }
  try {
    var c = localStorage.getItem(LS_COL);
    if (c != null && COLS[+c]) state.priceCol = +c;
  } catch (e) {}
  loadCart();

  var saved = null;
  try { saved = localStorage.getItem(LS_MODEL); } catch (e) {}
  state.model = (saved && modelInfo(saved)) ? saved : LIST[0].id;
  buildModelSelect();
  selectModel(state.model, function () {
    loadAll(function () { /* остальные каталоги — для сквозного поиска */ });
  });

  $("theme-toggle").onclick = function () {
    var t = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", t);
    try { localStorage.setItem(LS_THEME, t); } catch (e) {}
  };

  var s = $("search"), timer = null;
  s.oninput = function () {
    clearTimeout(timer);
    timer = setTimeout(function () { runSearch(s.value); }, 180);
  };
  $("search-clear").onclick = function () { s.value = ""; runSearch(""); };

  $("cart-toggle").onclick = function () { panel("cart", $("cart").classList.contains("hidden")); };
  $("cart-toggle").title = "Показать заказ";
  $("cart-close").onclick = closePanels;
  $("cart-overlay").onclick = closePanels;
  $("cart-clear").onclick = function () {
    if (confirm("Очистить заказ?")) { state.cart = {}; saveCart(); renderCart(); }
  };
  $("cart-print").onclick = function () { window.print(); };
  $("cart-csv").onclick = function () {
    var head = ["Обозначение", "Код ОКП", "Наименование", "Кол-во",
                "Цена (" + COLS[state.priceCol].label + "), " + PRICES.currency, "Сумма"];
    var rows = [["Машина", modelInfo(state.model).name, "Номер машины", $("serial").value || "", "", ""], head];
    Object.keys(state.cart).forEach(function (k) {
      var it = state.cart[k];
      var pr = priceOf({ okp: it.okp, des: it.des });
      rows.push([it.des, it.okp, it.name, it.n,
                 pr != null ? String(pr).replace(".", ",") : "",
                 pr != null ? String(pr * it.n).replace(".", ",") : ""]);
    });
    download("belaz-order.csv", csv(rows));
  };

  $("check-list").onclick = function () { panel("check", $("check-panel").classList.contains("hidden")); };
  $("check-close").onclick = closePanels;
  $("check-overlay").onclick = closePanels;
  $("check-run").onclick = runCheck;
  $("check-reset").onclick = function () {
    $("check-input").value = ""; $("check-results").innerHTML = "";
    $("check-summary").textContent = ""; $("check-dl").disabled = true;
  };
  $("check-dl").onclick = exportCheck;
  $("check-file-btn").onclick = function () { $("check-file").click(); };
  $("check-file").onchange = function (e) {
    var f = e.target.files[0]; if (!f) return;
    var r = new FileReader();
    r.onload = function () { $("check-input").value = r.result; runCheck(); };
    r.readAsText(f, "utf-8");
  };

  $("fleet-toggle").onclick = function () {
    var on = $("fleet-panel").classList.contains("hidden");
    panel("fleet", on);
    if (on) renderFleet($("fleet-search").value);
  };
  $("fleet-close").onclick = closePanels;
  $("fleet-overlay").onclick = closePanels;
  $("fleet-search").oninput = function () { renderFleet(this.value); };

  $("docs-toggle").onclick = function () {
    if ($("docs-panel").classList.contains("hidden")) openDocs(); else closePanels();
  };
  $("docs-close").onclick = closePanels;
  $("docs-overlay").onclick = closePanels;
  $("viewer-close").onclick = function () {
    show($("viewer"), false); $("viewer-frame").src = "about:blank";
  };

  $("update-prices").onclick = function () { $("price-file").click(); };
  $("price-file").onchange = function (e) {
    var f = e.target.files[0]; if (!f) return;
    var r = new FileReader();
    r.onload = function () { applyPriceFile(r.result); };
    r.readAsText(f, "utf-8");
  };

  $("pc-close").onclick = closePart;
  $("part-overlay").onclick = closePart;

  $("dl-model").onclick = function () {
    var m = cur(); if (m) exportParts([m], "belaz-" + m.id + ".csv");
  };
  $("dl-all").onclick = function () {
    loadAll(function () {
      var M = window.MODELS || {};
      exportParts(Object.keys(M).map(function (k) { return M[k]; }), "belaz-all-catalogs.csv");
    });
  };

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") { closePanels(); show($("viewer"), false); }
  });
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
else init();
})();
