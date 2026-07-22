(() => {
  "use strict";

  // Keep only the active top-level section's child entries visible in the page TOC.

  const targetIdFromHref = (href) => {
    const fragment = String(href || "").replace(/^#/, "");
    if (!fragment) return null;
    try {
      return decodeURIComponent(fragment);
    } catch (_error) {
      return null;
    }
  };

  const selectTocContext = (entries, marker, readTop = (entry) => entry.top) => {
    if (!entries.length) {
      return { activeEntry: null, activeTopLevelItem: null };
    }
    let activeEntry = entries[0];
    for (const entry of entries) {
      if (readTop(entry) <= marker) activeEntry = entry;
    }
    return {
      activeEntry,
      activeTopLevelItem: activeEntry.topLevelItem || null,
    };
  };

  const branchVisibility = (topLevelItems, activeTopLevelItem) =>
    topLevelItems.map((item) => item === activeTopLevelItem);

  const findTopLevelItem = (link, root) => {
    let item = link?.closest("li") || null;
    while (item && item.parentElement !== root) {
      item = item.parentElement?.closest("li") || null;
    }
    return item;
  };

  const updateSecondaryEntries = (root, activeTopLevelItem) => {
    const lists = Array.from(root.querySelectorAll(":scope > li > ul"));
    const visibility = branchVisibility(
      lists.map((list) => list.parentElement),
      activeTopLevelItem
    );
    lists.forEach((list, index) => {
      list.hidden = !visibility[index];
      list.classList.toggle("textbook-toc-branch-open", visibility[index]);
    });
  };

  const mountTocContext = (doc = document, win = window) => {
    const toc = doc.querySelector("#TOC");
    const root = toc?.querySelector(":scope > ul");
    if (!toc || !root || toc.dataset.contextReady === "true") return;
    toc.dataset.contextReady = "true";

    const links = Array.from(toc.querySelectorAll("a.nav-link"))
      .map((link) => {
        const identifier = targetIdFromHref(link.getAttribute("href"));
        return {
          link,
          target: identifier ? doc.getElementById(identifier) : null,
          topLevelItem: findTopLevelItem(link, root),
        };
      })
      .filter((entry) => entry.target);

    const setActive = (link) => {
      toc.querySelectorAll("a.nav-link.active").forEach((item) => {
        item.classList.remove("active");
      });
      if (link) link.classList.add("active");
      updateSecondaryEntries(root, findTopLevelItem(link, root));
    };

    const refresh = () => {
      const marker = win.scrollY + Math.min(win.innerHeight * 0.22, 180);
      const context = selectTocContext(
        links,
        marker,
        (entry) => entry.target.getBoundingClientRect().top + win.scrollY
      );
      setActive(context.activeEntry?.link || null);
    };

    links.forEach(({ link }) => {
      link.addEventListener("click", () => win.setTimeout(() => setActive(link), 0));
    });

    let ticking = false;
    win.addEventListener(
      "scroll",
      () => {
        if (ticking) return;
        ticking = true;
        win.requestAnimationFrame(() => {
          refresh();
          ticking = false;
        });
      },
      { passive: true }
    );
    win.addEventListener("resize", refresh);
    refresh();

    const observer = new win.MutationObserver(() => {
      const active = toc.querySelector("a.nav-link.active");
      updateSecondaryEntries(root, findTopLevelItem(active, root));
    });
    observer.observe(toc, {
      subtree: true,
      attributes: true,
      attributeFilter: ["class"],
    });
  };

  const api = Object.freeze({
    targetIdFromHref,
    selectTocContext,
    branchVisibility,
    updateSecondaryEntries,
    mountTocContext,
  });

  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }

  if (typeof window !== "undefined" && typeof document !== "undefined") {
    window.TextbookToc = api;
    const mount = () => {
      try {
        mountTocContext(document, window);
      } catch (error) {
        console.error("[textbook] 页内目录初始化失败", error);
      }
    };
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", mount, { once: true });
    } else {
      mount();
    }
  }
})();
