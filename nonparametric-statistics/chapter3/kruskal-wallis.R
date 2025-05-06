kruskal_wallis.test <- function(x, y = NULL, exact = FALSE, correct = FALSE) {
  if (is.data.frame(x) && ncol(x) == 2) {
    DNAME <- deparse(substitute(x))
    y <- x[, 2]
    x <- x[, 1]
  } else if (is.vector(x)) {
    if (is.null(y)) 
      stop("Error: x must have two columns or y is provided.")
    if (length(y) != length(x)) 
      stop("Error: x and y must have the same length.")
    DNAME <- paste(deparse(substitute(x)), "and", deparse(substitute(y)))
  } else {
    stop("Error: x must be a data frame with 2 columns or a vector.")
  }
  METHOD <- "Kruskal-Wallis test"
  TIES <- table(x)
  if (any(TIES > 1)) {
    ties <- TRUE
  } else {ties <- FALSE}
  unique_y <- sort(unique(y))
  rank_x <- rank(x)
  R_i <- sapply(unique_y, function(i) sum(rank_x[y == i]))
  n_i <- sapply(unique_y, function(i) sum(y == i))
  N <- length(x)
  STATISTIC <- setNames((12 / (N * (N + 1)) * sum(R_i^2 / n_i) - 3 * (N + 1)) 
                        / (1 - sum(TIES^3 - TIES) / (N^3 - N)), "H")
  if (!exact || ties) {
    df <- length(unique_y) - 1
    if (!correct) {
      p_value <- pchisq(STATISTIC, df = df, lower.tail = FALSE)
    } else {
      METHOD <- paste(METHOD, "with continuity correction")
      p_value <- pchisq(STATISTIC - 0.5, df = df, lower.tail = FALSE)
    }
  } else {
    H.cal <- function(rank_x, y) {
      R_i <- sapply(unique_y, function(i) sum(rank_x[y == i]))
      (12 / (N * (N + 1)) * sum(R_i^2 / n_i) - 3 * (N + 1))
    }
    METHOD <- sub("test", "exact test", METHOD, fixed = TRUE)
    library(gtools)
    all_permutations <- permutations(N, N)
    Hs <- sapply(1:nrow(all_permutations), function(i) {
      H.cal(all_permutations[i, ], y)
    })
    p_value <- mean(Hs >= STATISTIC)
  }
  RVAL <- list(statistic = STATISTIC, p.value = p_value, 
               method = METHOD, data.name = DNAME)
  class(RVAL) <- "htest"
  RVAL
}