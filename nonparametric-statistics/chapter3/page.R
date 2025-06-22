page.test <- function(x, factor = NULL, block = NULL, 
                      exact = FALSE, correct = FALSE,
                      repeated = FALSE) {
  if (repeated) {
    if (exact) {
      stop("Error: exact cannot be TRUE when repeated is TRUE.")
    }
    if (!is.data.frame(x) || ncol(x) == 1) {
      stop("Error: x must be a data frame with more than one column when repeated is TRUE.")
    }
    if (is.null(factor) || is.null(block)) {
      stop("Error: factor and block must be provided when repeated is TRUE.")
    }
    DNAME <- paste(deparse(substitute(x)), ", ", 
                   deparse(substitute(factor)), " and ", 
                   deparse(substitute(block)), sep = "")
  } else {
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
  }
  L.call <- function(ranks, factors, num_fac) {
    R_i <- tapply(ranks, factors, sum)
    sum(seq_len(num_fac) * R_i)
  }
  compute_z <- function(statistic, k, b, repeat_n, ties){
    mu <- repeat_n * b * k * (k + 1)^2 / 4
    sigma2 <- repeat_n * k * (k^2 - 1) * 
      (repeat_n * b * k * (repeat_n^2 * k^2 - 1) - sum(ties^3 - ties)) / 
      (144 * (repeat_n * k - 1))
    (statistic - mu) / sqrt(sigma2)
  }
  METHOD <- "Page test"
  k <- length(unique(factor))
  b <- length(unique(block))
  if (repeated) {
    repeat_n <- ncol(x)
    Ls <- sapply(1:repeat_n, function(repeat_idx) {
      response <- x[[repeat_idx]]
      rank <- ave(response, block, FUN = rank)
      L.call(rank, factor, k)
    })
    STATISTIC <- setNames(sum(Ls), "L")
    TIES <- unlist(sapply(1:repeat_n, function(repeat_idx) {
      unlist(tapply(x[[repeat_idx]], block, table))
    })) 
    Z <- compute_z(STATISTIC, k, b, repeat_n, TIES)
    if (!correct) {
      p_value <- pnorm(Z, lower.tail = FALSE)
    } else {
      p_value <- pnorm(Z - 0.5, lower.tail = FALSE)
      METHOD <- paste(METHOD, "with continuity correction")
    }
  } else {
    rank <- ave(response, block, FUN = rank)
    STATISTIC <- setNames(L.call(rank, factor, k), "L")
    TIES <- unlist(tapply(response, block, table))
    if (any(sapply(TIES, function(x) any(x > 1)))) {
      ties <- TRUE
    } else {ties <- FALSE}
    if (!exact || ties) {
      Z <- compute_z(STATISTIC, k, b, 1, TIES)
      if (!correct) {
        p_value <- pnorm(Z, lower.tail = FALSE)
      } else {
        p_value <- pnorm(Z - 0.5, lower.tail = FALSE)
        METHOD <- paste(METHOD, "with continuity correction")
      }
    } else {
      METHOD <- sub("test", "exact test", METHOD, fixed = TRUE)
      library(gtools)
      possible_ranks <- permutations(k, k)
      all_combinations <- permutations(nrow(possible_ranks), b, repeats.allowed = TRUE)
      Ls <- sapply(1:nrow(all_combinations), function(i) {
        b_combs <- possible_ranks[all_combinations[i, ], ]
        rank_i <- as.vector(b_combs)
        L.call(rank_i, factor, k)
      })
      p_value <- mean(Ls >= STATISTIC)
    }
  }
  RVAL <- list(statistic = STATISTIC, p.value = p_value, 
               method = METHOD, data.name = DNAME)
  class(RVAL) <- "htest"
  RVAL
}