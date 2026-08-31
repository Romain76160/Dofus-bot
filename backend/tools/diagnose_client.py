from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


TARGET_FILES = (
    "GameAssembly.dll",
    "global-metadata.dat",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_first(root: Path, name: str) -> Path | None:
    for candidate in root.rglob(name):
        if candidate.is_file():
            return candidate
    return None


def describe_file(path: Path | None) -> dict | None:
    if path is None:
        return None

    return {
        "path": str(path),
        "size": path.stat().st_size,
        "sha256": sha256(path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect a local Dofus client installation without modifying it."
    )
    parser.add_argument(
        "dofus_path",
        type=Path,
        help="Root folder of the Dofus client installation.",
    )
    args = parser.parse_args()

    root = args.dofus_path.expanduser().resolve()
    if not root.exists():
        raise SystemExit(f"Path does not exist: {root}")

    detected = {
        name: describe_file(find_first(root, name))
        for name in TARGET_FILES
    }

    map_bundles = [
        path
        for path in root.rglob("mapdata_assets_world_*.bundle")
        if path.is_file()
    ]

    streaming_content = next(
        (
            path
            for path in root.rglob("StreamingAssets")
            if path.is_dir() and (path / "Content").exists()
        ),
        None,
    )

    report = {
        "root": str(root),
        "game_assembly": detected["GameAssembly.dll"],
        "global_metadata": detected["global-metadata.dat"],
        "streaming_assets_content": (
            str(streaming_content / "Content")
            if streaming_content
            else None
        ),
        "map_bundle_count": len(map_bundles),
        "map_bundle_examples": [str(path) for path in map_bundles[:5]],
    }

    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
