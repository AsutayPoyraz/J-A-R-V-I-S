# JARVIS — Paketleme Rehberi (PyInstaller)

Tek kaynak kod; **her platform kendi makinesinde** derlenir (teknik zorunluluk,
"ayrı sürüm" değildir — bkz. Özellik 2).

## Windows'ta kaynaktan başlatma
Proje kökünde PowerShell açıp aşağıdaki komutu çalıştırın. Başlatıcı, sistemdeki
başka bir Python yerine proje içindeki `.venv` yorumlayıcısını kullanır ve
PySide6 eksikse ne yapılacağını bildirir:
```powershell
.\start_jarvis.ps1
```
PowerShell script çalıştırma ilkesini engellerse geçerli oturum için şu şekilde
başlatabilirsiniz:
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start_jarvis.ps1
```

## Ön koşullar
```powershell
python -m pip install -r requirements.txt
python -m pip install pyinstaller
```

## Lint kapısı (ruff)
Kod, hata sınıfı kurallara göre denetlenir (`ruff.toml`: E9, F821, F811,
F841, B023, B033). Stil kuralları (import sırası, tzinfo vb.) kasten kapalıdır —
mevcut kod tabanının tarzını korumak için. Her değişiklikten sonra çalıştırın:
```powershell
python -m ruff check .
```

## Windows (.exe)
```powershell
pyinstaller jarvis.spec --noconfirm
# Çıktı: dist\JARVIS\JARVIS.exe  (onedir klasörü — dağıtımı klasörün tamamı yap)
```
Yayın için: `dist\JARVIS\` klasörünü zip'le veya Inno Setup ile tek .exe kurucu
yap. `.env` dosyasını **JARVIS.exe'nin yanına** koy (bundle'a gömülmez —
`config.py` frozen modda EXE dizininden okur).

## Tek komutla derleme (sürüm otomasyonu)
Sürümün tek kaynağı `config.py` → `APP_VERSION`'dur; pencere başlığı, sistem
promptu ve tepsi ipucu da `APP_DISPLAY_VERSION` üzerinden buradan beslenir.
Yeni sürüm çıkarırken yalnızca bu değeri değiştirin ve şu komutu çalıştırın:
```powershell
python build_installer.py
```
Betik sırasıyla: (1) `installer.iss` içindeki `MyAppVersion`'ı otomatik
senkronlar, (2) PyInstaller EXE'yi derler, (3) Inno Setup kurucusunu üretir.
Bayraklar: `--sync-only` (yalnızca sürüm senkronu), `--skip-exe` (dist hazır
olduğunda kurucuyu hızlı yeniden üretir). Çıktı:
`Output\JARVIS-Setup-<sürüm>.exe`. Gerçek HTTPS güncelleme denetimini elle
doğrulamak için: `python tests\_update_e2e.py`.

## Sürüm çıkarma (release.py)
Tam zinciri tek komutla yürütür: kapı (ruff + test paketi) → `config.py`
sürümü → `installer.iss` senkronu → CHANGELOG bölümü (notlar + önceki etiketten
bu yana girilen commit'lerin otomatik listesi) → git commit → EXE + kurucu
derlemesi → `v<sürüm>` etiketi. Etiket yalnızca tüm zincir başarılıysa atılır;
kapı geçilmeden hiçbir dosya yazılmaz.
```powershell
python release.py --bump patch                    # 10.0.0 → 10.0.1
python release.py --bump minor --notes "..."      # notla birlikte
python release.py --version 11.0.0                # açık hedef sürüm
python release.py --bump patch --skip-build       # derlemesiz (commit + etiket)
python release.py --bump patch --dry-run          # önizleme, hiçbir şey yazmaz
```
Korumalar: hedef sürüm mevcut sürüme eşitse veya `v<sürüm>` etiketi zaten
varsa durur. Türkçe `--notes` için kodlama güvenliği istenirse `--notes-file`
kullanın. Yayınlama: `git push --follow-tags`.

## AI sağlayıcıları
Gündelik sohbet Groq ile başlar. Bilgi sorularında Gemini önce denenir; güncel
bilgi/haber veya web araması isteklerinde Google Search grounding kullanılır ve
bulunan kaynaklar yanıta eklenir. Uygun sağlayıcı yanıt veremezse normal sohbet
diğer sağlayıcıya düşebilir. Sağlayıcı yönlendirme ve akış kodu
`services/ai_engine.py` içindedir; `jarvis_v11.py` uygulamanın profil,
persona ve ayarlarını bu servise bağlar. `.env` dosyasına anahtarları ekleyin:
```dotenv
GROQ_API_KEY=...
JARVIS_GEMINI_API_KEY=...
# İsteğe bağlı model seçimi:
# JARVIS_GROQ_MODEL=openai/gpt-oss-20b
# JARVIS_GEMINI_MODEL=gemini-3.8-flash
```
Gemini sohbet/yedek bağlantısı Google'ın OpenAI uyumlu API uç noktasını, web
araması ise Gemini'nin Google Search destekli Interactions API'sini kullanır.
Web araması için Gemini anahtarı yoksa güncel yanıt uydurmak yerine hata
bildirilir. Model adındaki boşluklar API kimliği için otomatik olarak tireye
çevrilir (ör. `Gemini 3.5 Flash-Lite` → `gemini-3.5-flash-lite`). Kod veya
paket değişikliklerinden sonra `python -m pip install -r requirements.txt`
çalıştırın.

## Yavaş veya kesintili internet
Paylaşılan HTTP istekleri bağlantı kurmak için 10 saniye, yanıt verisi
beklerken 90 saniye zaman aşımı kullanır. Güvenli `GET`/`HEAD` istekleri
geçici ağ hatalarında sınırlı sayıda yeniden denenir. Varsayılan olarak açık
düşük internet modu, AI isteklerinde 300 saniye zaman aşımı, otomatik tekrar
olmaması ve en fazla 256 yanıt tokenı kullanır; otomatik hava/kur yenilemesini,
sabah brifingini ve sürekli wake-word dinlemesini durdurur. Bu davranış
`⚙ → Düşük internet modu` ayarından değiştirilebilir. Kullanıcının açıkça
başlattığı AI ve web istekleri yine internet gerektirir; bu ayarlar bağlantıyı
hızlandırmaz ve 1 kbit/s hızda zamanında yanıt garantisi vermez.
Speedtest kütüphanesi çalışmazsa
uygulama sınırsız bir indirme başlatmak yerine küçük bir bağlantı kontrolü
yapar; bu kontrol indirme/yükleme hızını ölçmez. AI veya araştırma isteği
iptal edildiğinde açık HTTP yanıt akışı kapatılmaya çalışılır. Bağlantı
kurulurken sunucudan henüz yanıt alınmadıysa işlem, ağ zaman aşımına kadar
bekleyebilir.

## Çevrimdışı komutlar ve düşük kaynak modu
AI sağlayıcısı veya internet olmadan `saat kaç`, `bugünün tarihi ne`,
`hesapla: 12 * (3 + 4)`, `sistem durumu`, `sohbet geçmişinde ara <ifade>` ve
`hafızada ara <ifade>` gibi yerel komutlar kullanılabilir. `çevrimdışı
komutlar` ifadesi yerel komut listesini gösterir. Serbest biçimli sohbet,
web araması, güncel hava/kur/haber bilgisi bulut veya ağ bağlantısı olmadan
çalışmaz. Hesap makinesi yalnızca sınırlı aritmetik ifadeleri kabul eder; Python
kodu çalıştırmaz.

Dört veya daha az mantıksal CPU ya da 4 GiB ve daha az RAM algılandığında düşük
kaynak modu otomatik seçilir; ayarlardan elle değiştirilebilir. Bu mod çekirdek
animasyonunu ve donanım ölçüm sıklığını azaltır. Gerçek performans hedefini
ölçmek için proje Python ortamında `python benchmarks\benchmark_pipeline.py`
çalıştırın. Rapor yerel komut gecikmesini, Python tahsis tepe değerini ve JARVIS
modülünün soğuk import süresi/RSS belleğini gösterir. Sonuçlar makineye özeldir;
import ölçümü tam GUI başlangıcı, saha donanım testi veya ağ bant genişliği
ölçümü değildir.

## Kalite kontrolleri
Kaynak ağacında testleri, Python sözdizimi denetimini ve GUI açılış smoke
testini birlikte çalıştırmak için:
```powershell
python tests\run_validation.py
```
Yeni oluşturulmuş Windows paketini de başlatıp temel import/veri dosyalarını
doğrulamak için `python tests\run_validation.py --package-dir
<PyInstaller-çıktı-klasörü>` kullanın.

## Tanılama ve yerel veriler
Uygulamada `⚙ → Uygulama tanılaması` API anahtarlarının yalnızca ayarlı
olup olmadığını (değerlerini göstermeden) ve isteğe bağlı bileşen durumlarını
listeler. İki AI sağlayıcısı da yapılandırılmamışsa açılış uyarısı gösterilir.
`⚙ → Verileri yedekle...` oturum/veritabanı, ayarlar, profil, kişiler, stil ve
PDF dosyalarını ZIP'e alır; `.env`, API anahtarları ve loglar yedeklenmez.
ZIP şifrelenmez; yedeği güvenli bir yerde saklayın. Geri yüklemede PDF'ler
eklenir veya aynı yollu dosyaların üzerine yazılır; arşivde olmayan mevcut
PDF'ler korunur.
`⚙ → Yedekten geri yükle...` öncesinde mevcut duruma otomatik bir güvenlik
yedeklemesi yapar. Geri yükleme sırasında dosya sistemi hatası olursa,
uygulama değiştirdiği dosyaları işlem öncesi durumuna döndürmeyi dener ve
başarılı/başarısız geri alma adımlarını hata mesajında bildirir. Güvenlik
yedeklemesi `~/.jarvis/backups/` altında ayrıca korunur. Geri yükleme sonrası
JARVIS'i yeniden başlatın.

## Görev, beceri ve bellek yönetimi
`⚙ → Görev Merkezi` açık AI/araştırma görevlerini ve bu oturumdaki son iş
akışlarını adım durumlarıyla gösterir; iptal edilebilir bir görev güvenli
iptal isteği alabilir. Görev geçmişi uygulama oturumunda tutulur, yeniden
başlatmada temizlenir. `⚙ → Beceri Kataloğu` uygulama yeteneklerini listeler.
Çok adımlı `planla:` isteklerinde planı başlatmak için onay gerekir; dosya,
mesaj veya bilgisayar üzerinde yüksek etkili adımlarda ek onay istenebilir.
`⚙ → İzin tercihleri...` üzerinden eylem türü başına her seferinde onay,
oturumda bir kez veya engelleme seçilebilir.

`⚙ → Bellek ve Profil...` profil alanlarını, yerel notları ve Atlas'ın
indekslenmiş kaynaklarını yönetir. Kaynak silme yalnızca Atlas yerel indeksini
kaldırır, özgün dosyaya dokunmaz. Yerel profil/bellek verileri uzaktaki AI
bağlamına ancak `JARVIS_SHARE_CONTEXT` etkinse eklenir.

Sohbet geçmişinde `"sohbet geçmişinde ara <ifade>"` komutu ile yerel arama
yapılabilir; eşleşmeler bu bilgisayardaki veritabanından getirilir ve AI
sağlayıcısına gönderilmez. Önceki sohbet mesajları, `JARVIS_SHARE_CONTEXT`
açık olsa dahi model isteğine eklenmez. Oturum özetleri de AI profil bağlamına
dahil edilmez. Profil ekranındaki yanıt derinliği tercihi (kısa, dengeli,
detaylı) yerel ayarlarda saklanır ve yanıtın biçimini yönlendirir.

Önceki mesajlardan birini belirli bir yanıt için kullanmak isterseniz
`geçmiş bağlamıyla: <isteğiniz>` yazın. JARVIS, geçmişi yerel olarak arar ve
göndermeden önce hangi alıntıların AI sağlayıcısına gönderileceğini gösterip
her seferinde ayrıca onay ister. Onay verilmezse istek gönderilmez; eşleşme
yoksa istek de gönderilmez. Paylaşım en fazla üç kısa alıntıyla sınırlıdır ve
kalıcı paylaşım ayarını değiştirmez. Bu seçenek Normal sohbet modunda
kullanılabilir; Deep Research modu geçmiş alıntılarını kullanmaz.

Saklanan konuşmalar `⚙ → Bu sohbetin geçmişini sil...` ile tek tek; `⚙ → Tüm
sohbet geçmişini sil...` ile topluca kalıcı olarak silinebilir. Silme, etkin AI,
araştırma veya görev çalışması tamamlanana ya da iptal edilene kadar engellenir.
AI persona talimatları bağlamı kullanma, karmaşık istekleri dikkatle ele alma,
belirsizliği belirtme ve doğrulanmamış bilgiyi uydurmama hedeflerini içerir.
“IQ 140/200” bir model ayarı veya ölçülebilir kalite garantisi değildir;
gerçek kapasite seçilen sağlayıcı/modelin yetenekleriyle sınırlıdır.

## Güncelleme denetimi
Güncelleme denetimi herhangi bir dosyayı indirmez veya çalıştırmaz. Bir
GitHub-compatible "latest release" JSON API endpoint'ini `JARVIS_UPDATE_URL`
ortam değişkeniyle HTTPS üzerinden yapılandırın; mevcut sürümün karşılaştırması
için `JARVIS_VERSION` değerini de sağlayın (tanımsızsa paketle gelen
`config.APP_VERSION` kullanılır). Bulunan yayın sayfasını kullanıcı isteğiyle
açar; kurulum kullanıcı tarafından incelenip elle yapılır. Kaynak deposu/release
adresi yapılandırılmadığında denetim bunu açıkça bildirir.

Açılıştan ~6 saniye sonra sessiz bir otomatik denetim yapılır (arka plan
`QThread`'i, UI bloklanmaz). Bu denetim:
- ⚙ menüsündeki "Güncellemeleri otomatik denetle" anahtarıyla kapatılabilir
  (tercih IP + makine kimliği bazlı kalıcıdır),
- `JARVIS_UPDATE_URL` ayarlı değilse, düşük internet modundaysa veya uygulama
  kapanıyorsa hiç başlamaz,
- "sürüm güncel" sonucunda kullanıcıyı rahatsız etmez (yalnızca loglar);
  yeni sürüm varsa yayın sayfasını açmayı teklif eder.

## macOS (.app)
```bash
python3 -m pip install -r requirements.txt pyinstaller
pyinstaller jarvis.spec --noconfirm
# Çıktı: dist/JARVIS.app (spec içinde BUNDLE bloğu)
```
İlk çalıştırmada izin rehberi (Accessibility / Ekran Kaydı) otomatik gösterilir
(Özellik 2). `.env` → `JARVIS.app/Contents/MacOS/JARVIS` yanına.

## Paket içeriği notları
- `data/curriculum.json` gömülüdür (Özellik 8); güncelleme → JSON'u düzenleyip
  yeniden derle.
- `.env` ASLA bundle'a eklenmez (API anahtarı sızıntısını önlemek için).
- **playwright** hariç tutuldu (~40MB tasarruf): Marketplace araması ve web
  etkileşimi paketlenmiş sürümde devre dışı kalır, kod mesajla zarif düşer.
  İstersen `jarvis.spec` → `excludes` listesinden `"playwright"` çıkarıp
  `python -m playwright install chromium` ile tam desteği ekle.
- Tesseract (OCR, Özellik 5) sistem kurulumudur: `winget install
  UB-Mannheim.TesseractOCR` + `pytesseract` yolu PATH'te olmalı.
- Konsolsuz derlemede `print()` uyarıları sessiz gider; loglar
  `~/.jarvis/logs/jarvis.log` içindedir.

## Doğrulama (derleme sonrası)
1. `dist\JARVIS\JARVIS.exe` çalıştır → karşılama mesajı + mavi durum çerçevesi.
2. `+ → Arıza → Windows` → ATLAS açılır, JARVIS gizlenir (Özellik 6/3).
3. `"... sunumu hazırla"` → `.pptx` üretilir ve açılır (Özellik 1).
4. Bir PNG ekleyip `"bunu pdf yap"` → PDF çıktısı (Özellik 5).
5. Tüm testler ve GUI smoke testi için `python tests\run_validation.py`.
