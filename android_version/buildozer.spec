[app]
title = MoonTele
package.name = moontele
package.domain = org.moon
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,session
version = 0.1
requirements = python3,kivy==2.3.0,kivymd==1.2.0,telethon,pyaes,asyncio

orientation = portrait
osx.python_version = 3
osx.kivy_version = 1.9.1

fullscreen = 0
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,MANAGE_EXTERNAL_STORAGE

android.api = 33
android.minapi = 21
android.ndk = 25b
android.ndk_path = 
android.sdk_path = 
android.ant_path = 

android.skip_update = False
android.accept_sdk_license = True
android.enable_androidx = True

android.archs = arm64-v8a
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 1
