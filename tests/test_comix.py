#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
from unittest import mock

import pytest

from src import comix


@pytest.mark.skipif(
    "TRAVIS" in os.environ and os.environ["TRAVIS"] == "true",
    reason="Skipping this test on Travis CI.",
)
@pytest.mark.non_travis
def test_run():
    comix.run(["comix"])


def test_run_with_patched_gtk():
    with mock.patch("src.comix.Gtk"):
        comix.run(["comix"])
