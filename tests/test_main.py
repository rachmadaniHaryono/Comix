#!/usr/bin/env python
# -*- coding: utf-8 -*-
import pytest


def test_main_window():
    try:
        try:
            from src import main
        except ModuleNotFoundError:
            from comix import main
    except SystemExit:
        pytest.skip("Import failed.")
    window = main.MainWindow()
    window.show()
    window.destroy()
