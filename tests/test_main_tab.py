import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget
from unittest.mock import patch, MagicMock

from src.ui.tabs.main_tab import MainTab, ClickerThread

# Inform pytest to use a QApp for these tests
pytestmark = pytest.mark.usefixtures("qapp")

@pytest.fixture
def main_tab():
    tab = MainTab()
    return tab

def test_initialization(main_tab):
    """Test that all UI components initialize with default values."""
    assert main_tab.is_running is False
    assert main_tab.btn_start.text() == "Start (F6)"
    
    # Check default intervals (0h 0m 1s 0ms)
    assert main_tab.get_interval_seconds() == 1.0
    
    # Check default combo box states
    assert main_tab.combo_button.currentText() == "Left"
    assert main_tab.combo_type.currentText() == "Single"
    assert main_tab.input_kb_key.text() == ""
    
    # Check default keyboard mode
    assert main_tab.radio_press.isChecked() is True
    assert main_tab.radio_hold.isChecked() is False

def test_get_interval_seconds(main_tab):
    """Test the interval calculation logic from the spinboxes."""
    from PySide6.QtWidgets import QSpinBox
    # Set values in spinboxes
    main_tab.spin_hours.findChild(QSpinBox).setValue(1) # 1 hour
    main_tab.spin_mins.findChild(QSpinBox).setValue(30)  # 30 mins
    main_tab.spin_secs.findChild(QSpinBox).setValue(15)  # 15 secs
    main_tab.spin_ms.findChild(QSpinBox).setValue(500)     # 500 ms
    
    expected_seconds = (1 * 3600) + (30 * 60) + 15 + 0.5
    assert main_tab.get_interval_seconds() == expected_seconds

@patch('src.ui.tabs.main_tab.Clicker')
@patch('src.ui.tabs.main_tab.ClickerThread')
def test_start_clicking(mock_thread_class, mock_clicker_class, main_tab, qtbot):
    """Test the start clicking flow sets up the backend and updates UI."""
    # Setup mock thread
    mock_thread_instance = MagicMock()
    mock_thread_class.return_value = mock_thread_instance
    
    # Click start button
    qtbot.mouseClick(main_tab.btn_start, Qt.LeftButton)
    
    # Verify State changed
    assert main_tab.is_running is True
    assert main_tab.btn_start.text() == "Stop (F6)"
    assert main_tab.btn_start.objectName() == "DangerButton"
    
    # Verify inputs are disabled
    assert main_tab.spin_hours.isEnabled() is False
    assert main_tab.combo_button.isEnabled() is False
    
    # Verify backend was created and thread started
    mock_clicker_class.assert_called_once_with(main_tab.stop_event)
    mock_thread_class.assert_called_once()
    mock_thread_instance.start.assert_called_once()

@patch('src.ui.tabs.main_tab.Clicker')
@patch('src.ui.tabs.main_tab.ClickerThread')
def test_stop_clicking(mock_thread_class, mock_clicker_class, main_tab, qtbot):
    """Test the stop clicking flow sets the stop event and updates UI."""
    # Start it first
    qtbot.mouseClick(main_tab.btn_start, Qt.LeftButton)
    assert main_tab.is_running is True
    
    # Click it again to stop
    qtbot.mouseClick(main_tab.btn_start, Qt.LeftButton)
    
    # Verify stop event was set
    assert main_tab.stop_event.is_set() is True
    
    # Wait for the emitted signal to process (simulated)
    # The actual UI update happens via the status_changed signal, so we trigger that block manually
    # or rely on qtbot waiting. Since our mocked thread didn't exit normally, we just ensure 
    # the method fires appropriately
    assert main_tab.is_running is False
    assert main_tab.btn_start.text() == "Start (F6)"
    assert main_tab.spin_hours.isEnabled() is True
