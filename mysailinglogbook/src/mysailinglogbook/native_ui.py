"""Everything that talks to UIKit directly, in one place.

Toga builds the screens, but it has gaps on iOS that the app fills with the native views behind its widgets
(``widget._impl.native``): its Label never word-wraps, a Switch shows one line, a Selection's wheel never closes, a
text view has no coloured lines, there is no folder picker, no pulse, no tinting of an icon. Those workarounds used to
be spread over ``app.py`` and ``settings_screen.py``; they live here, so the screens read as screens, and so it is
clear what would have to be rewritten if Toga were ever replaced.

Nothing here knows about the app's own screens or settings: the functions take the Toga widget (or its native view) they
work on, and values the caller decides (a width, a loop, the lines of the log).
"""

from __future__ import annotations

import toga
from rubicon.objc import (
    SEL,
    Block,
    CGPoint,
    CGRect,
    CGSize,
    NSObject,
    NSRange,
    ObjCClass,
    ObjCInstance,
    ObjCProtocol,
    UIEdgeInsetsMake,
    objc_id,
    objc_method,
    objc_property,
)
from toga.style.pack import ROW, Pack

from nmea2log import app_constants

_UIApplication = ObjCClass("UIApplication")
_UIView = ObjCClass("UIView")
_UIFont = ObjCClass("UIFont")
_UIColor = ObjCClass("UIColor")
_NSString = ObjCClass("NSString")
_NSAttributedString = ObjCClass("NSAttributedString")
_NSMutableAttributedString = ObjCClass("NSMutableAttributedString")
_NSNotificationCenter = ObjCClass("NSNotificationCenter")
_UIToolbar = ObjCClass("UIToolbar")
_UIBarButtonItem = ObjCClass("UIBarButtonItem")
_UIDocumentPickerViewController = ObjCClass("UIDocumentPickerViewController")
_UTType = ObjCClass("UTType")
_UIDocumentPickerDelegate = ObjCProtocol("UIDocumentPickerDelegate")

# Standard UIKit values (not exposed as named constants anywhere in toga_iOS or rubicon-objc -- stable, documented
# Apple values, safe to hardcode).
_UI_VIEW_ANIMATION_OPTION_REPEAT = 1 << 3
_UI_VIEW_ANIMATION_OPTION_AUTOREVERSE = 1 << 4
_UI_IMAGE_RENDERING_MODE_ALWAYS_TEMPLATE = 2
_BAR_BUTTON_DONE = 0
_BAR_BUTTON_FLEXIBLE_SPACE = 5
_FONT_TRAIT_BOLD = 2

# A choice in a picker closes it this long after the last change (a wheel reports every row it settles on).
PICKER_CLOSE_DELAY_S = 1.2
# A Switch with no text of its own: the control (~52pt) plus the stack's spacing (10), and some room to spare:
# a label that just fits would still push the row wider than the screen (seen on an iPhone 17).
SWITCH_WIDTH = 61 + 24


# -- colour, buttons, the screen ---------------------------------------------------------------------------------


def hex_color(value: str):
    """A UIColor from a "#RRGGBB" string."""
    red, green, blue = (int(value[index:index + 2], 16) / 255 for index in (1, 3, 5))
    return _UIColor.colorWithRed(red, green=green, blue=blue, alpha=1.0)


def template_tint_icon(button) -> None:
    """toga_iOS's own Button.set_icon() sets the icon image with UIKit's default rendering mode, which keeps every
    pixel exactly as rasterized -- solid black, invisible against a dark toolbar background (found testing
    "Apparaat volgen"/"Donker"): the title text next to these buttons already adapts automatically (UIKit's dynamic
    label colour), but the icons didn't move at all.

    Re-applying the same image in "always template" mode makes UIKit ignore its own pixels and paint the shape
    using the button's tintColor -- set to UIColor.labelColor, the same dynamic black-in-light/white-in-dark colour
    the title text uses, so both switch together."""
    native = button._impl.native
    templated = native.imageForState(0).imageWithRenderingMode(_UI_IMAGE_RENDERING_MODE_ALWAYS_TEMPLATE)
    native.setImage(templated, forState=0)
    native.tintColor = _UIColor.labelColor()


