/* ═══════════════════════════════════════════════════════
   Indicador 3 — Componentes React (Captura intermodal)
   ═══════════════════════════════════════════════════════ */

/* ─── Ind3View: contenedor completo del indicador 3 ──── */
function Ind3View() {
  var _s1 = useState(true);    var loading    = _s1[0]; var setLoading    = _s1[1];
  var _s2 = useState(null);    var error      = _s2[0]; var setError      = _s2[1];
  var _s3 = useState(300);     var radius     = _s3[0]; var setRadius     = _s3[1];
  var _s4 = useState('total'); var metric     = _s4[0]; var setMetric     = _s4[1];
  var _s5 = useState(null);    var selId      = _s5[0]; var setSelId      = _s5[1];
  var _s6 = useState([]);      var nodes      = _s6[0]; var setNodes      = _s6[1];
  var _s7 = useState(null);    var stats      = _s7[0]; var setStats      = _s7[1];
  var _s8 = useState([150,300,500]); var radii = _s8[0]; var setRadii = _s8[1];
  var _s9 = useState(0);       var dataVer    = _s9[0]; var setDataVer    = _s9[1];

  function metricValue(n) {
    return metric === 'out' ? n.out : metric === 'in' ? n['in'] : n.captured;
  }

  // Carga inicial: config + datos
  useEffect(function() {
    loadInd3Config().then(function(cfg) {
      if (cfg && cfg.radii) setRadii(cfg.radii);
      var r = (cfg && cfg.default_radius) || 300;
      setRadius(r);
      return loadInd3Data(r);
    }).then(function(res) {
      setNodes(res.nodes);
      setStats(res.stats);
      setDataVer(function(v){ return v + 1; });
      setLoading(false);
    }).catch(function(err) {
      setError(err.message);
      setLoading(false);
    });
  }, []);

  // Recargar cuando cambia el radio
  function changeRadius(r) {
    setRadius(r);
    setSelId(null);
    loadInd3Data(r).then(function(res) {
      setNodes(res.nodes);
      setStats(res.stats);
      setDataVer(function(v){ return v + 1; });
    });
  }

  var selNode = selId ? nodes.find(function(n){ return String(n.id) === String(selId); }) : null;

  if (loading) return h('div', { className: 'loading-overlay' },
    h('div', { className: 'loading-spinner' }),
    h('div', { className: 'loading-text' }, 'Cargando captura intermodal…')
  );
  if (error) return h('div', { className: 'loading-overlay' },
    h('div', { className: 'loading-error' }, '\u26A0 ' + error)
  );

  return h('div', { className: 'app-body' },
    h('aside', { className: 'sidebar' },

      // Descripción
      h('div', { className: 'sb-sec' },
        h('div', { className: 'sb-lbl' }, 'Indicador'),
        h('div', { style: { fontSize: 13, fontWeight: 600, marginBottom: 6 } },
          '\u00CDndice de captura intermodal'),
        h('div', { className: 'mode-caption' },
          'Viajes BiciMAD que se originan o terminan en el radio de influencia de cada ',
          h('strong', null, 'estaci\u00F3n de Metro / Cercan\u00EDas'), '.'
        )
      ),

      // Radio de influencia
      h('div', { className: 'sb-sec' },
        h('div', { className: 'sb-lbl' }, 'Radio de influencia'),
        h('div', { className: 'radio-row' },
          radii.map(function(r) {
            return h('button', {
              key: r,
              className: 'radio-btn ' + (radius === r ? 'on' : ''),
              onClick: function(){ changeRadius(r); }
            }, r + ' m');
          })
        ),
        h('div', { className: 'mode-caption', style: { marginTop: 6 } },
          'Distancia a pie desde la boca de metro a la estaci\u00F3n BiciMAD.'
        )
      ),

      // Métrica mostrada
      h('div', { className: 'sb-sec' },
        h('div', { className: 'sb-lbl' }, 'M\u00E9trica mostrada'),
        h('div', { className: 'metric-row' },
          [['total','Total'],['out','Salidas'],['in','Llegadas']].map(function(pair) {
            return h('button', {
              key: pair[0],
              className: 'metric-btn ' + (metric === pair[0] ? 'on' : ''),
              onClick: function(){ setMetric(pair[0]); }
            }, pair[1]);
          })
        )
      ),

      // Ranking
      h(Ind3Ranking, {
        nodes: nodes, metric: metric, metricValue: metricValue,
        selId: selId, onSelect: function(id){ setSelId(id); }
      }),

      // Estadísticas globales
      h(Ind3GlobalStats, { stats: stats, radius: radius }),

      // Leyenda
      h('div', { className: 'sb-sec' },
        h('div', { className: 'sb-lbl' }, 'Leyenda'),
        h('div', { className: 'leg-sw', style: { marginBottom: 6 } },
          h('div', { style: {
            width: 40, height: 10, borderRadius: 3,
            background: 'linear-gradient(90deg, var(--cap-0), var(--cap-4))'
          }}),
          h('span', { style: { fontSize: 12, color: 'var(--muted)', marginLeft: 8 } },
            'Captura: baja \u2192 alta')
        ),
        h('div', { className: 'leg-sw', style: { marginBottom: 6 } },
          h('div', { className: 'leg-dot', style: { background: 'var(--c-bici)' } }),
          h('span', { style: { fontSize: 12, color: 'var(--muted)', marginLeft: 4 } },
            'Estaci\u00F3n BiciMAD asignada')
        ),
        h('div', { className: 'leg-note' },
          'El tama\u00F1o del c\u00EDrculo de cada estaci\u00F3n de Metro es proporcional a los viajes BiciMAD capturados. Haz clic para ver el detalle.'
        )
      )
    ),

    // Mapa + tarjeta flotante
    h('main', { className: 'map-area' },
      h(Ind3MapView, {
        nodes: nodes, metric: metric, metricValue: metricValue,
        selId: selId, onSelect: function(id){ setSelId(id); },
        key: 'map3-' + dataVer
      }),
      selNode ? h(Ind3NodeCard, {
        node: selNode, metricValue: metricValue,
        onClose: function(){ setSelId(null); }
      }) : null
    )
  );
}

