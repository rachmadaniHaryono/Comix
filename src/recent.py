# coding=utf-8
"""recent.py - Recent files handler."""
from __future__ import absolute_import

try:
    from urllib import url2pathname, pathname2url  # Py2
except ImportError:
    # noinspection PyUnresolvedReferences,PyCompatibility
    from urllib.request import url2pathname, pathname2url  # Py3

from gi.repository import Gtk

from src import preferences


class RecentFilesMenu(Gtk.RecentChooserMenu):

    def __init__(self, ui, window):
        self._window = window
        self._manager = Gtk.RecentManager.get_default()
        super(RecentFilesMenu, self).__init__()

        self.set_sort_type(Gtk.RecentSortType.MRU)
        self.set_show_tips(True)

        rfilter = Gtk.RecentFilter()
        rfilter.add_pixbuf_formats()
        rfilter.add_mime_type('application/x-zip')
        rfilter.add_mime_type('application/zip')
        rfilter.add_mime_type('application/x-rar')
        rfilter.add_mime_type('application/x-tar')
        rfilter.add_mime_type('application/x-gzip')
        rfilter.add_mime_type('application/x-bzip2')
        rfilter.add_mime_type('application/x-cbz')
        rfilter.add_mime_type('application/x-cbr')
        rfilter.add_mime_type('application/x-cbt')
        self.add_filter(rfilter)

        self.connect('item_activated', self._load)

    def _load(self, *args):
        uri = self.get_current_uri()
        path = url2pathname(uri[7:])
        self._window.file_handler.open_file(path)

    def add(self, path):
        if not preferences.prefs['store recent file info']:
            return
        uri = 'file://' + pathname2url(path)
        self._manager.add_item(uri)
