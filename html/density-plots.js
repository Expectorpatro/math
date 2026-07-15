(() => {
  "use strict";

  const SVG_NS = "http://www.w3.org/2000/svg";
  const {
    SQRT_TWO_PI,
    clampProbability,
    expFromLog,
    logBeta,
    logGamma,
    noncentralChiSquareCDF,
    noncentralChiSquareDensity,
    normalCDF,
    regularizedBeta,
    regularizedGammaP,
  } = globalThis.TextbookDensityMath;
  let chartCounter = 0;

  const distributions = {
    uniform: {
      title: "均匀分布",
      parameters: [
        { key: "a", label: "a", defaultValue: 0, min: -10, max: 10, step: 0.25 },
        { key: "b", label: "b", defaultValue: 1, min: -10, max: 10, step: 0.25 },
      ],
      validate: ({ a, b }) => (a < b ? "" : "需要满足 a < b。"),
      notation: ({ a, b }) => `U(${formatValue(a)}, ${formatValue(b)})`,
      view: { x: [-10, 10], y: [0, 2.2] },
      defaultInterval: [0.25, 0.75],
      autoView: ({ a, b }) => {
        const padding = Math.max(0.5, (b - a) * 0.25);
        return [a - padding, b + padding];
      },
      density: (x, { a, b }) => (x >= a && x <= b ? 1 / (b - a) : 0),
      cdf: (x, { a, b }) =>
        x <= a ? 0 : x >= b ? 1 : (x - a) / (b - a),
      moments: ({ a, b }) => [
        ["期望", (a + b) / 2],
        ["方差", ((b - a) ** 2) / 12],
      ],
    },
    normal: {
      title: "一元正态分布",
      parameters: [
        { key: "mu", label: "μ", defaultValue: 0, min: -10, max: 10, step: 0.25 },
        { key: "variance", label: "σ²", defaultValue: 1, min: 0.25, max: 25, step: 0.25 },
      ],
      validate: ({ variance }) => (variance > 0 ? "" : "需要满足 σ² > 0。"),
      notation: ({ mu, variance }) =>
        `N(${formatValue(mu)}, ${formatValue(variance)})`,
      view: { x: [-15, 15], y: [0, 0.85] },
      defaultInterval: [-1, 1],
      autoView: ({ mu, variance }) => {
        const standardDeviation = Math.sqrt(variance);
        return [mu - 5 * standardDeviation, mu + 5 * standardDeviation];
      },
      density: (x, { mu, variance }) =>
        Math.exp(-((x - mu) ** 2) / (2 * variance)) /
        (SQRT_TWO_PI * Math.sqrt(variance)),
      cdf: (x, { mu, variance }) => normalCDF(x, mu, variance),
      moments: ({ mu, variance }) => [
        ["期望", mu],
        ["方差", variance],
      ],
    },
    "chi-square": {
      title: "非中心 χ² 分布",
      parameters: [
        { key: "n", label: "n", defaultValue: 4, min: 1, max: 60, step: 1, integer: true },
        { key: "lambda", label: "λ", defaultValue: 0, min: 0, max: 60, step: 0.5 },
      ],
      validate: ({ n, lambda }) => {
        if (!Number.isInteger(n) || n < 1) return "n 必须是正整数。";
        return lambda >= 0 ? "" : "需要满足 λ ≥ 0。";
      },
      notation: ({ n, lambda }) =>
        `χ²(n=${formatValue(n)}, λ=${formatValue(lambda)})`,
      view: { x: [0, 140], y: [0, 0.55] },
      defaultInterval: [2, 6],
      autoView: ({ n, lambda }) => [
        0,
        n + lambda + 6 * Math.sqrt(2 * (n + 2 * lambda)),
      ],
      density: (x, { n, lambda }) => noncentralChiSquareDensity(x, n, lambda),
      cdf: (x, { n, lambda }) => noncentralChiSquareCDF(x, n, lambda),
      moments: ({ n, lambda }) => [
        ["期望", n + lambda],
        ["方差", 2 * (n + 2 * lambda)],
      ],
    },
    "student-t": {
      title: "Student t 分布",
      parameters: [
        { key: "n", label: "n", defaultValue: 5, min: 1, max: 200, step: 1, integer: true },
      ],
      validate: ({ n }) =>
        Number.isInteger(n) && n >= 1 ? "" : "n 必须是正整数。",
      notation: ({ n }) => `t(${formatValue(n)})`,
      view: { x: [-8, 8], y: [0, 0.42] },
      defaultInterval: [-1, 1],
      density: (x, { n }) =>
        expFromLog(
          logGamma((n + 1) / 2) -
          logGamma(n / 2) -
          0.5 * Math.log(n * Math.PI) -
          ((n + 1) / 2) * Math.log1p((x * x) / n),
        ),
      cdf: (x, { n }) => {
        if (x === 0) return 0.5;
        const betaValue = regularizedBeta(n / (n + x * x), n / 2, 0.5);
        return x > 0 ? 1 - betaValue / 2 : betaValue / 2;
      },
      moments: ({ n }) => [
        ["期望", n > 1 ? 0 : "不存在"],
        ["方差", n > 2 ? n / (n - 2) : "不存在"],
      ],
    },
    f: {
      title: "F 分布",
      parameters: [
        { key: "m", label: "m", defaultValue: 5, min: 1, max: 100, step: 1, integer: true },
        { key: "n", label: "n", defaultValue: 10, min: 1, max: 100, step: 1, integer: true },
      ],
      validate: ({ m, n }) =>
        Number.isInteger(m) && m >= 1 && Number.isInteger(n) && n >= 1
          ? ""
          : "m、n 必须是正整数。",
      notation: ({ m, n }) => `F(${formatValue(m)}, ${formatValue(n)})`,
      view: { x: [0, 6], y: [0, 2.2] },
      defaultInterval: [0.5, 2],
      density: (x, { m, n }) => {
        if (x < 0) return 0;
        const exponent = m / 2 - 1;
        const logConstant = (m / 2) * Math.log(m / n) - logBeta(m / 2, n / 2);
        if (x === 0) {
          if (exponent < 0) return Number.POSITIVE_INFINITY;
          if (exponent === 0) return Math.exp(logConstant);
          return 0;
        }
        return expFromLog(
          logConstant +
          exponent * Math.log(x) -
          ((m + n) / 2) * Math.log1p((m * x) / n),
        );
      },
      cdf: (x, { m, n }) =>
        x <= 0
          ? 0
          : regularizedBeta((m * x) / (n + m * x), m / 2, n / 2),
      moments: ({ m, n }) => [
        ["期望", n > 2 ? n / (n - 2) : "不存在"],
        [
          "方差",
          n > 4
            ? (2 * n * n * (m + n - 2)) /
              (m * ((n - 2) ** 2) * (n - 4))
            : "不存在",
        ],
      ],
    },
    gamma: {
      title: "Gamma 分布（λ 为率参数）",
      parameters: [
        { key: "alpha", label: "α", defaultValue: 3, min: 0.1, max: 25, step: 0.1 },
        { key: "lambda", label: "λ", defaultValue: 1, min: 0.1, max: 10, step: 0.1 },
      ],
      validate: ({ alpha, lambda }) =>
        alpha > 0 && lambda > 0 ? "" : "需要满足 α > 0 且 λ > 0。",
      notation: ({ alpha, lambda }) =>
        `Gamma(${formatValue(alpha)}, ${formatValue(lambda)})`,
      view: { x: [0, 30], y: [0, 3] },
      defaultInterval: [1, 5],
      autoView: ({ alpha, lambda }) => [
        0,
        alpha / lambda + (6 * Math.sqrt(alpha)) / lambda,
      ],
      density: (x, { alpha, lambda }) => {
        if (x < 0) return 0;
        if (x === 0) {
          if (alpha < 1) return Number.POSITIVE_INFINITY;
          if (alpha === 1) return lambda;
          return 0;
        }
        return expFromLog(
          alpha * Math.log(lambda) -
          logGamma(alpha) +
          (alpha - 1) * Math.log(x) -
          lambda * x,
        );
      },
      cdf: (x, { alpha, lambda }) =>
        x <= 0 ? 0 : regularizedGammaP(alpha, lambda * x),
      moments: ({ alpha, lambda }) => [
        ["期望", alpha / lambda],
        ["方差", alpha / (lambda ** 2)],
      ],
    },
    beta: {
      title: "Beta 分布",
      parameters: [
        { key: "a", label: "a", defaultValue: 2, min: 0.1, max: 25, step: 0.1 },
        { key: "b", label: "b", defaultValue: 5, min: 0.1, max: 25, step: 0.1 },
      ],
      validate: ({ a, b }) => (a > 0 && b > 0 ? "" : "需要满足 a > 0 且 b > 0。"),
      notation: ({ a, b }) => `Beta(${formatValue(a)}, ${formatValue(b)})`,
      view: { x: [0, 1], y: [0, 5] },
      defaultInterval: [0.2, 0.8],
      density: (x, { a, b }) => {
        if (x < 0 || x > 1) return 0;
        if (x === 0) {
          if (a < 1) return Number.POSITIVE_INFINITY;
          if (a === 1) return Math.exp(-logBeta(a, b));
          return 0;
        }
        if (x === 1) {
          if (b < 1) return Number.POSITIVE_INFINITY;
          if (b === 1) return Math.exp(-logBeta(a, b));
          return 0;
        }
        return expFromLog(
          (a - 1) * Math.log(x) +
          (b - 1) * Math.log1p(-x) -
          logBeta(a, b),
        );
      },
      cdf: (x, { a, b }) => regularizedBeta(x, a, b),
      moments: ({ a, b }) => [
        ["期望", a / (a + b)],
        ["方差", (a * b) / (((a + b) ** 2) * (a + b + 1))],
      ],
    },
  };

  function formatValue(value) {
    if (!Number.isFinite(value)) return "—";
    if (Math.abs(value) >= 1000 || (Math.abs(value) > 0 && Math.abs(value) < 0.001)) {
      return value.toExponential(2);
    }
    return Number(value.toFixed(4)).toString();
  }

  function svgElement(name, attributes = {}, text = "") {
    const element = document.createElementNS(SVG_NS, name);
    for (const [key, value] of Object.entries(attributes)) {
      element.setAttribute(key, String(value));
    }
    if (text) element.textContent = text;
    return element;
  }

  function valuesFromInputs(inputs) {
    const values = {};
    for (const [key, input] of inputs.entries()) {
      values[key] = Number(input.value);
    }
    return values;
  }

  function curvePath(points) {
    return points
      .map(
        ({ x, y }, index) =>
          `${index === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`,
      )
      .join(" ");
  }

  function drawCurve(svg, specification, parameters, options) {
    const width = 760;
    const height = 420;
    const margin = { top: 24, right: 24, bottom: 58, left: 72 };
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    const allParameterSets = [
      ...options.comparisons.map((item) => item.parameters),
      parameters,
    ];
    let [xMinimum, xMaximum] = specification.view.x;
    if (options.adaptive && specification.autoView) {
      const views = allParameterSets.map(specification.autoView);
      xMinimum = Math.min(...views.map((view) => view[0]));
      xMaximum = Math.max(...views.map((view) => view[1]));
    }
    const span = xMaximum - xMinimum;
    const pointCount = 480;
    const evaluator = options.mode === "cdf" ? specification.cdf : specification.density;

    const sample = (parameterSet) => {
      const points = [];
      for (let index = 0; index < pointCount; index += 1) {
        const x = xMinimum + (index / (pointCount - 1)) * span;
        let evaluationPoint = x;
        if (options.mode === "density") {
          if (index === 0 && xMinimum === 0) evaluationPoint += span * 1e-6;
          if (
            index === pointCount - 1 &&
            xMaximum === 1 &&
            specification === distributions.beta
          ) {
            evaluationPoint -= span * 1e-6;
          }
        }
        points.push({ x, y: evaluator(evaluationPoint, parameterSet) });
      }
      return points;
    };

    const sampledComparisons = options.comparisons.map((item) => ({
      ...item,
      points: sample(item.parameters),
    }));
    const points = sample(parameters);
    const finiteValues = [...sampledComparisons.flatMap((item) => item.points), ...points]
      .map((point) => point.y)
      .filter((value) => Number.isFinite(value) && value >= 0);
    if (finiteValues.length === 0) throw new Error("当前参数下无法计算有限函数值。");

    const yMinimum = 0;
    let yMaximum = options.mode === "cdf" ? 1 : specification.view.y[1];
    if (options.adaptive && options.mode === "density") {
      yMaximum = Math.max(...finiteValues) * 1.08;
      if (!Number.isFinite(yMaximum) || yMaximum <= 0) yMaximum = 1;
    }
    const clipped = points.some(
      ({ y }) => !Number.isFinite(y) || y < yMinimum || y > yMaximum,
    );

    svg.replaceChildren();
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    const modeLabel = options.mode === "cdf" ? "分布函数" : "密度函数";
    svg.appendChild(svgElement("title", {}, `${specification.title}${modeLabel}曲线`));

    const clipIdentifier = `density-plot-clip-${chartCounter}`;
    const definitions = svgElement("defs");
    const clipPath = svgElement("clipPath", { id: clipIdentifier });
    clipPath.appendChild(
      svgElement("rect", {
        x: margin.left,
        y: margin.top,
        width: plotWidth,
        height: plotHeight,
      }),
    );
    definitions.appendChild(clipPath);
    svg.appendChild(definitions);

    const xScale = (x) => margin.left + ((x - xMinimum) / span) * plotWidth;
    const yScale = (y) =>
      margin.top +
      plotHeight -
      ((Math.min(Math.max(y, yMinimum), yMaximum) - yMinimum) /
        (yMaximum - yMinimum)) *
        plotHeight;

    const grid = svgElement("g", { class: "density-plot__grid" });
    for (let tick = 0; tick <= 5; tick += 1) {
      const x = margin.left + (tick / 5) * plotWidth;
      grid.appendChild(
        svgElement("line", {
          x1: x,
          x2: x,
          y1: margin.top,
          y2: margin.top + plotHeight,
        }),
      );
      grid.appendChild(
        svgElement(
          "text",
          { x, y: margin.top + plotHeight + 25, "text-anchor": "middle" },
          formatValue(xMinimum + (tick / 5) * span),
        ),
      );
    }
    for (let tick = 0; tick <= 4; tick += 1) {
      const y = margin.top + plotHeight - (tick / 4) * plotHeight;
      grid.appendChild(
        svgElement("line", {
          x1: margin.left,
          x2: margin.left + plotWidth,
          y1: y,
          y2: y,
        }),
      );
      grid.appendChild(
        svgElement(
          "text",
          { x: margin.left - 12, y: y + 4, "text-anchor": "end" },
          formatValue(yMinimum + (tick / 4) * (yMaximum - yMinimum)),
        ),
      );
    }
    svg.appendChild(grid);

    const axes = svgElement("g", { class: "density-plot__axes" });
    axes.appendChild(
      svgElement("line", {
        x1: margin.left,
        x2: margin.left + plotWidth,
        y1: margin.top + plotHeight,
        y2: margin.top + plotHeight,
      }),
    );
    axes.appendChild(
      svgElement("line", {
        x1: margin.left,
        x2: margin.left,
        y1: margin.top,
        y2: margin.top + plotHeight,
      }),
    );
    axes.appendChild(
      svgElement(
        "text",
        { x: margin.left + plotWidth / 2, y: height - 12, "text-anchor": "middle" },
        "x",
      ),
    );
    axes.appendChild(
      svgElement(
        "text",
        {
          x: 18,
          y: margin.top + plotHeight / 2,
          transform: `rotate(-90 18 ${margin.top + plotHeight / 2})`,
          "text-anchor": "middle",
        },
        options.mode === "cdf" ? "F(x)" : "p(x)",
      ),
    );
    svg.appendChild(axes);

    const curves = svgElement("g", { "clip-path": `url(#${clipIdentifier})` });
    const intervalMinimum = Math.min(options.interval[0], options.interval[1]);
    const intervalMaximum = Math.max(options.interval[0], options.interval[1]);
    if (options.mode === "density") {
      const visibleIntervalMinimum = Math.max(xMinimum, intervalMinimum);
      const visibleIntervalMaximum = Math.min(xMaximum, intervalMaximum);
      if (visibleIntervalMinimum <= visibleIntervalMaximum) {
        curves.appendChild(
          svgElement("rect", {
            class: "density-plot__interval-band",
            x: xScale(visibleIntervalMinimum),
            y: margin.top,
            width: Math.max(
              0,
              xScale(visibleIntervalMaximum) - xScale(visibleIntervalMinimum),
            ),
            height: plotHeight,
          }),
        );
      }
    }

    const mappedCurrent = points.map(({ x, y }) => ({
      x: xScale(x),
      y: yScale(Number.isFinite(y) && y >= 0 ? y : yMaximum),
      sourceX: x,
    }));
    if (options.mode === "density") {
      const intervalPoints = mappedCurrent.filter(
        (point) => point.sourceX >= intervalMinimum && point.sourceX <= intervalMaximum,
      );
      if (intervalPoints.length >= 2) {
        const intervalCurve = curvePath(intervalPoints);
        const intervalArea = [
          `M${intervalPoints[0].x.toFixed(2)},${(margin.top + plotHeight).toFixed(2)}`,
          intervalCurve.replace(/^M/, "L"),
          `L${intervalPoints[intervalPoints.length - 1].x.toFixed(2)},${(margin.top + plotHeight).toFixed(2)}`,
          "Z",
        ].join(" ");
        curves.appendChild(
          svgElement("path", { class: "density-plot__interval-area", d: intervalArea }),
        );
      }
    }

    const comparisonColors = ["#c26b4a", "#65945f", "#8c65ad"];
    sampledComparisons.forEach((item, index) => {
      const mapped = item.points.map(({ x, y }) => ({
        x: xScale(x),
        y: yScale(Number.isFinite(y) && y >= 0 ? y : yMaximum),
      }));
      curves.appendChild(
        svgElement("path", {
          class: "density-plot__curve density-plot__curve--comparison",
          d: curvePath(mapped),
          style: `--comparison-color:${comparisonColors[index % comparisonColors.length]}`,
        }),
      );
    });

    const currentPath = curvePath(mappedCurrent);
    if (options.mode === "density") {
      const areaPath = [
        `M${mappedCurrent[0].x.toFixed(2)},${(margin.top + plotHeight).toFixed(2)}`,
        currentPath.replace(/^M/, "L"),
        `L${mappedCurrent[mappedCurrent.length - 1].x.toFixed(2)},${(margin.top + plotHeight).toFixed(2)}`,
        "Z",
      ].join(" ");
      curves.appendChild(svgElement("path", { class: "density-plot__area", d: areaPath }));
    }
    curves.appendChild(svgElement("path", { class: "density-plot__curve", d: currentPath }));

    if (options.mode === "density") {
      [intervalMinimum, intervalMaximum].forEach((boundary) => {
        if (boundary < xMinimum || boundary > xMaximum) return;
        curves.appendChild(
          svgElement("line", {
            class: "density-plot__interval-boundary",
            x1: xScale(boundary),
            x2: xScale(boundary),
            y1: margin.top,
            y2: margin.top + plotHeight,
          }),
        );
      });
    }
    svg.appendChild(curves);
    globalThis.TextbookDensityProbe.install(svg, {
      evaluate: (x) => evaluator(x, parameters),
      mode: options.mode,
      x: [xMinimum, xMaximum],
      y: [yMinimum, yMaximum],
    });

    return {
      clipped,
      probability:
        options.mode === "density"
          ? clampProbability(
              specification.cdf(intervalMaximum, parameters) -
                specification.cdf(intervalMinimum, parameters),
            )
          : null,
      x: [xMinimum, xMaximum],
      y: [yMinimum, yMaximum],
    };
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
    if (!specification) return;
    chartCounter += 1;

    const heading = document.createElement("div");
    heading.className = "density-plot__heading";
    const title = document.createElement("strong");
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
      const identifier = `density-${name}-${chartCounter}-${parameter.key}`;
      const label = document.createElement("label");
      label.htmlFor = identifier;
      label.textContent = parameter.label;
      const range = document.createElement("input");
      range.type = "range";
      range.min = parameter.min;
      range.max = parameter.max;
      range.step = parameter.step;
      range.value = parameter.defaultValue;
      range.setAttribute("aria-label", `${parameter.label} 滑块`);
      const number = document.createElement("input");
      number.type = "number";
      number.id = identifier;
      number.min = parameter.min;
      number.max = parameter.max;
      number.step = parameter.step;
      number.value = parameter.defaultValue;
      number.inputMode = "decimal";
      group.append(label, range, number);
      controls.appendChild(group);
      inputs.set(parameter.key, number);
      ranges.set(parameter.key, range);
    }

    const interval = document.createElement("div");
    interval.className = "density-plot__interval-controls";
    const intervalTitle = document.createElement("span");
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
    separator.textContent = "≤ X ≤";
    interval.append(intervalTitle, intervalMinimum, separator, intervalMaximum);

    const summary = document.createElement("div");
    summary.className = "density-plot__summary";
    const legend = document.createElement("div");
    legend.className = "density-plot__legend";
    legend.setAttribute("aria-label", "曲线图例");
    const chart = document.createElement("div");
    chart.className = "density-plot__chart";
    const svg = svgElement("svg", {
      role: "img",
      preserveAspectRatio: "xMidYMid meet",
    });
    chart.appendChild(svg);
    const status = document.createElement("div");
    status.className = "density-plot__status";
    status.setAttribute("aria-live", "polite");
    const note = document.createElement("div");
    note.className = "density-plot__note";

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
    container.setAttribute("aria-label", `${specification.title}交互曲线`);

    let frame = 0;
    let adaptive = false;
    let comparisons = [];

    const updateLegend = () => {
      legend.replaceChildren();
      const current = document.createElement("span");
      current.className = "density-plot__legend-item density-plot__legend-item--current";
      current.textContent = "当前曲线";
      legend.appendChild(current);
      comparisons.forEach((item, index) => {
        const entry = document.createElement("span");
        entry.className = `density-plot__legend-item density-plot__legend-item--${index + 1}`;
        entry.textContent = item.label;
        legend.appendChild(entry);
      });
      clear.disabled = comparisons.length === 0;
    };

    const render = () => {
      frame = 0;
      const parameters = valuesFromInputs(inputs);
      const intervalValues = [Number(intervalMinimum.value), Number(intervalMaximum.value)];
      if (
        Object.values(parameters).some((value) => !Number.isFinite(value)) ||
        (mode.value === "density" &&
          intervalValues.some((value) => !Number.isFinite(value)))
      ) {
        status.textContent = "请输入有效的参数与概率区间。";
        status.classList.add("density-plot__status--error");
        note.textContent = "";
        svg.replaceChildren();
        return;
      }
      const validationMessage = specification.validate(parameters);
      if (validationMessage) {
        status.textContent = validationMessage;
        status.classList.add("density-plot__status--error");
        note.textContent = "";
        svg.replaceChildren();
        return;
      }
      status.classList.remove("density-plot__status--error");
      try {
        const result = drawCurve(svg, specification, parameters, {
          adaptive,
          comparisons,
          interval: intervalValues,
          mode: mode.value,
        });
        const functionName = mode.value === "cdf" ? "分布函数" : "密度函数";
        title.textContent = `${specification.title}${functionName}`;
        svg.setAttribute("aria-label", `${specification.title}${functionName}曲线`);
        if (mode.value === "density") {
          const lower = Math.min(...intervalValues);
          const upper = Math.max(...intervalValues);
          status.textContent =
            `当前参数：${specification.notation(parameters)}；` +
            `P(${formatValue(lower)} ≤ X ≤ ${formatValue(upper)}) = ` +
            formatValue(result.probability);
        } else {
          status.textContent = `当前参数：${specification.notation(parameters)}`;
        }

        summary.replaceChildren();
        for (const [label, value] of specification.moments(parameters)) {
          const item = document.createElement("span");
          item.innerHTML = `<strong>${label}</strong> ${
            typeof value === "number" ? formatValue(value) : value
          }`;
          summary.appendChild(item);
        }

        const coordinateMode = adaptive ? "自适应观察窗" : "固定观察窗";
        const windowDescription =
          `${coordinateMode}：x ∈ [${formatValue(result.x[0])}, ${formatValue(result.x[1])}]，` +
          `${mode.value === "cdf" ? "F" : "p"}(x) ∈ ` +
          `[${formatValue(result.y[0])}, ${formatValue(result.y[1])}]。`;
        note.textContent = result.clipped
          ? `${windowDescription} 曲线超出观察窗的部分已裁切。`
          : windowDescription;
      } catch (error) {
        status.textContent = error instanceof Error ? error.message : "曲线计算失败。";
        status.classList.add("density-plot__status--error");
        note.textContent = "";
        svg.replaceChildren();
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
        if (number.value !== "" && Number.isFinite(Number(number.value))) {
          range.value = number.value;
        }
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
      if (validationMessage || Object.values(parameters).some((value) => !Number.isFinite(value))) {
        status.textContent = validationMessage || "请输入有效的参数。";
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
