/* ═══════════════════════════════════════════════════════
   Indicador 1 — Componentes React (Saturación)
   ═══════════════════════════════════════════════════════ */

var useState = React.useState;
var useEffect = React.useEffect;
var useRef = React.useRef;
var useCallback = React.useCallback;
var h = React.createElement;

/* ─── MapView ─────────────────────────────────────────── */
function Ind1MapView(props) {
  var hour = props.hour;
  var onStationClick = props.onStationClick;
  var dataVer = props.dataVer || 0;

  var mountRef = useRef(null);
  var mapRef = useRef(null);
  var canvasRef = useRef(null);
  var mrkRef = useRef({});
  var hourRef = useRef(hour);

  // Keep hourRef updated synchronously with each render
  hourRef.current = hour;

  var drawBlobs = useCallback(function () {
    var map = mapRef.current;
    var canvas = canvasRef.current;
    if (!map || !canvas) return;
    var curHour = hourRef.current;
    var size = map.getSize();
    canvas.width = size.x;
    canvas.height = size.y;
    var ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, size.x, size.y);
    _stations.forEach(function (st) {
      var sat = getSat(st, curHour);
      if (sat === null || sat === undefined) return;
      var rgb = null,
        intensity = 0;
      if (sat > T_FULL) {
        rgb = [43, 92, 246];
        intensity = Math.pow((sat - T_FULL) / (1 - T_FULL), 0.65);
      } else if (sat < T_EMPTY) {
        rgb = [232, 66, 26];
        intensity = Math.pow((T_EMPTY - sat) / T_EMPTY, 0.65);
      }
      if (!rgb) return;
      var pt = map.latLngToContainerPoint([st.lat, st.lng]);
      var radius = (52 + (st.cap / 30) * 28) * (0.5 + 0.5 * intensity);
      var R = rgb[0],
        G = rgb[1],
        B = rgb[2];
      var grad = ctx.createRadialGradient(pt.x, pt.y, 0, pt.x, pt.y, radius);
      grad.addColorStop(
        0,
        "rgba(" + R + "," + G + "," + B + "," + 0.5 * intensity + ")",
      );
      grad.addColorStop(
        0.35,
        "rgba(" + R + "," + G + "," + B + "," + 0.28 * intensity + ")",
      );
      grad.addColorStop(
        0.7,
        "rgba(" + R + "," + G + "," + B + "," + 0.1 * intensity + ")",
      );
      grad.addColorStop(1, "rgba(" + R + "," + G + "," + B + ",0)");
      ctx.beginPath();
      ctx.fillStyle = grad;
      ctx.arc(pt.x, pt.y, radius, 0, Math.PI * 2);
      ctx.fill();
    });
  }, []);

  // Mount map once
  useEffect(
    function () {
      if (!_stations.length) return;
      var avgLat =
        _stations.reduce(function (s, st) {
          return s + st.lat;
        }, 0) / _stations.length;
      var avgLng =
        _stations.reduce(function (s, st) {
          return s + st.lng;
        }, 0) / _stations.length;
      var map = L.map(mountRef.current, {
        center: [avgLat, avgLng],
        zoom: 14,
        zoomControl: true,
      });
      L.tileLayer(
        "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        {
          attribution: "&copy; OpenStreetMap &copy; CARTO",
          subdomains: "abcd",
          maxZoom: 19,
        },
      ).addTo(map);
      var canvas = document.createElement("canvas");
      canvas.style.cssText =
        "position:absolute;top:0;left:0;pointer-events:none;z-index:450;";
      map.getContainer().appendChild(canvas);
      canvasRef.current = canvas;
      map.on("moveend zoomend resize", drawBlobs);
      _stations.forEach(function (st) {
        var sat = getSat(st, hourRef.current);
        var color = dotColor(sat);
        var opacity = sat === null || sat === undefined ? 0.45 : 1;
        var m = L.circleMarker([st.lat, st.lng], {
          radius: DOT_SIZE,
          fillColor: color,
          color: "#fff",
          fillOpacity: opacity,
          weight: 1.5,
          pane: "markerPane",
        });
        m.bindTooltip(st.name, { direction: "top", offset: [0, -6] });
        m.on("click", function () {
          onStationClick(st, getSat(st, hourRef.current));
        });
        m.addTo(map);
        mrkRef.current[st.id] = m;
      });
      mapRef.current = map;
      drawBlobs();
      return function () {
        map.remove();
      };
    },
    [drawBlobs, onStationClick],
  );

  // Update markers ONLY when dataVer changes (the single source of truth
  // for "data changed, re-render markers"). hour is read via hourRef so
  // it's always current without re-triggering this effect on hour change.
  useEffect(
    function () {
      var curHour = hourRef.current;
      _stations.forEach(function (st) {
        var m = mrkRef.current[st.id];
        if (!m) return;
        var sat = getSat(st, curHour);
        var color = dotColor(sat);
        var opacity = sat === null || sat === undefined ? 0.45 : 1;
        m.setStyle({
          fillColor: color,
          radius: DOT_SIZE,
          fillOpacity: opacity,
        });
      });
      drawBlobs();
    },
    [dataVer, drawBlobs],
  );

  return h("div", { ref: mountRef, id: "map-mount" });
}

