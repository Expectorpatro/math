durbin.test <- function(x, factor = NULL, block = NULL, 
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
  num_r <- table(factor)
  num_t <- table(block)
  if (length(unique(num_r)) != 1) {
    stop("Error: The design is not balanced. 
         Each treatment must appear in the same number of blocks.")
  }
  if (length(unique(num_t)) != 1) {
    stop("Error: The design is not balanced. 
         Each block must contain the same number of treatments.")
  }
  D.call <- function(ranks, factors) {
    R_i <- tapply(ranks, factors, sum)
    12 * (k - 1) / (r * k * (t^2 - 1)) * sum(R_i^2) - 
      3 * r * (k - 1) * (t + 1) / (t - 1)
  }
  METHOD <- "Friedman rank sum test"
  k <- length(unique(factor))
  b <- length(unique(block))
  r <- as.numeric(num_r[1])
  t <- as.numeric(num_t[1])
  rank <- ave(response, block, FUN = rank)
  STATISTIC <- setNames(D.call(rank, factor), "D")
  TIES <- unlist(tapply(response, block, table))
  if (any(sapply(TIES, function(x) any(x > 1)))) {
    ties <- TRUE
  } else {ties <- FALSE}
  if (!exact || ties) {
    Dc <- (k - 1) * sum((tapply(rank, factor, sum) - r * (t + 1) / 2)^2) /
      (sum(rank^2) - b * t * (t + 1)^2 / 4)
    if (!correct) {
      p_value <- pchisq(Dc, k - 1, lower.tail = FALSE)
    } else {
      p_value <- pchisq(Dc - 0.5, k - 1, lower.tail = FALSE)
      METHOD <- paste(METHOD, "with continuity correction")
    }
  } else {
    METHOD <- sub("test", "exact test", METHOD, fixed = TRUE)
    library(gtools)
    possible_ranks <- permutations(t, t)
    all_combinations <- permutations(nrow(possible_ranks), b, repeats.allowed = TRUE)
    Ds <- sapply(1:nrow(all_combinations), function(i) {
      b_combs <- possible_ranks[all_combinations[i, ], ]
      rank_i <- as.vector(b_combs)
      D.call(rank_i, factor)
    })
    p_value <- mean(Ds >= STATISTIC)
  }
  RVAL <- list(statistic = STATISTIC, p.value = p_value, 
               method = METHOD, data.name = DNAME)
  class(RVAL) <- "htest"
  RVAL
}