(() => {
  "use strict";

  function decodeSource(encoded) {
    const bytes = Uint8Array.from(atob(encoded), (character) => character.charCodeAt(0));
    return new TextDecoder().decode(bytes);
  }

  async function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return;
    }
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    const copied = document.execCommand("copy");
    textarea.remove();
    if (!copied) throw new Error("浏览器拒绝访问剪贴板");
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

    let restoreTimer = 0;
    button.addEventListener("click", async () => {
      window.clearTimeout(restoreTimer);
      try {
        await copyText(decodeSource(encoded));
        button.classList.remove("display-math-copy-button--error");
        button.classList.add("display-math-copy-button--success");
        button.innerHTML =
          '<i class="bi bi-check2" aria-hidden="true"></i><span>已复制</span>';
      } catch (error) {
        button.classList.remove("display-math-copy-button--success");
        button.classList.add("display-math-copy-button--error");
        button.innerHTML =
          '<i class="bi bi-exclamation-triangle" aria-hidden="true"></i>' +
          '<span>复制失败</span>';
      }
      restoreTimer = window.setTimeout(() => {
        button.classList.remove(
          "display-math-copy-button--success",
          "display-math-copy-button--error",
        );
        button.innerHTML =
          '<i class="bi bi-clipboard" aria-hidden="true"></i>' +
          '<span>复制 LaTeX</span>';
      }, 1800);
    });

    wrapper.appendChild(button);
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
    document.querySelectorAll(".display-math-copy-marker[data-source-tex]").forEach(
      attachMarker,
    );
    document.querySelectorAll(".display-math-source[data-source-tex]").forEach(
      initializeFormula,
    );
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeAll, { once: true });
  } else {
    initializeAll();
  }
})();
