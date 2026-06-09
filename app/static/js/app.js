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
