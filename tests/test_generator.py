import contextlib
import importlib.util
import io
import re
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


FIXTURE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<language name="Fixture">
  <highlighting>
    <list name="booleans"><item>yes</item></list>
    <list name="scopes">
      <item>CAPITAL</item>
    </list>
    <!-- BEGIN-GEN effects (generated) -->
    <list name="effects">
    </list>
    <!-- END-GEN effects -->
    <!-- BEGIN-GEN triggers (generated) -->
    <list name="triggers">
    </list>
    <!-- END-GEN triggers -->
    <!-- BEGIN-GEN modifiers (generated) -->
    <list name="modifiers">
    </list>
    <!-- END-GEN modifiers -->
    <list name="keywords"><item>focus</item></list>
  </highlighting>
</language>
"""


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

    def test_generates_deduplicated_lists(self):
        docs = {
            "effects_documentation.md": (
                "* [COUNTRY](#effects-for-scope-country)\n"
                "* [add_ideas](#add_ideas)\n"
                "* [if](#if)\n"
                "* [capital](#capital)\n"
            ),
            "triggers_documentation.md": (
                "* [if](#if)\n* [has_war](#has_war)\n* [Has_War](#has_war-1)\n"
            ),
            "modifiers_documentation.md": "* [stability_factor](#stability_factor)\n",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            documentation = temp_path / "game" / "documentation"
            documentation.mkdir(parents=True)
            for name, text in docs.items():
                (documentation / name).write_text(text, encoding="utf-8")

            # A minimal stand-in for hoi4.xml, so the test doesn't depend on
            # what the real hand-maintained lists happen to contain.
            xml_path = temp_path / "hoi4.xml"
            xml_path.write_text(FIXTURE_XML, encoding="utf-8")
            original_xml_path = generate_syntax.HOI4_XML
            generate_syntax.HOI4_XML = str(xml_path)
            try:
                with (
                    patch.object(
                        sys,
                        "argv",
                        ["generate_syntax.py", "--hoi4", str(temp_path / "game")],
                    ),
                    contextlib.redirect_stdout(io.StringIO()),
                ):
                    generate_syntax.main()
            finally:
                generate_syntax.HOI4_XML = original_xml_path

            root = ET.parse(xml_path).getroot()

        def items(name):
            for lst in root.iter("list"):
                if lst.attrib["name"] == name:
                    return [item.text for item in lst.iter("item")]
            self.fail(f"no list named {name}")

        # Scope TOC links are skipped, CAPITAL (scopes) wins over "capital",
        # and a token claimed by an earlier list or case variant is dropped.
        self.assertEqual(items("scopes"), ["CAPITAL"])
        self.assertEqual(items("effects"), ["add_ideas", "if"])
        self.assertEqual(len(items("triggers")), 1)
        self.assertEqual(items("triggers")[0].lower(), "has_war")
        self.assertEqual(items("modifiers"), ["stability_factor"])

    def test_write_atomic_writes_lf_on_every_platform(self):
        # On Linux text mode already writes LF, so check the argument that
        # keeps Windows from translating to CRLF rather than the bytes.
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "hoi4.xml"
            path.write_text("old", encoding="utf-8")
            with patch.object(
                generate_syntax.os, "fdopen", wraps=generate_syntax.os.fdopen
            ) as fdopen:
                generate_syntax.write_atomic(str(path), "a\nb\n")

            self.assertEqual(fdopen.call_args.kwargs.get("newline"), "\n")
            self.assertEqual(path.read_bytes(), b"a\nb\n")

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

    def test_number_rule_skips_digits_in_identifiers(self):
        language = self.language("hoi4.xml")
        pattern = next(
            rule.attrib["String"]
            for rule in language.iter("RegExpr")
            if rule.attrib["attribute"] == "Number" and "\\b" not in rule.attrib["String"]
        )
        number = re.compile(pattern)

        def numbers(line):
            # Mimic KSyntaxHighlighting: try the rule at each offset in turn.
            found, pos = [], 0
            while pos < len(line):
                match = number.match(line, pos)
                if match and match.end() > pos:
                    found.append(match.group())
                    pos = match.end()
                else:
                    pos += 1
            return found

        self.assertEqual(numbers("x = -5"), ["-5"])
        self.assertEqual(numbers("x=0.25"), ["0.25"])
        self.assertEqual(numbers("factor = .5"), ["5"])
        for line in ("focus_1 = {", "GER_1936", "1st_army", "id = news.12", "12ab"):
            self.assertEqual(numbers(line), [], line)

    def test_lua_uses_cstyle_indenter(self):
        language = self.language("hoi4-lua.xml")
        self.assertEqual(language.attrib["indenter"], "cstyle")


if __name__ == "__main__":
    unittest.main()
