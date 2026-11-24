"""Shared test setup.

Tests that build real Qt widgets need a QApplication, and on a machine with no
display (CI) Qt's default platform aborts the whole run when one is created.
The offscreen platform needs no display. Set before any test module creates
the application; an explicit QT_QPA_PLATFORM still wins.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
