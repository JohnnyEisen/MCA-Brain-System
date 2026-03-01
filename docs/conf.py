project = "brain-system"
author = "Brain AI Systems"
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
]

templates_path = ["_templates"]
exclude_patterns: list[str] = []

html_theme = "alabaster"

autodoc_typehints = "description"
