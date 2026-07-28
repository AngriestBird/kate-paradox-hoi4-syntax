import importlib.util
import stat
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Protocol, cast
from unittest.mock import patch


class GeneratorModule(Protocol):
    HOI4_XML: str

    def main(self) -> None: ...

    def write_atomic(self, path: str, contents: str) -> None: ...


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "generate_syntax", ROOT / "tools" / "generate_syntax.py"
)
if spec is None or spec.loader is None:
    raise RuntimeError("Could not load tools/generate_syntax.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
generate_syntax = cast(GeneratorModule, module)


class GeneratorTests(unittest.TestCase):
    def test_empty_documentation_preserves_xml(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            documentation = temp_path / "game" / "documentation"
            documentation.mkdir(parents=True)
            for name in (
                "effects_documentation.md",
                "triggers_documentation.md",
                "modifiers_documentation.md",
            ):
                (documentation / name).write_text("# export\n", encoding="utf-8")

            xml_path = temp_path / "hoi4.xml"
            original = (ROOT / "hoi4.xml").read_text(encoding="utf-8")
            xml_path.write_text(original, encoding="utf-8")
            original_xml_path = generate_syntax.HOI4_XML
            generate_syntax.HOI4_XML = str(xml_path)
            try:
                with (
                    patch.object(
                        sys,
                        "argv",
                        ["generate_syntax.py", "--hoi4", str(temp_path / "game")],
                    ),
                    self.assertRaisesRegex(SystemExit, "No documented tokens"),
                ):
                    generate_syntax.main()
            finally:
                generate_syntax.HOI4_XML = original_xml_path

            self.assertEqual(xml_path.read_text(encoding="utf-8"), original)

    def test_write_atomic_preserves_permissions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "hoi4.xml"
            path.write_text("old", encoding="utf-8")
            path.chmod(0o644)

            generate_syntax.write_atomic(str(path), "new")

            self.assertEqual(path.read_text(encoding="utf-8"), "new")
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o644)
            self.assertFalse(list(path.parent.glob(".hoi4.xml.*")))


class SyntaxMetadataTests(unittest.TestCase):
    def language(self, filename):
        return ET.parse(ROOT / filename).getroot()

    def test_localisation_priority_beats_yaml(self):
        language = self.language("hoi4-localisation.xml")
        self.assertGreaterEqual(int(language.attrib["priority"]), 10)

    def test_lua_uses_cstyle_indenter(self):
        language = self.language("hoi4-lua.xml")
        self.assertEqual(language.attrib["indenter"], "cstyle")


if __name__ == "__main__":
    unittest.main()
