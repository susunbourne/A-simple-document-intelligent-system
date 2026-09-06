from scripts.enqueue_directory import build_source_version_key, iter_source_files


def test_source_version_key_is_stable_and_changes_with_content():
    key = build_source_version_key("Finance/Statement.PDF", "abc")

    assert key == build_source_version_key("finance\\statement.pdf", "abc")
    assert key != build_source_version_key("finance/statement.pdf", "def")
    assert len(key) <= 128


def test_directory_connector_filters_and_bounds_files(tmp_path):
    (tmp_path / "b.pdf").write_bytes(b"b")
    (tmp_path / "a.docx").write_bytes(b"a")
    (tmp_path / "ignored.txt").write_text("ignored", encoding="utf-8")

    files = list(iter_source_files(tmp_path, max_files=1))

    assert [path.name for path in files] == ["a.docx"]
