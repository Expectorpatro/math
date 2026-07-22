"""Shared marker names used between LaTeX staging and AST transformation."""

TITLE_MARKER_PREFIX = "web-title:"
TITLE_START_PREFIX = "WEBTITLESTART"
TITLE_END_PREFIX = "WEBTITLEEND"
ALGORITHM_TITLE_START_PREFIX = "WEBALGOTITLESTART"
ALGORITHM_TITLE_END_PREFIX = "WEBALGOTITLEEND"
ALGORITHM_COMMAND_PREFIX = "WEBALGOCMD-"
DENSITY_PLOT_MARKER_PREFIX = "WEBDENSITYPLOT-"
TODO_START_PREFIX = "WEBTODOSTART-"
TODO_END_PREFIX = "WEBTODOEND-"
TODO_COMMANDS = frozenset({"info", "unsure", "change", "improvement"})
TABLE_MARKER_PREFIX = "WEBLATEXTABLE-"
DENSITY_PLOT_NAMES = frozenset(
    {"uniform", "normal", "chi-square", "student-t", "f", "gamma", "beta"}
)

BLOCK_TYPES = frozenset(
    {
        "BlockQuote",
        "BulletList",
        "CodeBlock",
        "DefinitionList",
        "Div",
        "Figure",
        "Header",
        "HorizontalRule",
        "LineBlock",
        "OrderedList",
        "Para",
        "Plain",
        "RawBlock",
        "Table",
    }
)

# A sentinel distinct from every valid Pandoc node.
REMOVE_AST_NODE = object()

