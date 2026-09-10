from __future__ import annotations

import os
import platform
import shutil
import struct
import subprocess
import sys
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QGuiApplication,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)


def _draw_background_squircle(p: QPainter, size: int, scale: float) -> None:
    m, r = 48.0 * scale, 210.0 * scale
    bg_path = QPainterPath()
    bg_path.addRoundedRect(QRectF(m, m, size - 2 * m, size - 2 * m), r, r)
    g = QLinearGradient(0, m, 0, size - m)
    g.setColorAt(0.0, QColor("#1e293b"))
    g.setColorAt(1.0, QColor("#0f172a"))
    p.fillPath(bg_path, QBrush(g))
    p.strokePath(bg_path, QPen(QColor(255, 255, 255, 30), 4.0 * scale))


def _draw_inner_card(p: QPainter, scale: float) -> None:
    c_path = QPainterPath()
    c_path.addRoundedRect(QRectF(150.0 * scale, 160.0 * scale, 724.0 * scale, 704.0 * scale), 50.0 * scale, 50.0 * scale)
    cg = QLinearGradient(0, 160.0 * scale, 0, 864.0 * scale)
    cg.setColorAt(0.0, QColor("#2563eb"))
    cg.setColorAt(1.0, QColor("#1d4ed8"))
    p.fillPath(c_path, QBrush(cg))


def _draw_spreadsheet(p: QPainter, scale: float) -> None:
    s_path = QPainterPath()
    s_path.addRoundedRect(QRectF(190.0 * scale, 240.0 * scale, 644.0 * scale, 570.0 * scale), 35.0 * scale, 35.0 * scale)
    p.fillPath(s_path, QBrush(QColor("#ffffff")))

    h_path = QPainterPath()
    h_path.addRoundedRect(QRectF(190.0 * scale, 240.0 * scale, 644.0 * scale, 100.0 * scale), 35.0 * scale, 35.0 * scale)
    p.fillPath(h_path, QBrush(QColor("#0284c7")))

    for i, c in enumerate(["#10b981", "#3b82f6", "#f59e0b", "#6366f1"]):
        y = 380.0 * scale + i * 95.0 * scale
        cp = QPainterPath()
        cp.addRoundedRect(QRectF(230.0 * scale, y, 110.0 * scale, 28.0 * scale), 14.0 * scale, 14.0 * scale)
        p.fillPath(cp, QBrush(QColor(c)))
        p.setPen(QPen(QColor("#cbd5e1"), 10.0 * scale))
        p.drawLine(QPointF(370.0 * scale, y + 14.0 * scale), QPointF(770.0 * scale, y + 14.0 * scale))


def _draw_dollar_badge(p: QPainter, size: int, scale: float) -> None:
    bs = 280.0 * scale
    bx, by = size - bs - 70.0 * scale, size - bs - 70.0 * scale
    brect = QRectF(bx, by, bs, bs)
    bg2 = QLinearGradient(bx, by, bx, by + bs)
    bg2.setColorAt(0.0, QColor("#10b981"))
    bg2.setColorAt(1.0, QColor("#059669"))
    bp = QPainterPath()
    bp.addEllipse(brect)
    p.fillPath(bp, QBrush(bg2))

    p.setPen(QPen(QColor("#ffffff")))
    p.setFont(QFont("Arial", int(140.0 * scale), QFont.Weight.Bold))
    p.drawText(brect, Qt.AlignmentFlag.AlignCenter, "$")


def draw_master_icon(size: int = 1024) -> QImage:
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    scale = size / 1024.0

    _draw_background_squircle(p, size, scale)
    _draw_inner_card(p, scale)
    _draw_spreadsheet(p, scale)
    _draw_dollar_badge(p, size, scale)

    p.end()
    return img


def create_ico(pngs: list[tuple[int, bytes]], out: Path) -> None:
    header = struct.pack("<HHH", 0, 1, len(pngs))
    offset = 6 + 16 * len(pngs)
    dirs, blobs = bytearray(), bytearray()
    for w, b in pngs:
        wb = 0 if w >= 256 else w
        dirs.extend(struct.pack("<BBBBHHII", wb, wb, 0, 0, 1, 32, len(b), offset + len(blobs)))
        blobs.extend(b)
    out.write_bytes(header + dirs + blobs)


def create_icns(img: QImage, out: Path) -> None:
    d = out.parent / "icon.iconset"
    d.mkdir(parents=True, exist_ok=True)
    for fn, s in [
        ("icon_16x16.png", 16), ("icon_16x16@2x.png", 32),
        ("icon_32x32.png", 32), ("icon_32x32@2x.png", 64),
        ("icon_128x128.png", 128), ("icon_128x128@2x.png", 256),
        ("icon_256x256.png", 256), ("icon_256x256@2x.png", 512),
        ("icon_512x512.png", 512), ("icon_512x512@2x.png", 1024),
    ]:
        img.scaled(s, s, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation).save(str(d / fn), "PNG")

    if platform.system() == "Darwin" and shutil.which("iconutil"):
        subprocess.run(["iconutil", "-c", "icns", str(d), "-o", str(out)], check=True)
        shutil.rmtree(d, ignore_errors=True)
    else:
        img.save(str(out), "ICNS")


def main() -> int:
    _app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    pdir = Path(__file__).parent.resolve()
    adir = pdir.parent / "inventory_updater" / "src" / "inventory_updater" / "assets"
    adir.mkdir(parents=True, exist_ok=True)

    master = draw_master_icon(1024)
    master.save(str(pdir / "icon.png"), "PNG")
    master.scaled(256, 256, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation).save(str(adir / "icon.png"), "PNG")

    ico_list = []
    for s in [16, 24, 32, 48, 64, 128, 256]:
        tmp = pdir / f"tmp_{s}.png"
        master.scaled(s, s, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation).save(str(tmp), "PNG")
        ico_list.append((s, tmp.read_bytes()))
        tmp.unlink()

    create_ico(ico_list, pdir / "icon.ico")
    create_icns(master, pdir / "icon.icns")
    print("Icons generated successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
