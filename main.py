"""Icon Shaper — меняет форму иконок установленных приложений (Kivy, Android)."""
import os
import threading

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics.texture import Texture
from kivy.lang import Builder
from kivy.properties import NumericProperty, ObjectProperty, StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from PIL import Image

import android_apps
import shapes

PREVIEW = 144   # размер превью в сетке, px
EXPORT = 256    # размер иконки ярлыка, px

KV = """
<AppTile>:
    orientation: 'vertical'
    padding: dp(4)
    spacing: dp(2)
    Image:
        texture: root.texture
        size_hint_y: None
        height: dp(60)
        allow_stretch: True
    Label:
        text: root.text
        font_size: '11sp'
        text_size: self.width, None
        halign: 'center'
        valign: 'top'
        shorten: True
        shorten_from: 'right'
        max_lines: 2

BoxLayout:
    orientation: 'vertical'
    padding: dp(8)
    spacing: dp(6)

    TextInput:
        id: search
        hint_text: 'Поиск приложения'
        multiline: False
        size_hint_y: None
        height: dp(44)
        on_text: app.refresh()

    BoxLayout:
        size_hint_y: None
        height: dp(44)
        spacing: dp(6)
        Spinner:
            id: shape
            text: app.shape_names[0]
            values: app.shape_names
            on_text: app.refresh()
        Spinner:
            id: bg
            text: app.bg_names[0]
            values: app.bg_names
            on_text: app.refresh()

    BoxLayout:
        size_hint_y: None
        height: dp(36)
        spacing: dp(6)
        Label:
            text: 'Масштаб'
            size_hint_x: None
            width: dp(80)
        Slider:
            id: scale
            min: 0.6
            max: 1.3
            value: 1.0
            step: 0.05
            on_value: app.refresh_later()

    RecycleView:
        id: rv
        viewclass: 'AppTile'
        bar_width: dp(4)
        RecycleGridLayout:
            cols: 4
            default_size: None, dp(100)
            default_size_hint: 1, None
            size_hint_y: None
            height: self.minimum_height

    Label:
        id: status
        text: app.status
        size_hint_y: None
        height: dp(40)
        font_size: '12sp'
        text_size: self.width, None
        halign: 'center'
"""


class AppTile(ButtonBehavior, BoxLayout):
    texture = ObjectProperty(None, allownone=True)
    text = StringProperty("")
    package = StringProperty("")

    def on_release(self):
        App.get_running_app().pin(self.package, self.text)


def to_texture(img):
    tex = Texture.create(size=img.size, colorfmt="rgba")
    tex.blit_buffer(img.tobytes(), colorfmt="rgba", bufferfmt="ubyte")
    tex.flip_vertical()
    return tex


class IconShaperApp(App):
    status = StringProperty("Загрузка приложений…")
    shape_names = [shapes.SHAPES[k] for k in shapes.SHAPES]
    bg_names = [shapes.BACKGROUNDS[k] for k in shapes.BACKGROUNDS]

    def build(self):
        self.title = "Icon Shaper"
        self.apps = []          # [{'label','package','img'(PIL)}]
        self._later = None
        self.root_widget = Builder.load_string(KV)
        return self.root_widget

    # ---- текущие настройки ----
    def _key(self, names, table, text):
        return list(table)[names.index(text)]

    def _settings(self):
        ids = self.root_widget.ids
        return (self._key(self.shape_names, shapes.SHAPES, ids.shape.text),
                self._key(self.bg_names, shapes.BACKGROUNDS, ids.bg.text),
                round(ids.scale.value, 2))

    # ---- загрузка ----
    def on_start(self):
        cache = os.path.join(self.user_data_dir, "icons")
        threading.Thread(target=self._load, args=(cache,), daemon=True).start()

    def _load(self, cache):
        try:
            apps = android_apps.load_apps(cache)
            for a in apps:
                a["img"] = Image.open(a["icon_path"]).convert("RGBA")
        except Exception as e:
            Clock.schedule_once(lambda dt: setattr(self, "status", f"Ошибка загрузки: {e}"))
            return
        Clock.schedule_once(lambda dt: self._loaded(apps))

    def _loaded(self, apps):
        self.apps = apps
        self.status = "Нажмите на иконку, чтобы создать ярлык с новой формой"
        self.refresh()

    # ---- перерисовка ----
    def refresh_later(self):
        if self._later:
            self._later.cancel()
        self._later = Clock.schedule_once(lambda dt: self.refresh(), 0.25)

    def refresh(self, *_):
        if not self.apps:
            return
        shape, bg, scale = self._settings()
        q = self.root_widget.ids.search.text.strip().lower()
        data = []
        for a in self.apps:
            if q and q not in a["label"].lower():
                continue
            out = shapes.apply_shape(a["img"], shape, size=PREVIEW, scale=scale, bg=bg)
            data.append({"text": a["label"], "package": a["package"], "texture": to_texture(out)})
        self.root_widget.ids.rv.data = data

    # ---- ярлык ----
    def pin(self, package, label):
        entry = next((a for a in self.apps if a["package"] == package), None)
        if not entry:
            return
        shape, bg, scale = self._settings()
        out = shapes.apply_shape(entry["img"], shape, size=EXPORT, scale=scale, bg=bg)
        path = os.path.join(self.user_data_dir, f"shaped_{package}.png")
        out.save(path)
        try:
            ok, msg = android_apps.pin_shortcut(package, label, path)
        except Exception as e:
            ok, msg = False, f"Ошибка: {e}"
        self.status = f"{label}: {msg}"


if __name__ == "__main__":
    Window.clearcolor = (0.08, 0.08, 0.1, 1)
    IconShaperApp().run()
