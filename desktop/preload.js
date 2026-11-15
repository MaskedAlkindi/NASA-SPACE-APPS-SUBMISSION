// Narrow bridge between the app's own local pages (connect / models) and the main process.
// Remote pages (the HEALTH-01 website) also get this object but it only exposes harmless calls.
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("health01", {
  isDesktop: true,
  config: () => ipcRenderer.invoke("config:get"),
  openServer: (url) => ipcRenderer.invoke("server:open", url),
  removeServer: (url) => ipcRenderer.invoke("server:remove", url),
  checkServer: (url) => ipcRenderer.invoke("server:check", url),
  startStack: () => ipcRenderer.invoke("stack:start"),
  ollama: {
    setUrl: (url) => ipcRenderer.invoke("ollama:setUrl", url),
    list: () => ipcRenderer.invoke("ollama:list"),
    remove: (name) => ipcRenderer.invoke("ollama:delete", name),
    pull: (name) => ipcRenderer.send("ollama:pull", name),
    onProgress: (fn) => ipcRenderer.on("ollama:pull-progress", (_e, msg) => fn(msg)),
  },
});
