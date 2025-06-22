goodman_kruskal_test <- function(x, y = NULL) {
  # 检查输入类型
  if (is.table(data)) {
    tbl <- data
  } else if (is.matrix(data)) {
    tbl <- as.table(data)
  } else {
    stop("Input data must be a table or a matrix.")
  }
  
  # 如果y不为NULL，检查x的类型
  if (!is.null(y)) {
    if (is.vector(x) && length(x) == nrow(tbl)) {
      # 将x和y合并为一个数据框，然后生成频数表
      df <- data.frame(x = x, y = y)
      tbl <- table(df$x, df$y)
    } else {
      stop("When y is provided, x must be a vector of the same length as the number of rows in the table.")
    }
  }
  
  # 进行Goodman-Kruskal检验的代码逻辑
  # 例如，计算 n_c, n_d 等等...
  
  return(list(tbl = tbl))  # 返回结果
}
x <- matrix(c(1, 3, 10, 1, 6, 14, 12, 0, 1, 9, 11), nrow = 3, byrow = T)
goodman_test(x)