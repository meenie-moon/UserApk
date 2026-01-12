[app]
title = MoonTele Hybrid
package.name = moontelehybrid
package.domain = org.moon
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,session,html,css,js
source.include_patterns = templates/*
version = 0.1
requirements = python3,kivy==2.3.0,telethon,pyaes,asyncio,openssl,flask,jinja2,pyjnius

orientation = portrait
android.permissions = INTERNET,ACCESS_NETWORK_STATE

android.api = 33
android.minapi = 21
android.ndk = 25b
android.enable_androidx = True
android.archs = arm64-v8a

[buildozer]
log_level = 2
warn_on_root = 1