/* ─── Sparkline with threshold coloring ───────────────── */
function buildThresholdSparkSVG(station, hour, W, H) {
  var sparkData = [];
  for (var i = 0; i < 24; i++) {
    var v = getSat(station, i);
    sparkData.push(v === null || v === undefined ? 0.5 : v);
  }
  var sat = getSat(station, hour);
  var satForColor = sat === null || sat === undefined ? 0.5 : sat;
  var color = dotColor(sat);

  var points = sparkData.map(function (v, idx) {
    return { x: (idx / 23) * W, y: H - v * H };
  });
  var ptsStr = points
    .map(function (p) {
      return p.x.toFixed(1) + "," + p.y.toFixed(1);
    })
    .join(" ");

  var fullY = H - T_FULL * H;
  var emptyY = H - T_EMPTY * H;

  var linePath =
    "M" +
    points
      .map(function (p) {
        return p.x.toFixed(1) + "," + p.y.toFixed(1);
      })
      .join(" L");

  var svg = "";
  svg += "<defs>";
  svg += '<clipPath id="clipBlue' + station.id + '">';
  svg +=
    '<rect x="0" y="0" width="' + W + '" height="' + fullY.toFixed(1) + '"/>';
  svg += "</clipPath>";
  svg += '<clipPath id="clipRed' + station.id + '">';
  svg +=
    '<rect x="0" y="' +
    emptyY.toFixed(1) +
    '" width="' +
    W +
    '" height="' +
    (H - emptyY).toFixed(1) +
    '"/>';
  svg += "</clipPath>";
  svg += '<clipPath id="clipNeutral' + station.id + '">';
  svg +=
    '<rect x="0" y="' +
    fullY.toFixed(1) +
    '" width="' +
    W +
    '" height="' +
    (emptyY - fullY).toFixed(1) +
    '"/>';
  svg += "</clipPath>";
  svg += "</defs>";

  svg +=
    '<line x1="0" y1="' +
    fullY.toFixed(1) +
    '" x2="' +
    W +
    '" y2="' +
    fullY.toFixed(1) +
    '" stroke="#2B5CF6" stroke-width="1" stroke-dasharray="3,3" opacity=".35"/>';
  svg +=
    '<line x1="0" y1="' +
    emptyY.toFixed(1) +
    '" x2="' +
    W +
    '" y2="' +
    emptyY.toFixed(1) +
    '" stroke="#E8421A" stroke-width="1" stroke-dasharray="3,3" opacity=".35"/>';

  svg +=
    '<polyline points="' +
    ptsStr +
    '" fill="none" stroke="#2B5CF6" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" clip-path="url(#clipBlue' +
    station.id +
    ')"/>';
  var blueArea =
    linePath +
    " L" +
    W.toFixed(1) +
    "," +
    fullY.toFixed(1) +
    " L0," +
    fullY.toFixed(1) +
    " Z";
  svg +=
    '<path d="' +
    blueArea +
    '" fill="rgba(43,92,246,0.10)" clip-path="url(#clipBlue' +
    station.id +
    ')"/>';

  svg +=
    '<polyline points="' +
    ptsStr +
    '" fill="none" stroke="#E8421A" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" clip-path="url(#clipRed' +
    station.id +
    ')"/>';
  var redArea =
    linePath +
    " L" +
    W.toFixed(1) +
    "," +
    emptyY.toFixed(1) +
    " L0," +
    emptyY.toFixed(1) +
    " Z";
  svg +=
    '<path d="' +
    redArea +
    '" fill="rgba(232,66,26,0.10)" clip-path="url(#clipRed' +
    station.id +
    ')"/>';

  svg +=
    '<polyline points="' +
    ptsStr +
    '" fill="none" stroke="#B0A99E" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" clip-path="url(#clipNeutral' +
    station.id +
    ')"/>';

  var cx = ((hour / 23) * W).toFixed(1);
  var cy = (H - satForColor * H).toFixed(1);
  svg +=
    '<circle cx="' +
    cx +
    '" cy="' +
    cy +
    '" r="4.5" fill="' +
    color +
    '" stroke="#fff" stroke-width="2"/>';

  return svg;
}

