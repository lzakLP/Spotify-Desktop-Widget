"""
Widget flutuante para Spotify (Windows 10/11)

Instalação:
    pip install PySide6 winrt-runtime winrt-Windows.Media.Control ^
        winrt-Windows.Storage.Streams winrt-Windows.Foundation ^
        winrt-Windows.Foundation.Collections

Uso:
    python spotify_widget.py

Controles:
    - Arraste com o mouse para mover
    - Clique na barra de progresso para pular para um ponto da música
    - Botão direito: fixar no topo / sair
"""
import sys
import time
import asyncio
import threading

from PySide6.QtCore import Qt, Signal, QObject, QTimer, QRectF, QVariantAnimation
from PySide6.QtGui import (QPainter, QColor, QPixmap, QPainterPath, QImage,
                           QLinearGradient, QFont, QFontMetrics)
from PySide6.QtWidgets import (QApplication, QWidget, QLabel, QPushButton,
                               QVBoxLayout, QHBoxLayout, QMenu)

from winrt.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as MediaManager,
    GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlayStatus,
)
from winrt.windows.storage.streams import DataReader


# ----------------------------------------------------------------------------
# Backend: conversa com o Windows (roda em thread própria)
# ----------------------------------------------------------------------------
class MediaBackend(QObject):
    updated = Signal(dict)

    def __init__(self):
        super().__init__()
        self.loop = asyncio.new_event_loop()
        self.manager = None
        self._last_key = None
        self._thumb = None
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.create_task(self._poll())
        self.loop.run_forever()

    async def _session(self):
        if self.manager is None:
            self.manager = await MediaManager.request_async()
        for s in self.manager.get_sessions():
            if "spotify" in s.source_app_user_model_id.lower():
                return s
        return self.manager.get_current_session()

    async def _read_thumb(self, ref):
        if ref is None:
            return None
        try:
            stream = await ref.open_read_async()
            size = stream.size
            reader = DataReader(stream.get_input_stream_at(0))
            await reader.load_async(size)
            buf = bytearray(size)
            reader.read_bytes(buf)
            return bytes(buf)
        except Exception:
            return None

    async def _poll(self):
        while True:
            try:
                s = await self._session()
                if s is None:
                    self.updated.emit({"active": False})
                else:
                    props = await s.try_get_media_properties_async()
                    info = s.get_playback_info()
                    tl = s.get_timeline_properties()
                    key = (props.title, props.artist)
                    if key != self._last_key:
                        self._last_key = key
                        self._thumb = await self._read_thumb(props.thumbnail)
                    self.updated.emit({
                        "active": True,
                        "title": props.title or "Sem título",
                        "artist": props.artist or "",
                        "playing": info.playback_status == PlayStatus.PLAYING,
                        "pos": (tl.position - tl.start_time).total_seconds(),
                        "dur": (tl.end_time - tl.start_time).total_seconds(),
                        "thumb": self._thumb,
                    })
            except Exception as e:  # não derruba o widget
                print("poll error:", e)
            await asyncio.sleep(0.5)

    def command(self, name, *args):
        async def _do():
            s = await self._session()
            if s:
                await getattr(s, name)(*args)
        asyncio.run_coroutine_threadsafe(_do(), self.loop)

    def play_pause(self): self.command("try_toggle_play_pause_async")
    def next(self):       self.command("try_skip_next_async")
    def prev(self):       self.command("try_skip_previous_async")

    def seek(self, seconds):
        self.command("try_change_playback_position_async", int(seconds * 10_000_000))


# ----------------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------------
def rounded_pixmap(img: QImage, size: int, radius: int) -> QPixmap:
    pm = QPixmap.fromImage(img).scaled(size, size, Qt.KeepAspectRatioByExpanding,
                                       Qt.SmoothTransformation)
    out = QPixmap(size, size)
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, size, size), radius, radius)
    p.setClipPath(path)
    p.drawPixmap(0, 0, pm)
    p.end()
    return out


def colors_from(img: QImage):
    c = img.scaled(1, 1, Qt.IgnoreAspectRatio, Qt.SmoothTransformation).pixelColor(0, 0)
    h, s, v, _ = c.getHsv()
    h = max(h, 0)
    bg = QColor.fromHsv(h, min(255, int(s * 1.2) + 30), 95)
    accent = QColor.fromHsv(h, min(255, max(80, s)), 255)
    return bg, accent


class Progress(QWidget):
    clicked = Signal(float)

    def __init__(self):
        super().__init__()
        self.setFixedHeight(12)
        self.setCursor(Qt.PointingHandCursor)
        self.value = 0.0
        self.accent = QColor("#1ed760")

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        y = self.height() / 2 - 2
        track = QRectF(0, y, self.width(), 4)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 50))
        p.drawRoundedRect(track, 2, 2)
        p.setBrush(self.accent)
        p.drawRoundedRect(QRectF(0, y, self.width() * self.value, 4), 2, 2)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit(max(0.0, min(1.0, e.position().x() / self.width())))


