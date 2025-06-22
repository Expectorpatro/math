cochran.test <- function(x, exact = FALSE, correct = FALSE) {
  if (!is.data.frame(x)) {
    stop("Error: x must be a data frame.")
  }
  DNAME <- deparse(substitute(x))
  METHOD <- "Cochran test"
  Ni <- apply(x, 1, sum)
  Lj <- apply(x, 2, sum)
  N <- sum(Ni)
  k <- nrow(x)
  STATISTIC <- (k * (k-1) * sum(Ni^2) - (k - 1) * N^2) / (k * N - sum(Lj^2))
  STATISTIC <- setNames(STATISTIC, "Q")
  if (!exact) {
    if (!correct){
      p_value <- pchisq(STATISTIC, k - 1, lower.tail = FALSE)
    } else {
      p_value <- pchisq(STATISTIC - 0.5, k - 1, lower.tail = FALSE)
      METHOD <- paste(METHOD, "with continuity correction")
    }
  } else {
    METHOD <- sub("test", "exact test", METHOD, fixed = TRUE)
    # exact test
  }
  
  RVAL <- list(statistic = STATISTIC, p.value = p_value, 
               method = METHOD, data.name = DNAME)
  class(RVAL) <- "htest"
  RVAL
}