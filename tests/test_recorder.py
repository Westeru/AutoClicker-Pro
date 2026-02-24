import pytest
from unittest.mock import MagicMock, patch
import time
from pynput.keyboard import Key

from src.recorder import Recorder

@pytest.fixture
def mock_listeners():
    with patch('src.recorder.pynput_mouse.Listener') as mock_mouse_listener, \
         patch('src.recorder.pynput_keyboard.Listener') as mock_kb_listener:
        yield {
            'mouse': mock_mouse_listener,
            'keyboard': mock_kb_listener
        }

@pytest.fixture
def recorder(mock_listeners):
    return Recorder()

def test_initialization(recorder):
    assert recorder.events == []
    assert not recorder.recording
    assert recorder.mouse_listener is None
    assert recorder.key_listener is None

def test_start_recording(recorder, mock_listeners):
    # Mock time to test start_time
    with patch('time.time', return_value=12345.0):
        recorder.start()
        
    assert recorder.recording
    assert recorder.start_time == 12345.0
    assert Key.f6 in recorder.ignore_keys
    assert Key.f7 in recorder.ignore_keys
    
    # Assert listeners were created and started
    mock_listeners['mouse'].assert_called_once()
    mock_listeners['keyboard'].assert_called_once()
    
    assert recorder.mouse_listener == mock_listeners['mouse'].return_value
    assert recorder.key_listener == mock_listeners['keyboard'].return_value
    
    recorder.mouse_listener.start.assert_called_once()
    recorder.key_listener.start.assert_called_once()

def test_stop_recording(recorder, mock_listeners):
    recorder.start()
    recorder.stop()
    
    assert not recorder.recording
    recorder.mouse_listener.stop.assert_called_once()
    recorder.key_listener.stop.assert_called_once()

@patch('time.time', return_value=12355.0)
def test_add_event(mock_time, recorder):
    recorder.recording = True
    recorder.start_time = 12345.0
    
    recorder._add_event("test_type", foo="bar")
    
    assert len(recorder.events) == 1
    event = recorder.events[0]
    assert event['type'] == 'test_type'
    assert event['foo'] == 'bar'
    # time should be time.time() - start_time = 12355.0 - 12345.0 = 10.0
    assert event['time'] == 10.0

def test_add_event_when_not_recording(recorder):
    recorder.recording = False
    recorder._add_event("test_type", foo="bar")
    assert len(recorder.events) == 0

def test_mouse_events(recorder):
    recorder.recording = True
    recorder.start_time = time.time()
    
    recorder.on_move(100, 200)
    assert len(recorder.events) == 1
    assert recorder.events[-1]['type'] == 'move'
    assert recorder.events[-1]['x'] == 100
    assert recorder.events[-1]['y'] == 200
    
    recorder.on_click(150, 250, 'Button.left', True)
    assert len(recorder.events) == 2
    assert recorder.events[-1]['type'] == 'click'
    assert recorder.events[-1]['button'] == 'left' # The method strips 'Button.'
    assert recorder.events[-1]['pressed'] is True
    
    recorder.on_scroll(300, 400, 0, 1)
    assert len(recorder.events) == 3
    assert recorder.events[-1]['type'] == 'scroll'
    assert recorder.events[-1]['dx'] == 0
    assert recorder.events[-1]['dy'] == 1

def test_keyboard_events(recorder):
    recorder.recording = True
    recorder.start_time = time.time()
    recorder.ignore_keys = [Key.f6]
    
    # Test ignored key
    recorder.on_press(Key.f6)
    assert len(recorder.events) == 0
    
    # Test normal char key
    class MockKey:
        char = 'a'
    
    recorder.on_press(MockKey())
    assert len(recorder.events) == 1
    assert recorder.events[-1]['type'] == 'key_press'
    assert recorder.events[-1]['key'] == 'a'
    
    # Test special key without char attribute
    recorder.on_release(Key.space)
    assert len(recorder.events) == 2
    assert recorder.events[-1]['type'] == 'key_release'
    assert recorder.events[-1]['key'] == 'Key.space'

def test_stop_remove_last_click(recorder):
    # Simulate a recording sequence ending with a click (e.g. clicking the UI stop button)
    recorder.recording = True
    recorder.start_time = time.time()
    
    # Some events
    recorder.events = [
        {'type': 'move', 'time': 1.0},
        {'type': 'key_press', 'time': 1.1},
        {'type': 'click', 'pressed': True, 'time': 2.0},
        {'type': 'click', 'pressed': False, 'time': 2.1}
    ]
    
    # Stop and remove last click
    recorder.stop(remove_last_click=True)
    
    # The last 2 clicks should be gone
    assert len(recorder.events) == 2
    assert recorder.events[0]['type'] == 'move'
    assert recorder.events[1]['type'] == 'key_press'

def test_stop_remove_last_click_not_at_end(recorder):
    # Simulate a recording sequence where the last click is not at the end
    recorder.recording = True
    recorder.start_time = time.time()
    
    recorder.events = [
        {'type': 'click', 'pressed': True, 'time': 1.0},
        {'type': 'click', 'pressed': False, 'time': 1.1},
        {'type': 'move', 'time': 2.0},
        {'type': 'move', 'time': 2.1},
        {'type': 'move', 'time': 2.2},
        {'type': 'move', 'time': 2.3},
        {'type': 'move', 'time': 2.4},
        {'type': 'move', 'time': 2.5}
    ]
    
    # Stop and remove last click
    recorder.stop(remove_last_click=True)
    
    # The clicks are not at the very end (index 0, 1 vs len 8), so they shouldn't be removed
    assert len(recorder.events) == 8
