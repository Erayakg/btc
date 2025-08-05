# Twitter Automation AI

Bu proje, Twitter otomasyonu için geliştirilmiş bir AI tabanlı sistemdir. Kullanıcıların ayarları kolayca yapılandırabilmesi için Flask tabanlı bir web arayüzü sunar.

## Özellikler

- 🤖 AI destekli tweet oluşturma ve yanıtlama
- 🔄 Rakip profillerden içerik takibi ve repost
- 📊 Anahtar kelime bazlı tweet analizi
- ❤️ Otomatik tweet beğenme
- 🌐 Web tabanlı ayar yönetimi
- 📝 Canlı log takibi

## Kurulum

1. Gerekli paketleri yükleyin:
```bash
pip install -r requirements.txt
```

2. Geckodriver'ı indirin ve proje dizinine yerleştirin (Windows için geckodriver-v0.36.0-win32 klasörü zaten mevcut)

3. API anahtarlarınızı ayarlayın:
   - OpenAI API Key
   - Gemini API Key (opsiyonel)
   - Azure OpenAI API Key (opsiyonel)

## Kullanım

### Web Arayüzü ile Kullanım (Önerilen)

1. Flask uygulamasını başlatın:
```bash
python app.py
```

2. Tarayıcınızda `http://localhost:5000` adresine gidin

3. Web arayüzünden:
   - API anahtarlarınızı girin
   - Twitter otomasyon ayarlarını yapılandırın
   - AI model ayarlarını belirleyin
   - Browser ayarlarını düzenleyin
   - "Ayarları Kaydet" butonuna tıklayın
   - "Otomasyonu Başlat" butonuna tıklayın

### Komut Satırı ile Kullanım

Doğrudan main.py'yi çalıştırabilirsiniz:
```bash
python src/main.py
```

## Ayar Yapılandırması

### API Anahtarları
- `openai_api_key`: OpenAI API anahtarınız
- `gemini_api_key`: Google Gemini API anahtarınız (opsiyonel)
- `azure_openai_api_key`: Azure OpenAI API anahtarınız (opsiyonel)

### Twitter Otomasyon Ayarları
- `response_interval_seconds`: Tweet'ler arası bekleme süresi
- `max_tweets_per_keyword_scrape`: Anahtar kelime başına maksimum tweet sayısı
- `enable_competitor_reposts`: Rakip repost'larını etkinleştir/devre dışı bırak
- `enable_keyword_replies`: Anahtar kelime yanıtlarını etkinleştir/devre dışı bırak
- `enable_liking_tweets`: Tweet beğenmeyi etkinleştir/devre dışı bırak

### AI Model Ayarları
- `llm_service`: Tercih edilen AI servisi (openai, gemini, azure)
- `model_name_override`: Kullanılacak model adı
- `max_tokens`: Maksimum token sayısı
- `temperature`: Yaratıcılık seviyesi (0-2 arası)

### Browser Ayarları
- `browser_type`: Tarayıcı tipi (firefox, chrome)
- `headless`: Arka planda çalıştırma modu
- `page_load_timeout_seconds`: Sayfa yükleme zaman aşımı
- `script_timeout_seconds`: Script çalışma zaman aşımı

## Hesap Yapılandırması

`jsonfetch/accounts.json` dosyasında Twitter hesaplarınızı yapılandırın:

```json
[
  {
    "account_id": "your_twitter_handle",
    "is_active": true,
    "target_keywords": ["keyword1", "keyword2"],
    "competitor_profiles": ["https://twitter.com/competitor1"],
    "news_sites": ["https://example.com"],
    "research_paper_sites": ["https://arxiv.org"],
    "cookies": "config/your_account_cookies.json"
  }
]
```

## Güvenlik

- API anahtarlarınızı güvenli tutun
- Cookie dosyalarınızı paylaşmayın
- Rate limit'lere dikkat edin

## Katkıda Bulunma

1. Bu repository'yi fork edin
2. Yeni bir branch oluşturun (`git checkout -b feature/amazing-feature`)
3. Değişikliklerinizi commit edin (`git commit -m 'Add amazing feature'`)
4. Branch'inizi push edin (`git push origin feature/amazing-feature`)
5. Pull Request oluşturun

## Lisans

Bu proje MIT lisansı altında lisanslanmıştır. Detaylar için `LICENSE` dosyasına bakın.

## Destek

Sorunlarınız için Issues bölümünü kullanın veya proje sahibiyle iletişime geçin.