# coding=utf-8
"""filechooser.py - Custom FileChooserDialog implementations."""
from __future__ import absolute_import, division

import os

from gi.repository import Gtk
from gi.repository import Pango

from src import encoding
from src import image
from src import labels
from src import thumbnail
from src.preferences import prefs

_main_filechooser_dialog = None
_library_filechooser_dialog = None

PANGO_SCALE_SMALL = 0.8333333333333


class _ComicFileChooserDialog(Gtk.Dialog):
    """We roll our own FileChooserDialog because the one in GTK seems
    buggy with the preview widget. The <action> argument dictates what type
    of filechooser dialog we want (i.e. it is Gtk.FileChooserAction.OPEN
    or Gtk.FileChooserAction.SAVE).

    This is a base class for the _MainFileChooserDialog, the
    _LibraryFileChooserDialog and the StandAloneFileChooserDialog.

    Subclasses should implement a method files_chosen(paths) that will be
    called once the filechooser has done its job and selected some files.
    If the dialog was closed or Cancel was pressed, <paths> is the empty list.
    """

    _last_activated_file = None

    def __init__(self, parent=None, action=Gtk.FileChooserAction.OPEN):
        self._action = action
        if action == Gtk.FileChooserAction.OPEN:
            title = _('Open')
            buttons = (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                       Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        else:
            title = _('Save')
            buttons = (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                       Gtk.STOCK_SAVE, Gtk.ResponseType.OK)

        super(_ComicFileChooserDialog, self).__init__(title=title, parent=parent, flags=0)
        self.add_buttons(*buttons)
        self.set_default_response(Gtk.ResponseType.OK)

        self.filechooser = Gtk.FileChooserWidget(action=action)
        self.filechooser.set_size_request(680, 420)
        self.vbox.pack_start(self.filechooser, True, True, 0)
        self.set_border_width(4)
        self.filechooser.set_border_width(6)
        self.connect('response', self._response)
        self.filechooser.connect('file_activated', self._response, Gtk.ResponseType.OK)

        preview_box = Gtk.VBox(False, 10)
        preview_box.set_size_request(130, 0)
        self._preview_image = Gtk.Image()
        self._preview_image.set_size_request(130, 130)
        preview_box.pack_start(self._preview_image, False, False, 0)
        self.filechooser.set_preview_widget(preview_box)
        self._namelabel = labels.BoldLabel()
        self._namelabel.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        preview_box.pack_start(self._namelabel, False, False, 0)
        self._sizelabel = Gtk.Label()
        self._sizelabel.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        preview_box.pack_start(self._sizelabel, False, False, 0)
        self.filechooser.set_use_preview_label(False)
        preview_box.show_all()
        self.filechooser.connect('update-preview', self._update_preview)

        ffilter = Gtk.FileFilter()
        ffilter.add_pattern('*')
        ffilter.set_name(_('All files'))
        self.filechooser.add_filter(ffilter)

        self.add_filter(_('All Archives'), ('application/x-zip',
                                            'application/zip', 'application/x-rar', 'application/x-tar',
                                            'application/x-gzip', 'application/x-bzip2', 'application/x-cbz',
                                            'application/x-cbr', 'application/x-cbt'))
        self.add_filter(_('ZIP archives'),
                        ('application/x-zip', 'application/zip', 'application/x-cbz'))
        self.add_filter(_('RAR archives'),
                        ('application/x-rar', 'application/x-cbr'))
        self.add_filter(_('Tar archives'),
                        ('application/x-tar', 'application/x-gzip',
                         'application/x-bzip2', 'application/x-cbt'))

        if self.__class__._last_activated_file is not None and os.path.isfile(self.__class__._last_activated_file):
            self.filechooser.set_filename(self.__class__._last_activated_file)
        elif prefs['path of last browsed in filechooser'] and os.path.isdir(prefs['path of last browsed in filechooser']):
            self.filechooser.set_current_folder(prefs['path of last browsed in filechooser'])

        self.show_all()

    def add_filter(self, name, mimes):
        """Add a filter, called <name>, for each mime type in <mimes> to
        the filechooser.
        """
        ffilter = Gtk.FileFilter()
        for mime in mimes:
            ffilter.add_mime_type(mime)
        ffilter.set_name(name)
        self.filechooser.add_filter(ffilter)

    def set_save_name(self, name):
        self.filechooser.set_current_name(name)

    def set_current_directory(self, path):
        self.filechooser.set_current_folder(path)

    # noinspection PyUnusedLocal
    def _response(self, widget, response):
        """Return a list of the paths of the chosen files, or None if the
        event only changed the current directory.
        """
        if response == Gtk.ResponseType.OK:
            paths = self.filechooser.get_filenames()
            if len(paths) == 1 and os.path.isdir(paths[0]):
                self.filechooser.set_current_folder(paths[0])
                self.emit_stop_by_name('response')
                return
            if not paths:
                return
            # FileChooser.set_do_overwrite_confirmation() doesn't seem to
            # work on our custom dialog, so we use a simple alternative.
            if self._action == Gtk.FileChooserAction.SAVE and os.path.exists(paths[0]):
                overwrite_dialog = Gtk.MessageDialog(None,
                                                     0,
                                                     Gtk.MessageType.QUESTION,
                                                     Gtk.ButtonsType.OK_CANCEL,
                                                     _("A file named '{}' already exists. "
                                                       "Do you want to replace it?").format(os.path.basename(paths[0])))
                overwrite_dialog.format_secondary_text(_('Replacing it will overwrite its contents.'))
                response = overwrite_dialog.run()
                overwrite_dialog.destroy()
                if response != Gtk.ResponseType.OK:
                    self.emit_stop_by_name('response')
                    return
            prefs['path of last browsed in filechooser'] = self.filechooser.get_current_folder()
            self.__class__._last_activated_file = paths[0]
            self.files_chosen(paths)
        else:
            self.files_chosen([])

    # noinspection PyUnusedLocal
    def _update_preview(self, *args):
        path = self.filechooser.get_preview_filename()
        if path and os.path.isfile(path):
            pixbuf = thumbnail.get_thumbnail(path, prefs['create thumbnails'])
            if pixbuf is None:
                self._preview_image.clear()
                self._namelabel.set_text('')
                self._sizelabel.set_text('')
            else:
                pixbuf = image.add_border(pixbuf, 1)
                self._preview_image.set_from_pixbuf(pixbuf)
                self._namelabel.set_text(encoding.to_unicode(os.path.basename(path)))
                self._sizelabel.set_text('{:.1f} KiB'.format(os.stat(path).st_size / 1024.0))
        else:
            self._preview_image.clear()
            self._namelabel.set_text('')
            self._sizelabel.set_text('')


class _MainFileChooserDialog(_ComicFileChooserDialog):
    """The normal filechooser dialog used with the "Open" menu item."""

    def __init__(self, window):
        super(_MainFileChooserDialog, self).__init__(parent=window)
        self._window = window
        self.set_transient_for(window)

        ffilter = Gtk.FileFilter()
        ffilter.add_pixbuf_formats()
        ffilter.set_name(_('All images'))
        self.filechooser.add_filter(ffilter)
        self.add_filter(_('JPEG images'), ('image/jpeg',))
        self.add_filter(_('PNG images'), ('image/png',))
        self.add_filter(_('GIF images'), ('image/gif',))
        self.add_filter(_('TIFF images'), ('image/tiff',))
        self.add_filter(_('BMP images'), ('image/bmp',))

        filters = self.filechooser.list_filters()
        self.filechooser.set_filter(filters[prefs['last filter in main filechooser']])

    def files_chosen(self, paths):
        if paths:
            filter_index = self.filechooser.list_filters().index(self.filechooser.get_filter())
            prefs['last filter in main filechooser'] = filter_index

            _close_main_filechooser_dialog()
            self._window.file_handler.open_file(paths[0])
        else:
            _close_main_filechooser_dialog()


class _LibraryFileChooserDialog(_ComicFileChooserDialog):
    """The filechooser dialog used when adding books to the library."""

    def __init__(self, library):
        super(_LibraryFileChooserDialog, self).__init__(parent=library)
        self._library = library
        self.set_transient_for(library)
        self.filechooser.set_select_multiple(True)
        self.filechooser.connect('current_folder_changed', self._set_collection_name)

        self._collection_button = Gtk.CheckButton('{}:'.format(_('Automatically add the books to this collection')), False)
        self._collection_button.set_active(prefs['auto add books into collections'])
        self._comboentry = Gtk.ComboBox.new_with_entry()
        self._comboentry.get_child().set_activates_default(True)
        for collection in self._library.backend.get_all_collections():
            name = self._library.backend.get_collection_name(collection)
            self._comboentry.append_text(name)
        collection_box = Gtk.HBox(False, 6)
        collection_box.pack_start(child=self._collection_button, expand=False, fill=False, padding=0)
        collection_box.pack_start(child=self._comboentry, expand=True, fill=True, padding=0)
        collection_box.show_all()
        self.filechooser.set_extra_widget(collection_box)

        filters = self.filechooser.list_filters()
        self.filechooser.set_filter(filters[prefs['last filter in library filechooser']])

    # noinspection PyUnusedLocal
    def _set_collection_name(self, *args):
        """Set the text in the ComboBoxEntry to the name of the current
        directory.
        """
        name = os.path.basename(self.filechooser.get_current_folder())
        self._comboentry.get_child().set_text(name)

    def files_chosen(self, paths):
        if paths:
            if self._collection_button.get_active():
                prefs['auto add books into collections'] = True
                collection_name = self._comboentry.get_title()
                if not collection_name:  # No empty-string names.
                    collection_name = None
            else:
                prefs['auto add books into collections'] = False
                collection_name = None
            filter_index = self.filechooser.list_filters().index(self.filechooser.get_filter())
            prefs['last filter in library filechooser'] = filter_index

            close_library_filechooser_dialog()
            self._library.add_books(paths, collection_name)
        else:
            close_library_filechooser_dialog()


class StandAloneFileChooserDialog(_ComicFileChooserDialog):
    """
    A simple filechooser dialog that is designed to be used with the
    Gtk.Dialog.run() method. The <action> dictates what type of filechooser
    dialog we want (i.e. save or open). If the type is an open-dialog, we
    use multiple selection by default.
    """

    def __init__(self, action=Gtk.FileChooserAction.OPEN):
        super(StandAloneFileChooserDialog, self).__init__(action=action)
        if action == Gtk.FileChooserAction.OPEN:
            self.filechooser.set_select_multiple(True)
        self._paths = None

        ffilter = Gtk.FileFilter()
        ffilter.add_pixbuf_formats()
        ffilter.set_name(_('All images'))
        self.filechooser.add_filter(ffilter)
        self.add_filter(_('JPEG images'), ('image/jpeg',))
        self.add_filter(_('PNG images'), ('image/png',))
        self.add_filter(_('GIF images'), ('image/gif',))
        self.add_filter(_('TIFF images'), ('image/tiff',))
        self.add_filter(_('BMP images'), ('image/bmp',))

    def get_paths(self):
        """Return the selected paths. To be called after run() has returned
        a response.
        """
        return self._paths

    def files_chosen(self, paths):
        self._paths = paths


# noinspection PyUnusedLocal
def open_main_filechooser_dialog(action, window):
    """Open the main filechooser dialog."""
    global _main_filechooser_dialog
    if _main_filechooser_dialog is None:
        _main_filechooser_dialog = _MainFileChooserDialog(window)
    else:
        _main_filechooser_dialog.present()


# noinspection PyUnusedLocal
def _close_main_filechooser_dialog(*args):
    """Close the main filechooser dialog."""
    global _main_filechooser_dialog
    if _main_filechooser_dialog is not None:
        _main_filechooser_dialog.destroy()
        _main_filechooser_dialog = None


def open_library_filechooser_dialog(library):
    """Open the library filechooser dialog."""
    global _library_filechooser_dialog
    if _library_filechooser_dialog is None:
        _library_filechooser_dialog = _LibraryFileChooserDialog(library)
    else:
        _library_filechooser_dialog.present()


# noinspection PyUnusedLocal
def close_library_filechooser_dialog(*args):
    """Close the library filechooser dialog."""
    global _library_filechooser_dialog
    if _library_filechooser_dialog is not None:
        _library_filechooser_dialog.destroy()
        _library_filechooser_dialog = None
