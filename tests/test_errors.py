from alignment_tool.core.errors import (
    AlignmentToolError,
    MediaLoadError, MidiParseError, CameraXmlParseError, VideoOpenError,
    PersistenceError, UnsupportedSchemaVersionError, CorruptAlignmentFileError,
    InvariantError, AnchorsExistError, InvalidAnchorError,
    UnknownMidiFileError, InvalidFpsError, MarkersNotSetError,
)


def test_all_errors_inherit_from_base():
    for cls in (
        MediaLoadError, MidiParseError, CameraXmlParseError, VideoOpenError,
        PersistenceError, UnsupportedSchemaVersionError, CorruptAlignmentFileError,
        InvariantError, AnchorsExistError, InvalidAnchorError,
        UnknownMidiFileError, InvalidFpsError, MarkersNotSetError,
    ):
        assert issubclass(cls, AlignmentToolError), cls.__name__


def test_media_load_error_carries_path_and_reason():
    exc = MidiParseError(path="/x/y.mid", reason="corrupt header")
    assert exc.path == "/x/y.mid"
    assert exc.reason == "corrupt header"
    assert "/x/y.mid" in str(exc)
    assert "corrupt header" in str(exc)


def test_anchors_exist_error_carries_count():
    exc = AnchorsExistError(count=3)
    assert exc.count == 3
    assert "3" in str(exc)


def test_unsupported_schema_version_error_carries_found_and_supported():
    exc = UnsupportedSchemaVersionError(found=99, supported=1)
    assert exc.found == 99
    assert exc.supported == 1
