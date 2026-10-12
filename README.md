# Baret Tespit — Olay Yönetimi

## Açılış

**BASLAT.cmd** dosyasını Dosya Gezgini'nden çift tıklayın veya VS Code terminalinde ` .\BASLAT.cmd ` çalıştırın. İlk açılış eksik Python paketlerini kurar. VS Code hata ayıklama düğmesi bu başlatıcı için kullanılmaz.

Fotoğraf, video veya kamerayı seçip **Tespiti ve olay takibini başlat** düğmesine basın. Fotoğraf tek karelik analizdir; 15 kare koşulu nedeniyle fotoğraftan olay üretilmez.

Ana ekran görüntü kaynağı, tespit seçenekleri, önizleme ve olay incelemesi olarak düzenlenmiştir. Model otomatik olarak `models/best.pt` konumundan yüklenir; işlem sonuçları `results` klasörüne kaydedilir. Model/kayıt klasörü seçme ve ayrı OpenCV penceresi seçenekleri arayüzden kaldırılmıştır. Güven eşiği ekranda gösterilmez; proje klasöründeki `settings.json` dosyasının `confidence` alanından değiştirilir (varsayılan 0.5). Değer her yeni tespit başlatıldığında okunur. Videonun tamamını kaydetme seçeneği korunmuştur.

## Olay oluşturma

- Ayrı kişi modeli YOLOv8 + ByteTrack ile kişi ID'leri üretir. Baş/baret bulguları kişinin üst bölgesiyle eşleştirilir. Kişi takibi olmadan ID uydurulmaz ve olay oluşmaz.
- Aynı kişi 15 ardışık işlenen kare boyunca baretsiz algılanırsa New olay ve görüntü kaydedilir. Baret, kararsızlık, başın görünmemesi veya kişinin bir karede kaybolması sayacı sıfırlar.
- Olay başına 1 saniyelik ses ve **Yeni İhlal Mevcut** bildirimi verilir.
- Aynı takip oturumunda aynı ID için yalnızca bir kayıt oluşturulur. İnceleme sonucu verilmesi aynı kişiye yeniden alarm üretmez. Kaynağı yeniden başlatmak yeni bir takip oturumudur; bu yüzden oturum kimliği de veritabanında tutulur.
- Baretsiz kişi kırmızı, baretli kişi yeşil, kararsız/yetersiz görüntü sarıdır. Tek başına tespit olmaması güvenli olunduğu anlamına gelmez.

15 kare, kaynak 15–30 FPS olduğunda yaklaşık 0.5–1 saniyelik görüntüye karşılık gelir. Canlı kamerada işlemci iki modeli daha yavaş işliyorsa gerçek bekleme süresi uzar; sabit bir saniye garantisi verilmez.

## Operatör incelemesi

**Olay kayıtlarını incele** düğmesi görüntüyü, kamera/kaynak adını, tarihi, saati, takip ID'sini ve durumu gösterir. Görüntü dosyasının yolu ekrana yazılmaz. New kayıtlar turuncu ve kalın yazıyla öne çıkar.

İlk açılışı yapan Windows hesabı yetkili operatör olarak kaydedilir. Kimlik Windows SID'si ile denetlenir; ayrıca uygulama parolası gerekmez. Başka Windows hesapları kendiliğinden yetkili olmaz. Ek operatör için veritabanındaki Operators tablosuna yöneticinin ilgili Windows SID'sini eklemesi gerekir.

- **Confirmed:** İhlali onaylar ve kaydı sonlandırır. Görüntü, onay saatinden 30 gün sonra silinmeye uygun olur.
- **False Alarm:** İnceleme sonucunu kaydeder, görüntüyü hemen siler ve snapshotPath alanını NULL yapar.
- Her iki durumda olay satırı ve ReviewHistory inceleme kaydı korunur. Sonlandırılmış kayıt tekrar değiştirilemez.
- Görüntü başka program tarafından kilitliyse inceleme sonucu korunur; temizlik tekrar denenir. Başarısız silme, başarılı gibi gösterilmez.

## Veritabanı ve saklama

Uygulama önce Windows kimliğiyle yerel MS SQL Server'a (`.` ve `.\MSSQLSERVER01`) bağlanarak **BaretTespitApp** veritabanını ve tablolarını oluşturmayı dener. SQL kullanıcı adı/parolası istenmez, mevcut başka veritabanları değiştirilmez.

Bağlantı kurulamazsa yerel SQLite veritabanına geçer ve arayüzde bunu belirtir. Seçilen veritabanı sonraki açılışlarda korunur; veriler iki farklı depoya sessizce bölünmez. Önceden SQL seçilmişken SQL erişilemez olursa otomatik olarak boş SQLite'a geçilmez, hata gösterilir.

Olay tablosu istenen alanları içerir: logId, trackId, timeStamp, sourceName, violationType, snapshotPath, status. ID'nin başka kamera/oturumla karışmaması için sessionId; saklama süresi ve inceleme için reviewedAt, reviewedBy, reviewedBySid eklenmiştir. SQL Server'da logId IDENTITY, SQLite'ta AUTOINCREMENT kullanılır. Unicode adlar için SQL Server metinleri NVARCHAR'dır. Zamanlar UTC kaydedilir, arayüzde yerel saate çevrilir.

Görüntüler uygulamanın `data/snapshots` klasöründe; veritabanı bağlantı seçimi `data/storage.json` içinde saklanır. snapshotPath bu veri klasörüne göre göreli dosya yoludur.

Temizlik açılışta ve uygulama açıkken her dakika yapılır. Uygulama ayrıca Windows oturumu açıkken saatte bir çalışan bir Windows zamanlanmış görevi kaydetmeyi dener. Böylece pencere kapalıyken de süresi dolan görüntüler temizlenebilir. Görev kurulamazsa arayüzde bildirilir; uygulama içi temizlik çalışmaya devam eder. Bilgisayar kapalıyken veya Windows oturumu kapalıyken temizlik yapılamaz; sonraki çalışmada geciken temizlik tamamlanır. New görüntüler otomatik silinmez.

**Videonun tamamını ayrıca kaydet** varsayılan olarak kapalıdır. Açılırsa oluşan video ve elle kaydedilen görüntüler olay görüntüsü saklama kuralından bağımsızdır; bunlar ayrıca yönetilmelidir. Kaynak olarak seçtiğiniz özgün videolar silinmez.

## Güvenli kapanış

**Durdur** akışı sonlandırır. Önizlemeye tıkladıktan sonra **Q** programı güvenle kapatır. Görüntü tek uygulama penceresinde gösterilir. Video yazıcısı ve kamera kaynakları kapatılır.

## Model durumu

Özgün eğitimde kullanılan model korunmuştur. Tam veri kümesinde ek eğitim ve yakın çekim eğitimi denendi; yeni model sabit video karelerinde daha iyi sonuç vermediğinden varsayılan yapılmadı. Çıkarım boyutu modelin eğitim boyutu olan 320'ye döndürüldü. Aynı baş için çelişkili head/helmet sonuçları Kararsız olarak gösterilir. Gerçek kişilerde yanlış tahmin hâlâ mümkündür; bu nedenle operatör incelemesi gereklidir.

## Doğrulama

`python -m unittest discover -s tests -v`

Ayrıntılar: **OLAY_TEST_RAPORU.md**. `TEST_RAPORU.md` önceki sürümün tarihsel raporudur.

Teknik referanslar: https://docs.ultralytics.com/modes/track/ ve https://learn.microsoft.com/en-us/windows/win32/taskschd/daily-trigger-example--xml-
