(() => {
  "use strict";

  const distributionApi = globalThis.TextbookDensityDistributions;
  const renderer = globalThis.TextbookDensityRenderer;
  if (!distributionApi || !renderer) {
    console.error("[textbook] 密度图界面依赖未加载");
    return;
  }
  const { distributions, formatValue } = distributionApi;
  const { drawCurve, svgElement } = renderer;
  let chartCounter = 0;

  function updateText(element, value) {
    if (element.textContent !== value) element.textContent = value;
  }

  function valuesFromInputs(inputs) {
    const values = {};
    for (const [key, input] of inputs.entries()) {
      values[key] = input.value.trim() === "" ? Number.NaN : Number(input.value);
    }
    return values;
  }

  function clampParameter(value, parameter) {
    return Math.min(Math.max(value, parameter.min), parameter.max);
  }

  function syncParameterInputs(parameter, number, range, commit = false) {
    if (number.value === "") return;
    const value = Number(number.value);
    if (!Number.isFinite(value)) return;
    const clamped = clampParameter(value, parameter);
    if (commit && clamped !== value) number.value = String(clamped);
    range.value = String(clamped);
  }

  function actionButton(label, className = "density-plot__action") {
    const button = document.createElement("button");
    button.type = "button";
    button.className = className;
    button.textContent = label;
    return button;
  }

  function initializePlot(container) {
    const name = container.dataset.distribution;
    const specification = distributions[name];
    if (!specification || container.dataset.densityInitialized === "true") return;
    container.dataset.densityInitialized = "true";
    const chartIdentifier = ++chartCounter;

    const heading = document.createElement("div");
    heading.className = "density-plot__heading";
    const title = document.createElement("strong");
    title.id = `density-plot-heading-${chartIdentifier}`;
    const headingActions = document.createElement("div");
    headingActions.className = "density-plot__heading-actions";
    const mode = document.createElement("select");
    mode.className = "density-plot__mode";
    mode.setAttribute("aria-label", "选择函数类型");
    mode.append(new Option("密度函数 PDF", "density"), new Option("分布函数 CDF", "cdf"));
    const scale = actionButton("固定坐标");
    scale.setAttribute("aria-pressed", "false");
    const freeze = actionButton("保留曲线");
    const clear = actionButton("清除对比");
    clear.disabled = true;
    const reset = actionButton("恢复默认", "density-plot__reset");
    headingActions.append(mode, scale, freeze, clear, reset);
    heading.append(title, headingActions);

    const controls = document.createElement("div");
    controls.className = "density-plot__controls";
    const inputs = new Map();
    const ranges = new Map();

    for (const parameter of specification.parameters) {
      const group = document.createElement("div");
      group.className = "density-plot__control";
      const identifier = `density-${name}-${chartIdentifier}-${parameter.key}`;
      const label = document.createElement("label");
      label.id = `${identifier}-label`;
      label.htmlFor = identifier;
      label.textContent = parameter.label;
      const range = document.createElement("input");
      range.type = "range";
      range.id = `${identifier}-range`;
      range.min = parameter.min;
      range.max = parameter.max;
      range.step = parameter.step;
      range.value = parameter.defaultValue;
      range.setAttribute("aria-labelledby", label.id);
      const number = document.createElement("input");
      number.type = "number";
      number.id = identifier;
      number.min = parameter.min;
      number.max = parameter.max;
      number.step = parameter.step;
      number.value = parameter.defaultValue;
      number.inputMode = "decimal";
      const hint = document.createElement("span");
      hint.id = `${identifier}-hint`;
      hint.className = "visually-hidden";
      hint.textContent =
        `允许范围 ${formatValue(parameter.min)} 至 ${formatValue(parameter.max)}` +
        `，步长 ${formatValue(parameter.step)}。`;
      range.setAttribute("aria-describedby", hint.id);
      number.setAttribute("aria-describedby", hint.id);
      group.setAttribute("role", "group");
      group.setAttribute("aria-labelledby", label.id);
      group.append(label, range, number, hint);
      controls.appendChild(group);
      inputs.set(parameter.key, number);
      ranges.set(parameter.key, range);
    }

    const interval = document.createElement("div");
    interval.className = "density-plot__interval-controls";
    const intervalTitle = document.createElement("span");
    intervalTitle.id = `density-plot-interval-${chartIdentifier}`;
    intervalTitle.textContent = "概率区间";
    const intervalMinimum = document.createElement("input");
    const intervalMaximum = document.createElement("input");
    const defaultSpan = specification.view.x[1] - specification.view.x[0];
    const [defaultMinimum, defaultMaximum] = specification.defaultInterval || [
      specification.view.x[0] + defaultSpan * 0.25,
      specification.view.x[0] + defaultSpan * 0.75,
    ];
    [intervalMinimum, intervalMaximum].forEach((input, index) => {
      input.type = "number";
      input.step = defaultSpan / 100;
      input.inputMode = "decimal";
      input.setAttribute("aria-label", index === 0 ? "概率区间下限" : "概率区间上限");
    });
    intervalMinimum.value = formatValue(defaultMinimum);
    intervalMaximum.value = formatValue(defaultMaximum);
    const separator = document.createElement("span");
    separator.setAttribute("aria-hidden", "true");
    separator.textContent = "≤ X ≤";
    interval.append(intervalTitle, intervalMinimum, separator, intervalMaximum);
    interval.setAttribute("role", "group");
    interval.setAttribute("aria-labelledby", intervalTitle.id);

    const summary = document.createElement("div");
    summary.className = "density-plot__summary";
    const legend = document.createElement("div");
    legend.className = "density-plot__legend";
    legend.setAttribute("role", "list");
    legend.setAttribute("aria-label", "曲线图例");
    const chart = document.createElement("div");
    chart.className = "density-plot__chart";
    const svg = svgElement("svg", {
      role: "img",
      preserveAspectRatio: "xMidYMid meet",
    });
    chart.appendChild(svg);
    const status = document.createElement("div");
    status.id = `density-plot-status-${chartIdentifier}`;
    status.className = "density-plot__status";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    status.setAttribute("aria-atomic", "true");
    const note = document.createElement("div");
    note.id = `density-plot-note-${chartIdentifier}`;
    note.className = "density-plot__note";
    svg.setAttribute("aria-describedby", `${status.id} ${note.id}`);

    container.replaceChildren(
      heading,
      controls,
      interval,
      summary,
      legend,
      chart,
      status,
      note,
    );
    container.setAttribute("role", "group");
    container.setAttribute("aria-labelledby", title.id);

    let frame = 0;
    let adaptive = false;
    let comparisons = [];

    const updateLegend = () => {
      legend.replaceChildren();
      const current = document.createElement("span");
      current.className = "density-plot__legend-item density-plot__legend-item--current";
      current.setAttribute("role", "listitem");
      current.textContent = "当前曲线";
      legend.appendChild(current);
      comparisons.forEach((item, index) => {
        const entry = document.createElement("span");
        entry.className = `density-plot__legend-item density-plot__legend-item--${index + 1}`;
        entry.setAttribute("role", "listitem");
        entry.textContent = item.label;
        legend.appendChild(entry);
      });
      clear.disabled = comparisons.length === 0;
    };

    const render = () => {
      frame = 0;
      const parameters = valuesFromInputs(inputs);
      const intervalValues = [intervalMinimum, intervalMaximum].map((input) =>
        input.value.trim() === "" ? Number.NaN : Number(input.value),
      );
      const invalidParameters = specification.parameters.filter((parameter) => {
        const value = parameters[parameter.key];
        return (
          !Number.isFinite(value) ||
          value < parameter.min ||
          value > parameter.max ||
          (parameter.integer && !Number.isInteger(value))
        );
      });
      specification.parameters.forEach((parameter) => {
        const invalid = invalidParameters.includes(parameter);
        inputs.get(parameter.key).setAttribute("aria-invalid", String(invalid));
        ranges.get(parameter.key).setAttribute("aria-invalid", String(invalid));
      });
      const invalidInterval =
        mode.value === "density" &&
        intervalValues.some((value) => !Number.isFinite(value));
      intervalMinimum.setAttribute("aria-invalid", String(invalidInterval));
      intervalMaximum.setAttribute("aria-invalid", String(invalidInterval));
      if (invalidParameters.length || invalidInterval) {
        const parameter = invalidParameters[0];
        const message = parameter
          ? parameter.integer && Number.isFinite(parameters[parameter.key])
            ? `${parameter.label} 必须是整数。`
            : `${parameter.label} 需要在 ${formatValue(parameter.min)} 至 ` +
              `${formatValue(parameter.max)} 之间。`
          : "请输入有效的参数与概率区间。";
        updateText(status, message);
        status.classList.add("density-plot__status--error");
        updateText(note, "");
        svg.replaceChildren();
        svg.setAttribute("aria-hidden", "true");
        return;
      }
      const validationMessage = specification.validate(parameters);
      if (validationMessage) {
        specification.parameters.forEach((parameter) => {
          inputs.get(parameter.key).setAttribute("aria-invalid", "true");
          ranges.get(parameter.key).setAttribute("aria-invalid", "true");
        });
        updateText(status, validationMessage);
        status.classList.add("density-plot__status--error");
        updateText(note, "");
        svg.replaceChildren();
        svg.setAttribute("aria-hidden", "true");
        return;
      }
      status.classList.remove("density-plot__status--error");
      try {
        const result = drawCurve(svg, specification, parameters, {
          adaptive,
          chartIdentifier,
          comparisons,
          interval: intervalValues,
          mode: mode.value,
          viewportWidth: chart.getBoundingClientRect().width,
        });
        svg.removeAttribute("aria-hidden");
        const functionName = mode.value === "cdf" ? "分布函数" : "密度函数";
        title.textContent = `${specification.title}${functionName}`;
        if (mode.value === "density") {
          const lower = Math.min(...intervalValues);
          const upper = Math.max(...intervalValues);
          updateText(
            status,
            `当前参数：${specification.notation(parameters)}；` +
            `P(${formatValue(lower)} ≤ X ≤ ${formatValue(upper)}) = ` +
            formatValue(result.probability),
          );
        } else {
          updateText(status, `当前参数：${specification.notation(parameters)}`);
        }

        summary.replaceChildren();
        for (const [label, value] of specification.moments(parameters)) {
          const item = document.createElement("span");
          const itemLabel = document.createElement("strong");
          itemLabel.textContent = label;
          item.append(
            itemLabel,
            ` ${typeof value === "number" ? formatValue(value) : value}`,
          );
          summary.appendChild(item);
        }

        const coordinateMode = adaptive ? "自适应观察窗" : "固定观察窗";
        const windowDescription =
          `${coordinateMode}：x ∈ [${formatValue(result.x[0])}, ${formatValue(result.x[1])}]，` +
          `${mode.value === "cdf" ? "F" : "p"}(x) ∈ ` +
          `[${formatValue(result.y[0])}, ${formatValue(result.y[1])}]。`;
        updateText(
          note,
          result.clipped
            ? `${windowDescription} 曲线或概率区间超出观察窗的部分已裁切。`
            : windowDescription,
        );
      } catch (error) {
        updateText(
          status,
          error instanceof Error ? error.message : "曲线计算失败。",
        );
        status.classList.add("density-plot__status--error");
        updateText(note, "");
        svg.replaceChildren();
        svg.setAttribute("aria-hidden", "true");
      }
    };
    const scheduleRender = () => {
      if (!frame) frame = window.requestAnimationFrame(render);
    };

    for (const parameter of specification.parameters) {
      const number = inputs.get(parameter.key);
      const range = ranges.get(parameter.key);
      range.addEventListener("input", () => {
        number.value = range.value;
        scheduleRender();
      });
      number.addEventListener("input", () => {
        syncParameterInputs(parameter, number, range);
        scheduleRender();
      });
      number.addEventListener("change", () => {
        syncParameterInputs(parameter, number, range, true);
        scheduleRender();
      });
    }
    intervalMinimum.addEventListener("input", scheduleRender);
    intervalMaximum.addEventListener("input", scheduleRender);
    mode.addEventListener("change", () => {
      interval.hidden = mode.value === "cdf";
      scheduleRender();
    });
    scale.addEventListener("click", () => {
      adaptive = !adaptive;
      scale.textContent = adaptive ? "自适应坐标" : "固定坐标";
      scale.setAttribute("aria-pressed", String(adaptive));
      scheduleRender();
    });
    freeze.addEventListener("click", () => {
      const parameters = valuesFromInputs(inputs);
      const validationMessage = specification.validate(parameters);
      const hasInvalidParameter = specification.parameters.some((parameter) => {
        const value = parameters[parameter.key];
        return (
          !Number.isFinite(value) ||
          value < parameter.min ||
          value > parameter.max ||
          (parameter.integer && !Number.isInteger(value))
        );
      });
      if (validationMessage || hasInvalidParameter) {
        updateText(status, validationMessage || "请输入有效的参数。");
        status.classList.add("density-plot__status--error");
        return;
      }
      comparisons = [
        ...comparisons,
        { parameters: { ...parameters }, label: specification.notation(parameters) },
      ].slice(-3);
      updateLegend();
      scheduleRender();
    });
    clear.addEventListener("click", () => {
      comparisons = [];
      updateLegend();
      scheduleRender();
    });
    reset.addEventListener("click", () => {
      for (const parameter of specification.parameters) {
        inputs.get(parameter.key).value = parameter.defaultValue;
        ranges.get(parameter.key).value = parameter.defaultValue;
      }
      intervalMinimum.value = formatValue(defaultMinimum);
      intervalMaximum.value = formatValue(defaultMaximum);
      mode.value = "density";
      interval.hidden = false;
      adaptive = false;
      scale.textContent = "固定坐标";
      scale.setAttribute("aria-pressed", "false");
      comparisons = [];
      updateLegend();
      scheduleRender();
    });
    if ("ResizeObserver" in window) {
      let previousWidth = 0;
      const observer = new ResizeObserver(([entry]) => {
        const width = Math.round(entry.contentRect.width);
        if (!width || Math.abs(width - previousWidth) < 4) return;
        previousWidth = width;
        scheduleRender();
      });
      observer.observe(chart);
    } else {
      window.addEventListener("resize", scheduleRender, { passive: true });
    }
    updateLegend();
    render();
  }

  const api = {
    distributions: Object.keys(distributions),
    initialize: initializePlot,
    defaults(name) {
      const specification = distributions[name];
      if (!specification) return null;
      return Object.fromEntries(
        specification.parameters.map(({ key, defaultValue }) => [key, defaultValue]),
      );
    },
    density(name, x, parameters) {
      const specification = distributions[name];
      if (!specification) throw new Error(`未知分布：${name}`);
      return specification.density(x, parameters);
    },
    cdf(name, x, parameters) {
      const specification = distributions[name];
      if (!specification) throw new Error(`未知分布：${name}`);
      return specification.cdf(x, parameters);
    },
    moments(name, parameters) {
      const specification = distributions[name];
      if (!specification) throw new Error(`未知分布：${name}`);
      return Object.fromEntries(specification.moments(parameters));
    },
    view(name) {
      const specification = distributions[name];
      return specification
        ? { x: [...specification.view.x], y: [...specification.view.y] }
        : null;
    },
  };
  globalThis.TextbookDensityPlots = api;
})();
