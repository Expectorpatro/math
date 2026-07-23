(() => {
  "use strict";

  const SQRT_TWO_PI = Math.sqrt(2 * Math.PI);

  function logGamma(value) {
    const coefficients = [
      676.5203681218851,
      -1259.1392167224028,
      771.3234287776531,
      -176.6150291621406,
      12.507343278686905,
      -0.13857109526572012,
      9.984369578019572e-6,
      1.5056327351493116e-7,
    ];
    if (value < 0.5) {
      return Math.log(Math.PI) - Math.log(Math.sin(Math.PI * value)) - logGamma(1 - value);
    }
    const shifted = value - 1;
    let series = 0.9999999999998099;
    for (let index = 0; index < coefficients.length; index += 1) {
      series += coefficients[index] / (shifted + index + 1);
    }
    const t = shifted + coefficients.length - 0.5;
    return (
      0.5 * Math.log(2 * Math.PI) +
      (shifted + 0.5) * Math.log(t) -
      t +
      Math.log(series)
    );
  }

  function logBeta(a, b) {
    return logGamma(a) + logGamma(b) - logGamma(a + b);
  }

  function expFromLog(value) {
    if (value > 709) return Number.POSITIVE_INFINITY;
    if (value < -745) return 0;
    return Math.exp(value);
  }

  function clampProbability(value) {
    return Math.min(1, Math.max(0, value));
  }

  function regularizedGammaP(shape, x) {
    if (x <= 0) return 0;
    const epsilon = 1e-13;
    const tiny = 1e-300;
    if (x < shape + 1) {
      let term = 1 / shape;
      let sum = term;
      let shiftedShape = shape;
      for (let iteration = 1; iteration <= 300; iteration += 1) {
        shiftedShape += 1;
        term *= x / shiftedShape;
        sum += term;
        if (Math.abs(term) <= Math.abs(sum) * epsilon) break;
      }
      return clampProbability(
        sum * Math.exp(-x + shape * Math.log(x) - logGamma(shape)),
      );
    }

    let b = x + 1 - shape;
    let c = 1 / tiny;
    let d = 1 / b;
    let fraction = d;
    for (let iteration = 1; iteration <= 300; iteration += 1) {
      const coefficient = -iteration * (iteration - shape);
      b += 2;
      d = coefficient * d + b;
      if (Math.abs(d) < tiny) d = tiny;
      c = b + coefficient / c;
      if (Math.abs(c) < tiny) c = tiny;
      d = 1 / d;
      const change = d * c;
      fraction *= change;
      if (Math.abs(change - 1) <= epsilon) break;
    }
    const upper =
      Math.exp(-x + shape * Math.log(x) - logGamma(shape)) * fraction;
    return clampProbability(1 - upper);
  }

  function betaContinuedFraction(a, b, x) {
    const epsilon = 1e-13;
    const tiny = 1e-300;
    const sum = a + b;
    const aPlusOne = a + 1;
    const aMinusOne = a - 1;
    let c = 1;
    let d = 1 - (sum * x) / aPlusOne;
    if (Math.abs(d) < tiny) d = tiny;
    d = 1 / d;
    let fraction = d;
    for (let iteration = 1; iteration <= 300; iteration += 1) {
      const twice = 2 * iteration;
      let coefficient =
        (iteration * (b - iteration) * x) /
        ((aMinusOne + twice) * (a + twice));
      d = 1 + coefficient * d;
      if (Math.abs(d) < tiny) d = tiny;
      c = 1 + coefficient / c;
      if (Math.abs(c) < tiny) c = tiny;
      d = 1 / d;
      fraction *= d * c;

      coefficient =
        -((a + iteration) * (sum + iteration) * x) /
        ((a + twice) * (aPlusOne + twice));
      d = 1 + coefficient * d;
      if (Math.abs(d) < tiny) d = tiny;
      c = 1 + coefficient / c;
      if (Math.abs(c) < tiny) c = tiny;
      d = 1 / d;
      const change = d * c;
      fraction *= change;
      if (Math.abs(change - 1) <= epsilon) break;
    }
    return fraction;
  }

  function regularizedBeta(x, a, b) {
    if (x <= 0) return 0;
    if (x >= 1) return 1;
    const leading = Math.exp(
      logGamma(a + b) -
      logGamma(a) -
      logGamma(b) +
      a * Math.log(x) +
      b * Math.log1p(-x),
    );
    if (x < (a + 1) / (a + b + 2)) {
      return clampProbability((leading * betaContinuedFraction(a, b, x)) / a);
    }
    return clampProbability(
      1 - (leading * betaContinuedFraction(b, a, 1 - x)) / b,
    );
  }

  function normalCDF(x, mean, variance) {
    const z = (x - mean) / Math.sqrt(2 * variance);
    const sign = z < 0 ? -1 : 1;
    const absolute = Math.abs(z);
    const t = 1 / (1 + 0.3275911 * absolute);
    const polynomial =
      (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t -
        0.284496736) * t +
        0.254829592) *
      t;
    const erf = sign * (1 - polynomial * Math.exp(-(absolute ** 2)));
    return clampProbability(0.5 * (1 + erf));
  }

  function centralChiSquareDensity(x, degrees) {
    const shape = degrees / 2;
    if (x < 0) return 0;
    if (x === 0) {
      if (shape < 1) return Number.POSITIVE_INFINITY;
      if (shape === 1) return 0.5;
      return 0;
    }
    return expFromLog(
      (shape - 1) * Math.log(x) -
      x / 2 -
      shape * Math.log(2) -
      logGamma(shape),
    );
  }

  function noncentralChiSquareDensity(x, degrees, noncentrality) {
    if (noncentrality === 0) return centralChiSquareDensity(x, degrees);
    if (x < 0) return 0;
    const poissonMean = noncentrality / 2;
    if (x === 0) {
      return Math.exp(-poissonMean) * centralChiSquareDensity(0, degrees);
    }
    let weight = Math.exp(-poissonMean);
    let density = 0;
    const maximumTerm = Math.min(
      500,
      Math.ceil(poissonMean + 12 * Math.sqrt(poissonMean + 1) + 50),
    );
    for (let term = 0; term <= maximumTerm; term += 1) {
      density += weight * centralChiSquareDensity(x, degrees + 2 * term);
      weight *= poissonMean / (term + 1);
      if (
        term > poissonMean + 12 * Math.sqrt(poissonMean + 1) &&
        weight < 1e-14
      ) {
        break;
      }
    }
    return density;
  }

  function noncentralChiSquareCDF(x, degrees, noncentrality) {
    if (x <= 0) return 0;
    if (noncentrality === 0) return regularizedGammaP(degrees / 2, x / 2);
    const poissonMean = noncentrality / 2;
    let weight = Math.exp(-poissonMean);
    let probability = 0;
    const maximumTerm = Math.min(
      500,
      Math.ceil(poissonMean + 12 * Math.sqrt(poissonMean + 1) + 50),
    );
    for (let term = 0; term <= maximumTerm; term += 1) {
      probability += weight * regularizedGammaP(degrees / 2 + term, x / 2);
      weight *= poissonMean / (term + 1);
    }
    return clampProbability(probability);
  }

  globalThis.TextbookDensityMath = {
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
  };
})();
