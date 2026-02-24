import pytest
from unittest.mock import MagicMock, patch
import threading
import time

from src.workflow_runner import WorkflowRunner
from pynput.mouse import Button

@pytest.fixture
def mock_dependencies():
    with patch('src.workflow_runner.pyautogui') as mock_pyautogui, \
         patch('src.workflow_runner.cv2') as mock_cv2, \
         patch('src.workflow_runner.MouseController') as mock_mouse, \
         patch('time.sleep') as mock_sleep:
        yield {
            'pyautogui': mock_pyautogui,
            'cv2': mock_cv2,
            'mouse': mock_mouse,
            'sleep': mock_sleep
        }

@pytest.fixture
def runner(mock_dependencies):
    stop_event = threading.Event()
    # Mocking MouseController means runner.mouse is the mock returned by the patch
    r = WorkflowRunner(stop_event)
    return r

def test_initialization(runner):
    """Test that WorkflowRunner initializes correctly."""
    assert runner.steps == []
    assert runner.current_step_index == 0
    assert not runner.running
    assert isinstance(runner.stop_event, threading.Event)

def test_set_steps(runner):
    steps = [{'action': 'Delay', 'params': {'duration': 500}}]
    runner.set_steps(steps)
    assert runner.steps == steps

def test_runner_loop_preemption(runner):
    """Test that the loop exits immediately if the stop_event is set."""
    runner.stop_event.set()
    steps = [{'action': 'Delay', 'params': {'duration': 500}}]
    runner.set_steps(steps)
    
    # Execute run
    runner.run()
    
    # Ensure it didn't iterate through the steps
    assert runner.current_step_index == 0

def test_execute_delay_action(runner, mock_dependencies):
    """Test Delay action translates to time.sleep properly."""
    step = {'action': 'Delay', 'params': {'duration': 2500}}
    runner.execute_step(step)
    mock_dependencies['sleep'].assert_called_once_with(2.5)

def test_execute_click_action(runner, mock_dependencies):
    """Test Click action translates to pyautogui and pynput calls."""
    step = {'action': 'Click', 'params': {'x': 100, 'y': 200, 'button': 'right', 'type': 'double'}}
    runner.execute_step(step)
    
    mock_pyautogui = mock_dependencies['pyautogui']
    mock_pyautogui.moveTo.assert_called_once_with(100, 200)
    
    runner.mouse.click.assert_called_once_with(Button.right, 2)
    assert runner.mouse.position == (100, 200)

def test_execute_key_press_action(runner, mock_dependencies):
    """Test Key Press maps string keys to pyautogui press/hotkey."""
    step_single = {'action': 'Key Press', 'params': {'key': 'a'}}
    runner.execute_step(step_single)
    mock_dependencies['pyautogui'].press.assert_called_with('a')
    
    step_hotkey = {'action': 'Key Press', 'params': {'key': 'ctrl+c'}}
    runner.execute_step(step_hotkey)
    mock_dependencies['pyautogui'].hotkey.assert_called_with('ctrl', 'c')
    
    step_windows = {'action': 'Key Press', 'params': {'key': 'windows+r'}}
    runner.execute_step(step_windows)
    mock_dependencies['pyautogui'].hotkey.assert_called_with('win', 'r')

def test_execute_type_text_action(runner, mock_dependencies):
    """Test Type Text calls pyautogui.write."""
    step = {'action': 'Type Text', 'params': {'text': 'Hello World!'}}
    runner.execute_step(step)
    mock_dependencies['pyautogui'].write.assert_called_once_with('Hello World!', interval=0.05)

@patch('time.time')
def test_wait_image_action_success(mock_time, runner, mock_dependencies):
    """Test Wait Image succeeds when image is found within timeout."""
    step = {'action': 'Wait Image', 'params': {'image_path': 'test.png', 'timeout': 5, 'confidence': 0.8}}
    
    # Mock find_image to simulate not finding it then finding it
    runner._find_image = MagicMock(side_effect=[None, (150, 250)])
    
    # Time advances simulated
    mock_time.side_effect = [10.0, 10.1, 10.6]  # start, loop 1 time.time(), loop 2 time.time()
    
    runner.execute_step(step)
    
    assert runner._find_image.call_count == 2
    mock_dependencies['sleep'].assert_called_with(0.5)

@patch('time.time')
def test_click_image_action_success(mock_time, runner, mock_dependencies):
    """Test Click Image clicks at right location when found."""
    step = {'action': 'Click Image', 'params': {'image_path': 'btn.png', 'timeout': 2, 'confidence': 0.9, 'button': 'left'}}
    
    runner._find_image = MagicMock(return_value=(300, 400))
    mock_time.side_effect = [10.0, 10.1]
    
    runner.execute_step(step)
    
    assert runner.mouse.position == (300, 400)
    runner.mouse.click.assert_called_once_with(Button.left, 1)

def test_find_image(runner, mock_dependencies):
    """Test inner _find_image uses cv2 correctly."""
    mock_cv2 = mock_dependencies['cv2']
    mock_pyautogui = mock_dependencies['pyautogui']
    
    # Mock template shape (h, w, c)
    mock_template = MagicMock()
    mock_template.shape = (50, 100, 3)
    mock_cv2.imread.return_value = mock_template
    
    # Mock screenshot and matchTemplate
    mock_cv2.matchTemplate.return_value = MagicMock()
    mock_cv2.minMaxLoc.return_value = (None, 0.95, None, (100, 100)) # return maxLoc as (100, 100) and max_val as 0.95
    
    # Conf threshold 0.9, so 0.95 should pass
    res = runner._find_image('dummy.png', 0.9)
    
    mock_cv2.imread.assert_called_once_with('dummy.png')
    mock_pyautogui.screenshot.assert_called_once()
    mock_cv2.matchTemplate.assert_called_once()
    
    # Found pos = loc + (w/2, h/2) = (100 + 50, 100 + 25) = (150, 125)
    assert res == (150, 125)
