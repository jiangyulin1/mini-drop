from server.app.analyzer_runner import _resolve_under_root


def test_resolve_under_root_allows_artifact_root(tmp_path, monkeypatch):
    monkeypatch.setenv("MINI_DROP_ARTIFACT_ROOT", str(tmp_path))
    target = tmp_path / "task" / "perf.data"
    target.parent.mkdir()
    target.write_text("perf", encoding="utf-8")

    assert _resolve_under_root(str(target)) == target.resolve()


def test_resolve_under_root_rejects_outside_path(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.perf"
    outside.write_text("perf", encoding="utf-8")
    monkeypatch.setenv("MINI_DROP_ARTIFACT_ROOT", str(root))

    assert _resolve_under_root(str(outside)) is None
