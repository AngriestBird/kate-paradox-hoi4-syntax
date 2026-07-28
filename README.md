# Kate Hearts of Iron IV Syntax Highlighting

Syntax highlighting for Hearts of Iron IV / Paradox script in the [Kate Text Editor](https://kate-editor.org/), and other KDE editors that use KSyntaxHighlighting (KWrite, KDevelop, etc).

> Unofficial and community-made. Not affiliated with or endorsed by KDE or Paradox Interactive. "Kate" and "KDE" are trademarks of KDE e.V., "Hearts of Iron" and "Paradox Interactive" are trademarks of Paradox Interactive AB, used here for identification only. No game files or assets are included or redistributed. The keyword lists are just the names of the game's documented scripting commands, which are facts about the language and not game content. MIT licensed (see `LICENSE`), no warranty, use at your own risk.

Three files, one per HOI4 file type:

- `hoi4.xml` for Paradox script (`.txt .gui .gfx .asset .sfx .settings .mod`)
- `hoi4-localisation.xml` for localisation (`*_l_english.yml`, `*_l_german.yml`, etc). It only matches Paradox-named `.yml` so it won't grab your other YAML files.
- `hoi4-lua.xml` for Lua (`.lua`)

## What it highlights

`hoi4.xml`: comments, strings, numbers, dates, booleans, and operators, plus every effect, trigger, and modifier from the game's own `documentation/` exports (around 1,900 tokens, colored by type). Also scopes, country tags, `@variables`, inline math like `@[ base + 10 ]`, and prefixes like `var:` and `event_target:`.

`hoi4-localisation.xml`: the `l_english:` header, keys and version numbers, and the markup inside strings (`§Y...§!` color codes, `[loc functions]`, `$variables$`, `£icons£`, `\n`).

`hoi4-lua.xml`: Kate's built-in Lua highlighting plus the engine naming conventions on top (`C` classes, `N` defines).

If something isn't highlighted it's probably a newer or DLC command. The wiki links at the bottom cover the rest.

## Install

### From a release (easiest)

Grab the `.zip` or `.tar.gz` from [Releases](../../releases), unpack it, and run the installer.

**Linux/MacOS**

```sh
tar -xzf hoi4-kate-syntax-*.tar.gz
cd hoi4-kate-syntax-*/
./install.sh
```

**Windows**

```powershell
Expand-Archive hoi4-kate-syntax-*.zip -DestinationPath .
cd hoi4-kate-syntax-*
.\install.ps1
```

Restart Kate and you're done.

### Flatpak and Snap

The default installer path is for native installs. For a sandboxed KDE editor,
pass its syntax directory explicitly:

```sh
# Kate Flatpak
./install.sh --dest "$HOME/.var/app/org.kde.kate/data/org.kde.syntax-highlighting/syntax"

# Kate Snap
./install.sh --dest "$HOME/snap/kate/current/.local/share/org.kde.syntax-highlighting/syntax"
```

Replace `org.kde.kate` or `kate` with the package name for another KDE editor.

### From source

```sh
git clone https://github.com/AngriestBird/kate-paradox-hoi4-syntax.git
cd kate-paradox-hoi4-syntax
./install.sh
```

Use `.\install.ps1` on Windows.

### By hand

Copy the three `.xml` files into your syntax folder.

**Linux**

```plaintext
~/.local/share/org.kde.syntax-highlighting/syntax/
```

**MacOS**

```plaintext
~/Library/Application Support/org.kde.syntax-highlighting/syntax/
```

**Windows**

```plaintext
%USERPROFILE%\AppData\Local\org.kde.syntax-highlighting\syntax\
```

Restart Kate. If a file doesn't pick it up on its own, set the language from the dropdown at the bottom-right, or under Tools > Highlighting > Scripts.

## Updating after a patch

The effect, trigger, and modifier lists are generated from HOI4's own documentation, so you can refresh them when the game updates:

```sh
tools/generate_syntax.py --hoi4 "/path/to/Steam/steamapps/common/Hearts of Iron IV"
```

It only rewrites the generated sections and leaves the hand-written lists and rules alone. Leave off `--hoi4` and it tries the usual Steam paths.

## Modding reference

The lists cover what's documented, but Paradox script is big and changes with every patch. For anything missing, or general modding help, the HOI4 wiki is the place to look:

- [Modding](https://hoi4.paradoxwikis.com/Modding)
- [Effects](https://hoi4.paradoxwikis.com/Effect)
- [Conditions (triggers)](https://hoi4.paradoxwikis.com/Conditions)
- [Scopes](https://hoi4.paradoxwikis.com/Scopes)
- [Modifiers](https://hoi4.paradoxwikis.com/Modifiers) and [List of modifiers](https://hoi4.paradoxwikis.com/List_of_modifiers)
- [Variables and data structures](https://hoi4.paradoxwikis.com/Data_structures)
- [Localisation](https://hoi4.paradoxwikis.com/Localisation)
