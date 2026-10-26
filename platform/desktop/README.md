# JARVIS Desktop (Electron) — Madde 28 MVP iskeleti

Sistem tepsisi + `Win+J` global kısayolu + tek örnek kilidi içeren sarmalayıcı.

## Kurulum ve çalıştırma
```powershell
cd platform/desktop
npm install                                  # electron indirir
$env:JARVIS_URL = "http://127.0.0.1:8000"    # web uygulamasının adresi
npm start
```

## Özellikler
- Sistem tepsisi: Aç/Gizle, Çıkış; X'e basınca tepsiye küçülür.
- `Win+J`: pencereyi her yerden açar/kapatır.
- Tek örnek: ikinci başlatış mevcut pencereyi öne getirir.

## Sınırlar (KISMEN raporu)
- `icon.png` deposa yok; tepsi ikonu boş görünür → **elle eklenecek**.
- URL sarmalayıcıdır; otomatik güncelleme (auto-update) yok.
- Electron derlemesi (exe) bu ortamda üretilmedi; `npm start` ile çalışır.
