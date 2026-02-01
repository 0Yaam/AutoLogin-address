"""
Shopee Auto Login - NiceGUI Interface
=====================================
Modern web-based UI for automated Shopee login flow.
"""

import asyncio
import sys
import os
from datetime import datetime
from typing import Optional
from nicegui import ui, app
import re
import requests
import time
import threading
import random

DEFAULT_DEVICE_KEY = "e8da52170928cf3"
ADDRESS_DEEPLINKS = [
    "https://vn.shp.ee/Y87fTfY",
    "https://vn.shp.ee/smcStgn",
    "https://vn.shp.ee/C8faVJT",
]
FASTINPUT_IME_IDS = [
    "com.github.uiautomator/.FastInputIME",
    "com.github.uiautomator.test/.FastInputIME",
]
SHOW_TAP_TOAST = False
TAP_TOAST_SECONDS = 0.7

# Thêm thư mục hiện tại vào path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import từ module test.py
try:
    from test import (
        ADBController,
        AutomationLogger,
        Config,
        DeviceStateManager,
        PopupHandler,
        UIElementFinder,
        normalize_text,
    )
    MODULES_AVAILABLE = True
    print("✅ Modules imported successfully!")
except ImportError as e:
    print(f"❌ Import error: {e}")
    MODULES_AVAILABLE = False


class LogHandler:
    """Handler để capture và hiển thị log trong UI"""
    
    def __init__(self):
        self.logs = []
        self.log_container = None
        
    def add_log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Màu sắc theo level
        colors = {
            "INFO": "#0ea5e9",
            "WARNING": "#f59e0b",
            "ERROR": "#ef4444",
            "SUCCESS": "#22c55e",
            "DEBUG": "#6366f1",
            "TAP": "#38bdf8"
        }
        color = colors.get(level, "#ffffff")
        
        log_entry = {
            "timestamp": timestamp,
            "level": level,
            "message": message,
            "color": color
        }
        self.logs.append(log_entry)
        
        # Giới hạn số log
        if len(self.logs) > 500:
            self.logs = self.logs[-500:]
            
        return log_entry
    
    def clear(self):
        self.logs = []
        
    def info(self, message: str):
        return self.add_log(message, "INFO")
        
    def warning(self, message: str):
        return self.add_log(message, "WARNING")
        
    def error(self, message: str):
        return self.add_log(message, "ERROR")
        
    def success(self, message: str):
        return self.add_log(message, "SUCCESS")

    def tap(self, message: str):
        return self.add_log(message, "TAP")