/* ─── StationCard ─────────────────────────────────────── */
function Ind1StationCard(props) {
  var station = props.station,
    hour = props.hour,
    onClose = props.onClose;
  var rawSat = getSat(station, hour);
  var hasData = rawSat !== null && rawSat !== undefined;
  var sat = hasData ? rawSat : 0;
  var bikes = Math.round(sat * station.cap);
  var docks = station.cap - bikes;
  var color = dotColor(rawSat);
  var W = 210,
    H = 44;

  return h(
    "div",
    { className: "station-card" },
    h(
      "div",
      { className: "sc-head" },
      h(
        "div",
        null,
        h("div", { className: "sc-name" }, station.name),
        h("div", { className: "sc-cap" }, station.cap + " anclajes totales"),
      ),
      h("button", { className: "sc-close", onClick: onClose }, "\u00D7"),
    ),
    h(
      "div",
      { className: "sc-sat-row" },
      h("span", { className: "sc-sat-key" }, "Saturación"),
      h(
        "span",
        { className: "sc-sat-pct", style: { color: color } },
        hasData ? Math.round(sat * 100) + "%" : "sin datos",
      ),
    ),
    h(
      "div",
      { className: "sc-bar" },
      h("div", {
        className: "sc-fill",
        style: { width: sat * 100 + "%", background: color },
      }),
    ),
    h(
      "div",
      { className: "sc-tiles" },
      h(
        "div",
        { className: "sc-tile" },
        h(
          "div",
          { className: "sc-tile-val", style: { color: color } },
          hasData ? bikes : "—",
        ),
        h("div", { className: "sc-tile-lbl" }, "Bicis"),
      ),
      h(
        "div",
        { className: "sc-tile" },
        h("div", { className: "sc-tile-val" }, hasData ? docks : "—"),
        h("div", { className: "sc-tile-lbl" }, "Libres"),
      ),
    ),
    h("div", { className: "sc-spark-lbl" }, "Saturación del día"),
    h("svg", {
      width: W,
      height: H + 2,
      style: { display: "block", overflow: "visible" },
      dangerouslySetInnerHTML: {
        __html: buildThresholdSparkSVG(station, hour, W, H),
      },
    }),
    h(
      "div",
      { className: "sc-spark-ticks" },
      ["00h", "06h", "12h", "18h", "23h"].map(function (t) {
        return h("span", { key: t }, t);
      }),
    ),
  );
}

