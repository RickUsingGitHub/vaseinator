**Fixes for the design library: two browser tabs, printer profiles, recovery and damaged files.** The web version has them too: <https://rickusinggithub.github.io/vaseinator/>.

### Download & run (Windows)
1. Download **Vaseinator.exe** below and run it. It is one file: nothing to unzip or install. SHA256SUMS.txt holds its checksum.
2. The app isn't code-signed, so Windows SmartScreen may say "Windows protected your PC". Click **More info → Run anyway**.

No Python needed. To run from source on any OS, see the README. Or just use it in your browser: <https://rickusinggithub.github.io/vaseinator/>.

### Changed in 1.14.2
- Fixed: with the web version open in two tabs, saving to the library in one could wipe what the other had saved. Each change is now made to the library as last saved, one tab at a time.
- Fixed: in the Windows app, applying a printer or material profile now keeps its settings for New and the next start, as changing them in the panel does. Undo still takes it back in one step.
- Fixed: typing a design's name no longer fills Recovery with one entry per letter, pushing out earlier designs. A change to the name alone keeps the design's one place.
- Fixed: a damaged library file (a wrong kind of value in it) is now reported as one, in both versions, instead of failing with an error.

Vaseinator is free. If it has made you something you like, you can [buy me a coffee](https://ko-fi.com/rickapps).
