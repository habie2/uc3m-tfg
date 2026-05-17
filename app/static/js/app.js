/* ═══════════════════════════════════════════════════════
   BiciMAD · App principal — Plataforma de Indicadores
   ═══════════════════════════════════════════════════════
   Depende de: data.js, ind1_components.js,
               ind2_components.js, ind3_components.js
*/

var h = React.createElement;

/* ─── Indicador 1 (contenido completo del sidebar + mapa) ── */
function Ind1View() {
  var _s1 = useState(true);   var loading  = _s1[0]; var setLoading  = _s1[1];
  var _s2 = useState(null);   var error    = _s2[0]; var setError    = _s2[1];
  var _s3 = useState('daytype'); var mode  = _s3[0]; var setMode     = _s3[1];
  var _s4 = useState('X');    var dayType  = _s4[0]; var setDayType  = _s4[1];
  var _s5 = useState(false);  var holiday  = _s5[0]; var setHoliday  = _s5[1];
  var _s6 = useState('');     var date     = _s6[0]; var setDate     = _s6[1];
  var _s7 = useState(false);  var dateHol  = _s7[0]; var setDateHol  = _s7[1];
  var _s8 = useState(9);      var hour     = _s8[0]; var setHour     = _s8[1];
  var _s9 = useState(false);  var playing  = _s9[0]; var setPlaying  = _s9[1];
  var _sA = useState(null);   var selSt    = _sA[0]; var setSelSt    = _sA[1];
  var _sB = useState(0);      var dataVer  = _sB[0]; var setDataVer  = _sB[1];
  var _sC = useState(null);   var month    = _sC[0]; var setMonth    = _sC[1];
  var _sD = useState([]);     var months   = _sD[0]; var setMonths   = _sD[1];

  var sliderRef = React.useRef(null);

  // Carga inicial
  useEffect(function() {
    (async function() {
      try {
        await loadStations();
        await loadDateRange();
        var avMonths = await loadAvailableMonths();
        setMonths(avMonths);
        setDate(_dateRange.min || '2019-05-01');
        await loadSaturation({ dayType: 'X', holiday: false });
        setDataVer(function(v){ return v + 1; });
        setLoading(false);
      } catch(err) {
        console.error(err);
        setError(err.message);
        setLoading(false);
      }
    })();
  }, []);

  // Recargar saturación
  useEffect(function() {
    if (loading) return;
    (async function() {
      try {
        if (mode === 'date') {
          await loadSaturation({ date: date });
        } else {
          await loadSaturation({ dayType: dayType, holiday: holiday, month: month });
        }
        setDataVer(function(v){ return v + 1; });
      } catch(err) { console.error('Error recargando:', err); }
    })();
  }, [mode, dayType, holiday, month, date, loading]);

  // Comprobar festivo
  useEffect(function() {
    if (mode !== 'date' || !date) return;
    checkHoliday(date).then(function(hol){ setDateHol(hol); });
  }, [date, mode]);

  var dateDay = (function() {
    try {
      var d = new Date(date + 'T12:00:00');
      var i = d.getDay();
      return DAY_KEYS[i === 0 ? 6 : i - 1];
    } catch(e) { return 'L'; }
  })();
  var effDay     = mode === 'date' ? dateDay : dayType;
  var effHoliday = mode === 'date' ? dateHol : holiday;
  var dayLabel   = DAY_NAMES[DAY_KEYS.indexOf(effDay)] + (effHoliday ? ' \u00B7 Festivo' : '');

  // Autoplay
  useEffect(function() {
    if (!playing) return;
    var t = setInterval(function(){ setHour(function(hh){ return (hh + 1) % 24; }); }, 650);
    return function(){ clearInterval(t); };
  }, [playing]);

  // Slider fill
  useEffect(function() {
    if (!sliderRef.current) return;
    var pct = (hour / 23) * 100;
    sliderRef.current.style.background =
      'linear-gradient(to right, var(--blue) 0%, var(--blue) '+pct+'%, var(--border) '+pct+'%, var(--border) 100%)';
  }, [hour]);

  var handleStation = useCallback(function(st){ setSelSt(st); }, []);

  var monthLabel = (function() {
    if (!month) return 'Todos los meses';
    var found = months.find(function(m){ return m.value === month; });
    return found ? found.label : 'Mes ' + month;
  })();

  if (loading || error) {
    return h('div', { className: 'loading-overlay' },
      error
        ? h('div', { className: 'loading-error' },
            '\u26A0 No se pudo conectar con el servidor.', h('br'), h('br'),
            error, h('br'), h('br'),
            'Aseg\u00FArate de que server.py est\u00E1 corriendo.')
        : h(React.Fragment, null,
            h('div', { className: 'loading-spinner' }),
            h('div', { className: 'loading-text' }, 'Cargando estaciones\u2026')
          )
    );
  }

  return h('div', { className: 'app-body' },
    // Sidebar
    h('aside', { className: 'sidebar' },
      h('div', { className: 'sb-sec' },
        h('div', { className: 'sb-lbl' }, 'Periodo de an\u00E1lisis'),
        h('div', { className: 'mode-row' },
          h('button', { className: 'mode-btn ' + (mode === 'daytype' ? 'on' : ''),
            onClick: function(){ setMode('daytype'); } }, 'Tipo de d\u00EDa'),
          h('button', { className: 'mode-btn ' + (mode === 'date' ? 'on' : ''),
            onClick: function(){ setMode('date'); } }, 'Fecha concreta')
        ),
        mode === 'daytype'
          ? h(React.Fragment, null,
              h('div', { className: 'day-row' },
                DAY_KEYS.map(function(d) {
                  return h('button', { key: d,
                    className: 'day-btn ' + (dayType === d ? 'on' : ''),
                    onClick: function(){ setDayType(d); }
                  }, d);
                })
              ),
              h('div', { className: 'sb-lbl', style: { marginTop: 12 } }, 'Mes'),
              h('div', { className: 'month-row' },
                h('button', {
                  className: 'month-btn ' + (month === null ? 'on' : ''),
                  onClick: function(){ setMonth(null); }
                }, 'Todos'),
                months.map(function(m) {
                  return h('button', { key: m.value,
                    className: 'month-btn ' + (month === m.value ? 'on' : ''),
                    onClick: function(){ setMonth(m.value); }
                  }, m.label.substring(0, 3));
                })
              ),
              h('div', { className: 'toggle-row' },
                h('span', { className: 'toggle-lbl' }, 'Festivo'),
                h('button', {
                  className: 'tgl ' + (holiday ? 'on' : ''),
                  onClick: function(){ setHoliday(function(v){ return !v; }); }
                })
              ),
              h('div', { className: 'mode-caption' },
                'Promedio de ', h('strong', null, DAY_NAMES[DAY_KEYS.indexOf(dayType)].toLowerCase()),
                holiday ? ' festivos' : '',
                ' \u2014 ', h('strong', null, monthLabel.toLowerCase()), '.'
              )
            )
          : h(React.Fragment, null,
              h('input', { type: 'date', className: 'date-inp', value: date,
                min: _dateRange.min, max: _dateRange.max,
                onChange: function(e){ setDate(e.target.value); }
              }),
              h('div', { className: 'day-badge ' + (dateHol ? 'holiday' : 'workday') },
                h('div', { className: 'dot' }),
                h('span', { className: 'lbl' }, dateHol ? 'Festivo' : 'D\u00EDa laborable')
              ),
              h('div', { className: 'mode-caption' },
                'Datos del ', h('strong', null, dayLabel), date ? ' \u2014 ' + date : '.'
              )
            )
      ),
      h(Ind1Stats, { hour: hour, key: 'stats-' + dataVer }),
      h('div', { className: 'sb-sec' },
        h('div', { className: 'sb-lbl' }, 'Leyenda'),
        h('div', { className: 'leg-swatches' },
          h('div', { className: 'leg-sw' },
            h('div', { className: 'leg-dot', style: { background: '#2B5CF6' } }),
            h('span', null, 'Llena (>65%)')
          ),
          h('div', { className: 'leg-sw' },
            h('div', { className: 'leg-dot', style: { background: '#E8421A' } }),
            h('span', null, 'Vac\u00EDa (<35%)')
          )
        ),
        h('div', { className: 'leg-neutral' },
          h('div', { className: 'leg-mini' }),
          h('span', null, 'Equilibrada (35\u201365%) \u2014 sin blob')
        ),
        h('div', { className: 'leg-note' },
          'El \u00E1rea difuminada refleja la intensidad de la condici\u00F3n. Haz clic en cualquier estaci\u00F3n para ver su detalle.'
        )
      )
    ),
    // Mapa + tarjeta + barra de tiempo
    h('main', { className: 'map-area' },
      h(Ind1MapView, {
        hour: hour, onStationClick: handleStation,
        key: 'map-' + dataVer
      }),
      selSt ? h(Ind1StationCard, {
        station: selSt, hour: hour,
        onClose: function(){ setSelSt(null); }
      }) : null,
      h('div', { className: 'time-bar' },
        h('div', { className: 'tb-top' },
          h('button', { className: 'tb-play',
            onClick: function(){ setPlaying(function(p){ return !p; }); }
          }, playing ? '\u23F8' : '\u25B6'),
          h('div', null,
            h('div', { className: 'tb-hour' }, hLabel(hour)),
            h('div', { className: 'tb-ctx' }, hCtx(hour))
          ),
          h('div', { className: 'tb-day' },
            dayLabel,
            mode === 'daytype' && month
              ? h('span', { className: 'tb-month-tag' }, ' \u00B7 ' + monthLabel)
              : null
          )
        ),
        h('input', {
          ref: sliderRef, type: 'range', min: 0, max: 23, value: hour,
          onChange: function(e){ setPlaying(false); setHour(Number(e.target.value)); }
        }),
        h('div', { className: 'tb-ticks' },
          [0,3,6,9,12,15,18,21,23].map(function(hh) {
            return h('span', { key: hh, className: 'tb-tick' },
              String(hh).padStart(2,'0') + 'h');
          })
        )
      )
    )
  );
}

