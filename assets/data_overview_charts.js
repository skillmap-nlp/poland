(function () {
  const payload = window.__DATA_OVERVIEW__;
  const T = window.__CHART_THEME__;
  if (!payload || !window.Plotly || !T) return;

  const fmtInt = (v) =>
    new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(v);

  const plotConfig = T.plotConfig;

  function horizontalBars(el, rows, opts) {
    if (!el) return;
    const labels = rows.map((r) =>
      (r.month || r.quarter || String(r.year)).slice(0, 3)
    );
    const values = rows.map((r) => r.value ?? r.services ?? r.pracuj_flow);
    const xmax = Math.max(...values, 1);
    const mom = rows.map((r) =>
      r.mom_pct == null ? "—" : `${r.mom_pct >= 0 ? "+" : ""}${r.mom_pct}%`
    );

    const track = {
      type: "bar",
      orientation: "h",
      y: labels,
      x: labels.map(() => xmax),
      marker: { color: T.track },
      hoverinfo: "skip",
      showlegend: false,
    };
    const bars = {
      type: "bar",
      orientation: "h",
      y: labels,
      x: values,
      marker: { color: opts.color },
      customdata: mom,
      hovertemplate:
        opts.hoverTemplate ||
        `<b>%{y}</b><br>${opts.valueLabel}: %{x:,}<br>MoM: %{customdata}<extra></extra>`,
      showlegend: false,
    };

    const layout = {
      ...T.baseLayout(),
      xaxis: {
        range: [0, xmax * 1.12],
        showgrid: false,
        zeroline: false,
        tickformat: ",.0f",
        tickfont: { color: T.muted },
      },
      yaxis: {
        autorange: "reversed",
        tickfont: { color: T.navy, size: 11 },
      },
      barmode: "overlay",
      showlegend: false,
      height: opts.height || 420,
    };

    Plotly.newPlot(el, [track, bars], layout, plotConfig);
  }

  function renderMonthlyVacancies() {
    const rows = payload.monthly.vacancies;
    horizontalBars(document.getElementById("chart-monthly-vacancies"), rows, {
      color: T.demand,
      valueLabel: "Estimated vacancies",
      hoverTemplate:
        "<b>%{y}</b><br>Estimated vacancies: %{x:,}<br>MoM: %{customdata}<extra></extra>",
      height: 400,
    });
  }

  function renderMonthlyBur() {
    const rows = payload.monthly.bur;
    horizontalBars(document.getElementById("chart-monthly-bur"), rows, {
      color: T.supply,
      valueLabel: "Training services",
      hoverTemplate:
        "<b>%{y}</b><br>Training services: %{x:,}<br>MoM: %{customdata}<extra></extra>",
      height: 400,
    });
  }

  function renderBurYearly() {
    const el = document.getElementById("chart-bur-yearly");
    if (!el) return;
    const rows = payload.bur_yearly;
    const years = rows.map((r) => String(r.year));
    const values = rows.map((r) => r.services);

    Plotly.newPlot(
      el,
      [
        {
          type: "bar",
          x: years,
          y: values,
          marker: { color: T.supply },
          customdata: rows.map((r) => [r.yoy_pct]),
          hovertemplate:
            "<b>%{x}</b><br>Services: %{y:,}<br>YoY: %{customdata[0]}%<extra></extra>",
        },
      ],
      {
        ...T.baseLayout(),
        xaxis: { tickfont: { color: T.navy } },
        yaxis: {
          tickformat: ",.0f",
          gridcolor: T.grid,
          zeroline: false,
        },
        height: 280,
        margin: { l: 56, r: 16, t: 8, b: 40 },
      },
      plotConfig
    );
  }

  function renderQuarterlyGus() {
    const el = document.getElementById("chart-quarterly-gus");
    if (!el) return;
    const rows = payload.quarterly_gus;
    const quarters = rows.map((r) => r.quarter);

    Plotly.newPlot(
      el,
      [
        {
          type: "bar",
          orientation: "h",
          name: "Pracuj.pl flow",
          y: quarters,
          x: rows.map((r) => r.pracuj_flow),
          marker: { color: T.demand },
          hovertemplate:
            "<b>%{y}</b><br>Pracuj.pl flow: %{x:,}<br>Ratio vs GUS: %{customdata:.2f}×<extra></extra>",
          customdata: rows.map((r) => r.ratio),
        },
        {
          type: "bar",
          orientation: "h",
          name: "GUS stock (EoQ)",
          y: quarters,
          x: rows.map((r) => r.gus_stock_eoq),
          marker: { color: T.gus },
          hovertemplate:
            "<b>%{y}</b><br>GUS stock (EoQ): %{x:,}<extra></extra>",
        },
      ],
      {
        ...T.baseLayout(),
        barmode: "group",
        xaxis: {
          tickformat: ",.0f",
          showgrid: true,
          gridcolor: T.grid,
        },
        yaxis: { autorange: "reversed", tickfont: { color: T.navy } },
        legend: {
          orientation: "h",
          y: 1.08,
          x: 0,
          bgcolor: "rgba(0,0,0,0)",
        },
        height: 300,
        margin: { l: 56, r: 16, t: 8, b: 32 },
      },
      plotConfig
    );

    const note = document.getElementById("chart-quarterly-gus-note");
    if (note) {
      const totalFlow = rows.reduce((s, r) => s + r.pracuj_flow, 0);
      const totalStock = rows.reduce((s, r) => s + r.gus_stock_eoq, 0);
      note.textContent = `Pracuj.pl flow total 2025: ${fmtInt(
        totalFlow
      )}; GUS stock sum of quarter-ends: ${fmtInt(
        totalStock
      )}. Flow/stock ratio averages ~3.2× across quarters.`;
    }
  }

  function renderMonthlyOffersToggle() {
    const el = document.getElementById("chart-monthly-offers");
    if (!el) return;
    const offers = payload.monthly.offers;
    const vacancies = payload.monthly.vacancies;

    const traces = [
      {
        type: "bar",
        x: offers.map((r) => r.month.slice(0, 3)),
        y: offers.map((r) => r.value),
        name: "Job offers (OJP)",
        marker: { color: T.neutral },
        visible: false,
        hovertemplate: "<b>%{x}</b><br>Offers: %{y:,}<extra></extra>",
      },
      {
        type: "bar",
        x: vacancies.map((r) => r.month.slice(0, 3)),
        y: vacancies.map((r) => r.value),
        name: "Est. vacancies (OJV)",
        marker: { color: T.demand },
        hovertemplate: "<b>%{x}</b><br>Vacancies: %{y:,}<extra></extra>",
      },
    ];

    Plotly.newPlot(
      el,
      traces,
      {
        ...T.baseLayout(),
        xaxis: { tickangle: -35 },
        yaxis: { tickformat: ",.0f", gridcolor: T.grid },
        updatemenus: [
          {
            type: "buttons",
            direction: "right",
            x: 0,
            y: 1.08,
            xanchor: "left",
            yanchor: "top",
            buttons: [
              {
                label: "Estimated vacancies",
                method: "update",
                args: [{ visible: [false, true] }],
              },
              {
                label: "Job offers",
                method: "update",
                args: [{ visible: [true, false] }],
              },
            ],
          },
        ],
        showlegend: false,
        height: 280,
        margin: { l: 56, r: 16, t: 8, b: 40 },
      },
      plotConfig
    );
  }

  renderMonthlyVacancies();
  renderMonthlyBur();
  renderBurYearly();
  renderQuarterlyGus();
  renderMonthlyOffersToggle();
})();
