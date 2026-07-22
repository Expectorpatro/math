# Shared graphics policy for R/knitr computation documents.

textbook_image_setting <- function(project_root, key) {
  config_path <- file.path(project_root, "html", "build-config.toml")
  if (!file.exists(config_path)) {
    stop("Cannot find html/build-config.toml below BOOK_PROJECT_ROOT.")
  }

  lines <- readLines(config_path, warn = FALSE, encoding = "UTF-8")
  section_start <- grep("^\\s*\\[images\\]\\s*$", lines)
  if (length(section_start) != 1L) {
    stop("build-config.toml must contain exactly one [images] section.")
  }
  following <- seq.int(section_start + 1L, length(lines))
  next_section <- following[grepl("^\\s*\\[", lines[following])]
  section_end <- if (length(next_section)) next_section[[1L]] - 1L else length(lines)
  section <- lines[seq.int(section_start + 1L, section_end)]
  pattern <- paste0("^\\s*", key, "\\s*=\\s*(.*?)\\s*(?:#.*)?$")
  matches <- regexec(pattern, section, perl = TRUE)
  values <- regmatches(section, matches)
  values <- values[lengths(values) == 2L]
  if (length(values) != 1L) {
    stop(sprintf("Expected one images.%s setting in build-config.toml.", key))
  }
  values[[1L]][[2L]]
}

configure_knitr_figures <- function(project_root = Sys.getenv("BOOK_PROJECT_ROOT")) {
  if (!nzchar(project_root)) {
    stop("Set BOOK_PROJECT_ROOT to the textbook project directory before rendering.")
  }
  project_root <- normalizePath(project_root, mustWork = TRUE)
  if (!requireNamespace("knitr", quietly = TRUE)) {
    stop("The locked R environment does not provide knitr.")
  }

  format_value <- textbook_image_setting(
    project_root, "computation_preferred_format"
  )
  format_value <- gsub('^"|"$', "", format_value)
  if (!format_value %in% c("svg", "png")) {
    stop("computation_preferred_format must be svg or png.")
  }
  dpi <- suppressWarnings(as.integer(textbook_image_setting(
    project_root, "computation_raster_dpi"
  )))
  if (is.na(dpi) || dpi <= 0L) {
    stop("computation_raster_dpi must be a positive integer.")
  }

  knitr::opts_chunk$set(
    dev = format_value,
    dpi = dpi,
    fig.retina = if (identical(format_value, "png")) 2 else 1
  )
  invisible(list(format = format_value, dpi = dpi))
}
