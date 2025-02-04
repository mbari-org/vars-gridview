# vars-gridview

**VARS GridView** is a tool for reviewing and correcting VARS localizations in bulk.

[![vars-gridview pypi](https://img.shields.io/pypi/v/vars-gridview.svg)](https://pypi.python.org/pypi/vars-gridview)
[![license](https://img.shields.io/badge/license-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/language-Python-blue.svg)](https://www.python.org/downloads/)
[![.github/workflows/ci.yml](https://github.com/mbari-org/vars-gridview/actions/workflows/ci.yml/badge.svg)](https://github.com/mbari-org/vars-gridview/actions/workflows/ci.yml)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://docs.astral.sh/ruff/)

Authors: Kevin Barnard ([kbarnard@mbari.org](mailto:kbarnard@mbari.org)), Paul Roberts ([proberts@mbari.org](mailto:proberts@mbari.org))

## :hammer: Installation

> [!NOTE]
> VARS GridView requires Python 3.8 or later.

To install VARS GridView, run:

```bash
pip install vars-gridview
```

### From source

VARS GridView is built with [hatch](https://hatch.pypa.io/) and managed with [uv](https://docs.astral.sh/uv/). To install from source, clone the repository and run:

```bash
pip install .
```

## :rocket: Usage

Once VARS GridView is installed, you can run it from the command line:

```bash
vars-gridview
```

You will first be prompted to log in. Enter your VARS username and password. 

*Note: If you are not using MBARI production VARS, change the "Config server" field to point to your instance of Raziel. This setting is persisted.*

## Credits

Icons courtesy of [Font Awesome](https://fontawesome.com/).

---

Copyright &copy; 2020 [Monterey Bay Aquarium Research Institute](https://www.mbari.org)
