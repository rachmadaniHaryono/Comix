#!/usr/bin/env python
# coding=utf-8
from __future__ import absolute_import, print_function

"""Comix - GTK Comic Book Viewer

Copyright (C) 2005-2009 Pontus Ekberg
<herrekberg@users.sourceforge.net>
"""

# -------------------------------------------------------------------------
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# -------------------------------------------------------------------------

import getopt
import gettext
import os
import signal
import sys

# Check for PyGobject and Pillow dependencies.
try:
    # noinspection PyUnresolvedReferences
    import gi

    gi.require_version("Gtk", "3.0")
    # noinspection PyUnresolvedReferences
    # noinspection PyUnresolvedReferences
    from gi.repository import GObject, Gtk

    GObject.threads_init()
except AssertionError:
    print("You don't have the required versions of GTK+ and/or PyGObject installed.")
    print(
        "Installed GTK+ version is: {}".format(
            ".".join([str(n) for n in Gtk.gtk_version])
        )
    )
    print("Required GTK+ version is: 3.0.3 or higher\n")
    sys.exit(1)
except ImportError:
    print("PyGObject version 3.0.3 or higher is required to run Comix.")
    print("No version of PyGObject was found on your system.")
    sys.exit(1)

try:
    # noinspection PyUnresolvedReferences
    from PIL import Image
except ImportError:
    print('Python Imaging Library (PIL) version 1.1.5 or higher or Pillow is required.')
    print('No version of the Python Imaging Library was found on your system.')
    sys.exit(1)


from src import constants, deprecated, icons, preferences
from src.main import MainWindow


def print_help():
    """Print the command-line help text and exit."""
    print('Usage:')
    print('  comix [OPTION...] [PATH]')
    print('\nView images and comic book archives.\n')
    print('Options:')
    print('  -h, --help              Show this help and exit.')
    print('  -f, --fullscreen        Start the application in fullscreen mode.')
    print('  -l, --library           Show the library on startup.')
    print('  -a, --animate-gifs      Play animations in GIF files.')
    sys.exit(1)


def run(argv):
    """Run the program."""
    # Use gettext translations as found in the source dir, otherwise based on
    # the install path.
    exec_path = os.path.abspath(argv[0])
    base_dir = os.path.dirname(os.path.dirname(exec_path))
    if os.path.isdir(os.path.join(base_dir, "messages")):
        gettext.install("comix", os.path.join(base_dir, "messages"))
    else:
        gettext.install("comix", os.path.join(base_dir, "share/locale"))

    animate_gifs = False
    fullscreen = False
    show_library = False
    open_path = None
    open_page = 1
    try:
        opts, args = getopt.gnu_getopt(
            argv[1:], "fhla", ["fullscreen", "help", "library", "animate-gifs"]
        )
    except getopt.GetoptError:
        opts = args = []
        print_help()
    for opt, value in opts:
        if opt in ('-h', '--help'):
            print_help()
        elif opt in ('-f', '--fullscreen'):
            fullscreen = True
        elif opt in ('-l', '--library'):
            show_library = True
        if opt in ('-a', '--animate-gifs'):
            animate_gifs = True

    if not os.path.exists(constants.DATA_DIR):
        os.makedirs(constants.DATA_DIR, 0o700)

    if not os.path.exists(constants.CONFIG_DIR):
        os.makedirs(constants.CONFIG_DIR, 0o700)

    deprecated.move_files_to_xdg_dirs()
    preferences.read_preferences_file()
    icons.load_icons()

    if len(args) >= 1:
        open_path = os.path.abspath(args[0])  # try to open whatever it is.
    elif preferences.prefs['auto load last file']:
        open_path = preferences.prefs['path to last file']
        open_page = preferences.prefs['page of last file']

    window = MainWindow(
        animate_gifs=animate_gifs,
        fullscreen=fullscreen,
        show_library=show_library,
        open_path=open_path,
        open_page=open_page,
    )
    deprecated.check_for_deprecated_files(window)

    def sigterm_handler(signal, frame):
        GObject.idle_add(window.terminate_program)

    signal.signal(signal.SIGTERM, sigterm_handler)

    try:
        Gtk.main()
    except KeyboardInterrupt:  # Will not always work because of threading.
        window.terminate_program()


if __name__ == '__main__':
    run(argv=sys.argv)
