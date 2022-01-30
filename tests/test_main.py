#!/usr/bin/env python
# -*- coding: utf-8 -*-
def test_main_window():
    from src import main
    window = main.MainWindow()
    window.show()
    window.destroy()
