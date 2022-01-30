# coding=utf-8
"""about.py - About dialog."""
from __future__ import absolute_import

import os
import sys

from PIL import Image
from gi.repository import GLib, GdkPixbuf, Gtk

from src import constants
from src import labels

ImageVersion = "Pillow-{}".format(Image.PILLOW_VERSION)

_dialog = None


class _AboutDialog(Gtk.Dialog):

    def __init__(self, window):
        super(_AboutDialog, self).__init__(title=_('About'), parent=window, flags=0)
        self.add_buttons(Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE)
        self.set_resizable(False)
        self.connect('response', _close_dialog)
        self.set_default_response(Gtk.ResponseType.CLOSE)

        notebook = Gtk.Notebook()
        self.vbox.pack_start(notebook, False, False, 0)
        self.set_border_width(4)
        notebook.set_border_width(6)

        # ----------------------------------------------------------------
        # About tab.
        # ----------------------------------------------------------------
        box = Gtk.VBox(False, 0)
        box.set_border_width(5)
        base = os.path.dirname(os.path.dirname(os.path.realpath(sys.argv[0])))
        icon_path = os.path.join(base, 'images/comix.svg')
        if not os.path.isfile(icon_path):
            for prefix in [base, '/usr', '/usr/local', '/usr/X11R6']:
                icon_path = os.path.join(prefix, 'share/comix/images/comix.svg')
                if os.path.isfile(icon_path):
                    break
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(icon_path, 200, 200)
            icon = Gtk.Image()
            icon.set_from_pixbuf(pixbuf)
            box.pack_start(icon, False, False, 10)
        except GLib.Error as e:
            print('! Could not find the icon file "comix.svg"\n')
            print(e.message)
        label = Gtk.Label()
        label.set_markup(
                '<big><big><big><big><b><span foreground="#333333">Com</span>' +
                '<span foreground="#79941b">ix</span> <span foreground="#333333">' +
                constants.VERSION +
                '</span></b></big></big></big></big>\n\n' +
                _('Comix is an image viewer specifically designed to handle comic books.') +
                '\n' +
                _('It reads ZIP, RAR and tar archives, as well as plain image files.') +
                '\n\n' +
                _('Comix is licensed under the GNU General Public License.') +
                '\n\n' +
                u'<small>Copyright © 2005-2009 Pontus Ekberg\n\n' +
                'herrekberg@users.sourceforge.net\n' +
                'http://comix.sourceforge.net</small>\n' +
                u'<small>Copyright © 2010-2017 David Pineau\n\n' +
                'dav.pineau@gmail.com\n' +
                'https://github.com/Joacchim/Comix</small>\n' +
                u'<small>Copyright © 2014-2017 Sergey Dryabzhinsky\n\n' +
                'sergey.dryabzhinksy@gmail.com\n' +
                'https://github.com/sergey-dryabzhinksy/Comix</small>\n' +
                '\n' + _('Image processing library') + ': {}\n'.format(ImageVersion)
        )
        box.pack_start(label, True, True, 0)
        label.set_justify(Gtk.Justification.CENTER)
        label.set_selectable(True)
        notebook.insert_page(box, Gtk.Label(label=_('About')), 0)

        # ----------------------------------------------------------------
        # Credits tab.
        # ----------------------------------------------------------------
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(hscrollbar_policy=Gtk.PolicyType.NEVER,
                            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC)
        hbox = Gtk.HBox(homogeneous=False, spacing=5)
        hbox.set_border_width(5)

        scrolled.add_with_viewport(hbox)
        left_box = Gtk.VBox(homogeneous=True, spacing=8)
        right_box = Gtk.VBox(homogeneous=True, spacing=8)

        hbox.pack_start(child=left_box, expand=False, fill=False, padding=0)
        hbox.pack_start(child=right_box, expand=False, fill=False, padding=0)
        for nice_person, description in (('Pontus Ekberg', _('Developer')),
                                         ('Emfox Zhou', _('Simplified Chinese translation')),
                                         ('Xie Yanbo', _('Simplified Chinese translation')),
                                         ('Manuel Quiñones', _('Spanish translation')),
                                         ('Marcelo Góes', _('Brazilian Portuguese translation')),
                                         ('Christoph Wolk', _('German translation and Nautilus thumbnailer')),
                                         ('Chris Leick', _('German translation')),
                                         ('Raimondo Giammanco', _('Italian translation')),
                                         ('GhePeU', _('Italian translation')),
                                         ('Arthur Nieuwland', _('Dutch translation')),
                                         ('Achraf Cherti', _('French translation')),
                                         ('Benoît H.', _('French translation')),
                                         ('Kamil Leduchowski', _('Polish translation')),
                                         ('Darek Jakoniuk', _('Polish translation')),
                                         ('Paul Chatzidimitriou', _('Greek translation')),
                                         ('Carles Escrig Royo', _('Catalan translation')),
                                         ('Hsin-Lin Cheng', _('Traditional Chinese translation')),
                                         ('Wayne Su', _('Traditional Chinese translation')),
                                         ('Mamoru Tasaka', _('Japanese translation')),
                                         ('Ernő Drabik', _('Hungarian translation')),
                                         ('Artyom Smirnov', _('Russian translation')),
                                         ('Adrian C.', _('Croatian translation')),
                                         ('김민기', _('Korean translation')),
                                         ('Maryam Sanaat', _('Persian translation')),
                                         ('Andhika Padmawan', _('Indonesian translation')),
                                         ('Jan Nekvasil', _('Czech translation')),
                                         ('Олександр Заяц', _('Ukrainian translation')),
                                         ('Roxerio Roxo Carrillo', _('Galician translation')),
                                         ('Victor Castillejo', _('Icon design'))):
            name_label = labels.BoldLabel('{}:'.format(nice_person))
            name_label.set_alignment(1.0, 1.0)
            left_box.pack_start(name_label, True, True, 0)
            desc_label = Gtk.Label(label=description)
            desc_label.set_alignment(0, 1.0)
            right_box.pack_start(desc_label, True, True, 0)

        notebook.insert_page(scrolled, Gtk.Label(label=_('Credits')), 0)
        self.show_all()


def open_dialog(action, window):
    """Create and display the about dialog."""
    global _dialog
    if _dialog is None:
        _dialog = _AboutDialog(window)
    else:
        _dialog.present()


def _close_dialog(*args):
    """Destroy the about dialog."""
    global _dialog
    if _dialog is not None:
        _dialog.destroy()
        _dialog = None
