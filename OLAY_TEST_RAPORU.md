# Olay yönetimi doğrulama raporu

## Otomatik testler

28 test başarılı: tam 15 ardışık kare, ara kareyle sayacın sıfırlanması, aynı ID için tek kayıt, aynı karede yinelenen ID, farklı oturumlarda aynı ID'nin ayrılması, görüntü kaydı, tek saniyelik alarm çağrısı, yetkisiz hesabın reddi, inceleme geçmişi, False Alarm görüntü silme ve NULL güncellemesi, Confirmed için 30 günlük sınır, New görüntünün korunması, silme hatasının yeniden denenmesi, izin verilen klasör dışına silmenin engellenmesi, Q kapanışı ve kaynakların kapatılması.

30 gün sınırı denetimli saat ile test edildi; gerçekte 30 gün beklenmedi. Ses testi winsound.Beep çağrısının 1000 ms olduğunu doğrular; hoparlörden duyulması bu turda fiziksel olarak sınanmadı. Q testi OpenCV tuş girdisini taklit ederek temiz kapanışı doğrular.

## Gerçek modeller ve videolar

- baretli_iki_calisan.mp4: 206 kare; olay oluşturulmadı.
- baretsiz.mp4: 646 kare; takip ID 1 için yalnızca bir New olay ve gerçek görüntü dosyası oluşturuldu.
- Gerçek YOLOv8 kişi modeli ve ByteTrack kullanıldı. Her iki video baştan sona işlendi.
- Olay tablosundaki sessionId + trackId tekilliği ve kaydedilen görüntünün varlığı doğrulandı.
- Bağımlılık tutarlılık kontrolü başarılı.

Bu sonuçlar bütün kamera sahnelerinde doğru sınıflandırma garantisi değildir.

## Model iyileştirme denemesi

İlk denemede 5.269 eğitim görüntüsüyle bir tam ek tur tamamlandı; ikinci turda, video karşılaştırması iyileşmediği için durduruldu. Ardından 500 baş kırpımı + 500 baret kırpımı + 800 tam görselle dört tur yakın çekim eğitimi tamamlandı. Videolar bu eğitimlere katılmadı.

Altı sabit video karesinde 9 elle belirlenmiş baş bölgesi değerlendirildi (IoU >= 0.5, eşik 0.5). Özgün model 320 boyutta 9 doğru kutu, 3 ek/yanlış kutu ve 0 kaçırma üretti. Son deneme modeli 8 doğru kutu, 3 ek/yanlış kutu ve 1 kaçırma üretti. Bu nedenle yeni model varsayılan yapılmadı. Kutular baretli baş bölgesini kapsar; yalnızca baret kabuğu sınırı beklenmez. Altı kare küçük bir regresyon örneğidir; bağımsız genel doğruluk yüzdesi değildir.

## Ortam sınırları

SQL Server hizmetleri bulundu. Codex'in ayrı Windows hesabı SQL Server'a erişemedi (SSPI/Windows kimliği sorunu); gerçek SQL Server yazma/inceleme işlemleri burada doğrulanamadı. SQL Server şeması ve bağlantı desteği hazır; ilk normal Windows açılışında otomatik denenir. Veritabanı işlevleri gerçek SQLite ile test edildi.

Yeni olay penceresini çalıştıran test bu ortamda Tk/Tcl kitaplığını yükleyemedi. Bu nedenle bu sürümde görsel pencere incelemesi ve gerçek tıklamayla uçtan uca UI testi tamamlanamadı. Önceki arayüzün daha önce geçen testleri yeni olay ekranının testi olarak sayılmadı.

Windows zamanlanmış temizlik görevi kullanıcı hesabında ilk normal açılışta kaydedilir; bu çalışma ortamında gerçek görev kaydı çalıştırılmadı. Uygulama açıkken ve açılışta aynı temizlik işlevi ayrıca çalışır.
