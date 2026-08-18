# CopperBars Launcher

Windows için modern, açık kaynaklı Minecraft launcher.

## Özellikler

- Mojang sürüm manifestinden release/snapshot sürüm listesi.
- Minecraft client, library ve asset dosyalarını indirir.
- SHA-1 doğrulaması ile bozuk indirmeleri yeniden alır.
- Legacy/Offline profil desteği.
- Microsoft cihaz kodu ile oturum açma.
- Java algılama ve özel Java yolu.
- RAM, oyun klasörü ve çözünürlük ayarları.
- Minecraft JVM/game argümanlarını sürüm manifestinden oluşturur.
- Windows tek dosya EXE ve Inno Setup kurulum paketi.

## Derleme

Windows PowerShell:

```powershell
./build/build.ps1
```

Installer için Inno Setup 6 ile `installer/CopperBarsLauncher.iss` derlenir.

## Kimlik doğrulama

Microsoft oturumu OAuth cihaz kodu akışını kullanır. Kullanıcı tarayıcı üzerinden Microsoft hesabına giriş yapar; parola launcher tarafından istenmez. Microsoft cihaz kodu protokolü cihaz kodu, doğrulama URI'si, polling aralığı ve refresh token davranışını tanımlar.

Launcher ayrıca offline profil oluşturabilir. Offline profil, yalnızca offline kabul eden ortamlarda kullanılabilir; resmi çevrimiçi hizmetler için hesabın Minecraft sahibi olması gerekir. Launcher herhangi bir hesap doğrulamasını atlatmaz.

## Mimari not

Proje, açık kaynak launcher'larda kullanılan genel tasarım desenlerinden esinlenen özgün bir uygulamadır; Legacy Launcher veya Prism Launcher kaynak kodunun kopyası değildir.

## Lisans

Bu proje repo'nun MIT lisansı altında dağıtılır. Minecraft yazılımı ve varlıkları Mojang/Microsoft'a aittir; launcher bunları resmi servislerden indirir.
