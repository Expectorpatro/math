JT.test <- function(x, y = NULL, exact = FALSE, correct = FALSE) {
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
  J.cal <- function(x, y, k) {
    U <- 0
    for (i in 1:(k - 1)) {
      for (j in (i + 1):k) {
        xi <- x[y==i]
        xj <- x[y==j]
        ties <- sum(outer(xi, xj, "==") * 1)
        U <- U + sum(outer(xi, xj, "<") * 1) + ties / 2
      }
    }
    U
  }
  METHOD <- "Jonckheere-Terpstra test"
  k <- max(y)
  U <- 0
  for (i in 1:(k - 1)) {
    for (j in (i + 1):k) {
      xi <- x[y==i]
      xj <- x[y==j]
      ties <- sum(outer(xi, xj, "==") * 1)
      if (ties > 0) {exact <- FALSE}
      U <- U + sum(outer(xi, xj, "<") * 1) + ties / 2
    }
  }
  STATISTIC <- setNames(U, "J")
  if (!exact) {
    ni <- table(y)
    N <- sum(ni)
    Z <- (STATISTIC - (N^2 - sum(ni^2)) / 4) / sqrt((N^2 * (2 * N + 3) - sum(ni^2 * (2 * ni + 3))) / 72)
    if (!correct) {
      p_value <- pnorm(Z, lower.tail = FALSE)
    } else {
      p_value <- pnorm(Z - 0.5, lower.tail = FALSE)
      METHOD <- paste(METHOD, "with continuity correction")
    }
  } else {
    METHOD <- sub("test", "exact test", METHOD, fixed = TRUE)
    library(gtools)
    n <- length(x)
    all_permutations <- permutations(n, n)
    JTs <- sapply(1:nrow(all_permutations), function(i) {
      J.cal(all_permutations[i, ], y, k)
    })
    p_value <- mean(JTs >= STATISTIC)
  }
  RVAL <- list(statistic = STATISTIC, p.value = p_value, 
               method = METHOD, data.name = DNAME)
  class(RVAL) <- "htest"
  RVAL
}