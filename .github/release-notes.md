**Colours by a function: a formula picks the filament at each point, so the colours can follow your texture.** The web version has it too: <https://rickusinggithub.github.io/vaseinator/>.

### Download & run (Windows)
1. Download **Vaseinator.exe** below and run it. It is one file: nothing to unzip or install. SHA256SUMS.txt holds its checksum.
2. The app isn't code-signed, so Windows SmartScreen may say "Windows protected your PC". Click **More info → Run anyway**.

No Python needed. To run from source on any OS, see the README. Or just use it in your browser: <https://rickusinggithub.github.io/vaseinator/>.

### Changed in 1.15.0
- **Colours by a function.** Advanced ▸ Colours ▸ Colours: **By a function** gives a second formula, with the same variables and functions as Your own function, for the **filament at each point** of the wall. Its value is rounded down: below 1 is filament 1, 1 to 2 filament 2, and so on; below 0 counts as filament 1, and the last filament in use takes everything above it.
  - Made from the same terms as your texture, it colours the texture. For the Zigzag ribs, `1.2 * tri(12*theta + 3*tri(2*pi*z/25))`, the colours `2 + 2*tri(2*pi*z/25)` climb up and down with their zigzag.
  - It comes with examples (zigzag bands, spiral stripes, bands, stripes up the sides, checks, speckles) and its own help.
  - Each colour is a closed part of its own in the 3MF, set to its filament and cut just where the formula changes, so the slicer changes filament itself. The floor, and a closed top, are a part each in the wall's colour where it meets them. Holes cut through every part.
  - The 3D view shows the colours. It needs a normal print: spiral vase mode prints one filament, and low-poly facets stay one colour.
- Surprise me's Colours lock keeps the colour function too.

Vaseinator is free. If it has made you something you like, you can [buy me a coffee](https://ko-fi.com/rickapps).
