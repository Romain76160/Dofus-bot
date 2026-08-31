#!/usr/bin/env python3
"""Download a maps SQLite asset from a dofus-sqlite GitHub release."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from urllib.request import Request, urlopen

REPO = "ledouxm/dofus-sqlite"
USER_AGENT = "dofus-hybrid-observer-game-data/0.5"
ASSET_NAMES = ("maps.sqlite", "map_interactions.sqlite")


def get_json(url: str) -> dict:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
        },
    )
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def release_metadata(tag: str | None) -> dict:
    if tag:
        return get_json(f"https://api.github.com/repos/{REPO}/releases/tags/{tag}")
    return get_json(f"https://api.github.com/repos/{REPO}/releases/latest")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", help="Pin a release tag instead of latest")
    parser.add_argument("--output", type=Path, default=Path("../data/maps.sqlite"))
    parser.add_argument(
        "--sha256",
        dest="pinned_sha256",
        help="Optional expected SHA-256 (overrides release metadata)",
    )
    args = parser.parse_args()

    release = release_metadata(args.tag)
    assets = release.get("assets", [])
    asset = next(
        (item for name in ASSET_NAMES for item in assets if item.get("name") == name),
        None,
    )
    if asset is None:
        raise SystemExit(
            "No compatible SQLite asset found. Expected one of: "
            + ", ".join(ASSET_NAMES)
        )

    release_digest = str(asset.get("digest") or "")
    release_hash = (
        release_digest.removeprefix("sha256:")
        if release_digest.startswith("sha256:")
        else None
    )
    expected_hash = args.pinned_sha256 or release_hash

    args.output.parent.mkdir(parents=True, exist_ok=True)
    request = Request(
        asset["browser_download_url"],
        headers={"User-Agent": USER_AGENT},
    )

    with tempfile.NamedTemporaryFile(delete=False) as temp_handle:
        temp_path = Path(temp_handle.name)
        with urlopen(request, timeout=120) as response:
            shutil.copyfileobj(response, temp_handle)

    actual_hash = sha256(temp_path)
    if expected_hash and actual_hash.lower() != expected_hash.lower():
        temp_path.unlink(missing_ok=True)
        raise SystemExit(
            f"SHA-256 mismatch: expected {expected_hash}, got {actual_hash}"
        )

    temp_path.replace(args.output)
    metadata = {
        "source": REPO,
        "tag": release.get("tag_name"),
        "asset": asset.get("name"),
        "sha256": actual_hash,
        "verified_against": (
            "pinned"
            if args.pinned_sha256
            else "release-digest"
            if release_hash
            else "self-only"
        ),
        "published_at": release.get("published_at"),
    }
    args.output.with_suffix(".meta.json").write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )

    print(f"installed: {args.output}")
    print(f"release: {metadata['tag']}")
    print(f"asset: {metadata['asset']}")
    print(f"sha256: {actual_hash}")
    print(f"verification: {metadata['verified_against']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
