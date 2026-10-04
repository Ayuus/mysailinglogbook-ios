"""Tests for settings_store.py -- see that module's own doc comment for why writes go through one
batched update() call instead of Android's own per-field property setters."""

import pytest

from mysailinglogbook.settings_store import DEFAULT_MIN_STOP_MINUTES, DEFAULT_SFTP_PORT, SettingsStore


def test_a_fresh_store_has_the_same_defaults_as_android(tmp_path):
    store = SettingsStore(tmp_path)

    assert store.w2k2_user == ""
    assert store.w2k2_password == ""
    assert store.auto_sync_on_launch is False
    assert store.auto_publish_after_build is True
    assert store.min_stop_minutes == DEFAULT_MIN_STOP_MINUTES
    assert store.sftp_port == DEFAULT_SFTP_PORT
    assert store.boot_round_interval_minutes == 60
    assert store.boot_final_on_harbour is True
    assert store.boot_final_on_left_boat is True
    assert store.boot_publish_every_round is False
    assert store.boot_stop_after_final is False
    assert store.boot_auto_start is False


def test_update_persists_across_a_new_instance_reading_the_same_directory(tmp_path):
    store = SettingsStore(tmp_path)
    store.update(w2k2_user="Test", w2k2_password="secret", boat_name="Little Endian")

    reloaded = SettingsStore(tmp_path)

    assert reloaded.w2k2_user == "Test"
    assert reloaded.w2k2_password == "secret"
    assert reloaded.boat_name == "Little Endian"


def test_update_only_touches_the_fields_it_is_given(tmp_path):
    store = SettingsStore(tmp_path)
    store.update(w2k2_user="Test")

    store.update(boat_name="Little Endian")

    assert store.w2k2_user == "Test"  # untouched by the second update()
    assert store.boat_name == "Little Endian"


def test_update_rejects_an_unknown_field(tmp_path):
    store = SettingsStore(tmp_path)

    with pytest.raises(KeyError):
        store.update(not_a_real_setting="x")


def test_a_corrupt_settings_file_falls_back_to_defaults_like_a_fresh_install(tmp_path):
    (tmp_path / "settings.json").write_text("{not valid json")

    store = SettingsStore(tmp_path)

    assert store.w2k2_user == ""
    assert store.min_stop_minutes == DEFAULT_MIN_STOP_MINUTES


def test_is_w2k2_config_complete_needs_both_fields_non_blank(tmp_path):
    store = SettingsStore(tmp_path)
    assert store.is_w2k2_config_complete is False

    store.update(w2k2_user="Test")
    assert store.is_w2k2_config_complete is False  # password still blank

    store.update(w2k2_password="secret")
    assert store.is_w2k2_config_complete is True


def test_is_w2k2_config_complete_treats_whitespace_only_as_blank(tmp_path):
    store = SettingsStore(tmp_path)
    store.update(w2k2_user="   ", w2k2_password="secret")

    assert store.is_w2k2_config_complete is False


def test_is_rest_upload_config_complete_needs_all_three_fields(tmp_path):
    store = SettingsStore(tmp_path)
    store.update(rest_upload_url="https://example.com/wp-json/nmea2log/v1/logbook")
    assert store.is_rest_upload_config_complete is False

    store.update(rest_upload_user="user")
    assert store.is_rest_upload_config_complete is False

    store.update(rest_upload_password="pw")
    assert store.is_rest_upload_config_complete is True


def test_is_sftp_config_complete_needs_all_four_fields(tmp_path):
    store = SettingsStore(tmp_path)
    store.update(sftp_host="example.com", sftp_user="user", sftp_password="pw")
    assert store.is_sftp_config_complete is False

    store.update(sftp_remote_path="/logbook.html")
    assert store.is_sftp_config_complete is True


def test_theme_mode_defaults_to_system_and_persists(tmp_path):
    store = SettingsStore(tmp_path)
    assert store.theme_mode == "system"  # the default of both apps, see nmea2log/app_settings.py

    store.update(theme_mode="dark")
    reloaded = SettingsStore(tmp_path)

    assert reloaded.theme_mode == "dark"
