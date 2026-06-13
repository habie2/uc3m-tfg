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

// ═══════════════════════════════════════════════════════
// Descarga de datos en crudo
// ═══════════════════════════════════════════════════════
async function downloadRawData(indicatorId) {
  var endpoints = {
    1: [
      { url: API_IND1 + "/stations", name: "ind1_estaciones" },
      { url: API_IND1 + "/saturation", name: "ind1_saturacion" },
    ],
    2: [
      { url: API_IND2 + "/cells", name: "ind2_celdas" },
      { url: API_IND2 + "/categories/intensity", name: "ind2_categorias" },
      { url: API_IND2 + "/stats", name: "ind2_estadisticas" },
    ],
    3: [
      { url: API_IND3 + "/capture?radius=300", name: "ind3_captura" },
      { url: API_IND3 + "/stats?radius=300", name: "ind3_estadisticas" },
    ],
  };

  var items = endpoints[indicatorId] || [];
  var bundle = {};
  for (var i = 0; i < items.length; i++) {
    try {
      var res = await fetch(items[i].url);
      if (res.ok) bundle[items[i].name] = await res.json();
    } catch (e) {
      bundle[items[i].name] = { error: e.message };
    }
  }

  var blob = new Blob([JSON.stringify(bundle, null, 2)], {
    type: "application/json",
  });
  var a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "bicimad_indicador" + indicatorId + "_datos.json";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(a.href);
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

// ═══════════════════════════════════════════════════════
// MODO DEMO — datos de muestra muy reducidos para que la
// aplicación pueda explorarse sin conexión a la base de
// datos. Se activa desde App al detectar que el backend
// no responde.
// ═══════════════════════════════════════════════════════
var DEMO_MODE = false;

function enableDemoMode() {
  DEMO_MODE = true;
}

function isDemoMode() {
  return DEMO_MODE;
}

/**
 * checkBackendHealth — sonda rápida contra /api/ind1/stations.
 * Devuelve true si el backend responde correctamente, false
 * solo en caso de fallo real de red. Sin timeout artificial:
 * confiamos en el timeout natural del navegador para no dar
 * por caído un backend simplemente lento.
 */
async function checkBackendHealth() {
  try {
    var res = await fetch(API_IND1 + "/stations");
    return res.ok;
  } catch (e) {
    return false;
  }
}

// ─── Datos demo Indicador 1 (Saturación) ───────────────
// 6 estaciones reales del centro de Madrid con patrones
// de saturación inventados pero coherentes con la realidad
// (centro se vacía por la mañana, llena por la tarde).
var _DEMO_STATIONS = [
  {
    id: 1,
    name: "Puerta del Sol",
    address: "Plaza Puerta del Sol",
    lat: 40.4168,
    lng: -3.7038,
    cap: 24,
  },
  {
    id: 2,
    name: "Plaza Mayor",
    address: "Plaza Mayor",
    lat: 40.4155,
    lng: -3.7074,
    cap: 20,
  },
  {
    id: 3,
    name: "Atocha",
    address: "Estación de Atocha",
    lat: 40.4067,
    lng: -3.6906,
    cap: 30,
  },
  {
    id: 4,
    name: "Gran Vía",
    address: "Gran Vía 1",
    lat: 40.4203,
    lng: -3.7058,
    cap: 24,
  },
  {
    id: 5,
    name: "Retiro",
    address: "Plaza de la Independencia",
    lat: 40.4205,
    lng: -3.6886,
    cap: 18,
  },
  {
    id: 6,
    name: "Argüelles",
    address: "Calle de la Princesa",
    lat: 40.4304,
    lng: -3.7165,
    cap: 22,
  },
];

// Patrón típico residencial: lleno de noche, vacío de día
function _demoPatternResidential(seed) {
  var arr = [];
  for (var h = 0; h < 24; h++) {
    var base;
    if (h < 6) base = 0.85;
    else if (h < 9) base = 0.7 - (h - 6) * 0.15;
    else if (h < 18) base = 0.25;
    else if (h < 22) base = 0.4 + (h - 18) * 0.1;
    else base = 0.8;
    var noise = ((seed * 13 + h * 7) % 11) / 100 - 0.05;
    arr.push(Math.max(0, Math.min(1, base + noise)));
  }
  return arr;
}

// Patrón típico de centro/destino: vacío de noche, lleno de día
function _demoPatternCentral(seed) {
  var arr = [];
  for (var h = 0; h < 24; h++) {
    var base;
    if (h < 6) base = 0.15;
    else if (h < 9) base = 0.25 + (h - 6) * 0.15;
    else if (h < 18) base = 0.75;
    else if (h < 22) base = 0.6 - (h - 18) * 0.1;
    else base = 0.2;
    var noise = ((seed * 17 + h * 5) % 11) / 100 - 0.05;
    arr.push(Math.max(0, Math.min(1, base + noise)));
  }
  return arr;
}

var _DEMO_SATURATION = {
  1: _demoPatternCentral(1), // Sol — destino
  2: _demoPatternCentral(2), // Plaza Mayor — destino
  3: _demoPatternCentral(3), // Atocha — destino
  4: _demoPatternCentral(4), // Gran Vía — destino
  5: _demoPatternResidential(5), // Retiro — más residencial
  6: _demoPatternResidential(6), // Argüelles — residencial
};

var _DEMO_DATE_RANGE = { min: "2019-05-01", max: "2019-05-31" };
// La UI espera objetos {value, label} para meses y años:
var _DEMO_MONTHS = [{ value: 5, label: "Mayo" }];
var _DEMO_YEARS = [{ value: 2019, label: "2019" }];

// ─── Datos demo Indicador 2 (Tránsito) ─────────────────
// ► PARA AJUSTAR LA LEYENDA: cambia el contenido de este
//   array para que coincida con tus categorías reales. Los
//   campos son category_code, display_name, color_hex,
//   meters (suma absoluta) y pct (porcentaje sobre el total).
//   Si añades o quitas categorías, ajusta también los pesos
//   en _demoCellDetail más abajo.
//
// Paleta inspirada en la jerarquía vial OSM:
//   verde   = vía ciclista
//   crema   = calles tranquilas
//   amarillo→ rojo → granate = jerarquía creciente
//   gris    = servicio/otros
var _DEMO_IND2_CATS = [
  {
    category_code: "via_ciclista",
    display_name: "Vía ciclista",
    color_hex: "#2E7D32",
    meters: 5900,
    pct: 13.9,
  },
  {
    category_code: "calle_tranquila",
    display_name: "Calle tranquila",
    color_hex: "#FFE082",
    meters: 11900,
    pct: 28.1,
  },
  {
    category_code: "via_terciaria",
    display_name: "Vía terciaria",
    color_hex: "#FFC107",
    meters: 6800,
    pct: 16.0,
  },
  {
    category_code: "via_secundaria",
    display_name: "Vía secundaria",
    color_hex: "#FB8C00",
    meters: 7600,
    pct: 17.9,
  },
  {
    category_code: "via_primaria",
    display_name: "Vía primaria",
    color_hex: "#E53935",
    meters: 5100,
    pct: 12.0,
  },
  {
    category_code: "via_rapida",
    display_name: "Vía rápida",
    color_hex: "#B71C1C",
    meters: 2100,
    pct: 5.0,
  },
  {
    category_code: "servicio_otros",
    display_name: "Servicio/Otros",
    color_hex: "#9E9E9E",
    meters: 3000,
    pct: 7.1,
  },
];

// 8 celdas en una rejilla 4x2 sobre el centro de Madrid
function _buildDemoCells() {
  var cells = [];
  var lat0 = 40.408,
    lon0 = -3.715;
  var step = 0.008;
  var labels = [
    "Latina",
    "Sol",
    "Lavapiés",
    "Atocha",
    "Argüelles",
    "Gran Vía",
    "Chueca",
    "Retiro",
  ];
  var meters = [3800, 5200, 4100, 4900, 2800, 4600, 3500, 5600];
  for (var i = 0; i < 8; i++) {
    var col = i % 4;
    var row = Math.floor(i / 4);
    var south = lat0 + row * step;
    var west = lon0 + col * step;
    cells.push({
      cell_id: i + 1,
      label: labels[i],
      south: south,
      north: south + step,
      west: west,
      east: west + step,
      centroid_lat: south + step / 2,
      centroid_lon: west + step / 2,
      total_meters: meters[i],
    });
  }
  return cells;
}
var _DEMO_IND2_CELLS = _buildDemoCells();

var _DEMO_IND2_STATS = {
  total_meters: 42400,
  top_cell: { cell_id: 8, label: "Retiro", meters: 5600 },
  dominant: {
    category_code: "calle_tranquila",
    display_name: "Calle tranquila",
    pct: 28.1,
  },
};

function _demoCellDetail(cellId) {
  var cell = _DEMO_IND2_CELLS.find(function (c) {
    return String(c.cell_id) === String(cellId);
  });
  if (!cell) return null;
  // Distribución por celda. Cada array suma 1.0 y tiene 7
  // valores (uno por categoría, en el mismo orden que
  // _DEMO_IND2_CATS). Se elige según cellId % 4.
  //                vía_cic, tranq, terc, sec,  prim, rápida, otros
  var weights = [
    [0.1, 0.4, 0.15, 0.15, 0.1, 0.03, 0.07], // 0 — residencial
    [0.05, 0.15, 0.2, 0.25, 0.2, 0.1, 0.05], // 1 — arterial
    [0.25, 0.3, 0.15, 0.1, 0.1, 0.02, 0.08], // 2 — ciclable
    [0.15, 0.25, 0.18, 0.18, 0.13, 0.05, 0.06], // 3 — equilibrado
  ];
  var w = weights[cellId % weights.length];
  var dist = _DEMO_IND2_CATS.map(function (c, i) {
    return {
      category_code: c.category_code,
      display_name: c.display_name,
      meters: Math.round(cell.total_meters * w[i]),
      pct: +(w[i] * 100).toFixed(1),
    };
  });
  return {
    cell_id: cell.cell_id,
    label: cell.label,
    total_meters: cell.total_meters,
    num_trips: Math.round(cell.total_meters / 12),
    distribution: dist,
  };
}

// ─── Datos demo Indicador 3 (Captura intermodal) ───────
var _DEMO_IND3_CONFIG = { radii: [150, 300, 500], default_radius: 300 };

var _DEMO_IND3_NODES = [
  {
    id: "SOL",
    name: "Sol",
    lat: 40.417,
    lon: -3.7038,
    lines: "L1·L2·L3",
    in: 1820,
    out: 1750,
    captured: 3570,
    stations: [
      { number: 1, name: "Puerta del Sol" },
      { number: 4, name: "Gran Vía" },
    ],
  },
  {
    id: "ATCH",
    name: "Atocha",
    lat: 40.4067,
    lon: -3.6906,
    lines: "L1·Cerc",
    in: 1450,
    out: 1380,
    captured: 2830,
    stations: [{ number: 3, name: "Atocha" }],
  },
  {
    id: "ARGL",
    name: "Argüelles",
    lat: 40.4304,
    lon: -3.7165,
    lines: "L3·L4·L6",
    in: 980,
    out: 910,
    captured: 1890,
    stations: [{ number: 6, name: "Argüelles" }],
  },
  {
    id: "RTIR",
    name: "Retiro",
    lat: 40.4205,
    lon: -3.6886,
    lines: "L2",
    in: 620,
    out: 590,
    captured: 1210,
    stations: [{ number: 5, name: "Retiro" }],
  },
  {
    id: "PMAY",
    name: "Tirso de Molina",
    lat: 40.4131,
    lon: -3.7027,
    lines: "L1",
    in: 450,
    out: 480,
    captured: 930,
    stations: [{ number: 2, name: "Plaza Mayor" }],
  },
];

var _DEMO_IND3_STATS = {
  total_intermodal: 10430,
  top_node: { id: "SOL", name: "Sol", captured: 3570 },
};

// ═══════════════════════════════════════════════════════
// Gateo de las funciones de carga
// ═══════════════════════════════════════════════════════
// Guardamos las versiones originales y las reemplazamos
// por wrappers que devuelven datos demo si DEMO_MODE === true.
var _real_loadStations = loadStations;
loadStations = async function () {
  if (DEMO_MODE) {
    _stations = _DEMO_STATIONS.slice();
    return _stations;
  }
  return _real_loadStations();
};

var _real_loadDateRange = loadDateRange;
loadDateRange = async function () {
  if (DEMO_MODE) {
    _dateRange = Object.assign({}, _DEMO_DATE_RANGE);
    return _dateRange;
  }
  return _real_loadDateRange();
};

var _real_loadAvailableMonths = loadAvailableMonths;
loadAvailableMonths = async function () {
  if (DEMO_MODE) {
    _availableMonths = _DEMO_MONTHS.slice();
    return _availableMonths;
  }
  return _real_loadAvailableMonths();
};

var _real_loadAvailableYears = loadAvailableYears;
loadAvailableYears = async function () {
  if (DEMO_MODE) {
    _availableYears = _DEMO_YEARS.slice();
    return _availableYears;
  }
  return _real_loadAvailableYears();
};

var _real_loadSaturation = loadSaturation;
loadSaturation = async function (params) {
  if (DEMO_MODE) {
    // En modo demo siempre devolvemos el mismo patrón —
    // los filtros no tienen efecto real, pero la UI sigue
    // siendo navegable.
    _satData = {};
    Object.keys(_DEMO_SATURATION).forEach(function (k) {
      _satData[k] = _DEMO_SATURATION[k].slice();
    });
    return _satData;
  }
  return _real_loadSaturation(params);
};

var _real_checkHoliday = checkHoliday;
checkHoliday = async function (dateStr) {
  if (DEMO_MODE) {
    // 1 de mayo es festivo
    return /-05-01$/.test(dateStr);
  }
  return _real_checkHoliday(dateStr);
};

var _real_loadInd2Data = loadInd2Data;
loadInd2Data = async function () {
  if (DEMO_MODE) {
    _ind2Categories = _DEMO_IND2_CATS.slice();
    _ind2Cells = _DEMO_IND2_CELLS.slice();
    _ind2Stats = Object.assign({}, _DEMO_IND2_STATS);
    _ind2UserColors = {};
    _ind2Categories.forEach(function (c) {
      _ind2UserColors[c.category_code] = c.color_hex;
    });
    return { cats: _ind2Categories, cells: _ind2Cells, stats: _ind2Stats };
  }
  return _real_loadInd2Data();
};

var _real_loadInd2CellDetail = loadInd2CellDetail;
loadInd2CellDetail = async function (cellId) {
  if (DEMO_MODE) return _demoCellDetail(cellId);
  return _real_loadInd2CellDetail(cellId);
};

function _demoCellWays(cellId) {
  var cell = _DEMO_IND2_CELLS.find(function (c) {
    return String(c.cell_id) === String(cellId);
  });
  if (!cell) return { type: "FeatureCollection", features: [] };
  var s = cell.south,
    n = cell.north,
    w = cell.west,
    e = cell.east;
  // Cinco ejes inventados por celda, cada uno con una
  // categoría distinta para que se aprecie la leyenda.
  // Coordenadas en orden [lon, lat] como espera GeoJSON.
  function code(name) {
    return _DEMO_IND2_CATS.find(function (c) {
      return c.category_code === name;
    }).category_code;
  }
  var lines = [
    // Eje principal horizontal — vía secundaria
    {
      cat: code("via_secundaria"),
      pts: [
        [0.05, 0.55],
        [0.95, 0.55],
      ],
    },
    // Eje vertical — vía terciaria
    {
      cat: code("via_terciaria"),
      pts: [
        [0.4, 0.05],
        [0.4, 0.95],
      ],
    },
    // Calle interior — calle tranquila
    {
      cat: code("calle_tranquila"),
      pts: [
        [0.1, 0.25],
        [0.65, 0.25],
      ],
    },
    // Diagonal — vía ciclista
    {
      cat: code("via_ciclista"),
      pts: [
        [0.15, 0.85],
        [0.85, 0.15],
      ],
    },
    // Arteria — vía primaria
    {
      cat: code("via_primaria"),
      pts: [
        [0.7, 0.05],
        [0.85, 0.95],
      ],
    },
    // Servicio
    {
      cat: code("servicio_otros"),
      pts: [
        [0.45, 0.7],
        [0.75, 0.7],
      ],
    },
  ];
  var features = lines.map(function (ln, i) {
    return {
      type: "Feature",
      properties: {
        category_code: ln.cat,
        name: "C/ " + cell.label + " " + (i + 1),
      },
      geometry: {
        type: "LineString",
        coordinates: ln.pts.map(function (p) {
          return [w + (e - w) * p[0], s + (n - s) * p[1]];
        }),
      },
    };
  });
  return { type: "FeatureCollection", features: features };
}

function _demoCellRoutes(cellId) {
  var cell = _DEMO_IND2_CELLS.find(function (c) {
    return String(c.cell_id) === String(cellId);
  });
  if (!cell) return { type: "FeatureCollection", features: [] };
  // Rutas OD inventadas: desde el centroide de la celda hacia
  // los centroides de las 3 celdas más próximas, con grosores
  // decrecientes (más viajes hacia las primeras).
  var others = _DEMO_IND2_CELLS.filter(function (c) {
    return c.cell_id !== cell.cell_id;
  });
  others.sort(function (a, b) {
    var da = Math.hypot(
      a.centroid_lat - cell.centroid_lat,
      a.centroid_lon - cell.centroid_lon,
    );
    var db = Math.hypot(
      b.centroid_lat - cell.centroid_lat,
      b.centroid_lon - cell.centroid_lon,
    );
    return da - db;
  });
  var picks = others.slice(0, 3);
  var trips = [180, 110, 60];
  var features = picks.map(function (other, i) {
    return {
      type: "Feature",
      properties: { num_trips: trips[i] },
      geometry: {
        type: "LineString",
        coordinates: [
          [cell.centroid_lon, cell.centroid_lat],
          [other.centroid_lon, other.centroid_lat],
        ],
      },
    };
  });
  return { type: "FeatureCollection", features: features };
}

var _real_loadInd2CellWays = loadInd2CellWays;
loadInd2CellWays = async function (cellId) {
  if (DEMO_MODE) return _demoCellWays(cellId);
  return _real_loadInd2CellWays(cellId);
};

var _real_loadInd2CellRoutes = loadInd2CellRoutes;
loadInd2CellRoutes = async function (cellId) {
  if (DEMO_MODE) return _demoCellRoutes(cellId);
  return _real_loadInd2CellRoutes(cellId);
};

var _real_loadInd3Config = loadInd3Config;
loadInd3Config = async function () {
  if (DEMO_MODE) {
    _ind3Config = Object.assign({}, _DEMO_IND3_CONFIG);
    return _ind3Config;
  }
  return _real_loadInd3Config();
};

var _real_loadInd3Data = loadInd3Data;
loadInd3Data = async function (radius) {
  if (DEMO_MODE) {
    _ind3Nodes = _DEMO_IND3_NODES.map(function (n) {
      return Object.assign({}, n, { stations: n.stations.slice() });
    });
    _ind3Stats = Object.assign({}, _DEMO_IND3_STATS);
    return { nodes: _ind3Nodes, stats: _ind3Stats };
  }
  return _real_loadInd3Data(radius);
};
