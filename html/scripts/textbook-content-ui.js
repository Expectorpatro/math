(() => {
  "use strict";

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  const polishDataframe = (table) => {
    table.classList.add("textbook-dataframe");
    table.removeAttribute("border");

    const headerRows = Array.from(table.tHead?.rows || []);
    const firstHeaderCells = Array.from(headerRows[0]?.cells || []);
    const indexNameRow = headerRows[headerRows.length - 1];
    const indexNameCells = Array.from(indexNameRow?.cells || []);
    const namedIndexCells = indexNameCells.filter((cell) => cell.textContent.trim());

    // pandas renders an index name (for example, K) on a sparse second row.
    // Move that label into the empty corner cell so every heading sits over
    // the column it describes.
    if (
      headerRows.length > 1 &&
      firstHeaderCells.length === indexNameCells.length &&
      !firstHeaderCells[0]?.textContent.trim() &&
      namedIndexCells.length === 1 &&
      namedIndexCells[0] === indexNameCells[0]
    ) {
      firstHeaderCells[0].append(...Array.from(indexNameCells[0].childNodes));
      indexNameRow.remove();
    }

    table.querySelectorAll("thead tr[style]").forEach((row) => {
      row.removeAttribute("style");
    });
    table.querySelectorAll("thead th").forEach((cell) => {
      cell.scope = "col";
    });

    const bodyRows = Array.from(table.tBodies).flatMap((body) =>
      Array.from(body.rows)
    );
    bodyRows.forEach((row) => {
      Array.from(row.cells).forEach((cell) => {
        if (cell.tagName === "TH") cell.scope = "row";
      });
    });

  };

  const mountReadingTools = () => {
    const main = document.querySelector("main.content");
    if (!main || document.querySelector(".textbook-reading-progress")) return;

    const progress = document.createElement("div");
    progress.className = "textbook-reading-progress";
    progress.setAttribute("aria-hidden", "true");
    progress.innerHTML = "<span></span>";
    document.body.appendChild(progress);

    const progressFill = progress.firstElementChild;
    const backToTop = document.createElement("button");
    backToTop.type = "button";
    backToTop.className = "btn textbook-back-to-top";
    backToTop.setAttribute("aria-label", "返回页面顶部");
    backToTop.setAttribute("title", "返回页面顶部");
    backToTop.innerHTML = '<i class="bi bi-arrow-up" aria-hidden="true"></i>';
    document.body.appendChild(backToTop);

    let ticking = false;
    const update = () => {
      const scrollable = Math.max(
        document.documentElement.scrollHeight - window.innerHeight,
        1
      );
      const amount = Math.min(Math.max(window.scrollY / scrollable, 0), 1);
      progressFill.style.transform = `scaleX(${amount})`;
      backToTop.classList.toggle("is-visible", window.scrollY > 640);
      ticking = false;
    };
    const requestUpdate = () => {
      if (ticking) return;
      ticking = true;
      window.requestAnimationFrame(update);
    };
    window.addEventListener("scroll", requestUpdate, { passive: true });
    window.addEventListener("resize", requestUpdate);
    backToTop.addEventListener("click", () => {
      window.scrollTo({ top: 0, behavior: reduceMotion.matches ? "auto" : "smooth" });
      const focusTarget = main.querySelector("h1") || main;
      const hadTabIndex = focusTarget.hasAttribute("tabindex");
      if (!hadTabIndex) focusTarget.tabIndex = -1;
      try {
        focusTarget.focus({ preventScroll: true });
      } catch (_error) {
        focusTarget.focus();
      }
      if (!hadTabIndex) {
        focusTarget.addEventListener(
          "blur",
          () => focusTarget.removeAttribute("tabindex"),
          { once: true },
        );
      }
    });
    update();
  };

  const polishDocument = () => {
    const home = document.querySelector(".textbook-home");
    document.body.classList.toggle("textbook-home-page", Boolean(home));

    const sidebarTitle = document.querySelector("#quarto-sidebar .sidebar-title");
    const titleLink = sidebarTitle?.querySelector(":scope > a");
    if (sidebarTitle && titleLink && !sidebarTitle.querySelector(".textbook-brand-mark")) {
      const mark = document.createElement("span");
      mark.className = "textbook-brand-mark";
      mark.setAttribute("aria-hidden", "true");
      mark.textContent = "x\u0304";
      sidebarTitle.insertBefore(mark, titleLink);
    }

    const scrollRegions = new Map();
    const registerScrollRegion = (region, label) => {
      if (scrollRegions.has(region)) return;
      scrollRegions.set(region, {
        label,
        role: region.getAttribute("role"),
        ariaLabel: region.getAttribute("aria-label"),
        tabIndex: region.getAttribute("tabindex"),
      });
    };

    document.querySelectorAll("main.content table").forEach((table) => {
      if (table.classList.contains("dataframe")) polishDataframe(table);
      const notationWrapper = table.closest(".notation-table-wrap");
      if (notationWrapper) {
        registerScrollRegion(notationWrapper, "可横向滚动的符号说明表");
        return;
      }
      if (table.classList.contains("notation-table")) {
        const wrapper = document.createElement("div");
        wrapper.className = "notation-table-wrap";
        table.parentNode.insertBefore(wrapper, table);
        wrapper.appendChild(table);
        registerScrollRegion(wrapper, "可横向滚动的符号说明表");
        return;
      }
      let wrapper = table.parentElement?.classList.contains("textbook-table-scroll")
        ? table.parentElement
        : null;
      if (!wrapper) {
        wrapper = document.createElement("div");
        wrapper.className = "textbook-table-scroll";
        if (table.classList.contains("textbook-dataframe")) {
          wrapper.classList.add("textbook-dataframe-scroll");
        }
        table.parentNode.insertBefore(wrapper, table);
        wrapper.appendChild(table);
      }
      registerScrollRegion(
        wrapper,
        table.classList.contains("textbook-dataframe")
          ? "可横向滚动的 Python 数据表格"
          : "可横向滚动的数据表格",
      );
    });

    let scrollRegionFrame = 0;
    const restoreAttribute = (element, name, value) => {
      if (value === null) element.removeAttribute(name);
      else element.setAttribute(name, value);
    };
    const updateScrollRegions = () => {
      scrollRegionFrame = 0;
      scrollRegions.forEach((original, region) => {
        const isScrollable = region.scrollWidth > region.clientWidth + 1;
        if (isScrollable) {
          region.setAttribute("role", "region");
          region.setAttribute("aria-label", original.label);
          region.tabIndex = 0;
        } else {
          restoreAttribute(region, "role", original.role);
          restoreAttribute(region, "aria-label", original.ariaLabel);
          restoreAttribute(region, "tabindex", original.tabIndex);
        }
      });
    };
    const scheduleScrollRegionUpdate = () => {
      if (scrollRegionFrame) return;
      scrollRegionFrame = window.requestAnimationFrame(updateScrollRegions);
    };
    if (scrollRegions.size) {
      if ("ResizeObserver" in window) {
        const observer = new ResizeObserver(scheduleScrollRegionUpdate);
        scrollRegions.forEach((_original, region) => {
          observer.observe(region);
          if (region.firstElementChild) observer.observe(region.firstElementChild);
        });
      } else {
        window.addEventListener("resize", scheduleScrollRegionUpdate, { passive: true });
      }
      const mathReady = window.MathJax?.startup?.promise;
      if (mathReady && typeof mathReady.then === "function") {
        mathReady.then(scheduleScrollRegionUpdate, scheduleScrollRegionUpdate);
      }
      scheduleScrollRegionUpdate();
    }

    const searchInput = document.querySelector("#quarto-sidebar .aa-Input");
    if (searchInput && !searchInput.getAttribute("placeholder")) {
      searchInput.setAttribute("placeholder", "搜索全书…");
    }
    const tocTitle = document.querySelector("#TOC #toc-title");
    if (tocTitle) {
      const textNode = Array.from(tocTitle.childNodes).find(
        (node) => node.nodeType === Node.TEXT_NODE && node.textContent.trim()
      );
      if (textNode) textNode.textContent = "本页目录";
    }
  };

  const mountChapterProgressDock = () => {
    const progress = document.querySelector("main.content .chapter-progress");
    const margin = document.getElementById("quarto-margin-sidebar");
    if (!progress || !margin || progress.dataset.dockReady === "true") return;

    progress.dataset.dockReady = "true";
    const placeholder = document.createComment("chapter-progress-placeholder");
    progress.before(placeholder);
    const desktop = window.matchMedia("(min-width: 992px)");
    let printing = false;

    const restoreToChapter = () => {
      placeholder.after(progress);
      progress.classList.remove("chapter-progress--docked");
      margin.classList.remove("chapter-progress-sidebar");
    };
    const place = () => {
      if (desktop.matches && !printing) {
        margin.appendChild(progress);
        progress.classList.add("chapter-progress--docked");
        margin.classList.add("chapter-progress-sidebar");
      } else {
        restoreToChapter();
      }
    };

    if (typeof desktop.addEventListener === "function") {
      desktop.addEventListener("change", place);
    } else {
      desktop.addListener(place);
    }
    window.addEventListener("beforeprint", () => {
      printing = true;
      place();
    });
    window.addEventListener("afterprint", () => {
      printing = false;
      place();
    });
    window.addEventListener("pageshow", place);
    place();
  };

  const mount = () => {
    const initializers = [
      ["页面排版", polishDocument],
      ["章节进度", mountChapterProgressDock],
      ["阅读工具", mountReadingTools],
    ];
    initializers.forEach(([name, initialize]) => {
      try {
        initialize();
      } catch (error) {
        console.error(`[textbook] ${name}初始化失败`, error);
      }
    });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount, { once: true });
  } else {
    mount();
  }
})();
