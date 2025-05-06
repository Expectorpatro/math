sign.test <- function(x, q0, pi, exact = FALSE, 
                      alternative = c("two.sided", "greater", "less")) {
  alternative <- match.arg(alternative)
  s_pos <- sum(x > q0)
  STATISTIC <- sum(x < q0)
  n <- s_pos + STATISTIC
  STATISTIC <- setNames(STATISTIC, "s_neg")
  hypothesis_message <- switch(alternative,
                               "greater" = paste("Q0 >", pi),
                               "less" = paste("Q0 <", pi),
                               "two.sided" = paste("Q0 !=", pi))
  if (exact) {
    METHOD <- "Sign Test (Exact)"
    p.value <- switch(alternative,
                      "greater" = pbinom(q = STATISTIC, size = n, prob = pi),
                      "less" = pbinom(q = STATISTIC-1, size = n, prob = pi, lower.tail = FALSE),
                      "two.sided" = 2 * min(pbinom(q = STATISTIC-1, size = n, prob = pi, lower.tail = FALSE),
                                            pbinom(q = STATISTIC, size = n, prob = pi)))
  } else {
    METHOD <- "Sign Test (Approximate)"
    z_score <- (STATISTIC - n * pi) / sqrt(n * pi * (1 - pi)) 
    p.value <- switch(alternative,
                      "greater" = pnorm(z_score, lower.tail = TRUE),
                      "less" = pnorm(z_score, lower.tail = FALSE),
                      "two.sided" = 2 * min(pnorm(z_score), 1 - pnorm(z_score)))
  }
  
  RVAL <- list(statistic = STATISTIC, p.value = p.value,
               data.name = deparse(substitute(x)),
               method = METHOD, alternative = hypothesis_message)
  class(RVAL) <- "htest"
  RVAL
}