/* ─── Stats ───────────────────────────────────────────── */
function Ind1Stats(props) {
  var hour = props.hour;
  var sats = [];
  var stsWithData = [];
  _stations.forEach(function (s) {
    var v = getSat(s, hour);
    if (v !== null && v !== undefined) {
      sats.push(v);
      stsWithData.push(s);
    }
  });
  if (!sats.length) {
    return h(
      "div",
      { className: "sb-sec" },
      h("div", { className: "sb-lbl" }, "Estadísticas — " + hLabel(hour)),
      h(
        "div",
        { className: "stat-list" },
        h(
          "div",
          { className: "stat-row2" },
          h("span", { className: "stat-lbl" }, "Sin datos para esta hora"),
        ),
      ),
    );
  }
  var avg =
    sats.reduce(function (a, b) {
      return a + b;
    }, 0) / sats.length;
  var maxIdx = sats.indexOf(Math.max.apply(null, sats));
  var minIdx = sats.indexOf(Math.min.apply(null, sats));
  var peakH = 0,
    bestDist = 99;
  for (var hh = 0; hh < 24; hh++) {
    var hourSats = [];
    _stations.forEach(function (st) {
      var v = getSat(st, hh);
      if (v !== null && v !== undefined) hourSats.push(v);
    });
    if (!hourSats.length) continue;
    var hAvg =
      hourSats.reduce(function (s, v) {
        return s + v;
      }, 0) / hourSats.length;
    var d = Math.abs(hAvg - 0.5);
    if (d < bestDist) {
      bestDist = d;
      peakH = hh;
    }
  }
  var rows = [
    {
      lbl: "Saturación media",
      sub: sats.length + " estaciones activas",
      val: Math.round(avg * 100) + "%",
      color: dotColor(avg),
    },
    {
      lbl: "Más llena",
      sub: stsWithData[maxIdx] ? stsWithData[maxIdx].name : "—",
      val: Math.round(sats[maxIdx] * 100) + "%",
      color: "#2B5CF6",
    },
    {
      lbl: "Más vacía",
      sub: stsWithData[minIdx] ? stsWithData[minIdx].name : "—",
      val: Math.round(sats[minIdx] * 100) + "%",
      color: "#E8421A",
    },
    {
      lbl: "Hora más activa",
      sub: "mayor movimiento",
      val: hLabel(peakH),
      color: "var(--black)",
    },
  ];
  return h(
    "div",
    { className: "sb-sec" },
    h("div", { className: "sb-lbl" }, "Estadísticas — " + hLabel(hour)),
    h(
      "div",
      { className: "stat-list" },
      rows.map(function (r) {
        return h(
          "div",
          { key: r.lbl, className: "stat-row2" },
          h(
            "div",
            { className: "stat-info" },
            h("span", { className: "stat-lbl" }, r.lbl),
            h("span", { className: "stat-sub" }, r.sub),
          ),
          h(
            "span",
            { className: "stat-val", style: { color: r.color } },
            r.val,
          ),
        );
      }),
    ),
  );
}

/* ─── PlaybackControls — step size + speed ─────────────── */
function Ind1PlaybackControls(props) {
  var step = props.step;
  var setStep = props.setStep;
  var fps = props.fps;
  var setFps = props.setFps;
  var mode = props.mode;

  var STEPS_AGG = [
    { value: 1, label: "1h" },
    { value: 2, label: "2h" },
    { value: 3, label: "3h" },
    { value: 4, label: "4h" },
    { value: 6, label: "6h" },
    { value: 12, label: "12h" },
  ];

  var STEPS_DISAGG = [
    { value: 1, label: "1h" },
    { value: 2, label: "2h" },
    { value: 3, label: "3h" },
    { value: 4, label: "4h" },
    { value: 6, label: "6h" },
    { value: 12, label: "12h" },
    { value: 24, label: "1 día" },
    { value: 168, label: "1 sem" },
  ];

  var steps = mode === "disagg" ? STEPS_DISAGG : STEPS_AGG;

  return h(
    "div",
    { className: "playback-controls" },
    h(
      "div",
      { className: "pb-group" },
      h("span", { className: "pb-label" }, "Salto"),
      h(
        "div",
        { className: "pb-btns" },
        steps.map(function (s) {
          return h(
            "button",
            {
              key: s.value,
              className: "pb-btn " + (step === s.value ? "on" : ""),
              onClick: function () {
                setStep(s.value);
              },
            },
            s.label,
          );
        }),
      ),
    ),
    h(
      "div",
      { className: "pb-group" },
      h("span", { className: "pb-label" }, "Vel."),
      h(
        "div",
        { className: "pb-speed" },
        h("input", {
          type: "range",
          min: 1,
          max: 10,
          value: fps,
          className: "pb-fps-slider",
          onChange: function (e) {
            setFps(Number(e.target.value));
          },
        }),
        h("span", { className: "pb-fps-val" }, fps + " fps"),
      ),
    ),
  );
}
