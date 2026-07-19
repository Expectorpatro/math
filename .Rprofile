local({
  textbook_root <- Sys.getenv("TEXTBOOK_ROOT", unset = getwd())
  renv_project <- normalizePath(textbook_root, mustWork = TRUE)
  Sys.setenv(RENV_PROJECT = renv_project)
  source(file.path(renv_project, "renv", "activate.R"))
})
