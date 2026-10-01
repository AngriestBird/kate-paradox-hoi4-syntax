#!/usr/bin/env python3
"""Regenerate the HOI4 Kate syntax keyword lists from the game's own docs.

HOI4 dumps every effect, trigger, and modifier to Markdown files in its
documentation/ folder. This reads those files and rewrites the GEN-marked
<list> blocks in hoi4.xml, so you don't have to maintain ~1,800 tokens by
hand. Re-run it after a game patch.

Usage:
    tools/generate_syntax.py --hoi4 "/path/to/Hearts of Iron IV"

Leave off --hoi4 to try the usual Steam paths. Only the GEN-marked sections
change; the hand-written lists and all the rules are left alone.
"""

import argparse
import os
import re
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOI4_XML = os.path.join(REPO, "hoi4.xml")

DEFAULT_STEAM_PATHS = [
    os.path.expanduser("~/.local/share/Steam"),
    os.path.expanduser("~/.steam/steam"),
    os.path.expanduser("~/.var/app/com.valvesoftware.Steam/.local/share/Steam"),
    os.path.expanduser("~/Library/Application Support/Steam"),
    r"C:\Program Files (x86)\Steam",
]

# Markdown item links look like `* [name](#name)`; scope table-of-content
# links look like `* [COUNTRY](#effects-for-scope-country)` and are skipped.
ITEM_RE = re.compile(r"^\* \[([A-Za-z0-9_]+)\]\(#(?!.*-for-scope-)")


def find_hoi4(explicit):
    libraries = []
    if not explicit:
        for steam in DEFAULT_STEAM_PATHS:
            libraries.append(steam)
            manifest = os.path.join(steam, "steamapps", "libraryfolders.vdf")
            try:
                with open(manifest, encoding="utf-8") as fh:
                    contents = fh.read()
            except FileNotFoundError:
                continue
            except (OSError, UnicodeError) as exc:
                print(f"Could not read {manifest}: {exc}", file=sys.stderr)
                continue
            for path in re.findall(r'"path"\s+"((?:\\.|[^"\\])*)"', contents):
                libraries.append(re.sub(r'\\([\\"])', r"\1", path))
    candidates = (
        [explicit]
        if explicit
        else [
            os.path.join(library, "steamapps", "common", "Hearts of Iron IV")
            for library in libraries
        ]
    )
    for path in candidates:
        if path and os.path.isdir(os.path.join(path, "documentation")):
            return path
    sys.exit(
        "Could not find a HOI4 install with a documentation/ folder.\n"
        "Pass it explicitly: tools/generate_syntax.py --hoi4 '/path/to/Hearts of Iron IV'"
    )


def extract(md_path):
    """Return the sorted set of documented token names from a doc .md file."""
    tokens = set()
    try:
        with open(md_path, encoding="utf-8") as fh:
            for line in fh:
                m = ITEM_RE.match(line)
                if m:
                    tokens.add(m.group(1))
    except OSError as exc:
        sys.exit(f"Could not read {md_path}: {exc}")
    if not tokens:
        sys.exit(
            f"No documented tokens found in {md_path}. The documentation format may have changed."
        )
    return tokens


def read_hand_list(xml_text, name):
    """Pull the <item> values out of a hand-maintained <list name=...>."""
    block = re.search(rf'<list name="{name}">(.*?)</list>', xml_text, re.DOTALL)
    if not block:
        return set()
    return set(re.findall(r"<item>([^<]+)</item>", block.group(1)))


def render_list(name, tokens):
    items = "\n".join(f"      <item>{t}</item>" for t in sorted(tokens))
    return f'    <list name="{name}">\n{items}\n    </list>'


def replace_gen(xml_text, name, rendered):
    pattern = re.compile(
        rf"(<!-- BEGIN-GEN {name}[^>]*-->\n).*?(\n\s*<!-- END-GEN {name} -->)",
        re.DOTALL,
    )
    if not pattern.search(xml_text):
        sys.exit(f"GEN markers for '{name}' not found in hoi4.xml")
    return pattern.sub(lambda m: m.group(1) + rendered + m.group(2), xml_text)


def write_atomic(path, contents):
    fd, temp_path = tempfile.mkstemp(
        dir=os.path.dirname(path), prefix=".hoi4.xml.", text=True
    )
    try:
        # newline="\n" keeps LF endings on Windows instead of rewriting the
        # whole file as CRLF.
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(contents)
        os.chmod(temp_path, os.stat(path).st_mode)
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--hoi4", help="path to the Hearts of Iron IV install directory")
    args = ap.parse_args()

    hoi4 = find_hoi4(args.hoi4)
    doc = os.path.join(hoi4, "documentation")

    effects = extract(os.path.join(doc, "effects_documentation.md"))
    triggers = extract(os.path.join(doc, "triggers_documentation.md"))
    modifiers = extract(os.path.join(doc, "modifiers_documentation.md"))

    try:
        with open(HOI4_XML, encoding="utf-8") as fh:
            xml_text = fh.read()
    except OSError as exc:
        sys.exit(f"Could not read {HOI4_XML}: {exc}")

    # Tokens owned by hand-maintained lists win; a token never appears twice,
    # so keyword matching is unambiguous (first matching <keyword> rule wins).
    # hoi4.xml matches keywords case-insensitively, so compare lowercased.
    taken = set()
    for hand in ("booleans", "scopes", "control_flow", "keywords"):
        taken |= {t.lower() for t in read_hand_list(xml_text, hand)}

    def claim(tokens):
        kept = set()
        for t in sorted(tokens):
            if t.lower() not in taken:
                taken.add(t.lower())
                kept.add(t)
        return kept

    effects = claim(effects)
    triggers = claim(triggers)
    modifiers = claim(modifiers)

    xml_text = replace_gen(xml_text, "effects", render_list("effects", effects))
    xml_text = replace_gen(xml_text, "triggers", render_list("triggers", triggers))
    xml_text = replace_gen(xml_text, "modifiers", render_list("modifiers", modifiers))

    write_atomic(HOI4_XML, xml_text)

    print(
        f"hoi4.xml updated from {hoi4}\n"
        f"  effects:   {len(effects)}\n"
        f"  triggers:  {len(triggers)}\n"
        f"  modifiers: {len(modifiers)}"
    )


if __name__ == "__main__":
    main()
