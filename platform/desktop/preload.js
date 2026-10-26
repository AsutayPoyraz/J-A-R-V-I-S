// Güvenli köprü (contextIsolation açık). MVP'de ek API yok; sürüm bilgisi yeterli.
const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld('jarvisDesktop', {
  version: process.versions.electron,
  platform: process.platform,
});
