# coding=utf-8
"""filehandler.py - File handler."""
from __future__ import absolute_import, division

import gc
import os
import re
import shutil
import sys
import tempfile
import threading

from gi.repository import Gtk, GdkPixbuf

from src import archive
from src import cursor
from src import encoding
from src import image
from src import thumbnail
from src.image import get_supported_format_extensions_preg
from src.preferences import prefs

# Compatibility
try:
    # noinspection PyUnresolvedReferences
    range = xrange  # Python2
except NameError:
    pass


class FileHandler(object):
    """The FileHandler keeps track of images, pages, caches and reads files.

    When the Filehandler's methods refer to pages, they are indexed from 1,
    i.e. the first page is page 1 etc.

    Other modules should *never* read directly from the files pointed to by
    paths given by the FileHandler's methods. The files are not even
    guaranteed to exist at all times since the extraction of archives is
    threaded.
    """

    def __init__(self, window):
        self.file_loaded = False
        self.archive_type = None

        self._window = window
        self._base_path = None
        self._tmp_dir = tempfile.mkdtemp(prefix='comix.', suffix=os.sep)
        self._image_files = []
        self._current_image_index = 0
        self._comment_files = []
        self._raw_pixbufs = {}
        self._name_table = {}
        self._extractor = archive.Extractor()
        self._condition = None

        self._image_re = re.compile('\.(' + '|'.join(get_supported_format_extensions_preg()) + ')\s*$', re.I)

        self.update_comment_extensions()

    def _get_pixbuf(self, index):
        """Return the pixbuf indexed by <index> from cache.
        Pixbufs not found in cache are fetched from disk first.
        """
        if index not in self._raw_pixbufs:
            self._wait_on_page(index + 1)
            pxb_err = False
            try:
                """ Check for gif in the name of the file.  If it is a gif,
                and the user wishes GIFs to be animated, load it as a
                PixbufAnimation and make sure that it actually is animated. 
                If it isn't animated, load a pixbuf instead.  """
                if not (prefs['animate gifs'] or prefs['animate']) \
                        or "gif" not in self._image_files[index][-3:].lower():
                    self._raw_pixbufs[index] = GdkPixbuf.Pixbuf.new_from_file(self._image_files[index])
                else:
                    self._raw_pixbufs[index] = GdkPixbuf.PixbufAnimation(self._image_files[index])
                    if self._raw_pixbufs[index].is_static_image():
                        self._raw_pixbufs[index] = self._raw_pixbufs[index].get_static_image()
            except Exception:
                pxb_err = True

            if pxb_err:
                try:
                    im = image.Image.open(self._image_files[index])
                    self._raw_pixbufs[index] = image.pil_to_pixbuf(im)
                except Exception:
                    self._raw_pixbufs[index] = self._get_missing_image()
        return self._raw_pixbufs[index]

    def get_pixbufs(self, single=False):
        """Return the pixbuf(s) for the image(s) that should be currently
        displayed, from cache. Return two pixbufs in double-page mode unless
        <single> is True. Pixbufs not found in cache are fetched from
        disk first.
        """
        if not self._window.displayed_double() or single:
            return self._get_pixbuf(self._current_image_index)
        return (self._get_pixbuf(self._current_image_index),
                self._get_pixbuf(self._current_image_index + 1))

    def do_cacheing(self):
        """Make sure that the correct pixbufs are stored in cache. These
        are (in the current implementation) the current image(s), and
        if cacheing is enabled, also the one or two pixbufs before and
        after them. All other pixbufs are deleted and garbage collected
        directly in order to save memory.
        """
        # Get list of wanted pixbufs.
        first_wanted = self._current_image_index
        last_wanted = first_wanted + 1
        if self._window.is_double_page:
            last_wanted += 1
        if prefs['cache']:
            first_wanted -= self._get_backward_step_length()
            last_wanted += self._get_forward_step_length()
        first_wanted = max(0, first_wanted)
        last_wanted = min(self.get_number_of_pages(), last_wanted)
        wanted_pixbufs = range(first_wanted, last_wanted)

        # Remove old pixbufs.
        for page in set(self._raw_pixbufs) - set(wanted_pixbufs):
            del self._raw_pixbufs[page]
        if sys.version_info[:3] >= (2, 5, 0):
            gc.collect(0)
        else:
            gc.collect()

        # Cache new pixbufs if they are not already cached.
        for wanted in wanted_pixbufs:
            self._get_pixbuf(wanted)

    def next_page(self):
        """Set up filehandler to the next page. Return True if this results
        in a new page.
        """
        if not self.file_loaded and not self._base_path:
            return False
        old_page = self.get_current_page()
        viewed = self._window.displayed_double() and 2 or 1
        if self.get_current_page() + viewed > self.get_number_of_pages():
            if prefs['auto open next archive'] and self.archive_type is not None:
                self._open_next_archive()
            return False
        self._current_image_index += self._get_forward_step_length()
        return old_page != self.get_current_page()

    def previous_page(self):
        """Set up filehandler to the previous page. Return True if this
        results in a new page.
        """
        if not self.file_loaded and not self._base_path:
            return False
        if self.get_current_page() == 1:
            if prefs['auto open next archive'] and self.archive_type is not None:
                self._open_previous_archive()
            return False
        old_page = self.get_current_page()
        step = self._get_backward_step_length()
        step = min(self._current_image_index, step)
        self._current_image_index -= step
        if step == 2 and self.get_virtual_double_page():
            self._current_image_index += 1
        return old_page != self.get_current_page()

    def first_page(self):
        """Set up filehandler to the first page. Return True if this
        results in a new page.
        """
        if not self.file_loaded:
            return False
        old_page = self.get_current_page()
        self._current_image_index = 0
        return old_page != self.get_current_page()

    def last_page(self):
        """Set up filehandler to the last page. Return True if this results
        in a new page.
        """
        if not self.file_loaded:
            return False
        old_page = self.get_current_page()
        offset = self._window.is_double_page and 2 or 1
        offset = min(self.get_number_of_pages(), offset)
        self._current_image_index = self.get_number_of_pages() - offset
        if offset == 2 and self.get_virtual_double_page():
            self._current_image_index += 1
        return old_page != self.get_current_page()

    def set_page(self, page_num):
        """Set up filehandler to the page <page_num>. Return True if this
        results in a new page.
        """
        if not 0 < page_num <= self.get_number_of_pages():
            return False
        old_page = self.get_current_page()
        self._current_image_index = page_num - 1
        return old_page != self.get_current_page()

    def get_virtual_double_page(self):
        """Return True if the current state warrants use of virtual
        double page mode (i.e. if double page mode is on, the corresponding
        preference is set, and one of the two images that should normally
        be displayed has a width that exceeds its height).
        """
        if not self._window.is_double_page or not prefs[
            'no double page for wide images'] or self.get_current_page() == self.get_number_of_pages():
            return False

        page1 = self._get_pixbuf(self._current_image_index)
        if page1.get_width() > page1.get_height():
            return True
        page2 = self._get_pixbuf(self._current_image_index + 1)
        if page2.get_width() > page2.get_height():
            return True
        return False

    def open_file(self, path, start_page=1):
        """Open the file pointed to by <path>.

        If <start_page> is not set we set the current
        page to 1 (first page), if it is set we set the current page to the
        value of <start_page>. If <start_page> is non-positive it means the
        last image.

        Return True if the file is successfully loaded.
        """
        dir_path = None
        # If the given <path> is invalid we update the statusbar.
        # (bad idea if it's permanently hidden; but no better way nearby)
        if not os.access(path, os.R_OK):
            self._window.statusbar.set_message(
                    _('Could not open {}: Permission denied.').format(path))
            return False
        if os.path.isdir(path):
            dir_path = path  # handle it as a directory later.
            # likely, can also check `os.access(path, os.X_OK)` instead of
            # getting 'unknown type'.
        elif not os.path.isfile(path):  # ...not dir or normal file.
            self._window.statusbar.set_message(
                    _('Could not open {}: No such file.').format(path))
            return False
        self.archive_type = archive.archive_mime_type(path)
        if self.archive_type is None and not is_image_file(path) and not dir_path:
            self._window.statusbar.set_message(_('Could not open {}: Unknown file type.').format(path))
            return False

        # We close the previously opened file.
        self._window.cursor_handler.set_cursor_type(cursor.WAIT)
        if self.file_loaded:
            self.close_file()
        while Gtk.events_pending():
            Gtk.main_iteration()

        unknown_files = []
        # If <path> is an archive we create an Extractor for it and set the
        # files in it with file endings indicating image files or comments
        # as the ones to be extracted.
        if self.archive_type is not None:
            self._base_path = path
            self._condition = self._extractor.setup(path, self._tmp_dir)
            files = self._extractor.get_files()
            image_files = [f for f in files if self._image_re.search(f)]
            alphanumeric_sort(image_files)
            comment_files = [f for f in files if self._comment_re.search(f)]
            # Allow managing sub-archives
            unknown_files = [f for f in files if f not in image_files + comment_files]
            self._image_files = \
                [os.path.join(self._tmp_dir, f) for f in image_files]
            self._comment_files = \
                [os.path.join(self._tmp_dir, f) for f in comment_files]
            for name, full_path in zip(image_files, self._image_files):
                self._name_table[full_path] = name
            for name, full_path in zip(comment_files, self._comment_files):
                self._name_table[full_path] = name
            for name in unknown_files:
                self._name_table[self._tmp_dir + name] = name

            self._redo_priority_ordering(start_page, image_files)

            self._extractor.extract()
        else:
            # If <path> is an image we scan its directory for more (or for
            # any at all if <path> is directory).
            self._base_path = dir_path if dir_path else os.path.dirname(path)
            # Not necessary to sort *all* of it, but whatever.
            for f in list_dir_sorted(self._base_path):
                fpath = os.path.join(self._base_path, f)
                if is_image_file(fpath):
                    self._image_files.append(fpath)
            if dir_path:
                self._redo_priority_ordering(start_page, self._image_files)
            else:
                self._current_image_index = self._image_files.index(path)

        # Manage subarchive
        if unknown_files:
            has_subarchive = False
            for (i, name) in enumerate(unknown_files):
                f = self._tmp_dir + name
                self._wait_on_file(f)
                if archive.archive_mime_type(f) is not None:
                    self._open_subarchive(os.path.dirname(f),
                                          os.path.basename(f))
                    has_subarchive = True
            # Allows to avoid any behaviour changes if there was no subarchive..
            if has_subarchive:
                # Now, get all files, and move them into the temp directory
                # while renaming them to avoid any sorting error.
                self._image_files = []
                tmpdir_len = len(self._tmp_dir)
                extracted_files = []
                for filename in get_next_file(self._tmp_dir):
                    dst = filename[tmpdir_len:].replace("/", "_")
                    extracted_files.append(dst)
                    dst = self._tmp_dir + dst
                    shutil.move(filename, dst)
                    self._image_files.append(dst)
                self._comment_files = [f for f in self._image_files if self._comment_re.search(f)]
                self._image_files = [f for f in self._image_files if self._image_re.search(f)]
                alphanumeric_sort(self._image_files)
                self._name_table.clear()
                for full_path in self._image_files + self._comment_files:
                    self._name_table[full_path] = os.path.basename(full_path)
                self._extractor.set_files(extracted_files, True)
                # redo calculation of current_index from start_page
                self._redo_priority_ordering(start_page, self._image_files)

        if not self._image_files:
            self._window.statusbar.set_message(_("No images or subarchives in '{}'").format(
                                               os.path.basename(path)))
            self.file_loaded = False
        else:
            self.file_loaded = True

        alphanumeric_sort(self._comment_files)
        self._window.cursor_handler.set_cursor_type(cursor.NORMAL)
        self._window.ui_manager.set_sensitivities()
        self._window.new_page()
        self._window.ui_manager.recent.add(path)

    def _redo_priority_ordering(self, start_page, lst):
        if start_page <= 0:
            if self._window.is_double_page:
                self._current_image_index = self.get_number_of_pages() - 2
            else:
                self._current_image_index = self.get_number_of_pages() - 1
        else:
            self._current_image_index = start_page - 1
        self._current_image_index = max(0, self._current_image_index)

        depth = self._window.is_double_page and 2 or 1
        priority_ordering = (
            list(range(self._current_image_index,
                  self._current_image_index + depth * 2)) +
            list(range(self._current_image_index - depth,
                  self._current_image_index))[::-1])
        priority_ordering = [lst[p] for p in priority_ordering
                             if 0 <= p <= self.get_number_of_pages() - 1]
        for i, name in enumerate(priority_ordering):
            lst.remove(name)
            lst.insert(i, name)

    def _open_subarchive(self, dir_name, path):
        """Allows to recursively extract all subarchives"""
        extractor = archive.Extractor()
        condition = extractor.setup(dir_name + "/" + path, dir_name)
        sub_files = extractor.get_files()
        alphanumeric_sort(sub_files)
        extractor.set_files(sub_files)
        extractor.extract()
        for name in sub_files:
            condition.acquire()
            while not extractor.is_ready(name):
                condition.wait()
            condition.release()
            name = dir_name + "/" + name
            if archive.archive_mime_type(name) is not None:
                self._open_subarchive(os.path.dirname(name), os.path.basename(name))
        os.remove(dir_name + "/" + path)

    def close_file(self, *args):
        """Run tasks for "closing" the currently opened file(s)."""
        self.file_loaded = False
        self._base_path = None
        self._image_files = []
        self._current_image_index = 0
        self._comment_files = []
        self._name_table.clear()
        self._raw_pixbufs.clear()
        self._window.clear()
        self._window.ui_manager.set_sensitivities()
        self._extractor.stop()
        thread_delete(self._tmp_dir)
        self._tmp_dir = tempfile.mkdtemp(prefix='comix.', suffix=os.sep)
        gc.collect()

    def cleanup(self):
        """Run clean-up tasks. Should be called prior to exit."""
        self._extractor.stop()
        thread_delete(self._tmp_dir)

    def is_last_page(self):
        """Return True if at the last page."""
        if self._window.displayed_double():
            return self.get_current_page() + 1 >= self.get_number_of_pages()
        else:
            return self.get_current_page() == self.get_number_of_pages()

    def get_number_of_pages(self):
        """Return the number of pages in the current archive/directory."""
        return len(self._image_files)

    def get_current_page(self):
        """Return the current page number."""
        return self._current_image_index + 1

    def get_number_of_comments(self):
        """Return the number of comments in the current archive."""
        return len(self._comment_files)

    def get_comment_text(self, num):
        """Return the text in comment <num> or None if comment <num> is not
        readable.
        """
        self._wait_on_comment(num)
        try:
            fd = open(self._comment_files[num - 1], 'rb')
            text = fd.read()
            fd.close()
        except Exception:
            text = None
        return text

    def get_comment_name(self, num):
        """Return the filename of comment <num>."""
        return self._comment_files[num - 1]

    def update_comment_extensions(self):
        """Update the regular expression used to filter out comments in
        archives by their filename.
        """
        exts = '|'.join(prefs['comment extensions'])
        self._comment_re = re.compile(r'\.({})\s*$'.format(exts), re.I)

    def get_path_to_page(self, page=None):
        """Return the full path to the image file for <page>, or the current
        page if <page> is None.
        """
        if page is None:
            return self._image_files[self._current_image_index]
        return self._image_files[page - 1]

    def get_path_to_base(self):
        """Return the full path to the current base (path to archive or
        image directory.)
        """
        return self._base_path

    def get_real_path(self):
        """Return the "real" path to the currently viewed file, i.e. the
        full path to the archive or the full path to the currently
        viewed image.
        """
        if self.archive_type is not None:
            return self.get_path_to_base()
        return self.get_path_to_page()

    def get_page_filename(self, page=None, double=False):
        """Return the filename of the <page>, or the filename of the
        currently viewed page if <page> is None. If <double> is True, return
        a tuple (p, p') where p is the filename of <page> (or the current
        page) and p' is the filename of the page after.
        """
        if page is None:
            page = self._current_image_index + 1
        if double:
            first = os.path.basename(self.get_path_to_page(page))
            second = os.path.basename(self.get_path_to_page(page + 1))
            return first, second
        return os.path.basename(self.get_path_to_page(page))

    def get_base_filename(self):
        """Return the filename of the current base (archive filename or
        directory name).
        """
        return os.path.basename(self.get_path_to_base())

    def get_pretty_current_filename(self):
        """Return a string with the name of the currently viewed file that is
        suitable for printing.
        """
        if self.archive_type is not None:
            name = os.path.basename(self._base_path)
        else:
            name = os.path.join(os.path.basename(self._base_path),
                                os.path.basename(self._image_files[self._current_image_index]))
        return encoding.to_unicode(name)

    def get_size(self, page=None):
        """Return a tuple (width, height) with the size of <page>. If <page>
        is None, return the size of the current page.
        """
        self._wait_on_page(page)
        info = GdkPixbuf.Pixbuf.get_file_info(self.get_path_to_page(page))
        if info is not None:
            return info[1], info[2]
        return 0, 0

    def get_mime_name(self, page=None):
        """Return a string with the name of the mime type of <page>. If
        <page> is None, return the mime type name of the current page.
        """
        self._wait_on_page(page)
        info = GdkPixbuf.Pixbuf.get_file_info(self.get_path_to_page(page))
        if info is not None:
            return info[0]['name'].upper()
        return _('Unknown filetype')

    def get_thumbnail(self, page=None, width=128, height=128, create=False):
        """Return a thumbnail pixbuf of <page> that fit in a box with
        dimensions <width>x<height>. Return a thumbnail for the current
        page if <page> is None.

        If <create> is True, and <width>x<height> <= 128x128, the
        thumbnail is also stored on disk.
        """
        self._wait_on_page(page)
        path = self.get_path_to_page(page)
        if width <= 128 and height <= 128:
            thumb = thumbnail.get_thumbnail(path, create)
        else:
            try:
                if "gif" not in path[-3:].lower():
                    thumb = GdkPixbuf.Pixbuf.new_from_file_at_size(path, width, height)
                else:
                    thumb = GdkPixbuf.PixbufAnimation(path).get_static_image()
                    src_width = thumb.get_width()
                    src_height = thumb.get_height()
                    if float(src_width) / width > float(src_height) / height:
                        thumb = thumb.scale_simple(width,
                                                   int(max(src_height * width / src_width, 1)), GdkPixbuf.InterpType.TILES)
                    else:
                        thumb = thumb.scale_simple(int(max(src_width * height / src_height, 1)),
                                                   height, GdkPixbuf.InterpType.TILES)
            except Exception:
                thumb = None
        if thumb is None:
            thumb = self._get_missing_image()
        thumb = image.fit_in_rectangle(thumb, width, height)
        return thumb

    def get_stats(self, page=None):
        """Return a stat object, as used by the stat module, for <page>.
        If <page> is None, return a stat object for the current page.
        Return None if the stat object can not be produced (e.g. broken file).
        """
        self._wait_on_page(page)
        try:
            stats = os.stat(self.get_path_to_page(page))
        except Exception:
            stats = None
        return stats

    def _get_forward_step_length(self):
        """Return the step length for switching pages forwards."""
        if (self._window.displayed_double() and
                prefs['double step in double page mode']):
            return 2
        return 1

    def _get_backward_step_length(self):
        """Return the step length for switching pages backwards."""
        if (self._window.is_double_page and
                prefs['double step in double page mode']):
            return 2
        return 1

    def _open_next_archive(self):
        """Open the archive that comes directly after the currently loaded
        archive in that archive's directory listing, sorted alphabetically.
        """
        arch_dir = os.path.dirname(self._base_path)
        files = list_dir_sorted(arch_dir)
        try:
            current_index = files.index(os.path.basename(self._base_path))
        except ValueError:
            return
        for f in files[current_index + 1:]:
            path = os.path.join(arch_dir, f)
            if archive.archive_mime_type(path) is not None:
                self.open_file(path)
                return

    def _open_previous_archive(self):
        """Open the archive that comes directly before the currently loaded
        archive in that archive's directory listing, sorted alphabetically.
        """
        arch_dir = os.path.dirname(self._base_path)
        files = list_dir_sorted(arch_dir)
        try:
            current_index = files.index(os.path.basename(self._base_path))
        except ValueError:
            return
        for f in reversed(files[:current_index]):
            path = os.path.join(arch_dir, f)
            if archive.archive_mime_type(path) is not None:
                self.open_file(path, 0)
                return

    def _get_missing_image(self):
        """Return a pixbuf depicting a missing/broken image."""
        return self._window.render_icon(Gtk.STOCK_MISSING_IMAGE,
                                        Gtk.IconSize.DIALOG)

    def _wait_on_page(self, page):
        """Block the running (main) thread until the file corresponding to
        image <page> has been fully extracted.
        """
        path = self.get_path_to_page(page)
        self._wait_on_file(path)

    def _wait_on_comment(self, num):
        """Block the running (main) thread until the file corresponding to
        comment <num> has been fully extracted.
        """
        path = self._comment_files[num - 1]
        self._wait_on_file(path)

    def _wait_on_file(self, path):
        """Block the running (main) thread if the file <path> is from an
        archive and has not yet been extracted. Return when the file is
        ready.
        """
        if self.archive_type is None:
            return
        name = self._name_table[path]
        self._condition.acquire()
        while not self._extractor.is_ready(name):
            self._condition.wait()
        self._condition.release()


