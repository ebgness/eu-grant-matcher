# EU Grant Scorer

Gerçek Funding & Tenders Portal çağrılarını proje profiliyle karşılaştıran, skor, risk, elenme nedeni ve öneri üreten AB hibe eşleştirme MVP'si.
# EU Grant Scorer

## Mevcut Durum

- FTOP/SEDIA çağrıları çekiliyor, geçmiş çağrılar filtreleniyor ve duplicate kayıtlar temizleniyor.
- TRL, eylem türü, konu ve embedding tabanlı anlamsal eşleşme değerlendiriliyor.
- PDF, DOCX, TXT, MD ve JSON profil yükleme destekleniyor.
- Türkçe/İngilizce arayüz, resmi çağrı linkleri, loading/error modalı ve 10 MB dosya doğrulaması var.
- UYGUN, RİSKLİ ve ELENEN sonuçları ile açıklanabilir öneriler gösteriliyor.
- PDF, Excel, Word, JSON ve TXT ön fizibilite raporları üretilebiliyor.
- Profil ve eşleşme sonuçları SQLite'a kaydediliyor.
- Embedding skorları işlem süresince önbelleğe alınıyor.
- Opsiyonel geçmiş proje kanıtı `data/historical_projects.json` üzerinden kullanılabiliyor.
## Kurulum ve Çalıştırma

```powershell
python -m pip install -r requirements.txt
python src/refresh_data.py --text digital --page-size 100 --pages 5
python app.py
```
Tarayıcı: `http://127.0.0.1:5000`

`refresh_data.py` FTOP verisini çeker ve `data/processed/calls.json` dosyasını yeniler. Windows Task Scheduler ile bu komut günlük çalıştırılabilir.
## Veri Akışı

```text
FTOP/SEDIA -> data/raw -> normalize_calls.py -> data/processed/calls.json
Profil formu veya belge -> hard filters + embeddings -> skor + öneri + rapor
```
## Önemli Dosyalar

- `app.py`: Flask web uygulaması ve rapor endpoint'leri
- `src/fetch_real_calls.py`: FTOP çağrılarını indirir
- `src/fetch_call_details.py`: çağrı detaylarını indirir
- `src/normalize_calls.py`: SEDIA kayıtlarını standartlaştırır
- `src/refresh_data.py`: veri yenileme pipeline'ı
- `src/real_scorer.py`: skor ve uygunluk motoru
- `src/semantic_matcher.py`: çok dilli embedding eşleştirmesi
- `src/document_profile.py`: belge alanı çıkarımı
- `src/recommendations.py`: açıklanabilir öneriler
- `src/historical_projects.py`: CSV/JSON geçmiş proje kanıtı
- `src/database.py`: SQLite profil ve match kayıtları
- `src/pdf_report.py`: A4 PDF raporu
- `src/export_reports.py`: Excel ve Word raporları
- `templates/index.html`: arayüz
- `static/style.css`: arayüz stilleri

## Geçmiş Proje Verisi

`data/historical_projects.json` bir liste içermelidir. Kayıtlarda `title`, `summary`, `objective`, `description` veya `topic` alanlarından en az biri bulunabilir. CORDIS/Kohesio dışa aktarımı kullanıldığında kaynak ve lisans bilgisi saklanmalıdır.

## LLM Danışmanı

LLM katmanı varsayılan olarak kapalıdır. API anahtarı tanımlanmadığında yerel ve açıklanabilir öneriler çalışır.

```powershell
$env:AI_API_KEY="API_ANAHTARIN"
$env:AI_MODEL="gpt-4o-mini"
python app.py
```

API anahtarını dosyaya veya Git deposuna yazma.

## Sınırlar ve Sonraki Üretim İşleri

- Skor ön fizibilite göstergesidir; resmi uygunluk veya fon garantisi değildir.
- Kapsamlı CORDIS veri seti ve otomatik etiketli başarı/red eğitimi henüz eklenmedi.
- Konsorsiyum, ülke ve bütçe kuralları yalnızca veride açıkça görülen sinyallerle uygulanıyor; resmi çağrı metni yine kontrol edilmelidir.
- Kullanıcı hesabı, çok kiracılı veri izolasyonu, GDPR/KVKK saklama-silme politikaları ve üretim sunucusu henüz kurulmadı.
- Vector database yerine işlem içi embedding cache kullanılıyor.
