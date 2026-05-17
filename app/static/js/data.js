/* ═══════════════════════════════════════════════════════
   BiciMAD · Capa de datos unificada
   ═══════════════════════════════════════════════════════ */

// ─── Configuración visual (ind1) ────────────────────────
var DOT_SIZE = 4;
var T_FULL  = 0.65;
var T_EMPTY = 0.35;

var DAY_KEYS  = ["L","M","X","J","V","S","D"];
var DAY_NAMES = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"];

// ─── Base URLs ──────────────────────────────────────────
var API_IND1 = "/api/ind1";
var API_IND2 = "/api/ind2";
var API_IND3 = "/api/ind3";

// ═══════════════════════════════════════════════════════
// INDICADOR 1 — Saturación
// ═══════════════════════════════════════════════════════
var _stations   = [];
var _satData    = {};
var _currentKey = null;
var _dateRange  = { min: "2019-05-01", max: "2019-05-31" };
var _availableMonths = [];

async function loadStations() {
  var res = await fetch(API_IND1 + "/stations");
  if (!res.ok) throw new Error("Error cargando estaciones: " + res.status);
  _stations = await res.json();
  return _stations;
}

async function loadDateRange() {
  var res = await fetch(API_IND1 + "/date-range");
  if (!res.ok) return;
  _dateRange = await res.json();
  return _dateRange;
}

async function loadAvailableMonths() {
  var res = await fetch(API_IND1 + "/available-months");
  if (!res.ok) return [];
  _availableMonths = await res.json();
  return _availableMonths;
}

async function loadSaturation(params) {
  var url, cacheKey;
  if (params.date) {
    url = API_IND1 + "/saturation-date?date=" + params.date;
    cacheKey = "date:" + params.date;
  } else {
    var dt  = params.dayType || "L";
    var hol = params.holiday ? "true" : "false";
    var month = params.month ? String(params.month) : "";
    url = API_IND1 + "/saturation?dayType=" + dt + "&holiday=" + hol;
    cacheKey = "day:" + dt + ":" + hol;
    if (month) { url += "&month=" + month; cacheKey += ":m" + month; }
  }
  if (cacheKey === _currentKey) return _satData;
  var res = await fetch(url);
  if (!res.ok) throw new Error("Error cargando saturación: " + res.status);
  _satData    = await res.json();
  _currentKey = cacheKey;
  return _satData;
}

async function checkHoliday(dateStr) {
  var res = await fetch(API_IND1 + "/is-holiday?date=" + dateStr);
  if (!res.ok) return false;
  var data = await res.json();
  return data.holiday;
}

function getSat(station, hour) {
  var arr = _satData[String(station.id)];
  if (!arr) return 0.5;
  var val = arr[hour];
  return val !== null && val !== undefined ? val : 0.5;
}

function dotColor(sat) {
  if (sat > T_FULL)  return "#2B5CF6";
  if (sat < T_EMPTY) return "#E8421A";
  return "#B0A99E";
}

function hLabel(h) { return String(h).padStart(2,"0") + ":00"; }
function hCtx(h) {
  if (h < 6)  return "Madrugada";
  if (h < 9)  return "Primera mañana";
  if (h < 12) return "Mañana";
  if (h < 14) return "Mediodía";
  if (h < 17) return "Tarde temprana";
  if (h < 21) return "Tarde";
  if (h < 23) return "Noche temprana";
  return "Noche";
}

// ═══════════════════════════════════════════════════════
// INDICADOR 2 — Tránsito
// ═══════════════════════════════════════════════════════
var _ind2Categories = [];
var _ind2Cells      = [];
var _ind2Stats      = null;
var _ind2UserColors = {};

function fmtKm(meters) {
  if (meters >= 1e6) return (meters / 1e6).toFixed(2) + " Mkm";
  if (meters >= 1e3) return (meters / 1e3).toFixed(1) + " km";
  return Math.round(meters) + " m";
}
function fmtPct(x) { return Number(x).toFixed(1) + "%"; }
function getInd2Color(code) { return _ind2UserColors[code] || "#999"; }

async function loadInd2Data() {
  var [cats, cells, stats] = await Promise.all([
    fetch(API_IND2 + "/categories/intensity").then(function(r){ return r.json(); }),
    fetch(API_IND2 + "/cells").then(function(r){ return r.json(); }),
    fetch(API_IND2 + "/stats").then(function(r){ return r.json(); }),
  ]);
  _ind2Categories = cats;
  _ind2Cells      = cells;
  _ind2Stats      = stats;
  cats.forEach(function(c){ _ind2UserColors[c.category_code] = c.color_hex; });
  return { cats: cats, cells: cells, stats: stats };
}

async function loadInd2CellDetail(cellId) {
  return fetch(API_IND2 + "/cells/" + cellId).then(function(r){ return r.json(); });
}

async function loadInd2CellWays(cellId) {
  return fetch(API_IND2 + "/cells/" + cellId + "/ways").then(function(r){ return r.json(); });
}

async function loadInd2CellRoutes(cellId) {
  return fetch(API_IND2 + "/cells/" + cellId + "/routes").then(function(r){ return r.json(); });
}

// ═══════════════════════════════════════════════════════
// INDICADOR 3 — Captura intermodal
// ═══════════════════════════════════════════════════════
var _ind3Nodes    = [];
var _ind3Stats    = null;
var _ind3Config   = null;

async function loadInd3Config() {
  try {
    _ind3Config = await fetch(API_IND3 + "/config").then(function(r){ return r.json(); });
  } catch(e) {
    _ind3Config = { radii: [150,300,500], default_radius: 150 };
  }
  return _ind3Config;
}

async function loadInd3Data(radius) {
  var [cap, stats] = await Promise.all([
    fetch(API_IND3 + "/capture?radius=" + radius).then(function(r){ return r.json(); }),
    fetch(API_IND3 + "/stats?radius=" + radius).then(function(r){ return r.json(); }),
  ]);
  _ind3Nodes = cap.nodes || [];
  _ind3Stats = stats;
  return { nodes: _ind3Nodes, stats: stats };
}

function fmt(n) { return Number(n || 0).toLocaleString("es-ES"); }

function capColor(value, max) {
  var t = Math.min(1, value / (max || 1));
  var stops = [
    [238,240,253],[195,201,245],[143,153,236],
    [95,107,228],[59,70,196]
  ];
  var seg = t * (stops.length - 1);
  var i = Math.min(stops.length - 2, Math.floor(seg));
  var f = seg - i;
  var rgb = stops[i].map(function(s, k){ return Math.round(s + (stops[i+1][k] - s) * f); });
  return "rgb(" + rgb.join(",") + ")";
}
