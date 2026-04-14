(function () {
  const payload = window.__LIGHTCAST_AI_SKILLS__;
  const mountEl = document.getElementById("lightcast-ai-skills-table");
  const modalEl = document.getElementById("lightcast-ai-skill-modal");
  const demandEl = document.getElementById("ai-cluster-demand");

  if (!payload) {
    return;
  }

  const rows = [...payload.rows];
  const state = {
    query: "",
    filter: "all",
    cluster: "",
    sortKey: "skill_name",
    sortDirection: "asc",
    page: 1,
    pageSize: 10,
  };

  const clusterOptions = [...new Set(rows.map((row) => row.cluster).filter(Boolean))].sort((a, b) =>
    a.localeCompare(b, "en")
  );

  const columns = [
    { key: "skill_name", label: "Skill", numeric: false },
    { key: "martins_neto", label: "Martins-Neto et al. 2026", numeric: false },
    { key: "cluster", label: "Cluster", numeric: false },
    { key: "subcategory", label: "Lightcast subcategory", numeric: false },
    { key: "categorization", label: "Categorization", numeric: false },
  ];

  const normalize = (value) => String(value || "").toLocaleLowerCase("en");
  const escapeHtml = (value) =>
    String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");

  const badgeHtml = (label, variant) =>
    `<span class="skill-flag skill-flag-${variant}">${escapeHtml(label)}</span>`;

  const shortText = (value, maxChars) => {
    const text = String(value || "").trim();
    if (text.length <= maxChars) {
      return text;
    }
    return `${text.slice(0, maxChars - 1)}…`;
  };

  const sortArrow = (columnKey) => {
    if (state.sortKey !== columnKey) {
      return '<span class="sort-arrow muted">↕</span>';
    }
    return state.sortDirection === "asc"
      ? '<span class="sort-arrow">↑</span>'
      : '<span class="sort-arrow">↓</span>';
  };

  function filteredRows() {
    const query = normalize(state.query);

    return rows.filter((row) => {
      if (state.filter === "martins" && !row.martins_neto) {
        return false;
      }
      if (state.filter === "new" && !row.lightcast_new) {
        return false;
      }
      if (state.cluster && row.cluster !== state.cluster) {
        return false;
      }
      if (!query) {
        return true;
      }

      return [
        row.skill_name,
        row.skill_id,
        row.cluster,
        row.category,
        row.subcategory,
        row.skill_type,
        row.description,
      ].some((value) => normalize(value).includes(query));
    });
  }

  function sortedRows() {
    const result = [...filteredRows()];
    if (state.cluster) {
      result.sort((a, b) => {
        if (a.martins_neto !== b.martins_neto) {
          return b.martins_neto - a.martins_neto;
        }
        if (a.lightcast_new !== b.lightcast_new) {
          return a.lightcast_new - b.lightcast_new;
        }
        return normalize(a.skill_name).localeCompare(normalize(b.skill_name), "en");
      });
      return result;
    }
    result.sort((a, b) => {
      const dir = state.sortDirection === "asc" ? 1 : -1;
      const left =
        state.sortKey === "martins_neto"
          ? normalize(a.martins_neto ? "yes" : "no")
          : state.sortKey === "categorization"
            ? normalize(a.cluster_source)
            : normalize(a[state.sortKey]);
      const right =
        state.sortKey === "martins_neto"
          ? normalize(b.martins_neto ? "yes" : "no")
          : state.sortKey === "categorization"
            ? normalize(b.cluster_source)
            : normalize(b[state.sortKey]);
      return left.localeCompare(right, "en") * dir;
    });
    return result;
  }

  function openModal(row) {
    document.getElementById("skill-modal-title").textContent = row.skill_name || "Untitled skill";
    document.getElementById("skill-modal-meta").innerHTML = [
      row.martins_neto ? badgeHtml("M-N et al. 2026", "martins") : "",
      row.lightcast_new ? badgeHtml("Added", "new") : "",
      row.cluster_source === "embedding_provisional"
        ? badgeHtml("Embedding-based cluster assignment", "new")
        : "",
      row.cluster ? `<span class="skill-meta-chip">${escapeHtml(row.cluster)}</span>` : "",
      row.category ? `<span class="skill-meta-chip">${escapeHtml(row.category)}</span>` : "",
      row.subcategory ? `<span class="skill-meta-chip">${escapeHtml(row.subcategory)}</span>` : "",
      row.skill_type ? `<span class="skill-meta-chip">${escapeHtml(row.skill_type)}</span>` : "",
      row.skill_id ? `<span class="skill-meta-chip">${escapeHtml(row.skill_id)}</span>` : "",
    ]
      .filter(Boolean)
      .join("");

    document.getElementById("skill-modal-body").innerHTML = row.description
      ? `<p>${escapeHtml(row.description)}</p>`
      : "<p>No description available for this skill.</p>";

    modalEl.classList.remove("hidden");
    modalEl.setAttribute("aria-hidden", "false");
    document.body.classList.add("modal-open");
  }

  function closeModal() {
    modalEl.classList.add("hidden");
    modalEl.setAttribute("aria-hidden", "true");
    document.body.classList.remove("modal-open");
  }

  function renderClusterDemand() {
    if (!demandEl) {
      return;
    }

    const demandRows = payload.demand_summary || [];
    demandEl.innerHTML = `
      <div class="ai-demand-summary">
        <p class="ai-demand-summary-copy">
          The expanded Lightcast AI definition identifies <strong>${payload.meta.ai_postings_total_expanded}</strong> AI-related postings under the conservative matching threshold of <strong>${payload.meta.match_threshold}</strong> ("Projektowanie efektywnych promptów" -> Prompt Engineering Tools, .63 similarity).
        </p>
      </div>
      <div class="ai-demand-cluster-grid">
        ${demandRows
          .map(
            (clusterRow) => `
              <article class="ai-demand-cluster-card">
                <div class="ai-demand-cluster-top">
                  <div>
                    <div class="ai-demand-cluster-name">${escapeHtml(clusterRow.cluster)}</div>
                    <div class="ai-demand-cluster-meta">
                      ${clusterRow.share_of_ai_postings_pct.toLocaleString("pl-PL", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}% of AI postings
                    </div>
                  </div>
                </div>
                <div class="ai-demand-skill-list">
                  ${clusterRow.top_skills
                    .map(
                      (skill, idx) => `
                        <div class="ai-demand-skill-item">
                          <div class="ai-demand-skill-rank">${idx + 1}</div>
                          <div class="ai-demand-skill-copy">
                            <div class="ai-demand-skill-name">${escapeHtml(skill.skill_name)}</div>
                            <div class="ai-demand-skill-meta">
                              ${skill.share_within_cluster_pct.toLocaleString("pl-PL", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}% of cluster
                            </div>
                          </div>
                          <div class="ai-demand-skill-tag">
                            ${skill.martins_neto ? badgeHtml("M-N et al. 2026", "martins") : badgeHtml("Added", "new")}
                          </div>
                        </div>
                      `
                    )
                    .join("")}
                </div>
              </article>
            `
          )
          .join("")}
      </div>
    `;
  }

  function render(options = {}) {
    const { restoreSearchFocus = false, searchCursor = null } = options;
    if (!mountEl || !modalEl) {
      return;
    }
    const allRows = sortedRows();
    const totalPages = Math.max(1, Math.ceil(allRows.length / state.pageSize));
    if (state.page > totalPages) {
      state.page = totalPages;
    }

    const start = (state.page - 1) * state.pageSize;
    const pageRows = allRows.slice(start, start + state.pageSize);

    mountEl.innerHTML = `
      <div class="skill-table-toolbar">
        <div class="skill-table-search">
          <label for="lightcast-skill-search">Search skills</label>
          <input id="lightcast-skill-search" type="search" value="${escapeHtml(state.query)}" placeholder="Search by skill, cluster, category, or keyword">
        </div>
        <div class="skill-table-filter">
          <label for="lightcast-skill-filter">Show</label>
          <select id="lightcast-skill-filter">
            <option value="all" ${state.filter === "all" ? "selected" : ""}>All skills (${payload.meta.count_total})</option>
            <option value="martins" ${state.filter === "martins" ? "selected" : ""}>Martins-Neto benchmark (${payload.meta.count_martins_neto})</option>
            <option value="new" ${state.filter === "new" ? "selected" : ""}>New in current Lightcast (${payload.meta.count_lightcast_new})</option>
          </select>
        </div>
        <div class="skill-table-filter">
          <label for="lightcast-cluster-filter">Cluster</label>
          <select id="lightcast-cluster-filter">
            <option value="">All clusters</option>
            ${clusterOptions
              .map(
                (cluster) =>
                  `<option value="${escapeHtml(cluster)}" ${state.cluster === cluster ? "selected" : ""}>${escapeHtml(cluster)}</option>`
              )
              .join("")}
          </select>
        </div>
        <div class="skill-table-filter skill-table-filter-small">
          <label for="lightcast-page-size">Rows</label>
          <select id="lightcast-page-size">
            ${[10, 15, 25].map((size) => `<option value="${size}" ${state.pageSize === size ? "selected" : ""}>${size} / page</option>`).join("")}
          </select>
        </div>
      </div>
      ${
        state.cluster
          ? `
        <div class="skill-active-cluster">
          <span>Active cluster filter:</span>
          <span class="skill-active-cluster-chip">${escapeHtml(state.cluster)}</span>
          <button type="button" class="skill-clear-cluster" id="skill-clear-cluster">Clear</button>
        </div>
      `
          : ""
      }
      <div class="skill-table-summary">
        Showing <strong>${allRows.length}</strong> skills. Page <strong>${state.page}</strong> of <strong>${totalPages}</strong>.
      </div>
      <div class="data-table-wrap">
        <table class="data-table skill-data-table">
          <thead>
            <tr>
              ${columns
                .map(
                  (column) => `
                    <th class="sortable ${state.sortKey === column.key ? "active-sort" : ""}" data-sort-key="${column.key}">
                      <span>${column.label}</span>${sortArrow(column.key)}
                    </th>
                  `
                )
                .join("")}
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            ${
              pageRows.length
                ? pageRows
                    .map(
                      (row, idx) => `
                        <tr data-row-index="${start + idx}" class="${row.lightcast_new ? "skill-row-new" : "skill-row-paper"}">
                          <td>
                            <div class="skill-name">${escapeHtml(row.skill_name)}</div>
                            <div class="skill-id">${escapeHtml(row.skill_id)}</div>
                          </td>
                          <td>${row.martins_neto ? badgeHtml("M-N et al. 2026", "martins") : badgeHtml("Added", "new")}</td>
                          <td>${row.cluster ? escapeHtml(row.cluster) : '<span class="skill-empty">Not classified yet</span>'}</td>
                          <td>${row.subcategory ? escapeHtml(row.subcategory) : '<span class="skill-empty">n/a</span>'}</td>
                          <td>${
                            row.cluster_source === "paper"
                              ? badgeHtml("M-N et al. 2026 cluster", "martins")
                              : badgeHtml("Added: embedding-based classification", "new")
                          }</td>
                          <td>
                            <button class="skill-view-btn skill-view-btn-compact" type="button" data-open-modal="${start + idx}">Description</button>
                          </td>
                        </tr>
                      `
                    )
                    .join("")
                : `
                  <tr>
                    <td colspan="8" class="skill-empty-row">No skills match the current search and filter.</td>
                  </tr>
                `
            }
          </tbody>
        </table>
      </div>
      <div class="skill-table-pagination">
        <button type="button" class="skill-page-btn" data-page-action="prev" ${state.page === 1 ? "disabled" : ""}>Previous</button>
        <button type="button" class="skill-page-btn" data-page-action="next" ${state.page === totalPages ? "disabled" : ""}>Next</button>
      </div>
    `;

    document.getElementById("lightcast-skill-search").addEventListener("input", (event) => {
      state.query = event.target.value;
      state.page = 1;
      const cursor =
        typeof event.target.selectionStart === "number"
          ? event.target.selectionStart
          : state.query.length;
      render({ restoreSearchFocus: true, searchCursor: cursor });
    });

    document.getElementById("lightcast-skill-filter").addEventListener("change", (event) => {
      state.filter = event.target.value;
      state.page = 1;
      render();
    });

    document.getElementById("lightcast-cluster-filter").addEventListener("change", (event) => {
      state.cluster = event.target.value;
      state.page = 1;
      render();
    });

    document.getElementById("lightcast-page-size").addEventListener("change", (event) => {
      state.pageSize = Number(event.target.value);
      state.page = 1;
      render();
    });

    const clearClusterBtn = document.getElementById("skill-clear-cluster");
    if (clearClusterBtn) {
      clearClusterBtn.addEventListener("click", () => {
        state.cluster = "";
        state.page = 1;
        render();
      });
    }

    mountEl.querySelectorAll("[data-sort-key]").forEach((header) => {
      header.addEventListener("click", () => {
        const nextKey = header.getAttribute("data-sort-key");
        if (state.sortKey === nextKey) {
          state.sortDirection = state.sortDirection === "asc" ? "desc" : "asc";
        } else {
          state.sortKey = nextKey;
          state.sortDirection = "asc";
        }
        render();
      });
    });

    mountEl.querySelectorAll("[data-open-modal]").forEach((button) => {
      button.addEventListener("click", () => {
        const rowIndex = Number(button.getAttribute("data-open-modal"));
        openModal(allRows[rowIndex]);
      });
    });

    mountEl.querySelectorAll("[data-page-action]").forEach((button) => {
      button.addEventListener("click", () => {
        const action = button.getAttribute("data-page-action");
        if (action === "prev" && state.page > 1) {
          state.page -= 1;
        }
        if (action === "next" && state.page < totalPages) {
          state.page += 1;
        }
        render();
      });
    });

    if (restoreSearchFocus) {
      const searchEl = document.getElementById("lightcast-skill-search");
      if (searchEl) {
        searchEl.focus();
        const cursorPos = typeof searchCursor === "number" ? searchCursor : searchEl.value.length;
        searchEl.setSelectionRange(cursorPos, cursorPos);
      }
    }
  }

  modalEl.addEventListener("click", (event) => {
    if (event.target instanceof HTMLElement && event.target.dataset.closeModal === "true") {
      closeModal();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modalEl.classList.contains("hidden")) {
      closeModal();
    }
  });

  document.querySelectorAll("[data-ai-cluster]").forEach((card) => {
    card.addEventListener("click", () => {
      const cluster = card.getAttribute("data-ai-cluster") || "";
      if (!clusterOptions.includes(cluster)) {
        return;
      }
      state.cluster = cluster;
      state.filter = "all";
      state.page = 1;
      render();
      mountEl.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });

  Object.entries(payload.meta.cluster_summary || {}).forEach(([cluster, summary]) => {
    document
      .querySelectorAll(`[data-ai-cluster-total-count="${CSS.escape(cluster)}"]`)
      .forEach((el) => {
        el.textContent = summary.total_count;
      });
    document
      .querySelectorAll(`[data-ai-cluster-new-count="${CSS.escape(cluster)}"]`)
      .forEach((el) => {
        el.textContent = summary.new_count;
      });
  });

  renderClusterDemand();
  render();
})();
