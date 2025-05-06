sample_size_p <- function(p, N, n, conf, repeat.times=10000) {
  moe_mc_help <- function(p, N, n, conf, repeat.times) {
    alpha <- 1 - conf
    u <- qnorm(1 - alpha / 2)
    X <- rep(c(0, 1), times = c(round(N * (1 - p)), round(N * p)))
    phat <- NULL
    for (i in 1:repeat.times) {
      x <- sample(X, n)
      phat <- append(phat, mean(x))
    }
    v <- var(phat)
    moe <- sqrt(v) * u
    moe
  }
  data.frame(n, sapply(n, moe_mc_help, p=p, N=N, conf=conf, 
                       repeat.times=repeat.times))
}
set.seed(1234)
sample_size_p(0.15, 3000, 860:880, 0.95)