class AutoLoginFlowUI:
    """Auto Login Flow với UI integration"""
    
    def __init__(self, device_key: str, credentials: str, logger: LogHandler):
        self.device_key = device_key
        self.credentials = credentials
        self.logger = logger
        
        # Parse credentials
        self.username = ""
        self.password = ""
        self.hotmail = ""
        self._parse_credentials()
        
        if MODULES_AVAILABLE:
            self.config = Config()
            self.adb = ADBController()
            self.device_manager = DeviceStateManager(self.config.PCHANGER_BASE_URL, device_key)
            self.element_finder = UIElementFinder(self.adb)
            self.popup_handler = PopupHandler(self.adb, self.element_finder, self.config)
        
        self.serial: Optional[str] = None
        self.screen_width = 1080
        self.screen_height = 1920
        self.running = False
        self.stop_requested = False
        
    def _parse_credentials(self):
        """Parse credentials từ format: user|pass|mail_data"""
        try:
            parts = self.credentials.split('|')
            if len(parts) >= 2:
                self.username = parts[0].strip()
                self.password = parts[1].strip()
                # Phần còn lại là mail data (có thể có nhiều phần)
                if len(parts) > 2:
                    self.hotmail = '|'.join(parts[2:])
                self.logger.info(f"Parsed credentials - User: {self.username}")
                if self.hotmail:
                    # Parse mail để lấy email address
                    mail_parts = self.hotmail.split('|')
                    if mail_parts:
                        self.logger.info(f"Mail: {mail_parts[0]}")
            else:
                self.logger.error("Invalid credentials format. Expected: user|pass|mail_data")
        except Exception as e:
            self.logger.error(f"Error parsing credentials: {e}")

    def _sleep(self, seconds: float, interval: float = 0.2) -> bool:
        if seconds <= 0:
            return self.running
        end_time = time.time() + seconds
        while self.running and time.time() < end_time:
            remaining = end_time - time.time()
            time.sleep(min(interval, max(0.0, remaining)))
        return self.running

    def _tap_ratio(self, x_ratio: float, y_ratio: float, wait: float = 0.0):
        if not self.running:
            return False
        x = int(self.screen_width * x_ratio)
        y = int(self.screen_height * y_ratio)
        self.logger.info(f"Tapping at ({x_ratio:.3f}, {y_ratio:.3f}) -> ({x}, {y})")
        if MODULES_AVAILABLE:
            _tap_with_debug(self.adb, self.serial, x, y)
        if wait > 0:
            return self._sleep(wait)
        return self.running

    def _wait_for_text(self, text: str, timeout: Optional[float] = 60.0, interval: float = 1.0) -> bool:
        if not self.running:
            return False
        if not MODULES_AVAILABLE:
            return self.running
        start_time = time.time()
        while self.running:
            elements = self.element_finder.find_by_text(
                self.serial, text, exact=False, normalize=True
            )
            if elements:
                return True
            if timeout is not None and time.time() - start_time >= timeout:
                return False
            if not self._sleep(interval):
                return False
        return False

    def _wait_and_tap_resource_id(self, resource_id: str, fallback_ratio=None,
                                   timeout: float = 30.0, interval: float = 1.0) -> bool:
        if not self.running:
            return False
        if not MODULES_AVAILABLE:
            return self.running
        start_time = time.time()
        while self.running and time.time() - start_time < timeout:
            elements = self.element_finder.find_elements(
                self.serial, resource_id=resource_id
            )
            visible = [
                el for el in elements
                if el.is_visible(self.screen_width, self.screen_height)
            ]
            if visible:
                cx, cy = visible[0].center
                self.logger.info(f"Found element '{resource_id}' at ({cx}, {cy})")
                self.adb.tap(self.serial, cx, cy)
                return True
            if not self._sleep(interval):
                return False
        return False

    def fetch_shopee_link_from_mail(self, mail_data: str, retry_interval: float = 5.0) -> Optional[str]:
        """Fetch Shopee verification link from mail using API.
        
        Mail data format: email|mail_pass|refresh_token|client_id|smvmail
        """
        if not self.running:
            return None
        if not mail_data:
            self.logger.error("No mail data provided")
            return None

        try:
            parts = mail_data.split('|')
            # Format: email|mail_pass|refresh_token|client_id|smvmail
            if len(parts) < 4:
                self.logger.error("Invalid mail format: need email|mail_pass|refresh_token|client_id")
                self.logger.error(f"Got {len(parts)} parts: {parts}")
                return None

            email = parts[0].strip()           # fatoumatan2751@hotmail.com
            # parts[1] = mail password (không dùng cho API)
            refresh_token = parts[2].strip()   # M.C517_BL2.0.U.-CrXIugGyIQ2K...
            client_id = parts[3].strip()       # 9e5f94bc-e8a4-4e73-b8be-63364c29d753

            self.logger.info(f"Processing mail: {email}")
            self.logger.info(f"Client ID: {client_id}")
            self.logger.info(f"Token (first 30 chars): {refresh_token[:30]}...")

        except Exception as e:
            self.logger.error(f"Error parsing mail data: {e}")
            return None

        url = "https://tools.dongvanfb.net/api/get_messages_oauth2"
        payload = {
            "email": email,
            "refresh_token": refresh_token,
            "client_id": client_id
        }

        attempt = 0
        while self.running:
            attempt += 1
            self.logger.info(f"Attempt {attempt}: Calling mail API...")

            try:
                response = requests.post(url, json=payload, timeout=15)

                if response.status_code != 200:
                    self.logger.warning(f"HTTP error: {response.status_code}. Retrying...")
                    if not self._sleep(retry_interval):
                        return None
                    continue

                data = response.json()

                if not data.get("status") or not data.get("messages"):
                    self.logger.warning("No messages found. Retrying...")
                    if not self._sleep(retry_interval):
                        return None
                    continue

                self.logger.info(f"Found {len(data['messages'])} messages. Searching for Shopee link...")

                for msg in data['messages']:
                    html_content = msg.get('message', '')
                    
                    # Tìm link dạng 1: https://vn.shp.ee/dlink/...
                    match = re.search(r'https://vn\.shp\.ee/dlink/[a-zA-Z0-9]+', html_content)
                    if match:
                        link_shopee = match.group(0)
                        self.logger.success(f"Found Shopee link (shp.ee): {link_shopee}")
                        return link_shopee
                    
                    # Tìm link dạng 2: https://u*.ct.sendgrid.net/ls/click?upn=...
                    match = re.search(r'https://u\d+\.ct\.sendgrid\.net/ls/click\?upn=[^\s"<>]+', html_content)
                    if match:
                        link_shopee = match.group(0)
                        self.logger.success(f"Found Shopee link (sendgrid): {link_shopee}")
                        return link_shopee

                self.logger.warning("No Shopee link found. Retrying...")
                if not self._sleep(retry_interval):
                    return None

            except Exception as e:
                self.logger.warning(f"Error: {e}. Retrying...")
                if not self._sleep(retry_interval):
                    return None
        
        return None

    def connect_device(self) -> bool:
        if not MODULES_AVAILABLE:
            self.logger.warning("Modules not available - running in demo mode")
            return True
            
        self.logger.info("Waiting for device to be ready...")
        self.serial = self.device_manager.get_device_serial()
        if not self.serial:
            self.logger.error("Failed to get device serial")
            return False

        timeout = 180
        start_time = time.time()
        while self.running and time.time() - start_time < timeout:
            if self.adb.get_device_state(self.serial) == "device":
                self.logger.info(f"Device {self.serial} is ready")
                break
            if not self._sleep(1.5):
                return False

        if not self.running:
            self.logger.warning("Stop requested while waiting for device")
            return False

        if time.time() - start_time >= timeout:
            self.logger.error("Device not ready")
            return False

        self.screen_width, self.screen_height = self.adb.get_screen_size(self.serial)
        self.logger.info(f"Screen size: {self.screen_width}x{self.screen_height}")
        return True

    def open_shopee_deeplink(self, link: str) -> bool:
        """
        Mở link trực tiếp trong Shopee app bằng Deep Link.
        Không cần qua trình duyệt!
        
        Command: am start -a android.intent.action.VIEW -d "LINK" -p com.shopee.vn
        """
        if not self.running:
            return False
        if not link:
            self.logger.error("No link provided")
            return False
            
        self.logger.info(f"Opening deep link in Shopee app...")
        self.logger.info(f"Link: {link}")
        
        if MODULES_AVAILABLE:
            try:
                # Dùng deep link mở thẳng vào Shopee app
                # -p com.shopee.vn: ép mở bằng Shopee, không hỏi
                result = self.adb.shell(self.serial, [
                    "am", "start",
                    "-a", "android.intent.action.VIEW",
                    "-d", link,
                    "-p", "com.shopee.vn"  # Quan trọng: chỉ định package Shopee
                ])
                self.logger.success(f"Deep link sent to Shopee app!")
                return True
            except Exception as e:
                self.logger.error(f"Failed to open deep link: {e}")
                return False
        else:
            self.logger.info("[Demo] Would open deep link in Shopee")
            return True

    def run(self, shopee_link: str = None) -> bool:
        """Run auto login flow"""
        self.running = True
        self.stop_requested = False
        
        if not self.connect_device():
            self.running = False
            return False

        self.logger.info("Launching Shopee app...")
        if MODULES_AVAILABLE:
            self.adb.unlock_screen(self.serial)
        if not self._sleep(0.2):
            self.running = False
            return False
        if MODULES_AVAILABLE:
            self.adb.launch_app(self.serial, self.config.APP_PACKAGE)
        if not self._sleep(5.0):
            self.running = False
            return False

        if not self._tap_ratio(0.705, 0.911, wait=1.75):
            self.running = False
            return False
        if not self._tap_ratio(0.235, 0.280, wait=0.3):
            self.running = False
            return False
        
        self.logger.info(f"Entering username: {self.username}")
        if not self.running:
            self.running = False
            return False
        if MODULES_AVAILABLE:
            self.adb.input_text(self.serial, self.username)
        if not self._sleep(0.3):
            self.running = False
            return False

        if not self._tap_ratio(0.237, 0.337, wait=0.3):
            self.running = False
            return False
        self.logger.info("Entering password...")
        if not self.running:
            self.running = False
            return False
        if MODULES_AVAILABLE:
            self.adb.input_text(self.serial, self.password)
        if not self._sleep(0.3):
            self.running = False
            return False

        if not self._tap_ratio(0.509, 0.410):
            self.running = False
            return False

        # Đợi cho đến khi xuất hiện màn hình xác minh email
        self.logger.info("Waiting for email verification screen...")
        email_verify_found = self._wait_for_text(
            "Xác minh bằng liên kết Email",
            timeout=60.0,
            interval=1.0
        )
        if not self.running:
            self.running = False
            return False
        
        # Nếu không thấy text đầu, thử text thứ 2
        if not email_verify_found:
            self.logger.info("Trying alternative text...")
            email_verify_found = self._wait_for_text(
                "Để tăng cường bảo mật cho tài khoản của bạn",
                timeout=10.0,
                interval=1.0
            )
        
        if email_verify_found:
            self.logger.success("Email verification screen appeared!")
        else:
            self.logger.warning("Email verification screen not found, continuing anyway...")
        
        # Tap vào "Xác minh bằng liên kết Email"
        if not self._tap_ratio(0.283, 0.228, wait=0.5):
            self.running = False
            return False

        self.logger.info("Handling permission prompt...")
        if not self._sleep(4.0):
            self.running = False
            return False
        if not self._tap_ratio(0.48, 0.768, wait=2.0):
            self.running = False
            return False

        if not self._tap_ratio(0.275, 0.535):
            self.running = False
            return False

        self.logger.info("Waiting before fetching mail verification link...")
        if not self._sleep(6.0):
            self.running = False
            return False

        # STEP 1: Fetch link xác minh từ mail (bắt buộc)
        mail_link = None
        if self.hotmail:
            mail_link = self.fetch_shopee_link_from_mail(self.hotmail)
        
        if not self.running:
            self.running = False
            return False
            
        if mail_link:
            self.logger.success(f"Using mail verification link: {mail_link}")
            self.logger.info("Opening link in Chrome for verification...")
            
            # STEP 2: Mở Chrome xác minh mail
            if MODULES_AVAILABLE:
                self.adb.shell(self.serial, [
                    "am", "start", "-a", "android.intent.action.VIEW", 
                    "-d", mail_link
                ])
            
            # STEP 3: Xử lý Chrome First Run button (timeout 3s)
            self.logger.info("Waiting for Chrome First Run button (3s)...")
            chrome_fre_found = self._wait_and_tap_resource_id(
                "com.android.chrome:id/fre_bottom_group",
                timeout=3.0
            )
            if not self.running:
                self.running = False
                return False
            if chrome_fre_found:
                self.logger.info("Tapped Chrome First Run button")
            else:
                self.logger.info("Chrome First Run not found, skipping...")
            
            # STEP 4: Đợi dialog vị trí (timeout 6s)
            self.logger.info("Waiting for location permission dialog (6s)...")
            location_dialog_found = self._wait_for_text(
                "shopee.vn muốn sử dụng thông tin vị trí thiết bị của bạn",
                timeout=6.0
            )
            if not self.running:
                self.running = False
                return False
            if location_dialog_found:
                self.logger.info("Location dialog appeared, tapping...")
                # Tap tọa độ (0.599, 0.558)
                if not self._tap_ratio(0.599, 0.558):
                    self.running = False
                    return False
                # Delay 1s rồi tap (0.689, 0.907)
                if not self._sleep(1.0):
                    self.running = False
                    return False
                if not self._tap_ratio(0.689, 0.907):
                    self.running = False
                    return False
            else:
                self.logger.info("Location dialog not found, skipping...")
            
            # STEP 5: Đợi trang Shopee load xong (timeout 8s)
            self.logger.info("Waiting for Shopee page to load (8s)...")
            shopee_page_loaded = self._wait_for_text(
                "Shopee Việt Nam | Mua và Bán Trên Ứng Dụng Di Động Hoặc Website",
                timeout=8.0
            )
            if not self.running:
                self.running = False
                return False
            if shopee_page_loaded:
                self.logger.success("Shopee page loaded successfully!")
            else:
                self.logger.warning("Shopee page not detected, continuing anyway...")
            
            # STEP 6: Quay lại Shopee app
            self.logger.info("Returning to Shopee app...")
            if MODULES_AVAILABLE and self.running:
                self.adb.launch_app(self.serial, self.config.APP_PACKAGE)
        else:
            self.logger.warning("No mail verification link available")
        
        # STEP 7: Đợi cho đến khi xuất hiện "Xác thực Đăng nhập Nhanh" (timeout 7s)
        self.logger.info("Waiting for 'Xác thực Đăng nhập Nhanh' dialog (7s)...")
        quick_login_found = self._wait_for_text(
            "Xác thực Đăng nhập Nhanh",
            timeout=7.0,
            interval=1.0
        )
        if not self.running:
            self.running = False
            return False
        
        # Nếu không thấy text đầu tiên, thử text thứ 2
        if not quick_login_found:
            self.logger.info("Trying alternative text...")
            quick_login_found = self._wait_for_text(
                "Bật đăng nhập nhanh để đăng nhập hiệu quả hơn",
                timeout=10.0,
                interval=1.0
            )
        
        if quick_login_found:
            self.logger.success("Quick login dialog appeared!")
            # Tap tại tọa độ (0.239, 0.972)
            self.logger.info("Tapping at (0.239, 0.972) to confirm...")
            if not self._tap_ratio(0.239, 0.972):
                self.running = False
                return False
            
            # Chờ 4s
            self.logger.info("Waiting 4s after confirmation...")
            if not self._sleep(4.0):
                self.running = False
                return False
        else:
            self.logger.warning("Quick login dialog not found, continuing...")
            if not self._sleep(2.0):
                self.running = False
                return False
        
        # STEP 8: Nếu có custom deep link, mở nó
        if shopee_link:
            self.logger.info("=" * 40)
            self.logger.success(f"Opening custom deep link: {shopee_link}")
            self.open_shopee_deeplink(shopee_link)
            self.logger.info("Waiting for product to load...")
            if not self._sleep(3.0):
                self.running = False
                return False
            self.logger.success("Deep link opened successfully!")
        else:
            # Chỉ nhấn back khi không mở deep link
            if MODULES_AVAILABLE and self.running:
                self.adb.press_keycode(self.serial, 4)
            
        if not self.running:
            self.running = False
            return False
        self.logger.success("Auto login flow completed!")
        self.running = False
        return True
    
    def stop(self):
        self.stop_requested = True
        self.running = False
        self.logger.warning("Stop requested. Finishing current step...")


