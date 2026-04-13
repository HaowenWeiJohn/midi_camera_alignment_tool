"""Exception hierarchy for the alignment tool. All exceptions inherit from AlignmentToolError."""
from __future__ import annotations


class AlignmentToolError(Exception):
    """Base for every domain exception raised by the tool."""


class MediaLoadError(AlignmentToolError):
    def __init__(self, path: str, reason: str):
        self.path = path
        self.reason = reason
        super().__init__(f"{path}: {reason}")


class MidiParseError(MediaLoadError):
    pass


class CameraXmlParseError(MediaLoadError):
    pass


class VideoOpenError(MediaLoadError):
    pass


class PersistenceError(AlignmentToolError):
    pass


class UnsupportedSchemaVersionError(PersistenceError):
    def __init__(self, found: int, supported: int):
        self.found = found
        self.supported = supported
        super().__init__(
            f"Alignment JSON schema_version={found} not supported (this build supports {supported})."
        )


class CorruptAlignmentFileError(PersistenceError):
    def __init__(self, path: str, reason: str):
        self.path = path
        self.reason = reason
        super().__init__(f"{path}: {reason}")


class InvariantError(AlignmentToolError):
    """Raised by services when a requested mutation would break an invariant."""


class AnchorsExistError(InvariantError):
    def __init__(self, count: int):
        self.count = count
        super().__init__(
            f"Cannot change global shift while {count} anchor(s) exist; "
            "pass clear_anchors_if_needed=True to proceed."
        )


class InvalidAnchorError(InvariantError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


class UnknownMidiFileError(InvariantError):
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Anchor references unknown MIDI file: {name!r}")


class InvalidFpsError(InvariantError):
    def __init__(self, fps: float):
        self.fps = fps
        super().__init__(f"capture_fps must be > 0, got {fps}")


class MarkersNotSetError(InvariantError):
    def __init__(self):
        super().__init__("Both MIDI and camera markers must be set first.")
