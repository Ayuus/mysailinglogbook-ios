from mysailinglogbook.handlers import chain_on_change


def _toga_wrapper(interface, handler, swallowed):
    """What toga's wrapped_handler() does: passes the widget to the handler, and catches (only prints) any error."""

    def _handler(*args, **kwargs):
        try:
            handler(interface, *args, **kwargs)
        except Exception as exc:  # toga prints "Error in handler" and carries on
            swallowed.append(exc)

    return _handler


def test_the_original_handler_runs_with_the_widget_exactly_once_and_then_the_follow_up():
    calls, swallowed = [], []
    widget = object()

    def original(w):
        calls.append(("original", w))

    previous = _toga_wrapper(widget, original, swallowed)
    chained = chain_on_change(previous, lambda: calls.append(("after",)))

    chained(widget)

    assert calls == [("original", widget), ("after",)]
    assert swallowed == []  # calling previous(widget) would have landed here: one argument too many


def test_without_a_previous_handler_only_the_follow_up_runs():
    calls = []

    chain_on_change(None, lambda: calls.append("after"))(object())

    assert calls == ["after"]
