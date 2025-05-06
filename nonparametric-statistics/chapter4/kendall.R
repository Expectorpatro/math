kendall.test <- function(x, factor = NULL, block = NULL, 
                          exact = FALSE, correct = FALSE) {
  if (is.data.frame(x)) {
    if (ncol(x) == 3) {
      response <- x[[1]]
      factor <- x[[2]]
      block <- x[[3]]
      DNAME <- deparse(substitute(x))
    }
  } else if (is.vector(x)) {
    if (is.null(factor) || is.null(block)) {
      stop("Error: factor and block must be provided when x is a vector.")
    }
    response <- x
    DNAME <- paste(deparse(substitute(x)), ", ", 
                   deparse(substitute(factor)), " and ", 
                   deparse(substitute(block)), sep = "")
  } else {
    stop("Error: x must be either a data frame with three columns or a vector.")
  }
  W.call <- function(ranks, factors) {
    R_i <- tapply(ranks, factors, sum)
    (12 / (b * k * (k + 1)) * sum(R_i^2) - 3 * b * (k + 1)) / (b * (k - 1))
  }
  METHOD <- "Kendall test"
  k <- length(unique(factor))
  b <- length(unique(block))
  rank <- ave(response, block, FUN = rank)
  STATISTIC <- setNames(W.call(rank, factor), "W")
  TIES <- unlist(tapply(response, block, table))
  if (any(sapply(TIES, function(x) any(x > 1)))) {exact = FALSE}
  if (!exact) {
    Wc <- STATISTIC / (1 - sum(TIES^3 - TIES) / (b * k * (k^2 - 1)))
    if (!correct) {
      p_value <- pchisq(Wc * b * (k - 1), k - 1, lower.tail = FALSE)
    } else {
      p_value <- pchisq(Wc * b * (k - 1) - 0.5, k - 1, lower.tail = FALSE)
      METHOD <- paste(METHOD, "with continuity correction")
    }
  } else {
    METHOD <- sub("test", "exact test", METHOD, fixed = TRUE)
    library(gtools)
    possible_ranks <- permutations(k, k)
    all_combinations <- permutations(nrow(possible_ranks), b, repeats.allowed = TRUE)
    Ws <- sapply(1:nrow(all_combinations), function(i) {
      b_combs <- possible_ranks[all_combinations[i, ], ]
      rank_i <- as.vector(b_combs)
      W.call(rank_i, factor)
    })
    p_value <- mean(Ws >= STATISTIC)
  }
  RVAL <- list(statistic = STATISTIC, p.value = p_value, 
               method = METHOD, data.name = DNAME)
  class(RVAL) <- "htest"
  RVAL
}