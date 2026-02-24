import pytest
from unittest.mock import MagicMock, patch
import threading
import time
import numpy as np

from src.vision import ImageSearcher

@pytest.fixture
def mock_dependencies():
    with patch('src.vision.cv2') as mock_cv2, \
         patch('src.vision.pyautogui') as mock_pyautogui, \
         patch('time.sleep') as mock_sleep:
             
        # Create a mock template image (h=50, w=100)
        mock_template = MagicMock()
        mock_template.shape = (50, 100, 3) 
        mock_cv2.imread.return_value = mock_template
        
        # When converting to grayscale, keep the shape mock
        mock_gray_template = MagicMock()
        mock_gray_template.shape = (50, 100)
        
        # We need cvtColor to return something when creating the template
        # The first call to cvtColor is for the template, the second is for the screenshot
        mock_cv2.cvtColor.side_effect = [mock_gray_template, MagicMock(), MagicMock()] 
        
        yield {
            'cv2': mock_cv2,
            'pyautogui': mock_pyautogui,
            'sleep': mock_sleep
        }

@pytest.fixture
def searcher():
    stop_event = threading.Event()
    # We pass a MagicMock for the update_callback to verify it gets called
    callback = MagicMock()
    return ImageSearcher(stop_event, callback)

def test_initialization(searcher):
    """Test standard initialization."""
    assert isinstance(searcher.stop_event, threading.Event)
    assert not searcher.stop_event.is_set()
    assert searcher.update_callback is not None

def test_load_image_failure(searcher, mock_dependencies):
    """Test that if imread fails (returns None), the run method early exits."""
    mock_dependencies['cv2'].imread.return_value = None
    
    config = {'img_path': 'bad_path.png'}
    searcher.run(config)
    
    # It should exit before taking any screenshots
    mock_dependencies['pyautogui'].screenshot.assert_not_called()

def test_search_loop_success(searcher, mock_dependencies):
    """Test that a successful match triggers a click."""
    mock_cv2 = mock_dependencies['cv2']
    mock_pyautogui = mock_dependencies['pyautogui']
    
    # Ensure the loop runs exactly once by setting the stop_event during pyautogui.click
    def stop_loop(*args, **kwargs):
        searcher.stop_event.set()
        
    mock_pyautogui.click.side_effect = stop_loop
    
    # Configure minMaxLoc to return a match (max_val = 0.95 > conf 0.8)
    # top_left = (100, 200)
    mock_cv2.minMaxLoc.return_value = (None, 0.95, None, (100, 200))

    config = {
        'img_path': 'test.png', 
        'interval': 0.1, 
        'confidence': 0.8, 
        'grayscale': True
    }
    
    searcher.run(config)
    
    # Verify the callback was called with the confidence value
    searcher.update_callback.assert_called_once_with(0.95)
    
    # Verify it clicked the center: 
    # top_left X (100) + width // 2 (100//2 = 50) = 150
    # top_left Y (200) + height // 2 (50//2 = 25) = 225
    mock_pyautogui.click.assert_called_once_with(150, 225)
    
    # Verify it moved the mouse away
    mock_pyautogui.moveTo.assert_called_once_with(10, 10)

def test_search_loop_no_match(searcher, mock_dependencies):
    """Test that if the confidence is too low, it does not click."""
    mock_cv2 = mock_dependencies['cv2']
    mock_pyautogui = mock_dependencies['pyautogui']
    
    # Stop loop on sleep
    def stop_loop(*args, **kwargs):
        searcher.stop_event.set()
        
    mock_dependencies['sleep'].side_effect = stop_loop
    
    # Match confidence 0.5 < 0.8
    mock_cv2.minMaxLoc.return_value = (None, 0.5, None, (100, 200))

    config = {
        'img_path': 'test.png', 
        'interval': 0.1, 
        'confidence': 0.8, 
        'grayscale': False # test grayscale=False path too
    }
    
    searcher.run(config)
    
    # Callback should still be called with the lower confidence
    searcher.update_callback.assert_called_once_with(0.5)
    
    # Should NOT have clicked
    mock_pyautogui.click.assert_not_called()
    mock_pyautogui.moveTo.assert_not_called()
    
def test_searcher_handles_exception_safely(searcher, mock_dependencies):
    """Test that an error in the loop (like matchTemplate crashing) doesn't break the whole thread."""
    mock_cv2 = mock_dependencies['cv2']
    mock_pyautogui = mock_dependencies['pyautogui']
    
    # Force matchTemplate to throw an exception
    mock_cv2.matchTemplate.side_effect = Exception("OpenCV Error")
    
    # Stop loop on sleep so it doesn't infinite loop
    def stop_loop(*args, **kwargs):
        searcher.stop_event.set()
        
    mock_dependencies['sleep'].side_effect = stop_loop
    
    config = {'img_path': 'test.png', 'interval': 0.1, 'confidence': 0.8}
    
    # It should catch the exception and gracefully continue to the sleep block, then exit
    searcher.run(config)
    
    # Verified it reached screenshot but failed later, didn't crash
    mock_pyautogui.screenshot.assert_called_once()
    mock_pyautogui.click.assert_not_called()
