# -*- coding: utf-8 -*-
"""
rectlabel.py -- Tools to implement a labeling UI for bounding boxes in images
Copyright 2020  Monterey Bay Aquarium Research Institute
Distributed under MIT license. See license.txt for more information.

"""

import logging
from datetime import datetime

from vars_gridview.lib.constants import LOG_DIR


def get_logger(
    filepath, file_level=logging.DEBUG, console_level=logging.WARN, logger_name=""
):
    """Get a logger object initialized with console and file output

    Parameters:
    -----------
    filepath : str
        The absolue path to the file for the FileHandler
    log_level : {'DEBUG', 'INFO', 'WARNING','ERROR','CRITICAL'}
        The log level for the logger,
    logger_name : str, optional
        A string prepended to each log message

    Returns:
    --------
    lgr: logger
        An initialized logger object

    """
    # create logger
    lgr = logging.getLogger(logger_name)
    lgr.setLevel(logging.DEBUG)

    # create console handler and set level to debug
    ch = logging.StreamHandler()
    ch.setLevel(console_level)

    fh = logging.FileHandler(filepath)
    fh.setLevel(file_level)

    # create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # add formatter to ch
    ch.setFormatter(formatter)
    fh.setFormatter(formatter)

    # add ch to lgr
    lgr.addHandler(ch)
    lgr.addHandler(fh)

    return lgr


# Create a logs dir if it does not exist
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOGGER = get_logger(
    str(LOG_DIR / (datetime.now().strftime("%Y-%m-%d") + ".txt")),
    file_level=logging.DEBUG,
    console_level=logging.WARN,
    logger_name="vars-gridview",
)
