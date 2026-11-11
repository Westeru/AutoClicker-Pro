import pytest
from unittest.mock import patch, MagicMock
from PySide6.QtCore import Qt

from src.ui.main_window import MainWindow

pytestmark = pytest.mark.usefixtures("qapp")

@patch('pynput.keyboard.GlobalHotKeys')
def test_main_window_lazy_tabs(mock_hotkeys, qtbot):
    """Verify that MainWindow does not instantiate heavy tabs at startup."""
    window = MainWindow()
    qtbot.addWidget(window)
    
    # At startup, only MainTab should be loaded
    assert window.tab_main is not None
    assert window._tab_vision is None
    assert window._tab_workflow is None
    assert window._tab_record is None
    assert window.content_stack.currentIndex() == 0

    # Switch to tab 1 (Vision) -> triggers lazy instantiation
    window.switch_tab(1)
    assert window._tab_vision is not None
    assert window.content_stack.currentIndex() == 1

    # Switch to tab 2 (Workflow) -> triggers lazy instantiation
    window.switch_tab(2)
    assert window._tab_workflow is not None
    assert window.content_stack.currentIndex() == 2

    # Switch to tab 3 (Record) -> triggers lazy instantiation
    window.switch_tab(3)
    assert window._tab_record is not None
    assert window.content_stack.currentIndex() == 3

@patch('pynput.keyboard.GlobalHotKeys')
def test_main_window_close_event_uninstantiated_tabs(mock_hotkeys, qtbot):
    """Verify closeEvent succeeds safely when secondary tabs were never opened."""
    window = MainWindow()
    qtbot.addWidget(window)
    
    # Close immediately without touching other tabs
    window.close()
