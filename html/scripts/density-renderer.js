(() => {
  "use strict";

  const SVG_NS = "http://www.w3.org/2000/svg";
  const distributionApi = globalThis.TextbookDensityDistributions;
  const densityMath = globalThis.TextbookDensityMath;
  if (!distributionApi || !densityMath) {
    console.error("[textbook] 密度图渲染依赖未加载");
    return;
  }
  const { distributions, formatValue } = distributionApi;
  const { clampProbability } = densityMath;
  function svgElement(name, attributes = {}, text = "") {
    const element = document.createElementNS(SVG_NS, name);
    for (const [key, value] of Object.entries(attributes)) {
      element.setAttribute(key, String(value));
    }
    if (text) element.textContent = text;
    return element;
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
    const viewportWidth = Number(options.viewportWidth) || 760;
    const compact = viewportWidth < 560;
    const width = compact ? Math.max(420, Math.round(viewportWidth)) : 760;
    const height = compact ? Math.max(340, Math.round(width * 0.72)) : 420;
    const margin = compact
      ? { top: 20, right: 14, bottom: 54, left: 56 }
      : { top: 24, right: 24, bottom: 58, left: 72 };
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
    const allPoints = [
      ...sampledComparisons.flatMap((item) => item.points),
      ...points,
    ];
    const intervalMinimum = Math.min(options.interval[0], options.interval[1]);
    const intervalMaximum = Math.max(options.interval[0], options.interval[1]);
    const clipped = allPoints.some(
      ({ y }) => !Number.isFinite(y) || y < yMinimum || y > yMaximum,
    ) || (
      options.mode === "density" &&
      (intervalMinimum < xMinimum || intervalMaximum > xMaximum)
    );

    svg.replaceChildren();
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    const renderedScale = Math.min(viewportWidth / width, 1);
    svg.style.minHeight = compact
      ? `${Math.max(220, Math.round(height * renderedScale))}px`
      : "";
    const modeLabel = options.mode === "cdf" ? "分布函数" : "密度函数";
    const titleIdentifier = `density-plot-title-${options.chartIdentifier}`;
    const descriptionIdentifier = `density-plot-description-${options.chartIdentifier}`;
    svg.setAttribute("aria-labelledby", `${titleIdentifier} ${descriptionIdentifier}`);
    svg.append(
      svgElement(
        "title",
        { id: titleIdentifier },
        `${specification.title}${modeLabel}曲线`,
      ),
      svgElement(
        "desc",
        { id: descriptionIdentifier },
        `横轴从 ${formatValue(xMinimum)} 到 ${formatValue(xMaximum)}，` +
          `纵轴从 ${formatValue(yMinimum)} 到 ${formatValue(yMaximum)}` +
          (clipped ? "；观察窗外的曲线或概率区间已裁切。" : "。"),
      ),
    );

    const clipIdentifier = `density-plot-clip-${options.chartIdentifier}`;
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
    const xTickCount = compact ? 4 : 5;
    for (let tick = 0; tick <= xTickCount; tick += 1) {
      const x = margin.left + (tick / xTickCount) * plotWidth;
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
          formatValue(xMinimum + (tick / xTickCount) * span),
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
    svg.onpointermove = null;
    svg.onpointerleave = null;
    if (!compact && typeof globalThis.TextbookDensityProbe?.install === "function") {
      try {
        globalThis.TextbookDensityProbe.install(svg, {
          evaluate: (x) => evaluator(x, parameters),
          mode: options.mode,
          x: [xMinimum, xMaximum],
          y: [yMinimum, yMaximum],
        });
      } catch (error) {
        console.error("[textbook] 密度图探针初始化失败", error);
      }
    }

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

  globalThis.TextbookDensityRenderer = Object.freeze({ drawCurve, svgElement });
})();
