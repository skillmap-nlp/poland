(function () {
  const payload = window.__AI_REGIONAL_REPORT__;
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

  const fmtRate = (value) =>
    new Intl.NumberFormat("en-US", {
      minimumFractionDigits: value < 10 ? 2 : 1,
      maximumFractionDigits: value < 10 ? 2 : 1,
    }).format(value);

  const fmtPct = (value) =>
    new Intl.NumberFormat("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);

  const titleVoiv = (row) =>
    T.voivodeshipLabel(row.voivodeship);

  function renderDetail(row) {
    const detailEl = document.getElementById("ai-regional-detail");
    if (!detailEl || !row) {
      return;
    }

    const chips = (row.top_characteristic_skills || [])
      .map(
        (skill, idx) => `
        <div class="ai-detail-skill">
          <div class="ai-detail-skill-rank">${idx + 1}</div>
          <div>
            <div class="ai-detail-skill-label">${String(skill.label || "")}</div>
            <div class="ai-detail-skill-meta">${skill.primary_category || ""}</div>
          </div>
        </div>
      `
      )
      .join("");

    const categories = (row.top_categories || [])
      .map(
        (cat, idx) => `
        <div class="ai-detail-cluster">
          <div class="ai-detail-cluster-rank">${idx + 1}</div>
          <div class="ai-detail-cluster-copy">
            <div class="ai-detail-cluster-label">${cat.category}</div>
            <div class="ai-detail-cluster-meta">${fmtPct(cat.share_of_regional_ai_pct)}% of regional AI postings</div>
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
            <span class="ai-detail-metric-label">AI offers per 100k LF</span>
            <span class="ai-detail-metric-value">${fmtRate(row.ai_offers_per_100k_lf)}</span>
          </div>
          <div class="ai-detail-metric">
            <span class="ai-detail-metric-label">AI offers</span>
            <span class="ai-detail-metric-value">${fmtInt(row.ai_offers)}</span>
          </div>
          <div class="ai-detail-metric">
            <span class="ai-detail-metric-label">Share of regional offers</span>
            <span class="ai-detail-metric-value">${fmtPct(row.ai_offer_share_pct)}%</span>
          </div>
        </div>
        <div class="ai-detail-panels">
          <div class="ai-detail-panel">
            <div class="ai-detail-skills-head">Top 5 characteristic AI skills by G²</div>
            <div class="ai-detail-skills">${chips}</div>
          </div>
          <div class="ai-detail-panel">
            <div class="ai-detail-clusters-head">AI demand by category</div>
            <div class="ai-detail-clusters">${categories}</div>
          </div>
        </div>
      </div>
    `;
  }

  function renderMap() {
    const mapEl = document.getElementById("ai-regional-map");
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
          customdata: rows.map((row) => [titleVoiv(row)]),
          z: rows.map((row) => row.ai_offers_per_100k_lf),
          colorscale: T.scale.demand,
          marker: T.mapMarker(),
          colorbar: {
            title: { text: "AI offers<br>per 100k LF" },
            thickness: 16,
            len: 0.7,
            x: 1.03,
            y: 0.5,
            outlinewidth: 0,
          },
          hovertemplate:
            "<b>%{customdata[0]}</b><extra></extra>",
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

    document.getElementById("ai-map-figure-title").textContent =
      "Figure 28. Regional AI demand intensity across Polish voivodeships";
    document.getElementById("ai-map-note").innerHTML = `
      <div class="figure-caption-source">
        Source: <a href="https://www.pracuj.pl/" target="_blank" rel="noopener noreferrer">Pracuj.pl</a>;
        Lightcast AI skills taxonomy; authors' semantic matching; labour force denominator from
        <a href="https://api.stat.gov.pl/Home/BdlApi?gt=&lang=en" target="_blank" rel="noopener noreferrer">GUS BDL API</a>.
        Regional assignment is available for ${fmtInt(meta.ai_offers_total_mapped)} of ${fmtInt(meta.ai_offers_total)} postings matched to Lightcast AI skills at a similarity threshold of ${meta.match_threshold}.
      </div>
    `;
  }

  renderMap();
  renderDetail(rows[0]);
})();
