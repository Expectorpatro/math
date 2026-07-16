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

  const applyTheme = (theme, button) => {
    const wantsDark = theme === "dark";
    const isDark = currentTheme() === "dark";
    if (wantsDark !== isDark && typeof window.quartoToggleColorScheme === "function") {
      writeStorage(
        window.localStorage,
        KEYS.quartoTheme,
        wantsDark ? "default" : "alternate"
      );
      window.quartoToggleColorScheme();
    }
    writeTheme(theme);
    updateThemeButton(button);
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

    document.querySelectorAll("main.content table").forEach((table) => {
      const notationWrapper = table.closest(".notation-table-wrap");
      if (notationWrapper) {
        notationWrapper.setAttribute("role", "region");
        notationWrapper.setAttribute("aria-label", "可横向滚动的符号说明表");
        notationWrapper.tabIndex = 0;
        return;
      }
      if (table.classList.contains("notation-table")) {
        const wrapper = document.createElement("div");
        wrapper.className = "notation-table-wrap";
        wrapper.setAttribute("role", "region");
        wrapper.setAttribute("aria-label", "可横向滚动的符号说明表");
        wrapper.tabIndex = 0;
        table.parentNode.insertBefore(wrapper, table);
        wrapper.appendChild(table);
        return;
      }
      if (table.parentElement?.classList.contains("textbook-table-scroll")) return;
      const wrapper = document.createElement("div");
      wrapper.className = "textbook-table-scroll";
      wrapper.setAttribute("role", "region");
      wrapper.setAttribute("aria-label", "可横向滚动的数据表格");
      wrapper.tabIndex = 0;
      table.parentNode.insertBefore(wrapper, table);
      wrapper.appendChild(table);
    });

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
    const states = readJSON(window.sessionStorage, proofStorageKey(), {});
    const proofs = originals.map((original, index) => {
      if (original instanceof HTMLDetailsElement) return original;
      const details = document.createElement("details");
      Array.from(original.attributes).forEach((attribute) => {
        details.setAttribute(attribute.name, attribute.value);
      });
      details.classList.add("proof-block", "proof-collapsible");
      if (!details.id) details.id = `proof-client-${index + 1}`;

      const summary = document.createElement("summary");
      summary.className = "proof-summary";
      summary.innerHTML =
        '<span><i class="bi bi-chevron-right" aria-hidden="true"></i>证明</span>' +
        '<small>点击折叠</small>';
      const content = document.createElement("div");
      content.className = "proof-content";
      while (original.firstChild) content.appendChild(original.firstChild);
      details.append(summary, content);
      details.open = states[details.id] !== false;
      summary.querySelector("small").textContent = details.open ? "点击折叠" : "点击展开";
      details.addEventListener("toggle", () => {
        const latest = readJSON(window.sessionStorage, proofStorageKey(), {});
        latest[details.id] = details.open;
        writeStorage(window.sessionStorage, proofStorageKey(), JSON.stringify(latest));
        summary.querySelector("small").textContent = details.open ? "点击折叠" : "点击展开";
      });
      original.replaceWith(details);
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

  const mount = () => {
    polishDocument();
    mountThemeToggle();
    mountChapterProgressDock();
    mountTocContext();
    mountReadingTools();
    mountProofFolding();
    mountReferenceInteractions();
    mountIssueLink();

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
