import contextlib
import fnmatch
import importlib.util
import io
import os
import re
import stat
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from types import ModuleType
from typing import Protocol, cast
from unittest.mock import patch


class GeneratorModule(Protocol):
    HOI4_XML: str
    DEFAULT_STEAM_PATHS: list[str]
    os: ModuleType

    def find_hoi4(self, explicit: str | None) -> str: ...

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
    <list name="control_flow"><item>if</item><item>else</item></list>
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
                "* [IF](#if)\n* [add_ideas](#add_ideas)\n"
                "* [has_war](#has_war)\n* [Has_War](#has_war-1)\n"
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
                    return [item.text or "" for item in lst.iter("item")]
            self.fail(f"no list named {name}")

        # Scope TOC links are skipped, CAPITAL (scopes) wins over "capital",
        # and a token claimed by an earlier list or case variant is dropped.
        self.assertEqual(items("scopes"), ["CAPITAL"])
        self.assertEqual(items("control_flow"), ["if", "else"])
        self.assertEqual(items("effects"), ["add_ideas"])
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


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.steam = self.root / "Steam"
        roots = patch.object(generate_syntax, "DEFAULT_STEAM_PATHS", [str(self.steam)])
        roots.start()
        self.addCleanup(roots.stop)

    def install(self, library):
        game = library / "steamapps" / "common" / "Hearts of Iron IV"
        (game / "documentation").mkdir(parents=True)
        return str(game)

    def test_default_library(self):
        expected = self.install(self.steam)
        self.assertEqual(generate_syntax.find_hoi4(None), expected)

    def test_flatpak_library(self):
        flatpak = self.root / ".var/app/com.valvesoftware.Steam/.local/share/Steam"
        expected = self.install(flatpak)
        with patch.object(
            generate_syntax, "DEFAULT_STEAM_PATHS", [str(self.steam), str(flatpak)]
        ):
            self.assertEqual(generate_syntax.find_hoi4(None), expected)

    def test_extra_library_with_spaces_and_unicode(self):
        library = self.root / "Données Steam"
        expected = self.install(library)
        steamapps = self.steam / "steamapps"
        steamapps.mkdir(parents=True)
        (steamapps / "libraryfolders.vdf").write_text(
            '"libraryfolders" { "1" { "path" "' + str(library) + '" } }',
            encoding="utf-8",
        )
        self.assertEqual(generate_syntax.find_hoi4(None), expected)

    def test_windows_library_path_escapes(self):
        steamapps = self.steam / "steamapps"
        steamapps.mkdir(parents=True)
        (steamapps / "libraryfolders.vdf").write_text(
            r'"libraryfolders" { "1" { "path" "D:\\Steam Library" } }',
            encoding="utf-8",
        )
        expected = os.path.join(
            r"D:\Steam Library", "steamapps", "common", "Hearts of Iron IV"
        )
        with patch.object(
            generate_syntax.os.path,
            "isdir",
            side_effect=lambda path: path == os.path.join(expected, "documentation"),
        ):
            self.assertEqual(generate_syntax.find_hoi4(None), expected)

    def test_bad_manifest_warns_and_tries_next_library(self):
        steamapps = self.steam / "steamapps"
        steamapps.mkdir(parents=True)
        (steamapps / "libraryfolders.vdf").write_bytes(b"\xff")
        extra = self.root / "other Steam"
        expected = self.install(extra)
        errors = io.StringIO()
        with (
            patch.object(
                generate_syntax, "DEFAULT_STEAM_PATHS", [str(self.steam), str(extra)]
            ),
            contextlib.redirect_stderr(errors),
        ):
            self.assertEqual(generate_syntax.find_hoi4(None), expected)
        self.assertIn("Could not read", errors.getvalue())

    def test_explicit_path_does_not_scan_libraries(self):
        expected = self.install(self.root / "explicit")
        self.install(self.steam)
        with patch("builtins.open", side_effect=AssertionError("unexpected discovery")):
            self.assertEqual(generate_syntax.find_hoi4(expected), expected)

    def test_invalid_explicit_path_does_not_fall_back(self):
        self.install(self.steam)
        with self.assertRaisesRegex(SystemExit, "Pass it explicitly"):
            generate_syntax.find_hoi4(str(self.root / "missing"))

    def test_missing_game_reports_how_to_set_path(self):
        with self.assertRaisesRegex(SystemExit, "Pass it explicitly"):
            generate_syntax.find_hoi4(None)


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
            if rule.attrib["attribute"] == "Number"
            and "\\b" not in rule.attrib["String"]
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

    def test_generic_extensions_are_opt_in(self):
        language = self.language("hoi4.xml")
        patterns = language.attrib["extensions"].split(";")
        for name in ("notes.txt", "go.mod", "scene.asset", "user.settings"):
            self.assertFalse(any(fnmatch.fnmatchcase(name, p) for p in patterns), name)
        for name in ("menu.gui", "sprites.gfx", "sounds.sfx", "descriptor.mod"):
            self.assertTrue(any(fnmatch.fnmatchcase(name, p) for p in patterns), name)
        self.assertEqual(self.language("hoi4-lua.xml").attrib["extensions"], "")

    def test_control_flow_has_one_shared_style(self):
        language = self.language("hoi4.xml")
        tokens = {"if", "else_if", "else", "limit"}
        control = language.find("./highlighting/list[@name='control_flow']")
        self.assertIsNotNone(control)
        assert control is not None
        self.assertEqual({item.text for item in control}, tokens)
        all_items = [item.text.lower() for item in language.iter("item") if item.text]
        for token in tokens:
            self.assertEqual(all_items.count(token), 1, token)
        rules = list(language.iter("keyword"))
        control_rule = next(r for r in rules if r.attrib["String"] == "control_flow")
        effects_rule = next(r for r in rules if r.attrib["String"] == "effects")
        self.assertLess(rules.index(control_rule), rules.index(effects_rule))
        style = next(
            item
            for item in language.iter("itemData")
            if item.attrib["name"] == control_rule.attrib["attribute"]
        )
        self.assertEqual(style.attrib["defStyleNum"], "dsControlFlow")

    def test_syntax_authors(self):
        for filename in ("hoi4.xml", "hoi4-localisation.xml", "hoi4-lua.xml"):
            self.assertEqual(self.language(filename).attrib["author"], "AngriestBird")

    def test_flatpak_steam_is_a_default_root(self):
        self.assertIn(
            os.path.expanduser("~/.var/app/com.valvesoftware.Steam/.local/share/Steam"),
            generate_syntax.DEFAULT_STEAM_PATHS,
        )


if __name__ == "__main__":
    unittest.main()