class Player(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(390, 150)

        self.backend = MediaBackend()
        self.backend.updated.connect(self.on_update)

        self._bg = QColor(24, 24, 28)
        self._accent = QColor("#1ed760")
        self._pos = self._dur = 0.0
        self._playing = False
        self._stamp = time.monotonic()
        self._drag = None
        self._last_thumb = None

        self.anim = QVariantAnimation(self, duration=700)
        self.anim.valueChanged.connect(self._set_bg)

        self._build_ui()

        t = QTimer(self)
        t.timeout.connect(self.tick)
        t.start(200)

    # -- layout ---------------------------------------------------------
    def _build_ui(self):
        self.cover = QLabel()
        self.cover.setFixedSize(110, 110)
        self.cover.setPixmap(self._placeholder())

        self.title = QLabel("Nada tocando")
        self.title.setStyleSheet("color:white;")
        self.title.setFont(QFont("Segoe UI Semibold", 13))
        self.artist = QLabel("Abra o Spotify")
        self.artist.setStyleSheet("color:rgba(255,255,255,170);")
        self.artist.setFont(QFont("Segoe UI", 10))

        self.progress = Progress()
        self.progress.clicked.connect(lambda f: self.backend.seek(f * self._dur))
        self.t_cur = QLabel("0:00")
        self.t_end = QLabel("0:00")
        for l in (self.t_cur, self.t_end):
            l.setStyleSheet("color:rgba(255,255,255,130);")
            l.setFont(QFont("Segoe UI", 8))

        times = QHBoxLayout()
        times.addWidget(self.t_cur)
        times.addStretch()
        times.addWidget(self.t_end)

        self.btn_prev = self._btn("⏮", self.backend.prev)
        self.btn_play = self._btn("▶", self.backend.play_pause, big=True)
        self.btn_next = self._btn("⏭", self.backend.next)
        controls = QHBoxLayout()
        controls.setSpacing(10)
        controls.addStretch()
        for b in (self.btn_prev, self.btn_play, self.btn_next):
            controls.addWidget(b)
        controls.addStretch()

        right = QVBoxLayout()
        right.setSpacing(0)
        right.addWidget(self.title)
        right.addWidget(self.artist)
        right.addSpacing(4)
        right.addWidget(self.progress)
        right.addLayout(times)
        right.addLayout(controls)

        root = QHBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(16)
        root.addWidget(self.cover, 0, Qt.AlignTop)
        root.addLayout(right, 1)

    def _btn(self, text, slot, big=False):
        b = QPushButton(text)
        b.setCursor(Qt.PointingHandCursor)
        size = 38 if big else 30
        b.setFixedSize(size, size)
        b.clicked.connect(slot)
        radius = size // 2
        if big:
            style = (f"QPushButton{{background:white;color:#111;border:none;"
                     f"border-radius:{radius}px;font:14px 'Segoe UI Symbol';}}"
                     f"QPushButton:hover{{background:#e8e8e8;}}")
        else:
            style = (f"QPushButton{{background:transparent;color:white;border:none;"
                     f"border-radius:{radius}px;font:15px 'Segoe UI Symbol';}}"
                     f"QPushButton:hover{{background:rgba(255,255,255,45);}}")
        b.setStyleSheet(style)
        return b

    def _placeholder(self):
        img = QImage(110, 110, QImage.Format_ARGB32)
        img.fill(QColor(255, 255, 255, 25))
        return rounded_pixmap(img, 110, 14)

    # -- pintura --------------------------------------------------------
    def _set_bg(self, c):
        self._bg = c
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        g = QLinearGradient(0, 0, self.width(), self.height())
        g.setColorAt(0, self._bg.lighter(125))
        g.setColorAt(1, QColor(14, 14, 18))
        p.setBrush(g)
        p.setPen(QColor(255, 255, 255, 25))
        p.drawRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), 22, 22)

    # -- dados ----------------------------------------------------------
    def _elide(self, label, text):
        w = self.width() - 18 * 2 - 110 - 16
        label.setText(QFontMetrics(label.font()).elidedText(text, Qt.ElideRight, w))

    @staticmethod
    def _fmt(s):
        s = max(0, int(s))
        return f"{s // 60}:{s % 60:02d}"

    def on_update(self, d):
        if not d.get("active"):
            self._elide(self.title, "Nada tocando")
            self._elide(self.artist, "Abra o Spotify")
            self._playing = False
            self.btn_play.setText("▶")
            return

        self._elide(self.title, d["title"])
        self._elide(self.artist, d["artist"])
        self._pos, self._dur = d["pos"], d["dur"]
        self._playing = d["playing"]
        self._stamp = time.monotonic()
        self.btn_play.setText("⏸" if self._playing else "▶")

        if d["thumb"] and d["thumb"] != self._last_thumb:
            self._last_thumb = d["thumb"]
            img = QImage.fromData(d["thumb"])
            if not img.isNull():
                self.cover.setPixmap(rounded_pixmap(img, 110, 14))
                bg, accent = colors_from(img)
                self._accent = accent
                self.progress.accent = accent
                self.anim.stop()
                self.anim.setStartValue(self._bg)
                self.anim.setEndValue(bg)
                self.anim.start()

    def tick(self):
        pos = self._pos
        if self._playing:
            pos += time.monotonic() - self._stamp
        if self._dur > 0:
            pos = min(pos, self._dur)
            self.progress.value = pos / self._dur
        else:
            self.progress.value = 0
        self.progress.update()
        self.t_cur.setText(self._fmt(pos))
        self.t_end.setText(self._fmt(self._dur))

    # -- mover / menu ---------------------------------------------------
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None and e.buttons() & Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, _):
        self._drag = None

    def contextMenuEvent(self, e):
        m = QMenu(self)
        top = m.addAction("Sempre no topo")
        top.setCheckable(True)
        top.setChecked(bool(self.windowFlags() & Qt.WindowStaysOnTopHint))
        quit_ = m.addAction("Sair")
        act = m.exec(e.globalPos())
        if act == quit_:
            QApplication.quit()
        elif act == top:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, top.isChecked())
            self.show()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = Player()
    screen = app.primaryScreen().availableGeometry()
    w.move(screen.right() - w.width() - 24, screen.bottom() - w.height() - 24)
    w.show()
    sys.exit(app.exec())