# ================== NiceGUI Interface ==================

# Global state
log_handler = LogHandler()
current_flow: Optional[AutoLoginFlowUI] = None
is_running = False


def create_ui():
    # Build the NiceGUI layout.

    ui.add_head_html("""
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }

        html, body {
            width: 100% !important;
            height: 100vh !important;
            margin: 0 !important;
            padding: 0 !important;
            overflow: hidden !important;
        }

        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            color: #e2e8f0;
        }

        /* Override NiceGUI default styles */
        .nicegui-content {
            width: 100% !important;
            max-width: 100% !important;
            padding: 0 !important;
            margin: 0 !important;
        }

        .q-page {
            padding: 0 !important;
        }

        .q-layout, .q-page-container, .q-page {
            width: 100% !important;
            max-width: 100% !important;
        }

        .app-container {
            width: 100% !important;
            height: 100vh;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }

        .status-badge {
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }
        .status-ready { background: rgba(34, 197, 94, 0.15); color: #4ade80; }
        .status-running { background: rgba(59, 130, 246, 0.15); color: #60a5fa; animation: pulse 2s infinite; }

        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }

        .main-content {
            flex: 1;
            display: flex;
            flex-direction: row;
            gap: 20px;
            min-height: 0;
            width: 100%;
        }

        .left-panel {
            width: 65%;
            flex-shrink: 0;
            display: flex;
            flex-direction: column;
            gap: 12px;
            overflow-y: auto;
        }

        .right-panel {
            width: 35%;
            flex-shrink: 0;
            display: flex;
            flex-direction: column;
            min-height: 0;
        }

        .card {
            background: rgba(30, 41, 59, 0.8);
            border: 1px solid rgba(148, 163, 184, 0.15);
            border-radius: 12px;
            padding: 16px;
        }

        .card-title {
            font-size: 14px;
            font-weight: 600;
            color: #f1f5f9;
            margin-bottom: 4px;
        }

        .card-hint {
            font-size: 12px;
            color: #94a3b8;
            margin-bottom: 12px;
        }

        .input-field textarea,
        .input-field input {
            width: 100%;
            background: rgba(15, 23, 42, 0.6) !important;
            border: 1px solid rgba(148, 163, 184, 0.2) !important;
            border-radius: 8px !important;
            color: #e2e8f0 !important;
            font-family: 'Consolas', monospace !important;
            font-size: 13px !important;
            padding: 10px 12px !important;
        }

        .input-field textarea:focus,
        .input-field input:focus {
            border-color: #38bdf8 !important;
            outline: none !important;
        }

        .btn-row {
            display: flex;
            gap: 10px;
            margin-top: 4px;
        }

        .link-row {
            display: flex;
            gap: 8px;
            align-items: center;
            margin-top: 8px;
        }

        .link-row .input-field {
            flex: 1;
        }

        .btn-open {
            padding: 10px 16px !important;
            background: linear-gradient(135deg, #10b981, #059669) !important;
            color: white !important;
            border: none !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
            text-transform: none !important;
            white-space: nowrap;
        }

        .btn {
            flex: 1;
            padding: 12px 20px !important;
            border: none !important;
            border-radius: 10px !important;
            font-weight: 600 !important;
            font-size: 14px !important;
            cursor: pointer;
            text-transform: none !important;
        }

        .btn-start {
            background: linear-gradient(135deg, #3b82f6, #2563eb) !important;
            color: white !important;
        }

        .btn-stop {
            background: linear-gradient(135deg, #ef4444, #dc2626) !important;
            color: white !important;
        }

        .btn-clear {
            background: transparent !important;
            border: 1px solid rgba(148, 163, 184, 0.3) !important;
            color: #94a3b8 !important;
            padding: 6px 12px !important;
            font-size: 12px !important;
        }

        .log-card {
            flex: 1;
            display: flex;
            flex-direction: column;
            min-height: 0;
        }

        .log-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }

        .log-container {
            flex: 1;
            background: #0f172a;
            border-radius: 8px;
            padding: 12px;
            font-family: 'Consolas', monospace;
            font-size: 12px;
            overflow-y: auto;
            min-height: 0;
        }

        .log-entry {
            padding: 4px 0;
            border-bottom: 1px solid rgba(148, 163, 184, 0.1);
        }

        .log-time { color: #64748b; margin-right: 8px; }
        .log-level {
            display: inline-block;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: 600;
            margin-right: 8px;
        }
        .log-INFO { background: rgba(59, 130, 246, 0.2); color: #60a5fa; }
        .log-SUCCESS { background: rgba(34, 197, 94, 0.2); color: #4ade80; }
        .log-WARNING { background: rgba(245, 158, 11, 0.2); color: #fbbf24; }
        .log-ERROR { background: rgba(239, 68, 68, 0.2); color: #f87171; }
        .log-TAP { background: rgba(56, 189, 248, 0.2); color: #7dd3fc; }

        .log-empty {
            color: #64748b;
            text-align: center;
            padding: 40px;
        }

        .log-count { color: #64748b; font-size: 12px; }

        /* NiceGUI overrides */
        .q-field--outlined .q-field__control:before { border: none !important; }
        .q-field--outlined .q-field__control:after { border: none !important; }
        .q-checkbox__label { color: #e2e8f0 !important; font-weight: 500; }
    </style>
    """)

    with ui.element('div').classes('app-container'):
        # Main content - 2 columns horizontal
        with ui.element('div').classes('main-content'):
            # Left panel - 65%
            with ui.element('div').classes('left-panel'):
                # Credentials card
                with ui.element('div').classes('card'):
                    with ui.element('div').classes('row items-center justify-between w-full'):
                        ui.html('<div class="card-title">Credentials</div>', sanitize=False)
                        status_label = ui.html('<span class="status-badge status-ready">Ready</span>', sanitize=False)
                    ui.html('<div class="card-hint">Format: user|pass|email|mail_pass|token|client_id|...</div>', sanitize=False)
                    credentials_input = ui.textarea(
                        placeholder='user|pass|email|mail_pass|token|client_id|...'
                    ).classes('input-field').props('outlined rows=3')

                # Shopee link card
                with ui.element('div').classes('card'):
                    use_custom_link = ui.checkbox('Dung link Shopee tuy chon (deep link)')
                    with ui.element('div').classes('link-row').bind_visibility_from(use_custom_link, 'value'):
                        shopee_link_input = ui.input(
                            placeholder='https://shopee.vn/... (de trong se random)'
                        ).classes('input-field').props('outlined')
                        ui.button('Open', on_click=lambda: open_deeplink_only(
                            shopee_link_input.value,
                            log_container
                        )).classes('btn-open')

                # Address card
                with ui.element('div').classes('card'):
                    add_address_checkbox = ui.checkbox('Them dia chi')
                    with ui.element('div').classes('link-row'):
                        address_input = ui.input(
                            placeholder='Nhap dia chi...'
                        ).classes('input-field').props('outlined')
                        ui.button('Add', on_click=lambda: threading.Thread(
                            target=add_address_only,
                            args=(address_input.value, log_container),
                            daemon=True,
                        ).start()).classes('btn-open')

                # Debug card
                with ui.element('div').classes('card'):
                    ui.html('<div class="card-title">Debug</div>', sanitize=False)
                    touch_debug_checkbox = ui.checkbox('Debug man hinh (show touches + pointer + toast)')
                    touch_debug_checkbox.on('update:model-value', lambda e: set_touch_debug(
                        bool(e.args),
                        log_container
                    ))

                # Buttons
                with ui.element('div').classes('btn-row'):
                    start_btn = ui.button('Start', on_click=lambda: start_flow(
                        credentials_input.value,
                        DEFAULT_DEVICE_KEY,
                        shopee_link_input.value if use_custom_link.value else None,
                        status_label, start_btn, stop_btn, log_container,
                        add_address_checkbox.value, address_input.value
                    )).classes('btn btn-start')
                    stop_btn = ui.button('Stop', on_click=lambda: stop_flow(
                        status_label, start_btn, stop_btn
                    )).classes('btn btn-stop').props('disable')

            # Right panel - 35%
            with ui.element('div').classes('right-panel'):
                with ui.element('div').classes('card log-card'):
                    with ui.element('div').classes('log-header'):
                        ui.html('<div class="card-title">Log Output</div>', sanitize=False)
                        with ui.row().classes('items-center gap-2'):
                            log_count = ui.label('0 entries').classes('log-count')
                            ui.button('Clear', on_click=lambda: clear_logs(log_container)).classes('btn btn-clear')

                    log_container = ui.html('', sanitize=False).classes('log-container')
                    ui.timer(0.5, lambda: update_logs(log_container, log_count))


