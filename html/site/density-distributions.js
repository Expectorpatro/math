(() => {
  "use strict";

  const densityMath = globalThis.TextbookDensityMath;
  if (!densityMath) {
    console.error("[textbook] 密度分布依赖 TextbookDensityMath 未加载");
    return;
  }
  function formatValue(value) {
    if (!Number.isFinite(value)) return "—";
    if (Math.abs(value) >= 1000 || (Math.abs(value) > 0 && Math.abs(value) < 0.001)) {
      return value.toExponential(2);
    }
    return Number(value.toFixed(4)).toString();
  }
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
  } = densityMath;
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

  globalThis.TextbookDensityDistributions = Object.freeze({
    distributions,
    formatValue,
  });
})();
