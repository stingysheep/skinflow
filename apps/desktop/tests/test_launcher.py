from skinflow_desktop.launcher import (
    DEFAULT_PORT,
    DEFAULT_WINDOW_SIZE,
    LOCAL_HOST,
    desktop_icon_path,
    find_available_port,
    generate_startup_token,
    load_window_size,
    save_window_size,
)


def test_startup_token_is_fresh_and_url_safe() -> None:
    first = generate_startup_token()
    second = generate_startup_token()

    assert first != second
    assert len(first) >= 32
    assert all(character.isalnum() or character in "-_" for character in first)


def test_find_available_port_prefers_default_when_free() -> None:
    port = find_available_port(preferred=0)

    assert port > 0
    assert LOCAL_HOST == "127.0.0.1"
    assert DEFAULT_PORT == 58150


def test_icon_is_project_local_and_distinct_from_legacy_path() -> None:
    icon = desktop_icon_path()
    assert icon.name == "skinflow.ico"
    assert icon.exists()
    assert "D:" not in str(icon)


def test_non_windows_single_instance_is_noop(monkeypatch) -> None:
    from skinflow_desktop import launcher

    monkeypatch.setattr(launcher.os, "name", "posix")
    assert launcher.acquire_single_instance("test") is True


def test_desktop_window_size_round_trips_between_sessions(tmp_path) -> None:
    state = tmp_path / "desktop_window.json"
    assert load_window_size(state) == DEFAULT_WINDOW_SIZE

    save_window_size(state, 1260, 780)

    assert load_window_size(state) == (1260, 780)


def test_desktop_window_size_rejects_invalid_or_too_small_values(tmp_path) -> None:
    state = tmp_path / "desktop_window.json"
    state.write_text('{"width": 500, "height": 400}', encoding="utf-8")
    assert load_window_size(state) == (1100, 720)
    state.write_text("invalid", encoding="utf-8")
    assert load_window_size(state) == DEFAULT_WINDOW_SIZE