def update_logs(container, count_label):
    "Update the log display."
    if not log_handler.logs:
        container.content = '<div class="log-empty">No logs yet...</div>'
        count_label.set_text('0 entries')
        return

    html_content = ""
    for log in log_handler.logs[-100:]:
        html_content += f'''
        <div class="log-entry">
            <span class="log-time">[{log['timestamp']}]</span>
            <span class="log-level log-{log['level']}">{log['level']}</span>
            <span style="color: {log['color']};">{log['message']}</span>
        </div>
        '''

    container.content = html_content
    count_label.set_text(f'{len(log_handler.logs)} entries')

    ui.run_javascript('''
        const logContainer = document.querySelector('.log-container');
        if (!logContainer) return;
        const threshold = 32; // px from bottom to keep auto-scroll
        const distanceFromBottom = logContainer.scrollHeight - logContainer.scrollTop - logContainer.clientHeight;
        if (distanceFromBottom <= threshold) {
            logContainer.scrollTop = logContainer.scrollHeight;
        }
    ''')


def clear_logs(container):
    "Clear the log output."
    log_handler.clear()
    container.content = '<div class="log-empty">Logs cleared</div>'


def _open_shopee_link(adb, serial, link: str) -> bool:
    link = (link or "").strip()
    if not link:
        return False
    adb.shell(serial, [
        "am", "start",
        "-a", "android.intent.action.VIEW",
        "-d", link,
        "-p", "com.shopee.vn",
    ])
    return True


