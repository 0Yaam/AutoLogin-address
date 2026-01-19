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
            "INFO": "#4ade80",      # green
            "WARNING": "#fbbf24",   # yellow  
            "ERROR": "#f87171",     # red
            "SUCCESS": "#22d3ee",   # cyan
            "DEBUG": "#a78bfa"      # purple
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

    def _tap_ratio(self, x_ratio: float, y_ratio: float, wait: float = 0.0):
        x = int(self.screen_width * x_ratio)
        y = int(self.screen_height * y_ratio)
        self.logger.info(f"Tapping at ({x_ratio:.3f}, {y_ratio:.3f}) -> ({x}, {y})")
        if MODULES_AVAILABLE:
            self.adb.tap(self.serial, x, y)
        if wait > 0:
            time.sleep(wait)

    def _wait_for_text(self, text: str, timeout: Optional[float] = 60.0, interval: float = 1.0) -> bool:
        if not MODULES_AVAILABLE:
            return True
        start_time = time.time()
        while self.running:
            elements = self.element_finder.find_by_text(
                self.serial, text, exact=False, normalize=True
            )
            if elements:
                return True
            if timeout is not None and time.time() - start_time >= timeout:
                return False
            time.sleep(interval)
        return False

    def _wait_and_tap_resource_id(self, resource_id: str, fallback_ratio=None,
                                   timeout: float = 30.0, interval: float = 1.0) -> bool:
        if not MODULES_AVAILABLE:
            return True
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
            time.sleep(interval)
        return False

    def fetch_shopee_link_from_mail(self, mail_data: str, retry_interval: float = 5.0) -> Optional[str]:
        """Fetch Shopee verification link from mail using API.
        
        Mail data format: email|mail_pass|refresh_token|client_id|smvmail
        """
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
                    time.sleep(retry_interval)
                    continue

                data = response.json()

                if not data.get("status") or not data.get("messages"):
                    self.logger.warning("No messages found. Retrying...")
                    time.sleep(retry_interval)
                    continue

                self.logger.info(f"Found {len(data['messages'])} messages. Searching for Shopee link...")

                for msg in data['messages']:
                    html_content = msg.get('message', '')
                    match = re.search(r'https://vn\.shp\.ee/dlink/[a-zA-Z0-9]+', html_content)

                    if match:
                        link_shopee = match.group(0)
                        self.logger.success(f"Found Shopee link: {link_shopee}")
                        return link_shopee

                self.logger.warning("No Shopee link found. Retrying...")
                time.sleep(retry_interval)

            except Exception as e:
                self.logger.warning(f"Error: {e}. Retrying...")
                time.sleep(retry_interval)
        
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

        if not self.adb.wait_for_device(self.serial, timeout=180):
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
        
        if not self.connect_device():
            return False

        self.logger.info("Launching Shopee app...")
        if MODULES_AVAILABLE:
            self.adb.unlock_screen(self.serial)
            time.sleep(0.2)
            self.adb.launch_app(self.serial, self.config.APP_PACKAGE)
        time.sleep(5.0)

        self._tap_ratio(0.705, 0.911, wait=1.75)
        self._tap_ratio(0.235, 0.280, wait=0.3)
        
        self.logger.info(f"Entering username: {self.username}")
        if MODULES_AVAILABLE:
            self.adb.input_text(self.serial, self.username)
        time.sleep(0.3)

        self._tap_ratio(0.237, 0.337, wait=0.3)
        self.logger.info("Entering password...")
        if MODULES_AVAILABLE:
            self.adb.input_text(self.serial, self.password)
        time.sleep(0.3)

        self._tap_ratio(0.509, 0.410)

        self.logger.info("Waiting for email verification option...")
        time.sleep(8.0)
        self._tap_ratio(0.283, 0.228, wait=0.5)

        self.logger.info("Handling permission prompt...")
        time.sleep(4.0)
        self._tap_ratio(0.48, 0.768, wait=2.0)

        self._tap_ratio(0.275, 0.535)

        self.logger.info("Waiting before fetching mail verification link...")
        time.sleep(6.0)

        # Nếu có link shopee được cung cấp (từ checkbox), sử dụng deep link
        if shopee_link:
            self.logger.success(f"Custom Shopee link provided!")
            self.open_shopee_deeplink(shopee_link)
            self.logger.info("Waiting for Shopee to load product...")
            time.sleep(3.0)
            self.logger.success("Done! Product should be open in Shopee app.")
            self.running = False
            return True
        
        # Nếu không có custom link, fetch từ mail (flow login cũ)
        link_to_use = None
        if self.hotmail:
            link_to_use = self.fetch_shopee_link_from_mail(self.hotmail)
            
        if link_to_use:
            self.logger.success(f"Using Shopee link: {link_to_use}")
            self.logger.info("Opening Shopee link in browser on device...")
            
            if MODULES_AVAILABLE:
                self.adb.shell(self.serial, [
                    "am", "start", "-a", "android.intent.action.VIEW", 
                    "-d", link_to_use
                ])
            
            self.logger.info("Waiting for Chrome First Run button...")
            chrome_fre_found = self._wait_and_tap_resource_id(
                "com.android.chrome:id/fre_bottom_group",
                timeout=30.0
            )
            if chrome_fre_found:
                self.logger.info("Tapped Chrome First Run button")
            else:
                self.logger.info("Tapping fallback coordinate")
                self._tap_ratio(0.496, 0.885)
            
            self.logger.info("Waiting for location permission dialog...")
            location_dialog_found = self._wait_for_text(
                "shopee.vn muốn sử dụng thông tin vị trí thiết bị của bạn",
                timeout=60.0
            )
            if location_dialog_found:
                self.logger.info("Location dialog appeared")
                time.sleep(2.5)
            
            self.logger.info("Returning to Shopee app...")
            if MODULES_AVAILABLE:
                self.adb.launch_app(self.serial, self.config.APP_PACKAGE)
        else:
            self.logger.warning("No Shopee link available")
            
        if MODULES_AVAILABLE:
            self.adb.press_keycode(self.serial, 4)
            
        self.logger.success("Auto login flow completed!")
        self.running = False
        return True
    
    def stop(self):
        self.running = False
        self.logger.warning("Stopping flow...")


