(function () {
  const payload = window.__LIGHTCAST_AI_SKILLS__;
  const mountEl = document.getElementById("lightcast-ai-skills-table");
  const modalEl = document.getElementById("lightcast-ai-skill-modal");
  const demandEl = document.getElementById("ai-category-demand");
  const categoryCardsEl = document.getElementById("ai-category-cards");
  const tagChartEl = document.getElementById("ai-tag-chart");

  if (!payload) {
    return;
  }

  const rows = [...payload.rows];
  const state = {
    query: "",
    filter: "all",
    category: "",
    sortKey: "skill_name",
    sortDirection: "asc",
    page: 1,
    pageSize: 10,
  };

  const categoryOrder = [
    "Machine Learning & Predictive AI",
    "Generative AI",
    "Robotics & Autonomous Systems",
    "AI Governance, Risk & Strategy",
  ];

  const categoryVariant = {
    "Machine Learning & Predictive AI": "ml",
    "Generative AI": "genai",
    "Robotics & Autonomous Systems": "robotics",
    "AI Governance, Risk & Strategy": "governance",
  };

  const categoryIcon = {
    "Machine Learning & Predictive AI": `<svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a7 7 0 0 1 7 7c0 2.4-1.2 4.5-3 5.7V17a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2v-2.3C6.2 13.5 5 11.4 5 9a7 7 0 0 1 7-7z"/><path d="M9 21h6"/><path d="M10 17v-2.5"/><path d="M14 17v-2.5"/></svg>`,
    "Generative AI": `<svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/><path d="M8 12h.01"/><path d="M12 12h.01"/><path d="M16 12h.01"/></svg>`,
    "Robotics & Autonomous Systems": `<svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="10" rx="2"/><path d="M12 2v4"/><circle cx="12" cy="7" r="1"/><path d="M8 15h.01"/><path d="M16 15h.01"/><path d="M9 19h6"/><path d="M2 15h1"/><path d="M21 15h1"/></svg>`,
    "AI Governance, Risk & Strategy": `<svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/></svg>`,
  };

  const tagVariant = {
    "Deep Learning": "dl",
    "NLP": "nlp",
    "Computer Vision": "cv",
    "AI Agents & Assistants": "agents",
    "Automation & Control": "auto",
    "MLOps & Deployment": "mlops",
    "Ethics & Responsible AI": "gov",
    "AI Platforms & Tools": "platform",
    "General AI": "general",
  };

  const columns = [
    { key: "skill_name", label: "Skill", numeric: false },
    { key: "martins_neto", label: "Source", numeric: false },
    { key: "primary_category", label: "Category", numeric: false },
    { key: "tags", label: "Tags", numeric: false },
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

  const categoryPillHtml = (label) => {
    if (!label) {
      return '<span class="skill-empty">Not categorized</span>';
    }
    const variant = categoryVariant[label] || "default";
    return `<span class="skill-cat-pill skill-cat-pill-${variant}">${escapeHtml(label)}</span>`;
  };

  const tagPillHtml = (tag) => {
    const variant = tagVariant[tag] || "default";
    return `<span class="skill-tag-pill skill-tag-pill-${variant}">${escapeHtml(tag)}</span>`;
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
      if (state.filter === "martins" && !row.martins_neto) return false;
      if (state.filter === "new" && !row.lightcast_new) return false;
      if (state.category && row.primary_category !== state.category) return false;
      if (!query) return true;
      return [
        row.skill_name,
        row.skill_id,
        row.primary_category,
        ...(row.tags || []),
        row.subcategory,
        row.description,
      ].some((value) => normalize(value).includes(query));
    });
  }

  function sortedRows() {
    const result = [...filteredRows()];
    result.sort((a, b) => {
      const dir = state.sortDirection === "asc" ? 1 : -1;
      let left, right;
      if (state.sortKey === "martins_neto") {
        left = a.martins_neto ? "a" : "b";
        right = b.martins_neto ? "a" : "b";
      } else if (state.sortKey === "tags") {
        left = normalize((a.tags || []).join(", "));
        right = normalize((b.tags || []).join(", "));
      } else {
        left = normalize(a[state.sortKey]);
        right = normalize(b[state.sortKey]);
      }
      return left.localeCompare(right, "en") * dir;
    });
    return result;
  }

  function openModal(row) {
    document.getElementById("skill-modal-title").textContent = row.skill_name || "Untitled skill";
    document.getElementById("skill-modal-meta").innerHTML = [
      row.martins_neto ? badgeHtml("Martins-Neto et al. 2026", "martins") : badgeHtml("Added", "new"),
      row.primary_category ? categoryPillHtml(row.primary_category) : "",
      ...(row.tags || []).map((tag) => tagPillHtml(tag)),
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

  /* ── Category cards ── */
  function renderCategoryCards() {
    if (!categoryCardsEl) return;
    const summary = payload.meta.category_summary || {};
    categoryCardsEl.innerHTML = categoryOrder
      .map((cat) => {
        const s = summary[cat] || { count: 0, martins_count: 0, new_count: 0 };
        const variant = categoryVariant[cat] || "default";
        const icon = categoryIcon[cat] || "";
        return `
          <button class="ai-cat-card ai-cat-card-${variant}" type="button" data-ai-category="${escapeHtml(cat)}">
            <span class="ai-cat-icon">${icon}</span>
            <span class="ai-cat-name">${escapeHtml(cat)}</span>
            <span class="ai-cat-count">${s.count} skills</span>
            <span class="ai-cat-breakdown">${s.martins_count} benchmark + ${s.new_count} new</span>
          </button>
        `;
      })
      .join("");

    categoryCardsEl.querySelectorAll("[data-ai-category]").forEach((card) => {
      card.addEventListener("click", () => {
        const cat = card.getAttribute("data-ai-category") || "";
        state.category = state.category === cat ? "" : cat;
        state.filter = "all";
        state.page = 1;
        render();
        mountEl.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });
  }

  /* ── Tag chart ── */
  function renderTagChart() {
    if (!tagChartEl) return;
    const tagSummary = payload.meta.tag_summary || {};
    const sorted = Object.entries(tagSummary)
      .filter(([tag]) => tag !== "General AI")
      .sort((a, b) => b[1] - a[1]);
    const maxCount = sorted.length > 0 ? sorted[0][1] : 1;

    tagChartEl.innerHTML = `
      <div class="ai-tag-chart-title">Cross-cutting tags</div>
      <div class="ai-tag-chart-subtitle">Tags are non-exclusive — a skill can carry multiple tags.</div>
      <div class="ai-tag-bars">
        ${sorted
          .map(
            ([tag, count]) => `
              <div class="ai-tag-bar-row">
                <div class="ai-tag-bar-label">${tagPillHtml(tag)}</div>
                <div class="ai-tag-bar-track">
                  <div class="ai-tag-bar-fill" style="width:${((count / maxCount) * 100).toFixed(1)}%"></div>
                </div>
                <div class="ai-tag-bar-value">${count}</div>
              </div>
            `
          )
          .join("")}
      </div>
    `;
  }

  /* ── Demand chart by category ── */
  function renderCategoryDemand() {
    if (!demandEl) return;
    const demandRows = [...(payload.demand_summary || [])].sort((a, b) => b.share_of_ai_postings_pct - a.share_of_ai_postings_pct);
    demandEl.innerHTML = `
      <div class="ai-demand-summary">
        <p class="ai-demand-summary-copy">
          The expanded Lightcast AI definition identifies <strong>${payload.meta.ai_postings_total_expanded.toLocaleString("pl-PL")}</strong> AI-related postings under the conservative matching threshold of <strong>${payload.meta.match_threshold}</strong>.
        </p>
      </div>
      <div class="ai-demand-category-grid">
        ${demandRows
          .map(
            (row) => `
              <article class="ai-demand-cat-card ai-demand-cat-card-${categoryVariant[row.category] || "default"}">
                <div class="ai-demand-cat-top">
                  <div>
                    <div class="ai-demand-cat-name">${escapeHtml(row.category)}</div>
                    <div class="ai-demand-cat-meta">
                      ${row.share_of_ai_postings_pct.toLocaleString("pl-PL", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}% of AI postings · ${row.skills_in_category} skills in category
                    </div>
                  </div>
                </div>
                <div class="ai-demand-skill-list">
                  ${row.top_skills
                    .map(
                      (skill, idx) => `
                        <div class="ai-demand-skill-item">
                          <div class="ai-demand-skill-rank">${idx + 1}</div>
                          <div class="ai-demand-skill-copy">
                            <div class="ai-demand-skill-name">${escapeHtml(skill.skill_name)}</div>
                            <div class="ai-demand-skill-meta">
                              ${skill.share_within_category_pct.toLocaleString("pl-PL", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}% of category
                            </div>
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

  /* ── Table ── */
  function render(options = {}) {
    const { restoreSearchFocus = false, searchCursor = null } = options;
    if (!mountEl || !modalEl) return;

    const allRows = sortedRows();
    const totalPages = Math.max(1, Math.ceil(allRows.length / state.pageSize));
    if (state.page > totalPages) state.page = totalPages;

    const start = (state.page - 1) * state.pageSize;
    const pageRows = allRows.slice(start, start + state.pageSize);

    mountEl.innerHTML = `
      <div class="skill-table-toolbar">
        <div class="skill-table-search">
          <label for="lightcast-skill-search">Search skills</label>
          <input id="lightcast-skill-search" type="search" value="${escapeHtml(state.query)}" placeholder="Search by skill, category, tag, or keyword">
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
          <label for="lightcast-category-filter">Category</label>
          <select id="lightcast-category-filter">
            <option value="">All categories</option>
            ${categoryOrder
              .map(
                (cat) =>
                  `<option value="${escapeHtml(cat)}" ${state.category === cat ? "selected" : ""}>${escapeHtml(cat)}</option>`
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
        state.category
          ? `
        <div class="skill-active-cluster">
          <span>Active category:</span>
          <span class="skill-active-cluster-chip">${escapeHtml(state.category)}</span>
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
                  (col) => `
                    <th class="sortable ${state.sortKey === col.key ? "active-sort" : ""}" data-sort-key="${col.key}">
                      <span>${col.label}</span>${sortArrow(col.key)}
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
                          <td>${row.martins_neto ? badgeHtml("M-N 2026", "martins") : badgeHtml("Added", "new")}</td>
                          <td>${categoryPillHtml(row.primary_category)}</td>
                          <td><div class="skill-tags-cell">${(row.tags || []).map((t) => tagPillHtml(t)).join("")}</div></td>
                          <td>
                            <button class="skill-view-btn skill-view-btn-compact" type="button" data-open-modal="${start + idx}">Description</button>
                          </td>
                        </tr>
                      `
                    )
                    .join("")
                : `
                  <tr>
                    <td colspan="5" class="skill-empty-row">No skills match the current search and filter.</td>
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

    document.getElementById("lightcast-skill-search").addEventListener("input", (e) => {
      state.query = e.target.value;
      state.page = 1;
      const cursor = typeof e.target.selectionStart === "number" ? e.target.selectionStart : state.query.length;
      render({ restoreSearchFocus: true, searchCursor: cursor });
    });

    document.getElementById("lightcast-skill-filter").addEventListener("change", (e) => {
      state.filter = e.target.value;
      state.page = 1;
      render();
    });

    document.getElementById("lightcast-category-filter").addEventListener("change", (e) => {
      state.category = e.target.value;
      state.page = 1;
      render();
    });

    document.getElementById("lightcast-page-size").addEventListener("change", (e) => {
      state.pageSize = Number(e.target.value);
      state.page = 1;
      render();
    });

    const clearBtn = document.getElementById("skill-clear-cluster");
    if (clearBtn) {
      clearBtn.addEventListener("click", () => {
        state.category = "";
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
        if (action === "prev" && state.page > 1) state.page -= 1;
        if (action === "next" && state.page < totalPages) state.page += 1;
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

  modalEl.addEventListener("click", (e) => {
    if (e.target instanceof HTMLElement && e.target.dataset.closeModal === "true") {
      closeModal();
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !modalEl.classList.contains("hidden")) {
      closeModal();
    }
  });

  renderCategoryCards();
  renderTagChart();
  renderCategoryDemand();
  render();
})();
