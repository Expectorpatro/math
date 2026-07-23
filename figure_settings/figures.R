# Fixed graphics setup for R/knitr computation documents on macOS.

configure_knitr_figures <- function(project_root = Sys.getenv("BOOK_PROJECT_ROOT")) {
  if (!requireNamespace("knitr", quietly = TRUE)) {
    stop("The locked R environment does not provide knitr.")
  }

  knitr::opts_chunk$set(
    dev = "png",
    dev.args = list(type = "quartz"),
    dpi = 192,
    fig.retina = 2
  )
  invisible(NULL)
}
