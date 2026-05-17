/* ═══════════════════════════════════════════════════════
   Indicador 1 — Componentes React (Saturación)
   ═══════════════════════════════════════════════════════ */

var useState    = React.useState;
var useEffect   = React.useEffect;
var useRef      = React.useRef;
var useCallback = React.useCallback;
var h           = React.createElement;

/* ─── MapView ─────────────────────────────────────────── */
function Ind1MapView(props) {
  var hour           = props.hour;
  var onStationClick = props.onStationClick;

  var mountRef  = useRef(null);
  var mapRef    = useRef(null);
  var canvasRef = useRef(null);
  var mrkRef    = useRef({});
  var propsRef  = useRef({ hour: hour });

  useEffect(function(){ propsRef.current.hour = hour; }, [hour]);

  var drawBlobs = useCallback(function() {
    var map    = mapRef.current;
    var canvas = canvasRef.current;
    if (!map || !canvas) return;
    var curHour = propsRef.current.hour;
    var size    = map.getSize();
    canvas.width  = size.x;
    canvas.height = size.y;
    var ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, size.x, size.y);
    _stations.forEach(function(st) {
      var sat = getSat(st, curHour);
      var rgb = null, intensity = 0;
      if (sat > T_FULL) {
        rgb = [43,92,246]; intensity = Math.pow((sat - T_FULL) / (1 - T_FULL), 0.65);
      } else if (sat < T_EMPTY) {
        rgb = [232,66,26]; intensity = Math.pow((T_EMPTY - sat) / T_EMPTY, 0.65);
      }
      if (!rgb) return;
      var pt     = map.latLngToContainerPoint([st.lat, st.lng]);
      var radius = (52 + (st.cap / 30) * 28) * (0.5 + 0.5 * intensity);
      var R = rgb[0], G = rgb[1], B = rgb[2];
      var grad = ctx.createRadialGradient(pt.x, pt.y, 0, pt.x, pt.y, radius);
      grad.addColorStop(0,    'rgba('+R+','+G+','+B+','+(0.50*intensity)+')');
      grad.addColorStop(0.35, 'rgba('+R+','+G+','+B+','+(0.28*intensity)+')');
      grad.addColorStop(0.7,  'rgba('+R+','+G+','+B+','+(0.10*intensity)+')');
      grad.addColorStop(1,    'rgba('+R+','+G+','+B+',0)');
      ctx.beginPath(); ctx.fillStyle = grad;
      ctx.arc(pt.x, pt.y, radius, 0, Math.PI * 2); ctx.fill();
    });
  }, []);

  useEffect(function() {
    if (!_stations.length) return;
    var avgLat = _stations.reduce(function(s, st){ return s + st.lat; }, 0) / _stations.length;
    var avgLng = _stations.reduce(function(s, st){ return s + st.lng; }, 0) / _stations.length;
    var map = L.map(mountRef.current, { center: [avgLat, avgLng], zoom: 14, zoomControl: true });
    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; OpenStreetMap &copy; CARTO', subdomains: 'abcd', maxZoom: 19,
    }).addTo(map);
    var canvas = document.createElement('canvas');
    canvas.style.cssText = 'position:absolute;top:0;left:0;pointer-events:none;z-index:450;';
    map.getContainer().appendChild(canvas);
    canvasRef.current = canvas;
    map.on('moveend zoomend resize', drawBlobs);
    _stations.forEach(function(st) {
      var sat = getSat(st, propsRef.current.hour);
      var m = L.circleMarker([st.lat, st.lng], {
        radius: DOT_SIZE, fillColor: dotColor(sat), color: '#fff',
        fillOpacity: 1, weight: 1.5, pane: 'markerPane',
      });
      m.bindTooltip(st.name, { direction: 'top', offset: [0, -6] });
      m.on('click', function(){ onStationClick(st, getSat(st, propsRef.current.hour)); });
      m.addTo(map);
      mrkRef.current[st.id] = m;
    });
    mapRef.current = map;
    drawBlobs();
    return function(){ map.remove(); };
  }, [drawBlobs, onStationClick]);

  useEffect(function() {
    _stations.forEach(function(st) {
      var m = mrkRef.current[st.id];
      if (!m) return;
      var sat = getSat(st, hour);
      m.setStyle({ fillColor: dotColor(sat), radius: DOT_SIZE });
    });
    drawBlobs();
  }, [hour, drawBlobs]);

  return h('div', { ref: mountRef, id: 'map-mount' });
}

