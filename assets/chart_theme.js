/**
 * Shared colour palette and Plotly defaults for the Poland 2025 report.
 * Keep chart colours centralised here: changing these tokens updates the report.
 */
(function () {
  const PALETTE = {
    ink: "#15314B",
    blue: "#2563EB",
    amber: "#F59E0B",
    slate: "#64748B",
    green: "#16A34A",
    red: "#DC2626",
    grid: "#E2E8F0",
    track: "#EAF1F8",
    white: "#FFFFFF",
  };

  const C = {
    palette: PALETTE,
    navy: PALETTE.ink,
    demand: PALETTE.blue,
    supply: PALETTE.amber,
    positive: PALETTE.green,
    negative: PALETTE.red,
    pup: PALETTE.red,
    gus: PALETTE.slate,
    neutral: PALETTE.slate,
    muted: PALETTE.slate,
    slate: PALETTE.slate,
    track: PALETTE.track,
    grid: PALETTE.grid,
    white: PALETTE.white,
    font: "Inter, system-ui, sans-serif",
  };

  function scale(colors) {
    const last = colors.length - 1;
    return colors.map((color, i) => [i / last, color]);
  }

  const VOIVODESHIP_LABELS = {
    "dolnośląskie": "Dolnośląskie",
    "kujawsko-pomorskie": "Kujawsko-pomorskie",
    "lubelskie": "Lubelskie",
    "lubuskie": "Lubuskie",
    "łódzkie": "Łódzkie",
    "małopolskie": "Małopolskie",
    "mazowieckie": "Mazowieckie",
    "mazowieckie regionalny": "Mazowieckie (regional BUR)",
    "opolskie": "Opolskie",
    "podkarpackie": "Podkarpackie",
    "podlaskie": "Podlaskie",
    "pomorskie": "Pomorskie",
    "śląskie": "Śląskie",
    "świętokrzyskie": "Świętokrzyskie",
    "warmińsko-mazurskie": "Warmińsko-mazurskie",
    "wielkopolskie": "Wielkopolskie",
    "zachodniopomorskie": "Zachodniopomorskie",
    "brak": "Brak danych",
  };

  function voivodeshipLabel(slug) {
    const key = String(slug || "")
      .trim()
      .toLowerCase();
    return VOIVODESHIP_LABELS[key] || slug;
  }

  window.__CHART_THEME__ = {
    ...C,
    voivodeshipLabel,
    plotConfig: { displayModeBar: false, responsive: true },
    scale: {
      demand: scale(["#EFF6FF", "#BFDBFE", "#60A5FA", PALETTE.blue, "#1E3A8A"]),
      supply: scale(["#FFF7ED", "#FED7AA", "#FDBA74", PALETTE.amber, "#B45309"]),
      neutral: scale(["#F8FAFC", "#E2E8F0", "#CBD5E1", PALETTE.slate]),
      green: scale(["#F0FDF4", "#BBF7D0", "#4ADE80", PALETTE.green, "#166534"]),
    },
    baseLayout(extra) {
      return {
        margin: { l: 72, r: 16, t: 12, b: 28 },
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        font: { family: C.font, color: C.navy, size: 12 },
        hoverlabel: {
          bgcolor: C.white,
          bordercolor: C.grid,
          font: { color: C.navy, size: 12 },
        },
        ...(extra || {}),
      };
    },
    gapColor(gapPp) {
      return gapPp >= 0 ? C.negative : C.positive;
    },
    mapMarker() {
      return { line: { color: "rgba(255,255,255,0.95)", width: 1 } };
    },
  };
})();
