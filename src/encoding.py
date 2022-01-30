# coding=utf-8
"""encoding.py - Encoding handler."""
from __future__ import absolute_import

import sys

_filesystemencoding = sys.getfilesystemencoding()


def to_unicode(string):
    """Convert <string> to unicode. First try the default filesystem
    encoding, and then fall back on some common encodings. If none
    of the convertions are successful, "???" is returned.
    """
    try:

        if isinstance(string, unicode):
            return string
        for encoding in (_filesystemencoding, 'utf-8', 'latin-1'):
            try:
                ustring = unicode(string, encoding)
                return ustring
            except (UnicodeError, LookupError):
                pass
        return u'???'
    except NameError:
        return string
