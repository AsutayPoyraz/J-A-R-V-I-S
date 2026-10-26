// JARVIS tarayıcı eklentisi — arka plan (MV3, madde 28 - MVP iskelet)
// Akış: sağ tık → "JARVIS ile özetle" → seçili metni /api/chat'e gönder → bildirim göster.
const DEFAULT_BASE = 'http://127.0.0.1:8000';

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: 'jarvis-summarize',
    title: 'JARVIS ile özetle: "%s"',
    contexts: ['selection'],
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== 'jarvis-summarize' || !tab?.id) return;
  try {
    const [{ result }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => String(window.getSelection ? window.getSelection() : '').trim(),
    });
    if (!result) return notify('JARVIS', 'Seçili metin bulunamadı.');
    const summary = await summarize(result);
    notify('JARVIS Özet', summary);
  } catch (e) {
    console.error('[jarvis-ext]', e);
    notify('JARVIS', 'Hata: ' + e.message);
  }
});

async function summarize(text) {
  const { baseUrl = DEFAULT_BASE, token = '', clientId = 'ext-1' } =
    await chrome.storage.sync.get(['baseUrl', 'token', 'clientId']);
  const res = await fetch(baseUrl.replace(/\/$/, '') + '/api/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Client-ID': clientId,
      ...(token ? { Authorization: 'Bearer ' + token } : {}),
    },
    // Not: gövde anahtarı backend sözleşmesine göre doğrulandı (message/text)
    body: JSON.stringify({
      message: 'Aşağıdaki metni 5 madde halinde özetle:\n\n' + text.slice(0, 8000),
    }),
  });
  if (!res.ok) throw new Error('JARVIS yanıtı: ' + res.status);
  const data = await res.json();
  return data.reply || data.message || JSON.stringify(data).slice(0, 200);
}

// Bildirim: icon128.png yoksa sessizce atla (KISMEN - ikon elle eklenecek)
function notify(title, message) {
  try {
    chrome.notifications.create({
      type: 'basic',
      iconUrl: 'icon128.png',
      title,
      message: String(message).slice(0, 300),
    });
  } catch (e) {
    console.warn('[jarvis-ext] bildirim gösterilemedi:', e.message);
  }
}
