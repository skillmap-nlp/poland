(function () {
  const payload = window.__RESULTS_EXTENDED__;
  const T = window.__CHART_THEME__;
  if (!payload || !window.Plotly || !T) return;

  const plotConfig = T.plotConfig;

  function plot(elId, traces, layout) {
    const el = document.getElementById(elId);
    if (!el) return;
    Plotly.newPlot(el, traces, { ...T.baseLayout(), ...layout }, plotConfig);
  }

  function renderDurationYearly() {
    const rows = payload.duration.yearly;
    plot("chart-duration-yearly", [
      {
        type: "scatter",
        mode: "lines+markers",
        name: "Median",
        x: rows.map((r) => r.year),
        y: rows.map((r) => r.median),
        line: { color: T.navy, width: 2.5 },
        marker: { size: 7 },
        hovertemplate: "Year %{x}<br>Median: %{y:.0f} h<extra></extra>",
      },
      {
        type: "scatter",
        mode: "lines",
        name: "Mean",
        x: rows.map((r) => r.year),
        y: rows.map((r) => r.mean),
        line: { color: T.demand, width: 2, dash: "dot" },
        hovertemplate: "Year %{x}<br>Mean: %{y:.0f} h<extra></extra>",
      },
      {
        type: "scatter",
        mode: "lines",
        name: "90th percentile",
        x: rows.map((r) => r.year),
        y: rows.map((r) => r.p90),
        line: { color: T.supply, width: 1.5, dash: "dash" },
        hovertemplate: "Year %{x}<br>P90: %{y:.0f} h<extra></extra>",
      },
    ], {
      margin: { l: 48, r: 16, t: 8, b: 40 },
      height: 340,
      xaxis: { tickmode: "linear", dtick: 1, gridcolor: T.grid },
      yaxis: { title: "Hours", gridcolor: T.grid },
      legend: { orientation: "h", y: 1.08, x: 0 },
    });
  }

  function renderDurationBuckets() {
    const rows = payload.duration.buckets_2025;
    plot("chart-duration-buckets", [
      {
        type: "bar",
        x: rows.map((r) => r.bucket),
        y: rows.map((r) => r.pct),
        marker: { color: T.demand },
        hovertemplate: "%{x}<br>%{y:.1f}% of trainings<extra></extra>",
      },
    ], {
      margin: { l: 48, r: 16, t: 8, b: 72 },
      height: 320,
      xaxis: { tickangle: -35 },
      yaxis: { ticksuffix: "%", gridcolor: T.grid },
    });
  }

  function renderDurationCategory() {
    const rows = payload.duration.by_category_2025.slice().reverse();
    plot("chart-duration-category", [
      {
        type: "bar",
        orientation: "h",
        y: rows.map((r) => r.category),
        x: rows.map((r) => r.median),
        marker: { color: T.supply },
        customdata: rows.map((r) => [r.mean, r.n]),
        hovertemplate:
          "<b>%{y}</b><br>Median: %{x:.0f} h<br>Mean: %{customdata[0]:.0f} h<br>n=%{customdata[1]:,}<extra></extra>",
      },
    ], {
      margin: { l: 220, r: 16, t: 8, b: 36 },
      height: 380,
      xaxis: { title: "Median hours", gridcolor: T.grid },
      yaxis: { tickfont: { size: 11 } },
    });
  }

  function renderMismatchOverview() {
    const rows = payload.mismatch.skills_s1_s8;
    const labels = rows.map((r) => r.label || r.title);
    plot("chart-mismatch-s1s8-overview", [
      {
        type: "bar",
        orientation: "h",
        name: "Demand",
        y: labels,
        x: rows.map((r) => r.demand_pct),
        marker: { color: T.demand },
        hovertemplate: "<b>%{y}</b><br>Demand: %{x:.1f}%<extra></extra>",
      },
      {
        type: "bar",
        orientation: "h",
        name: "Supply",
        y: labels,
        x: rows.map((r) => r.supply_pct),
        marker: { color: T.supply },
        hovertemplate: "<b>%{y}</b><br>Supply: %{x:.1f}%<extra></extra>",
      },
    ], {
      barmode: "group",
      margin: { l: 280, r: 16, t: 8, b: 36 },
      height: 420,
      xaxis: { ticksuffix: "%", gridcolor: T.grid },
      yaxis: { autorange: "reversed", tickfont: { size: 11 } },
      legend: { orientation: "h", y: 1.06, x: 0 },
    });
  }

  function renderMismatchGap() {
    const rows = payload.mismatch.skills_s1_s8
      .slice()
      .sort((a, b) => b.gap_pp - a.gap_pp);
    const labels = rows.map((r) => r.label || r.title);
    const colors = rows.map((r) => (r.gap_pp >= 0 ? T.negative : T.positive));
    plot("chart-mismatch-s1s8-gap", [
      {
        type: "bar",
        orientation: "h",
        y: labels,
        x: rows.map((r) => r.gap_pp),
        marker: { color: colors },
        customdata: rows.map((r) => [
          r.code,
          Math.abs(r.gap_pp),
          r.gap_pp >= 0 ? "Demand exceeds supply" : "Supply exceeds demand",
        ]),
        hovertemplate:
          "<b>%{y}</b> (%{customdata[0]})<br>" +
          "%{customdata[2]}: %{customdata[1]:.1f} pp<extra></extra>",
      },
    ], {
      margin: { l: 220, r: 16, t: 8, b: 36 },
      height: 340,
      xaxis: {
        title: "Demand minus supply (pp)",
        zeroline: true,
        zerolinecolor: T.navy,
        gridcolor: T.grid,
      },
      yaxis: { autorange: "reversed" },
    });
  }

  function renderMismatchL2() {
    const under = payload.mismatch.l2_top.under_supplied.slice().reverse();
    const over = payload.mismatch.l2_top.over_supplied.slice().reverse();
    plot("chart-mismatch-l2-under", [
      {
        type: "bar",
        orientation: "h",
        y: under.map((r) => r.title),
        x: under.map((r) => Math.abs(r.gap_pp)),
        marker: { color: T.negative },
        customdata: under.map((r) => r.gap_pp),
        hovertemplate:
          "<b>%{y}</b><br>Demand exceeds supply: %{x:.1f} pp" +
          "<br>Signed gap (demand − supply): %{customdata:+.1f} pp<extra></extra>",
      },
    ], {
      margin: { l: 260, r: 8, t: 8, b: 36 },
      height: 320,
      xaxis: { title: "|Demand − supply| (pp)", gridcolor: T.grid },
      yaxis: { tickfont: { size: 10 } },
    });
    plot("chart-mismatch-l2-over", [
      {
        type: "bar",
        orientation: "h",
        y: over.map((r) => r.title),
        x: over.map((r) => Math.abs(r.gap_pp)),
        marker: { color: T.positive },
        customdata: over.map((r) => r.gap_pp),
        hovertemplate:
          "<b>%{y}</b><br>Supply exceeds demand: %{x:.1f} pp" +
          "<br>Signed gap (demand − supply): %{customdata:+.1f} pp<extra></extra>",
      },
    ], {
      margin: { l: 260, r: 8, t: 8, b: 36 },
      height: 320,
      xaxis: { title: "|Demand − supply| (pp)", gridcolor: T.grid },
      yaxis: { tickfont: { size: 10 } },
    });
  }

  function renderAiNace() {
    const rows = payload.ai_nace_sections.slice(0, 10);
    plot("chart-ai-nace-sections", [
      {
        type: "bar",
        orientation: "h",
        y: rows.map((r) => r.label),
        x: rows.map((r) => r.pct),
        marker: { color: T.demand },
        customdata: rows.map((r) => r.value),
        hovertemplate:
          "<b>%{y}</b><br>%{x:.1f}% of AI offers<br>%{customdata:,} offers<extra></extra>",
      },
    ], {
      margin: { l: 260, r: 16, t: 8, b: 36 },
      height: 360,
      xaxis: { ticksuffix: "%", gridcolor: T.grid },
      yaxis: { autorange: "reversed", tickfont: { size: 11 } },
    });
  }

  function renderGreenNace() {
    const rows = payload.green_nace_sections;
    plot("chart-green-nace-sections", [
      {
        type: "bar",
        orientation: "h",
        y: rows.map((r) => r.label),
        x: rows.map((r) => r.pct),
        marker: { color: T.positive },
        customdata: rows.map((r) => r.value),
        hovertemplate:
          "<b>%{y}</b><br>%{x:.1f}% of section offers<br>%{customdata:,} green offers<extra></extra>",
      },
    ], {
      margin: { l: 260, r: 16, t: 8, b: 36 },
      height: 400,
      xaxis: { title: "Green share within NACE section (%)", gridcolor: T.grid },
      yaxis: { autorange: "reversed", tickfont: { size: 11 } },
    });
  }

  function renderCareBurShare() {
    const rows = payload.care.bur_public_health_share;
    plot("chart-care-bur-ph-share", [
      {
        type: "scatter",
        mode: "lines+markers",
        x: rows.map((r) => r.year),
        y: rows.map((r) => r.share_pct),
        line: { color: T.navy, width: 2.5 },
        marker: { size: 7 },
        customdata: rows.map((r) => r.trainings),
        hovertemplate:
          "Year %{x}<br>Share: %{y:.2f}%<br>Trainings: %{customdata:,}<extra></extra>",
      },
    ], {
      margin: { l: 48, r: 16, t: 8, b: 40 },
      height: 300,
      xaxis: { tickmode: "linear", dtick: 1, gridcolor: T.grid },
      yaxis: { ticksuffix: "%", gridcolor: T.grid },
    });
  }

  function renderCareOccupations() {
    const rows = payload.care.top_occupations.slice().reverse();
    plot("chart-care-top-occupations", [
      {
        type: "bar",
        orientation: "h",
        y: rows.map((r) => r.label),
        x: rows.map((r) => r.value),
        marker: { color: T.demand },
        hovertemplate: "<b>%{y}</b><br>%{x:,} offers<extra></extra>",
      },
    ], {
      margin: { l: 240, r: 16, t: 8, b: 36 },
      height: 420,
      xaxis: { gridcolor: T.grid },
      yaxis: { tickfont: { size: 11 } },
    });
  }

  function renderCarePhS1s8() {
    const rows = payload.care.public_health_s1s8
      .slice()
      .sort((a, b) => b.share_pct - a.share_pct);
    const labels = rows.map(
      (r) => r.label || `${r.code} · ${r.title}`
    );
    plot("chart-care-ph-s1s8", [
      {
        type: "bar",
        orientation: "h",
        y: labels,
        x: rows.map((r) => r.share_pct),
        marker: { color: T.supply },
        customdata: rows.map((r) => r.code),
        hovertemplate:
          "<b>%{y}</b> (%{customdata})<br>Share: %{x:.1f}%<extra></extra>",
      },
    ], {
      margin: { l: 300, r: 16, t: 8, b: 36 },
      height: Math.max(280, rows.length * 44 + 48),
      xaxis: { ticksuffix: "%", range: [0, 100], gridcolor: T.grid },
      yaxis: { autorange: "reversed", tickfont: { size: 11 } },
    });
  }

  function renderMismatchFamily() {
    const rows = payload.mismatch.by_family;
    plot("chart-mismatch-family", [
      {
        type: "bar",
        name: "Demand",
        x: rows.map((r) => r.family),
        y: rows.map((r) => r.demand_pct),
        marker: { color: T.demand },
        hovertemplate: "<b>%{x}</b><br>Demand: %{y:.1f}%<extra></extra>",
      },
      {
        type: "bar",
        name: "Supply",
        x: rows.map((r) => r.family),
        y: rows.map((r) => r.supply_pct),
        marker: { color: T.supply },
        hovertemplate: "<b>%{x}</b><br>Supply: %{y:.1f}%<extra></extra>",
      },
    ], {
      barmode: "group",
      margin: { l: 48, r: 16, t: 8, b: 100 },
      height: 360,
      xaxis: { tickangle: -25 },
      yaxis: { ticksuffix: "%", gridcolor: T.grid },
      legend: { orientation: "h", y: 1.08, x: 0 },
    });
  }

  function renderMismatchPillar(elId, rows, opts = {}) {
    const sorted = opts.preserveOrder
      ? rows.slice()
      : rows.slice().sort((a, b) => b.demand_pct - a.demand_pct);
    const labels = sorted.map((r) => r.label || r.title);
    const leftMargin = opts.wideLabels ? 300 : 220;
    plot(elId, [
      {
        type: "bar",
        orientation: "h",
        name: "Demand",
        y: labels,
        x: sorted.map((r) => r.demand_pct),
        marker: { color: T.demand },
        customdata: sorted.map((r) => r.code),
        hovertemplate:
          "<b>%{y}</b> (%{customdata})<br>Demand: %{x:.1f}% of pillar mentions<extra></extra>",
      },
      {
        type: "bar",
        orientation: "h",
        name: "Supply",
        y: labels,
        x: sorted.map((r) => r.supply_pct),
        marker: { color: T.supply },
        customdata: sorted.map((r) => r.code),
        hovertemplate:
          "<b>%{y}</b> (%{customdata})<br>Supply: %{x:.1f}% of pillar trainings<extra></extra>",
      },
    ], {
      barmode: "group",
      margin: { l: leftMargin, r: 16, t: 8, b: 36 },
      height: opts.height || 360,
      xaxis: {
        ticksuffix: "%",
        gridcolor: T.grid,
        title: { text: "Share within pillar (each side sums to 100%)" },
      },
      yaxis: { autorange: "reversed", tickfont: { size: 11 } },
      legend: { orientation: "h", y: 1.06, x: 0 },
    });
  }

  function renderTrainingChange() {
    const rows = payload.training_change_2019_2025
      .filter((r) => r.change_pct !== null)
      .sort((a, b) => a.change_pct - b.change_pct);
    plot("chart-training-change-2019-2025", [
      {
        type: "bar",
        orientation: "h",
        y: rows.map((r) => r.label),
        x: rows.map((r) => r.change_pct),
        marker: {
          color: rows.map((r) => (r.change_pct >= 0 ? T.positive : T.negative)),
        },
        customdata: rows.map((r) => [r.n_2019, r.n_2025]),
        hovertemplate:
          "<b>%{y}</b><br>2019: %{customdata[0]:,}<br>2025: %{customdata[1]:,}<br>Change: %{x:+.1f}%<extra></extra>",
      },
    ], {
      margin: { l: 160, r: 16, t: 8, b: 36 },
      height: 480,
      xaxis: { title: "Change in training services (%)", zeroline: true, gridcolor: T.grid },
      yaxis: { tickfont: { size: 11 } },
    });
  }

  function renderAiDivisions() {
    const rows = payload.ai_nace_divisions.slice().reverse();
    plot("chart-ai-nace-divisions", [
      {
        type: "bar",
        orientation: "h",
        y: rows.map((r) => r.label),
        x: rows.map((r) => r.pct),
        marker: { color: T.demand },
        customdata: rows.map((r) => r.value),
        hovertemplate:
          "<b>%{y}</b><br>%{x:.1f}% of AI offers<br>%{customdata:,} offers<extra></extra>",
      },
    ], {
      margin: { l: 300, r: 16, t: 8, b: 36 },
      height: 420,
      xaxis: { ticksuffix: "%", gridcolor: T.grid },
      yaxis: { tickfont: { size: 10 } },
    });
  }

  function renderAiTransversal() {
    const rows = payload.ai_transversal_groups;
    plot("chart-ai-transversal", [
      {
        type: "bar",
        orientation: "h",
        y: rows.map((r) => r.label),
        x: rows.map((r) => r.pct),
        marker: { color: T.demand },
        customdata: rows.map((r) => r.offers),
        hovertemplate: "<b>%{y}</b><br>%{x:.1f}% of AI offers with T-skills<br>n=%{customdata:,}<extra></extra>",
      },
    ], {
      margin: { l: 260, r: 16, t: 8, b: 36 },
      height: 340,
      xaxis: { ticksuffix: "%", gridcolor: T.grid },
      yaxis: { autorange: "reversed", tickfont: { size: 11 } },
    });
  }

  function renderUkrNace() {
    const UKR_POS = "#1d6fa8";
    const UKR_NEG = "#cf5c4f";
    const SHARE_UA_X = 0.8;
    const SHARE_OTHER_X = 0.96;
    const rows = payload.ukr_nace_sections
      .slice()
      .sort((a, b) => b.diff_pp - a.diff_pp);
    const labels = rows.map((r) => r.chart_label || `${r.code}  ·  ${r.label}`);
    const diffs = rows.map((r) => r.diff_pp);
    const colors = diffs.map((d) =>
      d > 0 ? UKR_POS : d < 0 ? UKR_NEG : T.muted
    );
    const absMax = Math.max(...diffs.map((d) => Math.abs(d)), 1);
    const labelPad = absMax * 0.06;

    const ppAnnotations = rows.map((r, i) => {
      const d = r.diff_pp;
      const color = d > 0 ? UKR_POS : d < 0 ? UKR_NEG : T.muted;
      return {
        x: d >= 0 ? d + labelPad : d - labelPad,
        y: labels[i],
        xref: "x",
        yref: "y",
        text: `${d > 0 ? "+" : ""}${d.toFixed(1)} pp`,
        showarrow: false,
        xanchor: d >= 0 ? "left" : "right",
        font: { size: 10, color, family: T.font },
      };
    });

    const shareHeader = [
      {
        x: (SHARE_UA_X + SHARE_OTHER_X) / 2,
        y: 1.045,
        xref: "paper",
        yref: "paper",
        text: "<b>Share of segment</b>",
        showarrow: false,
        xanchor: "center",
        font: { size: 10, color: "#6B7785" },
      },
      {
        x: SHARE_UA_X,
        y: 1.012,
        xref: "paper",
        yref: "paper",
        text: "UA-friendly",
        showarrow: false,
        xanchor: "right",
        font: { size: 9, color: "#94A0AD" },
      },
      {
        x: SHARE_OTHER_X,
        y: 1.012,
        xref: "paper",
        yref: "paper",
        text: "Other",
        showarrow: false,
        xanchor: "right",
        font: { size: 9, color: "#94A0AD" },
      },
    ];

    const shareRows = rows.flatMap((r, i) => [
      {
        x: SHARE_UA_X,
        y: labels[i],
        xref: "paper",
        yref: "y",
        text: `${r.ukr_pct.toFixed(1)}%`,
        showarrow: false,
        xanchor: "right",
        font: { size: 10, color: "#6B7785", family: "ui-monospace, monospace" },
      },
      {
        x: SHARE_OTHER_X,
        y: labels[i],
        xref: "paper",
        yref: "y",
        text: `${r.other_pct.toFixed(1)}%`,
        showarrow: false,
        xanchor: "right",
        font: { size: 10, color: "#6B7785", family: "ui-monospace, monospace" },
      },
    ]);

    plot("chart-ukr-nace-sections", [
      {
        type: "bar",
        orientation: "h",
        y: labels,
        x: diffs,
        marker: { color: colors },
        customdata: rows.map((r) => [r.code, r.ukr_pct, r.other_pct]),
        hovertemplate:
          "<b>%{y}</b><br>" +
          "Gap (UA-friendly − other): %{x:+.1f} pp<br>" +
          "UA-friendly share: %{customdata[1]:.1f}%<br>" +
          "Other postings share: %{customdata[2]:.1f}%<extra></extra>",
      },
    ], {
      margin: { l: 360, r: 28, t: 52, b: 56 },
      height: Math.max(560, rows.length * 34 + 96),
      xaxis: {
        domain: [0, 0.74],
        title: "Percentage-point gap (UA-friendly minus other postings)",
        range: [-absMax * 1.28, absMax * 1.12],
        zeroline: true,
        zerolinecolor: "#cbd5e1",
        tickformat: "+.0f",
        ticksuffix: " pp",
        gridcolor: T.grid,
      },
      yaxis: {
        domain: [0.06, 0.98],
        autorange: "reversed",
        tickfont: { size: 11 },
      },
      showlegend: false,
      annotations: [
        ...shareHeader,
        ...ppAnnotations,
        ...shareRows,
        {
          x: 0.01,
          y: -0.12,
          xref: "paper",
          yref: "paper",
          text: "<b>← under-represented vs other postings</b>",
          showarrow: false,
          font: { size: 10, color: UKR_NEG },
        },
        {
          x: 0.72,
          y: -0.12,
          xref: "paper",
          yref: "paper",
          text: "<b>over-represented vs other postings →</b>",
          showarrow: false,
          xanchor: "right",
          font: { size: 10, color: UKR_POS },
        },
      ],
    });
  }

  function renderCareBar(elId, rows, valueKey, pctKey, color) {
    const sorted = rows.slice().reverse();
    plot(elId, [
      {
        type: "bar",
        orientation: "h",
        y: sorted.map((r) => r.label),
        x: sorted.map((r) => r[pctKey] || r[valueKey]),
        marker: { color },
        customdata: sorted.map((r) => r.value),
        hovertemplate:
          pctKey
            ? "<b>%{y}</b><br>%{x:.1f}% of care offers<br>%{customdata:,} offers<extra></extra>"
            : "<b>%{y}</b><br>%{x:,}<extra></extra>",
      },
    ], {
      margin: { l: 260, r: 16, t: 8, b: 36 },
      height: 360,
      xaxis: { gridcolor: T.grid },
      yaxis: { tickfont: { size: 10 } },
    });
  }

  function renderCareS1s8Compare() {
    const rows = payload.care.s1s8_vs_health;
    plot("chart-care-s1s8-compare", [
      {
        type: "bar",
        name: "Care services (KZiS)",
        x: rows.map((r) => r.code),
        y: rows.map((r) => r.care_share_pct),
        marker: { color: T.demand },
        customdata: rows.map((r) => r.title),
        hovertemplate: "<b>%{x}</b> %{customdata}<br>Care: %{y:.1f}%<extra></extra>",
      },
      {
        type: "bar",
        name: "NACE R86 healthcare",
        x: rows.map((r) => r.code),
        y: rows.map((r) => r.health_share_pct),
        marker: { color: T.supply },
        customdata: rows.map((r) => r.title),
        hovertemplate: "<b>%{x}</b> %{customdata}<br>Healthcare: %{y:.1f}%<extra></extra>",
      },
    ], {
      barmode: "group",
      margin: { l: 48, r: 16, t: 8, b: 40 },
      height: 320,
      yaxis: { ticksuffix: "%", gridcolor: T.grid },
      legend: { orientation: "h", y: 1.08, x: 0 },
    });
  }

  function renderPhRegions() {
    const rows = payload.care.public_health_regions
      .filter((r) => r.label.toLowerCase() !== "unspecified")
      .slice()
      .sort((a, b) => b.value - a.value)
      .reverse();
    plot("chart-ph-regions", [
      {
        type: "bar",
        orientation: "h",
        y: rows.map((r) => r.label),
        x: rows.map((r) => r.value),
        marker: { color: T.supply },
        customdata: rows.map((r) => r.pct),
        hovertemplate: "<b>%{y}</b><br>%{x:,} trainings (%{customdata:.1f}%)<extra></extra>",
      },
    ], {
      margin: { l: 180, r: 16, t: 8, b: 36 },
      height: 360,
      xaxis: { gridcolor: T.grid },
    });
  }

  function renderPhModality() {
    const rows = payload.care.public_health_modality
      .slice()
      .sort((a, b) => b.pct - a.pct);
    plot("chart-ph-modality", [
      {
        type: "bar",
        orientation: "h",
        y: rows.map((r) => r.label),
        x: rows.map((r) => r.pct),
        marker: { color: T.demand },
        customdata: rows.map((r) => r.value),
        hovertemplate:
          "<b>%{y}</b><br>Share: %{x:.1f}%<br>Services: %{customdata:,}<extra></extra>",
      },
    ], {
      margin: { l: 280, r: 16, t: 8, b: 36 },
      height: Math.max(260, rows.length * 44 + 48),
      xaxis: { ticksuffix: "%", range: [0, 100], gridcolor: T.grid },
      yaxis: { autorange: "reversed", tickfont: { size: 11 } },
    });
  }

  function renderPhDuration() {
    const rows = payload.care.public_health_duration;
    plot("chart-ph-duration", [
      {
        type: "bar",
        x: rows.map((r) => r.label),
        y: rows.map((r) => r.pct),
        marker: { color: T.demand },
        hovertemplate: "<b>%{x}</b><br>%{y:.1f}%<extra></extra>",
      },
    ], {
      margin: { l: 48, r: 16, t: 8, b: 40 },
      height: 260,
      yaxis: { ticksuffix: "%", gridcolor: T.grid },
    });
  }

  function renderDigitalExamples() {
    const el = document.getElementById("digital-examples-columns");
    if (!el || !payload.digital_examples) return;
    const titles = { basic: "Basic", intermediate: "Intermediate", advanced: "Advanced" };
    el.innerHTML = Object.entries(payload.digital_examples)
      .map(
        ([level, skills]) => `
        <div class="digital-examples-col">
          <h4>${titles[level] || level}</h4>
          <ul>${skills.map((s) => `<li>${s}</li>`).join("")}</ul>
        </div>`
      )
      .join("");
  }

  renderDigitalExamples();
  renderDurationYearly();
  renderDurationBuckets();
  renderDurationCategory();
  renderTrainingChange();
  renderMismatchFamily();
  renderMismatchOverview();
  renderMismatchGap();
  renderMismatchPillar("chart-mismatch-transversal", payload.mismatch.transversal, {
    preserveOrder: true,
    wideLabels: true,
  });
  renderMismatchPillar("chart-mismatch-knowledge", payload.mismatch.knowledge, {
    preserveOrder: true,
    wideLabels: true,
    height: 420,
  });
  renderMismatchPillar("chart-mismatch-languages", payload.mismatch.languages, {
    preserveOrder: true,
  });
  renderMismatchL2();
  renderAiNace();
  renderAiDivisions();
  renderAiTransversal();
  renderGreenNace();
  renderUkrNace();
  renderCareBurShare();
  renderCareOccupations();
  renderCareBar("chart-care-top-skills", payload.care.top_skills, "value", "pct", T.demand);
  renderCareBar("chart-care-top-knowledge", payload.care.top_knowledge, "value", "pct", T.demand);
  renderCareBar("chart-care-top-transversal", payload.care.top_transversal, "value", "pct", T.demand);
  renderCareS1s8Compare();
  renderCarePhS1s8();
  renderPhRegions();
  renderPhModality();
  renderPhDuration();
  renderCareBar("chart-ph-top-skills", payload.care.public_health_top_skills, "value", "pct", T.supply);
})();
