"""
My Sailing Logbook (iOS) -- mirrors the Android app's own MainActivity as closely as the
platform allows (asked for explicitly, see this repo's own README: "Design principle: match
the Android app exactly"). Toolbar order, button purpose, and overall layout (toolbar, log/
status area, logbook view) are the same; see the Android app's MainActivity.kt for the
reference behavior each of these will eventually need to match.
"""

import toga
from toga.style.pack import COLUMN, ROW, Pack


class MySailingLogbook(toga.App):
    def startup(self):
        # Same order as Android's own toolbar (MainActivity.kt): download, rebuild, publish,
        # view logbook, boat mode, settings. Android's own toolbar buttons are icon-only, no
        # visible text label (see MainActivity.kt's iconButton() helper -- tooltip text only,
        # shown on long-press/hover) -- matched here the same way. Icons are the same shapes as
        # Android's own vector drawables (ic_download_24, ic_refresh_24, ic_upload_24,
        # ic_article_24, ic_sailboat_24, ic_settings_24), rasterized from matching SVGs -- see
        # resources/icons-svg/. Not wired up to anything yet -- this is the layout skeleton;
        # each button's real behavior (see the Android app's own doc comments for each one)
        # comes next.
        self.download_button = toga.Button(
            icon=toga.Icon("resources/download"), on_press=self.on_download, style=Pack(flex=1)
        )
        self.rebuild_button = toga.Button(
            icon=toga.Icon("resources/refresh"), on_press=self.on_rebuild, style=Pack(flex=1)
        )
        self.publish_button = toga.Button(
            icon=toga.Icon("resources/upload"), on_press=self.on_publish, style=Pack(flex=1)
        )
        self.view_button = toga.Button(
            icon=toga.Icon("resources/article"), on_press=self.on_view, style=Pack(flex=1)
        )
        self.boat_mode_button = toga.Button(
            icon=toga.Icon("resources/sailboat"), on_press=self.on_boat_mode, style=Pack(flex=1)
        )
        self.settings_button = toga.Button(
            icon=toga.Icon("resources/settings"), on_press=self.on_settings, style=Pack(flex=1)
        )

        toolbar = toga.Box(
            children=[
                self.download_button,
                self.rebuild_button,
                self.publish_button,
                self.view_button,
                self.boat_mode_button,
                self.settings_button,
            ],
            style=Pack(direction=ROW),
        )

        # Stands in for Android's own log view (a plain scrolling text area) until there's
        # something real to show there -- same "log is the default content, the built logbook
        # replaces it once there is one" idea as MainActivity's own setLogExpanded().
        self.log_view = toga.MultilineTextInput(readonly=True, style=Pack(flex=1))

        main_box = toga.Box(children=[toolbar, self.log_view], style=Pack(direction=COLUMN))

        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = main_box
        self.main_window.show()

    def log(self, line: str) -> None:
        self.log_view.value += line + "\n"

    # Placeholders -- see MainActivity.kt's own runSync()/buildFromLocalFilesAndMaybePublish()/
    # runPublish()/viewLocalLogbook()/toggleBootMode()/openSettings() for what each of these
    # needs to actually do.
    def on_download(self, widget):
        self.log("[info] Download tapped (not implemented yet)")

    def on_rebuild(self, widget):
        self.log("[info] Rebuild tapped (not implemented yet)")

    def on_publish(self, widget):
        self.log("[info] Publish tapped (not implemented yet)")

    def on_view(self, widget):
        self.log("[info] View tapped (not implemented yet)")

    def on_boat_mode(self, widget):
        self.log("[info] Boat mode tapped (not implemented yet)")

    def on_settings(self, widget):
        self.log("[info] Settings tapped (not implemented yet)")


def main():
    return MySailingLogbook()
