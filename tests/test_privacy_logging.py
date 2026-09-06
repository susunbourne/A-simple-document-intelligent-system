from src.core.logging import privacy_safe_file_id


def test_privacy_safe_file_id_is_stable_and_does_not_include_filename():
    filename = "Student Name - Bank Statement.pdf"
    file_id = privacy_safe_file_id(filename)

    assert file_id == privacy_safe_file_id(filename)
    assert len(file_id) == 16
    assert "Student" not in file_id
