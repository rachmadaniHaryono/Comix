# coding=utf-8
"""event.py - Event handling (keyboard, mouse, etc.) for the main window.

Logically this isn't really a separate module from main.py, but it is
given its own file for the sake of readability.
"""
from __future__ import absolute_import

try:
    from urllib import url2pathname  # Py2
except ImportError:
    from urllib.request import url2pathname  # Py3

from gi.repository import Gdk

from src import cursor
from src import preferences
from src.preferences import prefs


def _valwarp(cur, max_, tolerance=3):
    """ Helper function for wrapping the cursor around the screen when it
    comes within `tolerance` to a border. """
    if cur < tolerance:
        return cur + (max_ - 2 * tolerance)
    if (max_ - cur) < tolerance:
        return cur - (max_ - 2 * tolerance)
    return cur


class EventHandler(object):
    def __init__(self, window):
        self._window = window
        self._last_pointer_pos_x = 0
        self._last_pointer_pos_y = 0
        self._pressed_pointer_pos_x = 0
        self._pressed_pointer_pos_y = 0
        self._extra_scroll_events = 0  # For scrolling "off the page".

    def resize_event(self, widget, event):
        """Handle events from resizing and moving the main window."""
        if not self._window.is_fullscreen:
            prefs['window x'], prefs['window y'] = self._window.get_position()
        if event.width != self._window.width or event.height != self._window.height:
            if not self._window.is_fullscreen:
                prefs['window width'] = event.width
                prefs['window height'] = event.height
            self._window.width = event.width
            self._window.height = event.height
            self._window.draw_image(scroll=False)

    def key_press_event(self, widget, event, *args):
        """Handle key press events on the main window."""
        # ----------------------------------------------------------------
        # Some navigation keys that work as well as the accelerators in
        # ui.py.
        # ----------------------------------------------------------------
        if event.keyval in (Gdk.KEY_KP_Page_Up, Gdk.KEY_BackSpace):
            self._window.previous_page()
        elif event.keyval == Gdk.KEY_KP_Page_Down:
            self._window.next_page()

        # ----------------------------------------------------------------
        # Numpad (without numlock) aligns the image depending on the key.
        # ----------------------------------------------------------------
        elif event.keyval == Gdk.KEY_KP_1:
            self._window.scroll_to_fixed(horiz='left', vert='bottom')
        elif event.keyval == Gdk.KEY_KP_2:
            self._window.scroll_to_fixed(horiz='middle', vert='bottom')
        elif event.keyval == Gdk.KEY_KP_3:
            self._window.scroll_to_fixed(horiz='right', vert='bottom')
        elif event.keyval == Gdk.KEY_KP_4:
            self._window.scroll_to_fixed(horiz='left', vert='middle')
        elif event.keyval == Gdk.KEY_KP_5:
            self._window.scroll_to_fixed(horiz='middle', vert='middle')
        elif event.keyval == Gdk.KEY_KP_6:
            self._window.scroll_to_fixed(horiz='right', vert='middle')
        elif event.keyval == Gdk.KEY_KP_7:
            self._window.scroll_to_fixed(horiz='left', vert='top')
        elif event.keyval == Gdk.KEY_KP_8:
            self._window.scroll_to_fixed(horiz='middle', vert='top')
        elif event.keyval == Gdk.KEY_KP_9:
            self._window.scroll_to_fixed(horiz='right', vert='top')

        # ----------------------------------------------------------------
        # Enter/exit fullscreen. 'f' is also a valid key, defined as an
        # accelerator elsewhere.
        # ----------------------------------------------------------------
        elif event.keyval == Gdk.KEY_Escape:
            self._window.actiongroup.get_action('fullscreen').set_active(False)
        elif event.keyval == Gdk.KEY_F11:
            self._window.actiongroup.get_action('fullscreen').activate()

        # ----------------------------------------------------------------
        # Zooming commands for manual zoom mode. These keys complement
        # others (with the same action) defined as accelerators.
        # ----------------------------------------------------------------
        elif event.keyval in (Gdk.KEY_plus, Gdk.KEY_equal):
            self._window.actiongroup.get_action('zoom_in').activate()
        elif event.keyval == Gdk.KEY_minus:
            self._window.actiongroup.get_action('zoom_out').activate()
        elif event.keyval in (Gdk.KEY_0, Gdk.KEY_KP_0) and 'GDK_CONTROL_MASK' in event.get_state().value_names:
            self._window.actiongroup.get_action('zoom_original').activate()

        # ----------------------------------------------------------------
        # Arrow keys scroll the image, except in best fit mode where
        # they flip pages instead.
        # ----------------------------------------------------------------
        elif event.keyval in (Gdk.KEY_Down, Gdk.KEY_KP_Down):
            if not self._window.zoom_mode == preferences.ZOOM_MODE_BEST:
                self._scroll_with_flipping(0, 50)
            else:
                self._window.next_page()
        elif event.keyval in (Gdk.KEY_Up, Gdk.KEY_KP_Up):
            if not self._window.zoom_mode == preferences.ZOOM_MODE_BEST:
                self._scroll_with_flipping(0, -50)
            else:
                self._window.previous_page()
        elif event.keyval in (Gdk.KEY_Right, Gdk.KEY_KP_Right):
            if not self._window.zoom_mode == preferences.ZOOM_MODE_BEST:
                self._scroll_with_flipping(50, 0)
            else:
                self._window.next_page()
        elif event.keyval in (Gdk.KEY_Left, Gdk.KEY_KP_Left):
            if not self._window.zoom_mode == preferences.ZOOM_MODE_BEST:
                self._scroll_with_flipping(-50, 0)
            else:
                self._window.previous_page()

        # ----------------------------------------------------------------
        # Space key scrolls down a percentage of the window height or the
        # image height at a time. When at the bottom it flips to the next
        # page.
        #
        # It also has a "smart scrolling mode" in which we try to follow
        # the flow of the comic.
        #
        # If Shift is pressed we should backtrack instead.
        # ----------------------------------------------------------------
        elif event.keyval in [Gdk.KEY_space, Gdk.KEY_KP_Home,
                              Gdk.KEY_KP_End]:
            x_step, y_step = self._window.get_visible_area_size()
            x_step = int(x_step * 0.9)
            y_step = int(y_step * 0.9)
            if self._window.is_manga_mode:
                x_step *= -1
            if 'GDK_SHIFT_MASK' in event.get_state().value_names or event.keyval == Gdk.KEY_KP_Home:
                if prefs['smart space scroll']:
                    if self._window.displayed_double():
                        if self._window.is_on_first_page():
                            if not self._window.scroll(-x_step, 0, 'first'):
                                if not self._window.scroll(0, -y_step):
                                    self._window.previous_page()
                                else:
                                    self._window.scroll_to_fixed(
                                            horiz='endfirst')
                        else:
                            if not self._window.scroll(-x_step, 0, 'second'):
                                if not self._window.scroll(0, -y_step):
                                    if not self._window.scroll_to_fixed(
                                            horiz='endfirst'):
                                        self._window.previous_page()
                                    else:
                                        self._window.scroll_to_fixed(
                                                vert='bottom')
                                else:
                                    self._window.scroll_to_fixed(
                                            horiz='endsecond')
                    else:
                        if not self._window.scroll(-x_step, 0):
                            if not self._window.scroll(0, -y_step):
                                self._window.previous_page()
                            else:
                                self._window.scroll_to_fixed(horiz='endfirst')
                else:
                    if (self._window.zoom_mode == preferences.ZOOM_MODE_BEST or
                            not self._window.scroll(0, -y_step)):
                        self._window.previous_page()
            else:
                if prefs['smart space scroll']:
                    if self._window.displayed_double():
                        if self._window.is_on_first_page():
                            if not self._window.scroll(x_step, 0, 'first'):
                                if not self._window.scroll(0, y_step):
                                    if not self._window.scroll_to_fixed(
                                            horiz='startsecond'):
                                        self._window.next_page()
                                    else:
                                        self._window.scroll_to_fixed(
                                                vert='top')
                                else:
                                    self._window.scroll_to_fixed(
                                            horiz='startfirst')
                        else:
                            if not self._window.scroll(x_step, 0, 'second'):
                                if not self._window.scroll(0, y_step):
                                    self._window.next_page()
                                else:
                                    self._window.scroll_to_fixed(
                                            horiz='startsecond')
                    else:
                        if not self._window.scroll(x_step, 0):
                            if not self._window.scroll(0, y_step):
                                self._window.next_page()
                            else:
                                self._window.scroll_to_fixed(
                                        horiz='startfirst')
                else:
                    if (self._window.zoom_mode == preferences.ZOOM_MODE_BEST or
                            not self._window.scroll(0, y_step)):
                        self._window.next_page()

        # ----------------------------------------------------------------
        # We kill the signals here for the Up, Down, Space and Enter keys,
        # or they will start fiddling with the thumbnail selector (bad).
        # ----------------------------------------------------------------

        _ignored_keys = (Gdk.KEY_Up, Gdk.KEY_Down,
                         Gdk.KEY_space, Gdk.KEY_KP_Enter, Gdk.KEY_KP_Up,
                         Gdk.KEY_KP_Down, Gdk.KEY_KP_Home, Gdk.KEY_KP_End,
                         Gdk.KEY_KP_Page_Up, Gdk.KEY_KP_Page_Down)

        if event.keyval in _ignored_keys or (
                event.keyval == Gdk.KEY_Return and 'GDK_MOD1_MASK' not in event.get_state().value_names):
            self._window.emit_stop_by_name('key_press_event')
            return True

    def scroll_wheel_event(self, widget, event, *args):
        """Handle scroll wheel events on the maon layout area. The scroll
        wheel flips pages in best fit mode and scrolls the scrollbars
        otherwise.
        """
        if 'GDK_BUTTON2_MASK' in event.get_state().value_names:
            return
        if event.direction == Gdk.ScrollDirection.UP:
            if self._window.zoom_mode == preferences.ZOOM_MODE_BEST:
                self._window.previous_page()
            elif self._window.zoom_mode == preferences.ZOOM_MODE_HEIGHT:
                if self._window.is_manga_mode:
                    self._scroll_with_flipping(70, 0)
                else:
                    self._scroll_with_flipping(-70, 0)
            else:
                self._scroll_with_flipping(0, -70)
        elif event.direction == Gdk.ScrollDirection.DOWN:
            if self._window.zoom_mode == preferences.ZOOM_MODE_BEST:
                self._window.next_page()
            elif self._window.zoom_mode == preferences.ZOOM_MODE_HEIGHT:
                if self._window.is_manga_mode:
                    self._scroll_with_flipping(-70, 0)
                else:
                    self._scroll_with_flipping(70, 0)
            else:
                self._scroll_with_flipping(0, 70)
        elif event.direction == Gdk.ScrollDirection.RIGHT:
            self._window.next_page()
        elif event.direction == Gdk.ScrollDirection.LEFT:
            self._window.previous_page()

    def mouse_press_event(self, widget, event):
        """Handle mouse click events on the main layout area."""
        if event.button == 1:
            self._pressed_pointer_pos_x = event.x_root
            self._pressed_pointer_pos_y = event.y_root
            self._last_pointer_pos_x = event.x_root
            self._last_pointer_pos_y = event.y_root
        elif event.button == 2:
            self._window.actiongroup.get_action('lens').set_active(True)
        elif event.button == 3:
            self._window.cursor_handler.set_cursor_type(cursor.NORMAL)
            self._window.popup.popup(parent_menu_shell=None,
                                     parent_menu_item=None,
                                     func=None,
                                     data=None,
                                     button=event.button,
                                     activate_time=event.time)
        elif event.button == 8:  # Mouse "back" button
            self._window.previous_page()
        elif event.button == 9:  # Mouse "forward" button
            self._window.next_page()

    def mouse_release_event(self, widget, event):
        """Handle mouse button release events on the main layout area."""
        self._window.cursor_handler.set_cursor_type(cursor.NORMAL)
        if event.button == 1 and event.x_root == self._pressed_pointer_pos_x and event.y_root == self._pressed_pointer_pos_y:
            self._window.next_page()
        elif event.button == 1 and self._window.zoom_mode == preferences.ZOOM_MODE_BEST:
            # Change page by touchscreen-useful flicking. See
            # https://sourceforge.net/tracker/?func=detail&aid=3016790&group_id=146377&atid=764987
            evx = event.x_root - self._pressed_pointer_pos_x
            evy = event.y_root - self._pressed_pointer_pos_y
            if max(abs(evx), abs(evy)) > 20:  # flicked, perhaps
                if self._window.is_manga_mode:
                    evx *= -1  # reversed horizontal perspective on next/prev.
                if (evx if abs(evx) > abs(evy) else evy) < 0:
                    self._window.next_page()
                else:
                    self._window.previous_page()
        if event.button == 2:
            self._window.actiongroup.get_action('lens').set_active(False)

    def mouse_move_event(self, widget, event):
        """Handle mouse pointer movement events."""
        event = _get_latest_event_of_same_type(event)
        if 'GDK_BUTTON1_MASK' in event.get_state().value_names:
            if self._window.zoom_mode == preferences.ZOOM_MODE_BEST:
                return  # nothig to drag, obviously. Allow flicking, also.

            self._window.cursor_handler.set_cursor_type(cursor.GRAB)
            self._window.scroll(self._last_pointer_pos_x - event.x_root,
                                self._last_pointer_pos_y - event.y_root)

            # Cursor wrapping stuff. See:
            # https://sourceforge.net/tracker/?func=detail&aid=2988441&group_id=146377&atid=764987
            disp = Gdk.Display.get_default()
            scr = disp.get_default_screen()
            new_x = _valwarp(event.x_root, scr.get_width())
            new_y = _valwarp(event.y_root, scr.get_height())
            if (new_x != event.x_root) or (new_y != event.y_root):
                disp.warp_pointer(scr, int(new_x), int(new_y))

            self._last_pointer_pos_x = new_x
            self._last_pointer_pos_y = new_y
            self._drag_timer = event.time
        elif self._window.actiongroup.get_action('lens').get_active():
            self._window.glass.set_lens_cursor(event.x, event.y)
        else:
            self._window.cursor_handler.refresh()

    def drag_n_drop_event(self, widget, context, x, y, selection, drag_id, eventtime):
        """Handle drag-n-drop events on the main layout area."""
        # The drag source is inside Comix itself, so we ignore.
        if context.get_source_window() is not None:
            return
        uris = selection.get_uris()
        if not uris:
            return
        uri = uris[0]  # Open only one file.
        if uri.startswith('file://localhost/'):  # Correctly formatted.
            uri = uri[16:]
        elif uri.startswith('file:///'):  # Nautilus etc.
            uri = uri[7:]
        elif uri.startswith('file:/'):  # Xffm etc.
            uri = uri[5:]
        path = url2pathname(uri)
        self._window.file_handler.open_file(path)

    def _scroll_with_flipping(self, x, y):
        """Handle scrolling with the scroll wheel or the arow keys, for which
        the pages might be flipped depending on the preferences.
        """
        if self._window.scroll(x, y) or not prefs['flip with wheel']:
            self._extra_scroll_events = 0
            return
        if y > 0 or (self._window.is_manga_mode and x < 0) or (
                    not self._window.is_manga_mode and x > 0):
            forwards_scroll = True
        else:
            forwards_scroll = False
        if forwards_scroll:
            self._extra_scroll_events = max(1, self._extra_scroll_events + 1)
            if self._extra_scroll_events >= 3:
                self._extra_scroll_events = 0
                self._window.next_page()
        else:
            self._extra_scroll_events = min(-1, self._extra_scroll_events - 1)
            if self._extra_scroll_events <= -3:
                self._extra_scroll_events = 0
                self._window.previous_page()


def _get_latest_event_of_same_type(event):
    """Return the latest event in the event queue that is of the same type
    as <event>, or <event> itself if no such events are in the queue. All
    events of that type will be removed from the event queue.
    """
    events = []
    while Gdk.events_pending():
        queued_event = Gdk.event_get()
        if queued_event is not None:
            if queued_event.type == event.type:
                event = queued_event
            else:
                events.append(queued_event)
    for queued_event in events:
        queued_event.put()
    return event
