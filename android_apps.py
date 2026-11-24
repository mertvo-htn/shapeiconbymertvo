"""Доступ к установленным приложениям Android (pyjnius) и закрепление ярлыков.

На ПК (не Android) вместо этого отдаются демо-иконки, чтобы можно было
разрабатывать интерфейс без телефона.
"""
import os
import time

from kivy.utils import platform

IS_ANDROID = platform == "android"


# ---------------------------------------------------------------- демо (ПК)
def _demo_apps(cache_dir, size):
    from PIL import Image, ImageDraw, ImageFont

    palette = [(229, 57, 53), (67, 160, 71), (30, 136, 229), (251, 140, 0),
               (142, 36, 170), (0, 172, 193), (255, 179, 0), (84, 110, 122),
               (216, 27, 96), (57, 73, 171), (0, 137, 123), (109, 76, 65)]
    names = ["Почта", "Карты", "Музыка", "Камера", "Заметки", "Погода",
             "Часы", "Файлы", "Видео", "Чат", "Магазин", "Браузер"]
    apps = []
    for i, (name, col) in enumerate(zip(names, palette)):
        img = Image.new("RGBA", (size, size), col + (255,))
        d = ImageDraw.Draw(img)
        d.ellipse((size * .25, size * .25, size * .75, size * .75), fill=(255, 255, 255, 230))
        d.text((size * .44, size * .42), name[0], fill=col, font=ImageFont.load_default(size // 5))
        path = os.path.join(cache_dir, f"demo{i}.png")
        img.save(path)
        apps.append({"label": name, "package": f"demo.app{i}", "icon_path": path})
    return apps


# ------------------------------------------------------------- Android
def _activity():
    from jnius import autoclass
    return autoclass("org.kivy.android.PythonActivity").mActivity


def _drawable_to_png(drawable, size, path):
    """Рисует Drawable в PNG. У adaptive-иконок рисуем слои без системной маски,
    чтобы потом наложить свою форму."""
    from jnius import autoclass, cast
    Bitmap = autoclass("android.graphics.Bitmap")
    Config = autoclass("android.graphics.Bitmap$Config")
    Fmt = autoclass("android.graphics.Bitmap$CompressFormat")
    Canvas = autoclass("android.graphics.Canvas")
    FileOutputStream = autoclass("java.io.FileOutputStream")

    bmp = Bitmap.createBitmap(size, size, Config.ARGB_8888)
    canvas = Canvas(bmp)
    cls = drawable.getClass().getName()
    if cls == "android.graphics.drawable.AdaptiveIconDrawable":
        ad = cast(cls, drawable)
        q = int(size * 0.25)  # слои 108dp, видимая часть 72dp -> запас 25% с каждой стороны
        for layer in (ad.getBackground(), ad.getForeground()):
            if layer is not None:
                layer.setBounds(-q, -q, size + q, size + q)
                layer.draw(canvas)
    else:
        drawable.setBounds(0, 0, size, size)
        drawable.draw(canvas)
    fos = FileOutputStream(path)
    bmp.compress(Fmt.PNG, 100, fos)
    fos.flush()
    fos.close()


def load_apps(cache_dir, size=192):
    """Список запускаемых приложений: [{'label','package','icon_path'}], по алфавиту."""
    os.makedirs(cache_dir, exist_ok=True)
    if not IS_ANDROID:
        return _demo_apps(cache_dir, size)

    from jnius import autoclass, detach
    Intent = autoclass("android.content.Intent")
    act = _activity()
    pm = act.getPackageManager()
    intent = Intent(Intent.ACTION_MAIN)
    intent.addCategory(Intent.CATEGORY_LAUNCHER)
    infos = pm.queryIntentActivities(intent, 0)

    own, seen, apps = act.getPackageName(), set(), []
    for i in range(infos.size()):
        ri = infos.get(i)
        pkg = ri.activityInfo.packageName
        if pkg == own or pkg in seen:
            continue
        seen.add(pkg)
        try:
            label = ri.loadLabel(pm).toString()
            path = os.path.join(cache_dir, f"{pkg}.png")
            _drawable_to_png(ri.loadIcon(pm), size, path)
            apps.append({"label": label, "package": pkg, "icon_path": path})
        except Exception as e:  # одна кривая иконка не должна ломать список
            print("icon failed", pkg, e)
    try:
        detach()
    except Exception:
        pass
    apps.sort(key=lambda a: a["label"].lower())
    return apps


def pin_shortcut(package, label, png_path):
    """Просит лаунчер закрепить на рабочем столе ярлык приложения с новой иконкой.
    Возвращает (ok, сообщение)."""
    if not IS_ANDROID:
        return False, f"Только на Android. PNG сохранён: {png_path}"

    from jnius import autoclass, cast
    Build = autoclass("android.os.Build$VERSION")
    if Build.SDK_INT < 26:
        return False, "Нужен Android 8.0 или новее"

    Context = autoclass("android.content.Context")
    Intent = autoclass("android.content.Intent")
    ShortcutInfo = autoclass("android.content.pm.ShortcutInfo")
    Builder = autoclass("android.content.pm.ShortcutInfo$Builder")
    Icon = autoclass("android.graphics.drawable.Icon")
    BitmapFactory = autoclass("android.graphics.BitmapFactory")

    act = _activity()
    sm = cast("android.content.pm.ShortcutManager", act.getSystemService(Context.SHORTCUT_SERVICE))
    if not sm.isRequestPinShortcutSupported():
        return False, "Лаунчер не поддерживает закрепление ярлыков"

    launch = act.getPackageManager().getLaunchIntentForPackage(package)
    if launch is None:
        return False, "У приложения нет экрана запуска"
    launch.setAction(Intent.ACTION_MAIN)

    bmp = BitmapFactory.decodeFile(png_path)
    sid = f"{package}-{int(time.time())}"
    info = (Builder(act, sid)
            .setShortLabel(label)
            .setLongLabel(label)
            .setIcon(Icon.createWithBitmap(bmp))
            .setIntent(launch)
            .build())
    sm.requestPinShortcut(info, None)
    return True, "Подтвердите добавление ярлыка в системном окне"
