(() => {
  "use strict";

  const SVG_NS = "http://www.w3.org/2000/svg";
  const WIDTH = 760;
  const MARGIN = { top: 24, right: 24, bottom: 58, left: 72 };
  const PLOT_WIDTH = WIDTH - MARGIN.left - MARGIN.right;
  const PLOT_HEIGHT = 420 - MARGIN.top - MARGIN.bottom;

  function svgElement(name, attributes = {}, text = "") {
    const element = document.createElementNS(SVG_NS, name);
    for (const [key, value] of Object.entries(attributes)) {
      element.setAttribute(key, String(value));
    }
    if (text) element.textContent = text;
    return element;
  }

  function formatValue(value) {
    if (!Number.isFinite(value)) return "—";
    if (Math.abs(value) >= 1000 || (Math.abs(value) > 0 && Math.abs(value) < 0.001)) {
      return value.toExponential(3);
    }
    return Number(value.toFixed(5)).toString();
  }

  function install(svg, options) {
    const group = svgElement("g", {
      class: "density-plot__probe",
      visibility: "hidden",
      "aria-hidden": "true",
    });
    const vertical = svgElement("line", { class: "density-plot__probe-line" });
    const point = svgElement("circle", { class: "density-plot__probe-point", r: 4 });
    const labelBackground = svgElement("rect", {
      class: "density-plot__probe-label-bg",
      width: 168,
      height: 27,
      rx: 5,
    });
    const label = svgElement("text", { class: "density-plot__probe-label" });
    group.append(vertical, point, labelBackground, label);
    svg.appendChild(group);

    const xSpan = options.x[1] - options.x[0];
    const ySpan = options.y[1] - options.y[0];
    const yScale = (value) =>
      MARGIN.top +
      PLOT_HEIGHT -
      ((Math.min(Math.max(value, options.y[0]), options.y[1]) - options.y[0]) / ySpan) *
        PLOT_HEIGHT;

    svg.onpointermove = (event) => {
      const bounds = svg.getBoundingClientRect();
      if (!bounds.width) return;
      const svgX = ((event.clientX - bounds.left) / bounds.width) * WIDTH;
      if (svgX < MARGIN.left || svgX > MARGIN.left + PLOT_WIDTH) {
        group.setAttribute("visibility", "hidden");
        return;
      }
      const x = options.x[0] + ((svgX - MARGIN.left) / PLOT_WIDTH) * xSpan;
      const value = options.evaluate(x);
      if (!Number.isFinite(value) || value < options.y[0] || value > options.y[1]) {
        group.setAttribute("visibility", "hidden");
        return;
      }
      const y = yScale(value);
      label.textContent =
        `x = ${formatValue(x)}，${options.mode === "cdf" ? "F" : "p"}(x) = ` +
        formatValue(value);
      const measuredWidth =
        typeof label.getComputedTextLength === "function"
          ? label.getComputedTextLength()
          : label.textContent.length * 7;
      const labelWidth = Math.min(300, Math.max(168, Math.ceil(measuredWidth) + 18));
      const labelX =
        svgX + labelWidth + 14 > WIDTH - MARGIN.right
          ? svgX - labelWidth - 10
          : svgX + 10;
      const labelY = Math.max(MARGIN.top + 3, Math.min(y - 34, MARGIN.top + PLOT_HEIGHT - 30));
      vertical.setAttribute("x1", svgX);
      vertical.setAttribute("x2", svgX);
      vertical.setAttribute("y1", MARGIN.top);
      vertical.setAttribute("y2", MARGIN.top + PLOT_HEIGHT);
      point.setAttribute("cx", svgX);
      point.setAttribute("cy", y);
      labelBackground.setAttribute("x", labelX);
      labelBackground.setAttribute("y", labelY);
      labelBackground.setAttribute("width", labelWidth);
      label.setAttribute("x", labelX + 8);
      label.setAttribute("y", labelY + 18);
      group.setAttribute("visibility", "visible");
    };
    svg.onpointerleave = () => group.setAttribute("visibility", "hidden");
  }

  globalThis.TextbookDensityProbe = { install };
})();