def _tap_with_debug(adb, serial, x: int, y: int):
    adb.tap(serial, x, y)
    if SHOW_TAP_TOAST and MODULES_AVAILABLE:
        try:
            import uiautomator2 as u2
            d = u2.connect()
            d.toast(f"TAP {x},{y}", duration=TAP_TOAST_SECONDS)
        except Exception:
            pass


def set_touch_debug(enable: bool, log_container):
    "Enable/disable touch debug overlays on device (show touches + pointer location)."
    try:
        if not MODULES_AVAILABLE:
            log_handler.warning("Modules not available - demo mode")
            return
        global SHOW_TAP_TOAST
        SHOW_TAP_TOAST = bool(enable)
        adb = ADBController()
        device_manager = DeviceStateManager(Config().PCHANGER_BASE_URL, DEFAULT_DEVICE_KEY)
        serial = device_manager.get_device_serial()
        if not serial:
            log_handler.error("Failed to get device serial")
            return
        value = "1" if enable else "0"
        adb.shell(serial, ["settings", "put", "system", "show_touches", value])
        adb.shell(serial, ["settings", "put", "system", "pointer_location", value])
        state = "ON" if enable else "OFF"
        log_handler.info(f"Touch debug: {state}")
    except Exception as e:
        log_handler.error(f"Touch debug error: {e}")


