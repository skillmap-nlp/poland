(function () {
  const data = window.__UKRAINIAN_FRIENDLY__;
  const regionalPayload = window.__REGIONAL_REPORT__;
  const T = window.__CHART_THEME__;
  if (!data || !window.Plotly || !T) return;

  const geojson = regionalPayload ? regionalPayload.geojson : null;

  const fmtInt = (v) =>
    new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(v);
  const fmtPct = (v) =>
    new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(v);

  const truncateLabel = (label, max = 58) => {
    const text = String(label || "");
    return text.length > max ? `${text.slice(0, max - 1)}…` : text;
  };

  const titleVoiv = (row) =>
    T.voivodeshipLabel(typeof row === "string" ? row : row.voivodeship);

  const COLOR_MAIN = T.demand;
  const COLOR_ACCENT = T.supply;

  /* ── KPI cards ── */
  function renderCards() {
    const el = document.getElementById("ukr-kpi-cards");
    if (!el) return;
    const m = data.meta;
    el.innerHTML = [
      {
        label: "Offers screened for the badge",
        value: fmtInt(m.scraped_offers),
        subtext: "All Pracuj.pl postings (2025)",
      },
      {
        label: "Offers tagged 'Jobs for Ukrainians'",
        value: fmtInt(m.ukr_offers),
        subtext: `${fmtPct(m.ukr_pct_national)}% of all postings`,
      },
      {
        label: "Top region by share",
        value: (() => {
          const top = [...data.voivodeships].sort(
            (a, b) => b.ukr_pct - a.ukr_pct
          )[0];
          return titleVoiv(top);
        })(),
        subtext: (() => {
          const top = [...data.voivodeships].sort(
            (a, b) => b.ukr_pct - a.ukr_pct
          )[0];
          return `${fmtPct(top.ukr_pct)}% of regional offers`;
        })(),
      },
    ]
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

  /* ── Choropleth: % offers tagged Ukrainian-friendly by voivodeship ── */
  function renderMap() {
    const el = document.getElementById("ukr-regional-map");
    if (!el || !geojson) return;

    const rows = data.voivodeships;
    const locations = rows.map((r) => r.voivodeship);
    const z = rows.map((r) => r.ukr_pct);
    const customdata = rows.map((r) => [
      fmtInt(r.ukr_offers),
      fmtInt(r.total_offers),
      titleVoiv(r),
    ]);

    const trace = {
      type: "choropleth",
      geojson,
      featureidkey: "properties.nazwa",
      locations,
      z,
      customdata,
      colorscale: T.scale.demand,
      marker: T.mapMarker(),
      colorbar: {
        title: { text: "% offers<br>tagged for<br>Ukrainians" },
        thickness: 16,
        len: 0.7,
        x: 1.03,
        y: 0.5,
        outlinewidth: 0,
        ticksuffix: "%",
      },
      hovertemplate:
        "<b>%{customdata[2]}</b><br>" +
        "Share: %{z:.1f}%<br>" +
        "Tagged offers: %{customdata[0]}<br>" +
        "Total offers: %{customdata[1]}<extra></extra>",
    };

    const layout = {
      margin: { l: 0, r: 12, t: 0, b: 0 },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      dragmode: false,
      showlegend: false,
      geo: {
        fitbounds: "locations",
        visible: false,
        projection: { type: "mercator" },
        bgcolor: "rgba(0,0,0,0)",
      },
    };

    Plotly.newPlot(el, [trace], layout, {
      displayModeBar: false,
      responsive: true,
    });
  }

  /* ── Bar chart helper for share-style charts ── */
  function barShare(elId, rows, labelKey, color, height = 460, leftMargin = 280) {
    const el = document.getElementById(elId);
    if (!el) return;

    const r = [...rows].reverse();
    const trace = {
      type: "bar",
      orientation: "h",
      x: r.map((d) => d.ukr_pct),
      y: r.map((d) => truncateLabel(d[labelKey])),
      customdata: r.map((d) => [
        d[labelKey],
        fmtInt(d.ukr_offers),
        fmtInt(d.total_offers),
      ]),
      marker: { color, line: { width: 0 } },
      hovertemplate:
        "<b>%{customdata[0]}</b><br>Share Ukrainian-friendly: %{x:.1f}%<br>" +
        "Tagged offers: %{customdata[1]}<br>Total offers: %{customdata[2]}<extra></extra>",
    };

    const layout = {
      margin: { l: leftMargin, r: 30, t: 10, b: 40 },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      xaxis: {
        title: { text: "% offers tagged 'Jobs for Ukrainians'", standoff: 6 },
        ticksuffix: "%",
        gridcolor: "rgba(0,0,0,0.06)",
        zeroline: false,
      },
      yaxis: { automargin: true, tickfont: { size: 11 } },
      height,
      bargap: 0.25,
    };

    Plotly.newPlot(el, [trace], layout, {
      displayModeBar: false,
      responsive: true,
    });
  }

  /* ── Bar chart for absolute counts ── */
  function barCount(elId, rows, labelKey, color, height = 460, leftMargin = 280) {
    const el = document.getElementById(elId);
    if (!el) return;

    const r = [...rows].reverse();
    const trace = {
      type: "bar",
      orientation: "h",
      x: r.map((d) => d.ukr_offers),
      y: r.map((d) => truncateLabel(d[labelKey])),
      customdata: r.map((d) => [
        d[labelKey],
        d.ukr_pct.toFixed(1),
        fmtInt(d.total_offers),
      ]),
      marker: { color, line: { width: 0 } },
      hovertemplate:
        "<b>%{customdata[0]}</b><br>Tagged offers: %{x:,}<br>" +
        "Share: %{customdata[1]}%<br>Total offers: %{customdata[2]}<extra></extra>",
    };

    const layout = {
      margin: { l: leftMargin, r: 30, t: 10, b: 40 },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      xaxis: {
        title: { text: "Number of offers tagged 'Jobs for Ukrainians'", standoff: 6 },
        gridcolor: "rgba(0,0,0,0.06)",
        zeroline: false,
      },
      yaxis: { automargin: true, tickfont: { size: 11 } },
      height,
      bargap: 0.25,
    };

    Plotly.newPlot(el, [trace], layout, {
      displayModeBar: false,
      responsive: true,
    });
  }

  /* ── Scatter: offers/100k LF (X) vs Ukrainian-friendly share % (Y) ── */
  function renderDensityScatter() {
    const el = document.getElementById("ukr-density-scatter");
    if (!el) return;

    const rows = data.voivodeships.filter(
      (r) => r.offers_per_100k_lf != null
    );
    const xs = rows.map((r) => r.offers_per_100k_lf);
    const ys = rows.map((r) => r.ukr_pct);
    const labels = rows.map((r) => titleVoiv(r));

    const corr = data.meta.density_correlation;
    const xmin = Math.min(...xs);
    const xmax = Math.max(...xs);
    const xPad = (xmax - xmin) * 0.08;
    const lineX = [xmin - xPad, xmax + xPad];
    const lineY = lineX.map((x) => corr.intercept + corr.slope * x);

    const points = {
      type: "scatter",
      mode: "markers+text",
      x: xs,
      y: ys,
      text: labels,
      textposition: "top center",
      textfont: { size: 10, color: "#1e293b" },
      marker: { size: 11, color: COLOR_MAIN, line: { width: 1, color: "#fff" } },
      customdata: rows.map((r) => [
        fmtInt(r.total_offers),
        fmtInt(r.ukr_offers),
      ]),
      hovertemplate:
        "<b>%{text}</b><br>" +
        "Offers / 100k LF: %{x:,.0f}<br>" +
        "Ukrainian-friendly share: %{y:.2f}%<br>" +
        "Total offers: %{customdata[0]}<br>" +
        "Ukrainian-friendly: %{customdata[1]}<extra></extra>",
      name: "Voivodeships",
    };

    const fit = {
      type: "scatter",
      mode: "lines",
      x: lineX,
      y: lineY,
      line: { color: COLOR_ACCENT, width: 2, dash: "dash" },
      hoverinfo: "skip",
      name: `OLS fit (R²=${corr.r_squared.toFixed(2)})`,
    };

    const layout = {
      margin: { l: 70, r: 30, t: 40, b: 60 },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      xaxis: {
        title: { text: "Total job offers per 100k labour force" },
        gridcolor: "rgba(0,0,0,0.06)",
        zeroline: false,
      },
      yaxis: {
        title: { text: "Share of offers tagged 'Jobs for Ukrainians'" },
        ticksuffix: "%",
        gridcolor: "rgba(0,0,0,0.06)",
        zeroline: false,
      },
      showlegend: true,
      legend: { x: 0.02, y: 0.98, bgcolor: "rgba(255,255,255,0.7)" },
      annotations: [
        {
          xref: "paper",
          yref: "paper",
          x: 0.98,
          y: 0.04,
          xanchor: "right",
          yanchor: "bottom",
          showarrow: false,
          align: "right",
          bgcolor: "rgba(255,255,255,0.85)",
          bordercolor: "rgba(0,0,0,0.1)",
          borderwidth: 1,
          font: { size: 11, color: "#1e293b" },
          text:
            `Pearson r = ${corr.pearson_r.toFixed(2)}<br>` +
            `Spearman ρ = ${corr.spearman_rho.toFixed(2)}<br>` +
            `R² = ${corr.r_squared.toFixed(2)} (n=${rows.length})`,
        },
      ],
      height: 500,
    };

    Plotly.newPlot(el, [points, fit], layout, {
      displayModeBar: false,
      responsive: true,
    });
  }

  /* ── Renders ── */
  renderCards();
  renderMap();
  renderDensityScatter();

  // NACE sections (top-level industries) — sort by share within section view.
  // Largest-to-smallest (top-to-bottom); exclude Public administration (NACE section O).
  barShare(
    "ukr-industries-section-chart",
    [...data.industries_section]
      .filter((r) => r.nace_section !== "O")
      .sort((a, b) => b.ukr_pct - a.ukr_pct)
      .slice(0, 12)
      .map((r) => ({ ...r, label: `${r.nace_section_title} (${r.nace_section})` })),
    "label",
    COLOR_MAIN,
    520,
    320
  );

  // NACE divisions — top by share (with min-offer threshold applied upstream)
  barShare(
    "ukr-industries-share-chart",
    [...data.top_industries_by_share].slice(0, 15).map((r) => ({
      ...r,
      label: `${r.nace_title} (${r.nace_code})`,
    })),
    "label",
    COLOR_ACCENT,
    600,
    300
  );

  // NACE divisions — top by absolute number of Ukrainian-friendly offers
  barCount(
    "ukr-industries-count-chart",
    [...data.top_industries_by_count].slice(0, 15).map((r) => ({
      ...r,
      label: `${r.nace_title} (${r.nace_code})`,
    })),
    "label",
    COLOR_MAIN,
    600,
    300
  );

  // Job categories (narrow) — top by share
  barShare(
    "ukr-categories-narrow-share-chart",
    [...data.categories_narrow_by_share].slice(0, 15),
    "label",
    COLOR_ACCENT,
    560,
    260
  );

  // Job categories (narrow) — top by count
  barCount(
    "ukr-categories-narrow-count-chart",
    [...data.categories_narrow_by_count].slice(0, 15),
    "label",
    COLOR_MAIN,
    560,
    260
  );

  // Seniority — sort by share
  barShare(
    "ukr-seniority-chart",
    [...data.seniority].sort((a, b) => a.ukr_pct - b.ukr_pct),
    "label",
    COLOR_MAIN,
    420,
    240
  );

  // Contract types — sort by share
  barShare(
    "ukr-contracts-chart",
    [...data.contract_types].sort((a, b) => a.ukr_pct - b.ukr_pct),
    "label",
    COLOR_ACCENT,
    360,
    240
  );
})();

/* ============================================================
   Powiat-level: choropleth map of UA-friendly share + scatter
   ============================================================ */
(function () {
  const payload = window.__UKRAINIAN_FRIENDLY_POWIAT__;
  const T = window.__CHART_THEME__;
  if (!payload || !window.Plotly || !T) return;

  const fmtInt = (v) =>
    new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(v);

  const COLOR_MAIN = T.demand;
  const COLOR_ACCENT = T.supply;

  const lookup = new Map(payload.powiats.map((r) => [r.key, r]));

  /* Choropleth: total job-offer intensity per powiat (offers / 100k employed) */
  function renderPowiatIntensityMap(geojson) {
    const el = document.getElementById("ukr-powiat-intensity-map");
    if (!el) return;

    const features = geojson.features.filter(
      (f) =>
        lookup.has(f.properties.key) &&
        lookup.get(f.properties.key).offers_per_100k_emp != null
    );

    const locations = features.map((f) => f.properties.key);
    const z = features.map(
      (f) => lookup.get(f.properties.key).offers_per_100k_emp
    );
    const customdata = features.map((f) => {
      const r = lookup.get(f.properties.key);
      return [
        r.powiat_label,
        T.voivodeshipLabel(r.voivodeship),
        fmtInt(r.total_offers),
        fmtInt(r.employed_2025),
      ];
    });

    // Cap at the 95th percentile so dense outliers don't drown the rest.
    const sorted = [...z].sort((a, b) => a - b);
    const cap = sorted[Math.floor(sorted.length * 0.95)];

    const trace = {
      type: "choropleth",
      geojson,
      featureidkey: "properties.key",
      locations,
      z,
      customdata,
      zmin: 0,
      zmax: cap,
      colorscale: T.scale.demand,
      marker: { line: { color: "rgba(255,255,255,0.7)", width: 0.3 } },
      colorbar: {
        title: { text: "Offers per<br>100k employed" },
        thickness: 16,
        len: 0.7,
        x: 1.02,
        y: 0.5,
        outlinewidth: 0,
        tickformat: ",d",
      },
      hovertemplate:
        "<b>%{customdata[0]}</b><br>" +
        "Voivodeship: %{customdata[1]}<br>" +
        "Offers / 100k employed: %{z:,.0f}<br>" +
        "Total offers: %{customdata[2]}<br>" +
        "Employed (2025): %{customdata[3]}<extra></extra>",
    };

    const layout = {
      margin: { l: 0, r: 12, t: 0, b: 0 },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      dragmode: false,
      showlegend: false,
      geo: {
        fitbounds: "locations",
        visible: false,
        projection: { type: "mercator" },
        bgcolor: "rgba(0,0,0,0)",
      },
    };

    Plotly.newPlot(el, [trace], layout, {
      displayModeBar: false,
      responsive: true,
    });
  }

  function renderPowiatMap(geojson) {
    const el = document.getElementById("ukr-powiat-map");
    if (!el) return;

    // Filter to features that have data (most do; some city-rights have 0).
    const features = geojson.features.filter((f) =>
      lookup.has(f.properties.key)
    );

    const locations = features.map((f) => f.properties.key);
    const z = features.map((f) => lookup.get(f.properties.key).ukr_pct);
    const customdata = features.map((f) => {
      const r = lookup.get(f.properties.key);
      return [
        r.powiat_label,
        T.voivodeshipLabel(r.voivodeship),
        fmtInt(r.ukr_offers),
        fmtInt(r.total_offers),
      ];
    });

    const trace = {
      type: "choropleth",
      geojson,
      featureidkey: "properties.key",
      locations,
      z,
      customdata,
      // Cap colour scale at 25% so the long tail doesn't wash out the map.
      zmin: 0,
      zmax: 25,
      colorscale: T.scale.demand,
      marker: { line: { color: "rgba(255,255,255,0.7)", width: 0.3 } },
      colorbar: {
        title: { text: "% offers<br>tagged for<br>Ukrainians" },
        thickness: 16,
        len: 0.7,
        x: 1.02,
        y: 0.5,
        outlinewidth: 0,
        ticksuffix: "%",
      },
      hovertemplate:
        "<b>%{customdata[0]}</b><br>" +
        "Voivodeship: %{customdata[1]}<br>" +
        "Share: %{z:.1f}%<br>" +
        "Tagged: %{customdata[2]} / %{customdata[3]} offers<extra></extra>",
    };

    const layout = {
      margin: { l: 0, r: 12, t: 0, b: 0 },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      dragmode: false,
      showlegend: false,
      geo: {
        fitbounds: "locations",
        visible: false,
        projection: { type: "mercator" },
        bgcolor: "rgba(0,0,0,0)",
      },
    };

    Plotly.newPlot(el, [trace], layout, {
      displayModeBar: false,
      responsive: true,
    });
  }

  function renderPowiatScatter() {
    const el = document.getElementById("ukr-powiat-scatter");
    if (!el) return;

    const m = payload.meta;
    const rows = payload.powiats.filter(
      (r) =>
        r.offers_per_100k_emp != null &&
        r.total_offers >= m.min_offers_for_corr
    );

    const xs = rows.map((r) => r.offers_per_100k_emp);
    const ys = rows.map((r) => r.ukr_pct);
    const sizes = rows.map((r) =>
      Math.max(5, Math.min(28, Math.sqrt(r.total_offers) / 4))
    );

    // Highlight a handful of outliers / large markets.
    const labelSet = new Set(
      [
        ...rows.sort((a, b) => b.total_offers - a.total_offers).slice(0, 6),
        ...rows.sort((a, b) => b.ukr_pct - a.ukr_pct).slice(0, 4),
      ].map((r) => r.key)
    );
    const labels = rows.map((r) =>
      labelSet.has(r.key) ? r.powiat_label.replace(/^powiat /, "") : ""
    );

    const xmin = Math.min(...xs);
    const xmax = Math.max(...xs);
    const xPad = (xmax - xmin) * 0.05;
    const lineX = [Math.max(0, xmin - xPad), xmax + xPad];
    const lineY = lineX.map((x) => m.intercept + m.slope * x);

    const points = {
      type: "scatter",
      mode: "markers+text",
      x: xs,
      y: ys,
      text: labels,
      textposition: "top center",
      textfont: { size: 10, color: "#1e293b" },
      marker: {
        size: sizes,
        color: rows.map((r) => r.ukr_pct),
        colorscale: T.scale.demand,
        cmin: 0,
        cmax: 25,
        line: { width: 0.5, color: "rgba(255,255,255,0.7)" },
        opacity: 0.75,
      },
      customdata: rows.map((r) => [
        r.powiat_label,
        T.voivodeshipLabel(r.voivodeship),
        fmtInt(r.total_offers),
        fmtInt(r.ukr_offers),
        fmtInt(r.employed_2025),
      ]),
      hovertemplate:
        "<b>%{customdata[0]}</b><br>" +
        "Voivodeship: %{customdata[1]}<br>" +
        "Offers / 100k employed: %{x:,.0f}<br>" +
        "Ukrainian-friendly share: %{y:.2f}%<br>" +
        "Total offers: %{customdata[2]}<br>" +
        "Tagged: %{customdata[3]}<br>" +
        "Employed (2025): %{customdata[4]}<extra></extra>",
      name: "Powiats (counties)",
    };

    const fit = {
      type: "scatter",
      mode: "lines",
      x: lineX,
      y: lineY,
      line: { color: COLOR_ACCENT, width: 2, dash: "dash" },
      hoverinfo: "skip",
      name: `OLS fit (R²=${(m.r_squared ?? 0).toFixed(3)})`,
    };

    const layout = {
      margin: { l: 70, r: 30, t: 40, b: 60 },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      xaxis: {
        title: { text: "Total job offers per 100k employed (2025)" },
        gridcolor: "rgba(0,0,0,0.06)",
        zeroline: false,
      },
      yaxis: {
        title: { text: "Share of offers tagged 'Jobs for Ukrainians'" },
        ticksuffix: "%",
        gridcolor: "rgba(0,0,0,0.06)",
        zeroline: false,
      },
      showlegend: true,
      legend: { x: 0.02, y: 0.98, bgcolor: "rgba(255,255,255,0.7)" },
      annotations: [
        {
          xref: "paper",
          yref: "paper",
          x: 0.98,
          y: 0.04,
          xanchor: "right",
          yanchor: "bottom",
          showarrow: false,
          align: "right",
          bgcolor: "rgba(255,255,255,0.85)",
          bordercolor: "rgba(0,0,0,0.1)",
          borderwidth: 1,
          font: { size: 11, color: "#1e293b" },
          text:
            `Pearson r = ${(m.pearson_r ?? 0).toFixed(2)}<br>` +
            `Spearman ρ = ${(m.spearman_rho ?? 0).toFixed(2)}<br>` +
            `R² = ${(m.r_squared ?? 0).toFixed(3)} (n=${rows.length})`,
        },
      ],
      height: 540,
    };

    Plotly.newPlot(el, [points, fit], layout, {
      displayModeBar: false,
      responsive: true,
    });
  }

  if (payload.geojson) {
    renderPowiatIntensityMap(payload.geojson);
    renderPowiatMap(payload.geojson);
    renderPowiatScatter();
  }
})();
