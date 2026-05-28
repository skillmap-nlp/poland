/* ============================================================
   Ukrainian-friendly decomposition — shift-share figures.
   Consumes:
     window.__UKR_DECOMP__       (payload from build_ukrainian_friendly_decomposition.py)
     window.__CHART_THEME__      (shared colour theme)
   ============================================================ */
(function () {
  const payload = window.__UKR_DECOMP__;
  const T = window.__CHART_THEME__;
  if (!payload || !window.Plotly || !T) return;

  const fmtInt = (v) =>
    new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(v);

  /* ────────────────────────────────────────────────────────────
     Shift-share decomposition: stacked horizontal bars
     ──────────────────────────────────────────────────────────── */
  function renderShiftShare(elId, rows, title) {
    const el = document.getElementById(elId);
    if (!el || !rows || rows.length === 0) return;

    const sorted = [...rows].sort((a, b) => a.gap_pp - b.gap_pp);
    const labels = sorted.map((r) => r.label);
    const within = sorted.map((r) => r.within_pp);
    const between = sorted.map((r) => r.between_pp);
    const gap = sorted.map((r) => r.gap_pp);

    const traces = [
      {
        type: "bar",
        orientation: "h",
        name: "Within-sector (behavioural)",
        x: within,
        y: labels,
        marker: { color: T.demand },
        customdata: sorted.map((r) => [
          r.share_pct.toFixed(1),
          fmtInt(r.n),
          r.gap_pp.toFixed(1),
        ]),
        hovertemplate:
          "<b>%{y}</b><br>" +
          "Within-sector (behavioural): %{x:+.2f} pp<br>" +
          "Share: %{customdata[0]}%  ·  n=%{customdata[1]}  ·  gap=%{customdata[2]} pp<extra></extra>",
      },
      {
        type: "bar",
        orientation: "h",
        name: "Between-sector (composition)",
        x: between,
        y: labels,
        marker: { color: T.supply },
        customdata: sorted.map((r) => [
          r.share_pct.toFixed(1),
          fmtInt(r.n),
          r.gap_pp.toFixed(1),
        ]),
        hovertemplate:
          "<b>%{y}</b><br>" +
          "Between-sector (composition): %{x:+.2f} pp<br>" +
          "Share: %{customdata[0]}%  ·  n=%{customdata[1]}  ·  gap=%{customdata[2]} pp<extra></extra>",
      },
      {
        type: "scatter",
        mode: "markers",
        name: "Observed gap",
        x: gap,
        y: labels,
        marker: { color: "#111", size: 8, symbol: "diamond" },
        hovertemplate: "<b>%{y}</b><br>Observed gap: %{x:+.2f} pp<extra></extra>",
      },
    ];

    const layout = {
      barmode: "relative",
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      margin: { l: 240, r: 24, t: 8, b: 36 },
      height: Math.max(360, labels.length * 28 + 80),
      legend: { orientation: "h", x: 0, xanchor: "left", y: 1.06 },
      xaxis: {
        title: { text: "Contribution to gap from national share (pp)" },
        zeroline: true,
        zerolinecolor: "#999",
        zerolinewidth: 1,
        gridcolor: T.grid,
        ticksuffix: " pp",
      },
      yaxis: {
        autorange: "reversed",
        tickfont: { size: 11 },
      },
      title: title
        ? { text: title, font: { size: 13 }, x: 0, xanchor: "left" }
        : undefined,
    };

    Plotly.newPlot(el, traces, layout, {
      displayModeBar: false,
      responsive: true,
    });
  }

  function renderDecompKpis() {
    const el = document.getElementById("ukr-decomp-kpis");
    if (!el) return;
    const m = payload.meta;
    const powiats = payload.decomp_powiat || [];
    const voivs = payload.decomp_voivodeship || [];

    const cards = [
      {
        label: "National UA-tag share",
        value: `${m.national_share_pct.toFixed(1)}%`,
        subtext: `${fmtInt(m.n_postings)} postings with NACE & powiat`,
      },
      {
        label: "Powiats in decomposition",
        value: fmtInt(powiats.length),
        subtext: `Top-20 ranked by |gap|; ≥ ${m.min_postings_per_powiat} postings each`,
      },
      {
        label: "Voivodeships",
        value: fmtInt(voivs.length),
        subtext: "Within- vs between-sector split for all 16",
      },
    ];

    el.innerHTML = cards
      .map(
        (c) => `
        <article class="card">
          <p class="label">${c.label}</p>
          <p class="value">${c.value}</p>
          <p class="subtext">${c.subtext}</p>
        </article>`
      )
      .join("");
  }

  renderDecompKpis();
  renderShiftShare(
    "ukr-shift-powiat",
    payload.decomp_powiat,
    "Top-20 powiats by |gap from national share|"
  );
  renderShiftShare(
    "ukr-shift-voivodeship",
    payload.decomp_voivodeship,
    "All 16 voivodeships"
  );
})();
