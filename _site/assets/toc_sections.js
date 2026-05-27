(function () {
  function throttle(fn, wait) {
    let t = 0;
    return (...args) => {
      const now = Date.now();
      if (now - t >= wait) {
        t = now;
        fn(...args);
      }
    };
  }

  function setSectionOpen(section, open) {
    section.classList.toggle("is-open", open);
    section
      .querySelector(".toc-section-toggle")
      ?.setAttribute("aria-expanded", open ? "true" : "false");
  }

  function closeAllSections(wrap) {
    wrap
      .querySelectorAll(".toc-section:not(.toc-section--flat)")
      .forEach((section) => setSectionOpen(section, false));
  }

  function findActiveSection(wrap) {
    const sections = wrap.querySelectorAll(".toc-section:not(.toc-section--flat)");
    for (const section of sections) {
      if (section.querySelector("a.active")) return section;
    }
    for (const section of sections) {
      if (section.querySelector(".toc-section-head > a.active")) return section;
    }
    return null;
  }

  function syncOpenSections(wrap) {
    const active = findActiveSection(wrap);
    wrap
      .querySelectorAll(".toc-section:not(.toc-section--flat)")
      .forEach((section) => setSectionOpen(section, section === active));
  }

  function initSectionToc() {
    const toc = document.getElementById("TOC");
    if (!toc || toc.dataset.sectionToc === "true") return;

    const rootUl = toc.querySelector(":scope > ul");
    if (!rootUl) return;

    const title = toc.querySelector("#toc-title");
    if (title) title.textContent = "Contents";

    const wrap = document.createElement("div");
    wrap.className = "toc-sections";

    [...rootUl.children].forEach((li) => {
      const link = li.querySelector(":scope > a.nav-link");
      const subUl = li.querySelector(":scope > ul");
      if (!link) return;

      if (!subUl) {
        const flat = document.createElement("div");
        flat.className = "toc-section toc-section--flat";
        flat.appendChild(link.cloneNode(true));
        wrap.appendChild(flat);
        return;
      }

      const section = document.createElement("div");
      section.className = "toc-section";

      const head = document.createElement("div");
      head.className = "toc-section-head";

      const toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "toc-section-toggle";
      toggle.setAttribute("aria-expanded", "false");
      toggle.setAttribute("aria-label", `Expand ${link.textContent.trim()}`);
      toggle.innerHTML =
        '<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path fill="currentColor" d="M6 4l4 4-4 4V4z"/></svg>';

      const headLink = link.cloneNode(true);
      head.appendChild(toggle);
      head.appendChild(headLink);

      subUl.classList.remove("collapse");
      subUl.className = "toc-section-children";

      section.appendChild(head);
      section.appendChild(subUl);
      wrap.appendChild(section);

      toggle.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const willOpen = !section.classList.contains("is-open");
        closeAllSections(wrap);
        if (willOpen) setSectionOpen(section, true);
      });

      headLink.addEventListener("click", () => {
        closeAllSections(wrap);
        setSectionOpen(section, true);
      });
    });

    rootUl.remove();
    toc.appendChild(wrap);
    toc.dataset.sectionToc = "true";

    const sync = () => syncOpenSections(wrap);

    sync();
    requestAnimationFrame(sync);

    window.addEventListener("scroll", throttle(sync, 100), { passive: true });

    const observer = new MutationObserver(throttle(sync, 50));
    observer.observe(wrap, {
      subtree: true,
      attributes: true,
      attributeFilter: ["class"],
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initSectionToc);
  } else {
    initSectionToc();
  }
})();
