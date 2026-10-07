from mysailinglogbook.round_progress import BackgroundRoundProgress

LABELS = {"downloading": "Downloading", "decoding": "Decoding", "building_trips": "Assembling trips"}


def _progress(active=True):
    posted, lines, now = [], [], [0.0]
    progress = BackgroundRoundProgress(posted.append, lambda: active, lines.append, LABELS, clock=lambda: now[0])
    return progress, posted, lines, now


def test_the_first_report_is_shown_at_once():
    progress, posted, _, _ = _progress()

    progress.report(1, 80, "a.ebl")

    assert posted == ["Downloading 1/80"]


def test_reports_within_the_interval_are_skipped_and_one_after_it_is_shown():
    progress, posted, _, now = _progress()
    progress.report(1, 80, "a.ebl")

    now[0] = 5.0
    progress.report(5, 80, "b.ebl")
    now[0] = BackgroundRoundProgress.MIN_INTERVAL_S + 1
    progress.report(30, 80, "c.ebl")

    assert posted == ["Downloading 1/80", "Downloading 30/80"]


def test_a_new_phase_and_the_end_of_a_phase_are_shown_at_once():
    progress, posted, _, _ = _progress()

    progress.report(1, 80, "a.ebl")
    progress.onProgress("decoding", 1, 3)
    progress.onProgress("decoding", 3, 3)

    assert posted == ["Downloading 1/80", "Decoding 1/3", "Decoding 3/3"]


def test_nothing_is_shown_when_the_round_does_not_run_in_the_background():
    progress, posted, _, _ = _progress(active=False)

    progress.report(1, 80, "a.ebl")
    progress.onProgress("decoding", 1, 3)

    assert posted == []


def test_an_unknown_phase_or_no_total_is_ignored_and_log_lines_are_passed_on():
    progress, posted, lines, _ = _progress()

    progress.onProgress("something_else", 1, 3)
    progress.report(0, 0, "a.ebl")
    progress.onLogLine("a line")

    assert posted == [] and lines == ["a line"]
    assert progress.isCancelled() is False
