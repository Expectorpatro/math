(() => {
  "use strict";

  const containers = Array.from(
    document.querySelectorAll(".density-plot[data-distribution]"),
  );
  if (!containers.length) return;

  const base = new URL(".", document.currentScript.src);
  const versions = window.TextbookAssetVersions || {};
  let bundlePromise;

  function loadScript(name) {
    return new Promise((resolve, reject) => {
      if (document.querySelector(`script[data-density-module="${name}"]`)) {
        resolve();
        return;
      }
      const url = new URL(name, base);
      if (versions[name]) url.searchParams.set("v", versions[name]);
      const script = document.createElement("script");
      script.src = url.href;
      script.dataset.densityModule = name;
      script.onload = resolve;
      script.onerror = () => reject(new Error(`无法加载 ${name}`));
      document.head.appendChild(script);
    });
  }

  function loadBundle() {
    if (!bundlePromise) {
      bundlePromise = loadScript("density-math.js")
        .then(() => loadScript("density-distributions.js"))
        .then(() => loadScript("density-probe.js"))
        .then(() => loadScript("density-renderer.js"))
        .then(() => loadScript("density-plots.js"));
    }
    return bundlePromise;
  }

  async function activate(container) {
    if (container.dataset.densityReady === "true") return;
    container.dataset.densityReady = "true";
    container.setAttribute("aria-busy", "true");
    try {
      await loadBundle();
      globalThis.TextbookDensityPlots.initialize(container);
    } catch (error) {
      container.textContent = error instanceof Error ? error.message : "交互图加载失败。";
      container.classList.add("density-plot--load-error");
    } finally {
      container.removeAttribute("aria-busy");
    }
  }

  if (!("IntersectionObserver" in window)) {
    containers.forEach(activate);
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        observer.unobserve(entry.target);
        activate(entry.target);
      }
    },
    { rootMargin: "500px 0px" },
  );
  containers.forEach((container) => observer.observe(container));
})();
