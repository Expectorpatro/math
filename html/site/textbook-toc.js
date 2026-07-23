(() => {
  "use strict";

  // Keep only the active top-level section's child entries visible in the page TOC.

  const targetIdFromHref = (href) => {
    const value = String(href || "");
    const hashIndex = value.indexOf("#");
    const fragment = hashIndex >= 0 ? value.slice(hashIndex + 1) : "";
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

  const directChildren = (element, selector) =>
    Array.from(element?.children || []).filter((child) => child.matches(selector));

  const directLink = (item) =>
    directChildren(item, "a.nav-link")[0] || null;

  const findTopLevelItem = (link, root) => {
    let item = link?.closest("li") || null;
    while (item && item.parentElement !== root) {
      item = item.parentElement?.closest("li") || null;
    }
    return item;
  };

  const updateSecondaryEntries = (root, activeTopLevelItem) => {
    const topLevelItems = directChildren(root, "li");
    const lists = topLevelItems
      .map((item) => directChildren(item, "ul")[0] || null)
      .filter(Boolean);
    const visibility = branchVisibility(
      lists.map((list) => list.parentElement),
      activeTopLevelItem
    );
    lists.forEach((list, index) => {
      list.hidden = !visibility[index];
      list.classList.toggle("textbook-toc-branch-open", visibility[index]);
    });
  };

  const updateCurrentEntry = (toc, entry) => {
    toc.querySelectorAll(".textbook-toc-current").forEach((link) => {
      link.classList.remove("textbook-toc-current");
    });
    entry?.link?.classList.add("textbook-toc-current");
  };

  const mountTocContext = (doc = document, win = window) => {
    const toc = doc.querySelector("#TOC");
    const root = directChildren(toc, "ul")[0] || null;
    if (!toc || !root || toc.dataset.contextReady === "true") return;
    toc.dataset.contextReady = "true";

    const entries = Array.from(toc.querySelectorAll("a.nav-link"))
      .map((link) => {
        const identifier = targetIdFromHref(link?.getAttribute("href"));
        return {
          link,
          target: identifier ? doc.getElementById(identifier) : null,
          topLevelItem: findTopLevelItem(link, root),
        };
      })
      .filter((entry) => entry.target && entry.topLevelItem);

    let pendingTopLevelItem = null;
    let navigationTimer = 0;
    let ticking = false;

    const refresh = () => {
      if (pendingTopLevelItem) {
        updateSecondaryEntries(root, pendingTopLevelItem);
        return;
      }
      const marker = win.scrollY + Math.min(win.innerHeight * 0.22, 180);
      const context = selectTocContext(
        entries,
        marker,
        (entry) => {
          const computationLead = entry.topLevelItem.classList.contains(
            "computation-toc-item"
          )
            ? Math.min(win.innerHeight * 0.28, 200)
            : 0;
          return (
            entry.target.getBoundingClientRect().top +
            win.scrollY -
            computationLead
          );
        }
      );
      updateSecondaryEntries(root, context.activeTopLevelItem);
      updateCurrentEntry(toc, context.activeEntry);
    };

    const finishNavigation = () => {
      if (!pendingTopLevelItem) return;
      pendingTopLevelItem = null;
      win.clearTimeout(navigationTimer);
      navigationTimer = 0;
      refresh();
    };

    const deferNavigationFinish = (delay) => {
      win.clearTimeout(navigationTimer);
      navigationTimer = win.setTimeout(finishNavigation, delay);
    };

    toc.querySelectorAll("a.nav-link").forEach((link) => {
      link.addEventListener("click", () => {
        const topLevelItem = findTopLevelItem(link, root);
        if (!topLevelItem) return;
        pendingTopLevelItem = topLevelItem;
        updateSecondaryEntries(root, topLevelItem);
        updateCurrentEntry(
          toc,
          entries.find((entry) => entry.link === link) || null
        );
        deferNavigationFinish(900);
      });
    });

    win.addEventListener(
      "scroll",
      () => {
        if (pendingTopLevelItem) {
          deferNavigationFinish(180);
          return;
        }
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
    if ("onscrollend" in win) {
      win.addEventListener("scrollend", finishNavigation, { passive: true });
    }
    refresh();
  };

  const api = Object.freeze({
    targetIdFromHref,
    directChildren,
    selectTocContext,
    branchVisibility,
    updateSecondaryEntries,
    updateCurrentEntry,
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