def thread_delete(path):
    """Start a threaded removal of the directory tree rooted at <path>.
    This is to avoid long blockings when removing large temporary dirs.
    """
    del_thread = threading.Thread(target=shutil.rmtree, args=(path,))
    del_thread.setDaemon(False)
    del_thread.start()


def is_image_file(path):
    """Return True if the file at <path> is an image file recognized by PyGTK.
    """
    if os.path.isfile(path):
        info = GdkPixbuf.Pixbuf.get_file_info(path)
        return info is not None
    return False


def alphanumeric_sort(filenames):
    """Do an in-place alphanumeric sort of the strings in <filenames>,
    such that for an example "1.jpg", "2.jpg", "10.jpg" is a sorted
    ordering.
    """

    def _format_substring(s):
        if s.isdigit():
            return int(s)
        return s.lower()

    rec = re.compile("\d+|\D+")
    filenames.sort(key=lambda s: [_format_substring(i) for i in rec.findall(s)])


def list_dir_sorted(dir_name):
    """
    Helper for listing the directory contents with the preferred
    sorting.
     """
    files = os.listdir(dir_name)
    alphanumeric_sort(files)
    return files


def get_next_file(dir_name):
    """Yields the next file in the whole file hierarchy
       with dir_name as the top"""
    for (a_dir, dirs, files) in os.walk(dir_name):
        for filename in files:
            yield a_dir + '/' + filename