/* ─── Ranking de nodos (sidebar) ─────────────────────── */
function Ind3Ranking(props) {
  var nodes       = props.nodes;
  var metricValue = props.metricValue;
  var selId       = props.selId;
  var onSelect    = props.onSelect;

  var sorted = nodes.slice().sort(function(a, b) {
    return metricValue(b) - metricValue(a);
  });
  var top25 = sorted.slice(0, 25);
  var max = top25.length ? metricValue(top25[0]) : 1;

  return h('div', { className: 'sb-sec' },
    h('div', { className: 'sb-lbl' }, 'Ranking de nodos'),
    h('div', { className: 'rank-list' },
      top25.map(function(n, idx) {
        var v = metricValue(n);
        var isSel = String(n.id) === String(selId);
        return h('div', {
          key: n.id,
          className: 'rank-row' + (isSel ? ' selected' : ''),
          onClick: function(){ onSelect(n.id); }
        },
          h('div', { className: 'rank-pos' }, idx + 1),
          h('div', { className: 'rank-info' },
            h('div', { className: 'rank-name' }, n.name),
            h('div', { className: 'rank-bar' },
              h('div', { className: 'rank-bar-fill', style: {
                width: max ? (v / max * 100).toFixed(1) + '%' : '0%'
              }})
            )
          ),
          h('div', { className: 'rank-value' },
            fmt(v),
            h('span', { className: 'sub' }, n.stations.length + ' est. BiciMAD')
          )
        );
      })
    )
  );
}

