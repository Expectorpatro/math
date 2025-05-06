tag_recapture_CI <- function(a, b, c, d, alpha = 0.05, 
   method = c("normal", "chisq", "fisher", "likelihood", "bootstrap"),
   x.correct = FALSE, N = 1000, seed = 42) {
  # Ensure the 'method' parameter is valid
  method <- match.arg(method) 
  
  if (method == "chisq") {
    # Pearson's Chi-squared test
    p.values <- sapply(d, function(d_i) {
      chisq.test(matrix(c(a, b, c, d_i), nrow = 2, byrow = TRUE), 
                 correct = FALSE)$p.value
    })
    valid_d <- d[p.values > alpha]
    if (length(valid_d) == 0) {
      stop("No values satisfy the p-value > alpha condition.")
    }
    return(sum(c(a, b, c)) + range(valid_d))
    
  } else if (method == "fisher"){
    # Fisher's exact test
    p.values <- sapply(d, function(d_i) {
      fisher.test(matrix(c(a, b, c, d_i), nrow = 2, byrow = TRUE))$p.value
    })
    valid_d <- d[p.values > alpha]
    if (length(valid_d) == 0) {
      stop("No values satisfy the p-value > alpha condition.")
    }
    return(sum(c(a, b, c)) + range(valid_d))
    
  } else if (method == "normal") {
    # Normal approximation method
    X <- a + b
    y <- a + c
    x <- a
    if (x.correct) {
      t_hat <- (X + 1) * (y + 1) / (x + 1) - 1
      V_hat <- ((X + 1) * (y + 1) * (y - x) * (X - x)) / ((x + 1)^2 * (x + 2))
    } else {
      t_hat <- y * X / x
      V_hat <- y * X * (y - x) * (X - x) / x^3
    }
    CI_lower <- t_hat - qnorm(1 - alpha / 2) * sqrt(V_hat)
    CI_upper <- t_hat + qnorm(1 - alpha / 2) * sqrt(V_hat)
    return(c(CI_lower, CI_upper))
    
  } else if (method == "bootstrap") {
    # Bootstrap method
    set.seed(seed)
    sample.frame <- c(rep(1, a), rep(0, c)) # Construct sample frame
    bootstrap_estimates <- replicate(N, {
      sampled <- sample(sample.frame, a + c, replace = TRUE)
      x_boot <- sum(sampled)
      (a + b) * (a + c) / x_boot
    })
    CI <- quantile(bootstrap_estimates, probs = c(alpha / 2, 1 - alpha / 2))
    return(floor(CI))
    
  } else if (method == "likelihood") {
    # Likelihood method
    t_hat <- (a + b) * (a + c) / a
    ll_max <- dhyper(a, a + b, t_hat - (a + b), a + c, log = TRUE)
    ll <- sapply(d, function(d_i) {
      dhyper(a, a + b, d_i, a + c, log = TRUE)
    })
    valid_d <- d[2 * (ll_max - ll) < qchisq(1 - alpha, df = 1)]
    if (length(valid_d) == 0) {
      stop("No values satisfy the likelihood condition.")
    }
    return(a + b + range(valid_d))
  }
}
