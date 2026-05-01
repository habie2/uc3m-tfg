/* ═══════════════════════════════════════════════════════
   BiciMAD · Capa de datos
   ═══════════════════════════════════════════════════════
   Contiene:
     - Constantes de configuración
     - Llamadas a la API de Flask
     - getSat() que lee del caché cargado
*/

// ─── Configuración visual ───────────────────────────────
var DOT_SIZE = 4;
var T_FULL   = 0.65;   // por encima → azul (llena)
var T_EMPTY  = 0.35;   // por debajo → rojo (vacía)

var DAY_KEYS  = ['L','M','X','J','V','S','D'];
var DAY_NAMES = ['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo'];

// ─── Base URL de la API ─────────────────────────────────
var API_BASE = '';  // vacío = mismo origen (localhost:5000)

// ─── Cache de datos cargados ────────────────────────────
var _stations    = [];
var _satData     = {};
var _currentKey  = null;
var _dateRange   = { min: '2019-05-01', max: '2019-05-31' };


// ─── Cargar estaciones ──────────────────────────────────
async function loadStations() {
  var res = await fetch(API_BASE + '/api/stations');
  if (!res.ok) throw new Error('Error cargando estaciones: ' + res.status);
  _stations = await res.json();
  return _stations;
}

// ─── Cargar rango de fechas disponibles ─────────────────
async function loadDateRange() {
  var res = await fetch(API_BASE + '/api/date-range');
  if (!res.ok) return;
  _dateRange = await res.json();
  return _dateRange;
}

// ─── Cargar saturación ──────────────────────────────────
async function loadSaturation(params) {
  var url, cacheKey;

  if (params.date) {
    url = API_BASE + '/api/saturation-date?date=' + params.date;
    cacheKey = 'date:' + params.date;
  } else {
    var dt  = params.dayType || 'L';
    var hol = params.holiday ? 'true' : 'false';
    url = API_BASE + '/api/saturation?dayType=' + dt + '&holiday=' + hol;
    cacheKey = 'day:' + dt + ':' + hol;
  }

  if (cacheKey === _currentKey) return _satData;

  var res = await fetch(url);
  if (!res.ok) throw new Error('Error cargando saturación: ' + res.status);
  _satData    = await res.json();
  _currentKey = cacheKey;
  return _satData;
}

// ─── Comprobar si una fecha es festivo ──────────────────
async function checkHoliday(dateStr) {
  var res = await fetch(API_BASE + '/api/is-holiday?date=' + dateStr);
  if (!res.ok) return false;
  var data = await res.json();
  return data.holiday;
}

// ─── getSat: lectura desde el caché ─────────────────────
function getSat(station, hour) {
  var arr = _satData[String(station.id)];
  if (!arr) return 0.5;
  var val = arr[hour];
  return (val !== null && val !== undefined) ? val : 0.5;
}

// ─── Helpers de display ─────────────────────────────────
function dotColor(sat) {
  if (sat > T_FULL)  return '#2B5CF6';
  if (sat < T_EMPTY) return '#E8421A';
  return '#B0A99E';
}

function hLabel(h) {
  return String(h).padStart(2, '0') + ':00';
}

function hCtx(h) {
  if (h < 6)  return 'Madrugada';
  if (h < 9)  return 'Primera mañana';
  if (h < 12) return 'Mañana';
  if (h < 14) return 'Mediodía';
  if (h < 17) return 'Tarde temprana';
  if (h < 21) return 'Tarde';
  if (h < 23) return 'Noche temprana';
  return 'Noche';
}
