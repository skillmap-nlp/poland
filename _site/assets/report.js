(function () {
  const payload = window.__REGIONAL_REPORT__;
  const T = window.__CHART_THEME__;

  if (!payload || !window.Plotly || !T) {
    return;
  }

  const rows = [...payload.rows];
  const meta = payload.meta;
  const geojson = payload.geojson;

  const fmtInt = (value) =>
    new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value);

  const fmtRate = (value) =>
    new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value);

  const titleVoiv = (row) =>
    T.voivodeshipLabel(row.voivodeship);

  const rowsOffer = [...rows].sort(
    (a, b) => b.offers_per_100k_lf - a.offers_per_100k_lf
  );
  const rowsTraining = [...rows].sort(
    (a, b) => b.trainings_per_100k_lf - a.trainings_per_100k_lf
  );
  const rowsGap = [...rows].sort(
    (a, b) =>
      b.offers_per_100k_lf -
      b.trainings_per_100k_lf -
      (a.offers_per_100k_lf - a.trainings_per_100k_lf)
  );

  const topOffer = rowsOffer[0];
  const topTraining = rowsTraining[0];
  const topGap = rowsGap[0];
  const tableColumns = [
    { key: "voivodeship", label: "Voivodeship", numeric: false },
    { key: "offers", label: "Job offers", numeric: true },
    { key: "offers_per_100k_lf", label: "Offers per 100k LF", numeric: true },
    { key: "trainings", label: "Trainings 2025", numeric: true },
    { key: "trainings_per_100k_lf", label: "Trainings 2025 per 100k LF", numeric: true },
  ];
  const sortState = {
    key: "offers_per_100k_lf",
    direction: "desc",
  };

  function renderCards() {
    const cardsEl = document.getElementById("summary-cards");
    cardsEl.innerHTML = [
      {
        label: "Online job postings",
        value: "~733k",
        subtext: "Pracuj.pl, 2025 (full portal coverage)",
      },
      {
        label: "Training services",
        value: "~131k",
        subtext: "Baza Usług Rozwojowych, 2025",
      },
      {
        label: "Highest demand intensity",
        value: titleVoiv(topOffer),
        subtext: `${fmtRate(topOffer.offers_per_100k_lf)} job offers per 100k labour force.`,
      },
      {
        label: "Highest supply intensity",
        value: titleVoiv(topTraining),
        subtext: `${fmtRate(
          topTraining.trainings_per_100k_lf
        )} trainings per 100k labour force.`,
      },
    ]
      .map(
        (card) => `
        <article class="card">
          <p class="label">${card.label}</p>
          <p class="value">${card.value}</p>
          <p class="subtext">${card.subtext}</p>
        </article>
      `
      )
      .join("");
  }

  function renderMap() {
    const locations = rows.map((row) => row.voivodeship);
    const customdata = rows.map((row) => [
      titleVoiv(row),
      fmtInt(row.offers),
      fmtInt(row.trainings),
      fmtInt(row.labour_force_2025_avg),
      `${row.offer_share_pct.toFixed(2)}%`,
      `${row.training_share_pct.toFixed(2)}%`,
    ]);

    const traces = [
      {
        type: "choropleth",
        geojson,
        featureidkey: "properties.nazwa",
        locations,
        z: rows.map((row) => row.offers_per_100k_lf),
        customdata,
        colorscale: T.scale.demand,
        marker: T.mapMarker(),
        colorbar: {
          title: { text: "Offers<br>per 100k LF" },
          thickness: 16,
          len: 0.7,
          x: 1.03,
          y: 0.5,
          outlinewidth: 0,
        },
        hovertemplate:
          "<b>%{customdata[0]}</b><br>" +
          "Job offers per 100k LF: %{z:.0f}<br>" +
          "Job offers: %{customdata[1]}<br>" +
          "Trainings 2025: %{customdata[2]}<br>" +
          "Labour force (avg. 2025): %{customdata[3]}<br>" +
          "National share of offers: %{customdata[4]}<extra></extra>",
        visible: true,
      },
      {
        type: "choropleth",
        geojson,
        featureidkey: "properties.nazwa",
        locations,
        z: rows.map((row) => row.trainings_per_100k_lf),
        customdata,
        colorscale: T.scale.supply,
        marker: T.mapMarker(),
        colorbar: {
          title: { text: "Trainings 2025<br>per 100k LF" },
          thickness: 16,
          len: 0.7,
          x: 1.03,
          y: 0.5,
          outlinewidth: 0,
        },
        hovertemplate:
          "<b>%{customdata[0]}</b><br>" +
          "Trainings 2025 per 100k LF: %{z:.0f}<br>" +
          "Trainings 2025: %{customdata[2]}<br>" +
          "Job offers: %{customdata[1]}<br>" +
          "Labour force (avg. 2025): %{customdata[3]}<br>" +
          "National share of trainings: %{customdata[5]}<extra></extra>",
        visible: false,
      },
    ];

    const layout = {
      margin: { l: 0, r: 12, t: 0, b: 0 },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      dragmode: false,
      showlegend: false,
      updatemenus: [
        {
          type: "buttons",
          direction: "left",
          x: 0,
          y: 1.12,
          xanchor: "left",
          yanchor: "top",
          showactive: true,
          bgcolor: T.track,
          bordercolor: "rgba(36, 56, 89, 0.12)",
          borderwidth: 1,
          pad: { r: 8, t: 0, b: 0, l: 0 },
          buttons: [
            {
              label: "Job offers per 100k LF",
              method: "update",
              args: [{ visible: [true, false] }],
            },
            {
              label: "Trainings 2025 per 100k LF",
              method: "update",
              args: [{ visible: [false, true] }],
            },
          ],
        },
      ],
      geo: {
        fitbounds: "locations",
        visible: false,
        projection: { type: "mercator" },
        bgcolor: "rgba(0,0,0,0)",
      },
    };

    Plotly.newPlot("regional-map", traces, layout, {
      displayModeBar: false,
      responsive: true,
    });

    document.getElementById("map-figure-title").textContent =
      "Figure 1. Relative labour demand and training supply across Polish voivodeships";
    document.getElementById("map-note").innerHTML = `
      <div class="figure-caption-source">
        Source: <a href="https://www.pracuj.pl/" target="_blank" rel="noopener noreferrer">Pracuj.pl</a>;
        <a href="https://uslugirozwojowe.parp.gov.pl/" target="_blank" rel="noopener noreferrer">Baza Usług Rozwojowych</a>;
        <a href="https://api.stat.gov.pl/Home/BdlApi?gt=&lang=en" target="_blank" rel="noopener noreferrer">GUS BDL API</a>.
      </div>
    `;
  }

  function renderHighlights() {
    document.getElementById(
      "highlights-copy"
    ).innerHTML = `<strong>${titleVoiv(topOffer)}</strong> leads demand intensity, while <strong>${titleVoiv(topTraining)}</strong> leads training intensity. The largest positive gap between job postings and training provision per 100,000 labour force is in <strong>${titleVoiv(topOffer)}</strong>.`;

    const buildRankList = (title, topRows, metricKey, metricLabel) => `
      <div class="rank-box">
        <h3>${title}</h3>
        <div class="rank-list">
          ${topRows
            .map(
              (row, idx) => `
                <div class="rank-item">
                  <div class="rank-badge">${idx + 1}</div>
                  <div class="rank-copy">
                    <div class="rank-name">${titleVoiv(row)}</div>
                    <div class="rank-metric">${fmtRate(
                  row[metricKey]
                )} ${metricLabel}</div>
                  </div>
                </div>
              `
            )
            .join("")}
        </div>
      </div>
    `;

    document.getElementById("highlights-grid").innerHTML =
      buildRankList(
        "Top 5 voivodeships by job-offer intensity",
        rowsOffer.slice(0, 5),
        "offers_per_100k_lf",
        "offers per 100k LF"
      ) +
      buildRankList(
        "Top 5 voivodeships by training intensity",
        rowsTraining.slice(0, 5),
        "trainings_per_100k_lf",
        "trainings per 100k LF"
      );
  }

  function renderTable() {
    const sortedRows = [...rows].sort((a, b) => {
      const { key, direction } = sortState;
      const dir = direction === "asc" ? 1 : -1;
      if (key === "voivodeship") {
        return titleVoiv(a).localeCompare(titleVoiv(b), "pl") * dir;
      }
      return ((a[key] || 0) - (b[key] || 0)) * dir;
    });

    const sortArrow = (columnKey) => {
      if (sortState.key !== columnKey) {
        return '<span class="sort-arrow muted">↕</span>';
      }
      return sortState.direction === "asc"
        ? '<span class="sort-arrow">↑</span>'
        : '<span class="sort-arrow">↓</span>';
    };

    const tableHtml = `
      <table class="data-table">
        <thead>
          <tr>
            ${tableColumns
              .map(
                (column) => `
                  <th
                    class="${column.numeric ? "num " : ""}sortable${
                      sortState.key === column.key ? " active-sort" : ""
                    }"
                    data-sort-key="${column.key}"
                  >
                    <span>${column.label}</span>${sortArrow(column.key)}
                  </th>
                `
              )
              .join("")}
          </tr>
        </thead>
        <tbody>
          ${sortedRows
            .map(
              (row) => `
                <tr>
                  <td>${titleVoiv(row)}</td>
                  <td class="num">${fmtInt(row.offers)}</td>
                  <td class="num">${fmtRate(row.offers_per_100k_lf)}</td>
                  <td class="num">${fmtInt(row.trainings)}</td>
                  <td class="num">${fmtRate(row.trainings_per_100k_lf)}</td>
                </tr>
              `
            )
            .join("")}
        </tbody>
      </table>
    `;

    document.getElementById("regional-table").innerHTML = tableHtml;
    document.querySelectorAll("[data-sort-key]").forEach((header) => {
      header.addEventListener("click", () => {
        const nextKey = header.getAttribute("data-sort-key");
        if (sortState.key === nextKey) {
          sortState.direction = sortState.direction === "asc" ? "desc" : "asc";
        } else {
          sortState.key = nextKey;
          sortState.direction = nextKey === "voivodeship" ? "asc" : "desc";
        }
        renderTable();
      });
    });
    document.getElementById(
      "sources-note"
    ).innerHTML = `Sources: job offers from <a href="https://www.pracuj.pl/" target="_blank" rel="noopener noreferrer">Pracuj.pl</a> (${meta.job_ads_posted_date_min} to ${meta.job_ads_posted_date_max}); training services from <a href="https://uslugirozwojowe.parp.gov.pl/" target="_blank" rel="noopener noreferrer">Baza Usług Rozwojowych</a>; labour force denominator from the GUS BDL API; population reference from Statistics Poland (GUS).`;
  }

  renderCards();
  renderMap();
  renderHighlights();
  renderTable();
})();
