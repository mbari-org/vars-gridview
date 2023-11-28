# -*- coding: utf-8 -*-
"""
rectlabel.py -- Tools to implement a labeling UI for bounding boxes in images
Copyright 2020  Monterey Bay Aquarium Research Institute
Distributed under MIT license. See license.txt for more information.

"""

import logging
from datetime import datetime

from vars_gridview.lib.constants import LOG_DIR


class AppLogger:
    @staticmethod
    def get_instance():
        if not hasattr(AppLogger, "_instance"):
            AppLogger._instance = AppLogger()
        return AppLogger._instance

    def __init__(self):
        if hasattr(AppLogger, "_instance"):
            raise Exception("This class is a singleton! Use get_instance() instead.")

        # Create logger
        self._logger = logging.getLogger("vars-gridview")
        self._logger.setLevel(logging.DEBUG)

        # Create formatter
        self._formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

        # Create stream handler
        self._stream_handler = logging.StreamHandler()
        self._stream_handler.setLevel(logging.WARN)
        self._stream_handler.setFormatter(self._formatter)

        # Create file handler
        self._file_handler = logging.FileHandler(
            str(LOG_DIR / (datetime.now().strftime("%Y-%m-%d") + ".txt"))
        )
        self._file_handler.setLevel(logging.DEBUG)
        self._file_handler.setFormatter(self._formatter)

        # Add handlers
        self._logger.addHandler(self._stream_handler)
        self._logger.addHandler(self._file_handler)

    @property
    def logger(self):
        return self._logger

    def set_stream_level(self, level):
        self._stream_handler.setLevel(level)

    def set_file_level(self, level):
        self._file_handler.setLevel(level)


# Create a logs dir if it does not exist
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOGGER = AppLogger.get_instance().logger
