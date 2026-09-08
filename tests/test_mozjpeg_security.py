import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path

import mozjpeg_security as security


class MozJpegSecurityTests(unittest.TestCase):
    """Exercise the trust and archive boundaries used by MozJPEG installation."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_normalize_sha256_accepts_plain_and_prefixed_values(self):
        digest = "A" * 64
        self.assertEqual(security.normalize_sha256(digest), digest.lower())
        self.assertEqual(security.normalize_sha256(f"sha256:{digest}"), digest.lower())

    def test_normalize_sha256_rejects_missing_or_malformed_values(self):
        for value in (None, "", "sha256:short", "g" * 64):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    security.normalize_sha256(value)

    def test_verify_sha256_accepts_matching_file(self):
        asset = self.root / "asset.exe"
        asset.write_bytes(b"trusted test asset")
        digest = hashlib.sha256(asset.read_bytes()).hexdigest()

        security.verify_sha256(asset, digest)
        security.verify_sha256(asset, f"sha256:{digest}")

    def test_verify_sha256_rejects_modified_file(self):
        asset = self.root / "asset.exe"
        asset.write_bytes(b"modified asset")

        with self.assertRaises(ValueError):
            security.verify_sha256(asset, "0" * 64)

    def test_validate_release_asset_url_requires_official_download_path(self):
        # The installer must accept the official release path but reject lookalikes.
        security.validate_release_asset_url(
            "https://github.com/mozilla/mozjpeg/releases/download/v1.0/mozjpeg-win64.exe",
            "v1.0",
            "mozjpeg-win64.exe",
        )

        invalid_urls = (
            "http://github.com/mozilla/mozjpeg/releases/download/v1.0/mozjpeg-win64.exe",
            "https://example.com/mozilla/mozjpeg/releases/download/v1.0/mozjpeg-win64.exe",
            "https://github.com/other/repo/releases/download/v1.0/mozjpeg-win64.exe",
            "https://github.com/mozilla/mozjpeg/archive/v1.0.zip",
        )
        for url in invalid_urls:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    security.validate_release_asset_url(url, "v1.0", "mozjpeg-win64.exe")

    def test_validate_release_asset_url_rejects_path_like_asset_names(self):
        with self.assertRaises(ValueError):
            security.validate_release_asset_url(
                "https://github.com/mozilla/mozjpeg/releases/download/v1.0/evil.exe",
                "v1.0",
                "..\\evil.exe",
            )

        with self.assertRaises(ValueError):
            security.validate_release_asset_url(
                "https://github.com/mozilla/mozjpeg/releases/download/v1.0/readme.txt",
                "v1.0",
                "readme.txt",
            )

    def test_validate_zip_members_rejects_path_traversal(self):
        # A member must never be able to write outside the extraction directory.
        archive = self.root / "unsafe.zip"
        with zipfile.ZipFile(archive, "w") as zip_file:
            zip_file.writestr("../escape.txt", b"must not extract")

        with self.assertRaises(ValueError):
            security.validate_zip_members(archive)

    def test_validate_zip_members_rejects_too_many_members(self):
        # Many tiny entries can exhaust resources even when the ZIP is small.
        archive = self.root / "many-files.zip"
        with zipfile.ZipFile(archive, "w") as zip_file:
            for index in range(security.MAX_ZIP_MEMBERS + 1):
                zip_file.writestr(f"file-{index}.txt", b"")

        with self.assertRaises(ValueError):
            security.validate_zip_members(archive)

    def test_security_limits_are_bounded(self):
        self.assertGreater(security.MAX_DOWNLOAD_BYTES, 0)
        self.assertLessEqual(security.MAX_DOWNLOAD_BYTES, 250 * 1024 * 1024)
        self.assertGreater(security.MAX_ZIP_MEMBERS, 0)
        self.assertGreater(security.MAX_ZIP_UNCOMPRESSED_BYTES, 0)


if __name__ == "__main__":
    unittest.main()
