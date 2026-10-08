"""The help: one page shared with the Android app (nmea2log's assets/help/help.html, English, Dutch, French and German), in a web view.

The page is the copy last downloaded from GitHub, or the one that came with the app (nmea2log/help_page.py); its screenshots
are this app's own (resources/help/img/), embedded in the page because a web view cannot read files next to a page it was
handed as a string. The page has no JavaScript. Links to the web open in Safari; links inside the page (#connect) stay.
"""

from __future__ import annotations

from pathlib import Path

import toga
from toga.style.pack import COLUMN, Pack

from nmea2log import help_page

from . import native_ui
from .translations import language, t

_IMAGES_DIR = Path(__file__).parent / "resources" / "help" / "img"


def cache_dir(app: toga.App) -> Path:
    """Where the copy of the help page that was downloaded from GitHub is kept (iOS may clear caches when it needs the space;
    the page that came with the app is then used again)."""
    return Path(app.paths.cache) / "help"


class HelpScreen:
    """``content`` replaces the main window's content; Close puts ``back_content`` there again."""

    def __init__(self, app: toga.App, back_content: toga.Widget) -> None:
        self.app = app
        self._back_content = back_content
        html = help_page.inline_images(help_page.html_for_app(cache_dir(app), "ios", language()), _IMAGES_DIR)
        web_view = toga.WebView(style=Pack(flex=1), on_navigation_starting=self._on_navigation)
        web_view.set_content(f"file://{_IMAGES_DIR.parent}/", html)
        close_button = toga.Button(t("button_close"), on_press=self._on_close, style=Pack(margin=8))
        divider = toga.Box(style=Pack(height=1, background_color="#C6C6C8"))
        self.content = toga.Box(children=[web_view, divider, close_button], style=Pack(direction=COLUMN))

    def _on_navigation(self, widget, url: str, **kwargs) -> bool:
        if url.startswith(("http://", "https://")):
            native_ui.open_url(url)
            return False
        return True

    def _on_close(self, widget) -> None:
        self.app.main_window.content = self._back_content