def set_busy_pulse(button, busy: bool) -> None:
    """Same "something is happening" pulse as Android's setBusyAppearance() (alpha 1.0 <-> 0.35, 1500ms each way,
    repeating while busy). Toga has no generic opacity animation, so this goes through UIKit."""
    native = button._impl.native
    if busy:

        def _dim():
            native.alpha = 0.35

        _UIView.animateWithDuration(
            1.5,
            delay=0.0,
            options=_UI_VIEW_ANIMATION_OPTION_REPEAT | _UI_VIEW_ANIMATION_OPTION_AUTOREVERSE,
            animations=Block(_dim, None),
            completion=None,
        )
    else:
        native.layer.removeAllAnimations()
        native.alpha = 1.0


def round_corners(button, radius=10) -> None:
    native = button._impl.native
    native.layer.cornerRadius = radius
    native.clipsToBounds = True


def set_idle_timer_disabled(disabled: bool) -> None:
    """Keeps the screen from auto-locking while boat mode is on: boat mode is foreground-only (iOS has no equivalent
    of Android's foreground service), so the app being suspended when the screen locks would stop it just as surely as
    closing it. UIApplication.sharedApplication is a class-side accessor that rubicon-objc resolved as a property in
    one place and a method in another; tried as a property first, then called, and given up on silently rather than
    crashing boat mode over what is, worst case, a missed screen-lock prevention."""
    try:
        _UIApplication.sharedApplication.idleTimerDisabled = disabled
    except TypeError:
        try:
            _UIApplication.sharedApplication().idleTimerDisabled = disabled
        except Exception:
            pass


def window_width(app) -> float:
    """The width of the app's window in points."""
    return float(app.main_window._impl.native.bounds.size.width)


# -- the log: a text view with coloured lines, following the newest line -----------------------------------------


def attributed_log_text(text_view, lines):
    """The lines as attributed text: errors in red and warnings in yellow, both bold, like the Android log
    (app_constants decides which lines are which, and the colours). ``text_view`` is the native UITextView."""
    font = text_view.font
    # textColor is nil until something sets it: then the text is drawn in the system label colour.
    color = text_view.textColor or _UIColor.labelColor()
    bold = _UIFont.fontWithDescriptor(font.fontDescriptor.fontDescriptorWithSymbolicTraits(_FONT_TRAIT_BOLD), size=font.pointSize)
    error_color = hex_color(app_constants.LOG_ERROR_COLOR)
    warning_color = hex_color(app_constants.LOG_WARNING_COLOR)
    text = _NSMutableAttributedString.alloc().init()
    for line in lines:
        kind = app_constants.classify_line(line)
        if kind == "error":
            attributes = {"NSFont": bold, "NSColor": error_color}
        elif kind == "warning":
            attributes = {"NSFont": bold, "NSColor": warning_color}
        else:
            attributes = {"NSFont": font, "NSColor": color}
        text.appendAttributedString(_NSAttributedString.alloc().initWithString(line + "\n", attributes=attributes))
    return text


def lay_out_log_tail(text_view, tail_chars: int) -> None:
    """UIKit lays a UITextView's text out lazily, so right after the text changes its contentSize is still the old
    one -- which made both the was-at-bottom check and the scroll to the end come out wrong. Forces the layout of the
    end of the text now: only that, not the whole log, so it costs the same however long the log is."""
    length = text_view.textStorage.length()
    start = max(length - tail_chars, 0)
    text_view.layoutManager.ensureLayoutForCharacterRange(NSRange(start, length - start))
    text_view.layoutIfNeeded()


def scroll_to_bottom(text_view, tail_chars: int) -> None:
    lay_out_log_tail(text_view, tail_chars)
    end = text_view.contentSize.height - text_view.bounds.size.height + text_view.adjustedContentInset.bottom
    text_view.contentOffset = CGPoint(0, max(end, 0))


def is_scrolled_to_bottom(text_view) -> bool:
    # A few points of slack, same reasoning as Android's 4dp: scroll position/content height can be off by a rounding
    # point or two even while visually "at the bottom".
    slack = 4
    end = text_view.contentSize.height + text_view.adjustedContentInset.bottom
    return text_view.contentOffset.y + text_view.bounds.size.height >= end - slack


# -- labels and switches that fit the screen ---------------------------------------------------------------------


def _text_width(text: str, font) -> float:
    """How wide iOS draws ``text`` in ``font``, on one line."""
    return float(_NSString.stringWithString(text).sizeWithAttributes({"NSFont": font}).width)


