runs.test <- function(x, alternative = c("two.sided", "less", "greater"), exact = TRUE, correct = FALSE) {
  
  alternative <- match.arg(alternative)
  DNAME <- deparse1(substitute(x))
  METHOD <- "Runs test"
  
  # Calculate runs
  runs <- sum(diff(x) != 0) + 1
  
  # Calculate sample sizes
  N <- length(x)
  n <- sum(x)  # Number of 1s in x
  m <- N - n  # Number of 0s in x
  
  # Functions for cumulative probability
  pruns <- function(runs, m, n, lower.tail = TRUE){
    p <- 0
    if (lower.tail){
      for (i in 1:runs){
        if (i %% 2 == 0){
          k <- i / 2
          p <- p + 2 * choose(m - 1, k - 1) * 
            choose(n - 1, k - 1) / 
            choose(m + n, n)  
        }else{
          k <- (i - 1) / 2
          p <- p + (choose(m - 1, k - 1) * choose(n - 1, k) +
                      choose(m - 1, k) * choose(n - 1, k - 1)) / 
            choose(m + n, n) 
        }
      }
    }else{
      for (i in (runs + 1):(m+n)){
        if (i %% 2 == 0){
          k <- i / 2
          p <- p + 2 * choose(m - 1, k - 1) * 
            choose(n - 1, k - 1) / 
            choose(m + n, n)  
        }else{
          k <- (i - 1) / 2
          p <- p + (choose(m - 1, k - 1) * choose(n - 1, k) +
                      choose(m - 1, k) * choose(n - 1, k - 1)) / 
            choose(m + n, n) 
        }
      }
    }
    return(p)
  }
  
  if (exact){
    METHOD <- sub("test", "exact test", METHOD, fixed = TRUE)
    # Exact p-value calculation
    p.value <- switch(alternative,
                      two.sided = 2 * min(pruns(runs, m, n), 
                                          pruns(runs - 1, m, n, lower.tail = FALSE)),
                      less = pruns(runs, m, n),
                      greater = pruns(runs, m, n, lower.tail = FALSE))
  }else{
    # Normal approximation
    E_R <- (2 * m * n) / N + 1
    Var_R <- (2 * m * n * (2 * m * n - N)) / (N^2 * (N - 1))
    z <- (runs - E_R) / sqrt(Var_R)
    
    if (correct){
      METHOD <- paste(METHOD, "with continuity correction")
      # Apply continuity correction
      z <- runs - E_R
      CORRECTION <- switch(alternative, 
                           two.sided = sign(z) * 0.5, 
                           greater = 0.5, 
                           less = -0.5)
      z <- (z - CORRECTION) / sqrt(Var_R)
      # p-value using normal approximation
      p.value <- switch(alternative,
                        two.sided =  2 * min(pnorm(z), 
                                             pnorm(z, lower.tail = FALSE)),
                        less = pnorm(z),
                        greater = pnorm(z, lower.tail = FALSE))
    }else{
      p.value <- switch(alternative,
                        two.sided =  2 * min(pnorm(z), 
                                             pnorm(z, lower.tail = FALSE)),
                        less = pnorm(z),
                        greater = pnorm(z, lower.tail = FALSE))
    }
  }
  
  alternative <- switch(alternative,
                        two.sided = "The data lacks randomness.",
                        less = "The data has a tendency to cluster.",
                        greater = "The data has a tendency to mix.")
  
  # Create output in htest format
  RVAL <- list(statistics = setNames(runs, "runs"), 
               alternative = alternative, method = METHOD, 
               data.name = DNAME, p.value = p.value)
  class(RVAL) <- "htest"
  RVAL
}

# median <- median(x)
# x <- na.omit(ifelse(x > median, 1, ifelse(x < median, 0, NA)))
runs.test(x, alternative = "two.sided", 
          exact = TRUE, correct = FALSE)