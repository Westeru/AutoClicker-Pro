import json
import os
from typing import Any, Dict, List


def get_settings_path() -> str:
    """Return path to settings.json in AppData (or project root fallback)."""
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base:
        app_dir = os.path.join(base, "AutoClickerPro")
        os.makedirs(app_dir, exist_ok=True)
        return os.path.join(app_dir, "settings.json")
    return os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "settings.json")
    )


class SettingsManager:
    """Lightweight JSON-backed settings and profile manager."""

    DEFAULTS: Dict[str, Any] = {
        "start_stop_hotkey": "f6",
        "record_hotkey": "f7",
        "always_on_top": False,
        "gemini_key": "",
        "profiles": {},
    }

    def __init__(self, path: str = None):
        self.path = path or get_settings_path()
        self.data: Dict[str, Any] = dict(self.DEFAULTS)
        self.load()

    def load(self) -> Dict[str, Any]:
        loaded: Dict[str, Any] = {}
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
            except Exception:
                loaded = {}
        else:
            # One-time migration from legacy project-root settings.json if present
            legacy = os.path.normpath(
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "settings.json")
            )
            if legacy != self.path and os.path.exists(legacy):
                try:
                    with open(legacy, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                except Exception:
                    loaded = {}

        self.data = dict(self.DEFAULTS)
        if isinstance(loaded, dict):
            self.data.update(loaded)
        if not isinstance(self.data.get("profiles"), dict):
            self.data["profiles"] = {}
        return self.data

    def save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            print(f"SettingsManager save error: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any, auto_save: bool = True) -> None:
        self.data[key] = value
        if auto_save:
            self.save()

    # --- Profiles ---
    def list_profiles(self) -> List[str]:
        return sorted(self.data.get("profiles", {}).keys())

    def save_profile(self, name: str, profile_data: Dict[str, Any]) -> None:
        name = name.strip()
        if not name:
            return
        self.data.setdefault("profiles", {})[name] = profile_data
        self.save()

    def get_profile(self, name: str) -> Dict[str, Any]:
        return self.data.get("profiles", {}).get(name, {})

    def delete_profile(self, name: str) -> None:
        profiles = self.data.get("profiles", {})
        if name in profiles:
            del profiles[name]
            self.save()