def _is_fastinput_ime_installed(adb, serial) -> bool:
    code, out, _ = adb.shell(serial, ["ime", "list", "-s"])
    if code != 0:
        return False
    ime_list = [line.strip() for line in out.splitlines() if line.strip()]
    return any(ime_id in ime_list for ime_id in FASTINPUT_IME_IDS)


def _ensure_fastinput_ime(adb, serial):
    try:
        installed = _is_fastinput_ime_installed(adb, serial)
        if installed:
            log_handler.info("FastInputIME already installed.")
        else:
            log_handler.info("FastInputIME not found. Installing...")
        import uiautomator2 as u2
        d = u2.connect()
        if hasattr(d, "set_fastinput_ime"):
            d.set_fastinput_ime(True)
        elif hasattr(d, "set_input_ime"):
            d.set_input_ime(True)
        else:
            log_handler.warning("FastInputIME not supported by this uiautomator2 version.")
            return None
        if not installed:
            if _is_fastinput_ime_installed(adb, serial):
                log_handler.success("FastInputIME installed.")
            else:
                log_handler.warning("FastInputIME still not detected.")
        return d
    except Exception as e:
        log_handler.error(f"FastInputIME error: {e}")
        return None


def _open_random_address_link(adb, serial) -> str:
    if not ADDRESS_DEEPLINKS:
        log_handler.warning("No address deeplinks configured.")
        return ""
    link = random.choice(ADDRESS_DEEPLINKS)
    log_handler.info("Opening address deeplink...")
    log_handler.info(f"Link: {link}")
    _open_shopee_link(adb, serial, link)
    log_handler.success("Deep link sent to Shopee app!")
    return link


