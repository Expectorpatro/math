(() => {
  "use strict";

  const mountMathOverflow = () => {
    const main = document.querySelector("main.content");
    if (!main) return;

    const hintIdentifier = "textbook-math-overflow-hint";
    if (!document.getElementById(hintIdentifier)) {
      const hint = document.createElement("span");
      hint.id = hintIdentifier;
      hint.hidden = true;
      hint.textContent = "此公式可横向滚动以查看完整内容。";
      main.appendChild(hint);
    }
    const addDescription = (formula) => {
      const identifiers = new Set(
        (formula.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean),
      );
      identifiers.add(hintIdentifier);
      formula.setAttribute("aria-describedby", Array.from(identifiers).join(" "));
    };
    const removeDescription = (formula) => {
      const identifiers = (formula.getAttribute("aria-describedby") || "")
        .split(/\s+/)
        .filter((identifier) => identifier && identifier !== hintIdentifier);
      if (identifiers.length) formula.setAttribute("aria-describedby", identifiers.join(" "));
      else formula.removeAttribute("aria-describedby");
    };
    let frame = 0;
    const measure = () => {
      frame = 0;
      const formulas = [...main.querySelectorAll("span.math.inline")];
      const measurements = formulas.map((formula) => {
        const container =
          formula.closest("p, li, dd, dt, figcaption, .theorem-block, .proof-block") ||
          main;
        const formulaRect = formula.getBoundingClientRect();
        const mathRect = formula.querySelector("mjx-container")?.getBoundingClientRect();
        const containerRect = container.getBoundingClientRect();
        const containerStyle = window.getComputedStyle(container);
        const paddingRight = Number.parseFloat(containerStyle.paddingRight) || 0;
        const contentRight = containerRect.right - paddingRight;
        const availableWidth = Math.max(contentRight - formulaRect.left, 96);
        const intrinsicWidth = Math.max(
          formulaRect.width,
          mathRect?.width || 0,
          formula.scrollWidth || 0,
        );
        return {
          formula,
          availableWidth,
          overflows: intrinsicWidth > availableWidth + 1,
        };
      });
      measurements.forEach(({ formula, availableWidth, overflows }) => {
        if (overflows) {
          formula.classList.add("math-inline-overflow");
          formula.style.setProperty(
            "--math-inline-available-width",
            `${Math.floor(availableWidth)}px`
          );
          if (!formula.hasAttribute("tabindex")) {
            formula.tabIndex = 0;
            formula.dataset.mathOverflowTabindex = "true";
          }
          addDescription(formula);
          return;
        }
        formula.classList.remove("math-inline-overflow");
        formula.style.removeProperty("--math-inline-available-width");
        if (formula.dataset.mathOverflowTabindex === "true") {
          formula.removeAttribute("tabindex");
          delete formula.dataset.mathOverflowTabindex;
        }
        removeDescription(formula);
      });
    };
    const schedule = () => {
      window.cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(measure);
    };

    const mathReady = window.MathJax?.startup?.promise;
    if (mathReady && typeof mathReady.then === "function") {
      mathReady.then(schedule, schedule);
    } else {
      const observer = new MutationObserver(() => {
        if (!main.querySelector("span.math.inline mjx-container")) return;
        observer.disconnect();
        schedule();
      });
      observer.observe(main, { childList: true, subtree: true });
      window.setTimeout(() => {
        observer.disconnect();
        schedule();
      }, 2000);
    }
    if ("ResizeObserver" in window) {
      const observer = new ResizeObserver(schedule);
      observer.observe(main);
    } else {
      window.addEventListener("resize", schedule, { passive: true });
    }
    if (document.fonts?.ready) document.fonts.ready.then(schedule, schedule);
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

  const mountRecentCommits = () => {
    const lists = Array.from(document.querySelectorAll(".home-commits"));
    const repository = document.querySelector('meta[name="textbook-repository"]')?.content;
    if (!lists.length || !/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repository || "")) {
      return;
    }

    const createCommitItem = (commit) => {
      const hash = typeof commit?.sha === "string" ? commit.sha : "";
      const url = typeof commit?.html_url === "string" ? commit.html_url : "";
      const message = typeof commit?.commit?.message === "string"
        ? commit.commit.message.split(/\r?\n/, 1)[0].trim()
        : "";
      const rawDate = commit?.commit?.author?.date;
      const date = typeof rawDate === "string" ? rawDate.slice(0, 10) : "";
      if (!hash || !url || !message || !/^\d{4}-\d{2}-\d{2}$/.test(date)) {
        return null;
      }

      const item = document.createElement("li");
      const link = document.createElement("a");
      const code = document.createElement("code");
      const subject = document.createElement("span");
      const time = document.createElement("time");
      link.href = url;
      code.textContent = hash.slice(0, 7);
      subject.textContent = message;
      time.dateTime = date;
      time.textContent = date;
      link.append(code, subject, time);
      item.appendChild(link);
      return item;
    };

    lists.forEach((list) => list.setAttribute("aria-busy", "true"));
    fetch(`https://api.github.com/repos/${repository}/commits?sha=main&per_page=3`, {
      headers: { Accept: "application/vnd.github+json" },
      cache: "no-store",
    })
      .then((response) => {
        if (!response.ok) throw new Error(`GitHub commits request failed: ${response.status}`);
        return response.json();
      })
      .then((commits) => {
        if (!Array.isArray(commits)) return;
        lists.forEach((list) => {
          const items = commits.map(createCommitItem).filter(Boolean);
          if (!items.length) return;
          list.replaceChildren(...items);
          list.dataset.source = "github";
        });
      })
      .catch(() => {
        // Keep the build-time list visible when offline or rate-limited.
      })
      .finally(() => {
        lists.forEach((list) => list.removeAttribute("aria-busy"));
      });
  };

  const mount = () => {
    const initializers = [
      ["公式溢出", mountMathOverflow],
      ["问题反馈", mountIssueLink],
      ["最近提交", mountRecentCommits],
    ];
    initializers.forEach(([name, initialize]) => {
      try {
        initialize();
      } catch (error) {
        console.error(`[textbook] ${name}初始化失败`, error);
      }
    });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount, { once: true });
  } else {
    mount();
  }
})();