# ================== NiceGUI Interface ==================

# Global state
log_handler = LogHandler()
current_flow: Optional[AutoLoginFlowUI] = None
is_running = False


def create_ui():
    """Tạo giao diện NiceGUI - Layout 2 cột"""
    
    # Custom CSS
    ui.add_head_html('''
    <style>
        :root {
            --primary: #6366f1;
            --primary-dark: #4f46e5;
            --bg-dark: #0f172a;
            --bg-card: #1e293b;
            --bg-input: #334155;
            --text-primary: #f1f5f9;
            --text-secondary: #94a3b8;
            --border: #475569;
        }
        
        body {
            background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
            height: 100vh;
            overflow: hidden;
        }
        
        .main-wrapper {
            height: 100vh;
            padding: 16px;
            box-sizing: border-box;
        }
        
        .card {
            background: var(--bg-card);
            border-radius: 12px;
            padding: 16px;
            border: 1px solid var(--border);
        }
        
        .input-field textarea, .input-field input {
            background: var(--bg-input) !important;
            border: 1px solid var(--border) !important;
            border-radius: 8px !important;
            color: var(--text-primary) !important;
            font-family: 'Consolas', monospace !important;
            font-size: 13px !important;
        }
        
        .input-field textarea:focus, .input-field input:focus {
            border-color: var(--primary) !important;
        }
        
        .log-container {
            background: #0d1117;
            border-radius: 8px;
            padding: 12px;
            font-family: 'Consolas', monospace;
            font-size: 12px;
            height: calc(100vh - 140px);
            overflow-y: auto;
            border: 1px solid #30363d;
        }
        
        .log-entry {
            padding: 3px 0;
            border-bottom: 1px solid #21262d;
            line-height: 1.4;
        }
        
        .log-timestamp { color: #8b949e; margin-right: 6px; }
        .log-level {
            font-weight: 600;
            margin-right: 6px;
            padding: 1px 5px;
            border-radius: 3px;
            font-size: 10px;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%) !important;
            border: none !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
            text-transform: none !important;
            padding: 10px 20px !important;
        }
        
        .btn-danger { background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%) !important; }
        .btn-small { padding: 6px 12px !important; font-size: 12px !important; }
        
        .title-gradient {
            background: linear-gradient(135deg, #6366f1 0%, #a855f7 50%, #ec4899 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 700;
        }
        
        .status-badge {
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
        }
        .status-ready { background: rgba(34, 197, 94, 0.2); color: #22c55e; }
        .status-running { background: rgba(99, 102, 241, 0.2); color: #818cf8; }
        .pulse { animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
    </style>
    ''')
    
    with ui.column().classes('main-wrapper w-full'):
        # Header
        with ui.row().classes('w-full justify-between items-center mb-3'):
            ui.html('<h1 class="title-gradient text-2xl">🛒 Shopee Auto Login</h1>', sanitize=False)
            status_label = ui.html('<span class="status-badge status-ready">● Ready</span>', sanitize=False)
        
        # Main Content - 2 columns
        with ui.row().classes('w-full gap-4 flex-1'):
            # Left Column - Controls
            with ui.column().classes('flex-1 gap-3'):
                # Credentials
                with ui.card().classes('card w-full'):
                    ui.label('📝 Credentials').classes('font-semibold text-slate-200 mb-2')
                    ui.label('Format: user|pass|email|token|client_id|...').classes('text-xs text-slate-400 mb-2')
                    credentials_input = ui.textarea(
                        placeholder='user|pass|email|token|client_id|...'
                    ).classes('input-field w-full').props('outlined rows=3 dense')
                
                # Shopee Link Option
                with ui.card().classes('card w-full'):
                    with ui.row().classes('items-center gap-2'):
                        use_custom_link = ui.checkbox('🔗 Link Shopee tùy chỉnh').classes('text-sm')
                    shopee_link_input = ui.input(
                        placeholder='https://vn.shp.ee/dlink/...'
                    ).classes('input-field w-full').props('outlined dense').bind_visibility_from(use_custom_link, 'value')
                
                # Device Key
                with ui.card().classes('card w-full'):
                    ui.label('📱 Device Key').classes('font-semibold text-slate-200 mb-2')
                    device_key_input = ui.input(
                        value='e8da52170928cf3'
                    ).classes('input-field w-full').props('outlined dense')
                
                # Action Buttons
                with ui.row().classes('w-full gap-2'):
                    start_btn = ui.button('🚀 Start', on_click=lambda: start_flow(
                        credentials_input.value,
                        device_key_input.value,
                        shopee_link_input.value if use_custom_link.value else None,
                        status_label,
                        start_btn,
                        stop_btn,
                        log_container
                    )).classes('btn-primary flex-1')
                    
                    stop_btn = ui.button('⏹ Stop', on_click=lambda: stop_flow(
                        status_label, start_btn, stop_btn
                    )).classes('btn-primary btn-danger').props('disable')
            
            # Right Column - Logs
            with ui.column().classes('flex-1'):
                with ui.card().classes('card w-full h-full'):
                    with ui.row().classes('w-full justify-between items-center mb-2'):
                        ui.label('📋 Log Output').classes('font-semibold text-slate-200')
                        with ui.row().classes('gap-2 items-center'):
                            log_count = ui.label('0').classes('text-xs text-slate-400')
                            ui.button('🗑', on_click=lambda: clear_logs(log_container)).classes('btn-primary btn-small')
                    
                    log_container = ui.html('', sanitize=False).classes('log-container')
                    ui.timer(0.5, lambda: update_logs(log_container, log_count))


