# coding=utf-8
"""slideshow.py - Slideshow handler."""
from __future__ import absolute_import

from gi.repository import GObject

from src.preferences import prefs


class Slideshow(object):
    """Slideshow handler that manages starting and stopping of slideshows."""

    def __init__(self, window):
        self._window = window
        self._running = False
        self._id = None

    def _start(self):
        if not self._running:
            self._id = GObject.timeout_add(prefs['slideshow delay'], self._next)
            self._running = True
            self._window.update_title()

    def _stop(self):
        if self._running:
            GObject.source_remove(self._id)
            self._running = False
            self._window.update_title()

    def _next(self):
        if self._window.file_handler.is_last_page():
            self._window.actiongroup.get_action('slideshow').set_active(False)
            return False
        self._window.next_page()
        return True

    def toggle(self, action):
        """Toggle a slideshow on or off."""
        if action.get_active():
            self._start()
        else:
            self._stop()

    def is_running(self):
        """Return True if a slideshow is currently running."""
        return self._running

    def update_delay(self):
        """Update the delay time a started slideshow is using."""
        if self.is_running():
            self._stop()
            self._start()
