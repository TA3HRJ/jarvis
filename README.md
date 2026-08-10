# Jarvis

Türkçe konuşan, tek bir Linux dizüstü bilgisayarda offline-öncelikli çalışan bir sesli asistan. Sürekli dinleme, wake word, konuşma tanıma, katmanlı niyet yönlendirme, sesli yanıt, kod çalıştırma ve telefon üzerinden uzaktan komut gönderme yetenekleriyle günlük kullanım için geliştiriliyor.

## Neden farklı

Çoğu "sesli asistan" projesi her komutu doğrudan bir bulut LLM'e gönderir. Jarvis bunun tersini yapıyor: **LLM son çare.** Komutlar önce üç yerel, deterministik katmandan geçer; bulut yalnızca gerçekten açık uçlu/muhakeme gerektiren işlerde devreye girer.

```
mikrofon → AEC → VAD → wake word → STT (yerel Whisper)
                                       ↓
  [KATMAN 1] Gramer/regex          → doğrudan icra, LLM yok, ~200ms
             "sesi kıs", "saat kaç", "ekranı kilitle"
                                       ↓ eşleşmedi
  [KATMAN 2] Embedding niyet eşleme → şablon + slot doldurma, LLM yok
             yerel multilingual encoder (CPU), parafraz toleranslı
                                       ↓ güven düşük
  [KATMAN 3] Küçük yerel model      → SADECE niyet sınıflandırma + slot
             3B Q4 (~2 GB VRAM)        çıkarımı. Beyin DEĞİL.
                                       ↓ açık uçlu iş
  [KATMAN 4] Bulut LLM              → muhakeme, kod yazma, çok adımlı görev
```

Sonuç: günlük komutların büyük kısmı buluta hiç çıkmadan, ~200ms içinde biter. İnternet kesildiğinde katman 1-3 çalışmaya devam eder.

## Donanım kısıtı, tasarımı belirledi

Bu proje **6 GB VRAM'e ciddi bir yerel LLM'in sığmayacağı** varsayımıyla baştan tasarlandı — mimarideki her karar (katmanlı yönlendirici, lazy-load/idle-unload, int8 quantization, tek-süreç orkestratör) bu bütçeye oturmak için var.

| Bileşen | Değer | Kısıt |
|---|---|---|
| CPU | Intel Core i7, Alder Lake-P nesli (12. nesil mobil, 28W TDP) | sürekli yükte agresif throttle |
| GPU | RTX 3060 Laptop 75W, **6 GB VRAM** | **en sert kısıt** — ciddi yerel LLM sığmaz |
| RAM | **16 GB DDR4** | yükseltme yapılmadı, bütçe buna göre kuruldu |
| Kasa | İnce/hafif oyuncu dizüstü | termal duvar + fan gürültüsü |

VRAM bütçesi: Whisper `medium` int8 (~1.5-2 GB) + Katman 3'ün 3B Q4 modeli (~2-2.5 GB) aynı anda ~4/6 GB'a oturuyor; ikisi de kullanılmadığında GPU'dan otomatik boşalıyor.

## Bileşenler

- **STT:** faster-whisper `medium` int8, GPU'da
- **TTS:** Piper (`tr_TR-dfki-medium`), cümle bazlı streaming, konuşurken sözünü kesebilme (barge-in)
- **Wake word:** openWakeWord (`hey_jarvis`)
- **VAD / AEC:** Silero VAD, PipeWire echo-cancel
- **Katman 2:** `paraphrase-multilingual-MiniLM-L12-v2` embedding, CPU
- **Katman 3:** Qwen2.5-3B-Instruct Q4_K_M, GPU tam offload, JSON-schema kısıtlı çıktı
- **Katman 4:** DeepSeek veya Claude (tek satırla değiştirilebilir sağlayıcı soyutlaması), tool-calling ile sandbox'ta kod çalıştırma, kalıcı hafıza (SQLite + `sqlite-vec`), hava durumu, ses kontrolü
- **Sandbox:** `bwrap` ile izole kod çalıştırma — ağ yok, salt-okunur kök dosya sistemi
- **Uzaktan erişim:** FastAPI + token auth, Tailscale mesh üzerinden (internete açık uç yok), ntfy.sh push bildirimleri, iOS Shortcuts/Siri entegrasyonu
- **Servis:** tek `systemd --user` servisi, `Restart=on-failure`, yapılandırılmış log/denetim izi (journald)

Mimari kararların gerekçeleri ve fazların tam durumu için [`CLAUDE.md`](CLAUDE.md)'ye bakın.

## Kurulum

```bash
uv sync
cp .env.example .env   # kendi anahtar/token'larınızı doldurun
```

Gerekli modeller (Piper Türkçe sesi, openWakeWord, Katman 3 GGUF) ayrıca indirilmeli — `models/` dizini gitignore'da.

Servis olarak çalıştırmak için `~/.config/systemd/user/jarvis-main.service` örneğine bakın (`EnvironmentFile=.env`, `ExecStart=uv run python -m src.jarvis.main`).

## Durum

Aktif geliştirme aşamasında, kişisel/tek-kullanıcılı bir proje. Faz 0-4 ve 7 tamamlandı, Faz 5 (bulut LLM + sandbox + hafıza) çalışıyor, Faz 6'nın telefon tarafı (iOS Shortcuts) kullanıcı elinde tamamlanmayı bekliyor. Detaylı faz takibi `CLAUDE.md`'de.
