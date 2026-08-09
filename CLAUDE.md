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
| Oturum tipi | **Wayland'da kalınıyor** (Faz 5'te karar verildi) | KDE X11'i bakım moduna aldı, Plasma 7'de düşecek. Faz 5'in kod çalıştırma sandbox'ı headless (bwrap, GUI'ye dokunmuyor) — masaüstü otomasyonu ihtiyacı somutlaşmadı. Gerekirse `ydotool`/KWin D-Bus ile Wayland'da da GUI kontrolü mümkün |
| Beyin katmanı | **Katmanlı yönlendirici, LLM son çare** | maliyet + gecikme + çevrimdışı dayanıklılık |
| TTS | **Piper (yerel, offline, ücretsiz)** | çevrimdışı ve bedava; streaming arayüz arkasına soyutlanacak ki motor sonradan değişebilsin |
| STT | faster-whisper `medium` int8, GPU'da | Faz 2'de ölçüldü: `small` rahat/kısık konuşmada kelime kaçırıyor (örn. "hava"), `medium` aynı sesi doğru çözüyor. ~1.5-2GB VRAM, Katman 3 (~2GB) ile toplam 6GB bütçenin altında |
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
| Whisper medium int8 | VRAM | ~1.5-2 GB (small yerine medium'a geçildi, Faz 2) |
| Katman 3 yerel model (3B Q4, dosya 2.1 GB) | VRAM | ~2-2.5 GB |
| **VRAM toplam (aynı anda yüklüyse)** | | **~4 / 6 GB** — lazy load + idle unload kuralı önemli, ikisi sürekli birlikte yüklü kalmamalı |
| Katman 2 embedding modeli (`paraphrase-multilingual-MiniLM-L12-v2`) | RAM (CPU) | ~458 MB (plandaki ~100MB tahmininden büyük çıktı, Faz 4) |
| Piper TTS | RAM | ~200 MB |
| Orkestratör + ses hattı | RAM | ~800 MB |
| **Jarvis RAM ayak izi** | | **~1.5 GB** |

### 16 GB için bağlayıcı kurallar

1. **Gömülü hafıza katmanı, sunucu değil.** Qdrant/Postgres/Redis ayrı süreç YOK — SQLite + `sqlite-vec`.
2. **Tek süreç orkestratör.** Her Python süreci ~200-300 MB taban maliyet. Mikroservis sprawl yok; asyncio/thread.
3. **Model çıkarımı GPU'da.** CPU inference sistem RAM'ini yer.
4. **Docker Desktop yok.** Gerekirse native podman/docker.
5. **Lazy load + idle unload.** Kullanılmayan model VRAM'den düşer.
6. **Python'ı Arch'a bırakma.** `uv` ile pinlenmiş Python — rolling release'in venv'leri kırmasını engeller.

## Fazlar

- [x] **Faz 0 — Donanım doğrulama**
  - [x] Envanter raporu (kernel, CPU, RAM, GPU, oturum tipi)
  - [x] `arecord -l` / `wpctl status` — mikrofon dizisi görünüyor mu
  - [x] SOF firmware kernel mesajları temiz mi
  - [x] **Mikrofon kayıt kalite testi** — `Dmic0` %100 kazanç kırpıyordu, %50'ye (35) düşürüldü + `alsactl store` ile kalıcı yapıldı (reboot sonrası bir kez sıfırlanmıştı, tekrar uygulandı)
  - [x] AEC testi (hoparlör çalarken eşzamanlı kayıt) — akustik sızıntı var, beklenen (module-echo-cancel Faz 2'de kuruldu)
  - [x] `nvidia-smi`, `sensors`, `msi-ec` fan kontrolü — `msi-ec` EC firmware'i desteklemiyor, `msi_wmi_platform` salt-okunur çalışıyor (Faz 7'ye ertelendi)
  - [x] BIOS: VT-x/VT-d, güç/uyku politikası (AC'de uyuma yok, kapak kapalı çalışsın) — VT-x aktif, VT-d proje için gerekmiyor, lid policy `10-jarvis-lid.conf` aktif
  - [x] BTRFS snapshot yapılandırması doğrula — snapper `root` + timeline/cleanup timer aktif
- [x] **Faz 1 — Temel ortam**: uv + pinlenmiş Python 3.12, CUDA 13.3 + cuDNN 9.25, git, proje iskeleti
- [x] **Faz 2 — Kulak**: PipeWire echo-cancel modülü (`jarvis_echo_cancel_source/sink`), Silero VAD, openWakeWord (bundled `hey_jarvis_v0.1` modeli hazır), faster-whisper `medium` GPU'da doğrulandı — `ctranslate2` CUDA 12 ABI istiyor, sistem CUDA 13 ile çakışıyor: `nvidia-cublas-cu12`/`nvidia-cudnn-cu12` proje bağımlılığı olarak eklendi, çalıştırırken `LD_LIBRARY_PATH` bu paketlerin `lib/` dizinlerini göstermeli
- [x] **Faz 3 — Ağız**: Piper `tr_TR-dfki-medium` sesi, `src/jarvis/tts.py` — sentence-chunk streaming (`PiperVoice.synthesize()` iterator → `pw-cat --raw` stdin), barge-in (paralel thread'de `pw-record` + Silero VAD, konuşma algılanınca playback subprocess'i `terminate()`) — ikisi de canlı testte doğrulandı
- [x] **Faz 4 — Yönlendirici**: `src/jarvis/catalog.py` (komut kataloğu: 7 örnek niyet, regex + örnek ifadeler + slotlar), `src/jarvis/router.py` (Katman 1 regex → Katman 2 embedding → Katman 3 yerel LLM zinciri), `src/jarvis/layer3.py` (Qwen2.5-3B-Instruct Q4_K_M, GPU tam offload, JSON-schema ile kısıtlanmış çıktı — "beyin değil" sınırı kod seviyesinde uygulanıyor). Üçü de canlı test edildi ve çalışıyor: Katman 1 tam eşleşmede (`saat kaç` → conf 1.0), Katman 2 parafrazda güçlü (`şu an saati söyler misin` → conf 0.96, `...kilitler misin acaba` → conf 0.85, eşik 0.72). **Dürüst not:** Katman 3'ün Türkçe konuşma dili/saat ifadelerinde güvenilirliği düşük — net cümlelerde (`alarm kur saat 07:30`) doğru çalışıyor, ama "yedi otuzda" gibi günlük ifadeleri yanlış saatle (17:30) eşleştirdi ve bazı net niyetleri (`Ankara'da hava durumu ne alemde`) "belirsiz" işaretledi. Bu, projenin kendi tasarımıyla tutarlı (3B küçük model, "SADECE niyet sınıflandırma... Beyin DEĞİL") — zor/belirsiz durumlar Faz 5'teki bulut LLM'e (Katman 4) düşecek. Embedding modeli plandaki "~100MB" tahmininden büyük çıktı: `paraphrase-multilingual-MiniLM-L12-v2` gerçekte ~458MB (CPU'da çalışıyor, VRAM bütçesini etkilemiyor).
- [x] **Faz 5 — Beyin** (MCP kasıtlı olarak ertelendi, ihtiyaç netleşince eklenecek — bloklayıcı değil):
  - [x] **Kod çalıştırma sandbox'ı** (`src/jarvis/sandbox.py`): `bwrap` ile izole — salt-okunur kök fs, ağ yok, ayrı çalışma dizini. Test edildi: ağ izolasyonu, yazma izolasyonu, workdir yazılabilirliği doğrulandı.
  - [x] **SQLite hafıza** (`src/jarvis/memory.py`): `sqlite-vec` ile gömülü vektör arama, Katman 2'nin embedding modeli paylaşılıyor (ekstra model yükü yok). Semantik geri çağırma test edildi (doğru hafıza en yakın sırada çıktı).
  - [x] **Bulut LLM tool-calling döngüsü** (`src/jarvis/brain.py`, `src/jarvis/tools.py`): sağlayıcı bağımsız — `JARVIS_LLM_PROVIDER` ortam değişkeni ile **DeepSeek** (`deepseek-v4-pro`, OpenAI-uyumlu API, varsayılan) veya **Claude** (`claude-opus-5`, Anthropic Tool Runner, adaptive thinking) arasında seçim. Gerekçe: kullanıcının mevcut DeepSeek kredisi önce tüketilecek, sonra tek satırla Claude'a geçilecek — TTS motoru gibi soyutlama arkasında. `run_sandboxed_command`/`remember`/`recall` araçları her iki sağlayıcıya da bağlı. **Canlı test edildi (DeepSeek)**: hem sandbox komutu hem hafıza yazma gerçekten çalıştı ve kalıcı oldu (recall ile doğrulandı). API anahtarları `~/jarvis/.env`'de (gitignore'da).
  - [ ] MCP — somut bir üçüncü taraf entegrasyon ihtiyacı (takvim, ev otomasyonu vb.) netleşene kadar ertelendi, gerekmeden eklenmedi
  - [x] X11/Wayland kararı: **Wayland'da kalınıyor** (yukarıdaki karar tablosuna bak)
- [~] **Faz 6 — Uzaktan dispatch** ← ŞU AN BURADAYIZ (kısmen tamamlandı, kullanıcı tarafı adımlar bekleniyor):
  - [x] **FastAPI + token auth** (`src/jarvis/api.py`): `POST /command` — token doğrulama (`JARVIS_API_TOKEN`, `.env`'de), metni Katman 1-3 yönlendiricisine sokuyor, eşleşmezse Katman 4'e (bulut LLM) düşüyor. Canlı test edildi: yanlış token 401, `saat kaç` katman 1'de doğru eşleşti, açık uçlu bir kod yazma isteği katman 4'e düşüp sandbox'ta gerçekten çalıştı.
  - [x] **ntfy push** (`src/jarvis/notify.py`): her komut yanıtı `ntfy.sh` üzerinden push bildirimi olarak da gidiyor. Rastgele/tahmin edilemez konu adı (`JARVIS_NTFY_TOPIC`, `.env`'de) güvenlik sınırı — ntfy.sh herkese açık, konuyu bilmeyen okuyamaz. Canlı test edildi (gönderim başarılı).
  - [x] **Tailscale** — kuruldu, hesap oluşturuldu/giriş yapıldı, cihaz yetkilendirildi. Tailscale IP: `100.100.59.67`. Not: `systemd-resolved` + `NetworkManager` yanlış bağlı, MagicDNS muhtemelen çalışmıyor (IP ile erişim sorunsuz, hostname ile denenmedi) — Faz 7'de gerekirse düzeltilir.
  - [x] **API sunucusu systemd user servisi olarak çalışıyor** (`~/.config/systemd/user/jarvis-api.service`, `systemctl --user enable --now jarvis-api`), sadece Tailscale arayüzüne bind (`100.100.59.67:8765`), `.env`'den `EnvironmentFile` ile okunuyor. Manuel terminalden `uv run uvicorn` başlatmayı defalarca denedik, kullanıcının terminali tekrarlayan şekilde "resetlendi" (kök neden bulunamadı) — systemd servisi bu sorunu tamamen atladı, ayrıca kalıcılık/otomatik yeniden başlatma da bedava geldi (Faz 7'nin bir parçası erkenden bitti). Uçtan uca test edildi: Tailscale IP üzerinden `/health` ve `/command` (katman 1 eşleşmesi) çalışıyor.
  - [ ] **iOS Shortcuts + Siri** — telefon tarafında manuel kurulum: Kısayollar uygulamasında "Get Contents of URL" eylemi, POST, URL `http://100.100.59.67:8765/command`, header `Authorization: Bearer <JARVIS_API_TOKEN, .env'de>`, body `{"text": "[Konuşulan Metin]"}` (Dictate Text eylemiyle birleştirilip Siri'ye "Jarvis'e sor" gibi bir isimle atanabilir). Tailscale telefonda da kurulu ve aynı mesh'te olmalı.
- [ ] **Faz 7 — Servisleştirme + sertleştirme**: systemd servis, crash recovery, log/observability, yetki allowlist, denetim logu

## Güvenlik notları (mimariye bağlayıcı)

- Sistem hem **kod çalıştırabiliyor** hem **uzaktan erişilebilir** olacak. Bu kombinasyon Faz 7'yi opsiyonel değil zorunlu yapıyor.
- `ydotool`/`xdotool` sistem geneli sentetik girdi üretir. iPhone'dan gelen bir komut laptopta rastgele tuş basabilir hale gelir. Masaüstü kontrol araçları **en dar yetkiyle ve açık onayla** çalışacak.
- İnternete açık uç YOK. Uzaktan erişim yalnızca Tailscale mesh üzerinden.
- Rolling release: kritik güncelleme öncesi snapshot; ses yığını kırılırsa snapshot'tan dön.

## Açık sorular

- Mikrofon dizisi Linux'ta far-field wake word için yeterli kalitede mi? (Faz 0)
- ~~Türkçe Whisper `small` doğruluğu yeterli mi, `medium` gerekli mi?~~ → `medium` gerekli, karar verildi (Faz 2)
- Piper Türkçe ses kalitesi günlük kullanımda kabul edilebilir mi? (Faz 3)
- Jarvis ne kadar GUI otomasyonu yapacak → X11 mi Wayland mi? (Faz 5)
