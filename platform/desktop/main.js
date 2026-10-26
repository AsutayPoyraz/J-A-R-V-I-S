// JARVIS masaüstü kabuğu (madde 28 - MVP iskelet)
// Özellikler: sistem tepsisi, Win+J global kısayolu, tek örnek kilidi.
const { app, BrowserWindow, Tray, Menu, globalShortcut, nativeImage, shell } = require('electron');
const path = require('path');

// Sarmalanan web uygulamasının adresi (.env yerine ortam değişkeni)
const JARVIS_URL = process.env.JARVIS_URL || 'http://localhost:5173';

let win = null;
let tray = null;

// Tray ikonu: yanına icon.png konursa kullanılır; yoksa boş ikon (KISMEN - ikon eklenmeli)
function loadTrayIcon() {
  try {
    const img = nativeImage.createFromPath(path.join(__dirname, 'icon.png'));
    if (img.isEmpty()) console.warn('[jarvis-desktop] icon.png bulunamadı; tepsi ikonu boş olacak.');
    return img;
  } catch (e) {
    console.error('[jarvis-desktop] ikon yüklenemedi:', e.message);
    return nativeImage.createEmpty();
  }
}

function createWindow() {
  win = new BrowserWindow({
    width: 1280,
    height: 820,
    show: false, // tepsiye küçülerek başlar
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  win.loadURL(JARVIS_URL).catch((e) => {
    console.error('[jarvis-desktop] URL yüklenemedi:', JARVIS_URL, e.message);
    shell.openExternal(JARVIS_URL); // yedek: varsayılan tarayıcıda aç
  });
  // X'e basınca tam kapanmak yerine tepsiye küçül
  win.on('close', (ev) => {
    if (!app.isQuiting) {
      ev.preventDefault();
      win.hide();
    }
  });
}

function toggleWindow() {
  if (!win) return;
  if (win.isVisible() && win.isFocused()) win.hide();
  else {
    win.show();
    win.focus();
  }
}

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on('second-instance', () => toggleWindow());
  app.whenReady().then(() => {
    app.setAppUserModelId('com.jarvis.desktop');
    createWindow();

    // Sistem tepsisi
    tray = new Tray(loadTrayIcon());
    tray.setToolTip('JARVIS');
    tray.setContextMenu(
      Menu.buildFromTemplate([
        { label: 'Aç / Gizle (Win+J)', click: toggleWindow },
        { type: 'separator' },
        { label: 'Çıkış', click: () => { app.isQuiting = true; app.quit(); } },
      ])
    );
    tray.on('double-click', toggleWindow);

    // Win+J global kısayolu
    try {
      globalShortcut.register('Super+J', toggleWindow);
      console.log('[jarvis-desktop] Win+J kısayolu kaydedildi.');
    } catch (e) {
      console.error('[jarvis-desktop] kısayol kaydedilemedi:', e.message);
    }
    console.log('[jarvis-desktop] hazır:', JARVIS_URL);
  });

  app.on('before-quit', () => { app.isQuiting = true; });
  app.on('will-quit', () => globalShortcut.unregisterAll());
  // Tüm pencereler kapansa da tepside kalmaya devam et
  app.on('window-all-closed', () => {});
}
