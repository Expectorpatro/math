(() => {
  "use strict";

  const KEYS = {
    theme: "textbook-color-scheme",
    quartoTheme: "quarto-color-scheme",
    proofs: "textbook-proof-state-v1",
    scrollPrefix: "textbook-scroll-v1:",
    visitedReferences: "textbook-reference-visits-v1",
    pendingReference: "textbook-reference-pending-v1",
  };
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  let referenceArrivalHandled = false;
  let targetTimer = 0;

  const readStorage = (storage, key) => {
    try {
      return storage.getItem(key);
    } catch (_error) {
      return null;
    }
  };

  const writeStorage = (storage, key, value) => {
    try {
      storage.setItem(key, value);
    } catch (_error) {
      // The page remains usable when storage is disabled; only persistence is lost.
    }
  };

  const removeStorage = (storage, key) => {
    try {
      storage.removeItem(key);
    } catch (_error) {
      // See writeStorage.
    }
  };

  const readJSON = (storage, key, fallback) => {
    const raw = readStorage(storage, key);
    if (!raw) return fallback;
    try {
      return JSON.parse(raw);
    } catch (_error) {
      return fallback;
    }
  };

  const currentTheme = () =>
    document.body.classList.contains("quarto-dark") ? "dark" : "light";

  const readStoredTheme = () => {
    const value = readStorage(window.localStorage, KEYS.theme);
    return value === "dark" || value === "light" ? value : null;
  };

  const writeTheme = (theme) => {
    writeStorage(window.localStorage, KEYS.theme, theme);
    writeStorage(
      window.localStorage,
      KEYS.quartoTheme,
      theme === "dark" ? "alternate" : "default"
    );
  };

  const updateThemeButton = (button) => {
    const isDark = currentTheme() === "dark";
    const targetName = isDark ? "浅色" : "深色";
    const icon = button.querySelector("i");
    icon.className = isDark ? "bi bi-sun-fill" : "bi bi-moon-stars-fill";
    button.setAttribute("aria-label", `切换到${targetName}模式`);
    button.setAttribute("title", `切换到${targetName}模式`);
    button.setAttribute("aria-pressed", String(isDark));
  };

  const setQuartoColorScheme = (theme) => {
    const wantsDark = theme === "dark";
    const alternateSheets = document.querySelectorAll(
      "link.quarto-color-scheme.quarto-color-alternate"
    );
    const primarySheets = document.querySelectorAll(
      "link.quarto-color-scheme:not(.quarto-color-alternate)"
    );

    alternateSheets.forEach((sheet) => {
      sheet.rel = wantsDark ? "stylesheet" : "disabled-stylesheet";
    });
    primarySheets.forEach((sheet) => {
      sheet.rel = "stylesheet";
    });
    document.body.classList.toggle("quarto-dark", wantsDark);
    document.body.classList.toggle("quarto-light", !wantsDark);
    document.querySelectorAll(".quarto-color-scheme-toggle").forEach((toggle) => {
      toggle.classList.toggle("alternate", wantsDark);
    });
    window.dispatchEvent(new Event("resize"));
  };

  const applyTheme = (theme, button) => {
    setQuartoColorScheme(theme);
    writeTheme(theme);
    updateThemeButton(button);
  };

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

  const mountTocContext = () => {
    const toc = document.querySelector("#TOC");
    const root = toc?.querySelector(":scope > ul");
    if (!toc || !root || toc.dataset.contextReady === "true") return;
    toc.dataset.contextReady = "true";

    const applyVisibility = (active) => {
      const activeItem = active?.closest("li");
      let activeBranch = activeItem;
      while (activeBranch && activeBranch.parentElement !== root) {
        activeBranch = activeBranch.parentElement?.closest("li");
      }
      root.querySelectorAll(":scope > li > ul").forEach((list) => {
        const show = list.parentElement === activeBranch;
        list.classList.toggle("textbook-toc-branch-open", show);
        list.hidden = !show;
      });
    };

    const links = Array.from(toc.querySelectorAll("a.nav-link"))
      .map((link) => ({
        link,
        target: document.getElementById(
          decodeURIComponent((link.getAttribute("href") || "").replace(/^#/, ""))
        ),
      }))
      .filter((entry) => entry.target);
    const setActive = (link) => {
      toc.querySelectorAll("a.nav-link.active").forEach((item) => {
        item.classList.remove("active");
      });
      if (link) link.classList.add("active");
      applyVisibility(link);
    };
    const refresh = () => {
      const marker = window.scrollY + Math.min(window.innerHeight * 0.22, 180);
      let current = links[0]?.link;
      for (const entry of links) {
        if (entry.target.getBoundingClientRect().top + window.scrollY <= marker) {
          current = entry.link;
        }
      }
      setActive(current);
    };
    links.forEach(({ link }) => {
      link.addEventListener("click", () => window.setTimeout(() => setActive(link), 0));
    });
    let ticking = false;
    window.addEventListener(
      "scroll",
      () => {
        if (ticking) return;
        ticking = true;
        window.requestAnimationFrame(() => {
          refresh();
          ticking = false;
        });
      },
      { passive: true }
    );
    window.addEventListener("resize", refresh);
    refresh();
    const observer = new MutationObserver(() => {
      applyVisibility(toc.querySelector("a.nav-link.active"));
    });
    observer.observe(toc, {
      subtree: true,
      attributes: true,
      attributeFilter: ["class"],
    });
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

  const mountThemeToggle = () => {
    if (document.getElementById("textbook-theme-toggle")) return;
    const button = document.createElement("button");
    button.id = "textbook-theme-toggle";
    button.type = "button";
    button.className = "btn textbook-theme-toggle";
    button.innerHTML = '<i class="bi" aria-hidden="true"></i>';

    const place = () => {
      const tocTitle = document.querySelector("#TOC #toc-title");
      const useToc = Boolean(
        tocTitle && window.matchMedia("(min-width: 992px)").matches
      );
      document.querySelectorAll(".textbook-toc-title-with-toggle").forEach((element) => {
        element.classList.remove("textbook-toc-title-with-toggle");
      });
      if (useToc) {
        tocTitle.classList.add("textbook-toc-title-with-toggle");
        tocTitle.appendChild(button);
        button.classList.add("textbook-theme-toggle-in-toc");
        button.classList.remove("textbook-theme-toggle-floating");
      } else {
        document.body.appendChild(button);
        button.classList.add("textbook-theme-toggle-floating");
        button.classList.remove("textbook-theme-toggle-in-toc");
      }
    };
    place();
    window.addEventListener("resize", place);
    applyTheme(readStoredTheme() || currentTheme(), button);
    button.addEventListener("click", () => {
      applyTheme(currentTheme() === "dark" ? "light" : "dark", button);
    });
    window.addEventListener("pageshow", () => {
      applyTheme(readStoredTheme() || currentTheme(), button);
    });
  };

  const proofStorageKey = () => `${KEYS.proofs}:${window.location.pathname}`;

  const mountProofFolding = () => {
    const originals = Array.from(document.querySelectorAll("main.content .proof-block"));
    if (!originals.length) return;
    const storedStates = readJSON(window.sessionStorage, proofStorageKey(), {});
    const states = storedStates && typeof storedStates === "object" ? storedStates : {};
    const proofs = originals.map((original, index) => {
      let details = original;
      if (!(original instanceof HTMLDetailsElement)) {
        details = document.createElement("details");
        Array.from(original.attributes).forEach((attribute) => {
          details.setAttribute(attribute.name, attribute.value);
        });

        const summary = document.createElement("summary");
        summary.className = "proof-summary";
        summary.innerHTML =
          '<span><i class="bi bi-chevron-right" aria-hidden="true"></i>证明</span>' +
          '<small>点击折叠</small>';
        const content = document.createElement("div");
        content.className = "proof-content";
        while (original.firstChild) content.appendChild(original.firstChild);
        details.append(summary, content);
        details.open = true;
        original.replaceWith(details);
      }
      details.classList.add("proof-block", "proof-collapsible");
      if (!details.id) details.id = `proof-client-${index + 1}`;
      const summary = details.querySelector(":scope > summary");
      const hint = summary?.querySelector("small");
      if (Object.prototype.hasOwnProperty.call(states, details.id)) {
        details.open = Boolean(states[details.id]);
      }
      if (hint) hint.textContent = details.open ? "点击折叠" : "点击展开";
      details.addEventListener("toggle", () => {
        const storedLatest = readJSON(window.sessionStorage, proofStorageKey(), {});
        const latest =
          storedLatest && typeof storedLatest === "object" ? storedLatest : {};
        latest[details.id] = details.open;
        writeStorage(window.sessionStorage, proofStorageKey(), JSON.stringify(latest));
        if (hint) hint.textContent = details.open ? "点击折叠" : "点击展开";
      });
      return details;
    });

    if (proofs.length > 1) {
      const controls = document.createElement("div");
      controls.className = "proof-controls";
      controls.setAttribute("aria-label", "本页证明显示控制");
      const makeButton = (label, open) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "proof-control";
        button.textContent = label;
        button.addEventListener("click", () => {
          proofs.forEach((proof) => {
            proof.open = open;
          });
        });
        return button;
      };
      controls.append(makeButton("展开本页证明", true), makeButton("折叠本页证明", false));
      proofs[0].parentNode.insertBefore(controls, proofs[0]);
    }
  };

  const scrollStorageKey = () =>
    `${KEYS.scrollPrefix}${window.location.pathname}${window.location.search}`;

  const saveReadingPosition = () => {
    const headings = Array.from(
      document.querySelectorAll("main.content h1[id], main.content h2[id], main.content h3[id]")
    );
    const marker = window.scrollY + 120;
    let anchor = null;
    for (const heading of headings) {
      const top = heading.getBoundingClientRect().top + window.scrollY;
      if (top <= marker) anchor = { id: heading.id, top };
      else break;
    }
    const state = {
      y: window.scrollY,
      anchor: anchor?.id || "",
      delta: anchor ? window.scrollY - anchor.top : 0,
      savedAt: Date.now(),
    };
    writeStorage(window.sessionStorage, scrollStorageKey(), JSON.stringify(state));
  };

  const pendingReference = () =>
    readJSON(window.sessionStorage, KEYS.pendingReference, null);

  const pendingMatchesCurrentPage = (pending) => {
    if (!pending || Date.now() - Number(pending.createdAt || 0) > 10 * 60 * 1000) {
      return false;
    }
    return (
      pending.pathname === window.location.pathname &&
      pending.search === window.location.search &&
      pending.hash === window.location.hash
    );
  };

  const restoreReadingPosition = (event) => {
    const navigation = performance.getEntriesByType("navigation")[0];
    if (!(event?.persisted || navigation?.type === "back_forward")) return;
    if (referenceArrivalHandled || pendingMatchesCurrentPage(pendingReference())) return;
    const state = readJSON(window.sessionStorage, scrollStorageKey(), null);
    if (!state || Date.now() - Number(state.savedAt || 0) > 24 * 60 * 60 * 1000) return;

    const restore = () => {
      let targetY = Number(state.y || 0);
      if (state.anchor) {
        const anchor = document.getElementById(state.anchor);
        if (anchor) {
          targetY = anchor.getBoundingClientRect().top + window.scrollY + Number(state.delta || 0);
        }
      }
      if (Math.abs(window.scrollY - targetY) > 24) {
        window.scrollTo({ top: Math.max(0, targetY), behavior: "auto" });
      }
    };
    const afterLayout = () =>
      window.requestAnimationFrame(() => window.requestAnimationFrame(restore));
    const mathReady = window.MathJax?.startup?.promise;
    if (mathReady && typeof mathReady.then === "function") mathReady.then(afterLayout, afterLayout);
    else afterLayout();
  };

  const referenceVisitKey = (link) =>
    JSON.stringify([
      link.dataset.referenceKey || new URL(link.href).hash,
      link.dataset.referenceItems || "",
    ]);

  const readReferenceVisits = () => {
    const visits = readJSON(window.sessionStorage, KEYS.visitedReferences, []);
    return Array.isArray(visits) ? visits : [];
  };

  const syncReferenceVisits = () => {
    const visits = new Set(readReferenceVisits());
    document.querySelectorAll("a.textbook-cross-reference").forEach((link) => {
      const visited = visits.has(referenceVisitKey(link));
      link.classList.toggle("is-reference-visited", visited);
      if (!link.dataset.referenceBaseTitle) {
        link.dataset.referenceBaseTitle = link.getAttribute("title") || "";
      }
      const hint = link.dataset.referenceHint || "";
      const title = [link.dataset.referenceBaseTitle, hint, visited ? "已查看" : ""]
        .filter(Boolean)
        .join(" · ");
      if (title) link.setAttribute("title", title);
    });
  };

  const rememberReference = (link) => {
    const visits = readReferenceVisits().filter((item) => item !== referenceVisitKey(link));
    visits.push(referenceVisitKey(link));
    writeStorage(
      window.sessionStorage,
      KEYS.visitedReferences,
      JSON.stringify(visits.slice(-500))
    );
    link.classList.add("is-reference-visited");

    const target = new URL(link.href, window.location.href);
    writeStorage(
      window.sessionStorage,
      KEYS.pendingReference,
      JSON.stringify({
        pathname: target.pathname,
        search: target.search,
        hash: target.hash,
        title: link.dataset.referenceTitle || link.textContent.trim(),
        hint: link.dataset.referenceHint || "",
        createdAt: Date.now(),
      })
    );
    window.setTimeout(() => {
      if (
        target.pathname === window.location.pathname &&
        target.search === window.location.search &&
        target.hash === window.location.hash
      ) {
        handleReferenceArrival();
      }
    }, 0);
  };

  const showReferenceToast = (message) => {
    let toast = document.getElementById("textbook-reference-toast");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "textbook-reference-toast";
      toast.className = "reference-toast";
      toast.setAttribute("role", "status");
      toast.setAttribute("aria-live", "polite");
      document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.classList.remove("is-visible");
    void toast.offsetWidth;
    toast.classList.add("is-visible");
    window.clearTimeout(Number(toast.dataset.timer || 0));
    const timer = window.setTimeout(() => toast.classList.remove("is-visible"), 4200);
    toast.dataset.timer = String(timer);
  };

  const handleReferenceArrival = () => {
    const pending = pendingReference();
    if (!pendingMatchesCurrentPage(pending) || !window.location.hash) return false;
    const identifier = decodeURIComponent(window.location.hash.slice(1));
    const target = document.getElementById(identifier);
    if (!target) return false;

    const enclosingProof =
      target.matches("details.proof-block") ? target : target.closest("details.proof-block");
    if (enclosingProof) enclosingProof.open = true;
    let anchoredEquation = null;
    if (target.matches(".equation-anchor")) {
      anchoredEquation = target.nextElementSibling;
      while (anchoredEquation?.classList.contains("display-math-copy-marker")) {
        anchoredEquation = anchoredEquation.nextElementSibling;
      }
      if (!anchoredEquation?.matches(".math.display")) {
        anchoredEquation = target.parentElement?.nextElementSibling?.querySelector(
          ".math.display"
        );
      }
    }
    const highlight =
      anchoredEquation ||
      target.closest(
        ".theorem-block, .equation-block, .algorithm-block, .proof-block, li, p, section"
      ) ||
      target;
    document.querySelectorAll(".is-reference-target").forEach((element) => {
      element.classList.remove("is-reference-target");
    });
    highlight.classList.add("is-reference-target");
    window.clearTimeout(targetTimer);
    targetTimer = window.setTimeout(
      () => highlight.classList.remove("is-reference-target"),
      3000
    );
    const message = [`已跳转至${pending.title || "引用目标"}`, pending.hint]
      .filter(Boolean)
      .join("，");
    showReferenceToast(message);
    const alignAfterLayout = () => {
      window.requestAnimationFrame(() => {
        window.requestAnimationFrame(() => {
          const rect = target.getBoundingClientRect();
          if (rect.top < 96 || rect.bottom > window.innerHeight - 24) {
            target.scrollIntoView({ block: "start", behavior: "auto" });
          }
        });
      });
    };
    const mathReady = window.MathJax?.startup?.promise;
    if (mathReady && typeof mathReady.then === "function") {
      mathReady.then(alignAfterLayout, alignAfterLayout);
    } else {
      alignAfterLayout();
    }
    referenceArrivalHandled = true;
    removeStorage(window.sessionStorage, KEYS.pendingReference);
    return true;
  };

  const mountReferenceInteractions = () => {
    syncReferenceVisits();
    const activate = (event) => {
      if (event.type === "click" && event.button !== 0) return;
      if (event.type === "auxclick" && event.button !== 1) return;
      const link = event.target.closest?.("a.textbook-cross-reference");
      if (!link) return;
      rememberReference(link);
    };
    document.addEventListener("click", activate, true);
    document.addEventListener("auxclick", activate, true);
    window.addEventListener("hashchange", handleReferenceArrival);
    window.addEventListener("pageshow", () => {
      syncReferenceVisits();
      handleReferenceArrival();
    });
    handleReferenceArrival();
  };

  const mountMathOverflow = () => {
    const main = document.querySelector("main.content");
    if (!main) return;

    const hintIdentifier = "textbook-math-overflow-hint";
    if (!document.getElementById(hintIdentifier)) {
      const hint = document.createElement("span");
      hint.id = hintIdentifier;
      hint.hidden = true;
      hint.textContent = "此公式可横向滚动以查看完整内容。";
      main.appendChild(hint);
    }
    const addDescription = (formula) => {
      const identifiers = new Set(
        (formula.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean),
      );
      identifiers.add(hintIdentifier);
      formula.setAttribute("aria-describedby", Array.from(identifiers).join(" "));
    };
    const removeDescription = (formula) => {
      const identifiers = (formula.getAttribute("aria-describedby") || "")
        .split(/\s+/)
        .filter((identifier) => identifier && identifier !== hintIdentifier);
      if (identifiers.length) formula.setAttribute("aria-describedby", identifiers.join(" "));
      else formula.removeAttribute("aria-describedby");
    };
    let frame = 0;
    const measure = () => {
      frame = 0;
      const formulas = [...main.querySelectorAll("span.math.inline")];
      const measurements = formulas.map((formula) => {
        const container =
          formula.closest("p, li, dd, dt, figcaption, .theorem-block, .proof-block") ||
          main;
        const formulaRect = formula.getBoundingClientRect();
        const mathRect = formula.querySelector("mjx-container")?.getBoundingClientRect();
        const containerRect = container.getBoundingClientRect();
        const containerStyle = window.getComputedStyle(container);
        const paddingRight = Number.parseFloat(containerStyle.paddingRight) || 0;
        const contentRight = containerRect.right - paddingRight;
        const availableWidth = Math.max(contentRight - formulaRect.left, 96);
        const intrinsicWidth = Math.max(
          formulaRect.width,
          mathRect?.width || 0,
          formula.scrollWidth || 0,
        );
        return {
          formula,
          availableWidth,
          overflows: intrinsicWidth > availableWidth + 1,
        };
      });
      measurements.forEach(({ formula, availableWidth, overflows }) => {
        if (overflows) {
          formula.classList.add("math-inline-overflow");
          formula.style.setProperty(
            "--math-inline-available-width",
            `${Math.floor(availableWidth)}px`
          );
          if (!formula.hasAttribute("tabindex")) {
            formula.tabIndex = 0;
            formula.dataset.mathOverflowTabindex = "true";
          }
          addDescription(formula);
          return;
        }
        formula.classList.remove("math-inline-overflow");
        formula.style.removeProperty("--math-inline-available-width");
        if (formula.dataset.mathOverflowTabindex === "true") {
          formula.removeAttribute("tabindex");
          delete formula.dataset.mathOverflowTabindex;
        }
        removeDescription(formula);
      });
    };
    const schedule = () => {
      window.cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(measure);
    };

    const mathReady = window.MathJax?.startup?.promise;
    if (mathReady && typeof mathReady.then === "function") {
      mathReady.then(schedule, schedule);
    } else {
      const observer = new MutationObserver(() => {
        if (!main.querySelector("span.math.inline mjx-container")) return;
        observer.disconnect();
        schedule();
      });
      observer.observe(main, { childList: true, subtree: true });
      window.setTimeout(() => {
        observer.disconnect();
        schedule();
      }, 2000);
    }
    if ("ResizeObserver" in window) {
      const observer = new ResizeObserver(schedule);
      observer.observe(main);
    } else {
      window.addEventListener("resize", schedule, { passive: true });
    }
    if (document.fonts?.ready) document.fonts.ready.then(schedule, schedule);
  };

  const mountIssueLink = () => {
    if (document.querySelector(".textbook-home, .page-report-issue")) return;
    const main = document.querySelector("main.content");
    const repository = document.querySelector('meta[name="textbook-repository"]')?.content;
    if (!main || !repository) return;
    const pageTitle =
      document.querySelector("main.content h1")?.textContent.trim() || document.title;
    const query = new URLSearchParams({
      title: `[网页问题] ${pageTitle}`,
      body:
        `页面：${window.location.href}\n\n` +
        `位置或引用编号：\n\n问题描述：\n`,
    });
    const link = document.createElement("a");
    link.className = "page-report-issue";
    link.href = `https://github.com/${repository}/issues/new?${query.toString()}`;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.innerHTML =
      '<i class="bi bi-github" aria-hidden="true"></i>' +
      '<span>在 GitHub 上报告本页问题</span>' +
      '<i class="bi bi-arrow-up-right" aria-hidden="true"></i>';
    const navigation = main.querySelector(":scope > nav.page-navigation");
    main.insertBefore(link, navigation || null);
  };

  const mountRecentCommits = () => {
    const lists = Array.from(document.querySelectorAll(".home-commits"));
    const repository = document.querySelector('meta[name="textbook-repository"]')?.content;
    if (!lists.length || !/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repository || "")) {
      return;
    }

    const createCommitItem = (commit) => {
      const hash = typeof commit?.sha === "string" ? commit.sha : "";
      const url = typeof commit?.html_url === "string" ? commit.html_url : "";
      const message = typeof commit?.commit?.message === "string"
        ? commit.commit.message.split(/\r?\n/, 1)[0].trim()
        : "";
      const rawDate = commit?.commit?.author?.date;
      const date = typeof rawDate === "string" ? rawDate.slice(0, 10) : "";
      if (!hash || !url || !message || !/^\d{4}-\d{2}-\d{2}$/.test(date)) {
        return null;
      }

      const item = document.createElement("li");
      const link = document.createElement("a");
      const code = document.createElement("code");
      const subject = document.createElement("span");
      const time = document.createElement("time");
      link.href = url;
      code.textContent = hash.slice(0, 7);
      subject.textContent = message;
      time.dateTime = date;
      time.textContent = date;
      link.append(code, subject, time);
      item.appendChild(link);
      return item;
    };

    lists.forEach((list) => list.setAttribute("aria-busy", "true"));
    fetch(`https://api.github.com/repos/${repository}/commits?sha=main&per_page=3`, {
      headers: { Accept: "application/vnd.github+json" },
      cache: "no-store",
    })
      .then((response) => {
        if (!response.ok) throw new Error(`GitHub commits request failed: ${response.status}`);
        return response.json();
      })
      .then((commits) => {
        if (!Array.isArray(commits)) return;
        lists.forEach((list) => {
          const items = commits.map(createCommitItem).filter(Boolean);
          if (!items.length) return;
          list.replaceChildren(...items);
          list.dataset.source = "github";
        });
      })
      .catch(() => {
        // Keep the build-time list visible when offline or rate-limited.
      })
      .finally(() => {
        lists.forEach((list) => list.removeAttribute("aria-busy"));
      });
  };

  const mount = () => {
    const initializers = [
      ["页面排版", polishDocument],
      ["主题切换", mountThemeToggle],
      ["章节进度", mountChapterProgressDock],
      ["页内目录", mountTocContext],
      ["阅读工具", mountReadingTools],
      ["证明折叠", mountProofFolding],
      ["交叉引用", mountReferenceInteractions],
      ["公式溢出", mountMathOverflow],
      ["问题反馈", mountIssueLink],
      ["最近提交", mountRecentCommits],
    ];
    initializers.forEach(([name, initialize]) => {
      try {
        initialize();
      } catch (error) {
        console.error(`[textbook] ${name}初始化失败`, error);
      }
    });

    window.addEventListener("pagehide", saveReadingPosition);
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "hidden") saveReadingPosition();
    });
    window.addEventListener("pageshow", restoreReadingPosition);
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount, { once: true });
  } else {
    mount();
  }
})();
