/* ═══════════════════════════════════════════════════════
   BiciMAD · Capa de datos unificada
   ═══════════════════════════════════════════════════════ */

// ─── Configuración visual (ind1) ────────────────────────
var DOT_SIZE = 4;
var T_FULL = 0.65;
var T_EMPTY = 0.35;

var DAY_KEYS = ["L", "M", "X", "J", "V", "S", "D"];
var DAY_NAMES = [
  "Lunes",
  "Martes",
  "Miércoles",
  "Jueves",
  "Viernes",
  "Sábado",
  "Domingo",
];
var DAY_ISO = [1, 2, 3, 4, 5, 6, 7];

// ─── Base URLs ──────────────────────────────────────────
var API_IND1 = "/api/ind1";
var API_IND2 = "/api/ind2";
var API_IND3 = "/api/ind3";

// ═══════════════════════════════════════════════════════
// INDICADOR 1 — Saturación
// ═══════════════════════════════════════════════════════
var _stations = [];
var _satData = {};
var _dateRange = { min: "2019-05-01", max: "2019-05-31" };
var _availableMonths = [];
var _availableYears = [];

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

async function loadAvailableYears() {
  var res = await fetch(API_IND1 + "/available-years");
  if (!res.ok) return [];
  _availableYears = await res.json();
  return _availableYears;
}

/**
 * loadSaturation — fetches saturation data and RETURNS it.
 * Also updates global _satData. No cache layer here — caller
 * is responsible for deciding when to load.
 */
async function loadSaturation(params) {
  var url;
  if (params.date) {
    url = API_IND1 + "/saturation-date?date=" + params.date;
  } else {
    var qp = [];
    if (params.days && params.days.length)
      qp.push("days=" + params.days.join(","));
    if (params.months && params.months.length)
      qp.push("months=" + params.months.join(","));
    if (params.years && params.years.length)
      qp.push("years=" + params.years.join(","));
    if (params.holiday) qp.push("holiday=" + params.holiday);
    url = API_IND1 + "/saturation" + (qp.length ? "?" + qp.join("&") : "");
  }
  var res = await fetch(url);
  if (!res.ok) throw new Error("Error cargando saturación: " + res.status);
  var data = await res.json();
  _satData = data;
  return data;
}

async function checkHoliday(dateStr) {
  var res = await fetch(API_IND1 + "/is-holiday?date=" + dateStr);
  if (!res.ok) return false;
  var data = await res.json();
  return data.holiday;
}

/**
 * getSat — returns saturation for a station/hour, or null
 * if the station has no data (inactive that day).
 */
function getSat(station, hour, dataOverride) {
  var data = dataOverride || _satData;
  var arr = data[String(station.id)];
  if (!arr) return null;
  var val = arr[hour];
  return val !== null && val !== undefined ? val : null;
}

function dotColor(sat) {
  if (sat === null || sat === undefined) return "#D8D2C8";
  if (sat > T_FULL) return "#2B5CF6";
  if (sat < T_EMPTY) return "#E8421A";
  return "#B0A99E";
}

// For map dots: binary — always color if data exists, blob shows intensity
function dotColorBinary(sat) {
  if (sat === null || sat === undefined) return "#D8D2C8";
  if (sat >= 0.5) return "#2B5CF6";
  return "#E8421A";
}

function hLabel(h) {
  return String(h).padStart(2, "0") + ":00";
}
function hCtx(h) {
  if (h < 6) return "Madrugada";
  if (h < 9) return "Primera mañana";
  if (h < 12) return "Mañana";
  if (h < 14) return "Mediodía";
  if (h < 17) return "Tarde temprana";
  if (h < 21) return "Tarde";
  if (h < 23) return "Noche temprana";
  return "Noche";
}

