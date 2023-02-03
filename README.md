# vars-gridview

**VARS GridView** is a tool for reviewing and correcting VARS localizations in bulk.

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/language-Python-blue.svg)](https://www.python.org/downloads/)

Authors: Kevin Barnard ([kbarnard@mbari.org](mailto:kbarnard@mbari.org)), Paul Roberts ([proberts@mbari.org](mailto:proberts@mbari.org))

---

## Install

### From PyPI

VARS GridView is available on PyPI as `vars-gridview`. To install, run:

```bash
pip install vars-gridview
```

### From source

This project is built with [Poetry](https://python-poetry.org/). To install from source, run (in the project root):

```bash
poetry install
```

## Run

Once VARS GridView is installed, you can run it from the command line:

```bash
vars-gridview
```

You will first be prompted to log in. Enter your VARS username and password. 

*Note: If you are not using MBARI production VARS, change the "Config server" field to point to your instance of Raziel. This setting is persisted.*

---

Copyright &copy; 2020&ndash;2023 [Monterey Bay Aquarium Research Institute](https://www.mbari.org)