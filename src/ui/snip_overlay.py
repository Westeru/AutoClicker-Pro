from typing import Optional
from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtGui import (
    QPixmap, QPainter, QColor, QPen, QFont, QImage, QGuiApplication
)
from PySide6.QtCore import Qt, QRect, QPoint, Signal


class SnipOverlay(QWidget):
    """
    Full virtual-desktop screen snipping overlay across all connected monitors.
    Click & drag to select a region; release to capture; press Esc or right-click to cancel.
    """
    snip_captured = Signal(QPixmap)
    snip_rect_captured = Signal(tuple)
    snip_cancelled = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setCursor(Qt.CrossCursor)

        self._origin: Optional[QPoint] = None
        self._current: Optional[QPoint] = None
        self._dragging = False
        self._virtual_rect = QRect()
        self._bg_pixmap = QPixmap()

    def start_snip(self) -> None:
        """Capture all monitors and display the full-desktop snipping overlay."""
        screens = QGuiApplication.screens()
        if not screens:
            self.snip_cancelled.emit()
            self.close()
            return

        # Compute union geometry across all monitors
        union_rect = screens[0].geometry()
        for scr in screens[1:]:
            union_rect = union_rect.united(scr.geometry())
        self._virtual_rect = union_rect

        # Grab full virtual desktop image
        self._bg_pixmap = self._grab_virtual_desktop(union_rect, screens)
        self.setGeometry(union_rect)
        self.show()
        self.raise_()
        self.activateWindow()

    @staticmethod
    def _grab_virtual_desktop(union_rect: QRect, screens) -> QPixmap:
        """Capture all monitors into a single QPixmap aligned to union_rect."""
        # Prefer PIL ImageGrab(all_screens=True) on Windows for exact multi-monitor capture
        try:
            from PIL import ImageGrab
            pil_img = ImageGrab.grab(all_screens=True).convert("RGBA")
            data = pil_img.tobytes("raw", "RGBA")
            qimg = QImage(
                data,
                pil_img.width,
                pil_img.height,
                pil_img.width * 4,
                QImage.Format_RGBA8888,
            ).copy()
            return QPixmap.fromImage(qimg)
        except Exception:
            pass

        # Fallback: stitch Qt screen grabs
        canvas = QPixmap(union_rect.size())
        canvas.fill(QColor("#0B0F17"))
        painter = QPainter(canvas)
        for scr in screens:
            g = scr.geometry()
            grab = scr.grabWindow(0)
            painter.drawPixmap(g.topLeft() - union_rect.topLeft(), grab)
        painter.end()
        return canvas

    def _selection_rect(self) -> QRect:
        if self._origin is None or self._current is None:
            return QRect()
        return QRect(self._origin, self._current).normalized()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw frozen desktop screenshot
        if not self._bg_pixmap.isNull():
            painter.drawPixmap(self.rect(), self._bg_pixmap)

        # Dim entire desktop
        painter.fillRect(self.rect(), QColor(11, 15, 23, 130))

        sel = self._selection_rect()
        if self._dragging and sel.width() > 2 and sel.height() > 2:
            # Reveal crisp original screenshot inside selection
            if not self._bg_pixmap.isNull():
                scale_x = self._bg_pixmap.width() / max(1, self.width())
                scale_y = self._bg_pixmap.height() / max(1, self.height())
                src_rect = QRect(
                    int(sel.x() * scale_x),
                    int(sel.y() * scale_y),
                    int(sel.width() * scale_x),
                    int(sel.height() * scale_y),
                )
                painter.drawPixmap(sel, self._bg_pixmap, src_rect)

            # Bright electric-blue selection border
            pen = QPen(QColor("#3B82F6"), 2)
            painter.setPen(pen)
            painter.drawRect(sel)

            # Live dimension pill
            dim_text = f" {sel.width()} × {sel.height()} px "
            font = QFont("Segoe UI", 10, QFont.Bold)
            painter.setFont(font)
            fm = painter.fontMetrics()
            tw = fm.horizontalAdvance(dim_text) + 10
            th = fm.height() + 6
            label_y = sel.top() - th - 6 if sel.top() - th - 6 > 4 else sel.bottom() + 6
            label_rect = QRect(sel.left(), label_y, tw, th)
            painter.fillRect(label_rect, QColor("#1E293B"))
            painter.setPen(QColor("#38BDF8"))
            painter.drawText(label_rect, Qt.AlignCenter, dim_text)
        else:
            # Subtle instruction banner at top-center of primary screen
            hint = "Drag to capture a screen region  •  Press Esc or Right-Click to cancel"
            font = QFont("Segoe UI", 11, QFont.Bold)
            painter.setFont(font)
            fm = painter.fontMetrics()
            tw = fm.horizontalAdvance(hint) + 28
            th = fm.height() + 14
            primary = QGuiApplication.primaryScreen()
            if primary:
                pg = primary.geometry()
                cx = (pg.x() - self._virtual_rect.x()) + pg.width() // 2
                cy = (pg.y() - self._virtual_rect.y()) + 36
            else:
                cx = self.width() // 2
                cy = 36
            banner = QRect(cx - tw // 2, cy, tw, th)
            painter.fillRect(banner, QColor(15, 23, 42, 225))
            painter.setPen(QPen(QColor("#3B82F6"), 1))
            painter.drawRoundedRect(banner, 8, 8)
            painter.setPen(QColor("#F8FAFC"))
            painter.drawText(banner, Qt.AlignCenter, hint)

        painter.end()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.RightButton:
            self.snip_cancelled.emit()
            self.close()
            return
        if event.button() == Qt.LeftButton:
            self._origin = event.position().toPoint()
            self._current = self._origin
            self._dragging = True
            self.update()

    def mouseMoveEvent(self, event) -> None:
        if self._dragging:
            self._current = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self._dragging:
            self._dragging = False
            self._current = event.position().toPoint()
            sel = self._selection_rect()
            if sel.width() >= 5 and sel.height() >= 5 and not self._bg_pixmap.isNull():
                scale_x = self._bg_pixmap.width() / max(1, self.width())
                scale_y = self._bg_pixmap.height() / max(1, self.height())
                src_rect = QRect(
                    int(sel.x() * scale_x),
                    int(sel.y() * scale_y),
                    int(sel.width() * scale_x),
                    int(sel.height() * scale_y),
                )
                cropped = self._bg_pixmap.copy(src_rect)
                QApplication.clipboard().setPixmap(cropped)
                abs_left = int(self._virtual_rect.x() * scale_x) + src_rect.x()
                abs_top = int(self._virtual_rect.y() * scale_y) + src_rect.y()
                abs_right = abs_left + src_rect.width()
                abs_bottom = abs_top + src_rect.height()
                self.snip_rect_captured.emit((abs_left, abs_top, abs_right, abs_bottom))
                self.snip_captured.emit(cropped)
            else:
                self.snip_cancelled.emit()
            self.close()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self.snip_cancelled.emit()
            self.close()
