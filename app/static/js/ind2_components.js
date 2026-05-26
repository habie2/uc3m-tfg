/* ═══════════════════════════════════════════════════════
   Indicador 2 — Componentes React (Tránsito por tipo de vía)
   ═══════════════════════════════════════════════════════ */

/* ─── Ind2View: contenedor completo del indicador 2 ──── */
function Ind2View() {
  var _s1 = useState(true);
  var loading = _s1[0];
  var setLoading = _s1[1];
  var _s2 = useState(null);
  var error = _s2[0];
  var setError = _s2[1];
  var _s3 = useState("global");
  var mode = _s3[0];
  var setMode = _s3[1];
  var _s4 = useState(null);
  var selCell = _s4[0];
  var setSelCell = _s4[1];
  var _s5 = useState(0);
  var dataVer = _s5[0];
  var setDataVer = _s5[1];

  useEffect(function () {
    loadInd2Data()
      .then(function () {
        setDataVer(function (v) {
          return v + 1;
        });
        setLoading(false);
      })
      .catch(function (err) {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  function handleCellClick(cell) {
    setSelCell(cell);
    setMode("cell");
  }

  function handleClose() {
    setSelCell(null);
  }

  function handleModeGlobal() {
    setMode("global");
    setSelCell(null);
  }

  if (loading)
    return h(
      "div",
      { className: "loading-overlay" },
      h("div", { className: "loading-spinner" }),
      h("div", { className: "loading-text" }, "Cargando tránsito…"),
    );
  if (error)
    return h(
      "div",
      { className: "loading-overlay" },
      h("div", { className: "loading-error" }, "⚠ " + error),
    );

  return h(
    "div",
    { className: "app-body" },
    h(
      "aside",
      { className: "sidebar" },
      h(
        "div",
        { className: "sb-sec" },
        h("div", { className: "sb-lbl" }, "Modo de visualización"),
        h(
          "div",
          { className: "mode-row" },
          h(
            "button",
            {
              className: "mode-btn " + (mode === "global" ? "on" : ""),
              onClick: handleModeGlobal,
            },
            "Análisis global",
          ),
          h(
            "button",
            {
              className: "mode-btn " + (mode === "cell" ? "on" : ""),
              onClick: function () {
                setMode("cell");
              },
            },
            "Análisis de celda",
          ),
        ),
        h(
          "div",
          { className: "mode-caption" },
          mode === "global"
            ? h(
                React.Fragment,
                null,
                "Agregado sobre ",
                h("strong", null, "todos los viajes"),
                " del histórico BiciMAD.",
              )
            : "Haz clic sobre cualquier celda del mapa para ver el detalle por tipo de vía.",
        ),
      ),
      mode === "global"
        ? h(Ind2GlobalPanel, { key: "gp-" + dataVer })
        : h(Ind2CellPanel, { cell: selCell }),
      h(Ind2Legend, { mode: mode }),
    ),
    h(
      "main",
      { className: "map-area" },
      h(Ind2MapView, {
        mode: mode,
        selCell: selCell,
        onCellClick: handleCellClick,
        key: "map2-" + dataVer,
      }),
      selCell
        ? h(Ind2CellCard, {
            cell: selCell,
            onClose: handleClose,
          })
        : null,
    ),
  );
}

/* ─── Panel global (sidebar) ──────────────────────────── */
function Ind2GlobalPanel() {
  var cats = _ind2Categories.slice().sort(function (a, b) {
    return b.meters - a.meters;
  });
  var max = Math.max.apply(
    null,
    cats.map(function (c) {
      return c.meters;
    }),
  );
  var stats = _ind2Stats;

  return h(
    React.Fragment,
    null,
    h(
      "div",
      { className: "sb-sec" },
      h("div", { className: "sb-lbl" }, "Estadísticas globales"),
      h(
        "div",
        { className: "stat-list" },
        h(
          "div",
          { className: "stat-row2" },
          h(
            "div",
            { className: "stat-info" },
            h("span", { className: "stat-lbl" }, "Tránsito total"),
            h("span", { className: "stat-sub" }, "todas las celdas"),
          ),
          h(
            "span",
            { className: "stat-val", style: { color: "var(--blue)" } },
            fmtKm(stats ? stats.total_meters : 0),
          ),
        ),
        stats && stats.top_cell
          ? h(
              "div",
              { className: "stat-row2" },
              h(
                "div",
                { className: "stat-info" },
                h("span", { className: "stat-lbl" }, "Celda más intensa"),
                h(
                  "span",
                  { className: "stat-sub" },
                  stats.top_cell.label || "Celda " + stats.top_cell.cell_id,
                ),
              ),
              h(
                "span",
                { className: "stat-val", style: { color: "var(--blue)" } },
                fmtKm(stats.top_cell.meters),
              ),
            )
          : null,
        stats && stats.dominant
          ? h(
              "div",
              { className: "stat-row2" },
              h(
                "div",
                { className: "stat-info" },
                h("span", { className: "stat-lbl" }, "Tipo dominante"),
                h(
                  "span",
                  { className: "stat-sub" },
                  fmtPct(stats.dominant.pct) + " del total",
                ),
              ),
              h(
                "span",
                { className: "stat-val", style: { color: "var(--blue)" } },
                stats.dominant.display_name,
              ),
            )
          : null,
      ),
    ),
  );
}

/* ─── Panel celda (sidebar) ───────────────────────────── */
function Ind2CellPanel(props) {
  var cell = props.cell;
  var cats = _ind2Categories.slice().sort(function (a, b) {
    return b.meters - a.meters;
  });
  var max = Math.max.apply(
    null,
    cats.map(function (c) {
      return c.meters;
    }),
  );

  return h(
    React.Fragment,
    null,
    h(
      "div",
      { className: "sb-sec" },
      h("div", { className: "sb-lbl" }, "Modo análisis de celda"),
      cell
        ? h(
            "div",
            { className: "mode-caption" },
            "Mostrando vías OSM y rutas OD de la celda ",
            h(
              "strong",
              null,
              cell.label || "C-" + String(cell.cell_id).padStart(3, "0"),
            ),
            ". Las líneas coloreadas representan tramos de calle, las bandas azules las rutas más frecuentes.",
          )
        : h(
            "div",
            { className: "mode-caption" },
            "Haz clic sobre cualquier celda del mapa para ver metros por tipo de vía, distribución porcentual y vías OSM diferenciadas por color.",
          ),
    ),
    h(
      "div",
      { className: "sb-sec" },
      h("div", { className: "sb-lbl" }, "Intensidad global por tipo de vía"),
      h(
        "div",
        { className: "via-list" },
        cats.map(function (cat) {
          var color = getInd2Color(cat.category_code);
          return h(
            "div",
            { key: cat.category_code, className: "via-row" },
            h("div", { className: "via-swatch", style: { background: color } }),
            h(
              "div",
              { className: "via-info" },
              h("div", { className: "via-name" }, cat.display_name),
              h(
                "div",
                { className: "via-bar" },
                h("div", {
                  className: "via-bar-fill",
                  style: {
                    width: max
                      ? ((cat.meters / max) * 100).toFixed(1) + "%"
                      : "0%",
                    background: color,
                  },
                }),
              ),
            ),
            h(
              "div",
              { className: "via-value" },
              fmtKm(cat.meters),
              h("span", { className: "pct" }, fmtPct(cat.pct)),
            ),
          );
        }),
      ),
    ),
  );
}

/* ─── Leyenda ─────────────────────────────────────────── */
function Ind2Legend(props) {
  return h(
    "div",
    { className: "sb-sec" },
    h("div", { className: "sb-lbl" }, "Leyenda"),
    props.mode === "global"
      ? h(
          React.Fragment,
          null,
          h(
            "div",
            { className: "leg-sw", style: { marginBottom: 6 } },
            h("div", {
              style: {
                width: 40,
                height: 10,
                borderRadius: 3,
                background: "linear-gradient(90deg,#fff5ee,#8C3A2D)",
              },
            }),
            h(
              "span",
              { style: { fontSize: 12, color: "var(--muted)", marginLeft: 8 } },
              "Intensidad: claro → oscuro",
            ),
          ),
          h(
            "div",
            { className: "leg-note" },
            "Cada celda muestra los km totales transitados. Haz clic en una celda para ver su detalle.",
          ),
        )
      : h(
          React.Fragment,
          null,
          h(
            "div",
            { className: "leg-sw", style: { marginBottom: 6 } },
            h("div", {
              style: {
                width: 40,
                height: 10,
                borderRadius: 3,
                background: "linear-gradient(90deg, #c8d8f4, #4060c8)",
              },
            }),
            h(
              "span",
              { style: { fontSize: 12, color: "var(--muted)", marginLeft: 8 } },
              "Rutas OD: grosor = frecuencia",
            ),
          ),
          _ind2Categories.map(function (cat) {
            return h(
              "div",
              {
                key: cat.category_code,
                className: "leg-sw",
                style: { marginBottom: 4 },
              },
              h("div", {
                className: "leg-dot",
                style: { background: getInd2Color(cat.category_code) },
              }),
              h(
                "span",
                {
                  style: { fontSize: 12, color: "var(--muted)", marginLeft: 4 },
                },
                cat.display_name,
              ),
            );
          }),
          h(
            "div",
            { className: "leg-note", style: { marginTop: 6 } },
            "Los trazos de color representan vías OSM clasificadas por tipo. Las bandas azules semitransparentes son rutas OD (origen–destino).",
          ),
        ),
  );
}

/* ─── MapView (ind2) ──────────────────────────────────── */
function Ind2MapView(props) {
  var mode = props.mode;
  var selCell = props.selCell;
  var onCellClick = props.onCellClick;
  var mountRef = useRef(null);
  var mapRef = useRef(null);
  var layersRef = useRef({});

  function clearLayers() {
    ["cellLayer", "labelLayer", "waysLayer", "borderLayer"].forEach(
      function (k) {
        if (layersRef.current[k]) {
          layersRef.current[k].remove();
          layersRef.current[k] = null;
        }
      },
    );
  }

  function intensityColor(value, max) {
    var t = Math.min(1, value / (max || 1));
    var start = [255, 245, 238],
      end = [140, 58, 45];
    var rgb = start.map(function (s, i) {
      return Math.round(s + (end[i] - s) * t);
    });
    return "rgb(" + rgb.join(",") + ")";
  }

  /* ── Modo global: rectángulos de intensidad ── */
  function renderGlobal(map) {
    clearLayers();
    if (!_ind2Cells.length) return;
    var max = Math.max.apply(
      null,
      _ind2Cells.map(function (c) {
        return c.total_meters;
      }),
    );
    var cellLayer = L.layerGroup().addTo(map);
    var labelLayer = L.layerGroup().addTo(map);
    layersRef.current.cellLayer = cellLayer;
    layersRef.current.labelLayer = labelLayer;

    _ind2Cells.forEach(function (cell) {
      var bounds = [
        [cell.south, cell.west],
        [cell.north, cell.east],
      ];
      var rect = L.rectangle(bounds, {
        color: "#fff",
        weight: 1,
        fillColor: intensityColor(cell.total_meters, max),
        fillOpacity: 0.45,
      }).addTo(cellLayer);
      rect.on("click", function () {
        onCellClick(cell);
      });
      rect.on("mouseover", function () {
        this.setStyle({ weight: 2.5, color: "#333" });
      });
      rect.on("mouseout", function () {
        this.setStyle({ weight: 1, color: "#fff" });
      });

      L.marker([cell.centroid_lat, cell.centroid_lon], {
        icon: L.divIcon({
          className: "cell-label",
          html: fmtKm(cell.total_meters),
          iconSize: [60, 18],
          iconAnchor: [30, 9],
        }),
        interactive: false,
      }).addTo(labelLayer);
    });
  }

  /* ── Modo celda: grid tenue + clic para seleccionar ── */
  function renderCellGrid(map) {
    clearLayers();
    var cellLayer = L.layerGroup().addTo(map);
    layersRef.current.cellLayer = cellLayer;
    _ind2Cells.forEach(function (cell) {
      var bounds = [
        [cell.south, cell.west],
        [cell.north, cell.east],
      ];
      var rect = L.rectangle(bounds, {
        color: "#ddd",
        weight: 0.5,
        fillColor: "#fafafa",
        fillOpacity: 0.15,
      }).addTo(cellLayer);
      rect.on("click", function () {
        onCellClick(cell);
      });
      rect.on("mouseover", function () {
        this.setStyle({ weight: 1.5, color: "#999" });
      });
      rect.on("mouseout", function () {
        this.setStyle({ weight: 0.5, color: "#ddd" });
      });
    });
  }

  /* ── Dibujar borde punteado de la celda seleccionada ── */
  function drawBorder(map, cell) {
    if (layersRef.current.borderLayer) {
      layersRef.current.borderLayer.remove();
      layersRef.current.borderLayer = null;
    }
    if (!cell) return;
    var bounds = [
      [cell.south, cell.west],
      [cell.north, cell.east],
    ];
    layersRef.current.borderLayer = L.rectangle(bounds, {
      color: "#4f5ce8",
      weight: 2.5,
      fill: false,
      dashArray: "6 4",
      interactive: false,
      pane: "borderPane",
    }).addTo(map);
  }

  /* ── Dibujar rutas OD + vías OSM de la celda seleccionada ── */
  function drawCellWays(map, cell) {
    if (layersRef.current.waysLayer) {
      layersRef.current.waysLayer.remove();
      layersRef.current.waysLayer = null;
    }
    if (!cell) return;

    var waysGroup = L.layerGroup().addTo(map);
    layersRef.current.waysLayer = waysGroup;

    // Capa 1: rutas OD como bandas azules (grosor ∝ num_trips)
    loadInd2CellRoutes(cell.cell_id)
      .then(function (routes) {
        if (routes && routes.features && routes.features.length) {
          var trips = routes.features.map(function (f) {
            return f.properties.num_trips;
          });
          var maxT = Math.max.apply(null, trips);
          var minT = Math.min.apply(null, trips);
          var range = maxT - minT || 1;

          var sorted = routes.features.slice().sort(function (a, b) {
            return a.properties.num_trips - b.properties.num_trips;
          });

          var routeGroup = L.layerGroup();
          sorted.forEach(function (feat) {
            var t = (feat.properties.num_trips - minT) / range;
            var tLog = Math.log(1 + t * 9) / Math.log(10);
            L.geoJSON(feat, {
              style: {
                color: "#a8c4f0",
                weight: 2 + tLog * 18,
                opacity: 0.5,
                lineCap: "round",
                lineJoin: "round",
              },
              pane: "routePane",
            }).addTo(routeGroup);
          });
          routeGroup.addTo(waysGroup);
        }
      })
      .catch(function (e) {
        console.warn("No se pudieron cargar las rutas OD:", e);
      });

    // Capa 2: vías OSM coloreadas por tipo (encima de las rutas)
    loadInd2CellWays(cell.cell_id)
      .then(function (geojson) {
        if (!geojson || !geojson.features) return;
        L.geoJSON(geojson, {
          style: function (feature) {
            return {
              color: getInd2Color(feature.properties.category_code),
              weight: 3,
              opacity: 0.9,
              pane: "waysPane",
            };
          },
          onEachFeature: function (feature, layer) {
            if (feature.properties.name) {
              layer.bindTooltip(feature.properties.name, { sticky: true });
            }
          },
        }).addTo(waysGroup);
      })
      .catch(function (e) {
        console.warn("No se pudieron cargar las vías OSM:", e);
      });

    // Zoom a la celda
    var bounds = [
      [cell.south, cell.west],
      [cell.north, cell.east],
    ];
    map.flyToBounds(bounds, { padding: [80, 80], duration: 0.6 });
  }

  // Inicialización del mapa
  useEffect(function () {
    var map = L.map(mountRef.current, {
      center: [40.4168, -3.7038],
      zoom: 13,
      zoomControl: true,
      preferCanvas: false,
    });
    L.tileLayer(
      "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
      {
        attribution: "&copy; OpenStreetMap &copy; CARTO",
        subdomains: "abcd",
        maxZoom: 19,
      },
    ).addTo(map);

    // Panes con z-index para controlar el orden visual:
    // borde (abajo) → rutas OD (medio) → vías OSM (arriba)
    map.createPane("borderPane");
    map.getPane("borderPane").style.zIndex = 410;
    map.createPane("routePane");
    map.getPane("routePane").style.zIndex = 420;
    map.createPane("waysPane");
    map.getPane("waysPane").style.zIndex = 430;

    mapRef.current = map;
    renderGlobal(map);
    return function () {
      map.remove();
    };
  }, []);

  // Reaccionar a cambio de modo
  useEffect(
    function () {
      if (!mapRef.current) return;
      if (mode === "global") {
        renderGlobal(mapRef.current);
      } else {
        renderCellGrid(mapRef.current);
        if (selCell) {
          drawBorder(mapRef.current, selCell);
          drawCellWays(mapRef.current, selCell);
        }
      }
    },
    [mode],
  );

  // Reaccionar a selección de celda (en modo cell)
  useEffect(
    function () {
      if (!mapRef.current || mode !== "cell") return;
      drawBorder(mapRef.current, selCell);
      drawCellWays(mapRef.current, selCell);
    },
    [selCell],
  );

  return h("div", { ref: mountRef, id: "map-mount" });
}

/* ─── CellCard (ind2) ─────────────────────────────────── */
function Ind2CellCard(props) {
  var cell = props.cell;
  var onClose = props.onClose;
  var _s = useState(null);
  var detail = _s[0];
  var setDetail = _s[1];

  useEffect(
    function () {
      if (!cell) return;
      setDetail(null);
      loadInd2CellDetail(cell.cell_id).then(setDetail);
    },
    [cell],
  );

  if (!detail)
    return h(
      "div",
      { className: "station-card" },
      h("div", {
        className: "loading-spinner",
        style: { margin: "20px auto" },
      }),
    );

  return h(
    "div",
    { className: "station-card" },
    h(
      "div",
      { className: "sc-head" },
      h(
        "div",
        null,
        h(
          "div",
          { className: "sc-name" },
          detail.label || "Celda " + detail.cell_id,
        ),
        h(
          "div",
          { className: "sc-cap" },
          "Celda C-" + String(detail.cell_id).padStart(3, "0"),
        ),
      ),
      h("button", { className: "sc-close", onClick: onClose }, "\u00D7"),
    ),
    h(
      "div",
      { className: "cell-card-metrics" },
      h(
        "div",
        { className: "cell-card-metric" },
        h("div", { className: "value" }, fmtKm(detail.total_meters)),
        h("div", { className: "label" }, "km transitados"),
      ),
      h(
        "div",
        { className: "cell-card-metric" },
        h(
          "div",
          { className: "value" },
          (detail.num_trips || 0).toLocaleString(),
        ),
        h("div", { className: "label" }, "viajes"),
      ),
    ),
    h("div", { className: "sb-lbl" }, "Distribución por tipo"),
    detail.distribution
      ? detail.distribution.map(function (it) {
          return h(
            "div",
            { key: it.category_code, className: "dist-row" },
            h("div", {
              className: "dist-swatch",
              style: { background: getInd2Color(it.category_code) },
            }),
            h("div", { className: "dist-name" }, it.display_name),
            h(
              "div",
              { className: "dist-vals" },
              fmtKm(it.meters) + " · " + fmtPct(it.pct),
            ),
          );
        })
      : null,
  );
}
