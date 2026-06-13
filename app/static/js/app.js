/* ═══════════════════════════════════════════════════════
   BiciMAD · App principal — Plataforma de Indicadores
   ═══════════════════════════════════════════════════════
*/

/* ═══════════════════════════════════════════════════════
   App principal
   ═══════════════════════════════════════════════════════ */
function App() {
  var _s = useState(1);
  var ind = _s[0];
  var setInd = _s[1];

  // Estado de conexión con el backend:
  //   'checking' → sondeando al arrancar
  //   'ok'       → backend responde con normalidad
  //   'down'     → backend no responde, mostramos opción demo
  //   'demo'     → el usuario eligió continuar con datos de muestra
  var _sStatus = useState("checking");
  var status = _sStatus[0];
  var setStatus = _sStatus[1];

  function runHealthCheck() {
    setStatus("checking");
    checkBackendHealth().then(function (ok) {
      setStatus(ok ? "ok" : "down");
    });
  }

  useEffect(function () {
    runHealthCheck();
  }, []);

  // ── Pantalla de espera mientras se hace la sonda ──
  if (status === "checking") {
    return h(
      "div",
      { className: "loading-overlay" },
      h("div", { className: "loading-spinner" }),
      h("div", { className: "loading-text" }, "Conectando con el servidor…"),
    );
  }

  // ── Pantalla de error con opción de demo ──
  if (status === "down") {
    var btnBase = {
      padding: "10px 18px",
      borderRadius: 8,
      border: "1px solid rgba(0,0,0,0.15)",
      background: "#fff",
      color: "#222",
      fontSize: 13,
      fontWeight: 600,
      cursor: "pointer",
      fontFamily: "inherit",
    };
    var btnPrimary = Object.assign({}, btnBase, {
      background: "#2B5CF6",
      color: "#fff",
      border: "1px solid #2B5CF6",
    });

    return h(
      "div",
      { className: "loading-overlay" },
      h(
        "div",
        {
          className: "loading-error",
          style: {
            maxWidth: 480,
            textAlign: "center",
            padding: "28px 32px",
            lineHeight: 1.55,
          },
        },
        h(
          "div",
          { style: { fontSize: 20, marginBottom: 12 } },
          "\u26A0 No se pudo conectar con el servidor",
        ),
        h(
          "div",
          { style: { fontSize: 13, opacity: 0.85, marginBottom: 22 } },
          "La base de datos no responde. Aseg\u00FArate de que ",
          h("code", null, "server.py"),
          " est\u00E1 corriendo, o explora la aplicaci\u00F3n con un conjunto reducido de datos de muestra.",
        ),
        h(
          "div",
          {
            style: {
              display: "flex",
              gap: 10,
              justifyContent: "center",
              flexWrap: "wrap",
            },
          },
          h(
            "button",
            { onClick: runHealthCheck, style: btnBase },
            "Reintentar conexi\u00F3n",
          ),
          h(
            "button",
            {
              onClick: function () {
                enableDemoMode();
                setStatus("demo");
              },
              style: btnPrimary,
            },
            "Probar con datos de demo",
          ),
        ),
        h(
          "div",
          {
            style: {
              fontSize: 11,
              opacity: 0.6,
              marginTop: 18,
            },
          },
          "El modo demo usa unas pocas estaciones y celdas de ejemplo. Los filtros tendr\u00E1n efecto limitado.",
        ),
      ),
    );
  }

  // ── App normal (status === 'ok' o 'demo') ──
  var inDemo = status === "demo";

  var TABS = [
    { id: 1, label: "Saturación" },
    { id: 2, label: "Tránsito" },
    { id: 3, label: "Actividad compartida" },
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
        h("span", { className: "logo-bici" }, "indicadores bici"),
        h("span", { className: "logo-dot" }),
        h("span", { className: "logo-mad" }, "mad"),
      ),
      h("div", { className: "hd-sep" }),
      inDemo
        ? h(
            "div",
            {
              title:
                "Estás usando datos de muestra. Recarga la página para volver a intentar la conexión real.",
              style: {
                padding: "3px 10px",
                background: "#FFE9A8",
                color: "#7A5A00",
                borderRadius: 999,
                fontSize: 11,
                fontWeight: 700,
                letterSpacing: "0.04em",
                textTransform: "uppercase",
                border: "1px solid #E8C870",
              },
            },
            "Modo demo",
          )
        : null,
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
      // h(
      //   "button",
      //   {
      //     className: "download-btn",
      //     title: "Descargar datos en crudo del indicador actual",
      //     onClick: function () {
      //       downloadRawData(ind);
      //     },
      //   },
      //   h(
      //     "svg",
      //     {
      //       width: 16,
      //       height: 16,
      //       viewBox: "0 0 16 16",
      //       fill: "none",
      //       stroke: "currentColor",
      //       strokeWidth: 1.8,
      //       strokeLinecap: "round",
      //       strokeLinejoin: "round",
      //     },
      //     h("path", { d: "M8 2v8m0 0l-3-3m3 3l3-3" }),
      //     h("path", { d: "M2 12v1.5a.5.5 0 00.5.5h11a.5.5 0 00.5-.5V12" }),
      //   ),
      //   h("span", null, "Datos"),
      // ),
    ),
    ind === 1 ? h(Ind1View) : null,
    ind === 2 ? h(Ind2View) : null,
    ind === 3 ? h(Ind3View) : null,
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(h(App));
