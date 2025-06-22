brown.mood.test <- functions(data,
      alternative = c("two.sided", "less", "greater"),
      ties.method = c("omit", "less", "greater")){
  M_AB <- median(data[,1])
  switch(ties.method,
         omit = {data <- data[data[, 1] != M_AB,]},
         less = {data[data[, 1] == M_AB, 1] = M_AB - 1},
         greater = {data[data[, 1] == M_AB, 1] = M_AB + 1})
  
  C <- matrix(nr = 2, nc = 2)
  C[1, 1] <- sum(data[data[, 2] == 1, 1] > M_AB)
  C[1, 2] <- sum(data[data[, 2] == 2, 1] > M_AB)
  C[2, 1] <- sum(data[data[, 2] == 1, 1] < M_AB)
  C[2, 2] <- sum(data[data[, 2] == 2, 1] < M_AB)
  
  fisher.test(C, alt=alternative, conf.int = FALSE)
}
