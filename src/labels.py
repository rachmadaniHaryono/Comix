# coding=utf-8
"""labels.py - Gtk.Label convenience classes."""
from __future__ import absolute_import

from gi.repository import Gtk


class FormattedLabel(Gtk.Label):
    """FormattedLabel keeps a label always formatted with some pango weight,
    style and scale, even when new text is set using set_text().
    """

    def __init__(self, text=''):
        super(FormattedLabel, self).__init__(text)
        self._format()

    def set_text(self, text):
        super(FormattedLabel, self).set_text(text)
        self._format()

    def _format(self):
        self.set_markup("<b>{}</b>".format(self.get_label()))


class BoldLabel(FormattedLabel):
    """A FormattedLabel that is always bold and otherwise normal."""

    def __init__(self, text=''):
        super(BoldLabel, self).__init__(text)

    def _format(self):
        self.set_markup("<b>{}</b>".format(self.get_label()))


class ItalicLabel(FormattedLabel):
    """A FormattedLabel that is always italic and otherwise normal."""

    def __init__(self, text=''):
        super(ItalicLabel, self).__init__(text)

    def _format(self):
        self.set_markup("<i>{}</i>".format(self.get_label()))
