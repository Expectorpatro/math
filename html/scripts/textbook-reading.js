(() => {
  "use strict";

  const KEYS = {
    proofs: "textbook-proof-state-v1",
    scrollPrefix: "textbook-scroll-v1:",
    visitedReferences: "textbook-reference-visits-v1",
    pendingReference: "textbook-reference-pending-v1",
  };
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

  const mount = () => {
    [
      ["证明折叠", mountProofFolding],
      ["交叉引用", mountReferenceInteractions],
    ].forEach(([name, initialize]) => {
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
