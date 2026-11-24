import os
import pytest
from PySide6.QtGui import QImage, QColor
from PySide6.QtWidgets import QApplication

from src.ui.tabs.image_search_tab import ImageSearchTab

pytestmark = pytest.mark.usefixtures("qapp")


def test_image_search_tab_populates_monitors(qtbot):
    """Verify ImageSearchTab populates monitor selector with at least All Monitors."""
    tab = ImageSearchTab()
    qtbot.addWidget(tab)

    assert tab.combo_monitor.count() >= 1
    assert "All Monitors" in tab.combo_monitor.itemText(0)


def test_image_search_tab_paste_from_clipboard(qtbot, tmp_path, monkeypatch):
    """Verify pasting an image from clipboard saves it and populates the preview & path."""
    monkeypatch.setattr("src.screen_utils.get_snips_dir", lambda: str(tmp_path))

    tab = ImageSearchTab()
    qtbot.addWidget(tab)

    # Put a valid 32x24 test image onto the system clipboard
    img = QImage(32, 24, QImage.Format_RGB32)
    img.fill(QColor("#3B82F6"))
    QApplication.clipboard().setImage(img)

    pasted = tab.paste_from_clipboard()
    assert pasted is True

    saved_path = tab.line_img_path.text()
    assert os.path.isfile(saved_path)
    assert "32 × 24 px" in tab.lbl_img_meta.text()
