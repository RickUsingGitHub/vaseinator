// Vaseinator in the browser: the desktop app's own Python geometry, run by Pyodide in this worker so the
// page stays responsive while a vase is built.
//
// Messages in:  {id, call, args}   - call is a function of bridge.py
// Messages out: {id, ok, result} or {id, ok: false, error}; a build's mesh comes as transferable arrays.

importScripts("https://cdn.jsdelivr.net/pyodide/v0.26.4/full/pyodide.js");

let bridge = null;

async function start() {
  const py = await loadPyodide();
  await py.loadPackage("numpy");
  const files = await (await fetch("py/files.json")).json();
  py.FS.mkdirTree("/home/pyodide/vaseinator");
  for (const name of files) {
    const text = await (await fetch("py/" + name)).text();
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
      const [meta, pos, tri, col] = [out.get(0), out.get(1), out.get(2), out.get(3)];
      const result = { meta, positions: bytesOf(pos), triangles: bytesOf(tri), colours: bytesOf(col) };
      out.destroy();
      self.postMessage({ id, ok: true, result }, [result.positions, result.triangles, result.colours]);
      return;
    }
    if (call === "export_3mf" || call === "export_stl") {
      const buffer = bytesOf(bridge[call](...args));
      self.postMessage({ id, ok: true, result: buffer }, [buffer]);
      return;
    }
    self.postMessage({ id, ok: true, result: bridge[call](...args) });
  } catch (err) {
    self.postMessage({ id, ok: false, error: String(err && err.message ? err.message : err) });
  }
};
