# Jarvis — Sesli AI Asistan Projesi

Türkçe konuş. Kullanıcı Türkçe çalışıyor.

## Proje amacı

MSI Stealth 15M laptop üzerinde Jarvis tarzı sesli asistan:
- Sürekli dinleme, wake word, konuşma anlamlandırma
- Sesli geri bildirim (yapılan işleri sesli raporlama)
- Kod yazma/çalıştırma yeteneği (zorunlu gereksinim)
- iPhone'dan (ileride Android) uzaktan komut dispatch
- Çoklu amaçlı günlük kullanım

## Donanım (doğrulandı)

| Bileşen | Değer | Kısıt |
|---|---|---|
| Model | MSI Stealth 15M B12UE/B12UX | ince kasa, termal duvar + fan gürültüsü |
| CPU | Intel i7-1260P / 1280P (Alder Lake-P, 28W) | sürekli yükte agresif throttle |
| GPU | RTX 3060 Laptop 75W, **6 GB VRAM** | **en sert kısıt** — ciddi yerel LLM sığmaz |
| RAM | **16 GB DDR4** (2 slot, 64 GB'a kadar) | yükseltme fiyat nedeniyle **pas geçildi** |
| Ağ | Wi-Fi 6 AX201, BT 5.2 | yeterli |
| Ses | Intel SST + dizi mikrofon | **doğrulanmadı — Faz 0 blokeri** |

## Verilen kararlar

| Konu | Karar | Gerekçe |
|---|---|---|
| İşletim sistemi | **CachyOS + KDE Plasma** (temiz kurulum yapıldı) | güncel kernel = en iyi Alder Lake SOF şansı; BTRFS snapshot = rolling release güvenliği; PipeWire AEC; systemd servis yönetimi; 16 GB'da Windows+WSL2'ye göre ~4-5 GB daha az idle tüketim |
| Oturum tipi | **X11 + Wayland ikisi de kurulu, karar Faz 5'e ertelendi** | Wayland kısıtları `ydotool`/KWin D-Bus ile aşılabilir; KDE X11'i bakım moduna aldı, Plasma 7'de düşecek — kalıcı olarak X11'e kilitlenmek teknik borç |
| Beyin katmanı | **Katmanlı yönlendirici, LLM son çare** | maliyet + gecikme + çevrimdışı dayanıklılık |
| TTS | **Piper (yerel, offline, ücretsiz)** | çevrimdışı ve bedava; streaming arayüz arkasına soyutlanacak ki motor sonradan değişebilsin |
| STT | faster-whisper `small` int8, GPU'da | VRAM bütçesi; Türkçe doğruluk Faz 3'te ölçülecek, yetmezse `medium` yeniden hesaplanır |
| RAM yükseltmesi | **Yapılmayacak** | fiyat. Not: kullanıcı DDR5 fiyatına bakmıştı, bu makine DDR4 — istenirse yeniden değerlendirilebilir |

## Mimari — katmanlı niyet yönlendirici

Amaç: **LLM'i son çare yap.** Günlük komutların %70-80'i buluta hiç çıkmadan bitmeli.

```
mikrofon → AEC → VAD → wake word → STT (yerel Whisper)
                                       ↓
  [KATMAN 1] Gramer/regex          → doğrudan icra, LLM yok, ~200ms
             "sesi kıs", "saat kaç", "ekranı kilitle"
                                       ↓ eşleşmedi
  [KATMAN 2] Embedding niyet eşleme → şablon + slot doldurma, LLM yok
             yerel multilingual encoder (~100MB, CPU), parafraz toleranslı
                                       ↓ güven düşük
  [KATMAN 3] Küçük yerel model      → SADECE niyet sınıflandırma + slot
             3B Q4 (~2 GB VRAM)        çıkarımı. Beyin DEĞİL.
                                       ↓ açık uçlu iş
  [KATMAN 4] Bulut LLM              → muhakeme, kod yazma, çok adımlı görev
```

Faydası maliyetten ibaret değil: deterministik yol ~200ms (bulut turu ~1.5s) ve
internet kesildiğinde Katman 1-3 çalışmaya devam eder.

## Bellek bütçesi (16 GB / 6 GB VRAM)

| | Yer | Boyut |
|---|---|---|
| Whisper small int8 | VRAM | ~1 GB |
| Katman 3 yerel model (3B Q4) | VRAM | ~2 GB |
| **VRAM toplam** | | **~3 / 6 GB** |
| Piper TTS | RAM | ~200 MB |
| Orkestratör + ses hattı | RAM | ~800 MB |
| **Jarvis RAM ayak izi** | | **~1 GB** |

### 16 GB için bağlayıcı kurallar

1. **Gömülü hafıza katmanı, sunucu değil.** Qdrant/Postgres/Redis ayrı süreç YOK — SQLite + `sqlite-vec`.
2. **Tek süreç orkestratör.** Her Python süreci ~200-300 MB taban maliyet. Mikroservis sprawl yok; asyncio/thread.
3. **Model çıkarımı GPU'da.** CPU inference sistem RAM'ini yer.
4. **Docker Desktop yok.** Gerekirse native podman/docker.
5. **Lazy load + idle unload.** Kullanılmayan model VRAM'den düşer.
6. **Python'ı Arch'a bırakma.** `uv` ile pinlenmiş Python — rolling release'in venv'leri kırmasını engeller.

## Fazlar

- [ ] **Faz 0 — Donanım doğrulama** ← ŞU AN BURADAYIZ
  - [ ] Envanter raporu (kernel, CPU, RAM, GPU, oturum tipi)
  - [ ] `arecord -l` / `wpctl status` — mikrofon dizisi görünüyor mu
  - [ ] SOF firmware kernel mesajları temiz mi
  - [ ] **Mikrofon kayıt kalite testi** ← projenin gerçek risk kapısı
  - [ ] AEC testi (hoparlör çalarken eşzamanlı kayıt)
  - [ ] `nvidia-smi`, `sensors`, `msi-ec` fan kontrolü
  - [ ] BIOS: VT-x/VT-d, güç/uyku politikası (AC'de uyuma yok, kapak kapalı çalışsın)
  - [ ] BTRFS snapshot yapılandırması doğrula
- [ ] **Faz 1 — Temel ortam**: uv + pinlenmiş Python, CUDA + cuDNN, git, proje iskeleti
- [ ] **Faz 2 — Kulak**: PipeWire ses grafiği, AEC, Silero VAD, openWakeWord, faster-whisper + Türkçe doğruluk ölçümü
- [ ] **Faz 3 — Ağız**: Piper streaming TTS, barge-in (Jarvis konuşurken sözünü kesebilme)
- [ ] **Faz 4 — Yönlendirici**: Katman 1-2-3, komut kataloğu, slot doldurma
- [ ] **Faz 5 — Beyin**: bulut LLM tool-calling döngüsü, kod çalıştırma sandbox'ı, MCP, SQLite hafıza. **Masaüstü otomasyon ihtiyacı burada netleşir → X11/Wayland kararı burada verilir.**
- [ ] **Faz 6 — Uzaktan dispatch**: Tailscale (port forward YOK), FastAPI + token auth, iOS Shortcuts + Siri, ntfy push
- [ ] **Faz 7 — Servisleştirme + sertleştirme**: systemd servis, crash recovery, log/observability, yetki allowlist, denetim logu

## Güvenlik notları (mimariye bağlayıcı)

- Sistem hem **kod çalıştırabiliyor** hem **uzaktan erişilebilir** olacak. Bu kombinasyon Faz 7'yi opsiyonel değil zorunlu yapıyor.
- `ydotool`/`xdotool` sistem geneli sentetik girdi üretir. iPhone'dan gelen bir komut laptopta rastgele tuş basabilir hale gelir. Masaüstü kontrol araçları **en dar yetkiyle ve açık onayla** çalışacak.
- İnternete açık uç YOK. Uzaktan erişim yalnızca Tailscale mesh üzerinden.
- Rolling release: kritik güncelleme öncesi snapshot; ses yığını kırılırsa snapshot'tan dön.

## Açık sorular

- Mikrofon dizisi Linux'ta far-field wake word için yeterli kalitede mi? (Faz 0)
- Türkçe Whisper `small` doğruluğu yeterli mi, `medium` gerekli mi? (Faz 2)
- Piper Türkçe ses kalitesi günlük kullanımda kabul edilebilir mi? (Faz 3)
- Jarvis ne kadar GUI otomasyonu yapacak → X11 mi Wayland mi? (Faz 5)
