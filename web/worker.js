// Vaseinator in the browser: the desktop app's own Python, run by Pyodide in a worker so the page stays
// responsive. The page runs two: one builds the vase, the other answers everything else at once.
//
// Messages in:  {id, call, args}   - call is a function of bridge.py
// Messages out: {id, ok, result} or {id, ok: false, error}; a mesh or a file comes as transferable buffers.

importScripts("https://cdn.jsdelivr.net/pyodide/v0.26.4/full/pyodide.js");

let bridge = null;
const VERSION = self.location.search;          // the site's version, so its Python comes fresh with it

async function start() {
  const py = await loadPyodide();
  await py.loadPackage("numpy");
  const files = await (await fetch("py/files.json" + VERSION)).json();
  py.FS.mkdirTree("/home/pyodide/vaseinator");
  for (const name of files) {
    const text = await (await fetch("py/" + name + VERSION)).text();
    py.FS.writeFile("/home/pyodide/" + name, text);
  }
  py.runPython("import sys; sys.path.insert(0, '/home/pyodide')");
  bridge = py.pyimport("bridge");
  return bridge.start();
}

function bytesOf(proxy) {
  // a Python bytes object, as a fresh ArrayBuffer of its own
  const u8 = proxy.toJs();
  proxy.destroy?.();
  return u8.buffer.byteLength === u8.byteLength ? u8.buffer : u8.slice().buffer;
}

self.onmessage = async (event) => {
  const { id, call, args } = event.data;
  try {
    if (call === "start") {
      self.postMessage({ id, ok: true, result: await start() });
      return;
    }
    if (call === "build") {
      const out = bridge.build(...args);
      const result = { meta: out.get(0), positions: bytesOf(out.get(1)), triangles: bytesOf(out.get(2)),
        colours: bytesOf(out.get(3)), lean: bytesOf(out.get(4)) };
      out.destroy();
      self.postMessage({ id, ok: true, result }, [result.positions, result.triangles, result.colours, result.lean]);
      return;
    }
    if (call === "export_3mf") {
      const out = bridge.export_3mf(...args);
      const result = { data: bytesOf(out.get(0)), steps: out.get(1) };
      out.destroy();
      self.postMessage({ id, ok: true, result }, [result.data]);
      return;
    }
    if (call === "export_stl") {
      const buffer = bytesOf(bridge.export_stl(...args));
      self.postMessage({ id, ok: true, result: buffer }, [buffer]);
      return;
    }
    self.postMessage({ id, ok: true, result: bridge[call](...args) });
  } catch (err) {
    self.postMessage({ id, ok: false, error: String(err && err.message ? err.message : err) });
  }
};