/* ─── Date helpers ──────────────────────────────────────── */
function addDays(dateStr, n) {
  var d = new Date(dateStr + "T12:00:00");
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
}
function addWeeks(dateStr, n) {
  return addDays(dateStr, n * 7);
}
function addMonths(dateStr, n) {
  var d = new Date(dateStr + "T12:00:00");
  d.setMonth(d.getMonth() + n);
  return d.toISOString().slice(0, 10);
}
function addYears(dateStr, n) {
  var d = new Date(dateStr + "T12:00:00");
  d.setFullYear(d.getFullYear() + n);
  return d.toISOString().slice(0, 10);
}
function formatDateShort(dateStr) {
  if (!dateStr) return "";
  var parts = dateStr.split("-");
  var dayNames = ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"];
  var d = new Date(dateStr + "T12:00:00");
  return (
    dayNames[d.getDay()] +
    " " +
    parseInt(parts[2]) +
    "/" +
    parseInt(parts[1]) +
    "/" +
    parts[0]
  );
}

// ═══════════════════════════════════════════════════════
// INDICADOR 2 — Tránsito
// ═══════════════════════════════════════════════════════
var _ind2Categories = [];
var _ind2Cells = [];
var _ind2Stats = null;
var _ind2UserColors = {};

function fmtKm(meters) {
  if (meters >= 1e6) return (meters / 1e6).toFixed(2) + " Mkm";
  if (meters >= 1e3) return (meters / 1e3).toFixed(1) + " km";
  return Math.round(meters) + " m";
}
function fmtPct(x) {
  return Number(x).toFixed(1) + "%";
}
function getInd2Color(code) {
  return _ind2UserColors[code] || "#999";
}

async function loadInd2Data() {
  var [cats, cells, stats] = await Promise.all([
    fetch(API_IND2 + "/categories/intensity").then(function (r) {
      return r.json();
    }),
    fetch(API_IND2 + "/cells").then(function (r) {
      return r.json();
    }),
    fetch(API_IND2 + "/stats").then(function (r) {
      return r.json();
    }),
  ]);
  _ind2Categories = cats;
  _ind2Cells = cells;
  _ind2Stats = stats;
  cats.forEach(function (c) {
    _ind2UserColors[c.category_code] = c.color_hex;
  });
  return { cats: cats, cells: cells, stats: stats };
}

async function loadInd2CellDetail(cellId) {
  return fetch(API_IND2 + "/cells/" + cellId).then(function (r) {
    return r.json();
  });
}

async function loadInd2CellWays(cellId) {
  return fetch(API_IND2 + "/cells/" + cellId + "/ways").then(function (r) {
    return r.json();
  });
}

async function loadInd2CellRoutes(cellId) {
  return fetch(API_IND2 + "/cells/" + cellId + "/routes").then(function (r) {
    return r.json();
  });
}

// ═══════════════════════════════════════════════════════
// INDICADOR 3 — Captura intermodal
// ═══════════════════════════════════════════════════════
var _ind3Nodes = [];
var _ind3Stats = null;
var _ind3Config = null;

async function loadInd3Config() {
  try {
    _ind3Config = await fetch(API_IND3 + "/config").then(function (r) {
      return r.json();
    });
  } catch (e) {
    _ind3Config = { radii: [150, 300, 500], default_radius: 150 };
  }
  return _ind3Config;
}

async function loadInd3Data(radius) {
  var [cap, stats] = await Promise.all([
    fetch(API_IND3 + "/capture?radius=" + radius).then(function (r) {
      return r.json();
    }),
    fetch(API_IND3 + "/stats?radius=" + radius).then(function (r) {
      return r.json();
    }),
  ]);
  _ind3Nodes = cap.nodes || [];
  _ind3Stats = stats;
  return { nodes: _ind3Nodes, stats: stats };
}

function fmt(n) {
  return Number(n || 0).toLocaleString("es-ES");
}

function capColor(value, max) {
  var t = Math.min(1, value / (max || 1));
  var stops = [
    [238, 240, 253],
    [195, 201, 245],
    [143, 153, 236],
    [95, 107, 228],
    [59, 70, 196],
  ];
  var seg = t * (stops.length - 1);
  var i = Math.min(stops.length - 2, Math.floor(seg));
  var f = seg - i;
  var rgb = stops[i].map(function (s, k) {
    return Math.round(s + (stops[i + 1][k] - s) * f);
  });
  return "rgb(" + rgb.join(",") + ")";
}
