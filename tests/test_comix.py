#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
from unittest import mock

import pytest


def get_comix():
    try:
        try:
            from src import comix
        except ModuleNotFoundError:
            from comix import comix  # type: ignore
        return comix
    except SystemExit:
        return


def test_import():
    get_comix()


@pytest.mark.skipif(
    "TRAVIS" in os.environ and os.environ["TRAVIS"] == "true",
    reason="Skipping this test on Travis CI.",
)
@pytest.mark.skipif(not bool(get_comix()), reason="Import comix failed.")
@pytest.mark.non_travis
def test_run():
    get_comix().run(["comix"])


@pytest.mark.skipif(not bool(get_comix()), reason="Import comix failed.")
def test_run_with_patched_gtk():
    with mock.patch("src.comix.Gtk"):
        get_comix().run(["comix"])
