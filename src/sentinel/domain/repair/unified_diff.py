from sentinel.domain.repair.patch import PatchApplier, PatchApplicationError


class UnifiedDiffPatchApplier(PatchApplier):
    """Applies a restricted unified diff to text."""

    def apply(self, original: str, patch: str) -> str:
        if not patch.strip():
            raise PatchApplicationError("Patch cannot be empty.")

        lines = original.splitlines(keepends=True)
        patch_lines = patch.splitlines(keepends=True)

        output: list[str] = []
        source_index = 0
        patch_index = 0

        while patch_index < len(patch_lines):
            line = patch_lines[patch_index]

            if line.startswith("--- ") or line.startswith("+++ "):
                patch_index += 1
                continue

            if not line.startswith("@@"):
                raise PatchApplicationError(
                    f"Invalid patch header: {line.strip()}"
                )

            try:
                header = line.split("@@")[1].strip()
                source_range = header.split()[0]
                source_start = int(
                    source_range.split(",")[0].removeprefix("-")
                )
            except (IndexError, ValueError) as exc:
                raise PatchApplicationError(
                    f"Invalid unified diff hunk header: {line.strip()}"
                ) from exc

            target_index = source_start - 1

            if target_index < source_index or target_index > len(lines):
                raise PatchApplicationError(
                    "Patch hunk is outside the target file."
                )

            output.extend(lines[source_index:target_index])
            source_index = target_index

            patch_index += 1

            while patch_index < len(patch_lines):
                hunk_line = patch_lines[patch_index]

                if hunk_line.startswith("@@"):
                    break

                if hunk_line.startswith("\\ No newline"):
                    patch_index += 1
                    continue

                if not hunk_line:
                    patch_index += 1
                    continue

                marker = hunk_line[0]
                content = hunk_line[1:]

                if marker == " ":
                    if (
                        source_index >= len(lines)
                        or lines[source_index] != content
                    ):
                        raise PatchApplicationError(
                            "Patch context does not match target file."
                        )

                    output.append(lines[source_index])
                    source_index += 1

                elif marker == "-":
                    if (
                        source_index >= len(lines)
                        or lines[source_index] != content
                    ):
                        raise PatchApplicationError(
                            "Patch removal does not match target file."
                        )

                    source_index += 1

                elif marker == "+":
                    output.append(content)

                else:
                    raise PatchApplicationError(
                        f"Invalid patch line: {hunk_line.strip()}"
                    )

                patch_index += 1

        output.extend(lines[source_index:])

        return "".join(output)