def wrap_text_to_width(text: str, font, max_width: float) -> str:
    """``text`` with line breaks added between words so no line is wider than ``max_width``. Toga's iOS Label never
    word-wraps (it clips: a long label ran off the right edge of an iPhone 12), but it does show the lines of a text
    with newlines in it."""
    lines = []
    for paragraph in text.split("\n"):
        current = ""
        for word in paragraph.split(" "):
            candidate = word if not current else current + " " + word
            if current and _text_width(candidate, font) > max_width:
                lines.append(current)
                current = word
            else:
                current = candidate
        lines.append(current)
    return "\n".join(lines)


def wrapped_label(text: str, available_width: float, style=None):
    """A Label whose text is broken into lines that fit in ``available_width`` points."""
    label = toga.Label(text, style=style)
    label.text = wrap_text_to_width(text, label._impl.native.font, available_width)
    return label


def switch_row(text: str, value: bool, available_width: float, margin_top: int = 8):
    """A text on the left and a Switch on the right. toga.Switch shows only the first line of its own text
    (toga-core's setter keeps ``value.split("\\n")[0]``) and a long one pushes the control off the edge of a narrower
    iPhone, so the text is a separate Label, wrapped to fit, in a row with a Switch that has none; the label dims with
    the switch (see set_switch_enabled()). Returns (row, switch)."""
    row = toga.Box(style=Pack(direction=ROW, margin_top=margin_top, align_items="center"))
    label = wrapped_label(text, available_width - SWITCH_WIDTH, style=Pack(flex=1))
    switch = toga.Switch("", value=value)
    row.add(label)
    row.add(switch)
    switch._row_label = label
    return row, switch


def set_switch_enabled(switch, enabled: bool) -> None:
    switch.enabled = enabled
    switch._row_label._impl.native.enabled = enabled


# -- text entry -------------------------------------------------------------------------------------------------


def configure_technical_text_entry(field, disable_autofill: bool = False) -> None:
    """Every field of the settings is a technical value (URL, host, username, credential) or a short proper noun, not
    a sentence -- so iOS's default "capitalize the first letter of what looks like a new sentence" is actively wrong
    on all of them (it kept recapitalizing the first character of the WordPress URL while typing). UITextField has
    no cross-platform Toga API for this, so it is set on the native field. Autocorrection off for the same reason (a
    "corrected" URL/hostname/username is just wrong), spell-checking too.

    ``disable_autofill`` tells iOS not to guess what kind of field this is, so it never offers a Safari-saved-website
    suggestion there (matters for the WordPress URL field)."""
    native = field._impl.native
    native.autocapitalizationType = 0  # UITextAutocapitalizationTypeNone
    native.autocorrectionType = 1  # UITextAutocorrectionTypeNo
    native.spellCheckingType = 1  # UITextSpellCheckingTypeNo
    if disable_autofill:
        # "" (a real, empty NSString), not None/nil -- Apple's documented way to clear an inferred content type.
        native.textContentType = ""


def attach_secure_entry_toggle(field, switch) -> None:
    """No cross-platform Toga API to reveal a PasswordInput's text: ``switch`` toggles the native UITextField's
    secureTextEntry. Reassigning .text to itself right after works around a UITextField quirk: a secureTextEntry change
    alone doesn't reliably redraw an already-populated field's current text, only what's typed after it."""
    native = field._impl.native

    def _on_change(widget) -> None:
        native.secureTextEntry = not widget.value
        native.text = native.text

    switch.on_change = _on_change


class _PickerDoneTarget(NSObject):
    """The target of the "Gereed" button above a picker: ends the editing of the field that shows it."""

    field = objc_property(object, weak=True)

    @objc_method
    def done_(self, sender) -> None:
        self.field.resignFirstResponder()


def closing_picker(selection, loop):
    """Makes the picker of a toga.Selection (a wheel in place of the keyboard) go away by itself: a "Gereed" button
    above it, and closing a moment after a choice. Before, it stayed up until the user tapped elsewhere and covered
    the Annuleren / Opslaan buttons below the form. Returns the selection."""
    field = selection._impl.native
    target = _PickerDoneTarget.alloc().init()
    target.field = field
    selection._done_target = target  # the bar button does not retain its target
    done = _UIBarButtonItem.alloc().initWithBarButtonSystemItem(_BAR_BUTTON_DONE, target=target, action=SEL("done:"))
    space = _UIBarButtonItem.alloc().initWithBarButtonSystemItem(_BAR_BUTTON_FLEXIBLE_SPACE, target=None, action=None)
    toolbar = _UIToolbar.alloc().initWithFrame(CGRect(CGPoint(0, 0), CGSize(0, 44)))
    toolbar.setItems([space, done])
    field.inputAccessoryView = toolbar

    previous = selection.on_change
    pending = {"handle": None}

    def _on_change(widget, **kwargs) -> None:
        if previous is not None:
            previous(widget)
        if pending["handle"] is not None:
            pending["handle"].cancel()
        pending["handle"] = loop.call_later(PICKER_CLOSE_DELAY_S, field.resignFirstResponder)

    selection.on_change = _on_change
    return selection


