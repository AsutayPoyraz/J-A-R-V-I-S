# JARVIS Tarayıcı Eklentisi — Madde 28 MVP iskeleti

Chrome/Edge (MV3): sayfada metin seçip sağ tık → "JARVIS ile özetle".

## Yükleme
1. `chrome://extensions` → Geliştirici modu → "Paketlenmemiş öğe yükle" → bu klasörü seç.
2. Eklenti ayarlarından **base URL**, **access token (JWT)** ve **client id** gir.

## Akış
- `background.js`: seçili metni `/api/chat`'e gönderir (`X-Client-ID` + `Authorization` başlıklarıyla), yanıtı bildirimde gösterir.

## Sınırlar (KISMEN raporu)
- `icon128.png` deposa yok; bildirim ikonu olmadan bildirim sessizce atlanır → **elle eklenecek**.
- Yalnızca özet akışı var; mağaza derlemesi (store packaging) yapılmadı.
