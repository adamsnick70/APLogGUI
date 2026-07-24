"""AutoUpdate: version comparison, per-OS asset selection, and checksum
verification - the parts that don't require a real network call or a real
installer. fetch_latest_release/_download's actual HTTP is exercised only
via monkeypatched stand-ins here, never a live request."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest  # noqa: E402

import AutoUpdate  # noqa: E402


class TestIsNewer:
    def test_later_date_is_newer(self):
        assert AutoUpdate.is_newer("2026.08.01+abc1234", local_version="2026.07.23+def5678")

    def test_earlier_date_is_not_newer(self):
        assert not AutoUpdate.is_newer("2026.07.01+abc1234", local_version="2026.07.23+def5678")

    def test_same_date_different_sha_is_not_newer(self):
        assert not AutoUpdate.is_newer("2026.07.23+abc1234", local_version="2026.07.23+def5678")

    def test_dev_local_version_is_never_offered_an_update(self):
        # "dev" (a from-source run) has no installed build to replace, so
        # it should never be treated as older than a real dated release.
        assert not AutoUpdate.is_newer("2026.07.23+abc1234", local_version="dev")


class TestPickAsset:
    RELEASE = {
        "assets": [
            {"name": "AP-Log-Plotter-Setup.exe", "browser_download_url": "http://x/win.exe"},
            {"name": "AP-Log-Plotter-Setup.exe.sha256", "browser_download_url": "http://x/win.exe.sha256"},
            {"name": "AP-Log-Plotter.pkg", "browser_download_url": "http://x/mac.pkg"},
            {"name": "AP-Log-Plotter.pkg.sha256", "browser_download_url": "http://x/mac.pkg.sha256"},
            {"name": "ap-log-plotter.deb", "browser_download_url": "http://x/lin.deb"},
            {"name": "ap-log-plotter.deb.sha256", "browser_download_url": "http://x/lin.deb.sha256"},
        ]
    }

    def test_picks_the_windows_installer_and_its_checksum(self):
        installer, checksum = AutoUpdate.pick_asset(self.RELEASE, system="Windows")
        assert installer["name"] == "AP-Log-Plotter-Setup.exe"
        assert checksum["name"] == "AP-Log-Plotter-Setup.exe.sha256"

    def test_picks_the_macos_installer_and_its_checksum(self):
        installer, checksum = AutoUpdate.pick_asset(self.RELEASE, system="Darwin")
        assert installer["name"] == "AP-Log-Plotter.pkg"
        assert checksum["name"] == "AP-Log-Plotter.pkg.sha256"

    def test_picks_the_linux_installer_and_its_checksum(self):
        installer, checksum = AutoUpdate.pick_asset(self.RELEASE, system="Linux")
        assert installer["name"] == "ap-log-plotter.deb"
        assert checksum["name"] == "ap-log-plotter.deb.sha256"

    def test_unknown_system_returns_nothing(self):
        assert AutoUpdate.pick_asset(self.RELEASE, system="FreeBSD") == (None, None)

    def test_missing_checksum_asset_still_returns_the_installer(self):
        release = {"assets": [{"name": "AP-Log-Plotter-Setup.exe", "browser_download_url": "http://x"}]}
        installer, checksum = AutoUpdate.pick_asset(release, system="Windows")
        assert installer["name"] == "AP-Log-Plotter-Setup.exe"
        assert checksum is None


class TestCheckForUpdate:
    def test_no_release_data_means_no_update(self, monkeypatch):
        monkeypatch.setattr(AutoUpdate, "fetch_latest_release", lambda: None)
        assert AutoUpdate.check_for_update() is None

    def test_older_or_equal_release_means_no_update(self, monkeypatch):
        monkeypatch.setattr(AutoUpdate, "APP_VERSION", "2026.07.23+def5678")
        monkeypatch.setattr(
            AutoUpdate, "fetch_latest_release",
            lambda: {"tag_name": "2026.07.23+abc1234", "assets": []},
        )
        assert AutoUpdate.check_for_update() is None

    def test_newer_release_without_a_matching_asset_means_no_update(self, monkeypatch):
        monkeypatch.setattr(AutoUpdate, "APP_VERSION", "2026.07.01+def5678")
        monkeypatch.setattr(
            AutoUpdate, "fetch_latest_release",
            lambda: {"tag_name": "2026.07.23+abc1234", "assets": []},
        )
        assert AutoUpdate.check_for_update() is None

    def test_newer_release_with_a_matching_asset_is_returned(self, monkeypatch):
        monkeypatch.setattr(AutoUpdate, "APP_VERSION", "2026.07.01+def5678")
        monkeypatch.setattr(sys.modules["platform"], "system", lambda: "Windows")
        release = {
            "tag_name": "2026.07.23+abc1234",
            "assets": [{"name": "AP-Log-Plotter-Setup.exe", "browser_download_url": "http://x"}],
        }
        monkeypatch.setattr(AutoUpdate, "fetch_latest_release", lambda: release)
        result = AutoUpdate.check_for_update()
        assert result[0] == "2026.07.23+abc1234"
        assert result[1]["name"] == "AP-Log-Plotter-Setup.exe"


class TestChecksumVerification:
    def test_matching_checksum_verifies(self, tmp_path):
        path = tmp_path / "file.bin"
        path.write_bytes(b"hello world")
        import hashlib
        expected = hashlib.sha256(b"hello world").hexdigest()
        assert AutoUpdate.verify_checksum(path, expected)

    def test_mismatched_checksum_fails(self, tmp_path):
        path = tmp_path / "file.bin"
        path.write_bytes(b"hello world")
        assert not AutoUpdate.verify_checksum(path, "0" * 64)


class TestDownloadAndVerify:
    def _fake_download_factory(self, contents_by_name):
        def _fake_download(url, dest, timeout=30):
            name = Path(dest).name
            Path(dest).write_bytes(contents_by_name[name])
        return _fake_download

    def test_downloads_and_accepts_a_matching_checksum(self, tmp_path, monkeypatch):
        import hashlib
        installer_bytes = b"totally real installer"
        digest = hashlib.sha256(installer_bytes).hexdigest()
        monkeypatch.setattr(AutoUpdate, "_download", self._fake_download_factory({
            "app.exe": installer_bytes,
            "app.exe.sha256": f"{digest}  app.exe\n".encode(),
        }))

        installer_asset = {"name": "app.exe", "browser_download_url": "http://x/app.exe"}
        checksum_asset = {"name": "app.exe.sha256", "browser_download_url": "http://x/app.exe.sha256"}

        path = AutoUpdate.download_and_verify(installer_asset, checksum_asset, dest_dir=tmp_path)
        assert path.read_bytes() == installer_bytes

    def test_raises_on_checksum_mismatch(self, tmp_path, monkeypatch):
        monkeypatch.setattr(AutoUpdate, "_download", self._fake_download_factory({
            "app.exe": b"totally real installer",
            "app.exe.sha256": b"0" * 64 + b"  app.exe\n",
        }))
        installer_asset = {"name": "app.exe", "browser_download_url": "http://x/app.exe"}
        checksum_asset = {"name": "app.exe.sha256", "browser_download_url": "http://x/app.exe.sha256"}

        with pytest.raises(ValueError):
            AutoUpdate.download_and_verify(installer_asset, checksum_asset, dest_dir=tmp_path)

    def test_no_checksum_asset_skips_verification(self, tmp_path, monkeypatch):
        monkeypatch.setattr(AutoUpdate, "_download", self._fake_download_factory({
            "app.exe": b"totally real installer",
        }))
        installer_asset = {"name": "app.exe", "browser_download_url": "http://x/app.exe"}

        path = AutoUpdate.download_and_verify(installer_asset, None, dest_dir=tmp_path)
        assert path.read_bytes() == b"totally real installer"