class KeyboardAvoidance:
    """Found in practice: toga_iOS's ScrollContainer/TextInput have no keyboard-avoidance of their own -- with a form
    this long, the on-screen keyboard covering a field near the bottom reads as "everything disappeared" the moment
    you start typing, since nothing scrolls the focused field back into view.

    A generous fixed bottom inset while the keyboard is up, rather than reading its exact height out of the
    notification's userInfo (an NSValue-wrapped CGRect -- an extra struct extraction over rubicon-objc that isn't
    needed here), covers every keyboard height in practice; a too-generous inset only ever means a bit of harmless
    extra empty scroll room, never a hidden field. ``remove()`` takes the observers away again: a screen that is
    rebuilt on every visit would otherwise stack up one more per visit.

    Shifting the bottom margin of the box that holds both the scroll area and the button row was tried and reverted: it
    corrupted the scroll area's layout after opening a picker. The scroll view's own contentInset is narrower in scope
    and doesn't have this problem (it just doesn't reach the button row)."""

    INSET = 300

    def __init__(self, scroll):
        native = scroll._impl.native

        def _on_show(_notification: objc_id) -> None:
            native.contentInset = UIEdgeInsetsMake(0, 0, self.INSET, 0)
            native.scrollIndicatorInsets = UIEdgeInsetsMake(0, 0, self.INSET, 0)

        def _on_hide(_notification: objc_id) -> None:
            native.contentInset = UIEdgeInsetsMake(0, 0, 0, 0)
            native.scrollIndicatorInsets = UIEdgeInsetsMake(0, 0, 0, 0)

        center = _NSNotificationCenter.defaultCenter
        self._show_observer = center.addObserverForName(
            "UIKeyboardWillShowNotification", object=None, queue=None, usingBlock=Block(_on_show, None, objc_id)
        )
        self._hide_observer = center.addObserverForName(
            "UIKeyboardWillHideNotification", object=None, queue=None, usingBlock=Block(_on_hide, None, objc_id)
        )

    def remove(self) -> None:
        center = _NSNotificationCenter.defaultCenter
        center.removeObserver(self._show_observer)
        center.removeObserver(self._hide_observer)


# -- the folder picker (Toga has none on iOS) ---------------------------------------------------------------------


class FolderPickerDelegate(NSObject, protocols=[_UIDocumentPickerDelegate]):
    """UIDocumentPickerViewController's own delegate, defined via rubicon-objc's custom-Objective-C-class support:
    Toga has no folder picker on iOS (toga_iOS.dialogs' SelectFolderDialog/OpenFileDialog are not_implemented() stubs).

    ``app_ref`` is set right after alloc().init() -- an instance of this class is otherwise indistinguishable from
    any other bare NSObject to Python. It must be held by its owner too: UIDocumentPickerViewController's delegate
    property does not retain it."""

    @objc_method
    def documentPicker_didPickDocumentsAtURLs_(self, controller, urls) -> None:
        url = ObjCInstance(urls).objectAtIndex(0)
        self.app_ref.on_folder_picked(url)

    @objc_method
    def documentPickerWasCancelled_(self, controller) -> None:
        pass


def present_folder_picker(app) -> FolderPickerDelegate:
    """Shows the system folder picker; ``app.on_folder_picked(url)`` gets the chosen folder. Returns the delegate,
    which the caller keeps alive (see FolderPickerDelegate)."""
    folder_type = _UTType.typeWithIdentifier("public.folder")
    picker = _UIDocumentPickerViewController.alloc().initForOpeningContentTypes([folder_type])
    delegate = FolderPickerDelegate.alloc().init()
    delegate.app_ref = app
    picker.delegate = delegate
    toga.App.app.current_window._impl.native.rootViewController.presentViewController(
        picker, animated=True, completion=None
    )
    return delegate
