"""Security checks for downloaded MozJPEG release assets."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from urllib.parse import unquote, urlparse
import zipfile


# These limits protect the installer from untrusted or accidentally huge
# release responses before they reach the filesystem or archive extractor.
OFFICIAL_REPOSITORY = "mozilla/mozjpeg"
MAX_DOWNLOAD_BYTES = 250 * 1024 * 1024
MAX_ZIP_MEMBERS = 1000
MAX_ZIP_UNCOMPRESSED_BYTES = 500 * 1024 * 1024
_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


def normalize_sha256(digest: str | None) -> str:
    """Normalize GitHub's ``sha256:<hex>`` digest representation.

    A missing or malformed digest is rejected instead of allowing the caller
    to silently skip integrity verification.
    """
    if not digest:
        raise ValueError("The release asset has no SHA-256 digest.")
    value = digest.removeprefix("sha256:").strip()
    if not _SHA256_PATTERN.fullmatch(value):
        raise ValueError("The release asset has an invalid SHA-256 digest.")
    return value.lower()


def validate_release_asset_url(url: str, tag: str, asset_name: str) -> None:
    """Allow only the expected HTTPS URL for an official release asset.

    Filename matching alone is not sufficient: an unrelated executable with
    a convincing name must not be accepted by the installer.
    """
    parsed = urlparse(url)
    expected_path = (
        f"/{OFFICIAL_REPOSITORY}/releases/download/"
        f"{tag}/{asset_name}"
    )
    if (
        parsed.scheme != "https"
        or parsed.hostname != "github.com"
        or unquote(parsed.path) != expected_path
    ):
        raise ValueError("The release asset URL is not an official MozJPEG URL.")

    if Path(asset_name).name != asset_name or Path(asset_name).suffix.lower() not in {".exe", ".zip"}:
        raise ValueError("The release asset name is not a supported installer format.")


def verify_sha256(path: Path, expected_digest: str) -> None:
    """Verify a downloaded file before it is installed or executed."""
    expected = normalize_sha256(expected_digest)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != expected:
        raise ValueError("The downloaded MozJPEG asset failed SHA-256 verification.")


def validate_zip_members(zip_path: Path) -> None:
    """Reject traversal and resource-exhaustion patterns in a ZIP archive.

    This check runs before extraction. The separate extraction check in the
    application remains intentional because it validates the actual target
    directory used for extraction.
    """
    with zipfile.ZipFile(zip_path) as archive:
        members = archive.infolist()
        if len(members) > MAX_ZIP_MEMBERS:
            raise ValueError("The MozJPEG ZIP contains too many files.")

        total_size = sum(member.file_size for member in members)
        if total_size > MAX_ZIP_UNCOMPRESSED_BYTES:
            raise ValueError("The MozJPEG ZIP expands beyond the allowed size.")

        destination = zip_path.parent.resolve()
        for member in members:
            target = (destination / member.filename).resolve()
            if target != destination and destination not in target.parents:
                raise ValueError("The MozJPEG ZIP contains an invalid path.")
