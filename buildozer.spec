[app]
title = Icon Shaper
package.name = iconshaper
package.domain = org.iconshaper
source.dir = .
source.include_exts = py
version = 0.1
requirements = python3,kivy==2.3.0,pillow,pyjnius,android
orientation = portrait
fullscreen = 0

# QUERY_ALL_PACKAGES нужен, чтобы увидеть список установленных приложений (Android 11+)
android.permissions = QUERY_ALL_PACKAGES
android.api = 34
android.minapi = 26
android.archs = arm64-v8a
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
