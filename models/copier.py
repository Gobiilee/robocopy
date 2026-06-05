import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Callable


# 256 KB chunks — fine-grained enough for smooth progress on large files
# without the overhead of tiny reads on fast local drives.
CHUNK_SIZE = 256 * 1024


@dataclass
class CopyResult:
    """Result of a single file copy."""
    success: bool
    filepath: Path
    size_bytes: int = 0
    duration_seconds: float = 0.0
    error_message: str | None = None
    cancelled: bool = False


class RoboCopier:
    """Handles file scanning and copying."""

    def __init__(self, workers: int = 8) -> None:
        self.workers = workers
        self._is_cancelled = False

    def cancel(self) -> None:
        self._is_cancelled = True

    def copy_file(
        self,
        src: Path,
        dst: Path,
        progress_cb: Callable[[int], None] | None = None,
    ) -> CopyResult:
        """
        Copy *src* → *dst*, calling ``progress_cb(bytes_just_written)``
        after each chunk so callers can update a progress bar even for
        a single very large file.

        Falls back to ``shutil.copy2`` metadata copy at the end so
        timestamps / permissions are preserved.
        """
        if self._is_cancelled:
            return CopyResult(success=False, filepath=src, cancelled=True)

        try:
            size = src.stat().st_size
        except OSError as exc:
            return CopyResult(success=False, filepath=src, error_message=str(exc))

        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            t0 = time.perf_counter()

            with src.open("rb") as fsrc, dst.open("wb") as fdst:
                while True:
                    if self._is_cancelled:
                        # Clean up the incomplete destination file.
                        try:
                            dst.unlink(missing_ok=True)
                        except OSError:
                            pass
                        return CopyResult(
                            success=False, filepath=src, cancelled=True
                        )

                    chunk = fsrc.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    fdst.write(chunk)
                    if progress_cb is not None:
                        progress_cb(len(chunk))

            # Copy metadata (timestamps, permissions) — matches shutil.copy2
            import shutil
            shutil.copystat(src, dst)

            elapsed = time.perf_counter() - t0
            return CopyResult(
                success=True,
                filepath=src,
                size_bytes=size,
                duration_seconds=elapsed,
            )
        except Exception as exc:
            return CopyResult(
                success=False, filepath=src, size_bytes=size,
                error_message=str(exc),
            )

    def get_folder_stats(self, src_path: Path) -> tuple[list[Path], int]:
        """Return list of files and total size in bytes."""
        files = []
        total_bytes = 0
        for f in src_path.rglob("*"):
            if f.is_file():
                files.append(f)
                total_bytes += f.stat().st_size
        return files, total_bytes