/* ═══════════════════════════════════════════════════════
   App principal — navegación entre indicadores
   ═══════════════════════════════════════════════════════ */
function App() {
  var _s = useState(1); var ind = _s[0]; var setInd = _s[1];

  var TABS = [
    { id: 1, label: 'Saturaci\u00F3n' },
    { id: 2, label: 'Tr\u00E1nsito' },
    { id: 3, label: 'Captura' },
  ];

  return h('div', { className: 'app' },
    // Header
    h('header', { className: 'header' },
      h('div', { className: 'logo' },
        h('span', { className: 'logo-bici' }, 'bici'),
        h('span', { className: 'logo-dot' }),
        h('span', { className: 'logo-mad' }, 'mad')
      ),
      h('div', { className: 'hd-sep' }),
      h('div', { className: 'nav-tabs' },
        TABS.map(function(tab) {
          return h('button', {
            key: tab.id,
            className: 'nav-tab ' + (ind === tab.id ? 'on' : ''),
            onClick: function(){ setInd(tab.id); }
          }, tab.label);
        })
      )
    ),
    // Contenido del indicador activo
    ind === 1 ? h(Ind1View) : null,
    ind === 2 ? h(Ind2View) : null,
    ind === 3 ? h(Ind3View) : null
  );
}

// Montar
ReactDOM.createRoot(document.getElementById('root')).render(h(App));
