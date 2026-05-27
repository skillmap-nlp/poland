(function () {
  const payload = window.__DIGITAL_REGIONAL_REPORT__;
  const regionalPayload = window.__REGIONAL_REPORT__;
  const T = window.__CHART_THEME__;

  if (!payload || !window.Plotly || !regionalPayload || !regionalPayload.geojson || !T) {
    return;
  }

  const rows = [...payload.rows];
  const meta = payload.meta || {};
  const geojson = regionalPayload.geojson;

  const fmtInt = (value) =>
    new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value);

  const fmtPct = (value) =>
    new Intl.NumberFormat("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);

  const titleVoiv = (row) =>
    row.voivodeship_en || T.voivodeshipLabel(row.voivodeship);

  function renderDetail(row) {
    const detailEl = document.getElementById("digital-regional-detail");
    if (!detailEl || !row) {
      return;
    }

    const chips = (row.top_skills || [])
      .map(
        (skill, idx) => `
        <div class="ai-detail-skill">
          <div class="ai-detail-skill-rank">${idx + 1}</div>
          <div>
            <div class="ai-detail-skill-label">${String(skill.label || "")}</div>
            <div class="ai-detail-skill-meta">${fmtInt(skill.count)} offers</div>
          </div>
        </div>
      `
      )
      .join("");

    detailEl.innerHTML = `
      <div class="ai-detail-card">
        <p class="section-kicker">Selected voivodeship</p>
        <h3>${titleVoiv(row)}</h3>
        <div class="ai-detail-metrics">
          <div class="ai-detail-metric">
            <span class="ai-detail-metric-label">Share of offers with digital skill</span>
            <span class="ai-detail-metric-value">${fmtPct(row.digital_pct)}%</span>
          </div>
          <div class="ai-detail-metric">
            <span class="ai-detail-metric-label">Offers with ≥1 digital skill</span>
            <span class="ai-detail-metric-value">${fmtInt(row.digital_offers)}</span>
          </div>
          <div class="ai-detail-metric">
            <span class="ai-detail-metric-label">Total mapped offers</span>
            <span class="ai-detail-metric-value">${fmtInt(row.total_mapped)}</span>
          </div>
        </div>
        <div class="ai-detail-panel">
          <div class="ai-detail-skills-head">Top 10 ESCO digital skills by offer count</div>
          <div class="ai-detail-skills">${chips}</div>
        </div>
      </div>
    `;
  }

  function renderMap() {
    const mapEl = document.getElementById("digital-regional-map");
    if (!mapEl) {
      return;
    }

    const locations = rows.map((row) => row.voivodeship);
    Plotly.newPlot(
      mapEl,
      [
        {
          type: "choropleth",
          geojson,
          featureidkey: "properties.nazwa",
          locations,
          customdata: rows.map((row) => [
            titleVoiv(row),
            fmtInt(row.digital_offers),
            fmtInt(row.total_mapped),
          ]),
          z: rows.map((row) => row.digital_pct),
          colorscale: T.scale.demand,
          marker: T.mapMarker(),
          colorbar: {
            title: { text: "% offers<br>with digital<br>skill" },
            thickness: 16,
            len: 0.7,
            x: 1.03,
            y: 0.5,
            outlinewidth: 0,
            ticksuffix: "%",
          },
          hovertemplate:
            "<b>%{customdata[0]}</b><br>" +
            "Digital share: %{z:.1f}%<br>" +
            "Digital offers: %{customdata[1]}<br>" +
            "Total offers: %{customdata[2]}<extra></extra>",
        },
      ],
      {
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
      },
      {
        displayModeBar: false,
        responsive: true,
      }
    );

    mapEl.on("plotly_click", (event) => {
      const point = event?.points?.[0];
      if (!point) {
        return;
      }
      const row = rows.find((item) => item.voivodeship === point.location);
      renderDetail(row);
    });

    document.getElementById("digital-map-note").innerHTML = `
      <div class="figure-caption-source">
        Source: <a href="https://www.pracuj.pl/" target="_blank" rel="noopener noreferrer">Pracuj.pl</a>
        2025 postings; ESCO Digital Skills Collection (PL preferredLabel + altLabels);
        regional assignment via TERYT SIMC geocoding.
        ${fmtInt(meta.total_digital_offers)} of ${fmtInt(meta.total_mapped_offers)} regionally assigned postings
        contain at least one ESCO digital skill (national share: ${fmtPct(meta.national_digital_pct)}%).
        Click a voivodeship to see the top demanded digital skills.
      </div>
    `;
  }

  renderMap();
  renderDetail(rows[0]);
})();
