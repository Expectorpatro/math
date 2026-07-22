(() => {
  "use strict";

  // Theme persistence, Quarto stylesheet synchronization, and toggle placement.

  const THEME_STORAGE_KEY = "textbook-color-scheme";
  const QUARTO_THEME_STORAGE_KEY = "quarto-color-scheme";

  const normalizeTheme = (value) =>
    value === "dark" || value === "light" ? value : null;

  const nextTheme = (theme) => (theme === "dark" ? "light" : "dark");

  const quartoThemePreference = (theme) =>
    theme === "dark" ? "alternate" : "default";

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

  const localStorageFor = (win) => {
    try {
      return win.localStorage;
    } catch (_error) {
      return null;
    }
  };

  const currentTheme = (doc) =>
    doc.body.classList.contains("quarto-dark") ? "dark" : "light";

  const readStoredTheme = (storage) =>
    normalizeTheme(readStorage(storage, THEME_STORAGE_KEY));

  const writeTheme = (storage, theme) => {
    writeStorage(storage, THEME_STORAGE_KEY, theme);
    writeStorage(storage, QUARTO_THEME_STORAGE_KEY, quartoThemePreference(theme));
  };

  const updateThemeButton = (button, theme) => {
    const isDark = theme === "dark";
    const targetName = isDark ? "浅色" : "深色";
    const icon = button.querySelector("i");
    if (icon) {
      icon.className = isDark ? "bi bi-sun-fill" : "bi bi-moon-stars-fill";
    }
    button.setAttribute("aria-label", `切换到${targetName}模式`);
    button.setAttribute("title", `切换到${targetName}模式`);
    button.setAttribute("aria-pressed", String(isDark));
  };

  const setQuartoColorScheme = (theme, doc, win) => {
    const wantsDark = theme === "dark";
    const alternateSheets = doc.querySelectorAll(
      "link.quarto-color-scheme.quarto-color-alternate"
    );
    const primarySheets = doc.querySelectorAll(
      "link.quarto-color-scheme:not(.quarto-color-alternate)"
    );

    alternateSheets.forEach((sheet) => {
      sheet.rel = wantsDark ? "stylesheet" : "disabled-stylesheet";
    });
    primarySheets.forEach((sheet) => {
      sheet.rel = "stylesheet";
    });
    doc.body.classList.toggle("quarto-dark", wantsDark);
    doc.body.classList.toggle("quarto-light", !wantsDark);
    doc.querySelectorAll(".quarto-color-scheme-toggle").forEach((toggle) => {
      toggle.classList.toggle("alternate", wantsDark);
    });
    win.dispatchEvent(new win.Event("resize"));
  };

  const applyTheme = (theme, button, doc, win) => {
    const normalized = normalizeTheme(theme) || "light";
    setQuartoColorScheme(normalized, doc, win);
    writeTheme(localStorageFor(win), normalized);
    updateThemeButton(button, normalized);
  };

  const mountThemeToggle = (doc = document, win = window) => {
    if (doc.getElementById("textbook-theme-toggle")) return;

    const button = doc.createElement("button");
    button.id = "textbook-theme-toggle";
    button.type = "button";
    button.className = "btn textbook-theme-toggle";
    button.innerHTML = '<i class="bi" aria-hidden="true"></i>';

    const place = () => {
      const tocTitle = doc.querySelector("#TOC #toc-title");
      const useToc = Boolean(
        tocTitle && win.matchMedia("(min-width: 992px)").matches
      );
      doc.querySelectorAll(".textbook-toc-title-with-toggle").forEach((element) => {
        element.classList.remove("textbook-toc-title-with-toggle");
      });
      if (useToc) {
        tocTitle.classList.add("textbook-toc-title-with-toggle");
        tocTitle.appendChild(button);
        button.classList.add("textbook-theme-toggle-in-toc");
        button.classList.remove("textbook-theme-toggle-floating");
      } else {
        doc.body.appendChild(button);
        button.classList.add("textbook-theme-toggle-floating");
        button.classList.remove("textbook-theme-toggle-in-toc");
      }
    };

    const restoreTheme = () => {
      applyTheme(
        readStoredTheme(localStorageFor(win)) || currentTheme(doc),
        button,
        doc,
        win
      );
    };

    place();
    win.addEventListener("resize", place);
    restoreTheme();
    button.addEventListener("click", () => {
      applyTheme(nextTheme(currentTheme(doc)), button, doc, win);
    });
    win.addEventListener("pageshow", restoreTheme);
  };

  const api = Object.freeze({
    THEME_STORAGE_KEY,
    QUARTO_THEME_STORAGE_KEY,
    normalizeTheme,
    nextTheme,
    quartoThemePreference,
    updateThemeButton,
    setQuartoColorScheme,
    applyTheme,
    mountThemeToggle,
  });

  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }

  if (typeof window !== "undefined" && typeof document !== "undefined") {
    window.TextbookTheme = api;
    const mount = () => {
      try {
        mountThemeToggle(document, window);
      } catch (error) {
        console.error("[textbook] 主题切换初始化失败", error);
      }
    };
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", mount, { once: true });
    } else {
      mount();
    }
  }
})();
