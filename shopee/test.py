"""
Shopee Android Automation Testing Framework
============================================
A modular, Object-Oriented framework for testing Android E-commerce applications
using Python and ADB (Android Debug Bridge).

Author: QA Automation Team
Purpose: Legitimate UI Stability Testing & User Onboarding Flow Verification
Package Under Test: com.shopee.vn
"""

import os
import random
import re
import subprocess
import time
import unicodedata
import xml.etree.ElementTree as ET
from typing import Optional, Tuple, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
import logging
import base64
import threading

import requests
import cv2
import numpy as np

from registration_flow import RegistrationFlow


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class Config:
    """Central configuration for the automation framework"""
    # API Endpoints
    PCHANGER_BASE_URL: str = "http://127.0.0.1:8080"
    SMS_API_URL: str = "https://otistx.com"
    SMS_API_KEY: str = "otis_QpzoL8MJ96MYaokccBsM3Pk4QkUPnetx"  # Replace with your actual API key
    CAPTCHA_API_KEY: str = "779ae1c479854310b35bb9983dea54ca"  # Achicaptcha API key (updated 2026)
    
    # App Configuration
    APP_PACKAGE: str = "com.shopee.vn"
    
    # Timeout Settings (seconds)
    DEVICE_READY_TIMEOUT: int = 300
    PACKAGE_INSTALL_TIMEOUT: int = 300
    POPUP_HANDLE_TIMEOUT: int = 5
    OTP_POLLING_TIMEOUT: int = 60
    OTP_POLLING_INTERVAL: int = 5
    
    # UI Element Identifiers
    RESOURCE_ID_PHONE_INPUT: str = "com.shopee.vn:id/cret_edit_text"
    RESOURCE_ID_OTP_INPUT: str = "com.shopee.vn:id/cret_edit_text"  # Same as phone input
    RESOURCE_ID_CONTINUE_BTN: str = "com.shopee.vn:id/btnContinue"
    RESOURCE_ID_SEARCH_BAR: str = "com.shopee.vn:id/search_bar_container"
    RESOURCE_ID_NOTIFICATION_ICON: str = "com.shopee.vn:id/icon"
    CONTENT_DESC_NOTIFICATION: str = "tab_bar_button_notification"
    CONTENT_DESC_CLOSE_BANNER: str = "close"
    
    # Permission & Dialog IDs
    RESOURCE_ID_PERMISSION_MSG: str = "com.android.permissioncontroller:id/permission_message"
    RESOURCE_ID_PERMISSION_DENY: str = "com.android.permissioncontroller:id/permission_deny_button"
    RESOURCE_ID_OK_BUTTON: str = "android:id/ok"
    RESOURCE_ID_DIALOG_TITLE: str = "com.shopee.vn:id/txt_title"
    RESOURCE_ID_DIALOG_POSITIVE: str = "com.shopee.vn:id/buttonDefaultPositive"
    RESOURCE_ID_PHONE_INPUT: str = "com.shopee.vn:id/cret_edit_text" 
    RESOURCE_ID_ACTIVATE_WALLET: str = "com.shopee.vn:id/tvActivateWallet"
    
    # Nút Đăng nhập/Tiếp tục (nút màu cam sau khi điền sdt)
    RESOURCE_ID_LOGIN_BTN: str = "com.shopee.vn:id/btnLogin"
    
    # Icon Thông báo ở tab bar
    RESOURCE_ID_NOTIFICATION_ICON: str = "com.shopee.vn:id/icon"
    CONTENT_DESC_NOTIFICATION: str = "tab_bar_button_notification"
    # Captcha Detection
    ACTIVITY_CAPTCHA: str = "com.shopee.app.ui.auth2.captcha.WebCaptchaPopupActivity"
    
    # Product Card Pattern
    PRODUCT_CARD_DESC_PREFIX: str = "dd_module_product_card_"
    
    # UI Text Constants
    TEXT_OK: str = "OK"
    TEXT_START: str = "BẮT ĐẦU"
    TEXT_ALLOW: str = "Cho phép"
    TEXT_DENY: str = "Không cho phép"
    TEXT_CLOSE_X: str = "X"
    
    # Behavior Settings
    MIN_SWIPE_COUNT: int = 2
    MAX_SWIPE_COUNT: int = 3
    MIN_PRODUCT_VIEW_TIME: float = 1.5
    MAX_PRODUCT_VIEW_TIME: float = 4.0


class LogLevel(Enum):
    """Logging levels for the framework"""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


# ============================================================================
# LOGGING UTILITIES
# ============================================================================

class AutomationLogger:
    """Enhanced logger with structured output and context"""
    
    def __init__(self, name: str, level: LogLevel = LogLevel.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level.value)
        
        # Console handler with formatting
        if not self.logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(level.value)
            formatter = logging.Formatter(
                fmt='[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
                datefmt='%H:%M:%S'
            )
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
    
    def debug(self, message: str):
        self.logger.debug(message)
    
    def info(self, message: str):
        self.logger.info(message)
    
    def warning(self, message: str):
        self.logger.warning(message)
    
    def error(self, message: str):
        self.logger.error(message)
    
    def critical(self, message: str):
        self.logger.critical(message)
    
    def section(self, title: str):
        """Log a section header"""
        separator = "=" * 60
        self.logger.info(f"\n{separator}")
        self.logger.info(f"  {title}")
        self.logger.info(f"{separator}")


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================



def normalize_text(value: str) -> str:
    """
    Normalize text by removing Vietnamese accents and standardizing whitespace.
    Useful for fuzzy matching of UI element text.
    
    Args:
        value: Input text to normalize
        
    Returns:
        Normalized uppercase text with single spaces
    """
    if not value:
        return ""
    value = str(value).strip()
    # Remove Vietnamese accents using Unicode normalization
    value = unicodedata.normalize("NFD", value)
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    value = value.upper()
    return " ".join(value.split())


def parse_bounds(bounds_str: str) -> Optional[Tuple[int, int, int, int]]:
    """
    Parse Android UI bounds string into coordinate tuple.
    
    Args:
        bounds_str: Bounds string in format '[x1,y1][x2,y2]'
        
    Returns:
        Tuple of (x1, y1, x2, y2) or None if parsing fails
    """
    if not bounds_str:
        return None
    try:
        nums = []
        current = ""
        for ch in bounds_str:
            if ch.isdigit():
                current += ch
            elif current:
                nums.append(int(current))
                current = ""
        if current:
            nums.append(int(current))
        
        if len(nums) == 4:
            return tuple(nums)  # (x1, y1, x2, y2)
    except Exception:
        pass
    return None


def get_center_coordinates(bounds: Tuple[int, int, int, int]) -> Tuple[int, int]:
    """
    Calculate center point of a bounding box.
    
    Args:
        bounds: Tuple of (x1, y1, x2, y2)
        
    Returns:
        Tuple of (center_x, center_y)
    """
    x1, y1, x2, y2 = bounds
    return (x1 + x2) // 2, (y1 + y2) // 2


def is_point_visible(x: int, y: int, screen_width: int, screen_height: int) -> bool:
    """
    Check if a point is within visible screen bounds.
    
    Args:
        x: X coordinate
        y: Y coordinate
        screen_width: Device screen width
        screen_height: Device screen height
        
    Returns:
        True if point is visible, False otherwise
    """
    return 0 < x < screen_width and 0 < y < screen_height


# ============================================================================
# UI ELEMENT REPRESENTATION
# ============================================================================

@dataclass
class UIElement:
    """Represents a UI element found in the Android UI hierarchy"""
    bounds: Tuple[int, int, int, int]
    resource_id: str = ""
    text: str = ""
    content_desc: str = ""
    class_name: str = ""
    clickable: bool = True
    
    @property
    def center(self) -> Tuple[int, int]:
        """Get center coordinates of the element"""
        return get_center_coordinates(self.bounds)
    
    def is_visible(self, screen_width: int, screen_height: int) -> bool:
        """Check if element is visible on screen"""
        cx, cy = self.center
        return is_point_visible(cx, cy, screen_width, screen_height)


# ============================================================================
# ADB CONTROLLER MODULE
# ============================================================================