def update_logs(container, count_label):
    """Cập nhật log display"""
    if not log_handler.logs:
        container.content = '<div style="color: #8b949e; text-align: center; padding: 20px;">No logs yet...</div>'
        count_label.set_text('0 entries')
        return
    
    html_content = ""
    for log in log_handler.logs[-100:]:  # Hiển thị 100 log gần nhất
        level_colors = {
            "INFO": "#3b82f6",
            "WARNING": "#f59e0b", 
            "ERROR": "#ef4444",
            "SUCCESS": "#22c55e",
            "DEBUG": "#a855f7"
        }
        bg_color = level_colors.get(log['level'], '#6b7280')
        
        html_content += f'''
        <div class="log-entry">
            <span class="log-timestamp">[{log['timestamp']}]</span>
            <span class="log-level" style="background: {bg_color}20; color: {bg_color};">{log['level']}</span>
            <span style="color: {log['color']};">{log['message']}</span>
        </div>
        '''
    
    container.content = html_content
    count_label.set_text(f'{len(log_handler.logs)} entries')
    
    # Auto scroll to bottom
    ui.run_javascript('''
        const logContainer = document.querySelector('.log-container');
        if (logContainer) logContainer.scrollTop = logContainer.scrollHeight;
    ''')


def clear_logs(container):
    """Xóa tất cả logs"""
    log_handler.clear()
    container.content = '<div style="color: #8b949e; text-align: center; padding: 20px;">Logs cleared</div>'


async def start_flow(credentials: str, device_key: str, shopee_link: str, 
                     status_label, start_btn, stop_btn, log_container):
    """Bắt đầu auto login flow"""
    global current_flow, is_running
    
    if not credentials.strip():
        log_handler.error("Please enter credentials!")
        return
    
    if is_running:
        log_handler.warning("Flow is already running!")
        return
    
    is_running = True
    status_label.content = '<span class="status-badge status-running pulse">● Running...</span>'
    start_btn.props('disable')
    stop_btn.props(remove='disable')
    
    log_handler.clear()
    log_handler.info("=" * 50)
    log_handler.info("Starting Shopee Auto Login Flow")
    log_handler.info("=" * 50)
    
    try:
        current_flow = AutoLoginFlowUI(device_key, credentials, log_handler)
        
        # Run in background thread
        def run_flow():
            global is_running
            try:
                success = current_flow.run(shopee_link)
                if success:
                    log_handler.success("✅ Auto login completed successfully!")
                else:
                    log_handler.error("❌ Auto login failed!")
            except Exception as e:
                log_handler.error(f"Error: {e}")
            finally:
                is_running = False
        
        thread = threading.Thread(target=run_flow, daemon=True)
        thread.start()
        
        # Wait for completion
        while is_running:
            await asyncio.sleep(0.5)
            
    except Exception as e:
        log_handler.error(f"Error starting flow: {e}")
        is_running = False
    
    # Reset UI
    status_label.content = '<span class="status-badge status-ready">● Ready</span>'
    start_btn.props(remove='disable')
    stop_btn.props('disable')


def stop_flow(status_label, start_btn, stop_btn):
    """Dừng flow"""
    global current_flow, is_running
    
    if current_flow:
        current_flow.stop()
    
    is_running = False
    log_handler.warning("Flow stopped by user")
    
    status_label.content = '<span class="status-badge status-ready">● Ready</span>'
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
    dark=True
)
