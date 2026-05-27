(function () {
  const payload = window.__METHODOLOGY_CHARTS__;
  const T = window.__CHART_THEME__;
  if (!payload || !window.Plotly || !T) return;

  const plotConfig = T.plotConfig;

  function plot(elId, traces, layout) {
    const el = document.getElementById(elId);
    if (!el) return;
    Plotly.newPlot(el, traces, { ...T.baseLayout(), ...layout }, plotConfig);
  }

  function renderKzis() {
    const rows = payload.kzis_comparison.slice().sort(
      (a, b) => b.pracuj_share_pct - a.pracuj_share_pct
    );
    const labels = rows.map((r) => r.group);
    plot("chart-kzis-comparison", [
      {
        type: "bar",
        orientation: "h",
        name: "Pracuj.pl",
        y: labels,
        x: rows.map((r) => r.pracuj_share_pct),
        marker: { color: T.demand },
        hovertemplate: "<b>%{y}</b><br>Pracuj.pl: %{x:.1f}%<extra></extra>",
      },
      {
        type: "bar",
        orientation: "h",
        name: "MRPiPS / PUP",
        y: labels,
        x: rows.map((r) => r.pup_share_pct),
        marker: { color: T.pup },
        hovertemplate: "<b>%{y}</b><br>MRPiPS / PUP: %{x:.1f}%<extra></extra>",
      },
    ], {
      barmode: "group",
      margin: { l: 210, r: 16, t: 8, b: 36 },
      height: 380,
      xaxis: { ticksuffix: "%", gridcolor: T.grid },
      yaxis: { autorange: "reversed", tickfont: { size: 11 } },
      legend: { orientation: "h", y: 1.06, x: 0 },
    });
  }

  function renderProviders() {
    const rows = payload.provider_types;
    const labels = rows.map((r) => r.bucket);
    plot("chart-bur-providers", [
      {
        type: "bar",
        orientation: "h",
        name: "Trainings",
        y: labels,
        x: rows.map((r) => r.trainings),
        marker: { color: T.supply },
        customdata: rows.map((r) => r.trainings_pct),
        hovertemplate:
          "<b>%{y}</b><br>Trainings: %{x:,}<br>Share: %{customdata:.1f}%<extra></extra>",
      },
      {
        type: "bar",
        orientation: "h",
        name: "Providers",
        y: labels,
        x: rows.map((r) => r.providers),
        marker: { color: T.positive },
        customdata: rows.map((r) => r.providers_pct),
        hovertemplate:
          "<b>%{y}</b><br>Providers: %{x:,}<br>Share: %{customdata:.1f}%<extra></extra>",
      },
    ], {
      barmode: "group",
      margin: { l: 160, r: 16, t: 8, b: 36 },
      height: 280,
      xaxis: { tickformat: ",.0f", gridcolor: T.grid },
      yaxis: { autorange: "reversed" },
      legend: { orientation: "h", y: 1.1, x: 0 },
    });
  }

  function renderRecurrence() {
    const rows = payload.recurrence.years_distribution.filter((r) => r.years <= 6);
    plot("chart-bur-recurrence", [
      {
        type: "bar",
        x: rows.map((r) => String(r.years)),
        y: rows.map((r) => r.postings),
        marker: { color: T.demand },
        customdata: rows.map((r) => r.courses),
        hovertemplate:
          "Years on offer: %{x}<br>Postings: %{y:,}<br>Courses: %{customdata:,}<extra></extra>",
      },
    ], {
      margin: { l: 56, r: 16, t: 8, b: 40 },
      height: 280,
      xaxis: { title: { text: "Years on offer (2016–2025)" } },
      yaxis: { tickformat: ",.0f", gridcolor: T.grid },
    });
  }

  function renderQualifications() {
    const rows = payload.certificates.by_year.filter((r) => r.year <= 2023);
    plot("chart-bur-qualifications", [
      {
        type: "scatter",
        mode: "lines+markers",
        name: "Q1 vocational",
        x: rows.map((r) => r.year),
        y: rows.map((r) => r.q1_pct),
        line: { color: T.demand, width: 2 },
      },
      {
        type: "scatter",
        mode: "lines+markers",
        name: "Q2 public authority",
        x: rows.map((r) => r.year),
        y: rows.map((r) => r.q2_pct),
        line: { color: T.negative, width: 2 },
      },
      {
        type: "scatter",
        mode: "lines+markers",
        name: "Q3 position entitlements",
        x: rows.map((r) => r.year),
        y: rows.map((r) => r.q3_pct),
        line: { color: T.supply, width: 2 },
      },
      {
        type: "scatter",
        mode: "lines+markers",
        name: "Q4 international",
        x: rows.map((r) => r.year),
        y: rows.map((r) => r.q4_pct),
        line: { color: T.positive, width: 2 },
      },
    ], {
      margin: { l: 56, r: 16, t: 8, b: 40 },
      height: 300,
      xaxis: { dtick: 1, title: { text: "Year" } },
      yaxis: { ticksuffix: "%", gridcolor: T.grid, title: { text: "Share of trainings" } },
      legend: { orientation: "h", y: 1.14, x: 0, font: { size: 10 } },
    });
  }

  function renderDocuments2025() {
    const rows = payload.certificates.documents_2025;
    plot("chart-bur-documents-2025", [
      {
        type: "bar",
        orientation: "h",
        y: rows.map((r) => r.label),
        x: rows.map((r) => r.share_pct),
        marker: { color: [T.demand, T.slate] },
        customdata: rows.map((r) => r.n),
        hovertemplate: "<b>%{y}</b><br>Share: %{x:.1f}%<br>Count: %{customdata:,}<extra></extra>",
      },
    ], {
      margin: { l: 280, r: 16, t: 8, b: 36 },
      height: 240,
      xaxis: { ticksuffix: "%", gridcolor: T.grid, range: [0, 100] },
      yaxis: { autorange: "reversed", tickfont: { size: 11 } },
    });
  }

  function renderModality() {
    const rows = payload.modality_2025;
    plot("chart-bur-modality", [
      {
        type: "bar",
        orientation: "h",
        y: rows.map((r) => r.label),
        x: rows.map((r) => r.share_pct),
        marker: { color: [T.demand, T.supply, T.positive] },
        customdata: rows.map((r) => r.n),
        hovertemplate: "<b>%{y}</b><br>Share: %{x:.1f}%<br>Services: %{customdata:,}<extra></extra>",
      },
    ], {
      margin: { l: 130, r: 16, t: 8, b: 32 },
      height: 220,
      xaxis: { ticksuffix: "%", range: [0, 75], gridcolor: T.grid },
      yaxis: { autorange: "reversed" },
    });
  }

  function renderEscoSamples() {
    const el = document.getElementById("esco-sample-grid");
    if (!el) return;
    el.innerHTML = payload.esco_samples
      .map((s) => `<span class="esco-sample-tag">${s}</span>`)
      .join("");
  }

  function renderRecurrenceStats() {
    const m = payload.recurrence.meta;
    const fmt = (n) => new Intl.NumberFormat("en-US").format(n);
    const map = {
      "recur-unique-courses": fmt(m.unique_courses),
      "recur-recurring-courses": fmt(m.recurring_courses),
      "recur-recurring-postings": fmt(m.recurring_postings),
      "recur-2025": fmt(m.postings_2025_recurring),
    };
    Object.entries(map).forEach(([id, val]) => {
      const node = document.getElementById(id);
      if (node) node.textContent = val;
    });
  }

  renderKzis();
  renderProviders();
  renderRecurrence();
  renderQualifications();
  renderDocuments2025();
  renderModality();
  renderEscoSamples();
  renderRecurrenceStats();
})();
