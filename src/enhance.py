# coding=utf-8
"""enhance.py - Image enhancement handler and dialog (e.g. contrast,
brightness etc.)
"""
from __future__ import absolute_import

from gi.repository import Gtk

from src import histogram
from src import image

_dialog = None


class ImageEnhancer(object):
    """The ImageEnhancer keeps track of the "enhancement" values and performs
    these enhancements on pixbufs. Changes to the ImageEnhancer's values
    can be made using an _EnhanceImageDialog.
    """

    def __init__(self, window):
        self._window = window
        self.brightness = 1.0
        self.contrast = 1.0
        self.saturation = 1.0
        self.sharpness = 1.0
        self.autocontrast = False

    def enhance(self, pixbuf):
        """Return an "enhanced" version of <pixbuf>."""
        if any([self.brightness != 1.0, self.contrast != 1.0, self.saturation != 1.0, self.sharpness != 1.0,
                self.autocontrast]):
            return image.enhance(pixbuf, self.brightness, self.contrast,
                                 self.saturation, self.sharpness, self.autocontrast)
        return pixbuf

    def signal_update(self):
        """Signal to the main window that a change in the enhancement
        values has been made.
        """
        self._window.draw_image(scroll=False)


class _EnhanceImageDialog(Gtk.Dialog):
    """
    A Gtk.Dialog which allows modification of the values belonging to
    an ImageEnhancer.
    """

    def __init__(self, window):
        super(_EnhanceImageDialog, self).__init__(title=_('Enhance image'), parent=window, flags=0)
        self.add_buttons(_('Defaults'), Gtk.ResponseType.NO,
                         Gtk.STOCK_OK, Gtk.ResponseType.OK)
        self.set_resizable(False)
        self.connect('response', self._response)
        self.set_default_response(Gtk.ResponseType.OK)

        self._enhancer = window.enhancer
        self._block = False

        vbox = Gtk.VBox(False, 10)
        self.set_border_width(4)
        vbox.set_border_width(6)
        self.vbox.add(vbox)

        self._hist_image = Gtk.Image()
        self._hist_image.set_size_request(262, 170)
        vbox.pack_start(self._hist_image, True, True, 0)
        vbox.pack_start(Gtk.HSeparator.new(True, True, 0))

        hbox = Gtk.HBox(False, 4)
        vbox.pack_start(hbox, False, False, 2)
        vbox_left = Gtk.VBox(False, 4)
        vbox_right = Gtk.VBox(False, 4)
        hbox.pack_start(vbox_left, False, False, 2)
        hbox.pack_start(vbox_right, True, True, 2)

        label = Gtk.Label(label=_('Brightness') + ':')
        label.set_alignment(1, 0.5)
        vbox_left.pack_start(label, True, False, 2)
        adj = Gtk.Adjustment(0.0, -1.0, 1.0, 0.01, 0.1)
        self._brightness_scale = Gtk.HScale.new(adj)
        self._brightness_scale.set_digits(2)
        self._brightness_scale.set_value_pos(Gtk.PositionType.RIGHT)
        self._brightness_scale.connect('value-changed', self._change_values)
        # self._brightness_scale.set_update_policy(Gtk.UPDATE_DELAYED) # TODO Removed in GTK3
        vbox_right.pack_start(self._brightness_scale, True, False, 2)

        label = Gtk.Label(label=_('Contrast') + ':')
        label.set_alignment(1, 0.5)
        vbox_left.pack_start(label, True, False, 2)
        adj = Gtk.Adjustment(0.0, -1.0, 1.0, 0.01, 0.1)
        self._contrast_scale = Gtk.HScale.new(adj)
        self._contrast_scale.set_digits(2)
        self._contrast_scale.set_value_pos(Gtk.PositionType.RIGHT)
        self._contrast_scale.connect('value-changed', self._change_values)
        # self._contrast_scale.set_update_policy(Gtk.UPDATE_DELAYED) # TODO Removed in GTK3
        vbox_right.pack_start(self._contrast_scale, True, False, 2)

        label = Gtk.Label(label=_('Saturation') + ':')
        label.set_alignment(1, 0.5)
        vbox_left.pack_start(label, True, False, 2)
        adj = Gtk.Adjustment(0.0, -1.0, 1.0, 0.01, 0.1)
        self._saturation_scale = Gtk.HScale.new(adj)
        self._saturation_scale.set_digits(2)
        self._saturation_scale.set_value_pos(Gtk.PositionType.RIGHT)
        self._saturation_scale.connect('value-changed', self._change_values)
        # self._saturation_scale.set_update_policy(Gtk.UPDATE_DELAYED) # TODO Removed in GTK3
        vbox_right.pack_start(self._saturation_scale, True, False, 2)

        label = Gtk.Label(label=_('Sharpness') + ':')
        label.set_alignment(1, 0.5)
        vbox_left.pack_start(label, True, False, 2)
        adj = Gtk.Adjustment(0.0, -1.0, 1.0, 0.01, 0.1)
        self._sharpness_scale = Gtk.HScale.new(adj)
        self._sharpness_scale.set_digits(2)
        self._sharpness_scale.set_value_pos(Gtk.PositionType.RIGHT)
        self._sharpness_scale.connect('value-changed', self._change_values)
        # self._sharpness_scale.set_update_policy(Gtk.UPDATE_DELAYED) # TODO Removed in GTK3
        vbox_right.pack_start(self._sharpness_scale, True, False, 2)

        vbox.pack_start(Gtk.HSeparator.new(True, True, 0))

        self._autocontrast_button = Gtk.CheckButton(_('Automatically adjust contrast.'))
        self._autocontrast_button.set_tooltip_text(_('Automatically adjust contrast (both lightness and darkness), separately for each colour band.'))
        vbox.pack_start(self._autocontrast_button, False, False, 2)
        self._autocontrast_button.connect('toggled', self._change_values)

        self._block = True
        self._brightness_scale.set_value(self._enhancer.brightness - 1)
        self._contrast_scale.set_value(self._enhancer.contrast - 1)
        self._saturation_scale.set_value(self._enhancer.saturation - 1)
        self._sharpness_scale.set_value(self._enhancer.sharpness - 1)
        self._autocontrast_button.set_active(self._enhancer.autocontrast)
        self._block = False
        self._contrast_scale.set_sensitive(not self._autocontrast_button.get_active())

        self.show_all()

    def draw_histogram(self, image):
        """Draw a histogram representing <image> in the dialog."""
        pixbuf = image.get_pixbuf()
        if pixbuf is not None:
            self._hist_image.set_from_pixbuf(histogram.draw_histogram(pixbuf,
                                                                      text=False))

    def clear_histogram(self):
        """Clear the histogram in the dialog."""
        self._hist_image.clear()

    def _change_values(self, *args):
        if self._block:
            return
        self._enhancer.brightness = self._brightness_scale.get_value() + 1
        self._enhancer.contrast = self._contrast_scale.get_value() + 1
        self._enhancer.saturation = self._saturation_scale.get_value() + 1
        self._enhancer.sharpness = self._sharpness_scale.get_value() + 1
        self._enhancer.autocontrast = self._autocontrast_button.get_active()
        self._contrast_scale.set_sensitive(
                not self._autocontrast_button.get_active())
        self._enhancer.signal_update()

    def _response(self, dialog, response):
        if response in [Gtk.ResponseType.OK, Gtk.ResponseType.DELETE_EVENT]:
            _close_dialog()
        elif response == Gtk.ResponseType.NO:
            self._block = True
            self._brightness_scale.set_value(0.0)
            self._contrast_scale.set_value(0.0)
            self._saturation_scale.set_value(0.0)
            self._sharpness_scale.set_value(0.0)
            self._autocontrast_button.set_active(False)
            self._block = False
            self._change_values(self)


def draw_histogram(image):
    """Draw a histogram of <image> in the dialog, if there is one."""
    if _dialog is not None:
        _dialog.draw_histogram(image)


def clear_histogram():
    """Clear the histogram in the dialog, if there is one."""
    if _dialog is not None:
        _dialog.clear_histogram()


def open_dialog(action, window):
    """Create and display the (singleton) image enhancement dialog."""
    global _dialog
    if _dialog is None:
        _dialog = _EnhanceImageDialog(window)
        draw_histogram(window.left_image)
    else:
        _dialog.present()


def _close_dialog(*args):
    """Destroy the image enhancement dialog."""
    global _dialog
    if _dialog is not None:
        _dialog.destroy()
        _dialog = None
