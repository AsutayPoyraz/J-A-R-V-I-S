// Ayar sayfası: base URL / token / client id saklama (chrome.storage.sync)
const fields = ['baseUrl', 'token', 'clientId'];

chrome.storage.sync.get(fields).then((v) => {
  for (const f of fields) {
    document.getElementById(f).value = v[f] || (f === 'clientId' ? 'ext-1' : '');
  }
});

document.getElementById('save').addEventListener('click', async () => {
  const data = {};
  for (const f of fields) data[f] = document.getElementById(f).value.trim();
  await chrome.storage.sync.set(data);
  const s = document.getElementById('status');
  s.textContent = 'Kaydedildi.';
  setTimeout(() => (s.textContent = ''), 2000);
});
