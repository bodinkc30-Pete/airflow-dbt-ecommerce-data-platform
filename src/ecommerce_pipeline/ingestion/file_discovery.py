from dataclasses import dataclass
from pathlib import Path

from ecommerce_pipeline.ingestion.source_registry import (
    SourceConfig,
    get_source_config,
)


@dataclass(frozen=True)
class DiscoveredFile:
    source_name: str
    file_path: Path
    file_name: str


def _validate_input_directory(input_directory: str | Path) -> Path:
    directory = Path(input_directory).resolve()

    if not directory.exists():
        raise FileNotFoundError(
            f"Input directory does not exist: {directory}"
        )

    if not directory.is_dir():
        raise ValueError(
            f"Input path is not a directory: {directory}"
        )

    return directory


def _discover_matching_files(
    directory: Path,
    source_config: SourceConfig,
) -> list[Path]:
    matches = [
        path.resolve()
        for path in directory.glob(source_config.file_pattern)
        if path.is_file()
    ]

    return sorted(
        matches,
        key=lambda path: (
            path.name.casefold(),
            str(path).casefold(),
        ),
    )


def discover_source_files(
    source_name: str,
    input_directory: str | Path,
) -> tuple[DiscoveredFile, ...]:
    source_config = get_source_config(source_name)
    directory = _validate_input_directory(input_directory)

    matching_files = _discover_matching_files(
        directory=directory,
        source_config=source_config,
    )

    if (
        len(matching_files) > 1
        and not source_config.supports_multiple_files
    ):
        raise ValueError(
            f"Source '{source_name}' matched multiple files "
            f"but supports_multiple_files=False: "
            f"{len(matching_files)} files found"
        )

    return tuple(
        DiscoveredFile(
            source_name=source_name,
            file_path=file_path,
            file_name=file_path.name,
        )
        for file_path in matching_files
    )


def discover_all_sources(
    input_directory: str | Path,
) -> dict[str, tuple[DiscoveredFile, ...]]:
    directory = _validate_input_directory(input_directory)

    results: dict[str, tuple[DiscoveredFile, ...]] = {}

    from ecommerce_pipeline.ingestion.source_registry import (
        list_source_names,
    )

    for source_name in list_source_names():
        results[source_name] = discover_source_files(
            source_name=source_name,
            input_directory=directory,
        )

    return results