import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYNTAX_FILES = ("hoi4.xml", "hoi4-localisation.xml", "hoi4-lua.xml")


@unittest.skipUnless(os.name == "posix", "The shell installer requires a POSIX host")
class ShellInstallerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home = self.root / "home"
        self.env = dict(os.environ, HOME=str(self.home))
        self.env.pop("XDG_DATA_HOME", None)

    def install(self, *args):
        return subprocess.run(
            ["sh", str(ROOT / "install.sh"), *args],
            env=self.env,
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )

    def assert_installed(self, dest):
        for filename in SYNTAX_FILES:
            self.assertEqual(
                (dest / filename).read_bytes(), (ROOT / filename).read_bytes()
            )

    def test_default_destination(self):
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = (
            "Library/Application Support"
            if sys.platform == "darwin"
            else ".local/share"
        )
        self.assert_installed(self.home / data / "org.kde.syntax-highlighting/syntax")

    def test_xdg_destination(self):
        data = self.root / "custom data"
        self.env["XDG_DATA_HOME"] = str(data)
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        if sys.platform == "darwin":
            data = self.home / "Library/Application Support"
        self.assert_installed(data / "org.kde.syntax-highlighting/syntax")

    def test_custom_destination_and_reinstall(self):
        dest = self.root / "custom [syntax]"
        result = self.install("--dest", str(dest))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_installed(dest)
        (dest / "hoi4.xml").write_text("old version", encoding="utf-8")
        result = self.install("--dest", str(dest))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_installed(dest)
        self.assertFalse(self.home.exists())

    def test_invalid_arguments_do_not_install(self):
        for args in (("--dest",), ("--dest", ""), ("--unknown",), ("--dest", "a", "b")):
            with self.subTest(args=args):
                result = self.install(*args)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("Usage:", result.stderr)
                self.assertFalse(self.home.exists())
                self.assertFalse((self.root / "a").exists())


if __name__ == "__main__":
    unittest.main()
