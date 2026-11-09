**Typing your own function no longer stalls, and phi spreads it evenly round a box.** The web version has it all too: <https://rickusinggithub.github.io/vaseinator/>.

### Download & run (Windows)
1. Download **Vaseinator.exe** below and run it. It is one file: nothing to unzip or install. SHA256SUMS.txt holds its checksum.
2. The app isn't code-signed, so Windows SmartScreen may say "Windows protected your PC". Click **More info → Run anyway**.

No Python needed. To run from source on any OS, see the README. Or just use it in your browser: <https://rickusinggithub.github.io/vaseinator/>.

### Changed in 1.14.1
- **Typing in Your own function no longer stalls the app.** When you pause, you get a quick rough look at the shape. The whole vase, which can take several seconds, is built once you've stopped typing for 3 seconds, when you leave the box, or when you press Ctrl+Enter.
- **`phi` on a box:** with Evenly round the wall on (a tissue box cover starts with it on), your function's `phi` counts along the wall rather than the angle from the middle. So `1.2 * sin(20*phi)` spaces its waves as evenly along the long sides as round the ends. The function's help says how, and Evenly round the wall now shows whenever your function uses `phi`.
- Fixed: in the web version, the printing steps for a vase or a lid mentioned a button that isn't there.

Vaseinator is free. If it has made you something you like, you can [buy me a coffee](https://ko-fi.com/rickapps).
