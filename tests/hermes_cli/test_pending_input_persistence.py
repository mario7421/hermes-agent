"""Regression tests: undispatched queued prompts survive a CLI restart.

process_loop dispatches each input inline, so a blocking call (voice teardown) can
stall the queue with no log; a restart must not silently destroy what was queued.
"""

import os
import queue
import time
from unittest.mock import patch

import pytest

from cli import HermesCLI
from hermes_cli import cli_tui_runtime_mixin as ctr


@pytest.fixture
def cli_obj():
    obj = HermesCLI.__new__(HermesCLI)
    obj._pending_input = queue.Queue()
    obj.session_id = "test_session_123"
    return obj


def _patched_hermes_home(tmp_path):
    return patch.object(ctr, "get_hermes_home", return_value=tmp_path)


def test_persist_empty_queue_writes_nothing(cli_obj, tmp_path):
    with _patched_hermes_home(tmp_path):
        cli_obj._tui_persist_pending_input_to_disk()
    assert not (tmp_path / "pending_input").exists()


def test_persist_and_restore_round_trip(cli_obj, tmp_path):
    items = ["Why payment is a weakness?", "/queue list", "/queue clear"]
    for item in items:
        cli_obj._pending_input.put(item)

    with _patched_hermes_home(tmp_path):
        cli_obj._tui_persist_pending_input_to_disk()

        cli_obj2 = HermesCLI.__new__(HermesCLI)
        cli_obj2._pending_input = queue.Queue()
        cli_obj2.session_id = "test_session_123"
        cli_obj2._tui_restore_pending_input_from_disk()

    assert list(cli_obj2._pending_input.queue) == items
    # Files are consumed on restore — a later restart must not re-deliver them.
    assert not list((tmp_path / "pending_input").glob("*.json"))


def test_persist_serializes_tuple_payloads(cli_obj, tmp_path):
    import json
    cli_obj._pending_input.put(("some text", ["img1.png"]))
    cli_obj._pending_input.put("plain message")
    with _patched_hermes_home(tmp_path):
        cli_obj._tui_persist_pending_input_to_disk()
    data = json.loads(
        next((tmp_path / "pending_input").glob("*.json")).read_text(encoding="utf-8"))
    assert data == ["some text", "plain message"]