/* ─── StationCard ─────────────────────────────────────── */
function Ind1StationCard(props) {
  var station = props.station, hour = props.hour, onClose = props.onClose;
  var sat   = getSat(station, hour);
  var bikes = Math.round(sat * station.cap);
  var docks = station.cap - bikes;
  var color = dotColor(sat);
  var W = 210, H = 44;
  var sparkData = [];
  for (var i = 0; i < 24; i++) sparkData.push(getSat(station, i));
  var pts = sparkData.map(function(v, i){ return (i/23*W).toFixed(1)+','+(H-v*H).toFixed(1); }).join(' ');
  var cx = (hour / 23 * W).toFixed(1);
  var cy = (H - sat * H).toFixed(1);
  return h('div', { className: 'station-card' },
    h('div', { className: 'sc-head' },
      h('div', null,
        h('div', { className: 'sc-name' }, station.name),
        h('div', { className: 'sc-cap' }, station.cap + ' anclajes totales')
      ),
      h('button', { className: 'sc-close', onClick: onClose }, '\u00D7')
    ),
    h('div', { className: 'sc-sat-row' },
      h('span', { className: 'sc-sat-key' }, 'Saturación'),
      h('span', { className: 'sc-sat-pct', style: { color: color } }, Math.round(sat * 100) + '%')
    ),
    h('div', { className: 'sc-bar' },
      h('div', { className: 'sc-fill', style: { width: (sat*100)+'%', background: color } })
    ),
    h('div', { className: 'sc-tiles' },
      h('div', { className: 'sc-tile' },
        h('div', { className: 'sc-tile-val', style: { color: color } }, bikes),
        h('div', { className: 'sc-tile-lbl' }, 'Bicis')
      ),
      h('div', { className: 'sc-tile' },
        h('div', { className: 'sc-tile-val' }, docks),
        h('div', { className: 'sc-tile-lbl' }, 'Libres')
      )
    ),
    h('div', { className: 'sc-spark-lbl' }, 'Saturación del día'),
    h('svg', {
      width: W, height: H + 2, style: { display: 'block', overflow: 'visible' },
      dangerouslySetInnerHTML: { __html:
        '<defs><linearGradient id="sg'+station.id+'" x1="0%" y1="0%" x2="100%" y2="0%">'+
        '<stop offset="0%" stop-color="#E8421A"/><stop offset="40%" stop-color="#B0A99E"/>'+
        '<stop offset="60%" stop-color="#B0A99E"/><stop offset="100%" stop-color="#2B5CF6"/>'+
        '</linearGradient></defs>'+
        '<line x1="0" y1="'+(H-T_FULL*H)+'" x2="'+W+'" y2="'+(H-T_FULL*H)+'" stroke="#2B5CF6" stroke-width="1" stroke-dasharray="3,3" opacity=".35"/>'+
        '<line x1="0" y1="'+(H-T_EMPTY*H)+'" x2="'+W+'" y2="'+(H-T_EMPTY*H)+'" stroke="#E8421A" stroke-width="1" stroke-dasharray="3,3" opacity=".35"/>'+
        '<polyline points="'+pts+'" fill="none" stroke="url(#sg'+station.id+')" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>'+
        '<circle cx="'+cx+'" cy="'+cy+'" r="4.5" fill="'+color+'" stroke="#fff" stroke-width="2"/>'
      }
    }),
    h('div', { className: 'sc-spark-ticks' },
      ['00h','06h','12h','18h','23h'].map(function(t){ return h('span', { key: t }, t); })
    )
  );
}

/* ─── Stats ───────────────────────────────────────────── */
function Ind1Stats(props) {
  var hour = props.hour;
  var sats = _stations.map(function(s){ return getSat(s, hour); });
  if (!sats.length) return null;
  var avg    = sats.reduce(function(a,b){ return a+b; }, 0) / sats.length;
  var maxIdx = sats.indexOf(Math.max.apply(null, sats));
  var minIdx = sats.indexOf(Math.min.apply(null, sats));
  var peakH = 0, bestDist = 99;
  for (var hh = 0; hh < 24; hh++) {
    var hAvg = _stations.reduce(function(s,st){ return s + getSat(st, hh); }, 0) / _stations.length;
    var d = Math.abs(hAvg - 0.5);
    if (d < bestDist) { bestDist = d; peakH = hh; }
  }
  var rows = [
    { lbl: 'Saturación media', sub: 'todas las estaciones', val: Math.round(avg*100)+'%', color: dotColor(avg) },
    { lbl: 'Más llena', sub: _stations[maxIdx] ? _stations[maxIdx].name : '—', val: Math.round(sats[maxIdx]*100)+'%', color: '#2B5CF6' },
    { lbl: 'Más vacía', sub: _stations[minIdx] ? _stations[minIdx].name : '—', val: Math.round(sats[minIdx]*100)+'%', color: '#E8421A' },
    { lbl: 'Hora más activa', sub: 'mayor movimiento', val: hLabel(peakH), color: 'var(--black)' },
  ];
  return h('div', { className: 'sb-sec' },
    h('div', { className: 'sb-lbl' }, 'Estadísticas — ' + hLabel(hour)),
    h('div', { className: 'stat-list' },
      rows.map(function(r) {
        return h('div', { key: r.lbl, className: 'stat-row2' },
          h('div', { className: 'stat-info' },
            h('span', { className: 'stat-lbl' }, r.lbl),
            h('span', { className: 'stat-sub' }, r.sub)
          ),
          h('span', { className: 'stat-val', style: { color: r.color } }, r.val)
        );
      })
    )
  );
}
