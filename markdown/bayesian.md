Adding more data. A key aspect of Bayesian analysis is the ease with which sequential analyses can be performed.

Since we are considering only these possibilities, we could renormalize the three numbers to sum to 1 (p(random) = 760  760+60.5+3.12 , etc.) but there is no need, as the adjustment would merely be absorbed into the proportionality constant in (1.6).

When we dispute the claims of a posterior distribution, we are saying that the model does not fit the data or that we have additional prior information not included in the model so far.

it becomes as natural to consider the probability that an unknown estimand lies in a particular range of values as it is to consider the probability that the mean of a random sample of 10 items from a known fixed population of size 100 will lie in a certain range.

Bayesian methods enable statements to be made about the partial knowledge available (based on data) concerning some situation or ‘state of nature’ (unobservable or as yet unobserved) in a systematic way, using probability as the yardstick. The guiding principle is that the state of knowledge about anything unknown is described by a probability distribution.

The guiding principle is that the state of knowledge about anything unknown is described by a probability distribution.

For many practical purposes, however, various numerical summaries of the distribution are desirable. Commonly used summaries of location are the mean, median, and mode(s) of the distribution; variation is commonly summarized by the standard deviation, the interquartile range, and other quantiles. Each summary has its own interpretation: for example, the mean is the posterior expectation of the parameter, and the mode may be interpreted as the single ‘most likely’ value, given the data (and the model).

Our general approach to computation is to fit many models, gradually increasing the complexity. We do not recommend the strategy of writing a model and then letting the computer run overnight to estimate it perfectly. Rather, we prefer to fit each model relatively quickly, using inferences from the previously fitted simpler models as starting values, and displaying inferences and comparing to data before continuing.

- In performing simulations, it is helpful to consider the duality between a probability density function and a histogram of a set of random draws from the distribution: given a large enough sample, the histogram can provide practically complete information about the density, and in particular, various sample moments, percentiles, and other summary statistics provide estimates of any aspect of the distribution, to a level of precision that can be estimated.

- Another advantage of simulation is that extremely large or small simulated values often flag a problem with model specification or parameterization (for example, see Figure 4.2) that might not be noticed if estimates and probability statements were obtained in analytic form.

- the prior mean of ω is the average of all possible posterior means over the distribution of possible data. 

- the posterior variance is on average smaller than the prior variance, by an amount that depends on the variation in posterior means over the distribution of possible data.

The mean and variance relations only describe expectations, and in particular situations the posterior variance can be similar to or even larger than the prior variance (although <u>this can be an indication of conflict or inconsistency between the sampling model and prior distribution</u>).

This is a general feature of Bayesian inference: the posterior distribution is centered at a point that represents a compromise between the prior information and the data, and the compromise is controlled to a greater extent by the data as the sample size increases.



As already noted, when estimating a proportion, the normal approximation is generally improved by applying it to the logit transform, $\log{\frac{\theta}{1-\theta}}$, which transforms the parameter space from the unit interval to the real line.
