# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# http://www.sphinx-doc.org/en/master/config

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
import param

param.parameterized.docstring_signature = False
param.parameterized.docstring_describe_params = False

sys.path.insert(0, os.path.abspath("../../src"))


# -- Project information -----------------------------------------------------

project = "pydrobert-param"
copyright = "2021, Sean Robertson"
author = "Sean Robertson"

language = "en"

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinxcontrib.programoutput",
]

naploeon_numpy_docstring = True

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []

intersphinx_mapping = {
    "python": ("https://docs.python.org/", None),
    "numpy": ("https://docs.scipy.org/doc/numpy/", None),
    "ruamel.yaml": ("https://yaml.readthedocs.io/en/latest/", None),
    "pandas": ("https://pandas.pydata.org/pandas-docs/stable/", None),
    "optuna": ("https://optuna.readthedocs.io/en/latest/", None),
    "param": ("https://param.holoviz.org/", None),
}


# -- Options for HTML output -------------------------------------------------

on_rtd = os.environ.get("READTHEDOCS") == "True"
if on_rtd:
    html_theme = "default"
else:
    html_theme = "sphinx_rtd_theme"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

highlight_language = "python"

master_doc = "index"


def my_handler(app, what, name, obj, options, lines):
    if "Params" in name.split(".")[-1]:
        pdict = obj.param.objects(instance=False)
        del pdict["name"]
        new_lines = []
        for name, p in pdict.items():
            doc = p.doc
            deft = p.default
            bounds = p.bounds if hasattr(p, "bounds") else None
            new_lines.append(
                "- **{}**: {}. *default={}{}*".format(
                    name, doc, deft, ", bounds={}".format(bounds) if bounds else ""
                )
            )
            new_lines.append("")
            new_lines.append("")
        if new_lines:
            new_lines.insert(0, "")
            new_lines.insert(0, "")
            new_lines.insert(1, "**Parameters**")
            new_lines.insert(2, "")
            new_lines.insert(2, "")
            lines += new_lines
        options["undoc-members"] = False
    elif "Parameterized" in name.split(".")[-1]:
        options["undoc-members"] = False


def setup(app):
    app.connect("autodoc-process-docstring", my_handler)
