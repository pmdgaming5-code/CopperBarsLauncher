# CopperBars Launcher 2.0

Açık kaynaklı, Windows odaklı ve sade bir Minecraft Java launcher.

## Neden CopperBars?

CopperBars yalnızca bir "Play" butonu değil. Kendi kullanım alanını oluşturan özellikler sunar:

- **Copper Profiles:** Her profilin ayrı Minecraft sürümü, oyun klasörü, RAM ve JVM ayarları vardır.
- **Java AutoPilot:** Java yolunu elle seçmek zorunlu değildir. Launcher uygun Java'yı bilgisayarda arar; uyumlu sürüm yoksa resmi Mojang Java runtime manifestlerinden gerekli runtime'ı otomatik indirip yönetir.
- **Copper Shield:** Başlatmadan önce client, Java sürümü, disk alanı ve indirilen dosyalar için doğrulama yapar.
- **Repair:** Eksik veya bozuk Minecraft dosyalarını SHA-1 ile yeniden doğrular/indirir.
- **Copper Boost:** Sistem RAM'ini okuyup makul bir oyun belleği önerir ve güvenli JVM ayarlarını uygular.
- **Modpack Import:** ZIP modpack'lerini profil klasörüne güvenli yol kontrolüyle aktarır.
- **Fancy UI:** Koyu Copper teması, hızlı araçlar, profil merkezli çalışma alanı ve canlı günlük paneli.
- **Microsoft device-code login:** Parola launcher'a girilmeden resmi cihaz kodu akışı kullanılır.

## Kurulum

Windows için önerilen yol GitHub Releases bölümündeki `CopperBarsLauncher-Setup-2.0.0.exe` kurulum paketidir.

Geliştirme için:

```powershell
python --version
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m compileall -q .
python launcher.py
```

Python 3.11 veya daha yenisi gerekir.

## Mimari

Launcher kodu `copperbars_launcher/` altında çekirdek, uyumluluk ve arayüz olarak ayrılmıştır. `launcher.py` yalnızca giriş noktası ve geriye dönük test/import uyumluluğu sağlar.

Açık kaynak launcher projelerindeki genel tasarım fikirlerinden esinlenmiştir; Legacy Launcher veya Prism Launcher kaynak kodu kopyalanmamıştır.

## Lisans

Bu proje repo'nun MIT lisansı altındadır. Minecraft yazılımı, Java runtime dağıtımları ve oyun varlıkları ilgili hak sahiplerine aittir; launcher resmi servislerden gerekli dosyaları indirir.
