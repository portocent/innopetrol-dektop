#!/bin/sh
# Installs InnoPetrol for the current user: copies the program to ~/.local/opt/InnoPetrol and adds
# it to the applications menu. Run it from the extracted folder:  ./install.sh
# To uninstall: rm -rf ~/.local/opt/InnoPetrol ~/.local/share/applications/innopetrol.desktop
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.local/opt/InnoPetrol"
mkdir -p "$DEST" "$HOME/.local/share/applications"
cp -R "$HERE"/. "$DEST"/
ICON="$(find "$DEST" -name logo-08.png | head -n 1)"
cat > "$HOME/.local/share/applications/innopetrol.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=InnoPetrol
Comment=Well log viewer and petrophysics
Exec="$DEST/InnoPetrol" %F
Icon=$ICON
Terminal=false
Categories=Science;Education;
DESKTOP
echo "InnoPetrol installed in $DEST"
