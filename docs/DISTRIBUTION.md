# Distribution: installers and code signing

Every push builds and tests these files on GitHub Actions (tab **Actions**, artifacts of the run):

| System | Files | How users install |
|---|---|---|
| Windows | `InnoPetrol-<version>-windows-setup.exe`, `.zip` | Run the installer. It installs per user, needs no administrator rights, adds Start menu and optional desktop shortcuts, and opens `.ipproj` projects with InnoPetrol. |
| macOS | `InnoPetrol-<version>-macos-arm64.dmg`, `.zip` | Open the disk image and drag InnoPetrol to Applications. |
| Linux | `InnoPetrol-<version>-linux-x86_64.tar.gz` | Extract the archive and run `./install.sh`, which adds the program to the applications menu. It can also run in place with `./InnoPetrol`. |

CI tests what users download. The Windows installer is installed silently, the Linux archive is
extracted, the macOS disk image is mounted. In each case the installed program must start, open a
LAS file and draw it (`--smoke-test`).

To build locally on each system: `uv run --group build python packaging/build.py`. The Windows
installer also needs [Inno Setup 6](https://jrsoftware.org/isinfo.php); without it, only the `.zip` is
built.

## Why downloaded copies show warnings

The executables are **not signed**, so the operating systems warn when they are downloaded from the
internet.

- **Windows SmartScreen:** "Windows protected your PC". Click *More info* ▸ *Run anyway*.
- **macOS Gatekeeper:** "InnoPetrol cannot be opened because it is from an unidentified developer",
  or "is damaged". Right-click the app ▸ *Open*, or run `xattr -dr com.apple.quarantine /Applications/InnoPetrol.app`.

Removing the warnings requires paid certificates. That is a decision for the project owner.

### macOS: Developer ID and notarization

1. **Developer account:** an Apple Developer Program membership (99 USD per year) gives a
   *Developer ID Application* certificate.
2. **Sign:** sign the app with the hardened runtime:
   `codesign --deep --force --options runtime --sign "Developer ID Application: …" InnoPetrol.app`.
   PyInstaller can sign during the build with `--codesign-identity`.
3. **Notarize:** submit the DMG for notarization and attach the ticket to it:
   `xcrun notarytool submit InnoPetrol.dmg --apple-id … --team-id … --wait`, then
   `xcrun stapler staple InnoPetrol.dmg`.
4. **In CI:** store the certificate (.p12, base64) and the notarization password as repository
   secrets, and import them into a temporary keychain before building.

### Windows: code signing certificate

- **Options:** an OV or EV code signing certificate from a certificate authority, or *Azure
  Trusted Signing*, the cheapest option for individuals and small organizations (monthly
  subscription).
- **What to sign:** both `InnoPetrol.exe` and the installer, with `signtool sign /fd sha256 /tr <timestamp-url> /td sha256 …`.
  Inno Setup can sign the installer and uninstaller itself through its `SignTool` directive.
- **SmartScreen reputation:** with an OV certificate, it builds up as more people download the
  signed files. With EV and Trusted Signing, it is immediate.

## Licences in the packages

The program is LGPL-3.0-or-later and uses PySide6/Qt (LGPL). Every package includes `COPYING` and
`COPYING.LESSER`, and the Windows installer shows the licence before installing. The *About* window
credits PySide6, lasio and NumPy.