def _run_add_address_flow(adb, serial, screen_width: int, screen_height: int, address: str):
    try:
        tap_delay = 0.8
        steps = [
            ("Mua hang", 0.727, 0.914, 3.0),
            ("Xac nhan mua hang", 0.69, 0.905, 3.0),
            ("Them dia chi", 0.681, 0.508, 3.0),
            ("Thoat", 0.404, 0.229, tap_delay),
            ("Chon o nhap dia chi", 0.29, 0.22, tap_delay),
        ]
        for label, x, y, delay in steps:
            _tap_with_debug(adb, serial, int(screen_width * x), int(screen_height * y))
            log_handler.tap(f"{label} ({x}, {y})")
            time.sleep(delay)

        device = _ensure_fastinput_ime(adb, serial)
        if address:
            if device:
                device.send_keys(address)
                log_handler.success("Da nhap dia chi.")
            else:
                log_handler.warning("Khong the nhap dia chi (FastInputIME chua san sang).")
        else:
            log_handler.warning("Khong co dia chi de nhap.")

        time.sleep(tap_delay)
        tail_steps = [
            ("Nhap dia chi", 0.863, 0.27, 2.7),
            ("input SDT", 0.322, 0.471, tap_delay),
            ("SDT mac dinh", 0.836, 0.53, tap_delay),
            ("Hoan thanh", 0.49, 0.854, tap_delay),
        ]
        for label, x, y, delay in tail_steps:
            _tap_with_debug(adb, serial, int(screen_width * x), int(screen_height * y))
            log_handler.tap(f"{label} ({x}, {y})")
            time.sleep(delay)
        log_handler.success("Hoan thanh them dia chi!")
    except Exception as e:
        log_handler.error(f"Error in add address flow: {e}")


def run_add_address_flow(adb, serial, screen_width: int, screen_height: int, address: str):
    link_used = _open_random_address_link(adb, serial)
    if not link_used:
        log_handler.warning("Address link empty. Skipping address flow.")
        return
    log_handler.info("Waiting 3s after opening link...")
    time.sleep(3.0)
    _run_add_address_flow(adb, serial, screen_width, screen_height, address)


