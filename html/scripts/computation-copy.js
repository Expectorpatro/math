(() => {
  "use strict";

  const copyText = async (value) => {
    if (navigator.clipboard && window.isSecureContext) {
      try {
        await navigator.clipboard.writeText(value);
        return;
      } catch (_error) {
        // Fall through to the selection-based copy path.
      }
    }

    const textarea = document.createElement("textarea");
    textarea.value = value;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.inset = "-9999px auto auto -9999px";
    document.body.appendChild(textarea);
    textarea.select();
    const copied =
      typeof document.execCommand === "function" &&
      document.execCommand("copy");
    textarea.remove();
    if (!copied) throw new Error("浏览器拒绝复制");
  };

  const sourceText = (sourceCode) => {
    const code = sourceCode.querySelector("pre > code");
    if (!code) return "";
    return code.textContent
      .replace(/\r\n?/g, "\n")
      .replace(/\u00a0/g, " ")
      .replace(/\n+$/, "");
  };

  const setIconButtonState = (button, state) => {
    window.clearTimeout(Number(button.dataset.resetTimer || 0));
    button.dataset.copyState = state;
    const label =
      state === "success"
        ? "代码已复制"
        : state === "error"
          ? "复制失败"
          : "复制这段代码";
    const icon =
      state === "success"
        ? "bi-check2"
        : state === "error"
          ? "bi-exclamation-lg"
          : "bi-clipboard";
    button.title = label;
    button.setAttribute("aria-label", label);
    button.innerHTML = `<i class="bi ${icon}" aria-hidden="true"></i>`;
    if (state !== "idle") {
      button.dataset.resetTimer = String(
        window.setTimeout(() => setIconButtonState(button, "idle"), 1800)
      );
    }
  };

  const setResultButtonState = (button, state) => {
    window.clearTimeout(Number(button.dataset.resetTimer || 0));
    button.dataset.copyState = state;
    const label =
      state === "success"
        ? "已复制全部代码"
        : state === "error"
          ? "复制失败"
          : "复制本实验全部代码";
    const icon =
      state === "success"
        ? "bi-check2"
        : state === "error"
          ? "bi-exclamation-lg"
          : "bi-clipboard";
    button.setAttribute("aria-label", label);
    button.title = label;
    button.innerHTML =
      `<i class="bi ${icon}" aria-hidden="true"></i>` +
      `<span>${label}</span>`;
    if (state !== "idle") {
      button.dataset.resetTimer = String(
        window.setTimeout(() => setResultButtonState(button, "idle"), 2200)
      );
    }
  };

  const bindCopy = (button, getText, setState) => {
    if (button.dataset.textbookCopyReady === "true") return;
    button.dataset.textbookCopyReady = "true";
    button.addEventListener(
      "click",
      async (event) => {
        event.preventDefault();
        event.stopImmediatePropagation();
        const value = getText();
        if (!value) {
          setState(button, "error");
          return;
        }
        try {
          await copyText(value);
          setState(button, "success");
        } catch (_error) {
          setState(button, "error");
        }
      },
      { capture: true }
    );
  };

  const mountBlockCopy = (sourceCode) => {
    let scaffold = sourceCode.parentElement;
    if (!scaffold?.classList.contains("code-copy-outer-scaffold")) {
      scaffold = document.createElement("div");
      scaffold.className = "code-copy-outer-scaffold";
      sourceCode.before(scaffold);
      scaffold.appendChild(sourceCode);
    }

    const pre = sourceCode.querySelector("pre");
    if (pre) pre.classList.add("code-with-copy");

    let button = Array.from(scaffold.children).find((child) =>
      child.classList.contains("code-copy-button")
    );
    if (!button) {
      button = document.createElement("button");
      button.type = "button";
      button.className = "code-copy-button";
      scaffold.appendChild(button);
    }
    button.type = "button";
    setIconButtonState(button, "idle");
    bindCopy(
      button,
      () => sourceText(sourceCode),
      setIconButtonState
    );
  };

  const mountResultCopy = (result) => {
    const sourceCodes = Array.from(
      result.querySelectorAll("div.sourceCode")
    ).filter((sourceCode) => sourceText(sourceCode));
    if (!sourceCodes.length) return;

    const label = result.querySelector(":scope > .computation-result-label");
    if (!label || label.querySelector(".computation-copy-all-button")) return;
    label.classList.add("computation-result-label--with-copy");

    const button = document.createElement("button");
    button.type = "button";
    button.className = "computation-copy-all-button";
    setResultButtonState(button, "idle");
    bindCopy(
      button,
      () => sourceCodes.map(sourceText).join("\n\n"),
      setResultButtonState
    );
    label.appendChild(button);
  };

  const mount = () => {
    document
      .querySelectorAll(".computation-result div.sourceCode")
      .forEach(mountBlockCopy);
    document
      .querySelectorAll(".computation-result")
      .forEach(mountResultCopy);
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount, { once: true });
  } else {
    mount();
  }
})();
