"""Local runtime preservation commands, independent of HTTP and storage mechanics."""

from pathlib import Path
from typing import Protocol


class RuntimeStatePort(Protocol):
    def backup(self, output: Path, source_root: Path | None) -> dict[str, object]: ...

    def inspect(self, archive: Path) -> dict[str, object]: ...

    def verify(self, archive: Path) -> dict[str, object]: ...

    def restore(self, archive: Path, target_root: Path) -> dict[str, object]: ...


class RuntimeStateService:
    def __init__(self, storage: RuntimeStatePort) -> None:
        self.storage = storage

    def backup(self, output: Path, source_root: Path | None = None) -> dict[str, object]:
        if output.exists() or output.is_symlink():
            raise FileExistsError("Backup output already exists; choose a new filename")
        return self.storage.backup(output, source_root)

    def inspect(self, archive: Path) -> dict[str, object]:
        return self.storage.inspect(archive)

    def verify(self, archive: Path) -> dict[str, object]:
        return self.storage.verify(archive)

    def restore(self, archive: Path, target_root: Path) -> dict[str, object]:
        if target_root.exists() or target_root.is_symlink():
            raise FileExistsError("Restore target already exists; choose a new directory")
        return self.storage.restore(archive, target_root)
