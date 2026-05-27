(function () {
  const data = window.__INTL_COMPARISON__;
  const T = window.__CHART_THEME__;
  if (!data || !window.Plotly || !T) return;

  const COUNTRY_FULL = {
    JP: "Japan",
    KR: "S. Korea",
    TW: "Taiwan",
    TH: "Thailand",
    MY: "Malaysia",
    SG: "Singapore",
    ID: "Indonesia",
    VN: "Vietnam",
    PH: "Philippines",
    IN: "India",
    MX: "Mexico",
    PL: "Poland",
  };

  const HIGHLIGHT_NAME = data.highlight_country || "Poland";
  const HIGHLIGHT_ISO = data.highlight_iso || "PL";

  const COUNTRY_ORDER = [
    "JP",
    "KR",
    "TW",
    "TH",
    "MY",
    "SG",
    "ID",
    "VN",
    "PH",
    "IN",
    "MX",
    "PL",
  ];

  const REGION_OF = {};
  (data.regions?.east_asia || []).forEach((c) => (REGION_OF[c] = "east_asia"));
  (data.regions?.benchmark || []).forEach((c) => (REGION_OF[c] = "benchmark"));

  const ACCENT = "#7c3aed";
  const ACCENT_SOFT = "#ede9fe";
  const EAST_ASIA = "#0f766e";
  const BENCHMARK = "#7c3aed";
  const POLAND = "#1d4ed8";

  const fmtPct = (v) => `${(v * 100).toFixed(1)}%`;
  const fmtInt = (v) =>
    v == null
      ? "—"
      : new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(v);
  const fmtMoney = (v) =>
    v == null
      ? "—"
      : `$${new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(v)}`;
  const fmtFloat1 = (v) =>
    v == null ? "—" : Number(v).toFixed(1);

  /* ── Macro context table ──────────────────────────────────── */
  function renderMacro() {
    const el = document.getElementById("intl-macro-card");
    if (!el) return;
    const macro = data.macro || {};

    const rows = COUNTRY_ORDER.filter((iso) => macro[iso]).map((iso) => {
      const m = macro[iso];
      const region = REGION_OF[COUNTRY_FULL[iso]] || "east_asia";
      const highlight = iso === HIGHLIGHT_ISO;
      return `
        <tr class="${highlight ? "intl-row-highlight" : ""} intl-row-${region}">
          <td class="intl-country">
            <span class="intl-region-dot intl-region-${region}"></span>
            <strong>${COUNTRY_FULL[iso]}</strong>${highlight ? ' <span class="intl-this-report">this report</span>' : ""}
          </td>
          <td>${m.income_group || "—"}</td>
          <td class="num">${fmtMoney(m.gdp_cap_ppp)}</td>
          <td class="num">${fmtFloat1(m.old_age_dep)}</td>
          <td class="num">${fmtFloat1(m.fertility)}</td>
          <td class="num">${fmtFloat1(m.manuf_pct)}%</td>
          <td class="num">${fmtFloat1(m.services_pct)}%</td>
          <td class="num">${fmtFloat1(m.exports_pct)}%</td>
        </tr>`;
    });

    el.innerHTML = `
      <div class="intl-table-wrap">
        <table class="intl-table">
          <thead>
            <tr>
              <th>Country</th>
              <th>Income group</th>
              <th class="num">GDP/cap PPP</th>
              <th class="num">Old-age dep.</th>
              <th class="num">Fertility</th>
              <th class="num">Manuf. %GDP</th>
              <th class="num">Services %GDP</th>
              <th class="num">Exports %GDP</th>
            </tr>
          </thead>
          <tbody>${rows.join("")}</tbody>
        </table>
      </div>
      <p class="notes source-note">Source: World Bank macro indicators (latest available year per country), drawn from the East Asia skill-demand report. Poland row contextualises figures shown elsewhere in this report.</p>
    `;
  }

  /* ── Digital skill levels (Basic / Intermediate / Advanced) ── */
  function renderDigitalLevels() {
    const el = document.getElementById("intl-digital-levels");
    if (!el) return;
    const rows = (data.digital_levels?.rows || []).slice();

    rows.sort(
      (a, b) =>
        (b.shares?.Advanced || 0) - (a.shares?.Advanced || 0),
    );

    const countries = rows.map((r) => r.country);
    const advanced = rows.map((r) => (r.shares?.Advanced || 0) * 100);
    const intermediate = rows.map((r) => (r.shares?.Intermediate || 0) * 100);
    const basic = rows.map((r) => (r.shares?.Basic || 0) * 100);

    const colorFor = (level, country) => {
      if (country === HIGHLIGHT_NAME) {
        if (level === "advanced") return "#15314B";
        if (level === "intermediate") return "#1d4ed8";
        return "#3b82f6";
      }
      if (level === "advanced") return "#94a3b8";
      if (level === "intermediate") return "#cbd5e1";
      return "#e2e8f0";
    };

    const advColors = countries.map((c) => colorFor("advanced", c));
    const intColors = countries.map((c) => colorFor("intermediate", c));
    const basColors = countries.map((c) => colorFor("basic", c));

    const traces = [
      {
        x: countries,
        y: basic,
        name: "Basic",
        type: "bar",
        marker: { color: basColors },
        hovertemplate: "<b>%{x}</b><br>Basic: %{y:.1f}%<extra></extra>",
      },
      {
        x: countries,
        y: intermediate,
        name: "Intermediate",
        type: "bar",
        marker: { color: intColors },
        hovertemplate: "<b>%{x}</b><br>Intermediate: %{y:.1f}%<extra></extra>",
      },
      {
        x: countries,
        y: advanced,
        name: "Advanced",
        type: "bar",
        marker: { color: advColors },
        hovertemplate: "<b>%{x}</b><br>Advanced: %{y:.1f}%<extra></extra>",
      },
    ];

    const layout = {
      barmode: "stack",
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      margin: { l: 50, r: 12, t: 10, b: 60 },
      xaxis: {
        tickangle: -25,
        automargin: true,
        tickfont: { size: 11 },
      },
      yaxis: {
        title: { text: "Share of classified digital mentions (%)" },
        ticksuffix: "%",
        range: [0, 100],
        gridcolor: "rgba(0,0,0,0.06)",
      },
      legend: { orientation: "h", y: 1.12, x: 0 },
      height: 380,
    };

    Plotly.newPlot(el, traces, layout, {
      displayModeBar: false,
      responsive: true,
    });
  }

  /* ── ESCO S1-S8 demand mix across countries ───────────────── */
  function renderEscoMix() {
    const el = document.getElementById("intl-esco-s1s8");
    if (!el) return;
    const meta = data.esco_skill_shares?.skill_meta || {};
    const order = data.esco_skill_shares?.country_order || [];
    const countries = order.filter(
      (c) => data.esco_skill_shares?.countries?.[c]?.skill_shares,
    );

    const pillars = ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"];
    const pillarLabel = (code) => `${code} · ${meta[code] || ""}`;

    const palette = {
      S1: "#0f766e",
      S2: "#0891b2",
      S3: "#22c55e",
      S4: "#1d4ed8",
      S5: "#7c3aed",
      S6: "#f59e0b",
      S7: "#a16207",
      S8: "#dc2626",
    };

    const traces = pillars.map((p) => ({
      x: countries.map((c) =>
        ((data.esco_skill_shares.countries[c].skill_shares[p] || 0) * 100).toFixed(1),
      ),
      y: countries,
      orientation: "h",
      type: "bar",
      name: pillarLabel(p),
      marker: { color: palette[p] },
      hovertemplate: `<b>%{y}</b><br>${pillarLabel(p)}: %{x}%<extra></extra>`,
    }));

    const layout = {
      barmode: "stack",
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      margin: { l: 120, r: 10, t: 10, b: 60 },
      xaxis: {
        title: { text: "Share of ESCO S1–S8 demand mentions (%)" },
        ticksuffix: "%",
        range: [0, 100],
        gridcolor: "rgba(0,0,0,0.06)",
      },
      yaxis: {
        automargin: true,
        tickfont: (() => {
          // Bold tick for Poland.
          return { size: 11 };
        })(),
      },
      legend: { orientation: "h", y: -0.22, x: 0 },
      height: 420,
    };

    Plotly.newPlot(el, traces, layout, {
      displayModeBar: false,
      responsive: true,
    });
  }

  /* ── Render all ───────────────────────────────────────────── */
  renderMacro();
  renderDigitalLevels();
  renderEscoMix();
})();
