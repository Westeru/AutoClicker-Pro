import pytest
from unittest.mock import MagicMock, patch
import threading
import time

# We patch pynput inside the test to prevent it from actually listening or moving the mouse during tests.
from src.clicker import Clicker
from pynput.mouse import Button

@pytest.fixture
def mock_mouse_controller():
    with patch('src.clicker.MouseController') as mock:
        yield mock

@pytest.fixture
def mock_keyboard_controller():
    with patch('src.clicker.KeyboardController') as mock:
        yield mock

@pytest.fixture
def clicker_instance(mock_mouse_controller, mock_keyboard_controller):
    stop_event = threading.Event()
    return Clicker(stop_event)

def test_initialization(clicker_instance, mock_mouse_controller, mock_keyboard_controller):
    """Test that Clicker initializes correctly and creates the controllers."""
    assert isinstance(clicker_instance.stop_event, threading.Event)
    assert not clicker_instance.stop_event.is_set()
    mock_mouse_controller.assert_called_once()
    mock_keyboard_controller.assert_called_once()

def test_start_stop_state_toggling(clicker_instance, mock_mouse_controller):
    """Test that the loop exits immediately if the stop_event is set."""
    # Set the stop event before running to ensure it never enters the loop
    clicker_instance.stop_event.set()
    config = {'interval': 1.0, 'action_type': 'mouse', 'mouse_btn': 'left', 'click_type': 'single'}
    
    # The run method should return immediately without executing clicks
    clicker_instance.run(config)
    clicker_instance.mouse.click.assert_not_called()

def test_interval_calculations(clicker_instance):
    """Test that the run loop respecs the interval and sleeps appropriately."""
    config = {'interval': 0.1, 'action_type': 'mouse', 'mouse_btn': 'left', 'click_type': 'single'}
    
    # We want it to execute exactly one click, then stop during the sleep loop.
    # To do this without waiting real time, we mock time.sleep so it sets the stop_event.
    original_sleep = time.sleep
    def mock_sleep(duration):
        clicker_instance.stop_event.set()
        # Sleep a tiny amount so time advances a little, but tests run fast
        original_sleep(0.001)

    with patch('time.sleep', side_effect=mock_sleep):
        clicker_instance.run(config)
        
    # It should have performed one click before sleeping
    clicker_instance.mouse.click.assert_called_once_with(Button.left, 1)

def test_invalid_click_type(clicker_instance):
    """Test how clicker handles an invalid click_type like 'triple'."""
    # Clicker defaults to count=1 for anything that isn't 'double'
    config = {'interval': 0.01, 'action_type': 'mouse', 'mouse_btn': 'right', 'click_type': 'triple'}
    
    def set_stop(*args, **kwargs):
        clicker_instance.stop_event.set()
        
    clicker_instance.mouse.click.side_effect = set_stop
    
    clicker_instance.run(config)
    clicker_instance.mouse.click.assert_called_once_with(Button.right, 1)

def test_invalid_action_type(clicker_instance):
    """Test what happens if an invalid action_type is passed."""
    # Should ignore unknown action types and just sleep
    config = {'interval': 0.01, 'action_type': 'telepathy'}
    
    def mock_sleep(duration):
        clicker_instance.stop_event.set()
        
    with patch('time.sleep', side_effect=mock_sleep):
        clicker_instance.run(config)
        
    # Neither mouse nor keyboard should have been triggered
    clicker_instance.mouse.click.assert_not_called()
    clicker_instance.keyboard.press.assert_not_called()

def test_invalid_mouse_btn(clicker_instance):
    """Test what happens if an invalid mouse_btn is passed (gracefully skips)."""
    # 'nonexistent' does not exist on pynput.mouse.Button, should be skipped.
    config = {'interval': 0.01, 'action_type': 'mouse', 'mouse_btn': 'nonexistent', 'click_type': 'single'}
    
    def mock_sleep(duration):
        clicker_instance.stop_event.set()

    with patch('time.sleep', side_effect=mock_sleep):
        clicker_instance.run(config)
    
    # Should have skipped the click entirely
    clicker_instance.mouse.click.assert_not_called()


def test_repeat_count_stops_after_exact_clicks(clicker_instance):
    """Test that repeat_count stops automatically after exact number of clicks."""
    clicked_count = []
    clicker_instance.on_click_callback = lambda: clicked_count.append(1)

    config = {
        'interval': 0.001,
        'action_type': 'mouse',
        'mouse_btn': 'left',
        'click_type': 'single',
        'repeat_count': 3,
    }

    with patch('time.sleep'):
        clicker_instance.run(config)

    assert clicker_instance.mouse.click.call_count == 3
    assert len(clicked_count) == 3


def test_fixed_pos_and_return_cursor(clicker_instance):
    """Test fixed_pos moves to target, clicks, and restores original cursor position."""
    clicker_instance.mouse.position = (10, 20)
    positions_at_click = []
    clicker_instance.mouse.click.side_effect = lambda btn, cnt: positions_at_click.append(clicker_instance.mouse.position)

    config = {
        'interval': 0.001,
        'action_type': 'mouse',
        'mouse_btn': 'left',
        'click_type': 'single',
        'repeat_count': 1,
        'fixed_pos': (500, 600),
        'return_cursor': True,
    }

    with patch('time.sleep'):
        clicker_instance.run(config)

    assert positions_at_click == [(500, 600)]
    assert clicker_instance.mouse.position == (10, 20)

