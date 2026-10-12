# Test raporu — 21 Eylül 2026

## Gerçek model ve girdiler

Kullanıcının `helmet_v1/weights/best.pt` modeli başarıyla yüklendi. Sınıf sırası doğrulandı: `0: head`, `1: helmet`, `2: person`. CPU üzerinde, güven eşiği 0.50 ve görüntü boyutu 640 ile çalıştırıldı.

| Test | Sonuç |
|---|---|
| Üç gerçek veri kümesi fotoğrafı | Tamamlandı; sırasıyla 8 baret, tespit yok, 1 baretsiz baş |
| baretli_iki_calisan.mp4 | 206/206 kare işlendi, çıktı yeniden okunarak doğrulandı; yaklaşık 19.72 saniye |
| baretsiz.mp4 | 646/646 kare işlendi, çıktı yeniden okunarak doğrulandı; yaklaşık 50.89 saniye |
| Canlı kamera 0 | Windows kamera erişimiyle görüntü okundu; 5 kare gerçek modelle işlendi, MP4 kaydı yeniden açıldı |
| Türkçe masaüstü arayüzü | Gizli Tk penceresinde gerçek fotoğraf işlendi; önizleme, sayaçlar, düğme durumu ve kapanış doğrulandı |
| Bağımlılık tutarlılığı | pip check başarılı |

Arayüz testi programatik olarak yapıldı; görünür pencere üzerinde elle tıklama/estetik inceleme yapılmadı. Bir kaydedilmiş fotoğraf ayrıca görsel olarak incelendi. Canlı kamera görüntüleri teslim paketine dahil edilmedi. Paket içindeki `test_results` üç fotoğrafın sonuçlarını ve 30 karelik video örneğini içerir; iki tam videonun test özetleri `verification` altında bulunur.

## Otomatik hata ve kayıt testleri

`python -m unittest discover -s tests -v`: **8 test başarılı**.

- Türkçe karakterli fotoğraf yolu, JPG ve CSV kaydı.
- Video dosyasının 5 kareyle kaydedilip yeniden açılması.
- İlk kareden sonra iptal ve oynatılabilir kısmi video.
- Bozuk fotoğraf hatası.
- Geçersiz güven eşiğinin reddi.
- Kamera bağlantısı kesildiğinde hata ve kaynak kapatma (taklit kamera).
- Kullanılamayan kamera hatası ve kaynak kapatma (taklit kamera).
- Video yazıcısı açılamadığında hata ve kaynak kapatma (taklit yazıcı).

## Model kalitesinin sınırı

Bu testler yazılımın çalıştığını doğrular; modelin bütün sahnelerde doğru tespit yaptığını göstermez. Mevcut eğitim 5 epoch. Arşivlenen son eğitim satırında precision 0.93974, recall 0.54191, mAP50 0.59747 ve mAP50–95 0.36819 görülüyor. Bunlar önceki eğitimin kayıtlarıdır, yeni ölçüm değildir. Özgün data.yaml içinde val ve test aynı klasöre işaret ediyor; bağımsız test başarısı olarak yorumlanmamalıdır.

Tespit olmayan fotoğraf ve sınırlı recall nedeniyle bazı baş/baretler kaçabilir. Güven eşiği arayüzden ayarlanabilir. Kişi takibi ve eski kodun zaman içindeki oylaması bu sürümde kullanılmaz; kutular ve sayılar doğrudan modelin kare bazındaki sonuçlarıdır.

## Çalıştırma

Bu bilgisayarda outputs klasöründeki `HEMEN_BASLAT.cmd` hazırlanmış test ortamını kullanır. ZIP başka yere çıkarılırsa içindeki `BASLAT.cmd` gerekli ortamı ilk açılışta kurar. Sabitlenmiş bağımlılıklar `requirements-lock.txt` içindedir. İlk kurulumlu başlatıcı uçtan uca ayrıca çalıştırılmadı; uygulama ve paketler hazırlanmış Python ortamında test edildi.
