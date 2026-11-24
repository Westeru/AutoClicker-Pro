from src.settings_manager import SettingsManager


def test_settings_persistence_and_profiles(tmp_path):
    """Test saving/loading settings and named profiles."""
    settings_file = str(tmp_path / "settings.json")
    mgr = SettingsManager(path=settings_file)

    mgr.set("start_stop_hotkey", "f8")
    mgr.set("always_on_top", True)
    mgr.save_profile("Gaming", {"ms": 10, "secs": 0, "jitter_ms": 5})

    # Reload from disk
    mgr2 = SettingsManager(path=settings_file)
    assert mgr2.get("start_stop_hotkey") == "f8"
    assert mgr2.get("always_on_top") is True
    assert mgr2.list_profiles() == ["Gaming"]
    assert mgr2.get_profile("Gaming")["ms"] == 10

    mgr2.delete_profile("Gaming")
    assert mgr2.list_profiles() == []