class ADBController:
    """
    Low-level ADB command executor for Android device control.
    Handles all ADB shell commands and device interactions.
    """
    
    def __init__(self, adb_path: str = "adb"):
        """
        Initialize ADB controller.
        
        Args:
            adb_path: Path to ADB executable (defaults to 'adb' in PATH)
        """
        self.adb_path = self._find_adb_executable(adb_path)
        self.logger = AutomationLogger("ADBController")
        self.logger.info(f"Initialized with ADB path: {self.adb_path}")
    
    def _find_adb_executable(self, default_path: str) -> str:
        """
        Locate ADB executable in common locations.
        
        Args:
            default_path: Default ADB path to try
            
        Returns:
            Path to ADB executable
        """
        # Check current directory
        cwd_adb = os.path.join(os.getcwd(), "adb.exe")
        if os.path.exists(cwd_adb):
            return cwd_adb
        
        # Check script directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        local_adb = os.path.join(script_dir, "adb.exe")
        if os.path.exists(local_adb):
            return local_adb
        
        # Use system PATH
        return default_path
    
    def _execute(self, args: List[str], timeout: int = 20) -> Tuple[int, str, str]:
        """
        Execute ADB command with error handling.
        
        Args:
            args: Command arguments list
            timeout: Command timeout in seconds
            
        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        try:
            result = subprocess.run(
                [self.adb_path] + args,
                capture_output=True,
                text=False,
                timeout=timeout,
                check=False
            )
            stdout = result.stdout.decode("utf-8", errors="replace").strip()
            stderr = result.stderr.decode("utf-8", errors="replace").strip()
            return result.returncode, stdout, stderr
        except subprocess.TimeoutExpired:
            self.logger.error(f"Command timeout after {timeout}s: {' '.join(args)}")
            return -1, "", "Command timeout"
        except Exception as e:
            self.logger.error(f"Command execution failed: {e}")
            return -1, "", str(e)
    
    def get_connected_devices(self) -> List[str]:
        """
        Get list of connected Android devices.
        
        Returns:
            List of device serial numbers
        """
        code, out, err = self._execute(["devices"])
        if code != 0:
            self.logger.error(f"Failed to get devices: {err}")
            return []
        
        devices = []
        for line in out.splitlines():
            line = line.strip()
            if not line or line.startswith("List of devices"):
                continue
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                devices.append(parts[0])
        
        return devices
    
    def get_device_state(self, serial: str) -> str:
        """
        Get current state of a device.
        
        Args:
            serial: Device serial number
            
        Returns:
            Device state ('device', 'offline', etc.) or empty string
        """
        code, out, _ = self._execute(["-s", serial, "get-state"])
        return out.strip() if code == 0 else ""
    
    def wait_for_device(self, serial: str, timeout: int = 300, interval: int = 3) -> bool:
        """
        Wait for device to become ready.
        
        Args:
            serial: Device serial number
            timeout: Maximum wait time in seconds
            interval: Check interval in seconds
            
        Returns:
            True if device is ready, False if timeout
        """
        self.logger.info(f"Waiting for device {serial} to be ready...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            state = self.get_device_state(serial)
            if state == "device":
                self.logger.info(f"Device {serial} is ready")
                return True
            time.sleep(interval)
        
        self.logger.error(f"Device {serial} not ready after {timeout}s")
        return False
    
    def shell(self, serial: str, args: List[str], timeout: int = 20) -> Tuple[int, str, str]:
        """
        Execute shell command on device.
        
        Args:
            serial: Device serial number
            args: Shell command arguments
            timeout: Command timeout
            
        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        cmd = ["-s", serial, "shell"] + args
        return self._execute(cmd, timeout=timeout)
    
    def tap(self, serial: str, x: int, y: int):
        """
        Simulate screen tap at coordinates.
        
        Args:
            serial: Device serial number
            x: X coordinate
            y: Y coordinate
        """
        self.shell(serial, ["input", "tap", str(x), str(y)])
        self.logger.debug(f"Tapped at ({x}, {y})")
    
    def swipe(self, serial: str, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300):
        """
        Simulate swipe gesture.
        
        Args:
            serial: Device serial number
            x1, y1: Start coordinates
            x2, y2: End coordinates
            duration_ms: Swipe duration in milliseconds
        """
        self.shell(serial, ["input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration_ms)])
        self.logger.debug(f"Swiped from ({x1},{y1}) to ({x2},{y2})")
    
    def input_text(self, serial: str, text: str):
        """
        Input text into focused field.
        
        Args:
            serial: Device serial number
            text: Text to input (spaces will be encoded)
        """
        # Escape spaces for ADB input
        escaped_text = str(text).replace(" ", "%s")
        self.shell(serial, ["input", "text", escaped_text])
        self.logger.debug(f"Inputted text: {text}")
    
    def press_keycode(self, serial: str, keycode: int):
        """
        Press Android keycode.
        
        Args:
            serial: Device serial number
            keycode: Android keycode (e.g., 4 for BACK)
        """
        self.shell(serial, ["input", "keyevent", str(keycode)])
        self.logger.debug(f"Pressed keycode: {keycode}")
    
    def launch_app(self, serial: str, package: str):
        """
        Launch application by package name.
        
        Args:
            serial: Device serial number
            package: App package name
        """
        self.shell(serial, [
            "monkey", "-p", package, 
            "-c", "android.intent.category.LAUNCHER", "1"
        ], timeout=30)
        self.logger.info(f"Launched app: {package}")
    
    def is_app_installed(self, serial: str, package: str) -> bool:
        """
        Check if app is installed on device.
        
        Args:
            serial: Device serial number
            package: App package name
            
        Returns:
            True if app is installed
        """
        code, out, _ = self.shell(serial, ["pm", "path", package])
        return code == 0 and out.strip().startswith("package:")
    
    def wait_for_app_installation(self, serial: str, package: str, 
                                  timeout: int = 300, interval: int = 5) -> bool:
        """
        Wait for app to be installed.
        
        Args:
            serial: Device serial number
            package: App package name
            timeout: Maximum wait time
            interval: Check interval
            
        Returns:
            True if app is installed within timeout
        """
        self.logger.info(f"Waiting for {package} installation...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.is_app_installed(serial, package):
                self.logger.info(f"App {package} is installed")
                return True
            time.sleep(interval)
        
        self.logger.error(f"App {package} not installed after {timeout}s")
        return False
    
    def get_screen_size(self, serial: str) -> Tuple[int, int]:
        """
        Get device screen dimensions.
        
        Args:
            serial: Device serial number
            
        Returns:
            Tuple of (width, height), defaults to (1080, 1920) if detection fails
        """
        code, out, _ = self.shell(serial, ["wm", "size"])
        if code != 0:
            return 1080, 1920
        
        try:
            # Parse output like "Physical size: 1080x1920"
            for line in out.splitlines():
                if ":" in line:
                    size_part = line.split(":")[-1].strip()
                    if "x" in size_part:
                        w, h = size_part.split("x")
                        return int(w), int(h)
        except Exception as e:
            self.logger.warning(f"Failed to parse screen size: {e}")
        
        return 1080, 1920
    
    def unlock_screen(self, serial: str):
        """
        Unlock device screen.
        
        Args:
            serial: Device serial number
        """
        # Press menu button
        self.press_keycode(serial, 82)
        time.sleep(0.5)
        # Swipe up to unlock
        self.swipe(serial, 500, 1000, 500, 200, 300)
        self.logger.debug("Unlocked screen")
    
    def dump_ui_hierarchy(self, serial: str) -> str:
        """
        Dump current UI hierarchy XML.
        
        Args:
            serial: Device serial number
            
        Returns:
            XML string of UI hierarchy
        """
        # Trigger UI dump
        self.shell(serial, ["uiautomator", "dump", "/sdcard/uidump.xml"])
        # Read dumped XML
        code, out, _ = self.shell(serial, ["cat", "/sdcard/uidump.xml"])
        return out if code == 0 else ""


# ============================================================================
# UI ELEMENT FINDER
# ============================================================================

class UIElementFinder:
    """
    Parses Android UI XML hierarchy and finds elements matching criteria.
    Implements robust element searching with visibility checks.
    """
    
    def __init__(self, adb: ADBController):
        """
        Initialize UI element finder.
        
        Args:
            adb: ADB controller instance
        """
        self.adb = adb
        self.logger = AutomationLogger("UIElementFinder")
    
    def find_elements(self, serial: str, **criteria) -> List[UIElement]:
        """
        Find UI elements matching search criteria.
        
        Args:
            serial: Device serial number
            **criteria: Search criteria (resource_id, text, content_desc, partial_text, etc.)
            
        Returns:
            List of matching UIElement objects
        """
        xml_content = self.adb.dump_ui_hierarchy(serial)
        if not xml_content.strip():
            self.logger.warning("UI hierarchy dump is empty")
            return []
        
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            self.logger.error(f"Failed to parse UI XML: {e}")
            return []
        
        results = []
        
        # Extract search criteria
        target_resource_id = criteria.get('resource_id')
        target_text = criteria.get('text')
        target_content_desc = criteria.get('content_desc')
        partial_text = criteria.get('partial_text')
        partial_desc = criteria.get('partial_desc')
        target_class = criteria.get('class_name')
        
        # Iterate through all nodes
        for node in root.iter():
            if not self._matches_criteria(node, target_resource_id, target_text, 
                                          target_content_desc, partial_text, 
                                          partial_desc, target_class):
                continue
            
            # Parse bounds
            bounds = parse_bounds(node.attrib.get('bounds', ''))
            if not bounds:
                continue
            
            # Create UI element
            element = UIElement(
                bounds=bounds,
                resource_id=node.attrib.get('resource-id', ''),
                text=node.attrib.get('text', ''),
                content_desc=node.attrib.get('content-desc', ''),
                class_name=node.attrib.get('class', ''),
                clickable=node.attrib.get('clickable', 'false') == 'true'
            )
            results.append(element)
        
        self.logger.debug(f"Found {len(results)} elements matching criteria")
        return results
    
    def _matches_criteria(self, node, resource_id, text, content_desc, 
                         partial_text, partial_desc, class_name) -> bool:
        """Check if node matches all specified criteria"""
        if resource_id and resource_id not in node.attrib.get('resource-id', ''):
            return False
        if text and text != node.attrib.get('text', ''):
            return False
        if content_desc and content_desc != node.attrib.get('content-desc', ''):
            return False
        if partial_text and partial_text not in node.attrib.get('text', ''):
            return False
        if partial_desc and partial_desc not in node.attrib.get('content-desc', ''):
            return False
        if class_name and class_name not in node.attrib.get('class', ''):
            return False
        return True
    
    def find_visible_elements(self, serial: str, screen_width: int, 
                            screen_height: int, **criteria) -> List[UIElement]:
        """
        Find elements that are visible on screen.
        
        Args:
            serial: Device serial number
            screen_width: Screen width in pixels
            screen_height: Screen height in pixels
            **criteria: Search criteria
            
        Returns:
            List of visible UIElement objects
        """
        all_elements = self.find_elements(serial, **criteria)
        visible = [elem for elem in all_elements if elem.is_visible(screen_width, screen_height)]
        self.logger.debug(f"Found {len(visible)} visible elements out of {len(all_elements)}")
        return visible
    
    def find_by_xpath(self, serial: str, xpath: str) -> List[UIElement]:
        """Find elements by a limited XPath-like path."""
        xml_content = self.adb.dump_ui_hierarchy(serial)
        if not xml_content.strip():
            return []
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError:
            return []

        path = xpath.strip()
        resource_id = None
        match = re.match(r'^\/\/\*\[@resource-id="([^"]+)"\](/.*)?$', path)
        if match:
            resource_id = match.group(1)
            path = match.group(2) or ''

        segments = [seg for seg in path.split('/') if seg]
        if resource_id:
            candidates = [node for node in root.iter() if node.attrib.get('resource-id') == resource_id]
        else:
            candidates = [root]

        for seg in segments:
            seg_match = re.match(r'^(?P<class>[^\[]+)(\[(?P<index>\d+)\])?$', seg)
            if not seg_match:
                return []
            class_name = seg_match.group('class')
            index = int(seg_match.group('index')) if seg_match.group('index') else None
            next_candidates = []
            for node in candidates:
                children = [child for child in list(node) if child.attrib.get('class') == class_name]
                if index is not None:
                    if 1 <= index <= len(children):
                        next_candidates.append(children[index - 1])
                else:
                    next_candidates.extend(children)
            candidates = next_candidates
            if not candidates:
                break

        results = []
        for node in candidates:
            bounds = parse_bounds(node.attrib.get('bounds', ''))
            if not bounds:
                continue
            results.append(UIElement(
                bounds=bounds,
                resource_id=node.attrib.get('resource-id', ''),
                text=node.attrib.get('text', ''),
                content_desc=node.attrib.get('content-desc', ''),
                class_name=node.attrib.get('class', ''),
                clickable=node.attrib.get('clickable', 'false') == 'true'
            ))
        return results

    def find_by_text(self, serial: str, text: str, exact: bool = True, 
                    normalize: bool = True) -> List[UIElement]:
        """
        Find elements by text content with optional normalization.
        
        Args:
            serial: Device serial number
            text: Text to search for
            exact: Exact match vs partial match
            normalize: Apply Vietnamese accent removal
            
        Returns:
            List of matching elements
        """
        if normalize:
            xml_content = self.adb.dump_ui_hierarchy(serial)
            if not xml_content.strip():
                return []
            
            try:
                root = ET.fromstring(xml_content)
            except ET.ParseError:
                return []
            
            target_norm = normalize_text(text)
            results = []
            
            for node in root.iter():
                for attr in ("text", "content-desc"):
                    value = node.attrib.get(attr, "")
                    if not value:
                        continue
                    
                    value_norm = normalize_text(value)
                    if exact and value_norm == target_norm:
                        bounds = parse_bounds(node.attrib.get("bounds", ""))
                        if bounds:
                            results.append(UIElement(
                                bounds=bounds,
                                text=node.attrib.get('text', ''),
                                content_desc=node.attrib.get('content-desc', '')
                            ))
                    elif not exact and target_norm in value_norm:
                        bounds = parse_bounds(node.attrib.get("bounds", ""))
                        if bounds:
                            results.append(UIElement(
                                bounds=bounds,
                                text=node.attrib.get('text', ''),
                                content_desc=node.attrib.get('content-desc', '')
                            ))
            
            return results
        else:
            if exact:
                return self.find_elements(serial, text=text)
            else:
                return self.find_elements(serial, partial_text=text)


# ============================================================================
# POPUP HANDLER MODULE
# ============================================================================

class PopupHandler:
    """
    Handles system popups, permissions, and app banners automatically.
    Implements intelligent popup detection and dismissal strategies.
    """
    
    def __init__(self, adb: ADBController, element_finder: UIElementFinder, config: Config):
        """
        Initialize popup handler.
        
        Args:
            adb: ADB controller instance
            element_finder: UI element finder instance
            config: Configuration object
        """
        self.adb = adb
        self.finder = element_finder
        self.config = config
        self.logger = AutomationLogger("PopupHandler")
    
    def handle_all_popups(self, serial: str, screen_width: int, screen_height: int, 
                         max_attempts: int = 2, quick_mode: bool = False,
                         prioritize_permission: bool = True,
                         allow_banner: bool = True,
                         allow_permission: bool = True) -> Dict[str, bool]:
        """
        Handle all common popups in a single pass.
        
        Args:
            serial: Device serial number
            screen_width: Screen width
            screen_height: Screen height
            max_attempts: Maximum handling attempts (default 2 for speed)
            quick_mode: If True, skip checks faster
            prioritize_permission: If True, handle permission before banner when both appear
            allow_banner: If False, skip banner handling
            allow_permission: If False, skip permission handling
            
        Returns:
            Dictionary with popup types handled
        """
        result = {
            'ok_button': False,
            'start_button': False,
            'permission': False,
            'in_app_blocker': False,
            'banner': False,
            'dialog': False
        }
        
        self.logger.debug("Starting popup handling...")
        
        for attempt in range(max_attempts):
            handled_something = False
            
            # Get XML once per attempt for efficiency
            xml_content = self.adb.dump_ui_hierarchy(serial)
            if not xml_content.strip():
                time.sleep(0.1)
                continue
            
            xml_norm = normalize_text(xml_content)
            deny_markers = [
                normalize_text(self.config.TEXT_DENY),
                "DENY",
                "DONT ALLOW",
                "DON'T ALLOW",
            ]
            if allow_permission:
                permission_present = (
                    self.config.RESOURCE_ID_PERMISSION_MSG in xml_content
                    or self.config.RESOURCE_ID_PERMISSION_DENY in xml_content
                    or any(marker in xml_norm for marker in deny_markers)
                )
            else:
                permission_present = False

            # Priority 1: Start button (highest priority)
            if self._handle_start_button_fast(serial, screen_width, screen_height, xml_content):
                result['start_button'] = True
                self.logger.info("✓ Tapped START button")
                time.sleep(3 if quick_mode else 4)  # Reduced from 6s
                break  # Exit after handling start button
            
            # Priority 2: OK button
            if self._handle_ok_button_fast(serial, screen_width, screen_height, xml_content):
                result['ok_button'] = True
                self.logger.info("✓ Tapped OK button")
                handled_something = True
                time.sleep(0.2 if quick_mode else 0.3)
                continue
            
            # Priority 3: Permission dialogs
            if allow_permission and self._handle_permissions_fast(serial, screen_width, screen_height, xml_content):
                result['permission'] = True
                self.logger.info("Denied permission")
                handled_something = True
                time.sleep(0.2 if quick_mode else 0.3)
                continue

            # Priority 3.5: In-app blockers (location denied, banned, etc.)
            if self._handle_in_app_blockers(serial, screen_width, screen_height, xml_content):
                result['in_app_blocker'] = True
                self.logger.info("Closed in-app blocker")
                handled_something = True
                time.sleep(0.2 if quick_mode else 0.3)
                continue

            # Priority 4: Agreement Dialog
            if self._handle_dialog_fast(serial, screen_width, screen_height, xml_content):
                result['dialog'] = True
                self.logger.info("✓ Accepted dialog")
                handled_something = True
                time.sleep(0.2 if quick_mode else 0.3)
                continue

            if allow_permission and prioritize_permission and permission_present and not result['permission']:
                time.sleep(0.2 if quick_mode else 0.3)
                continue
            
            # Priority 5: Banners (lowest priority)
            if allow_banner and self._handle_banner_fast(serial, screen_width, screen_height, xml_content):
                result['banner'] = True
                self.logger.info("✓ Closed banner (advanced detection)")
                handled_something = True
                time.sleep(0.8)  # Chờ lâu hơn để banner biến mất hoàn toàn
                continue
            
            # If nothing was handled, exit loop early
            if not handled_something:
                break
        
        self.logger.debug(f"Popup handling complete: {result}")
        return result
    
    def _handle_start_button_fast(self, serial: str, width: int, height: int, xml_content: str) -> bool:
        """Handle 'Start' button popup - optimized version"""
        if self.config.TEXT_START in xml_content.upper() or "BAT DAU" in xml_content.upper():
            elements = self._find_by_text_from_xml(xml_content, self.config.TEXT_START, normalize=True)
            visible = [e for e in elements if e.is_visible(width, height)]
            if visible:
                cx, cy = visible[0].center
                self.adb.tap(serial, cx, cy)
                return True
        return False
    
    def _handle_ok_button_fast(self, serial: str, width: int, height: int, xml_content: str) -> bool:
        """Handle 'OK' button popup - optimized version"""
        if self.config.RESOURCE_ID_OK_BUTTON in xml_content:
            elements = self.finder.find_elements(serial, resource_id=self.config.RESOURCE_ID_OK_BUTTON)
            visible = [e for e in elements if e.is_visible(width, height)]
            if visible:
                cx, cy = visible[0].center
                self.adb.tap(serial, cx, cy)
                return True
        return False
    
    def _handle_permissions_fast(self, serial: str, width: int, height: int, xml_content: str) -> bool:
        """Handle permission dialogs - optimized version"""
        # Resource-id based deny button
        if (self.config.RESOURCE_ID_PERMISSION_MSG in xml_content
                or self.config.RESOURCE_ID_PERMISSION_DENY in xml_content):
            deny_elements = self.finder.find_elements(serial, resource_id=self.config.RESOURCE_ID_PERMISSION_DENY)
            visible = [e for e in deny_elements if e.is_visible(width, height)]
            if visible:
                cx, cy = visible[0].center
                self.adb.tap(serial, cx, cy)
                return True

        # Text fallback for permission deny buttons
        deny_texts = [self.config.TEXT_DENY, "Deny", "Don't allow", "Dont allow"]
        for txt in deny_texts:
            elements = self._find_by_text_from_xml(xml_content, txt, normalize=True)
            visible = [e for e in elements if e.is_visible(width, height)]
            if visible:
                cx, cy = visible[0].center
                self.adb.tap(serial, cx, cy)
                return True
        return False

    def _handle_in_app_blockers(self, serial: str, width: int, height: int, xml_content: str) -> bool:
        """Handle in-app blockers like banned notices (NOT permission - that's handled separately)."""
        xml_norm = normalize_text(xml_content)
        keyword_groups = [
            {
                'keywords': ['BANNED', 'BAN', 'BI KHOA', 'KHOA TAI KHOAN', 'TAM KHOA'],
                'buttons': ['OK', 'DONG', 'THOAT', 'XAC NHAN', 'DA HIEU', 'HIEU ROI'],
            },
        ]
        for group in keyword_groups:
            if any(keyword in xml_norm for keyword in group['keywords']):
                for btn_text in group['buttons']:
                    elements = self._find_by_text_from_xml(xml_content, btn_text, normalize=True)
                    visible = [e for e in elements if e.is_visible(width, height)]
                    if visible:
                        cx, cy = visible[0].center
                        self.adb.tap(serial, cx, cy)
                        return True
        return False

    def _handle_dialog_fast(self, serial: str, width: int, height: int, xml_content: str) -> bool:
        """Handle agreement/confirmation dialogs (Terms of Service, etc.) - optimized version"""
        if self.config.RESOURCE_ID_DIALOG_TITLE in xml_content:
            self.logger.debug("Found dialog title, looking for Agree/Confirm button...")
            button_elements = self.finder.find_elements(serial, resource_id=self.config.RESOURCE_ID_DIALOG_POSITIVE)
            visible = [e for e in button_elements if e.is_visible(width, height)]
            if visible:
                cx, cy = visible[0].center
                self.adb.tap(serial, cx, cy)
                self.logger.info("✓ Tapped 'Agree/Confirm' button (Terms of Service)")
                return True
            else:
                self.logger.warning("Dialog title found but positive button not visible")
        return False
    
    def _handle_banner_fast(self, serial: str, width: int, height: int, xml_content: str) -> bool:
        """Handle banner - Detect popup_banner_image → tap điểm close"""
        # Chỉ detect khi có popup_banner_image (chính xác nhất)
        if "popup_banner_image" not in xml_content:
            return False
        
        self.logger.info("✓ Detected banner (popup_banner_image) → Closing...")
        
        # Điểm close chuẩn (0.881, 0.206)
        close_x = int(width * 0.881)
        close_y = int(height * 0.206)
        
        self.logger.info(f"Tapping close button at ({close_x}, {close_y})...")
        self.adb.tap(serial, close_x, close_y)
        time.sleep(1.5)  # Chờ animation
        
        return True
    
    def _find_by_text_from_xml(self, xml_content: str, target_text: str, normalize: bool = True) -> List[UIElement]:
        """Find elements by text from XML string (no additional dump)"""
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError:
            return []
        
        target_norm = normalize_text(target_text) if normalize else target_text
        results = []
        
        for node in root.iter():
            for attr in ("text", "content-desc"):
                value = node.attrib.get(attr, "")
                if not value:
                    continue
                value_norm = normalize_text(value) if normalize else value
                if target_norm in value_norm:
                    bounds = parse_bounds(node.attrib.get("bounds", ""))
                    if bounds:
                        results.append(UIElement(
                            bounds=bounds,
                            text=node.attrib.get('text', ''),
                            content_desc=node.attrib.get('content-desc', '')
                        ))
        return results
    
    def handle_captcha(self, serial: str) -> bool:
        """
        Detect CAPTCHA and pause for manual intervention.
        
        Args:
            serial: Device serial number
            
        Returns:
            True if CAPTCHA was detected
        """
        xml_content = self.adb.dump_ui_hierarchy(serial)
        
        # Check for CAPTCHA indicators (based on actual activity and UI elements)
        captcha_indicators = [
            self.config.ACTIVITY_CAPTCHA,  # WebCaptchaPopupActivity
            "WebCaptchaPopupActivity",
            "android.widget.FrameLayout[2]/android.widget.LinearLayout[1]",
            "nhập các ký tự",
            "captcha",
            "verification",
            "xác thực"
        ]
        
        xml_lower = xml_content.lower()
        if any(indicator.lower() in xml_lower for indicator in captcha_indicators):
            self.logger.warning("\n" + "="*60)
            self.logger.warning("⚠️⚠️⚠️ CAPTCHA DETECTED! ⚠️⚠️⚠️")
            self.logger.warning("Please solve the CAPTCHA on the device NOW!")
            self.logger.warning("="*60)
            print("\a")  # System beep
            input(">>> After solving CAPTCHA, press ENTER to continue...")
            self.logger.info("Continuing automation...")
            time.sleep(1)  # Brief pause after user input
            return True
        
        return False


# ============================================================================
# SMS CLIENT MODULE
# ============================================================================

class SMSClient:
    """
    Client for interacting with 3rd-party OTP/SMS rental service API.
    Handles phone number rental and OTP code retrieval with retry mechanism.
    """
    
    def __init__(self, api_url: str, api_key: str):
        """
        Initialize SMS client.
        
        Args:
            api_url: Base URL of the SMS service API
            api_key: API authentication key
        """
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({'X-API-Key': api_key} if api_key else {})
        self.logger = AutomationLogger("SMSClient")
    
    def rent_number(self, service: str = "otissim_v4", carrier: str = "random") -> Tuple[Optional[str], Optional[str]]:
        """
        Rent a phone number for OTP reception.
        
        Args:
            service: Service type (default: otissim_v4)
            carrier: Carrier preference (default: random)
            
        Returns:
            Tuple of (session_id, phone_number) or (None, None) if failed
        """
        url = f"{self.api_url}/api/phone-rental/start"
        payload = {
            "service": service,
            "carrier": carrier
        }
        
        try:
            self.logger.info(f"Requesting phone number from {url}...")
            response = self.session.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            session_id = data.get("sessionId")
            phone_number = data.get("phoneNumber")  # API trả về phoneNumber, không phải number
            
            if session_id and phone_number:
                # Bỏ prefix 84 nếu có, Shopee cần format không có mã vùng
                if phone_number.startswith("84"):
                    phone_number = phone_number[2:]  # 84392541030 -> 392541030
                
                self.logger.info(f"✓ Rented number: {phone_number} (Session: {session_id})")
                return session_id, phone_number
            else:
                self.logger.error(f"Invalid API response: {data}")
                return None, None
                
        except requests.RequestException as e:
            self.logger.error(f"Failed to rent number: {e}")
            return None, None
        except Exception as e:
            self.logger.error(f"Unexpected error during number rental: {e}")
            return None, None
    
    def get_otp(self, session_id: str, max_retries: int = 12, retry_interval: int = 5) -> Optional[str]:
        """
        Retrieve OTP code with polling mechanism.
        
        Args:
            session_id: Session ID from rent_number()
            max_retries: Maximum number of polling attempts
            retry_interval: Seconds between attempts
            
        Returns:
            OTP code string or None if not received
        """
        url = f"{self.api_url}/api/phone-rental/get-otp"
        params = {"sessionId": session_id}
        
        self.logger.info(f"Waiting for OTP (max {max_retries * retry_interval}s)...")
        
        for attempt in range(1, max_retries + 1):
            try:
                response = self.session.get(url, params=params, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                otp = data.get("otp")
                
                if otp:
                    self.logger.info(f"✓ Received OTP: {otp}")
                    return otp
                
                self.logger.debug(f"OTP not ready yet ({attempt}/{max_retries})...")
                time.sleep(retry_interval)
                
            except requests.RequestException as e:
                self.logger.warning(f"API request failed (attempt {attempt}): {e}")
                time.sleep(retry_interval)
            except Exception as e:
                self.logger.error(f"Unexpected error getting OTP: {e}")
                time.sleep(retry_interval)
        
        self.logger.error("Failed to receive OTP within timeout period")
        return None


# ============================================================================
# SHOPEE CAPTCHA SOLVER
# ============================================================================

class ShopeeCaptchaSolver:
    """
    Shopee Slider Captcha solver using Achicaptcha API.
    Handles captcha detection, image capture, API interaction, and swipe execution.
    """
    
    def __init__(self, api_key: str):
        """
        Initialize captcha solver.
        
        Args:
            api_key: Achicaptcha API key
        """
        self.api_key = api_key
        self.api_url = "https://api.achicaptcha.com"
        self.logger = AutomationLogger("CaptchaSolver")
        
    def solve_captcha(self, mask_base64: str, bg_base64: str, sub_type: int = 0) -> Optional[str]:
        """
        Solve Shopee captcha using Achicaptcha API.
        
        Args:
            mask_base64: Base64 encoded mask image (puzzle piece)
            bg_base64: Base64 encoded background image
            sub_type: Captcha type (0: slider captcha)
            
        Returns:
            X coordinate as string, or None if failed
        """
        try:
            # Step 1: Create task
            create_url = f"{self.api_url}/createTask"
            create_payload = {
                "clientKey": self.api_key,
                "task": {
                    "type": "ShopeeCaptchaTask",
                    "image": f"{mask_base64}|{bg_base64}",
                    "subType": sub_type
                }
            }
            
            self.logger.info("Creating captcha task...")
            response = requests.post(create_url, json=create_payload, timeout=30)
            result = response.json()
            
            if result.get("errorId") != 0:
                self.logger.error(f"Failed to create task: {result.get('errorDescription', 'Unknown error')}")
                return None
            
            task_id = result.get("taskId")
            self.logger.info(f"Task created: {task_id}")
            
            # Step 2: Poll for result
            get_result_url = f"{self.api_url}/getTaskResult"
            max_attempts = 60  # 60 * 2s = 120s timeout
            
            for attempt in range(max_attempts):
                time.sleep(2)  # Wait 2 seconds between polls
                
                get_payload = {
                    "clientKey": self.api_key,
                    "taskId": task_id
                }
                
                response = requests.post(get_result_url, json=get_payload, timeout=30)
                result = response.json()
                
                error_id = result.get("errorId")
                status = result.get("status")
                
                # Success
                if error_id == 0 and status == "ready":
                    solution = result.get("solution")
                    self.logger.info(f"✓ Captcha solved: {solution}")
                    return solution
                
                # Still processing
                if error_id == 1:
                    self.logger.debug(f"Processing... ({attempt + 1}/{max_attempts})")
                    continue
                
                # Error
                if error_id not in [0, 1]:
                    self.logger.error(f"Task failed: {result.get('errorDescription', 'Unknown error')}")
                    return None
            
            self.logger.error("Captcha solving timeout")
            return None
            
        except requests.RequestException as e:
            self.logger.error(f"API request failed: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error solving captcha: {e}")
            return None
    
    def capture_and_solve(self, adb: 'ADBController', serial: str, screen_width: int, screen_height: int) -> Optional[int]:
        """
        Capture captcha images from device and solve using API.
        
        Args:
            adb: ADB controller instance
            serial: Device serial number
            screen_width: Device screen width
            screen_height: Device screen height
            
        Returns:
            X coordinate in pixels, or None if failed
        """
        try:
            import base64
            from io import BytesIO
            from PIL import Image
            
            self.logger.info("Capturing captcha screenshot...")
            
            # Take screenshot
            screenshot_path = f"/sdcard/captcha_screenshot.png"
            adb.shell(serial, ["screencap", "-p", screenshot_path])
            
            # Pull screenshot to local
            local_path = "captcha_temp.png"
            adb._execute(["-s", serial, "pull", screenshot_path, local_path])
            
            # Load image
            img = Image.open(local_path)
            
            # TODO: Crop mask and background based on captcha element bounds
            # For now, assume full screen (you need to detect captcha bounds)
            # This is a placeholder - bạn cần tìm bounds của mask và background
            
            # Example: Crop top half as mask, bottom half as bg (ADJUST THIS!)
            width, height = img.size
            mask_img = img.crop((0, 0, width, height // 2))
            bg_img = img.crop((0, height // 2, width, height))
            
            # Convert to base64
            def image_to_base64(image):
                buffered = BytesIO()
                image.save(buffered, format="PNG")
                return base64.b64encode(buffered.getvalue()).decode('utf-8')
            
            mask_base64 = image_to_base64(mask_img)
            bg_base64 = image_to_base64(bg_img)
            
            self.logger.info("Images converted to Base64, sending to API...")
            
            # Solve captcha
            solution = self.solve_captcha(mask_base64, bg_base64)
            
            if solution:
                # Parse X coordinate
                x_coord = int(solution.split(',')[0]) if ',' in solution else int(solution)
                self.logger.info(f"Captcha X coordinate: {x_coord}")
                
                # Clean up
                os.remove(local_path)
                adb.shell(serial, ["rm", screenshot_path])
                
                return x_coord
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to capture and solve captcha: {e}")
            return None
    
    def perform_swipe(self, adb: 'ADBController', serial: str, x_api: int, 
                     slider_bounds: Tuple[int, int, int, int],
                     image_width: int, screen_width: int):
        """
        Perform swipe action with proper scaling and human-like behavior.
        
        Args:
            adb: ADB controller instance
            serial: Device serial number
            x_api: X coordinate from API (based on image size)
            slider_bounds: (left, top, right, bottom) of slider element
            image_width: Width of image sent to API
            screen_width: Device screen width
        """
        try:
            # Calculate scale ratio
            slider_width = slider_bounds[2] - slider_bounds[0]
            scale_ratio = slider_width / image_width
            
            # Calculate actual swipe distance on screen
            x_swipe = int(x_api * scale_ratio)
            
            # Get slider center position
            start_x = slider_bounds[0] + 20  # Start from left edge + small offset
            start_y = (slider_bounds[1] + slider_bounds[3]) // 2  # Middle Y
            
            end_x = start_x + x_swipe
            end_y = start_y + random.randint(-5, 5)  # Random Y variation
            
            # Random duration (human-like speed)
            duration = random.randint(500, 1000)  # 500-1000ms
            
            self.logger.info(f"Swiping from ({start_x}, {start_y}) to ({end_x}, {end_y}) in {duration}ms")
            
            # Perform swipe with curve (more human-like)
            self._swipe_with_curve(adb, serial, start_x, start_y, end_x, end_y, duration)
            
            self.logger.info("✓ Swipe completed")
            
        except Exception as e:
            self.logger.error(f"Failed to perform swipe: {e}")
    
    def _swipe_with_curve(self, adb: 'ADBController', serial: str, 
                         start_x: int, start_y: int, end_x: int, end_y: int, duration: int):
        """
        Perform swipe with slight curve to mimic human behavior.
        """
        # Simple curve: add midpoint with Y offset
        mid_x = (start_x + end_x) // 2
        mid_y = (start_y + end_y) // 2 + random.randint(-10, 10)
        
        # For simplicity, use basic swipe (uiautomator2 supports bezier curves in some versions)
        # You can enhance this with touch.down -> move -> up sequence
        adb.swipe(serial, start_x, start_y, end_x, end_y, duration)


# ============================================================================
# DEVICE STATE MANAGER
# ============================================================================

class DeviceStateManager:
    """
    Manages device state changes through PChanger API.
    Mock implementation for device info randomization and state changes.
    """
    
    def __init__(self, base_url: str, device_key: str):
        """
        Initialize device state manager.
        
        Args:
            base_url: PChanger API base URL
            device_key: Device authentication key
        """
        self.base_url = base_url.rstrip("/")
        self.device_key = device_key
        self.session = requests.Session()
        self.logger = AutomationLogger("DeviceStateManager")
    
    def _check_status(self, data: Dict[str, Any]) -> bool:
        """Check if API response status is OK"""
        status = data.get("status", False)
        if isinstance(status, str):
            return status.lower() == "true"
        return bool(status)
    
    def _api_get(self, endpoint: str, params: Optional[Dict] = None, 
                expect_status: bool = True) -> Dict[str, Any]:
        """
        Make GET request to PChanger API with retry on 'device busy'.
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            expect_status: Whether to check status field
            
        Returns:
            API response data
        """
        url = f"{self.base_url}{endpoint}"
        
        while True:
            try:
                response = self.session.get(url, params=params, timeout=15)
                response.raise_for_status()
                data = response.json()
                
                # Retry if device is busy
                if expect_status and not self._check_status(data):
                    if data.get("note") == "device busy":
                        self.logger.debug("Device busy, retrying in 2s...")
                        time.sleep(2)
                        continue
                
                return data
                
            except requests.RequestException as e:
                self.logger.error(f"API request failed: {e}")
                raise
    
    def get_device_serial(self) -> Optional[str]:
        """
        Get ADB serial number for the device.
        
        Returns:
            Device serial number or None
        """
        try:
            data = self._api_get(f"/dev/{self.device_key}/device")
            if not self._check_status(data):
                self.logger.error(f"get_device failed: {data.get('note')}")
                return None
            
            serial = data.get("adb")
            self.logger.info(f"Retrieved device serial: {serial}")
            return serial
            
        except Exception as e:
            self.logger.error(f"Failed to get device serial: {e}")
            return None
    
    def randomize_device_info(self) -> bool:
        """
        Randomize device information (IMEI, Android ID, etc.).
        
        Returns:
            True if successful
        """
        try:
            self.logger.info("Randomizing device information...")
            data = self._api_get(f"/dev/{self.device_key}/random")
            
            if not self._check_status(data):
                self.logger.error(f"Random info failed: {data.get('note')}")
                return False
            
            self.logger.info("✓ Device info randomized")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to randomize device info: {e}")
            return False
    
    def change_device_state(self) -> bool:
        """
        Trigger device state change (causes reboot).
        
        Returns:
            True if change initiated successfully
        """
        try:
            self.logger.info("Initiating device state change...")
            data = self._api_get(f"/dev/{self.device_key}/change")
            
            if not self._check_status(data):
                self.logger.error(f"Change info failed: {data.get('note')}")
                return False
            
            self.logger.info("✓ Device state change initiated")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to change device state: {e}")
            return False
    
    def backup_device(self, backup_name: str) -> bool:
        """
        Create device backup.
        
        Args:
            backup_name: Name for the backup
            
        Returns:
            True if backup initiated successfully
        """
        try:
            self.logger.info(f"Creating backup: {backup_name}")
            data = self._api_get(f"/dev/{self.device_key}/backup", 
                               params={"name": backup_name})
            
            if not self._check_status(data):
                self.logger.error(f"Backup failed: {data.get('note')}")
                return False
            
            self.logger.info(f"✓ Backup created: {backup_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create backup: {e}")
            return False
    
    def list_backups(self) -> List[str]:
        """
        List all available backups.
        
        Returns:
            List of backup names
        """
        try:
            data = self._api_get("/list_backup", expect_status=False)
            if isinstance(data, list):
                return data
            return []
        except Exception:
            return []


# ============================================================================
# SHOPEE AUTOMATION MODULE
# ============================================================================

class ShopeeAutomation:
    """
    Main automation orchestrator for Shopee app testing.
    Implements complete user onboarding and browsing flow.
    """
    
    def __init__(self, adb: ADBController, sms_client: SMSClient, 
                device_manager: DeviceStateManager, config: Config):
        """
        Initialize Shopee automation.
        
        Args:
            adb: ADB controller instance
            sms_client: SMS client for OTP
            device_manager: Device state manager
            config: Configuration object
        """
        self.adb = adb
        self.sms = sms_client
        self.device = device_manager
        self.config = config
        self.logger = AutomationLogger("ShopeeAutomation")
        
        self.serial: Optional[str] = None
        self.screen_width: int = 1080
        self.screen_height: int = 1920
        
        # Initialize helper modules
        self.element_finder = UIElementFinder(adb)
        self.popup_handler = PopupHandler(adb, self.element_finder, config)
        self.captcha_solver = ShopeeCaptchaSolver(config.CAPTCHA_API_KEY)
        self.registration = RegistrationFlow(self)
        
        # Popup monitoring state (for parallel popup checking)
        self._popup_monitor_active = False
        self._popup_monitor_lock = threading.Lock()
        self._action_paused = threading.Event()
        self._action_paused.set()  # Initially not paused (set = can continue)
        self._permission_closed = False
        self._banner_closed = False
    
    def connect_device(self) -> bool:
        """
        Establish connection to the device.
        
        Returns:
            True if connection successful
        """
        self.logger.section("Device Connection")
        
        # Get device serial from API
        self.serial = self.device.get_device_serial()
        if not self.serial:
            self.logger.error("Failed to get device serial")
            return False
        
        # Wait for device to be ready
        if not self.adb.wait_for_device(self.serial, timeout=180):
            self.logger.error("Device not ready")
            return False
        
        # Get screen dimensions
        self.screen_width, self.screen_height = self.adb.get_screen_size(self.serial)
        self.logger.info(f"Screen size: {self.screen_width}x{self.screen_height}")
        
        return True
    
    def wait_for_app_installation(self) -> bool:
        """
        Wait for Shopee app to be installed.
        
        Returns:
            True if app is installed
        """
        # Quick check first - app might already be installed
        if self.adb.is_app_installed(self.serial, self.config.APP_PACKAGE):
            self.logger.info("✓ Shopee app already installed")
            return True
        
        self.logger.info("Waiting for Shopee app installation...")
        return self.adb.wait_for_app_installation(
            self.serial, 
            self.config.APP_PACKAGE,
            timeout=self.config.PACKAGE_INSTALL_TIMEOUT
        )
    
    def launch_app_and_handle_popups(self):
        """
        Launch Shopee app, handle START/OK, refresh once, then wait for permission/banner.
        
        """
        self.logger.info("Launching Shopee app...")
        
        # Unlock screen first
        self.adb.unlock_screen(self.serial)
        time.sleep(0.2)
        
        # Launch app
        self.adb.launch_app(self.serial, self.config.APP_PACKAGE)
        time.sleep(random.uniform(2.0, 2.5))  # Chờ app load
        
        # Handle START/OK first, then refresh and wait for permission/banner.
        self.logger.info("Handling START/OK popup...")
        result = self.popup_handler.handle_all_popups(
            self.serial,
            self.screen_width,
            self.screen_height,
            max_attempts=2,
            quick_mode=False
        )

        if result.get('start_button') or result.get('ok_button'):
            self.logger.info("Waiting 0.9s after START/OK...")
            time.sleep(0.9)
            self._pull_to_refresh()

        self.logger.info("Handling popups until permission & banner closed...")
        self._handle_popups_until_cleared()
    
    def simulate_browsing(self):
        """Simulate user browsing behavior"""
        self.logger.info("Simulating user browsing...")
        
        # Random scrolling and product viewing
        num_browse_cycles = 2
        
        for cycle in range(num_browse_cycles):
            self.logger.info(f"Browse cycle {cycle + 1}/{num_browse_cycles}")
            
            # Swipe to view more products
            num_swipes = 2
            for _ in range(num_swipes):
                self._random_swipe_up()
                time.sleep(random.uniform(0.25, 0.4))  # Reduced from 0.3-0.5
            
            # Quick popup check (only if needed)
            self.popup_handler.handle_all_popups(
                self.serial, 
                self.screen_width, 
                self.screen_height,
                max_attempts=1,
                quick_mode=True
            )
            
            # Click on a product (visible on screen)
            self._click_visible_product()

            # Handle popups that may appear after entering product
            self.popup_handler.handle_all_popups(
                self.serial,
                self.screen_width,
                self.screen_height,
                max_attempts=1,
                quick_mode=True
            )
            view_time = random.uniform(0.8, 1.5)  # Reduced from 1.0-2.0
            self.logger.info(f"Viewing product for {view_time:.8f}s...")
            time.sleep(view_time)
            
            # Go back
            self.adb.press_keycode(self.serial, 4)  # BACK button
            time.sleep(random.uniform(0.25, 0.5))  # Reduced from 0.3-0.6
            
            # Quick popup check
            self.popup_handler.handle_all_popups(
                self.serial, 
                self.screen_width, 
                self.screen_height,
                max_attempts=1,
                quick_mode=True
            )
    
    def _random_swipe_up(self):
        """Perform random upward swipe with minimum length"""
        x = random.randint(int(self.screen_width * 0.3), int(self.screen_width * 0.7))
        y1 = random.randint(int(self.screen_height * 0.65), int(self.screen_height * 0.85))
        min_len = int(self.screen_height * 0.35)
        max_len = int(self.screen_height * 0.55)
        swipe_len = random.randint(min_len, max_len)
        y2 = max(int(self.screen_height * 0.15), y1 - swipe_len)
        duration = random.randint(300, 450)
        self.logger.debug(f"Swiping up: ({x}, {y1}) -> ({x}, {y2})")
        self.adb.swipe(self.serial, x, y1, x, y2, duration)
    
    def _random_swipe_down(self):
        """Perform random downward swipe (pull to refresh)"""
        x = random.randint(int(self.screen_width * 0.3), int(self.screen_width * 0.7))
        y1 = random.randint(int(self.screen_height * 0.25), int(self.screen_height * 0.35))
        y2 = random.randint(int(self.screen_height * 0.7), int(self.screen_height * 0.8))
        duration = random.randint(300, 450)
        self.logger.debug(f"Swiping down: ({x}, {y1}) -> ({x}, {y2})")
        self.adb.swipe(self.serial, x, y1, x, y2, duration)

    def _pull_to_refresh(self):
        """Perform a stronger pull-to-refresh gesture"""
        x = int(self.screen_width * 0.5)
        y1 = int(self.screen_height * 0.2)
        y2 = int(self.screen_height * 0.75)
        duration = 900
        self.logger.info(f"Pull to refresh: ({x}, {y1}) -> ({x}, {y2})")
        self.adb.swipe(self.serial, x, y1, x, y2, duration)
    
    def _click_product_area(self):
        """Click in the typical product display area"""
        x = int(self.screen_width * 0.5)
        y = int(self.screen_height * 0.6)
        self.adb.tap(self.serial, x, y)
    
    def _click_visible_product(self):
        """Click a product using fixed random positions to avoid robot checks"""
        positions = [
            (0.146, 0.175),
            (0.331, 0.177),
            (0.702, 0.176),
            (0.913, 0.177),
        ]
        pos_x, pos_y = random.choice(positions)
        for idx in range(1, 3):
            tap_x = int(self.screen_width * pos_x)
            tap_y = int(self.screen_height * pos_y)
            self.logger.info(f"Tapping product {idx}/2 at ({tap_x}, {tap_y})...")
            self.adb.tap(self.serial, tap_x, tap_y)
            time.sleep(0.6)

    def _find_clickable_in_product_area(self, xml_content: str) -> List:
        """Find clickable elements in the typical product display area"""
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError:
            return []
        
        results = []
        # Product area: typically y between 35% and 85% of screen, x between 5% and 95%
        min_y = int(self.screen_height * 0.35)
        max_y = int(self.screen_height * 0.85)
        min_x = int(self.screen_width * 0.05)
        max_x = int(self.screen_width * 0.95)
        
        for node in root.iter():
            clickable = node.attrib.get("clickable", "false") == "true"
            if not clickable:
                continue
            
            bounds = parse_bounds(node.attrib.get("bounds", ""))
            if not bounds:
                continue
            
            x1, y1, x2, y2 = bounds
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2
            
            # Check if in product area
            if min_x <= cx <= max_x and min_y <= cy <= max_y:
                # Skip very small elements (icons, buttons)
                width = x2 - x1
                height = y2 - y1
                if width > 100 and height > 100:  # Reasonable product card size
                    results.append(UIElement(
                        bounds=bounds,
                        text=node.attrib.get('text', ''),
                        content_desc=node.attrib.get('content-desc', '')
                    ))
        
        return results
    
    def navigate_to_login_screen(self):
        """Navigate to the login screen via the Notification tab."""
        return self.registration.navigate_to_login_screen()

    def perform_registration_flow(self):
        """Run the separated registration flow."""
        return self.registration.perform_registration_flow()

    def _check_popups(self):
        """Helper: Check và xử lý popup (permission) - KHÔNG check banner ở đây"""
        self.popup_handler.handle_all_popups(
            self.serial, 
            self.screen_width, 
            self.screen_height,
            max_attempts=2,
            quick_mode=True
        )

    def run_full_workflow(self) -> bool:
        """
        Execute the complete automation workflow.
        
        Flow: Mở app → Handle popup → Lướt → Nhấn sản phẩm (lướt 1-2 lần) → Back 
        → Nhấn tọa độ → Vuốt xuống → Chờ 3s → Close app → Mở lại 
        → Lướt → Nhấn sản phẩm (lướt 1 lần) → Back → Back → Ready for registration
        
        Returns:
            True if workflow completed successfully
        """
        try:
            # Clear app data before first launch
            self.logger.info("="*60)
            self.logger.info("Clearing Shopee app data before first launch...")
            self.logger.info("="*60)
            self.adb.shell(self.serial, ["pm", "clear", self.config.APP_PACKAGE])
            time.sleep(2)

            # Step 1: Launch app, handle START/OK, refresh, then wait for permission/banner
            self.logger.info("="*60)
            self.logger.info("Step 1: Launching Shopee and handling START/OK popup...")
            self.logger.info("="*60)
            self.launch_app_and_handle_popups()
            
            # Step 2: Lướt (2 lần)
            self.logger.info("="*60)
            self.logger.info("Step 2: Scrolling...")
            self.logger.info("="*60)
            num_swipes = 2
            self.logger.info(f"Swiping {num_swipes} times...")
            for i in range(num_swipes):
                self.logger.info(f"Swipe {i+1}/{num_swipes}...")
                self._random_swipe_up()
                time.sleep(random.uniform(0.3, 0.5))
            
            # Step 3: Nhấn sản phẩm (lướt 2 lần trong đó), back
            self.logger.info("="*60)
            self.logger.info("Step 3: Click product, scroll inside, back...")
            self.logger.info("="*60)
            self._click_product_scroll_and_back(swipes_inside=2)
            
            # Step 4: Nhấn tọa độ (0.097, 0.91)
            self.logger.info("="*60)
            self.logger.info("Step 4: Tapping at (0.097, 0.91)...")
            self.logger.info("="*60)
            tap_x = int(self.screen_width * 0.097)
            tap_y = int(self.screen_height * 0.91)
            self.logger.info(f"Tapping at ({tap_x}, {tap_y})...")
            self.adb.tap(self.serial, tap_x, tap_y)
            time.sleep(1)
            
            # Step 5: Vuốt xuống (pull to refresh)
            self.logger.info("="*60)
            self.logger.info("Step 5: Swiping down (pull to refresh)...")
            self.logger.info("="*60)
            self._random_swipe_down()
            
            # Step 6: Chờ 3.2s
            self.logger.info("Waiting...")
            time.sleep(random.uniform(5, 5.5))
            
            # Step 7: Close app hoàn toàn
            self.logger.info("="*60)
            self.logger.info("Step 7: Closing app completely...")
            self.logger.info("="*60)
            self.adb.shell(self.serial, ["am", "force-stop", self.config.APP_PACKAGE])
            time.sleep(2)
            
            # Step 8: Mở lại app và handle popup (banner + permission)
            self.logger.info("="*60)
            self.logger.info("Step 8: Relaunching app (skip wait for permission/banner)...")
            self.logger.info("="*60)
            self.adb.unlock_screen(self.serial)
            time.sleep(0.2)
            self.adb.launch_app(self.serial, self.config.APP_PACKAGE)
            time.sleep(random.uniform(2.0, 3.0))
            # Quick popup check only (no wait for permission/banner)
            self.logger.info("Quick popup check (no wait for permission/banner)...")
            self.popup_handler.handle_all_popups(
                self.serial,
                self.screen_width,
                self.screen_height,
                max_attempts=1,
                quick_mode=True
            )
            
            # Step 9: Lướt (2-3 lần)
            self.logger.info("="*60)
            self.logger.info("Step 9: Scrolling after relaunch...")
            self.logger.info("="*60)
            num_swipes = random.randint(2, 3)
            self.logger.info(f"Swiping {num_swipes} times...")
            for i in range(num_swipes):
                self.logger.info(f"Swipe {i+1}/{num_swipes}...")
                self._random_swipe_up()
                time.sleep(random.uniform(0.3, 0.5))
            
            # Step 10: Nhấn sản phẩm (lướt 1-2 lần), back
            self.logger.info("="*60)
            self.logger.info("Step 10: Click product, scroll 1-2 times, back...")
            self.logger.info("="*60)
            self._click_product_scroll_and_back(swipes_inside=random.randint(1, 2))
            
            # Step 11: Ready for registration (Notification tab)
            self.logger.info("="*60)
            self.logger.info("Step 11: Ready to open Notification tab for registration (see registration_flow.py).")
            self.logger.info("="*60)

            # Step 12: Tap, swipe random 1-2 times, then tap mid-left/right
            self.logger.info("="*60)
            self.logger.info("Step 12: Tapping (0.49, 0.911), swiping 1-2 times, then tapping mid-left/right...")
            self.logger.info("="*60)
            tap_x = int(self.screen_width * 0.49)
            tap_y = int(self.screen_height * 0.911)
            self.logger.info(f"Tapping at ({tap_x}, {tap_y})...")
            self.adb.tap(self.serial, tap_x, tap_y)
            time.sleep(random.uniform(4.0, 5.0))

            num_swipes = random.randint(1, 2)
            self.logger.info(f"Swiping {num_swipes} time(s)...")
            for i in range(num_swipes):
                self.logger.info(f"Swipe {i+1}/{num_swipes}...")
                self._random_swipe_up()
                time.sleep(random.uniform(0.3, 0.5))

            tap_x = int(self.screen_width * 0.226)
            tap_y = int(self.screen_height * 0.97)
            self.logger.info(f"Tapping at ({tap_x}, {tap_y}) (back)...")
            self.adb.tap(self.serial, tap_x, tap_y)
            time.sleep(0.3)

            tap_x = int(self.screen_width * 0.288)
            tap_y = int(self.screen_height * 0.909)
            self.logger.info(f"Tapping at ({tap_x}, {tap_y})...")
            self.adb.tap(self.serial, tap_x, tap_y)
            self.logger.info("Waiting 10s...")
            time.sleep(10.0)

            tap_x = int(self.screen_width * 0.7)
            tap_y = int(self.screen_height * 0.91)
            max_taps = 4
            prompt_handled = False
            for i in range(3):
                self.logger.info(f"Tapping at ({tap_x}, {tap_y})...")
                self.adb.tap(self.serial, tap_x, tap_y)
                time.sleep(2.0)

            # Start checking after the 3rd tap
            prompt_handled = self._tap_signup_prompt_if_present()

            # If not visible yet, tap more (max 4 total)
            extra_taps = max_taps - 3
            while not prompt_handled and extra_taps > 0:
                self.logger.info(f"Tapping at ({tap_x}, {tap_y})...")
                self.adb.tap(self.serial, tap_x, tap_y)
                time.sleep(2.0)
                prompt_handled = self._tap_signup_prompt_if_present()
                extra_taps -= 1

            self.logger.info("Waiting 1s...")
            time.sleep(1.0)
            self.logger.info("close app...")
            self.adb.shell(self.serial, ["am", "force-stop", self.config.APP_PACKAGE])
            self.logger.info("✓ Workflow completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Workflow failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _start_popup_monitor(self):
        """
        Bắt đầu luồng B - check popup liên tục.
        Khi thấy popup → pause luồng A → đóng popup → resume luồng A.
        Dừng khi đã đóng CẢ permission VÀ banner.
        """
        self._permission_closed = False
        self._banner_closed = False
        self._popup_monitor_active = True
        permission_wait_start = time.time()
        permission_grace_seconds = 8
        
        def monitor_loop():
            self.logger.info("[Popup Monitor] Started - checking for popups...")
            
            while self._popup_monitor_active:
                # Đã đóng cả 2 → dừng monitor
                if self._permission_closed and self._banner_closed:
                    self.logger.info("[Popup Monitor] Both permission & banner closed. Stopping monitor.")
                    self._popup_monitor_active = False
                    break
                
                # Check popup
                allow_banner = self._permission_closed or (time.time() - permission_wait_start) >= permission_grace_seconds
                allow_permission = not self._permission_closed
                result = self.popup_handler.handle_all_popups(
                    self.serial, 
                    self.screen_width, 
                    self.screen_height,
                    max_attempts=1,
                    quick_mode=False,
                    prioritize_permission=True,
                    allow_banner=allow_banner,
                    allow_permission=allow_permission
                )
                
                handled_any = any(result.values())
                
                if handled_any:
                    # Pause luồng A
                    self._action_paused.clear()
                    
                    if result.get('start_button') or result.get('ok_button'):
                        self.logger.info("[Popup Monitor] ✓ START/OK handled")
                        time.sleep(1.0)
                    
                    if result.get('permission'):
                        self._permission_closed = True
                        self.logger.info("[Popup Monitor] ✓ Permission closed")
                        time.sleep(0.5)
                    
                    if result.get('banner'):
                        self._banner_closed = True
                        self.logger.info("[Popup Monitor] ✓ Banner closed")
                        time.sleep(0.5)
                    
                    # Resume luồng A
                    self._action_paused.set()
                else:
                    # Không thấy popup, chờ một chút
                    time.sleep(0.3)
            
            self.logger.info("[Popup Monitor] Stopped.")
        
        # Start monitor thread
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
    
    def _stop_popup_monitor(self):
        """Dừng luồng B"""
        self._popup_monitor_active = False
        self._action_paused.set()  # Đảm bảo luồng A không bị block
    
    def _wait_if_popup(self):
        """Luồng A gọi trước mỗi action - chờ nếu đang có popup"""
        self._action_paused.wait()  # Block nếu đang xử lý popup
    
    def _handle_popups_until_cleared(self):
        """
        Xử lý popup - BLOCKING cho đến khi đóng xong permission VÀ banner.
        Dùng khi cần chờ popup trước khi làm việc khác.
        """
        self._permission_closed = False
        self._banner_closed = False
        permission_wait_start = time.time()
        permission_grace_seconds = 8
        banner_wait_start = None
        banner_grace_seconds = 8
        max_checks = 15
        
        self.logger.info("Handling popups until permission & banner closed...")
        
        for i in range(max_checks):
            # Đã đóng cả 2 → xong
            if self._permission_closed and self._banner_closed:
                self.logger.info("✓ Both permission & banner handled.")
                return
            
            allow_banner = self._permission_closed or (time.time() - permission_wait_start) >= permission_grace_seconds
            allow_permission = not self._permission_closed
            result = self.popup_handler.handle_all_popups(
                self.serial, 
                self.screen_width, 
                self.screen_height,
                max_attempts=1,
                quick_mode=False,
                prioritize_permission=True,
                allow_banner=allow_banner,
                allow_permission=allow_permission
            )
            
            if result.get('start_button') or result.get('ok_button'):
                self.logger.info("✓ START/OK handled")
                time.sleep(1.0)
                continue
            
            if result.get('permission') and not self._permission_closed:
                self._permission_closed = True
                self.logger.info("✓ Permission closed")
                time.sleep(0.5)
                # If permission is handled, allow banner next
                permission_wait_start = time.time() - permission_grace_seconds
                banner_wait_start = time.time()
                continue
            
            if result.get('banner'):
                self._banner_closed = True
                self.logger.info("✓ Banner closed")
                time.sleep(0.5)
                continue

            if self._permission_closed and not self._banner_closed and banner_wait_start:
                if (time.time() - banner_wait_start) >= banner_grace_seconds:
                    self._banner_closed = True
                    self.logger.info("No banner detected after permission; continuing...")
                    return
            
            # Không thấy gì
            time.sleep(0.3)
        
        self.logger.info(f"Popup handling done. Permission: {self._permission_closed}, Banner: {self._banner_closed}")
    
    def _click_product_scroll_and_back(self, swipes_inside: int = 1):
        """
        Helper: Nhấn sản phẩm, lướt bên trong, back
        Không check popup ở đây - popup chỉ xuất hiện khi mở app
        
        Args:
            swipes_inside: Số lần lướt bên trong trang sản phẩm
        """
        # Nhấn sản phẩm
        self.logger.info("Clicking on a product...")
        self._click_visible_product()
        time.sleep(random.uniform(1.5, 4))  # Chờ load trang sản phẩm
        
        # Lướt bên trong sản phẩm
        self.logger.info(f"Scrolling {swipes_inside} time(s) inside product page...")
        for i in range(swipes_inside):
            time.sleep(random.uniform(1.0, 3.5))
            self._random_swipe_up()
        
        time.sleep(random.uniform(0.5, 1.0))
        
        # Back
        self.logger.info("Pressing Back...")
        self.adb.press_keycode(self.serial, 4)  # BACK
        time.sleep(random.uniform(1.0, 1.5))

    def _tap_signup_prompt_if_present(self) -> bool:
        """
        Detect signup prompts and tap specific coordinates if found.

        Returns:
            True if a prompt was detected and tapped, False otherwise
        """
        xml_content = self.adb.dump_ui_hierarchy(self.serial)
        if not xml_content.strip():
            return False

        if self.config.RESOURCE_ID_ACTIVATE_WALLET in xml_content:
            tap_x = int(self.screen_width * 0.38)
            tap_y = int(self.screen_height * 0.421)
            self.logger.info(
                "Detected activate wallet prompt; tapping at "
                f"({tap_x}, {tap_y})..."
            )
            self.adb.tap(self.serial, tap_x, tap_y)
            return True

        return False


# ============================================================================
# AUTOMATION ENGINE
# ============================================================================

class AutomationEngine:
    """
    Main automation engine coordinating all modules.
    Manages the complete test loop with device state changes.
    """
    
    def __init__(self, device_key: str, num_loops: int, backup_name_template: str, backup_start_index: int):
        """
        Initialize automation engine.
        
        Args:
            device_key: PChanger device key
            num_loops: Number of test loops to execute
            backup_name_template: Backup name template (use 'xxx' as index placeholder)
            backup_start_index: Starting index for backup names
        """
        self.device_key = device_key
        self.num_loops = num_loops
        self.backup_name_template = backup_name_template.strip()
        if not self.backup_name_template:
            self.backup_name_template = f"{time.strftime('%d_%m_%Y')}---xxx"
        self.backup_start_index = backup_start_index if backup_start_index > 0 else 1
        self.logger = AutomationLogger("AutomationEngine")
        
        # Load configuration
        self.config = Config()
        
        # Initialize modules
        self.logger.info("Initializing automation modules...")
        
        self.adb = ADBController()
        self.sms_client = SMSClient(self.config.SMS_API_URL, self.config.SMS_API_KEY)
        self.device_manager = DeviceStateManager(self.config.PCHANGER_BASE_URL, device_key)
        
        self.shopee = ShopeeAutomation(
            self.adb, 
            self.sms_client, 
            self.device_manager, 
            self.config
        )
    
    def initialize(self) -> bool:
        """
        Initialize engine (device connection happens after change/backup).
        
        Returns:
            True if initialization successful
        """
        self.logger.section("Initialization")
        self.logger.info("Initialization complete")
        return True

    def wait_for_device_reboot(self) -> bool:
        """
        Wait for device to reboot after state change.
        
        Returns:
            True if device reconnected successfully
        """
        self.logger.info("Waiting for device reboot...")
        
        # Wait for reboot to start
        time.sleep(10)
        
        # Reconnect to device
        if not self.shopee.connect_device():
            self.logger.error("Failed to reconnect after reboot")
            return False
        
        # Give system a moment to stabilize after connection
        self.logger.info("Checking system readiness...")
        time.sleep(3)
        
        # Actively check for app installation instead of blind waiting
        self.logger.info("Checking for app installation...")
        max_wait = 60  # Maximum 60 seconds to wait for app
        check_interval = 3  # Check every 3 seconds
        elapsed = 0
        
        while elapsed < max_wait:
            if self.adb.is_app_installed(self.shopee.serial, self.config.APP_PACKAGE):
                self.logger.info(f"✓ App ready after {elapsed}s")
                return True
            
            time.sleep(check_interval)
            elapsed += check_interval
            self.logger.debug(f"Still waiting for app... ({elapsed}s)")
        
        # If we get here, app might still be installing, but we'll proceed anyway
        self.logger.warning(f"App not detected after {max_wait}s, proceeding anyway")
        return True
    
    def generate_backup_name(self, loop_number: int) -> str:
        """Generate backup name using template + loop index"""
        index = self.backup_start_index + loop_number - 1
        if "xxx" in self.backup_name_template:
            return self.backup_name_template.replace("xxx", str(index))
        return f"{self.backup_name_template}---{index}"
    
    def run_loop(self, loop_number: int) -> bool:
        """
        Execute a single test loop.
        
        Args:
            loop_number: Current loop number (1-indexed)
            
        Returns:
            True if loop completed successfully
        """
        self.logger.section(f"Loop {loop_number}/{self.num_loops}")
        
        try:
            if loop_number == 1:
                self.logger.info("Loop 1: random info -> change -> wait for reboot...")
                if not self.device_manager.randomize_device_info():
                    return False
                if not self.device_manager.change_device_state():
                    return False
                if not self.wait_for_device_reboot():
                    return False
            else:
                self.logger.info("Waiting for device after previous backup...")
                if not self.wait_for_device_reboot():
                    return False
                self.logger.info("Randomizing device info before Shopee...")
                if not self.device_manager.randomize_device_info():
                    return False
            
            # Wait for Shopee to be installed
            if not self.shopee.wait_for_app_installation():
                self.logger.error("Shopee app not installed")
                return False
            
            # Run Shopee automation workflow
            if not self.shopee.run_full_workflow():
                return False

            # Randomize info then backup
            self.logger.info("Randomizing device info before backup...")
            if not self.device_manager.randomize_device_info():
                return False
            backup_name = self.generate_backup_name(loop_number)
            if not self.device_manager.backup_device(backup_name):
                self.logger.error("Backup failed")
                return False
            self.logger.info(f"Backup requested: {backup_name}")
            
            self.logger.info(f"✓ Loop {loop_number} completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Loop {loop_number} failed: {e}")
            return False
    
    def run(self) -> bool:
        """
        Run the complete automation test suite.
        
        Returns:
            True if all loops completed successfully
        """
        self.logger.section("Shopee Automation Test Suite")
        self.logger.info(f"Device Key: {self.device_key}")
        self.logger.info(f"Total Loops: {self.num_loops}")
        self.logger.info(f"Backup Template: {self.backup_name_template}")
        self.logger.info(f"Backup Start Index: {self.backup_start_index}")
        
        start_time = time.time()
        
        # Initialize
        if not self.initialize():
            self.logger.error("Initialization failed")
            return False
        
        # Run all loops
        for loop_num in range(1, self.num_loops + 1):
            if not self.run_loop(loop_num):
                self.logger.error(f"Stopping due to loop {loop_num} failure")
                return False
            
            # Small delay between loops
            if loop_num < self.num_loops:
                time.sleep(5)
        
        # Calculate elapsed time
        elapsed = time.time() - start_time
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        
        self.logger.section("Test Suite Complete")
        self.logger.info(f"✓ All {self.num_loops} loops completed successfully")
        self.logger.info(f"Total time: {minutes}m {seconds}s")
        
        return True


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point for the automation framework"""
    print("=" * 70)
    print("  Shopee Android Automation Testing Framework")
    print("  Version: 2.0 - Modular OOP Architecture")
    print("=" * 70)
    print()
    
    try:
        # Get user input
        device_key = input("Enter PChanger Device Key: ").strip()
        if not device_key:
            print("Error: Device key cannot be empty")
            return
        
        num_loops_input = input("Enter number of test loops: ").strip()
        try:
            num_loops = int(num_loops_input)
            if num_loops < 1:
                print("Error: Number of loops must be at least 1")
                return
        except ValueError:
            print("Error: Invalid number format")
            return

        default_template = f"{time.strftime('%d_%m_%Y')}---xxx"
        backup_name_template = input(
            f"Enter backup name template (default: {default_template}): "
        ).strip()

        backup_start_input = input("Enter backup start index (default: 1): ").strip()
        if backup_start_input:
            try:
                backup_start_index = int(backup_start_input)
                if backup_start_index < 1:
                    print("Error: Backup start index must be at least 1")
                    return
            except ValueError:
                print("Error: Invalid backup start index format")
                return
        else:
            backup_start_index = 1
        
        print()
        
        # Create and run automation engine
        engine = AutomationEngine(device_key, num_loops, backup_name_template, backup_start_index)
        success = engine.run()
        
        print()
        if success:
            print("✓✓✓ Automation completed successfully ✓✓✓")
        else:
            print("✗✗✗ Automation failed ✗✗✗")
        
    except KeyboardInterrupt:
        print("\n\nAutomation interrupted by user")
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
