# JARVIS — Mobil Native & Akıllı Saat Entegrasyonu (Madde 28 · Dürüst Durum)

## Karar (kural gereği sahte kod yok)
Bu geliştirme ortamında Android/iOS derleme, NFC yığını, Wear OS / watchOS SDK **mevcut değil**.
Bu nedenle native uygulama/NFC/AOD widget için **sahte kod yazılmadı**; yapılabilir kısmı tamamlandı:

- **PWA**: `platform/web/public/` altında manifest + servis çalışanı (çekirdek ekran yüklemesi).
- **API sözleşmesi hazır** (aşağıda) → native ekip doğrudan bağlanabilir.
- **Eşleştirme**: QR + PIN akışı zaten backend'de çalışıyor (`/api/pair/*`).

## Yapılamayanlar (KISMEN / YAPILAMADI)
| Özellik | Durum | Neden |
| --- | --- | --- |
| Android/iOS native uygulama | YAPILAMADI | Store derleme ortamı yok |
| NFC ile eşleştirme | YAPILAMADI | NFC donanım/yığını gerekir |
| AOD widget (saat) | YAPILAMADI | Wear OS/watchOS SDK derlemesi gerekir |
| PWA + API sözleşmesi | TAMAMLANDI | — |

## Native ekip için API sözleşmesi
| Amaç | Uç | Not |
| --- | --- | --- |
| Eşleştirme | `POST /api/pair/generate`, `POST /api/pair/confirm`, `POST /api/pair/pin-confirm` | Token 5 dk ömürlü, tek kullanım |
| Ayar çek | `GET /api/settings` | `X-Client-ID` + `Authorization: Bearer <jwt>` |
| Ayar yaz | `PUT /api/settings` | Whitelist alanlar |
| Sohbet | `POST /api/chat` | Misafirte kalıcı kayıt yok |
| Kritik komut 2FA | `POST /api/critical/prepare-command`, `POST /api/critical/confirm-2fa` | Biyometrik/OTP |
| İzinler | `GET/PUT /api/privacy/permissions` | Hassas işlem kapıları |
| Denetim kaydı | `GET /api/privacy/audit/export` | İndirilebilir JSON |

## Açık kimlik doğrulama notu
JWT access token 15 dk ömürlü; refresh akışı `POST /api/auth/refresh`. Mobil istemci token'ı
güvenli saklamalı (Keychain/Keystore).
