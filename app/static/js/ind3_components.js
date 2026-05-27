/* ═══════════════════════════════════════════════════════
   Indicador 3 — Componentes React (Captura intermodal)
   ═══════════════════════════════════════════════════════ */

/* ─── Ind3View: contenedor completo del indicador 3 ──── */
function Ind3View() {
  var _s1 = useState(true);
  var loading = _s1[0];
  var setLoading = _s1[1];
  var _s2 = useState(null);
  var error = _s2[0];
  var setError = _s2[1];
  var _s3 = useState(300);
  var radius = _s3[0];
  var setRadius = _s3[1];
  var _s4 = useState("total");
  var metric = _s4[0];
  var setMetric = _s4[1];
  var _s5 = useState(null);
  var selId = _s5[0];
  var setSelId = _s5[1];
  var _s6 = useState([]);
  var nodes = _s6[0];
  var setNodes = _s6[1];
  var _s7 = useState(null);
  var stats = _s7[0];
  var setStats = _s7[1];
  var _s8 = useState([150, 300, 500]);
  var radii = _s8[0];
  var setRadii = _s8[1];
  var _s9 = useState(0);
  var dataVer = _s9[0];
  var setDataVer = _s9[1];

  function metricValue(n) {
    return metric === "out" ? n.out : metric === "in" ? n["in"] : n.captured;
  }

  // Carga inicial: config + datos
  useEffect(function () {
    loadInd3Config()
      .then(function (cfg) {
        if (cfg && cfg.radii) setRadii(cfg.radii);
        var r = (cfg && cfg.default_radius) || 300;
        setRadius(r);
        return loadInd3Data(r);
      })
      .then(function (res) {
        setNodes(res.nodes);
        setStats(res.stats);
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

  // Recargar cuando cambia el radio
  function changeRadius(r) {
    setRadius(r);
    setSelId(null);
    loadInd3Data(r).then(function (res) {
      setNodes(res.nodes);
      setStats(res.stats);
      setDataVer(function (v) {
        return v + 1;
      });
    });
  }

  var selNode = selId
    ? nodes.find(function (n) {
        return String(n.id) === String(selId);
      })
    : null;

  if (loading)
    return h(
      "div",
      { className: "loading-overlay" },
      h("div", { className: "loading-spinner" }),
      h("div", { className: "loading-text" }, "Cargando captura intermodal…"),
    );
  if (error)
    return h(
      "div",
      { className: "loading-overlay" },
      h("div", { className: "loading-error" }, "\u26A0 " + error),
    );

  return h(
    "div",
    { className: "app-body" },
    h(
      "aside",
      { className: "sidebar" },

      // Descripción
      h(
        "div",
        { className: "sb-sec" },
        h("div", { className: "sb-lbl" }, "Indicador"),
        h(
          "div",
          { style: { fontSize: 13, fontWeight: 600, marginBottom: 6 } },
          "\u00CDndice de captura intermodal",
        ),
        h(
          "div",
          { className: "mode-caption" },
          "Viajes BiciMAD que se originan o terminan en el radio de influencia de cada ",
          h("strong", null, "estaci\u00F3n de Metro / Cercan\u00EDas"),
          ".",
        ),
      ),

      // Radio de influencia
      h(
        "div",
        { className: "sb-sec" },
        h("div", { className: "sb-lbl" }, "Radio de influencia"),
        h(
          "div",
          { className: "radio-row" },
          radii.map(function (r) {
            return h(
              "button",
              {
                key: r,
                className: "radio-btn " + (radius === r ? "on" : ""),
                onClick: function () {
                  changeRadius(r);
                },
              },
              r + " m",
            );
          }),
        ),
        h(
          "div",
          { className: "mode-caption", style: { marginTop: 6 } },
          "Distancia a pie desde la boca de metro a la estaci\u00F3n BiciMAD.",
        ),
      ),

      // Métrica mostrada
      h(
        "div",
        { className: "sb-sec" },
        h("div", { className: "sb-lbl" }, "M\u00E9trica mostrada"),
        h(
          "div",
          { className: "metric-row" },
          [
            ["total", "Total"],
            ["out", "Salidas"],
            ["in", "Llegadas"],
          ].map(function (pair) {
            return h(
              "button",
              {
                key: pair[0],
                className: "metric-btn " + (metric === pair[0] ? "on" : ""),
                onClick: function () {
                  setMetric(pair[0]);
                },
              },
              pair[1],
            );
          }),
        ),
      ),

      // Donut de la estación seleccionada (solo si hay selección)
      selNode
        ? h(Ind3NodeDonut, { node: selNode, stats: stats, radius: radius })
        : null,

      // Barra compacta de cobertura global (siempre visible)
      h(Ind3GlobalBar, { stats: stats, radius: radius }),

      // Ranking
      h(Ind3Ranking, {
        nodes: nodes,
        metric: metric,
        metricValue: metricValue,
        selId: selId,
        onSelect: function (id) {
          setSelId(id);
        },
      }),

      // Estadísticas globales
      h(Ind3GlobalStats, { stats: stats, radius: radius }),

      // Leyenda
      h(
        "div",
        { className: "sb-sec" },
        h("div", { className: "sb-lbl" }, "Leyenda"),
        h(
          "div",
          { className: "leg-sw", style: { marginBottom: 6 } },
          h("div", {
            style: {
              width: 40,
              height: 10,
              borderRadius: 3,
              background: "linear-gradient(90deg, var(--cap-0), var(--cap-4))",
            },
          }),
          h(
            "span",
            { style: { fontSize: 12, color: "var(--muted)", marginLeft: 8 } },
            "Captura: baja \u2192 alta",
          ),
        ),
        h(
          "div",
          { className: "leg-sw", style: { marginBottom: 6 } },
          h("div", {
            className: "leg-dot",
            style: { background: "var(--c-bici)" },
          }),
          h(
            "span",
            { style: { fontSize: 12, color: "var(--muted)", marginLeft: 4 } },
            "Estaci\u00F3n BiciMAD asignada",
          ),
        ),
        h(
          "div",
          { className: "leg-note" },
          "La intensidad y extensi\u00F3n del difuminado de cada estaci\u00F3n de Metro son proporcionales a los viajes BiciMAD capturados. Haz clic para ver el detalle y el radio de influencia.",
        ),
      ),
    ),

    // Mapa + tarjeta flotante
    h(
      "main",
      { className: "map-area" },
      h(Ind3MapView, {
        nodes: nodes,
        metric: metric,
        metricValue: metricValue,
        selId: selId,
        onSelect: function (id) {
          setSelId(id);
        },
        radius: radius,
        key: "map3-" + dataVer,
      }),
      selNode
        ? h(Ind3NodeCard, {
            node: selNode,
            metricValue: metricValue,
            onClose: function () {
              setSelId(null);
            },
          })
        : null,
    ),
  );
}

/* ─── Ranking de nodos (sidebar) ─────────────────────── */
function Ind3Ranking(props) {
  var nodes = props.nodes;
  var metricValue = props.metricValue;
  var selId = props.selId;
  var onSelect = props.onSelect;

  var sorted = nodes.slice().sort(function (a, b) {
    return metricValue(b) - metricValue(a);
  });
  var top25 = sorted.slice(0, 25);
  var max = top25.length ? metricValue(top25[0]) : 1;

  return h(
    "div",
    { className: "sb-sec" },
    h("div", { className: "sb-lbl" }, "Ranking de nodos"),
    h(
      "div",
      { className: "rank-list" },
      top25.map(function (n, idx) {
        var v = metricValue(n);
        var isSel = String(n.id) === String(selId);
        return h(
          "div",
          {
            key: n.id,
            className: "rank-row" + (isSel ? " selected" : ""),
            onClick: function () {
              onSelect(n.id);
            },
          },
          h("div", { className: "rank-pos" }, idx + 1),
          h(
            "div",
            { className: "rank-info" },
            h("div", { className: "rank-name" }, n.name),
            h(
              "div",
              { className: "rank-bar" },
              h("div", {
                className: "rank-bar-fill",
                style: {
                  width: max ? ((v / max) * 100).toFixed(1) + "%" : "0%",
                },
              }),
            ),
          ),
          h(
            "div",
            { className: "rank-value" },
            fmt(v),
            h(
              "span",
              { className: "sub" },
              n.stations.length + " est. BiciMAD",
            ),
          ),
        );
      }),
    ),
  );
}

/* ─── Estadísticas globales (sidebar) ────────────────── */
function Ind3GlobalStats(props) {
  var stats = props.stats;
  var radius = props.radius;
  if (!stats) return null;

  return h(
    "div",
    { className: "sb-sec" },
    h("div", { className: "sb-lbl" }, "Estad\u00EDsticas globales"),
    h(
      "div",
      { className: "stat-list" },
      h(
        "div",
        { className: "stat-row2" },
        h(
          "div",
          { className: "stat-info" },
          h("span", { className: "stat-lbl" }, "Viajes intermodales"),
          h("span", { className: "stat-sub" }, "radio " + radius + " m"),
        ),
        h(
          "span",
          { className: "stat-val", style: { color: "var(--blue)" } },
          fmt(stats.total_intermodal),
        ),
      ),
      stats.top_node
        ? h(
            "div",
            { className: "stat-row2" },
            h(
              "div",
              { className: "stat-info" },
              h("span", { className: "stat-lbl" }, "Nodo l\u00EDder"),
              h("span", { className: "stat-sub" }, stats.top_node.name),
            ),
            h(
              "span",
              { className: "stat-val", style: { color: "var(--blue)" } },
              fmt(stats.top_node.captured),
            ),
          )
        : null,
      h(
        "div",
        { className: "stat-row2" },
        h(
          "div",
          { className: "stat-info" },
          h("span", { className: "stat-lbl" }, "% del hist\u00F3rico BiciMAD"),
          h("span", { className: "stat-sub" }, "cobertura intermodal"),
        ),
        h(
          "span",
          { className: "stat-val", style: { color: "var(--blue)" } },
          (stats.share_pct != null ? stats.share_pct : "\u2014") + "%",
        ),
      ),
    ),
  );
}

/* ─── MapView (ind3) ─────────────────────────────────── */
/*
   Render: cada nodo se dibuja como un BLOB DIFUMINADO con radio en
   METROS REALES (no píxeles), por lo que escala correctamente con
   el zoom. La intensidad (opacidad central) refleja el volumen de
   viajes con una escala potencial para que las diferencias se noten.

   Al hacer click en un nodo se dibuja un ANILLO DISCONTINUO con el
   radio de influencia elegido (también en metros reales).
*/
function Ind3MapView(props) {
  var nodes = props.nodes;
  var metricValue = props.metricValue;
  var selId = props.selId;
  var onSelect = props.onSelect;
  var radiusM = props.radius;

  var mountRef = useRef(null);
  var mapRef = useRef(null);
  var svgRef = useRef(null);
  var defsRef = useRef(null);
  var blobsGRef = useRef(null);
  var hitGRef = useRef(null);
  var layersRef = useRef({});

  // Refs "vivas" — siempre apuntan al valor más reciente. Los listeners
  // de Leaflet, registrados una sola vez, leen de aquí en lugar de
  // capturar valores obsoletos en closures.
  var nodesRef = useRef(nodes);
  var metricValueRef = useRef(metricValue);
  var selIdRef = useRef(selId);
  var onSelectRef = useRef(onSelect);
  var radiusMRef = useRef(radiusM);
  nodesRef.current = nodes;
  metricValueRef.current = metricValue;
  selIdRef.current = selId;
  onSelectRef.current = onSelect;
  radiusMRef.current = radiusM;

  var BLOB_MIN_M = 90;
  var BLOB_MAX_M = 300;

  function metersToPixels(latlng, meters) {
    var map = mapRef.current;
    if (!map) return 0;
    var p1 = map.project(latlng, map.getZoom());
    var dest = L.latLng(latlng.lat + meters / 111320, latlng.lng);
    var p2 = map.project(dest, map.getZoom());
    return Math.abs(p2.y - p1.y);
  }

  /* Construye el overlay SVG una sola vez en un PANE PROPIO con
     zIndex claramente definido, encima del anillo y debajo de los
     puntos BiciMAD. Así no compite con el SVG interno de Leaflet. */
  function ensureSvgOverlay() {
    var map = mapRef.current;
    if (!map || svgRef.current) return;

    // Pane propio para nuestros blobs
    if (!map.getPane("blobsPane")) {
      map.createPane("blobsPane");
      map.getPane("blobsPane").style.zIndex = 500;
    }

    var svgNs = "http://www.w3.org/2000/svg";
    var pane = map.getPane("blobsPane");

    var svg = document.createElementNS(svgNs, "svg");
    svg.setAttribute("class", "ind3-blob-overlay");
    svg.style.position = "absolute";
    // El SVG NO captura eventos a nivel raíz. Solo cada hit individual.
    svg.style.pointerEvents = "none";
    svg.style.overflow = "visible";
    pane.appendChild(svg);

    var defs = document.createElementNS(svgNs, "defs");
    svg.appendChild(defs);

    var blobsG = document.createElementNS(svgNs, "g");
    blobsG.setAttribute("class", "ind3-blobs");
    svg.appendChild(blobsG);

    var hitG = document.createElementNS(svgNs, "g");
    hitG.setAttribute("class", "ind3-hits");
    svg.appendChild(hitG);

    svgRef.current = svg;
    defsRef.current = defs;
    blobsGRef.current = blobsG;
    hitGRef.current = hitG;
  }

  function positionSvg() {
    var map = mapRef.current;
    var svg = svgRef.current;
    if (!map || !svg) return;
    var size = map.getSize();
    var topLeft = map.containerPointToLayerPoint([0, 0]);
    svg.setAttribute("width", size.x);
    svg.setAttribute("height", size.y);
    svg.style.width = size.x + "px";
    svg.style.height = size.y + "px";
    svg.style.left = topLeft.x + "px";
    svg.style.top = topLeft.y + "px";
    svg.setAttribute("viewBox", "0 0 " + size.x + " " + size.y);
  }

  /* Pintado COMPLETO de los blobs.
     Lee SIEMPRE de las refs vivas para evitar closures obsoletos. */
  function renderBlobs() {
    var map = mapRef.current;
    if (!map || !svgRef.current) return;

    var curNodes = nodesRef.current || [];
    var curMetric = metricValueRef.current;
    var curSel = selIdRef.current;

    if (!curNodes.length) {
      defsRef.current.innerHTML = "";
      blobsGRef.current.innerHTML = "";
      hitGRef.current.innerHTML = "";
      return;
    }

    positionSvg();

    var svgNs = "http://www.w3.org/2000/svg";
    var defs = defsRef.current;
    var gB = blobsGRef.current;
    var gH = hitGRef.current;
    defs.innerHTML = "";
    gB.innerHTML = "";
    gH.innerHTML = "";

    var values = curNodes.map(curMetric);
    var max = Math.max.apply(null, values.concat([1]));
    var topLeft = map.containerPointToLayerPoint([0, 0]);

    var ordered = curNodes.slice().sort(function (a, b) {
      return curMetric(a) - curMetric(b);
    });

    ordered.forEach(function (n) {
      var v = curMetric(n);
      if (v <= 0) return;

      var t = v / max;
      var rMeters = BLOB_MIN_M + Math.sqrt(t) * (BLOB_MAX_M - BLOB_MIN_M);

      var latlng = L.latLng(n.lat, n.lon);
      var pt = map.latLngToLayerPoint(latlng);
      var cx = pt.x - topLeft.x;
      var cy = pt.y - topLeft.y;
      var rPx = metersToPixels(latlng, rMeters);
      var isSel = String(n.id) === String(curSel);

      var coreOpacity = 0.18 + Math.pow(t, 0.45) * 0.72;
      if (isSel) coreOpacity = Math.min(1, coreOpacity + 0.08);
      var color = capColor(v, max);

      // Gradiente radial
      var gradId = "blob-grad-" + n.id;
      var grad = document.createElementNS(svgNs, "radialGradient");
      grad.setAttribute("id", gradId);
      grad.setAttribute("cx", "50%");
      grad.setAttribute("cy", "50%");
      grad.setAttribute("r", "50%");
      [
        ["0%", coreOpacity],
        ["45%", coreOpacity * 0.45],
        ["100%", 0],
      ].forEach(function (s) {
        var stop = document.createElementNS(svgNs, "stop");
        stop.setAttribute("offset", s[0]);
        stop.setAttribute("stop-color", color);
        stop.setAttribute("stop-opacity", Number(s[1]).toFixed(3));
        grad.appendChild(stop);
      });
      defs.appendChild(grad);

      // Blob difuminado
      var blob = document.createElementNS(svgNs, "circle");
      blob.setAttribute("cx", cx);
      blob.setAttribute("cy", cy);
      blob.setAttribute("r", rPx);
      blob.setAttribute("fill", "url(#" + gradId + ")");
      blob.setAttribute("pointer-events", "none");
      gB.appendChild(blob);

      // Punto central nítido
      var coreR = isSel ? 6 : 4;
      var core = document.createElementNS(svgNs, "circle");
      core.setAttribute("cx", cx);
      core.setAttribute("cy", cy);
      core.setAttribute("r", coreR);
      core.setAttribute("fill", color);
      core.setAttribute("stroke", "#fff");
      core.setAttribute("stroke-width", isSel ? 2.5 : 1.5);
      core.setAttribute("pointer-events", "none");
      gB.appendChild(core);

      // Hit-target — único elemento del SVG que recibe ratón.
      var hitR = Math.max(14, Math.min(rPx, 26));
      var hit = document.createElementNS(svgNs, "circle");
      hit.setAttribute("cx", cx);
      hit.setAttribute("cy", cy);
      hit.setAttribute("r", hitR);
      hit.setAttribute("fill", "transparent");
      hit.setAttribute("pointer-events", "all");
      hit.style.cursor = "pointer";
      hit.setAttribute("data-node-id", String(n.id));
      gH.appendChild(hit);
    });
  }

  /* Listener UNO solo en el grupo de hits, usando event delegation.
     Esto evita acumular listeners viejos en hits eliminados, y
     garantiza que cada clic ejecuta el onSelect MÁS RECIENTE. */
  function attachHitDelegation() {
    var gH = hitGRef.current;
    if (!gH || gH.__delegated) return;
    gH.__delegated = true;

    // En el target del clic leemos el data-node-id y disparamos
    // onSelectRef.current(id). stopPropagation evita que Leaflet
    // se entere del clic (no entra en modo drag, no deselecciona).
    function onClick(e) {
      var t = e.target;
      var id = t && t.getAttribute && t.getAttribute("data-node-id");
      if (!id) return;
      e.stopPropagation();
      e.preventDefault();
      if (L && L.DomEvent) {
        L.DomEvent.stopPropagation(e);
        L.DomEvent.preventDefault(e);
      }
      var fn = onSelectRef.current;
      if (fn) fn(id);
    }
    function onMouseDown(e) {
      // Evita que Leaflet inicie un drag al pulsar sobre un hit.
      var t = e.target;
      if (t && t.getAttribute && t.getAttribute("data-node-id")) {
        e.stopPropagation();
        if (L && L.DomEvent) L.DomEvent.stopPropagation(e);
      }
    }
    gH.addEventListener("click", onClick);
    gH.addEventListener("mousedown", onMouseDown);
  }

  function renderLabels() {
    var map = mapRef.current;
    if (!map) return;
    if (layersRef.current.labelLayer) {
      layersRef.current.labelLayer.remove();
      layersRef.current.labelLayer = null;
    }
    var labelLayer = L.layerGroup().addTo(map);
    layersRef.current.labelLayer = labelLayer;

    var curNodes = nodesRef.current || [];
    var curMetric = metricValueRef.current;
    var curSel = selIdRef.current;
    var max = Math.max.apply(null, curNodes.map(curMetric).concat([1]));

    curNodes.forEach(function (n) {
      var v = curMetric(n);
      var isSel = String(n.id) === String(curSel);
      var t = v / max;
      if (!isSel && t < 0.18) return;

      L.marker([n.lat, n.lon], {
        icon: L.divIcon({
          className: "metro-label",
          html: n.name,
          iconSize: [140, 16],
          iconAnchor: [-10, 8],
        }),
        interactive: false,
      }).addTo(labelLayer);
    });
  }

  function drawInfluenceRing(node) {
    if (layersRef.current.ringLayer) {
      layersRef.current.ringLayer.remove();
      layersRef.current.ringLayer = null;
    }
    var map = mapRef.current;
    if (!map || !node) return;
    var ringLayer = L.layerGroup().addTo(map);
    layersRef.current.ringLayer = ringLayer;

    L.circle([node.lat, node.lon], {
      radius: radiusMRef.current,
      color: "#3b46c4",
      weight: 2,
      opacity: 0.85,
      dashArray: "6, 6",
      fill: true,
      fillColor: "#3b46c4",
      fillOpacity: 0.04,
      interactive: false,
      pane: "ringPane",
    }).addTo(ringLayer);

    var latOffset = radiusMRef.current / 111320;
    L.marker([node.lat + latOffset, node.lon], {
      icon: L.divIcon({
        className: "ind3-radius-label",
        html: radiusMRef.current + " m",
        iconSize: [60, 16],
        iconAnchor: [30, 8],
      }),
      interactive: false,
      pane: "ringPane",
    }).addTo(ringLayer);
  }

  function drawLinks(node) {
    if (layersRef.current.linkLayer) {
      layersRef.current.linkLayer.remove();
      layersRef.current.linkLayer = null;
    }
    var map = mapRef.current;
    if (!map || !node) return;
    var linkLayer = L.layerGroup().addTo(map);
    layersRef.current.linkLayer = linkLayer;

    node.stations.forEach(function (st, i) {
      var ang = (i / Math.max(1, node.stations.length)) * 2 * Math.PI;
      var dd = (st.dist || 150) / 111000;
      var blat = node.lat + Math.cos(ang) * dd;
      var blon =
        node.lon + (Math.sin(ang) * dd) / Math.cos((node.lat * Math.PI) / 180);

      L.polyline(
        [
          [node.lat, node.lon],
          [blat, blon],
        ],
        {
          color: "#c8cdf4",
          weight: 2,
          opacity: 0.85,
          pane: "biciLinkPane",
          interactive: false,
        },
      ).addTo(linkLayer);

      L.circleMarker([blat, blon], {
        radius: 5,
        color: "#fff",
        weight: 1.5,
        fillColor: "#2E8B57",
        fillOpacity: 1,
        pane: "biciPane",
        interactive: false,
      }).addTo(linkLayer);
    });
  }

  // ─── Inicialización del mapa ─────────────────────────────
  useEffect(function () {
    var map = L.map(mountRef.current, {
      center: [40.429, -3.699],
      zoom: 13,
      zoomControl: true,
      // OJO: preferCanvas: true hace que Leaflet meta un <canvas> que
      // cubre el overlayPane y captura el ratón sobre toda su área,
      // bloqueando nuestros hits SVG cuando hay anillo de selección.
      // Usamos renderer SVG explícito.
      preferCanvas: false,
      renderer: L.svg(),
    });
    L.tileLayer(
      "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
      {
        attribution: "\u00A9 OpenStreetMap \u00A9 CARTO",
        subdomains: "abcd",
        maxZoom: 19,
      },
    ).addTo(map);
    mapRef.current = map;

    // Pane para el anillo de influencia: queda por debajo del SVG de blobs.
    map.createPane("ringPane");
    map.getPane("ringPane").style.zIndex = 395;
    // El pane de Leaflet es <div>; sus children pueden capturar eventos.
    // Lo desactivamos a nivel de pane.
    map.getPane("ringPane").style.pointerEvents = "none";

    // Panes dedicados para los puntos BiciMAD (por encima del blob SVG)
    map.createPane("biciLinkPane");
    map.getPane("biciLinkPane").style.zIndex = 645;
    map.getPane("biciLinkPane").style.pointerEvents = "none";
    map.createPane("biciPane");
    map.getPane("biciPane").style.zIndex = 650;
    map.getPane("biciPane").style.pointerEvents = "none";

    ensureSvgOverlay();
    attachHitDelegation();

    // Por si Leaflet creara algún canvas inadvertidamente,
    // lo dejamos sin captura de ratón.
    var canvases = mountRef.current.querySelectorAll("canvas");
    for (var i = 0; i < canvases.length; i++) {
      canvases[i].style.pointerEvents = "none";
    }

    // Repintar en zoom/move (escala real). Usamos referencias estables
    // para poder hacer off() en el cleanup.
    var onMove = function () {
      renderBlobs();
    };
    map.on("zoomend", onMove);
    map.on("moveend", onMove);
    map.on("viewreset", onMove);

    renderBlobs();
    renderLabels();

    return function () {
      map.off("zoomend", onMove);
      map.off("moveend", onMove);
      map.off("viewreset", onMove);
      if (svgRef.current && svgRef.current.parentNode) {
        svgRef.current.parentNode.removeChild(svgRef.current);
      }
      svgRef.current = null;
      defsRef.current = null;
      blobsGRef.current = null;
      hitGRef.current = null;
      map.remove();
    };
  }, []);

  // Repintar cuando cambian datos, métrica O selección. Vuelvo a
  // depender de selId porque necesitamos resaltar el nodo seleccionado.
  // El truco para que el cursor no se quede pegado: la delegación de
  // eventos en el <g> padre — los hits hijos pueden ir y venir sin
  // problema porque el listener no está en ellos.
  useEffect(
    function () {
      if (!mapRef.current) return;
      ensureSvgOverlay();
      attachHitDelegation();
      renderBlobs();
      renderLabels();
    },
    [nodes, props.metric, selId],
  );

  // Anillo + enlaces: cambian con selección o radio
  useEffect(
    function () {
      if (!mapRef.current) return;
      ["linkLayer", "ringLayer"].forEach(function (k) {
        if (layersRef.current[k]) {
          layersRef.current[k].remove();
          layersRef.current[k] = null;
        }
      });
      if (selId) {
        var selNode = nodes.find(function (n) {
          return String(n.id) === String(selId);
        });
        if (selNode) {
          drawInfluenceRing(selNode);
          drawLinks(selNode);
        }
      }
    },
    [selId, radiusM, nodes],
  );

  return h("div", { ref: mountRef, id: "map-mount" });
}

/* ─── Ind3NodeDonut: donut grande de la estación seleccionada ── */
function Ind3NodeDonut(props) {
  var node = props.node;
  var stats = props.stats;
  var radius = props.radius;
  if (!node || !stats) return null;

  var total = stats.total_intermodal || 1;
  var pct = +((node.captured / total) * 100).toFixed(1);
  var cap = node.captured || 1;
  var oPct = ((node.out / cap) * 100).toFixed(1);
  var iPct = ((node["in"] / cap) * 100).toFixed(1);

  // SVG donut
  var size = 110,
    stroke = 11,
    r = (size - stroke) / 2;
  var circ = 2 * Math.PI * r;
  var offset = circ - (pct / 100) * circ;

  return h(
    "div",
    { className: "sb-sec" },
    h("div", { className: "sb-lbl" }, "Estaci\u00F3n seleccionada"),
    h(
      "div",
      {
        style: {
          display: "flex",
          alignItems: "center",
          gap: 14,
          marginBottom: 10,
        },
      },
      // Donut
      h(
        "div",
        {
          style: {
            position: "relative",
            width: size,
            height: size,
            flexShrink: 0,
          },
        },
        h(
          "svg",
          { width: size, height: size, viewBox: "0 0 " + size + " " + size },
          h("circle", {
            cx: size / 2,
            cy: size / 2,
            r: r,
            fill: "none",
            stroke: "#f0f0f3",
            strokeWidth: stroke,
          }),
          h("circle", {
            cx: size / 2,
            cy: size / 2,
            r: r,
            fill: "none",
            stroke: "var(--blue)",
            strokeWidth: stroke,
            strokeDasharray: circ,
            strokeDashoffset: offset,
            strokeLinecap: "round",
            transform: "rotate(-90 " + size / 2 + " " + size / 2 + ")",
            style: { transition: "stroke-dashoffset 0.6s ease" },
          }),
        ),
        h(
          "div",
          {
            style: {
              position: "absolute",
              inset: 0,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
            },
          },
          h(
            "span",
            {
              style: {
                fontSize: 22,
                fontWeight: 700,
                color: "var(--blue)",
                fontVariantNumeric: "tabular-nums",
                lineHeight: 1,
              },
            },
            pct + "%",
          ),
          h(
            "span",
            {
              style: {
                fontSize: 8,
                color: "var(--muted)",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                marginTop: 2,
              },
            },
            "del total",
          ),
        ),
      ),
      // Info del nodo
      h(
        "div",
        { style: { minWidth: 0 } },
        h(
          "div",
          {
            style: {
              fontSize: 14,
              fontWeight: 600,
              color: "var(--ink)",
              marginBottom: 2,
            },
          },
          node.name,
        ),
        h(
          "div",
          { style: { fontSize: 11, color: "var(--muted)", marginBottom: 8 } },
          node.lines,
        ),
        h(
          "div",
          {
            style: {
              fontSize: 12,
              color: "var(--ink)",
              fontWeight: 600,
              fontVariantNumeric: "tabular-nums",
            },
          },
          fmt(node.captured) + " viajes",
        ),
        h(
          "div",
          { style: { display: "flex", gap: 10, marginTop: 4, fontSize: 11 } },
          h(
            "span",
            { style: { color: "#3b46c4" } },
            "\u2191 " + fmt(node.out) + " (" + oPct + "%)",
          ),
          h(
            "span",
            { style: { color: "#8f99ec" } },
            "\u2193 " + fmt(node["in"]) + " (" + iPct + "%)",
          ),
        ),
      ),
    ),
  );
}

/* ─── Ind3GlobalBar: barra compacta de cobertura global ─── */
function Ind3GlobalBar(props) {
  var stats = props.stats;
  var radius = props.radius;
  if (!stats) return null;

  var pct = stats.share_pct != null ? stats.share_pct : 0;
  var metroWB = stats.metro_with_bici || 0;
  var metroTot = stats.metro_total || 1;
  var metroPct = stats.metro_coverage_pct || 0;

  return h(
    "div",
    { className: "sb-sec" },
    h("div", { className: "sb-lbl" }, "Cobertura intermodal"),

    // Viajes intermodales
    h(
      "div",
      {
        style: {
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          fontSize: 12,
          marginBottom: 4,
        },
      },
      h("span", { style: { color: "var(--muted)" } }, "Viajes intermodales"),
      h(
        "span",
        {
          style: {
            fontWeight: 700,
            color: "var(--blue)",
            fontVariantNumeric: "tabular-nums",
          },
        },
        pct + "%",
      ),
    ),
    h(
      "div",
      {
        style: {
          height: 5,
          background: "#f0f0f3",
          borderRadius: 3,
          overflow: "hidden",
          marginBottom: 3,
        },
      },
      h("div", {
        style: {
          height: "100%",
          borderRadius: 3,
          background: "var(--blue)",
          width: Math.min(pct, 100) + "%",
          transition: "width 0.5s ease",
        },
      }),
    ),
    h(
      "div",
      { style: { fontSize: 10, color: "var(--muted)", marginBottom: 10 } },
      fmt(stats.total_intermodal) +
        " de " +
        fmt(stats.historic_trips) +
        " viajes (radio " +
        radius +
        " m)",
    ),

    // Estaciones cubiertas
    h(
      "div",
      {
        style: {
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          fontSize: 12,
          marginBottom: 4,
        },
      },
      h(
        "span",
        { style: { color: "var(--muted)" } },
        "Estaciones metro con BiciMAD",
      ),
      h(
        "span",
        {
          style: {
            fontWeight: 700,
            color: "var(--c-bici)",
            fontVariantNumeric: "tabular-nums",
          },
        },
        metroWB + " / " + metroTot,
      ),
    ),
    h(
      "div",
      {
        style: {
          height: 5,
          background: "#f0f0f3",
          borderRadius: 3,
          overflow: "hidden",
          marginBottom: 3,
        },
      },
      h("div", {
        style: {
          height: "100%",
          borderRadius: 3,
          background: "var(--c-bici)",
          width: metroPct + "%",
          transition: "width 0.5s ease",
        },
      }),
    ),
    h(
      "div",
      { style: { fontSize: 10, color: "var(--muted)" } },
      metroPct + "% de cobertura espacial",
    ),
  );
}

/* ─── NodeCard (ind3) — tarjeta flotante de detalle ──── */
function Ind3NodeCard(props) {
  var node = props.node;
  var onClose = props.onClose;

  if (!node) return null;

  var cap = node.captured || 1;
  var oPct = ((node.out / cap) * 100).toFixed(1);
  var iPct = ((node["in"] / cap) * 100).toFixed(1);

  return h(
    "div",
    { className: "station-card", style: { width: 280 } },
    // Cabecera
    h(
      "div",
      { className: "sc-head" },
      h(
        "div",
        null,
        h("div", { className: "sc-name" }, node.name),
        h(
          "div",
          { className: "sc-cap" },
          node.lines + " \u00B7 c\u00F3d CTM " + node.id,
        ),
      ),
      h("button", { className: "sc-close", onClick: onClose }, "\u00D7"),
    ),

    // Métricas principales
    h(
      "div",
      { className: "cell-card-metrics" },
      h(
        "div",
        { className: "cell-card-metric" },
        h("div", { className: "value" }, fmt(node.captured)),
        h("div", { className: "label" }, "viajes capturados"),
      ),
      h(
        "div",
        { className: "cell-card-metric" },
        h("div", { className: "value" }, node.stations.length),
        h("div", { className: "label" }, "estaciones BiciMAD"),
      ),
    ),

    // Reparto salidas / llegadas
    h("div", { className: "sb-lbl" }, "Reparto salidas / llegadas"),
    h(
      "div",
      { className: "dist-row" },
      h("div", { className: "dist-swatch", style: { background: "#3b46c4" } }),
      h("div", { className: "dist-name" }, "Salidas (desde el nodo)"),
      h(
        "div",
        { className: "dist-vals" },
        fmt(node.out) + " \u00B7 " + oPct + "%",
      ),
    ),
    h(
      "div",
      { className: "dist-row" },
      h("div", { className: "dist-swatch", style: { background: "#8f99ec" } }),
      h("div", { className: "dist-name" }, "Llegadas (hacia el nodo)"),
      h(
        "div",
        { className: "dist-vals" },
        fmt(node["in"]) + " \u00B7 " + iPct + "%",
      ),
    ),

    // Estaciones BiciMAD asignadas
    node.stations.length > 0
      ? h(
          React.Fragment,
          null,
          h(
            "div",
            { className: "sb-lbl", style: { marginTop: 12 } },
            "Estaciones BiciMAD asignadas",
          ),
          node.stations.map(function (st) {
            return h(
              "div",
              { key: st.number, className: "dist-row" },
              h("div", {
                className: "dist-swatch",
                style: { background: "#2E8B57" },
              }),
              h(
                "div",
                { className: "dist-name" },
                st.name,
                h(
                  "span",
                  { style: { color: "var(--muted)" } },
                  " \u00B7 " + st.dist + " m",
                ),
              ),
              h("div", { className: "dist-vals" }, "#" + st.number),
            );
          }),
        )
      : h(
          "div",
          { style: { fontSize: 12, color: "var(--muted)", marginTop: 8 } },
          "Sin estaciones BiciMAD en el radio.",
        ),
  );
}
