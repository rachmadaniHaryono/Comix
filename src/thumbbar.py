# coding=utf-8
"""thumbbar.py - Thumbnail sidebar for main window."""
from __future__ import absolute_import

try:
    from urllib import pathname2url  # Py2
except ImportError:
    # noinspection PyCompatibility,PyUnresolvedReferences
    from urllib.request import pathname2url  # Py3


from PIL import Image
from PIL import ImageDraw
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GObject
from gi.repository import Gtk

from src import image
from src.preferences import prefs

# Compatibility
try:
    # noinspection PyUnresolvedReferences,PyShadowingBuiltins
    range = xrange  # Python2
except NameError:
    pass


class ThumbnailSidebar(Gtk.HBox):
    """A thumbnail sidebar including scrollbar for the main window."""

    def __init__(self, window):
        super(ThumbnailSidebar, self).__init__(homogeneous=False, spacing=0)
        self._window = window
        self._loaded = False
        self._load_task = None
        self._height = 0
        self._stop_update = False

        self._liststore = Gtk.ListStore(GdkPixbuf.Pixbuf)
        self._treeview = Gtk.TreeView(self._liststore)

        self._treeview.enable_model_drag_source(Gdk.ModifierType.BUTTON1_MASK,
                                                [('text/uri-list', 0, 0)], Gdk.DragAction.COPY)

        self._column = Gtk.TreeViewColumn(None)
        cellrenderer = Gtk.CellRendererPixbuf()
        self._layout = Gtk.Layout()
        self._layout.put(self._treeview, 0, 0)
        self._column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        self._treeview.append_column(self._column)
        self._column.pack_start(cellrenderer, True)
        self._column.set_attributes(cellrenderer, pixbuf=0)
        self._column.set_fixed_width(prefs['thumbnail size'] + 7)
        self._layout.set_size_request(prefs['thumbnail size'] + 7, 0)
        self._treeview.set_headers_visible(False)
        self._vadjust = self._layout.get_vadjustment()
        self._vadjust.step_increment = 15
        self._vadjust.page_increment = 1
        self._scroll = Gtk.VScrollbar(None)
        self._scroll.set_adjustment(self._vadjust)
        self._selection = self._treeview.get_selection()

        self.pack_start(self._layout, True, True, 0)
        self.pack_start(self._scroll, True, True, 0)

        self._treeview.connect_after('drag_begin', self._drag_begin)
        self._treeview.connect('drag_data_get', self._drag_data_get)
        self._selection.connect('changed', self._selection_event)
        self._layout.connect('scroll_event', self._scroll_event)

    def get_width(self):
        """Return the width in pixels of the ThumbnailSidebar."""
        return self._layout.size_request().width + self._scroll.size_request().width

    # noinspection PyUnusedLocal
    def show(self, *args):
        """Show the ThumbnailSidebar."""
        self.show_all()

    def clear(self):
        """Clear the ThumbnailSidebar of any loaded thumbnails."""
        self._liststore.clear()
        self._layout.set_size(0, 0)
        self._height = 0
        self._loaded = False
        self._stop_update = True

    def resize(self):
        """Reload the thumbnails with the size specified by in the
        preferences.
        """
        self._column.set_fixed_width(prefs['thumbnail size'] + 7)
        self._layout.set_size_request(prefs['thumbnail size'] + 7, 0)
        self.clear()
        self.load_thumbnails()

    def load_thumbnails(self):
        """Load the thumbnails, if it is appropriate to do so."""
        if any([self._loaded,
                not self._window.file_handler.file_loaded,
                not prefs['show thumbnails'],
                prefs['hide all'],
                (self._window.is_fullscreen and prefs['hide all in fullscreen'])]):
            return

        self._loaded = True
        if self._load_task is not None:
            GObject.source_remove(self._load_task)
        self._load_task = GObject.idle_add(self._load)

    def update_select(self):
        """Select the thumbnail for the currently viewed page and make sure
        that the thumbbar is scrolled so that the selected thumb is in view.
        """
        if not self._loaded:
            return
        self._selection.select_path(
                self._window.file_handler.get_current_page() - 1)
        rect = self._treeview.get_background_area(Gtk.TreePath(self._window.file_handler.get_current_page() - 1), self._column)
        if rect.y < self._vadjust.get_value() or rect.y + rect.height > self._vadjust.get_value() + self._vadjust.get_page_size():
            value = rect.y + (rect.height // 2) - (self._vadjust.get_page_size() // 2)
            value = max(0, value)
            value = min(self._vadjust.get_upper() - self._vadjust.get_page_size(), value)
            self._vadjust.set_value(value)

    def _load(self):
        if self._window.file_handler.archive_type is not None:
            create = False
        else:
            create = prefs['create thumbnails']
        self._stop_update = False
        for i in range(1, self._window.file_handler.get_number_of_pages() + 1):
            pixbuf = self._window.file_handler.get_thumbnail(i, prefs['thumbnail size'], prefs['thumbnail size'], create)
            if prefs['show page numbers on thumbnails']:
                _add_page_number(pixbuf, i)
            pixbuf = image.add_border(pixbuf, 1)
            self._liststore.append([pixbuf])
            while Gtk.events_pending():
                Gtk.main_iteration()
            if self._stop_update:
                return
            self._height += self._treeview.get_background_area(Gtk.TreePath(i - 1), self._column).height
            self._layout.set_size(0, self._height)
        self._stop_update = True
        self.update_select()

    def _get_selected_row(self):
        """Return the index of the currently selected row."""
        selected_rows = self._selection.get_selected_rows()
        try:
            return selected_rows[1][0][0]
        except IndexError:
            return None

    # noinspection PyUnusedLocal
    def _selection_event(self, tree_selection):
        """Handle events due to changed thumbnail selection."""
        if self._get_selected_row() is not None:
            self._window.set_page(self._get_selected_row() + 1)

    # noinspection PyUnusedLocal
    def _scroll_event(self, widget, event):
        """Handle scroll events on the thumbnail sidebar."""
        if event.direction == Gdk.ScrollDirection.UP:
            self._vadjust.set_value(self._vadjust.get_value() - 60)
        elif event.direction == Gdk.ScrollDirection.DOWN:
            upper = self._vadjust.get_upper() - self._vadjust.get_page_size()
            self._vadjust.set_value(min(self._vadjust.get_value() + 60, upper))

    # noinspection PyUnusedLocal
    def _drag_data_get(self, treeview, context, selection, *args):
        """
        Put the URI of the selected file into the SelectionData, so that
        the file can be copied (e.g. to a file manager).
        """
        selected = self._get_selected_row()
        path = self._window.file_handler.get_path_to_page(selected + 1)
        uri = 'file://localhost' + pathname2url(path)
        selection.set_uris([uri])

    def _drag_begin(self, treeview, context):
        """
        We hook up on drag_begin events so that we can set the hotspot
        for the cursor at the top left corner of the thumbnail (so that we
        might actually see where we are dropping!).
        """
        path = treeview.get_cursor()[0]
        pixmap = treeview.create_row_drag_icon(path)
        Gtk.drag_set_icon_surface(context, pixmap)


def _add_page_number(pixbuf, page):
    """Add page number <page> in a black rectangle in the top left corner of
    <pixbuf>. This is highly dependent on the dimensions of the built-in
    font in PIL (bad). If the PIL font was changed, this function would
    likely produce badly positioned numbers on the pixbuf.
    """
    text = str(page)
    width = min(6 * len(text) + 2, pixbuf.get_width())
    height = min(10, pixbuf.get_height())
    im = Image.new('RGB', (width, height), (0, 0, 0))
    draw = ImageDraw.Draw(im)
    draw.text((1, -1), text, fill=(255, 255, 255))
    num_pixbuf = image.pil_to_pixbuf(im)
    num_pixbuf.copy_area(0, 0, width, height, pixbuf, 0, 0)
