(function () {
  const data = window.__GREEN_SKILLS__;
  const regionalPayload = window.__REGIONAL_REPORT__;
  const T = window.__CHART_THEME__;

  if (!data || !window.Plotly || !T) return;

  const geojson = regionalPayload ? regionalPayload.geojson : null;
  const meta = data.meta;

  const fmtInt = (v) =>
    new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(v);

  const titleVoiv = (row) =>
    row.voivodeship_en || T.voivodeshipLabel(row.voivodeship);

  /* ── KPI cards ── */
  function renderGreenCards() {
    const el = document.getElementById("green-kpi-cards");
    if (!el) return;
    el.innerHTML = [
      {
        label: "Offers with ≥1 green skill",
        value: fmtInt(meta.total_green_offers),
        subtext: `${meta.green_pct_national}% of all mapped offers`,
      },
      {
        label: "Genuine green skills matched",
        value: fmtInt(meta.genuine_green_count),
        subtext: `out of ~830 ESCO green skills`,
      },
      {
        label: "False positives excluded",
        value: fmtInt(meta.false_positive_count),
        subtext: "Skills flagged as non-green after manual review",
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

  /* ── Choropleth map ── */
  function renderGreenMap() {
    const el = document.getElementById("green-regional-map");
    if (!el || !geojson) return;

    const rows = data.voivodeships;
    const locations = rows.map((r) => r.voivodeship);
    const z = rows.map((r) => r.green_pct);
    const customdata = rows.map((r) => [
      fmtInt(r.green_offers),
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
      colorscale: T.scale.green,
      marker: T.mapMarker(),
      colorbar: {
        title: { text: "% offers<br>with green<br>skill" },
        thickness: 16,
        len: 0.7,
        x: 1.03,
        y: 0.5,
        outlinewidth: 0,
        ticksuffix: "%",
      },
      hovertemplate:
        "<b>%{customdata[2]}</b><br>" +
        "Green share: %{z:.1f}%<br>" +
        "Green offers: %{customdata[0]}<br>" +
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

  /* ── Top skills horizontal bar ── */
  function renderTopSkills() {
    const el = document.getElementById("green-top-skills-chart");
    if (!el) return;

    const skills = [...data.top_skills].slice(0, 25).reverse();

    const trace = {
      type: "bar",
      orientation: "h",
      x: skills.map((s) => s.offer_count),
      y: skills.map((s) => s.skill_en),
      marker: {
        color: T.positive,
        line: { width: 0 },
      },
      hovertemplate: "<b>%{y}</b><br>Offers: %{x:,}<extra></extra>",
    };

    const layout = {
      margin: { l: 280, r: 30, t: 10, b: 40 },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      xaxis: {
        title: { text: "Number of job offers", standoff: 6 },
        gridcolor: "rgba(0,0,0,0.06)",
        zeroline: false,
      },
      yaxis: {
        automargin: true,
        tickfont: { size: 11 },
      },
      height: 620,
      bargap: 0.25,
    };

    Plotly.newPlot(el, [trace], layout, {
      displayModeBar: false,
      responsive: true,
    });
  }

  /* ── Top occupations horizontal bar ── */
  function renderTopOccupations() {
    const el = document.getElementById("green-top-occupations-chart");
    if (!el) return;

    const occs = [...data.top_occupations].slice(0, 15).reverse();

    const trace = {
      type: "bar",
      orientation: "h",
      x: occs.map((o) => o.green_offers),
      y: occs.map((o) => o.kzis_occupation_en || o.kzis_occupation),
      marker: {
        color: T.positive,
        line: { width: 0 },
      },
      customdata: occs.map((o) => [o.avg_green_skills.toFixed(2)]),
      hovertemplate:
        "<b>%{y}</b><br>Offers with green skills: %{x:,}<br>Avg green skills per offer: %{customdata[0]}<extra></extra>",
    };

    const layout = {
      margin: { l: 360, r: 30, t: 10, b: 40 },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      xaxis: {
        title: { text: "Number of offers with green skills", standoff: 6 },
        gridcolor: "rgba(0,0,0,0.06)",
        zeroline: false,
      },
      yaxis: {
        automargin: true,
        tickfont: { size: 11 },
      },
      height: 500,
      bargap: 0.25,
    };

    Plotly.newPlot(el, [trace], layout, {
      displayModeBar: false,
      responsive: true,
    });
  }

  /* ── False positives table ── */
  function renderFalsePositives() {
    const el = document.getElementById("green-false-positives-list");
    if (!el) return;

    const fps = data.false_positives;
    const tableHtml = `
      <table class="data-table">
        <thead>
          <tr>
            <th>Skill (EN)</th>
            <th>Skill (PL)</th>
            <th class="num">Offer count</th>
          </tr>
        </thead>
        <tbody>
          ${fps
            .map(
              (r) => `
              <tr>
                <td>${r.skill_en}</td>
                <td>${r.skill_pl}</td>
                <td class="num">${fmtInt(r.offer_count)}</td>
              </tr>`
            )
            .join("")}
        </tbody>
      </table>`;
    el.innerHTML = tableHtml;
  }

  renderGreenCards();
  renderGreenMap();
  renderTopSkills();
  renderTopOccupations();
  renderFalsePositives();
})();
