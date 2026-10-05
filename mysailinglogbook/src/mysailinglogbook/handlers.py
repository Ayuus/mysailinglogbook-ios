"""Small helpers for toga event handlers (no UIKit here, so they can be tested without an iPhone)."""

from __future__ import annotations


def chain_on_change(previous, after):
    """An ``on_change`` handler that first runs what ``widget.on_change`` held before, then ``after()``.

    What ``widget.on_change`` returns is not the handler that was assigned but toga's own wrapper around it, and that
    wrapper passes the widget to the handler itself. Calling it with the widget again (``previous(widget)``) gave the
    handler one argument too many: toga catches that and only prints "Error in handler", so the original handler
    silently never ran (the WordPress fields of Settings did not appear when the choice changed). ``previous`` is
    called with no arguments for that reason.
    """

    def _on_change(widget, **kwargs) -> None:
        if previous is not None:
            previous(**kwargs)
        after()

    return _on_change