def add_address_only(address: str, log_container):
    "Open random address link and run add-address flow without login."
    try:
        log_handler.info("=" * 40)
        log_handler.info("Starting add-address flow...")
        if MODULES_AVAILABLE:
            adb = ADBController()
            device_manager = DeviceStateManager(Config().PCHANGER_BASE_URL, DEFAULT_DEVICE_KEY)
            serial = device_manager.get_device_serial()
            if not serial:
                log_handler.error("Failed to get device serial")
                return

            screen_width, screen_height = adb.get_screen_size(serial)
            run_add_address_flow(adb, serial, screen_width, screen_height, address)
            log_handler.success("Add-address flow completed.")
        else:
            log_handler.warning("Modules not available - demo mode")
            log_handler.success("[Demo] Add address flow would run")
    except Exception as e:
        log_handler.error(f"Error running add address flow: {e}")


def open_deeplink_only(shopee_link: str, log_container):
    "Open deep link directly without full flow."
    link = (shopee_link or "").strip()
    if not link:
        log_handler.warning("Empty link. Skipping open.")
        return

    log_handler.info("=" * 40)
    log_handler.info("Opening deep link directly...")
    log_handler.info(f"Link: {link}")

    try:
        if MODULES_AVAILABLE:
            adb = ADBController()
            device_manager = DeviceStateManager(Config().PCHANGER_BASE_URL, DEFAULT_DEVICE_KEY)
            serial = device_manager.get_device_serial()
            if not serial:
                log_handler.error("Failed to get device serial")
                return

            _open_shopee_link(adb, serial, link)
            log_handler.success("Deep link sent to Shopee app!")
        else:
            log_handler.warning("Modules not available - demo mode")
            log_handler.success("[Demo] Deep link would be opened")
    except Exception as e:
        log_handler.error(f"Error opening deep link: {e}")


async def start_flow(credentials: str, device_key: str, shopee_link: str,
                     status_label, start_btn, stop_btn, log_container,
                     add_address: bool = False, address: str = ""):
    "Start the auto login flow."
    global current_flow, is_running

    if not credentials.strip():
        log_handler.error("Please enter credentials.")
        return

    if is_running:
        log_handler.warning("Flow is already running.")
        return

    is_running = True
    status_label.content = '<span class="status-badge status-running pulse">Running</span>'
    start_btn.props('disable')
    stop_btn.props(remove='disable')

    log_handler.clear()
    log_handler.info("=" * 50)
    log_handler.info("Starting Shopee Auto Login Flow")
    log_handler.info("=" * 50)

    try:
        current_flow = AutoLoginFlowUI(device_key, credentials, log_handler)

        def run_flow():
            global is_running
            try:
                flow_link = shopee_link if (shopee_link and not add_address) else None
                success = current_flow.run(flow_link)
                if success:
                    log_handler.success("Auto login completed successfully.")

                    if add_address:
                        try:
                            if MODULES_AVAILABLE:
                                adb = ADBController()
                                serial = current_flow.serial
                                if serial:
                                    run_add_address_flow(
                                        adb,
                                        serial,
                                        current_flow.screen_width,
                                        current_flow.screen_height,
                                        address,
                                    )
                                else:
                                    log_handler.warning("No device serial for address flow.")
                            else:
                                log_handler.warning("Modules not available - skipping address flow")
                        except Exception as e:
                            log_handler.error(f"Address flow error: {e}")

                    if shopee_link and add_address:
                        try:
                            if MODULES_AVAILABLE:
                                adb = ADBController()
                                serial = current_flow.serial
                                if serial:
                                    log_handler.info("Opening custom link after address flow...")
                                    _open_shopee_link(adb, serial, shopee_link)
                                else:
                                    log_handler.warning("No device serial for custom link.")
                            else:
                                log_handler.warning("Modules not available - skipping custom link")
                        except Exception as e:
                            log_handler.error(f"Custom link error: {e}")
                elif current_flow and current_flow.stop_requested:
                    log_handler.warning("Flow stopped.")
                else:
                    log_handler.error("Auto login failed.")
            except Exception as e:
                log_handler.error(f"Error: {e}")
            finally:
                is_running = False

        thread = threading.Thread(target=run_flow, daemon=True)
        thread.start()

        while is_running:
            await asyncio.sleep(0.5)

    except Exception as e:
        log_handler.error(f"Error starting flow: {e}")
        is_running = False

    status_label.content = '<span class="status-badge status-ready">Ready</span>'
    start_btn.props(remove='disable')
    stop_btn.props('disable')


def stop_flow(status_label, start_btn, stop_btn):
    "Stop the current flow."
    global current_flow, is_running

    if current_flow:
        current_flow.stop()

    is_running = False
    log_handler.warning("Flow stopped by user.")

    status_label.content = '<span class="status-badge status-ready">Ready</span>'
    start_btn.props(remove='disable')
    stop_btn.props('disable')

# Create UI
create_ui()

# Run the app
ui.run(
    title='Shopee Auto Login',
    port=8888,
    reload=False,
    show=True,
    dark=False
)
