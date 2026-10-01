from pathlib import Path


class RepairPolicy:
    """Defines which repository files Sentinel may modify."""

    _PROTECTED_DIRECTORIES = {
        ".git",
    }

    _PROTECTED_FILES = {
        ".env",
        ".env.local",
        ".env.production",
    }

    def __init__(self, repository_root: Path) -> None:
        self._repository_root = repository_root.resolve()

    def validate_path(self, file_path: str) -> Path:
        path = Path(file_path)

        if path.is_absolute() or file_path.startswith(("/", "\\")):
            raise ValueError("Repair path must be repository-relative.")

        resolved_path = (self._repository_root / path).resolve()

        try:
            resolved_path.relative_to(self._repository_root)
        except ValueError as exc:
            raise ValueError(
                "Repair path must remain inside the repository."
            ) from exc

        relative_path = resolved_path.relative_to(self._repository_root)

        if any(
            part in self._PROTECTED_DIRECTORIES
            for part in relative_path.parts
        ):
            raise ValueError("Repair cannot modify protected directories.")

        if relative_path.name in self._PROTECTED_FILES:
            raise ValueError("Repair cannot modify protected files.")

        return resolved_path