/* ─── Estadísticas globales (sidebar) ────────────────── */
function Ind3GlobalStats(props) {
  var stats  = props.stats;
  var radius = props.radius;
  if (!stats) return null;

  return h('div', { className: 'sb-sec' },
    h('div', { className: 'sb-lbl' }, 'Estad\u00EDsticas globales'),
    h('div', { className: 'stat-list' },
      h('div', { className: 'stat-row2' },
        h('div', { className: 'stat-info' },
          h('span', { className: 'stat-lbl' }, 'Viajes intermodales'),
          h('span', { className: 'stat-sub' }, 'radio ' + radius + ' m')
        ),
        h('span', { className: 'stat-val', style: { color: 'var(--blue)' } },
          fmt(stats.total_intermodal))
      ),
      stats.top_node ? h('div', { className: 'stat-row2' },
        h('div', { className: 'stat-info' },
          h('span', { className: 'stat-lbl' }, 'Nodo l\u00EDder'),
          h('span', { className: 'stat-sub' }, stats.top_node.name)
        ),
        h('span', { className: 'stat-val', style: { color: 'var(--blue)' } },
          fmt(stats.top_node.captured))
      ) : null,
      h('div', { className: 'stat-row2' },
        h('div', { className: 'stat-info' },
          h('span', { className: 'stat-lbl' }, '% del hist\u00F3rico BiciMAD'),
          h('span', { className: 'stat-sub' }, 'cobertura intermodal')
        ),
        h('span', { className: 'stat-val', style: { color: 'var(--blue)' } },
          (stats.share_pct != null ? stats.share_pct : '\u2014') + '%')
      )
    )
  );
}

/* ─── MapView (ind3) ─────────────────────────────────── */
function Ind3MapView(props) {
  var nodes       = props.nodes;
  var metricValue = props.metricValue;
  var selId       = props.selId;
  var onSelect    = props.onSelect;

  var mountRef   = useRef(null);
  var mapRef     = useRef(null);
  var layersRef  = useRef({});
  var markersRef = useRef({});

  function clearLayers() {
    ['nodeLayer','labelLayer','linkLayer'].forEach(function(k) {
      if (layersRef.current[k]) { layersRef.current[k].remove(); layersRef.current[k] = null; }
    });
    markersRef.current = {};
  }

  function renderNodes() {
    var map = mapRef.current;
    if (!map || !nodes.length) return;
    clearLayers();

    var max = Math.max.apply(null, nodes.map(metricValue).concat([1]));
    var nodeLayer  = L.layerGroup().addTo(map);
    var labelLayer = L.layerGroup().addTo(map);
    layersRef.current.nodeLayer  = nodeLayer;
    layersRef.current.labelLayer = labelLayer;

    nodes.forEach(function(n) {
      var v = metricValue(n);
      var radiusPx = 8 + Math.sqrt(v / max) * 32;
      var isSel = String(n.id) === String(selId);

      var c = L.circleMarker([n.lat, n.lon], {
        radius: radiusPx,
        color: '#fff',
        weight: isSel ? 4 : 2,
        fillColor: capColor(v, max),
        fillOpacity: 0.82,
      });
      c.on('click', function(){ onSelect(n.id); });
      c.on('mouseover', function(){ this.setStyle({ weight: 3.5 }); });
      c.on('mouseout', function(){
        this.setStyle({ weight: String(n.id) === String(selId) ? 4 : 2 });
      });
      c.addTo(nodeLayer);
      markersRef.current[n.id] = c;

      // Etiqueta solo si el círculo es suficientemente grande o está seleccionado
      if (radiusPx > 14 || isSel) {
        L.marker([n.lat, n.lon], {
          icon: L.divIcon({
            className: 'metro-label',
            html: n.name,
            iconSize: [140, 16],
            iconAnchor: [-radiusPx + 4, 8],
          }),
          interactive: false,
        }).addTo(labelLayer);
      }
    });
  }

  function drawLinks(node) {
    if (layersRef.current.linkLayer) layersRef.current.linkLayer.remove();
    var map = mapRef.current;
    if (!map || !node) return;
    var linkLayer = L.layerGroup().addTo(map);
    layersRef.current.linkLayer = linkLayer;

    node.stations.forEach(function(st, i) {
      var ang = (i / Math.max(1, node.stations.length)) * 2 * Math.PI;
      var dd  = (st.dist || 150) / 111000;
      var blat = node.lat + Math.cos(ang) * dd;
      var blon = node.lon + Math.sin(ang) * dd / Math.cos(node.lat * Math.PI / 180);

      L.polyline([[node.lat, node.lon], [blat, blon]], {
        color: '#c8cdf4', weight: 2, opacity: 0.6,
      }).addTo(linkLayer);

      L.circleMarker([blat, blon], {
        radius: 5, color: '#fff', weight: 1.5,
        fillColor: '#2E8B57', fillOpacity: 0.9,
      }).bindTooltip(st.name + ' \u00B7 ' + st.dist + ' m', { sticky: true })
       .addTo(linkLayer);
    });
  }

  // Inicialización del mapa
  useEffect(function() {
    var map = L.map(mountRef.current, {
      center: [40.4290, -3.6990],
      zoom: 13,
      zoomControl: true,
      preferCanvas: true,
    });
    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
      attribution: '\u00A9 OpenStreetMap \u00A9 CARTO',
      subdomains: 'abcd',
      maxZoom: 19,
    }).addTo(map);
    mapRef.current = map;
    renderNodes();
    return function(){ map.remove(); };
  }, []);

  // Actualizar cuando cambian nodos, métrica o selección
  useEffect(function() {
    if (!mapRef.current) return;
    renderNodes();
    if (selId) {
      var selNode = nodes.find(function(n){ return String(n.id) === String(selId); });
      if (selNode) {
        drawLinks(selNode);
        if (markersRef.current[selId]) markersRef.current[selId].setStyle({ weight: 4 });
      }
    }
  }, [nodes, selId, props.metric]);

  return h('div', { ref: mountRef, id: 'map-mount' });
}

