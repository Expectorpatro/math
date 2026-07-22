(() => {
  "use strict";

  function decodeSource(encoded) {
    const bytes = Uint8Array.from(atob(encoded), (character) => character.charCodeAt(0));
    return new TextDecoder().decode(bytes);
  }

  function legacyCopyText(text) {
    const activeElement = document.activeElement;
    const selection = document.getSelection();
    const ranges = selection
      ? Array.from({ length: selection.rangeCount }, (_item, index) =>
          selection.getRangeAt(index).cloneRange(),
        )
      : [];
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.setAttribute("aria-hidden", "true");
    textarea.tabIndex = -1;
    Object.assign(textarea.style, {
      position: "fixed",
      top: "0",
      left: "-9999px",
      opacity: "0",
    });
    document.body.appendChild(textarea);
    let copied = false;
    try {
      try {
        textarea.focus({ preventScroll: true });
      } catch (_error) {
        textarea.focus();
      }
      textarea.select();
      textarea.setSelectionRange(0, textarea.value.length);
      copied = typeof document.execCommand === "function" && document.execCommand("copy");
    } finally {
      textarea.remove();
      if (selection) {
        selection.removeAllRanges();
        ranges.forEach((range) => selection.addRange(range));
      }
      if (activeElement instanceof HTMLElement) {
        try {
          activeElement.focus({ preventScroll: true });
        } catch (_error) {
          activeElement.focus();
        }
      }
    }
    if (!copied) throw new Error("浏览器拒绝访问剪贴板");
  }

  async function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      try {
        await navigator.clipboard.writeText(text);
        return;
      } catch (_error) {
        // Permission can be denied even in a secure context; try the local fallback.
      }
    }
    legacyCopyText(text);
  }

  function initializeFormula(wrapper) {
    if (wrapper.dataset.copyReady === "true") return;
    const encoded = wrapper.dataset.sourceTex;
    if (!encoded) return;

    const button = document.createElement("button");
    button.type = "button";
    button.className = "display-math-copy-button";
    button.setAttribute("aria-label", "复制原始 LaTeX");
    button.title = "复制原始 LaTeX";
    button.innerHTML =
      '<i class="bi bi-clipboard" aria-hidden="true"></i>' +
      '<span>复制 LaTeX</span>';
    const announcement = document.createElement("span");
    announcement.className = "visually-hidden";
    announcement.setAttribute("role", "status");
    announcement.setAttribute("aria-live", "polite");
    announcement.setAttribute("aria-atomic", "true");

    let restoreTimer = 0;
    let operation = 0;
    let copying = false;
    button.addEventListener("click", async () => {
      if (copying) return;
      copying = true;
      const currentOperation = ++operation;
      window.clearTimeout(restoreTimer);
      button.setAttribute("aria-busy", "true");
      try {
        await copyText(decodeSource(encoded));
        if (currentOperation !== operation) return;
        button.classList.remove("display-math-copy-button--error");
        button.classList.add("display-math-copy-button--success");
        button.innerHTML =
          '<i class="bi bi-check2" aria-hidden="true"></i><span>已复制</span>';
        announcement.textContent = "原始 LaTeX 已复制到剪贴板。";
      } catch (_error) {
        if (currentOperation !== operation) return;
        button.classList.remove("display-math-copy-button--success");
        button.classList.add("display-math-copy-button--error");
        button.innerHTML =
          '<i class="bi bi-exclamation-triangle" aria-hidden="true"></i>' +
          '<span>复制失败</span>';
        announcement.textContent = "复制失败，请检查浏览器的剪贴板权限。";
      } finally {
        if (currentOperation === operation) {
          copying = false;
          button.removeAttribute("aria-busy");
        }
      }
      restoreTimer = window.setTimeout(() => {
        if (currentOperation !== operation) return;
        button.classList.remove(
          "display-math-copy-button--success",
          "display-math-copy-button--error",
        );
        button.innerHTML =
          '<i class="bi bi-clipboard" aria-hidden="true"></i>' +
          '<span>复制 LaTeX</span>';
        announcement.textContent = "";
      }, 1800);
    });

    wrapper.append(button, announcement);
    wrapper.dataset.copyReady = "true";
  }

  function attachMarker(marker) {
    const encoded = marker.dataset.sourceTex;
    if (!encoded) return;
    const parent = marker.parentElement;
    let math = parent
      ? Array.from(parent.querySelectorAll(".math.display")).find(
          (candidate) =>
            marker.compareDocumentPosition(candidate) & Node.DOCUMENT_POSITION_FOLLOWING,
        )
      : null;
    if (!math) {
      let candidate = parent ? parent.nextElementSibling : null;
      while (candidate && !math) {
        math = candidate.matches(".math.display")
          ? candidate
          : candidate.querySelector(".math.display");
        if (math || candidate.textContent.trim()) break;
        candidate = candidate.nextElementSibling;
      }
    }
    if (!math || math.closest(".display-math-source")) {
      marker.remove();
      return;
    }

    const wrapper = document.createElement("span");
    wrapper.className = "display-math-source";
    wrapper.dataset.sourceTex = encoded;
    math.parentNode.insertBefore(wrapper, math);
    wrapper.appendChild(math);
    marker.remove();
    if (parent && !parent.textContent.trim() && parent.children.length === 0) {
      parent.remove();
    }
    initializeFormula(wrapper);
  }

  function initializeAll() {
    const initializeSafely = (initialize) => (element) => {
      try {
        initialize(element);
      } catch (error) {
        console.error("[textbook] 公式复制控件初始化失败", error);
      }
    };
    document
      .querySelectorAll(".display-math-copy-marker[data-source-tex]")
      .forEach(initializeSafely(attachMarker));
    document
      .querySelectorAll(".display-math-source[data-source-tex]")
      .forEach(initializeSafely(initializeFormula));
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeAll, { once: true });
  } else {
    initializeAll();
  }
})();
