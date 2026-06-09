/* ═══════════════════════════════════════════════════════
   BiciMAD · App principal — Plataforma de Indicadores
   ═══════════════════════════════════════════════════════
*/

var h = React.createElement;

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
              "Cargando estaciones\u2026",
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
          "\u00CDndice de saturaci\u00F3n de estaciones",
        ),
        h(
          "div",
          { className: "mode-caption" },
          "Muestra el nivel de ocupaci\u00F3n (ratio bicis/anclajes) de cada estaci\u00F3n BiciMAD a lo largo del d\u00EDa. Permite identificar estaciones ",
          h("strong", null, "llenas"),
          " (sin anclajes libres) o ",
          h("strong", null, "vac\u00EDas"),
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

/* ═══════════════════════════════════════════════════════
   App principal
   ═══════════════════════════════════════════════════════ */
function App() {
  var _s = useState(1);
  var ind = _s[0];
  var setInd = _s[1];

  var TABS = [
    { id: 1, label: "Saturaci\u00F3n" },
    { id: 2, label: "Tr\u00E1nsito" },
    { id: 3, label: "Captura" },
  ];

  return h(
    "div",
    { className: "app" },
    h(
      "header",
      { className: "header" },
      h(
        "div",
        { className: "logo" },
        h("span", { className: "logo-bici" }, "bici"),
        h("span", { className: "logo-dot" }),
        h("span", { className: "logo-mad" }, "mad"),
      ),
      h("div", { className: "hd-sep" }),
      h(
        "div",
        { className: "nav-tabs" },
        TABS.map(function (tab) {
          return h(
            "button",
            {
              key: tab.id,
              className: "nav-tab " + (ind === tab.id ? "on" : ""),
              onClick: function () {
                setInd(tab.id);
              },
            },
            tab.label,
          );
        }),
      ),
      h(
        "button",
        {
          className: "download-btn",
          title: "Descargar datos en crudo del indicador actual",
          onClick: function () {
            downloadRawData(ind);
          },
        },
        h(
          "svg",
          {
            width: 16,
            height: 16,
            viewBox: "0 0 16 16",
            fill: "none",
            stroke: "currentColor",
            strokeWidth: 1.8,
            strokeLinecap: "round",
            strokeLinejoin: "round",
          },
          h("path", { d: "M8 2v8m0 0l-3-3m3 3l3-3" }),
          h("path", { d: "M2 12v1.5a.5.5 0 00.5.5h11a.5.5 0 00.5-.5V12" }),
        ),
        h("span", null, "Datos"),
      ),
    ),
    ind === 1 ? h(Ind1View) : null,
    ind === 2 ? h(Ind2View) : null,
    ind === 3 ? h(Ind3View) : null,
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(h(App));
