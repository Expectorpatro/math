(() => {
  "use strict";

  const modules = [
    "textbook-content-ui.js",
    "textbook-reading.js",
    "textbook-page-ui.js",
  ];
  const ownScript = document.currentScript;
  const base = ownScript?.src
    ? new URL(".", ownScript.src)
    : new URL(".", document.baseURI);
  const versions = window.TextbookAssetVersions || {};

  const load = (name) =>
    new Promise((resolve, reject) => {
      if (document.querySelector(`script[data-textbook-ui-module="${name}"]`)) {
        resolve();
        return;
      }
      const url = new URL(name, base);
      if (versions[name]) url.searchParams.set("v", versions[name]);
      const script = document.createElement("script");
      script.src = url.href;
      script.async = false;
      script.dataset.textbookUiModule = name;
      script.addEventListener("load", resolve, { once: true });
      script.addEventListener("error", reject, { once: true });
      document.head.appendChild(script);
    });

  modules.reduce(
    (ready, name) => ready.then(() => load(name)),
    Promise.resolve(),
  ).catch((error) => {
    console.error("[textbook] 页面交互模块加载失败", error);
  });
})();