/* ─── NodeCard (ind3) — tarjeta flotante de detalle ──── */
function Ind3NodeCard(props) {
  var node        = props.node;
  var onClose     = props.onClose;

  if (!node) return null;

  var cap = node.captured || 1;
  var oPct = (node.out / cap * 100).toFixed(1);
  var iPct = (node['in'] / cap * 100).toFixed(1);

  return h('div', { className: 'station-card', style: { width: 280 } },
    // Cabecera
    h('div', { className: 'sc-head' },
      h('div', null,
        h('div', { className: 'sc-name' }, node.name),
        h('div', { className: 'sc-cap' }, node.lines + ' \u00B7 c\u00F3d CTM ' + node.id)
      ),
      h('button', { className: 'sc-close', onClick: onClose }, '\u00D7')
    ),

    // Ratio tag
    h('div', { className: 'ratio-tag' },
      node.is_hub
        ? 'Nodo intercambiador \u00B7 alta funci\u00F3n intermodal'
        : 'Estaci\u00F3n urbana \u00B7 funci\u00F3n mixta'
    ),

    // Métricas principales
    h('div', { className: 'cell-card-metrics' },
      h('div', { className: 'cell-card-metric' },
        h('div', { className: 'value' }, fmt(node.captured)),
        h('div', { className: 'label' }, 'viajes capturados')
      ),
      h('div', { className: 'cell-card-metric' },
        h('div', { className: 'value' }, node.stations.length),
        h('div', { className: 'label' }, 'estaciones BiciMAD')
      )
    ),

    // Reparto salidas / llegadas
    h('div', { className: 'sb-lbl' }, 'Reparto salidas / llegadas'),
    h('div', { className: 'dist-row' },
      h('div', { className: 'dist-swatch', style: { background: '#3b46c4' } }),
      h('div', { className: 'dist-name' }, 'Salidas (desde el nodo)'),
      h('div', { className: 'dist-vals' }, fmt(node.out) + ' \u00B7 ' + oPct + '%')
    ),
    h('div', { className: 'dist-row' },
      h('div', { className: 'dist-swatch', style: { background: '#8f99ec' } }),
      h('div', { className: 'dist-name' }, 'Llegadas (hacia el nodo)'),
      h('div', { className: 'dist-vals' }, fmt(node['in']) + ' \u00B7 ' + iPct + '%')
    ),

    // Estaciones BiciMAD asignadas
    node.stations.length > 0
      ? h(React.Fragment, null,
          h('div', { className: 'sb-lbl', style: { marginTop: 12 } },
            'Estaciones BiciMAD asignadas'),
          node.stations.map(function(st) {
            return h('div', { key: st.number, className: 'dist-row' },
              h('div', { className: 'dist-swatch', style: { background: '#2E8B57' } }),
              h('div', { className: 'dist-name' },
                st.name,
                h('span', { style: { color: 'var(--muted)' } }, ' \u00B7 ' + st.dist + ' m')
              ),
              h('div', { className: 'dist-vals' }, '#' + st.number)
            );
          })
        )
      : h('div', { style: { fontSize: 12, color: 'var(--muted)', marginTop: 8 } },
          'Sin estaciones BiciMAD en el radio.')
  );
}
