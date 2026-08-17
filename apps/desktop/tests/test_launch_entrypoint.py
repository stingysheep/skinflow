from pathlib import Path


def test_source_tree_entrypoint_exists_and_bootstraps_paths() -> None:
    entrypoint = Path(__file__).resolve().parents[1] / "launch.py"
    source = entrypoint.read_text(encoding="utf-8")
    assert "ROOT / \"api\"" in source
    assert "ROOT / \"desktop\"" in source
    assert "run_self_check" in source
