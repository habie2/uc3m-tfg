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

/* ─── Indicador 1 ──────────────────────────────────────── */
function Ind1View() {
  var _s1 = useState(true);
  var loading = _s1[0];
  var setLoading = _s1[1];
  var _s2 = useState(null);
  var error = _s2[0];
  var setError = _s2[1];
  var _s3 = useState("agg");
  var mode = _s3[0];
  var setMode = _s3[1];
  var _s4 = useState([]);
  var selDays = _s4[0];
  var setSelDays = _s4[1];
  var _s5 = useState([]);
  var selMonths = _s5[0];
  var setSelMonths = _s5[1];
  var _s6 = useState([]);
  var selYears = _s6[0];
  var setSelYears = _s6[1];
  var _s7 = useState("all");
  var holiday = _s7[0];
  var setHoliday = _s7[1];
  var _s8 = useState("");
  var dateFrom = _s8[0];
  var setDateFrom = _s8[1];
  var _s9 = useState("");
  var dateTo = _s9[0];
  var setDateTo = _s9[1];
  var _sA = useState("");
  var curDate = _sA[0];
  var setCurDate = _sA[1];
  var _sB = useState(false);
  var dateHol = _sB[0];
  var setDateHol = _sB[1];
  var _sC = useState(9);
  var hour = _sC[0];
  var setHour = _sC[1];
  var _sD = useState(false);
  var playing = _sD[0];
  var setPlaying = _sD[1];
  var _sE = useState(null);
  var selSt = _sE[0];
  var setSelSt = _sE[1];
  var _sF = useState(0);
  var dataVer = _sF[0];
  var setDataVer = _sF[1];
  var _sG = useState([]);
  var months = _sG[0];
  var setMonths = _sG[1];
  var _sH = useState([]);
  var years = _sH[0];
  var setYears = _sH[1];
  var _sI = useState(1);
  var step = _sI[0];
  var setStep = _sI[1];
  var _sJ = useState(2);
  var fps = _sJ[0];
  var setFps = _sJ[1];

  var sliderRef = React.useRef(null);

  // Lock to prevent concurrent loads
  var loadingRef = useRef(false);
  // Track which "request" is current to discard stale responses
  var reqIdRef = useRef(0);

  // ── Initial load ──
  useEffect(function () {
    (async function () {
      try {
        await loadStations();
        await loadDateRange();
        var avMonths = await loadAvailableMonths();
        var avYears = await loadAvailableYears();
        setMonths(avMonths);
        setYears(avYears);
        setDateFrom(_dateRange.min || "2019-05-01");
        setDateTo(_dateRange.min || "2019-05-01");
        setCurDate(_dateRange.min || "2019-05-01");
        await loadSaturation({
          days: [],
          months: [],
          years: [],
          holiday: "all",
        });
        setDataVer(function (v) {
          return v + 1;
        });
        setLoading(false);
      } catch (err) {
        console.error(err);
        setError(err.message);
        setLoading(false);
      }
    })();
  }, []);

  // ── Centralized loader ──
  // This is the SINGLE place where data is loaded. Markers update only
  // when dataVer increments, which only happens AFTER successful load.
  var doLoad = useCallback(function (loadParams) {
    var myReqId = ++reqIdRef.current;
    loadingRef.current = true;
    return loadSaturation(loadParams)
      .then(function () {
        // Only update state if this is still the current request
        if (myReqId !== reqIdRef.current) return false;
        loadingRef.current = false;
        setDataVer(function (v) {
          return v + 1;
        });
        return true;
      })
      .catch(function (err) {
        console.error("Error en carga:", err);
        loadingRef.current = false;
        return false;
      });
  }, []);

  // ── Reload on filter changes (NOT on curDate change — playback handles that) ──
  useEffect(
    function () {
      if (loading) return;
      if (mode === "agg") {
        doLoad({
          days: selDays,
          months: selMonths,
          years: selYears,
          holiday: holiday,
        });
      }
    },
    [mode, selDays, selMonths, selYears, holiday, loading, doLoad],
  );

  // ── Reload on curDate change (disagg mode only) ──
  // This handles BOTH manual date changes AND playback day transitions.
  // The key: we update curDate FIRST, then this effect loads data,
  // then dataVer increments → markers update with correct data.
  useEffect(
    function () {
      if (loading) return;
      if (mode !== "disagg") return;
      if (!curDate) return;
      doLoad({ date: curDate });
    },
    [mode, curDate, loading, doLoad],
  );

  // ── Check holiday for disagg ──
  useEffect(
    function () {
      if (mode !== "disagg" || !curDate) return;
      checkHoliday(curDate).then(function (hol) {
        setDateHol(hol);
      });
    },
    [curDate, mode],
  );

  // ── Autoplay logic ──
  // Playback updates state; loading is handled by the reload effects.
  // On day transitions, we queue the new hour to be applied AFTER the
  // data load completes, to avoid markers reading stale data.
  var hourRef = useRef(hour);
  var curDateRef = useRef(curDate);
  var pendingHourRef = useRef(null); // hour to apply after data loads
  useEffect(
    function () {
      hourRef.current = hour;
    },
    [hour],
  );
  useEffect(
    function () {
      curDateRef.current = curDate;
    },
    [curDate],
  );

  useEffect(
    function () {
      if (!playing) return;
      var interval = Math.round(1000 / fps);
      var t = setInterval(function () {
        // Wait for any in-flight load to finish before advancing
        if (loadingRef.current) return;

        // If there's a pending hour to apply (after day-transition load), apply now
        if (pendingHourRef.current !== null) {
          var ph = pendingHourRef.current;
          pendingHourRef.current = null;
          setHour(ph);
          hourRef.current = ph;
          return;
        }

        var hh = hourRef.current;
        var next = hh + step;

        if (mode === "agg") {
          if (next > 23) {
            setPlaying(false);
            setHour(23);
            return;
          }
          setHour(next);
          return;
        }

        // Disaggregated mode
        var d = curDateRef.current;
        var needsNewDay = false;
        var daysToAdd = 0;
        var newHour = next;

        if (step >= 24) {
          needsNewDay = true;
          daysToAdd = step === 168 ? 7 : Math.floor(step / 24);
          newHour = hh;
        } else if (next > 23) {
          needsNewDay = true;
          daysToAdd = 1;
          newHour = next - 24;
        }

        if (!needsNewDay) {
          setHour(next);
          return;
        }

        // Day transition: compute new date
        var newDate = daysToAdd === 7 ? addWeeks(d, 1) : addDays(d, daysToAdd);
        if (newDate > dateTo) {
          setPlaying(false);
          return;
        }

        // Queue the new hour to apply AFTER the data load.
        // Don't change hour now — that would cause markers to read stale data.
        pendingHourRef.current = newHour;
        // Mark loading immediately so the next tick waits for the actual load
        // to complete. doLoad will set this again, but setting it here closes
        // the gap between setCurDate and doLoad actually running.
        loadingRef.current = true;
        // Change date → reload effect will fire and load data
        setCurDate(newDate);
        curDateRef.current = newDate;
      }, interval);
      return function () {
        clearInterval(t);
      };
    },
    [playing, step, fps, mode, dateTo],
  );

  // ── Slider fill ──
  useEffect(
    function () {
      if (!sliderRef.current) return;
      var pct = (hour / 23) * 100;
      sliderRef.current.style.background =
        "linear-gradient(to right, var(--blue) 0%, var(--blue) " +
        pct +
        "%, var(--border) " +
        pct +
        "%, var(--border) 100%)";
    },
    [hour],
  );

  // ── Bump dataVer when hour changes so markers re-render ──
  // (markers depend ONLY on dataVer to avoid stale-data race conditions)
  useEffect(
    function () {
      if (loading) return;
      setDataVer(function (v) {
        return v + 1;
      });
    },
    [hour, loading],
  );

  var handleStation = useCallback(function (st) {
    setSelSt(st);
  }, []);

  function toggleDay(isoDay) {
    setSelDays(function (prev) {
      var idx = prev.indexOf(isoDay);
      if (idx === -1) return prev.concat([isoDay]);
      var next = prev.slice();
      next.splice(idx, 1);
      return next;
    });
  }
  function toggleMonth(m) {
    setSelMonths(function (prev) {
      var idx = prev.indexOf(m);
      if (idx === -1) return prev.concat([m]);
      var next = prev.slice();
      next.splice(idx, 1);
      return next;
    });
  }
  function toggleYear(y) {
    setSelYears(function (prev) {
      var idx = prev.indexOf(y);
      if (idx === -1) return prev.concat([y]);
      var next = prev.slice();
      next.splice(idx, 1);
      return next;
    });
  }

  var dayLabel = "";
  if (mode === "disagg" && curDate) {
    dayLabel = formatDateShort(curDate) + (dateHol ? " · Festivo" : "");
  } else {
    var dayStrs = selDays.map(function (d) {
      return DAY_NAMES[d - 1];
    });
    dayLabel = dayStrs.length ? dayStrs.join(", ") : "Todos los días";
  }

  function aggCaption() {
    var parts = [];
    if (selDays.length) {
      parts.push(
        selDays
          .map(function (d) {
            return DAY_NAMES[d - 1].toLowerCase();
          })
          .join(", "),
      );
    } else {
      parts.push("todos los días");
    }
    if (selMonths.length) {
      var mNames = selMonths.map(function (m) {
        var found = months.find(function (x) {
          return x.value === m;
        });
        return found ? found.label.toLowerCase() : "mes " + m;
      });
      parts.push(mNames.join(", "));
    }
    if (selYears.length) {
      parts.push(selYears.join(", "));
    }
    if (holiday === "only") parts.push("solo festivos");
    if (holiday === "exclude") parts.push("sin festivos");
    return "Promedio de " + parts.join(" · ") + ".";
  }

  if (loading || error) {
    return h(
      "div",
      { className: "loading-overlay" },
      error
        ? h(
            "div",
            { className: "loading-error" },
            "\u26A0 No se pudo conectar con el servidor.",
            h("br"),
            h("br"),
            error,
            h("br"),
            h("br"),
            "Aseg\u00FArate de que server.py est\u00E1 corriendo.",
          )
        : h(
            React.Fragment,
            null,
            h("div", { className: "loading-spinner" }),
            h(
              "div",
              { className: "loading-text" },
              "Cargando...",
            ),
          ),
    );
  }

  return h(
    "div",
    { className: "app-body" },
    h(
      "aside",
      { className: "sidebar" },
      h(
        "div",
        { className: "sb-sec" },
        h("div", { className: "sb-lbl" }, "Indicador"),
        h(
          "div",
          { style: { fontSize: 13, fontWeight: 600, marginBottom: 6 } },
          "Saturación de estaciones",
        ),
        h(
          "div",
          { className: "mode-caption" },
          "Muestra el nivel de ocupación (ratio bicis/anclajes) de cada estación BiciMAD a lo largo del día. Permite identificar estaciones ",
          h("strong", null, "llenas"),
          " (sin anclajes libres) o ",
          h("strong", null, "vacías"),
          " (sin bicis disponibles) y analizar patrones temporales en modo agregado o desagregado.",
        ),
      ),
      h(
        "div",
        { className: "sb-sec" },
        h("div", { className: "sb-lbl" }, "Tipo de datos"),
        h(
          "div",
          { className: "mode-row" },
          h(
            "button",
            {
              className: "mode-btn " + (mode === "agg" ? "on" : ""),
              onClick: function () {
                setMode("agg");
                setPlaying(false);
              },
            },
            "Agregados",
          ),
          h(
            "button",
            {
              className: "mode-btn " + (mode === "disagg" ? "on" : ""),
              onClick: function () {
                setMode("disagg");
                setPlaying(false);
              },
            },
            "Desagregados",
          ),
        ),

        mode === "agg"
          ? h(
              React.Fragment,
              null,
              h(
                "div",
                { className: "sb-lbl", style: { marginTop: 14 } },
                "Día de la semana",
              ),
              h(
                "div",
                { className: "day-row" },
                DAY_KEYS.map(function (d, idx) {
                  var isoDay = idx + 1;
                  var isOn = selDays.indexOf(isoDay) !== -1;
                  return h(
                    "button",
                    {
                      key: d,
                      className: "day-btn " + (isOn ? "on" : ""),
                      onClick: function () {
                        toggleDay(isoDay);
                      },
                    },
                    d,
                  );
                }),
              ),
              h(
                "div",
                { className: "filter-hint" },
                selDays.length === 0
                  ? "Todos seleccionados"
                  : selDays.length +
                      " de 7 seleccionado" +
                      (selDays.length > 1 ? "s" : ""),
              ),

              h(
                "div",
                { className: "sb-lbl", style: { marginTop: 14 } },
                "Festivos",
              ),
              h(
                "div",
                { className: "holiday-row" },
                [
                  { val: "all", lbl: "Todos" },
                  { val: "exclude", lbl: "Sin festivos" },
                  { val: "only", lbl: "Solo festivos" },
                ].map(function (opt) {
                  return h(
                    "button",
                    {
                      key: opt.val,
                      className: "hol-btn " + (holiday === opt.val ? "on" : ""),
                      onClick: function () {
                        setHoliday(opt.val);
                      },
                    },
                    opt.lbl,
                  );
                }),
              ),

              h(
                "div",
                { className: "sb-lbl", style: { marginTop: 14 } },
                "Mes",
              ),
              h(
                "div",
                { className: "month-row" },
                months.map(function (m) {
                  var isOn = selMonths.indexOf(m.value) !== -1;
                  return h(
                    "button",
                    {
                      key: m.value,
                      className: "month-btn " + (isOn ? "on" : ""),
                      onClick: function () {
                        toggleMonth(m.value);
                      },
                    },
                    m.label.substring(0, 3),
                  );
                }),
              ),
              h(
                "div",
                { className: "filter-hint" },
                selMonths.length === 0
                  ? "Todos los meses"
                  : selMonths.length +
                      " mes" +
                      (selMonths.length > 1 ? "es" : "") +
                      " seleccionado" +
                      (selMonths.length > 1 ? "s" : ""),
              ),

              h(
                "div",
                { className: "sb-lbl", style: { marginTop: 14 } },
                "Año",
              ),
              h(
                "div",
                { className: "year-row" },
                years.map(function (y) {
                  var isOn = selYears.indexOf(y.value) !== -1;
                  return h(
                    "button",
                    {
                      key: y.value,
                      className: "year-btn " + (isOn ? "on" : ""),
                      onClick: function () {
                        toggleYear(y.value);
                      },
                    },
                    String(y.value),
                  );
                }),
              ),
              h(
                "div",
                { className: "filter-hint" },
                selYears.length === 0
                  ? "Todos los años"
                  : selYears.length +
                      " año" +
                      (selYears.length > 1 ? "s" : "") +
                      " seleccionado" +
                      (selYears.length > 1 ? "s" : ""),
              ),

              h("div", { className: "mode-caption" }, aggCaption()),
            )
          : h(
              React.Fragment,
              null,
              h(
                "div",
                { className: "sb-lbl", style: { marginTop: 14 } },
                "Intervalo de fechas",
              ),
              h(
                "div",
                { className: "date-range-row" },
                h(
                  "div",
                  { className: "date-range-field" },
                  h("label", null, "Desde"),
                  h("input", {
                    type: "date",
                    className: "date-inp",
                    value: dateFrom,
                    min: _dateRange.min,
                    max: _dateRange.max,
                    onChange: function (e) {
                      var v = e.target.value;
                      setDateFrom(v);
                      setCurDate(v);
                      if (v > dateTo) setDateTo(v);
                    },
                  }),
                ),
                h(
                  "div",
                  { className: "date-range-field" },
                  h("label", null, "Hasta"),
                  h("input", {
                    type: "date",
                    className: "date-inp",
                    value: dateTo,
                    min: _dateRange.min,
                    max: _dateRange.max,
                    onChange: function (e) {
                      setDateTo(e.target.value);
                    },
                  }),
                ),
              ),
              h(
                "div",
                { className: "day-badge " + (dateHol ? "holiday" : "workday") },
                h("div", { className: "dot" }),
                h(
                  "span",
                  { className: "lbl" },
                  dateHol ? "Festivo" : "Día laborable",
                ),
              ),
              h(
                "div",
                { className: "mode-caption" },
                "Datos del ",
                h("strong", null, dayLabel),
                curDate ? " — " + curDate : ".",
              ),
            ),
      ),
      h(Ind1Stats, { hour: hour, key: "stats-" + dataVer }),
      h(
        "div",
        { className: "sb-sec" },
        h("div", { className: "sb-lbl" }, "Leyenda"),
        h(
          "div",
          { className: "leg-swatches" },
          h(
            "div",
            { className: "leg-sw" },
            h("div", {
              className: "leg-dot",
              style: { background: "#2B5CF6" },
            }),
            h("span", null, "Llena (>65%)"),
          ),
          h(
            "div",
            { className: "leg-sw" },
            h("div", {
              className: "leg-dot",
              style: { background: "#E8421A" },
            }),
            h("span", null, "Vacía (<35%)"),
          ),
        ),
        h(
          "div",
          { className: "leg-neutral" },
          h("div", { className: "leg-mini" }),
          h("span", null, "Equilibrada (35–65%) — sin blob"),
        ),
        h(
          "div",
          { className: "leg-neutral", style: { marginTop: 4 } },
          h("div", {
            className: "leg-mini",
            style: { background: "#D8D2C8", opacity: 0.6 },
          }),
          h("span", null, "Sin datos para esta fecha"),
        ),
        h(
          "div",
          { className: "leg-note" },
          "El área difuminada refleja la intensidad de la condición. Haz clic en cualquier estación para ver su detalle.",
        ),
      ),
    ),
    h(
      "main",
      { className: "map-area" },
      h(Ind1MapView, {
        hour: hour,
        onStationClick: handleStation,
        dataVer: dataVer,
      }),
      selSt
        ? h(Ind1StationCard, {
            station: selSt,
            hour: hour,
            onClose: function () {
              setSelSt(null);
            },
          })
        : null,
      h(
        "div",
        { className: "time-bar" },
        h(
          "div",
          { className: "tb-top" },
          h(
            "button",
            {
              className: "tb-play",
              onClick: function () {
                setPlaying(function (p) {
                  return !p;
                });
              },
            },
            playing ? "\u23F8" : "\u25B6",
          ),
          h(
            "div",
            null,
            h("div", { className: "tb-hour" }, hLabel(hour)),
            mode === "disagg"
              ? h("div", { className: "tb-ctx" }, formatDateShort(curDate))
              : null,
          ),
          h(
            "div",
            { className: "tb-day" },
            dayLabel,
            mode === "agg" && selMonths.length
              ? h(
                  "span",
                  { className: "tb-month-tag" },
                  " · " +
                    selMonths
                      .map(function (m) {
                        var found = months.find(function (x) {
                          return x.value === m;
                        });
                        return found ? found.label.substring(0, 3) : "";
                      })
                      .join(", "),
                )
              : null,
          ),
        ),
        h(Ind1PlaybackControls, {
          step: step,
          setStep: setStep,
          fps: fps,
          setFps: setFps,
          mode: mode === "agg" ? "agg" : "disagg",
        }),
        h(
          "div",
          { className: "tb-slider-row" },
          h("input", {
            ref: sliderRef,
            type: "range",
            min: 0,
            max: 23,
            value: hour,
            onChange: function (e) {
              setPlaying(false);
              setHour(Number(e.target.value));
            },
          }),
        ),
        h(
          "div",
          { className: "tb-ticks" },
          [0, 3, 6, 9, 12, 15, 18, 21, 23].map(function (hh) {
            return h(
              "span",
              { key: hh, className: "tb-tick" },
              String(hh).padStart(2, "0") + "h",
            );
          }),
        ),
      ),
    ),
  );
}
