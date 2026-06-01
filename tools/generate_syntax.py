#!/usr/bin/env python3
"""Regenerate the HOI4 Kate syntax keyword lists from the game's own docs.

HOI4 dumps every effect, trigger, and modifier to Markdown files in its
documentation/ folder. This reads those files and rewrites the GEN-marked
<list> blocks in hoi4.xml, so you don't have to maintain ~1,900 tokens by
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

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOI4_XML = os.path.join(REPO, "hoi4.xml")

DEFAULT_HOI4_PATHS = [
    os.path.expanduser("~/.local/share/Steam/steamapps/common/Hearts of Iron IV"),
    os.path.expanduser("~/.steam/steam/steamapps/common/Hearts of Iron IV"),
    os.path.expanduser(
        "~/Library/Application Support/Steam/steamapps/common/Hearts of Iron IV"
    ),
    r"C:\Program Files (x86)\Steam\steamapps\common\Hearts of Iron IV",
]

# Markdown item links look like `* [name](#name)`; scope table-of-content
# links look like `* [COUNTRY](#effects-for-scope-country)` and are skipped.
ITEM_RE = re.compile(r"^\* \[([A-Za-z0-9_]+)\]\(#(?!.*-for-scope-)")


def find_hoi4(explicit):
    candidates = [explicit] if explicit else DEFAULT_HOI4_PATHS
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
    with open(md_path, encoding="utf-8") as fh:
        for line in fh:
            m = ITEM_RE.match(line)
            if m:
                tokens.add(m.group(1))
    return tokens


def read_hand_list(xml_text, name):
    """Pull the <item> values out of a hand-maintained <list name=...>."""
    block = re.search(
        rf'<list name="{name}">(.*?)</list>', xml_text, re.DOTALL
    )
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


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--hoi4", help="path to the Hearts of Iron IV install directory")
    args = ap.parse_args()

    hoi4 = find_hoi4(args.hoi4)
    doc = os.path.join(hoi4, "documentation")

    effects = extract(os.path.join(doc, "effects_documentation.md"))
    triggers = extract(os.path.join(doc, "triggers_documentation.md"))
    modifiers = extract(os.path.join(doc, "modifiers_documentation.md"))

    with open(HOI4_XML, encoding="utf-8") as fh:
        xml_text = fh.read()

    # Tokens owned by hand-maintained lists win; a token never appears twice,
    # so keyword matching is unambiguous (first matching <keyword> rule wins).
    reserved = set()
    for hand in ("booleans", "scopes", "keywords"):
        reserved |= read_hand_list(xml_text, hand)

    effects -= reserved
    triggers -= reserved | effects
    modifiers -= reserved | effects | triggers

    xml_text = replace_gen(xml_text, "effects", render_list("effects", effects))
    xml_text = replace_gen(xml_text, "triggers", render_list("triggers", triggers))
    xml_text = replace_gen(xml_text, "modifiers", render_list("modifiers", modifiers))

    with open(HOI4_XML, "w", encoding="utf-8") as fh:
        fh.write(xml_text)

    print(
        f"hoi4.xml updated from {hoi4}\n"
        f"  effects:   {len(effects)}\n"
        f"  triggers:  {len(triggers)}\n"
        f"  modifiers: {len(modifiers)}"
    )


if __name__ == "__main__":
    main()
