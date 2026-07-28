#!/usr/bin/env sh
# Install the HOI4 Kate syntax-highlighting files for the current user.
# Works from a cloned repo or an extracted release archive (it copies the
# .xml files sitting next to this script).
set -eu

DEST=""
case "${1:-}" in
--dest)
	[ "$#" -eq 2 ] || {
		printf '%s\n' "Usage: $0 [--dest DIRECTORY]" >&2
		exit 2
	}
	DEST="$2"
	;;
"") ;;
*)
	printf '%s\n' "Usage: $0 [--dest DIRECTORY]" >&2
	exit 2
	;;
esac

if [ -z "$DEST" ]; then
	case "$(uname -s)" in
	Darwin) DEST="$HOME/Library/Application Support/org.kde.syntax-highlighting/syntax" ;;
	*) DEST="${XDG_DATA_HOME:-$HOME/.local/share}/org.kde.syntax-highlighting/syntax" ;;
	esac
fi

SRC="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$DEST"

for f in hoi4.xml hoi4-localisation.xml hoi4-lua.xml; do
	cp "$SRC/$f" "$DEST/$f"
	echo "installed $f -> $DEST"
done

echo "Done. Restart Kate to load the new highlighting."
