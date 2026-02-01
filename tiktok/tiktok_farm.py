"""
TikTok Farm Automation Script
=============================
Script t? d?ng hóa nuôi nick TikTok s? d?ng uiautomator2, gspread và ADB.

Author: Automation Team
Package: com.zhiliaoapp.musically
"""

import os
import sys
import time
import random
import requests
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict, Any

import uiautomator2 as u2
try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
except Exception:
    # Google Sheets dependencies are optional while sheet flow is disabled.
    gspread = None
    ServiceAccountCredentials = None

# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    """C?u h́nh cho TikTok automation"""
    
    # TikTok App
    TIKTOK_PACKAGE = "com.zhiliaoapp.musically"
    
    # API Endpoints
    MAIL_API_URL_OLD = "https://tools.dongvanfb.net/api/get_code_oauth2"
    MAIL_API_URL_NEW = "https://mailvip.net/index.php"
    PCHANGER_BASE_URL = "http://127.0.0.1:8080"

    # Default device key (no prompt)
    DEFAULT_DEVICE_KEY = "e8da52170928cf3"

    # Visual tap debug
    SHOW_TAP_TOAST = True
    TAP_TOAST_SECONDS = 0.7
    
    # Mail API debug
    DEBUG_MAIL_API = False
    MAIL_NEW_IGNORE_MINTIME = True
    MAILVIP_ALLOWED_DOMAINS = {"mailvip.net", "tempm.com"}
    
    # Google Sheets
    CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "credentials.json")
    SHEET_NAME = "TikTok Farm"  # Tên sheet Google
    SHEET_URL = "https://docs.google.com/spreadsheets/d/195HgTVjWlIrR41VBoHf90thTf1YSph6YCiCcYqxkdcg/edit?gid=0#gid=0"
    
    # Timeouts
    OTP_TIMEOUT = 68  # Giây tru?c khi g?i l?i mă
    OTP_POLL_INTERVAL = 3  # Giây gi?a các l?n ki?m tra OTP
    MAX_OTP_ATTEMPTS = 5  # S? l?n th? t?i da
    DEVICE_BUSY_TIMEOUT = 300  # Giây ch? device h?t busy
    
    # Activities
    ACTIVITY_NEW_USER = "NewUserJourneyActivity"
    ACTIVITY_SIGNUP_LOGIN = "SignUpOrLoginActivity"
    ACTIVITY_SPARK = "com.bytedance.hybrid.spark.page.SparkActivity"


# ============================================================================
# LOGGING
# ============================================================================

class Logger:
    """Simple logger v?i màu s?c"""
    _COLOR_RESET = "\033[0m"
    _COLOR_CYAN = "\033[36m"
    
    @staticmethod
    def info(msg: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [INFO] {msg}")
    
    @staticmethod
    def success(msg: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [SUCCESS] ? {msg}")
    
    @staticmethod
    def warning(msg: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [WARNING] ? {msg}")
    
    @staticmethod
    def error(msg: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [ERROR] ? {msg}")

    @staticmethod
    def tap(msg: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"{Logger._COLOR_CYAN}[{timestamp}] [TAP] {msg}{Logger._COLOR_RESET}")


log = Logger()

# Stop control (set by UI)
STOP_REQUESTED = False


class StopRequested(BaseException):
    """Raised when a stop is requested to abort the current flow immediately."""


_RAW_SLEEP = time.sleep


def _sleep(seconds: float, check_interval: float = 0.1):
    """Sleep with periodic stop checks for fast cancellation."""
    if seconds <= 0:
        return
    end_time = time.time() + seconds
    while True:
        if STOP_REQUESTED:
            raise StopRequested()
        remaining = end_time - time.time()
        if remaining <= 0:
            return
        _RAW_SLEEP(min(check_interval, remaining))


def request_stop():
    global STOP_REQUESTED
    STOP_REQUESTED = True


def clear_stop():
    global STOP_REQUESTED
    STOP_REQUESTED = False


# ============================================================================
# GOOGLE SHEETS HANDLER
# ============================================================================

class GoogleSheetsHandler:
    """X? lư d?c/ghi Google Sheets"""
    
    def __init__(self, credentials_file: str, sheet_url_or_name: str):
        """
        Kh?i t?o k?t n?i Google Sheets
        
        Args:
            credentials_file: Đu?ng d?n file credentials.json
            sheet_url_or_name: URL ho?c tên Google Sheet
        """
        self.credentials_file = credentials_file
        self.sheet_url_or_name = sheet_url_or_name
        self.client = None
        self.sheet = None
        self._connect()
    
    def _connect(self):
        """K?t n?i d?n Google Sheets"""
        if gspread is None or ServiceAccountCredentials is None:
            raise RuntimeError("Google Sheets libraries are not installed.")
        try:
            scope = [
                "https://www.googleapis.com/auth/spreadsheets", # <-- Dùng cái này
                "https://www.googleapis.com/auth/drive"
            ]
            creds = ServiceAccountCredentials.from_json_keyfile_name(
                self.credentials_file, scope
            )
            self.client = gspread.authorize(creds)
            
            # Ki?m tra n?u là URL
            if "docs.google.com" in self.sheet_url_or_name or "spreadsheets" in self.sheet_url_or_name:
                self.sheet = self.client.open_by_url(self.sheet_url_or_name).sheet1
                log.success(f"Connected to Google Sheet via URL")
            else:
                self.sheet = self.client.open(self.sheet_url_or_name).sheet1
                log.success(f"Connected to Google Sheet: {self.sheet_url_or_name}")
        except gspread.exceptions.SpreadsheetNotFound:
            log.error(f"Sheet not found: {self.sheet_url_or_name}")
            log.error("Make sure the sheet is shared with the service account email!")
            raise
        except Exception as e:
            log.error(f"Failed to connect Google Sheets: {e}")
            raise
    
    def get_next_unprocessed_row(self) -> Optional[Tuple[int, str, str, str]]:
        """
        L?y ḍng ti?p theo chua x? lư
        
        Returns:
            Tuple (row_number, user, password, mail) ho?c None
        """
        try:
            all_data = self.sheet.get_all_values()
            
            for idx, row in enumerate(all_data[1:], start=2):  # B? qua header
                col_a = row[0] if len(row) > 0 else ""  # user|pass|mail
                col_b = row[1] if len(row) > 1 else ""  # Tr?ng thái
                
                # N?u c?t A có d? li?u và c?t B tr?ng -> chua x? lư
                if col_a and not col_b.strip():  # strip() d? lo?i b? kho?ng tr?ng
                    # Ch? split 2 l?n d?u, ph?n c̣n l?i gom vào mail
                    parts = col_a.split("|", 2)
                    if len(parts) >= 3:
                        user = parts[0].strip()
                        password = parts[1].strip()
                        mail = parts[2].strip()  # Ch?a toàn b?: email|mail_pass|token|client_id
                        log.info(f"Found unprocessed row {idx}: {user}")
                        return (idx, user, password, mail)
            
            log.warning("No unprocessed rows found")
            return None
            
        except Exception as e:
            log.error(f"Error reading sheet: {e}")
            return None

    def get_next_unprocessed_row_skip_status(self) -> Optional[Tuple[int, str, str, str]]:
        """
        L?y ḍng ti?p theo chua x? lư, b? qua tr?ng thái '1' và 'PROCESSING'.
        """
        try:
            all_data = self.sheet.get_all_values()
            for idx, row in enumerate(all_data[1:], start=2):
                col_a = row[0] if len(row) > 0 else ""  # user|pass|mail
                col_b = row[1] if len(row) > 1 else ""  # Tr?ng thái
                status = (col_b or "").strip().upper()
                if status in {"1", "PROCESSING"}:
                    continue
                if col_a and not col_b.strip():
                    parts = col_a.split("|", 2)
                    if len(parts) >= 3:
                        user = parts[0].strip()
                        password = parts[1].strip()
                        mail = parts[2].strip()
                        log.info(f"Found unprocessed row {idx}: {user}")
                        return (idx, user, password, mail)
            log.warning("No unprocessed rows found")
            return None
        except Exception as e:
            log.error(f"Error reading sheet: {e}")
            return None
    
    def update_status(self, row: int, status: str):
        """C?p nh?t tr?ng thái c?t B"""
        try:
            self.sheet.update_cell(row, 2, status)
            log.info(f"Updated row {row} status: {status}")
        except Exception as e:
            log.error(f"Failed to update status: {e}")
    
    def update_device_id(self, row: int, device_id: str):
        """C?p nh?t Device ID c?t C"""
        try:
            self.sheet.update_cell(row, 3, device_id)
        except Exception as e:
            log.error(f"Failed to update device ID: {e}")
    
    def update_backup_time(self, row: int, timestamp: str):
        """C?p nh?t th?i gian backup c?t D"""
        try:
            self.sheet.update_cell(row, 4, timestamp)
        except Exception as e:
            log.error(f"Failed to update backup time: {e}")
    
    def update_backup_name(self, row: int, backup_name: str):
        """C?p nh?t tên file backup c?t E"""
        try:
            self.sheet.update_cell(row, 5, backup_name)
        except Exception as e:
            log.error(f"Failed to update backup name: {e}")


# ============================================================================
# PCHANGER API (Backup/Device)
# ============================================================================

class PchangerAPI:
    """API client cho Pchanger (backup, device status)"""
    
    def __init__(self, base_url: str = Config.PCHANGER_BASE_URL):
        self.base_url = base_url
    
    def check_device_status(self, device_key: str) -> Dict[str, Any]:
        """
        Ki?m tra tr?ng thái thi?t b?
        
        Args:
            device_key: Key c?a thi?t b?
            
        Returns:
            Dict v?i status và thông tin thi?t b?
        """
        try:
            url = f"{self.base_url}/dev/{device_key}/device"
            response = requests.get(url, timeout=10)
            return response.json()
        except Exception as e:
            log.error(f"Device status check failed: {e}")
            return {"status": False, "note": str(e)}
    
    def wait_for_device_ready(self, device_key: str, timeout: int = Config.DEVICE_BUSY_TIMEOUT) -> bool:
        """
        Ch? thi?t b? h?t busy
        
        Args:
            device_key: Key thi?t b?
            timeout: Th?i gian ch? t?i da (giây)
            
        Returns:
            True n?u device s?n sàng
        """
        log.info(f"Waiting for device {device_key} to be ready...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            result = self.check_device_status(device_key)
            
            if result.get("status") == "true" or result.get("status") == True:
                log.success(f"Device {device_key} is ready")
                return True
            
            note = result.get("note", "")
            if "busy" in note.lower():
                log.info(f"Device busy, waiting... ({int(time.time() - start_time)}s)")
            
            _sleep(5)
        
        log.error(f"Device not ready after {timeout}s")
        return False
    
    def backup_device(self, device_key: str, backup_name: str) -> Optional[str]:
        """
        T?o backup cho thi?t b?
        
        Args:
            device_key: Key thi?t b?
            backup_name: Tên file backup
            
        Returns:
            Tên backup n?u thành công, None n?u l?i
        """
        try:
            # Ch? device s?n sàng
            if not self.wait_for_device_ready(device_key):
                return None
            
            url = f"{self.base_url}/dev/{device_key}/backup?name={backup_name}"
            log.info(f"Creating backup: {backup_name}")
            
            response = requests.get(url, timeout=30)
            result = response.json()
            
            if result.get("status") == True:
                log.success(f"Backup initiated: {backup_name}")
                
                # Ch? backup hoàn t?t (device h?t busy)
                _sleep(5)
                if self.wait_for_device_ready(device_key, timeout=600):
                    return backup_name
            else:
                log.error(f"Backup failed: {result.get('note', 'Unknown error')}")
            
            return None
            
        except Exception as e:
            log.error(f"Backup error: {e}")
            return None
    
    def get_devices(self) -> List[Dict]:
        """L?y danh sách thi?t b?"""
        try:
            url = f"{self.base_url}/devices"
            response = requests.get(url, timeout=10)
            return response.json()
        except Exception as e:
            log.error(f"Get devices failed: {e}")
            return []


# ============================================================================
# MAIL API (Get TikTok OTP)
# ============================================================================

def _parse_mail_date(value: str) -> Optional[datetime]:
    """Parse API date format: 'HH:MM - DD/MM/YYYY'."""
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%H:%M - %d/%m/%Y")
    except Exception:
        return None


def get_tiktok_otp(email: str, refresh_token: str, client_id: str,
                   min_time: Optional[datetime] = None,
                   tolerance_minutes: int = 1) -> Optional[str]:
    """
    L?y mă OTP TikTok t? mail
    
    Args:
        email: Đ?a ch? email
        refresh_token: OAuth2 refresh token
        client_id: OAuth2 client ID
        
    Returns:
        Mă OTP n?u t́m th?y, None n?u không
    """
    try:
        def _extract_json_object(text: str) -> Optional[dict]:
            if not text:
                return None
            start = text.find("{")
            end = text.rfind("}")
            if start == -1 or end == -1 or end <= start:
                return None
            snippet = text[start:end + 1]
            try:
                import json
                return json.loads(snippet)
            except Exception:
                return None

        # Prefer old API when refresh_token + client_id are present.
        if refresh_token and client_id:
            log.info("Using mail API: OLD")
            payload = {
                "email": email,
                "refresh_token": refresh_token,
                "client_id": client_id,
                "type": "tiktok"
            }
            response = requests.post(
                Config.MAIL_API_URL_OLD,
                json=payload,
                timeout=15
            )
            try:
                result = response.json()
            except Exception as e:
                log.error(f"Mail API (old) error: {e}")
                return None

            if result.get("status") == True and result.get("code"):
                code = result.get("code")
                mail_date = _parse_mail_date(result.get("date", ""))
                if min_time:
                    if not mail_date:
                        log.warning("OTP date missing/unparseable, skipping")
                        return None
                    # API ch? có phút, nên so sánh theo phút (cho phép l?ch 1p)
                    min_time_floor = min_time.replace(second=0, microsecond=0)
                    min_allowed = min_time_floor - timedelta(minutes=tolerance_minutes)
                    if mail_date < min_allowed:
                        log.info(
                            f"OTP is older than send time ({mail_date} < {min_allowed}), skipping"
                        )
                        return None
                log.success(f"Got OTP: {code}")
                return code
            return None

        # New API: only needs full email
        log.info("Using mail API: NEW")
        email_domain = email.split("@")[-1].lower().strip() if "@" in email else ""
        if email_domain and email_domain not in Config.MAILVIP_ALLOWED_DOMAINS:
            log.warning(
                f"Mailvip API may not support domain '{email_domain}'. "
                f"Try mailvip.net or tempm.com."
            )
        params = {"action": "get_tempm", "email": email}
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(Config.MAIL_API_URL_NEW, params=params, headers=headers, timeout=15)
        try:
            response.encoding = response.encoding or "utf-8"
        except Exception:
            pass
        if Config.DEBUG_MAIL_API:
            log.info(f"Mail API NEW status={response.status_code} url={response.url}")
            preview = (response.text or "").strip().replace("\n", " ")
            log.info(f"Mail API NEW response: {preview[:400]}")
        try:
            result = response.json()
        except Exception as e:
            try:
                import json
                result = json.loads(response.text)
            except Exception:
                extracted = _extract_json_object(response.text)
                if extracted is not None:
                    result = extracted
                else:
                    preview = (response.text or "").strip().replace("\n", " ")
                    log.error(f"Mail API (new) parse error: {e}. Response: {preview[:200]}")
                    return None

        # Normalize to list of mail items
        if isinstance(result, dict):
            items = result.get("data") or result.get("mails") or result.get("mail") or [result]
        elif isinstance(result, list):
            items = result
        else:
            items = []
        if Config.DEBUG_MAIL_API:
            log.info(f"Mail API NEW parsed items: {len(items)}")

        def _parse_sent_time(value: str) -> Optional[datetime]:
            if not value:
                return None
            try:
                return datetime.strptime(value.strip(), "%Y-%m-%d %H:%M:%S")
            except Exception:
                return None

        # Allow some time skew between device time and mail server time
        min_time_floor = None
        if min_time and not Config.MAIL_NEW_IGNORE_MINTIME:
            min_time_floor = min_time - timedelta(hours=3)

        for item in items:
            if not isinstance(item, dict):
                continue
            sender = str(item.get("from", item.get("sender", ""))).strip().lower()
            title = str(item.get("title", item.get("subject", ""))).strip()
            sent_time = _parse_sent_time(str(item.get("sent_time", item.get("time", ""))).strip())
            if sender and sender != "register@account.tiktok.com":
                continue
            # Extract 6-digit code
            import re
            match = re.search(r"\b(\d{6})\b", title)
            if not match:
                continue
            if min_time_floor and sent_time and sent_time < min_time_floor:
                continue
            code = match.group(1)
            log.success(f"Got OTP: {code}")
            return code

        if Config.DEBUG_MAIL_API:
            log.info("Mail API NEW: no OTP found in response")
        return None

    except Exception as e:
        log.error(f"Mail API error: {e}")
        return None


# ============================================================================
# TIKTOK AUTOMATION
# ============================================================================

class TikTokAutomation:
    """Main class d? di?u khi?n TikTok automation"""
    
    def __init__(self, device_serial: str):
        """
        Kh?i t?o automation
        
        Args:
            device_serial: Serial number c?a thi?t b? Android
        """
        self.device_serial = device_serial
        self.device = None
        self.screen_width = 1080
        self.screen_height = 1920
        self._connect_device()
    
    def _connect_device(self):
        """K?t n?i d?n thi?t b? qua uiautomator2"""
        try:
            self.device = u2.connect(self.device_serial)
            info = self.device.info
            self.screen_width = info.get("displayWidth", 1080)
            self.screen_height = info.get("displayHeight", 1920)
            log.success(f"Connected to device: {self.device_serial}")
            log.info(f"Screen size: {self.screen_width}x{self.screen_height}")
            # Show touch points/pointer location for on-screen debug
            self.enable_touch_debug(True)
        except Exception as e:
            log.error(f"Failed to connect device: {e}")
            raise

    def _should_stop(self) -> bool:
        if STOP_REQUESTED:
            log.warning("Stop requested. Exiting current flow.")
            return True
        return False
    
    def get_device_model(self) -> str:
        """L?y tên model thi?t b?"""
        try:
            info = self.device.device_info
            brand = info.get("brand", "")
            model = info.get("model", "")
            if brand and model:
                return f"{brand} {model}"
            return model or brand or self.device_serial
        except Exception:
            return self.device_serial
    
    def tap_ratio(self, x_ratio: float, y_ratio: float, delay: float = 0.3):
        """
        Tap t?i t?a d? theo t? l? màn h́nh
        
        Args:
            x_ratio: T? l? X (0-1)
            y_ratio: T? l? Y (0-1)
            delay: Delay sau khi tap (giây)
        """
        x = int(x_ratio * self.screen_width)
        y = int(y_ratio * self.screen_height)
        self.device.click(x, y)
        log.tap(f"({x_ratio:.3f}, {y_ratio:.3f}) -> ({x}, {y})")
        if Config.SHOW_TAP_TOAST:
            try:
                self.device.toast(f"TAP {x},{y}", duration=Config.TAP_TOAST_SECONDS)
            except Exception:
                pass
        _sleep(delay)
    
    def _adb_shell(self, args: List[str]):
        """Run adb shell command on the device."""
        import subprocess
        subprocess.run(
            ["adb", "-s", self.device_serial, "shell"] + args,
            capture_output=True
        )

    def open_url(self, url: str):
        """Open a URL via Android intent."""
        # Prefer opening inside TikTok app
        self._adb_shell([
            "am", "start", "-a", "android.intent.action.VIEW",
            "-d", url, "-p", Config.TIKTOK_PACKAGE
        ])

    def enable_touch_debug(self, enable: bool = True):
        """B?t/t?t hi?n th? v? trí ch?m trên màn h́nh (Developer options)."""
        value = "1" if enable else "0"
        # show_touches: d?u ch?m noi ch?m; pointer_location: t?a d? + v?t di chuy?n
        self._adb_shell(["settings", "put", "system", "show_touches", value])
        self._adb_shell(["settings", "put", "system", "pointer_location", value])
        state = "ON" if enable else "OFF"
        log.info(f"Touch debug: {state}")

    def tap_random(self, coords: List[Tuple[float, float]], delay: float = 0.3):
        """
        Tap ng?u nhiên vào m?t trong các t?a d?
        
        Args:
            coords: List các tuple (x_ratio, y_ratio)
            delay: Delay sau khi tap
        """
        x_ratio, y_ratio = random.choice(coords)
        self.tap_ratio(x_ratio, y_ratio, delay)
    
    def random_swipe(self, count: int = None):
        """
        Th?c hi?n vu?t ng?u nhiên
        
        Args:
            count: S? l?n vu?t (None = random 3-5)
        """
        if count is None:
            count = random.randint(3, 5)
        
        log.info(f"Performing {count} random swipe(s)...")
        
        for i in range(count):
            if self._should_stop():
                return
            # Random v? trí start/end (tránh sát trên/du?i) - vu?t m?nh hon
            start_x = random.randint(int(self.screen_width * 0.2), int(self.screen_width * 0.8))
            start_y = random.randint(int(self.screen_height * 0.65), int(self.screen_height * 0.85))
            end_x = random.randint(int(self.screen_width * 0.2), int(self.screen_width * 0.8))
            end_y = random.randint(int(self.screen_height * 0.15), int(self.screen_height * 0.35))
            
            # Random duration (nhanh hon ~50%)
            duration = random.uniform(0.08, 0.18)
            
            self.device.swipe(start_x, start_y, end_x, end_y, duration=duration)
            log.info(f"Swipe {i+1}: ({start_x},{start_y}) -> ({end_x},{end_y})")
            _sleep(3)
    
    def input_text(self, text: str):
        """Nh?p text"""
        # Clear existing text: move cursor to end and long-press delete
        self._adb_shell(["input", "keyevent", "123"])  # KEYCODE_MOVE_END
        self._adb_shell(["input", "keyevent", "--longpress", "67"])  # KEYCODE_DEL

        escaped_text = str(text).replace(" ", "%s")
        self._adb_shell(["input", "text", escaped_text])
        log.info(f"Inputted text: {text}")
    
    def wait_for_element(self, xpath: str = None, text: str = None, 
                         resource_id: str = None, timeout: float = 10.0) -> bool:
        """
        Ch? element xu?t hi?n
        
        Args:
            xpath: XPath c?a element
            text: Text c?a element
            resource_id: Resource ID c?a element
            timeout: Th?i gian ch? t?i da
            
        Returns:
            True n?u element xu?t hi?n
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self._should_stop():
                return False
            try:
                if xpath:
                    if self.device.xpath(xpath).exists:
                        return True
                elif text:
                    if self.device(text=text).exists:
                        return True
                elif resource_id:
                    if self.device(resourceId=resource_id).exists:
                        return True
            except Exception:
                pass
            _sleep(0.5)
        
        return False
    
    def check_activity(self, activity_name: str) -> bool:
        """Ki?m tra activity hi?n t?i"""
        try:
            current = self.device.app_current()
            return activity_name in current.get("activity", "")
        except Exception:
            return False
    
    def launch_tiktok(self, clear_data: bool = True, open_settings: bool = True):
        """M? app TikTok"""
        if clear_data:
            log.info("Clearing TikTok app data...")
            self._adb_shell(["pm", "clear", Config.TIKTOK_PACKAGE])
            _sleep(1)
        if open_settings:
            log.info("Opening Date settings...")
            self._adb_shell(["am", "start", "-a", "android.settings.DATE_SETTINGS"])
            _sleep(1)
            self.tap_ratio(0.875, 0.286, delay=0.3)
            self.tap_ratio(0.34, 0.376, delay=0.3)

            # Choose date: today minus 7-10 days (prefer tapping day text)
            target_date = datetime.now() - timedelta(days=random.randint(3, 5))
            target_day = str(target_date.day)
            if (target_date.month != datetime.now().month) or (target_date.year != datetime.now().year):
                log.info("Target date is in previous month, tapping prev month button")
                if self.device(resourceId="android:id/prev").exists:
                    self.device(resourceId="android:id/prev").click()
                else:
                    self.tap_ratio(0.246, 0.35, delay=0.3)
                _sleep(0.3)
            if self.device(text=target_day).exists:
                log.info(f"Tapping day '{target_day}' in Date settings")
                self.device(text=target_day).click()
                _sleep(0.3)
            else:
                log.warning(f"Day '{target_day}' not found, fallback to center tap")
                self.tap_ratio(0.517, 0.592, delay=0.3)

            self.tap_ratio(0.758, 0.74, delay=0.6)
        log.info("Launching TikTok...")
        self.device.app_start(Config.TIKTOK_PACKAGE)
        _sleep(3)

    def close_tiktok(self):
        """Đóng app TikTok"""
        log.info("Closing TikTok...")
        try:
            self.device.app_stop(Config.TIKTOK_PACKAGE)
        except Exception:
            self._adb_shell(["am", "force-stop", Config.TIKTOK_PACKAGE])
    
    def unlock_screen(self):
        """
        M? khóa màn h́nh (copy t? shopee/test.py)
        Dùng ADB shell command tr?c ti?p
        """
        log.info("Unlocking screen...")
        import subprocess
        
        # Press menu button (keycode 82) - gi?ng shopee
        subprocess.run(
            ["adb", "-s", self.device_serial, "shell", "input", "keyevent", "82"],
            capture_output=True
        )
        _sleep(0.5)
        
        # Swipe up to unlock - gi?ng shopee: swipe(500, 1000, 500, 200, 300)
        subprocess.run(
            ["adb", "-s", self.device_serial, "shell", "input", "swipe", "500", "1000", "500", "200", "300"],
            capture_output=True
        )
        log.success("Screen unlocked")
        _sleep(0.5)
    
    # ========================================================================
    # GIAI ĐO?N 1: M? APP & TUONG TÁC BAN Đ?U
    # ========================================================================
    
    def phase1_initial_interaction(self) -> bool:
        """
        Giai do?n 1: M? app và x? lư màn h́nh chào m?ng
        
        Returns:
            True n?u thành công
        """
        log.info("=" * 50)
        log.info("PHASE 1: Initial Interaction")
        log.info("=" * 50)
        if self._should_stop():
            return False
        
        # M? khóa màn h́nh tru?c
        self.unlock_screen()
        
        # Launch TikTok
        self.launch_tiktok()

        # Không swipe/wipe: ch? 7s, tap 1 t?a d?, ch? 2s
        _sleep(7)
        self.tap_ratio(0.899, 0.913)
        _sleep(2)
        _sleep(3)
        self.tap_ratio(0.26, 0.898)
        _sleep(2)
        # Strong swipe
        start_x = int(self.screen_width * 0.5)
        start_y = int(self.screen_height * 0.8)
        end_x = int(self.screen_width * 0.5)
        end_y = int(self.screen_height * 0.2)
        self.device.swipe(start_x, start_y, end_x, end_y, duration=0.12)
        _sleep(4)
        
        log.success("Phase 1 completed")
        return True
    
    # ========================================================================
    # GIAI ĐO?N 2: ĐI?U HU?NG VÀO LOGIN
    # ========================================================================
    
    def phase2_navigate_to_login(self) -> bool:
        """
        Giai do?n 2: Đi?u hu?ng vào màn h́nh dang nh?p
        
        Returns:
            True n?u thành công
        """
        log.info("=" * 50)
        log.info("PHASE 2: Navigate to Login")
        log.info("=" * 50)
        if self._should_stop():
            return False
        
        # Click nút H? so/Tôi
        log.info("Clicking Profile button...")
        self.tap_ratio(0.89, 0.906)
        _sleep(2)
        
        # Click t?a d? c? d?nh
        self.tap_ratio(0.735, 0.343)
        _sleep(2)
        
        # Click Random
        coords_4 = [(0.702, 0.119), (0.629, 0.119)]
        self.tap_random(coords_4)
        _sleep(0.5)
        
        # Click Random ti?p
        coords_5 = [(0.418, 0.198), (0.133, 0.196)]
        self.tap_random(coords_5)
        _sleep(1)
        
        log.success("Phase 2 completed")
        return True
    
    # ========================================================================
    # GIAI ĐO?N 3: NH?P USER & PASSWORD
    # ========================================================================
    
    def phase3_input_credentials(self, username: str, password: str) -> bool:
        """
        Giai do?n 3: Nh?p username và password
        
        Args:
            username: Tên dang nh?p
            password: M?t kh?u
            
        Returns:
            True n?u thành công
        """
        log.info("=" * 50)
        log.info("PHASE 3: Input Credentials")
        log.info("=" * 50)
        if self._should_stop():
            return False
        
        # Nh?p username
        log.info(f"Inputting username: {username}")
        self.input_text(username)
        _sleep(1)
        
        # Click Random d? ti?p t?c
        coords_6 = [(0.512, 0.552), (0.612, 0.566)]
        self.tap_random(coords_6)
        
        # Ch? màn h́nh password
        log.info("Waiting for password screen...")
        password_screen_found = self.wait_for_element(
            resource_id="com.zhiliaoapp.musically:id/ecc",
            timeout=10.0
        )
        
        if not password_screen_found:
            # Th? ki?m tra text
            password_screen_found = self.wait_for_element(
                text="Nh?p m?t kh?u",
                timeout=5.0
            )
        
        if password_screen_found:
            log.success("Password screen appeared")
        else:
            log.warning("Password screen not detected, continuing...")
        
        # Click Random vào ô password
        coords_7 = [(0.181, 0.234), (0.422, 0.246)]
        self.tap_random(coords_7)
        _sleep(0.5)
        
        # Nh?p password
        log.info("Inputting password...")
        self.input_text(password)
        _sleep(1)
        
        # Click nút Đang nh?p
        coords_8 = [(0.461, 0.558), (0.702, 0.564)]
        self.tap_random(coords_8)
        # N?u xu?t hi?n permission h?i danh b? th́ x? lư nhanh
        permission_found = self.wait_for_element(
            resource_id="com.android.permissioncontroller:id/permission_message",
            timeout=2.0
        )
        if not permission_found:
            permission_found = self.wait_for_element(
                resource_id="com.android.permissioncontroller:id/permission_deny_button",
                timeout=2.0
            )
        if not permission_found:
            permission_found = self.wait_for_element(
                resource_id="com.android.permissioncontroller:id/grant_dialog",
                timeout=2.0
            )
        if not permission_found and self.check_activity("GrantPermissionsActivity"):
            permission_found = True
        if permission_found:
            log.info("Permission prompt detected, tapping deny coordinate")
            self.tap_ratio(0.512, 0.6, delay=1)
        _sleep(5)
        
        log.success("Phase 3 completed")
        _sleep(6)
        return True
    
    # ========================================================================
    # GIAI ĐO?N 4: XÁC TH?C OTP
    # ========================================================================
    
    def phase4_otp_verification(self, email: str, refresh_token: str, client_id: str,
                                password: str) -> bool:
        """
        Giai do?n 4: Xác th?c OTP qua mail
        
        Args:
            email: Email
            refresh_token: OAuth2 refresh token
            client_id: OAuth2 client ID
            password: M?t kh?u (dùng l?i n?u c?n)
            
        Returns:
            True n?u xác th?c thành công
        """
        log.info("=" * 50)
        log.info("PHASE 4: OTP Verification")
        log.info("=" * 50)
        if self._should_stop():
            return False
        
        # Ch? màn h́nh xác th?c
        log.info("Waiting for verification screen...")
        verification_found = self.wait_for_element(
            resource_id="com.zhiliaoapp.musically:id/n8t",
            timeout=10.0
        )
        
        if not verification_found:
            log.warning("Verification screen not detected")
            # Ki?m tra xem dă dang nh?p thành công chua
            _sleep(3)
            if self.check_login_success():
                log.success("Already logged in!")
                return True
            return False
        
        log.success("Verification screen appeared")
        
        # Click vào ô OTP
        self.tap_ratio(0.53, 0.299)
        _sleep(0.5)
        
        # Click nút G?i mă
        log.info("Clicking 'Send Code' button...")
        self.tap_ratio(0.521, 0.853)
        
        # B?t d?u timer (ch? l?y OTP t? th?i di?m này tr? di)
        send_code_time = time.time()
        send_code_dt = datetime.now().replace(second=0, microsecond=0)
        attempt = 0
        
        while attempt < Config.MAX_OTP_ATTEMPTS:
            if self._should_stop():
                return False
            attempt += 1
            log.info(f"OTP attempt {attempt}/{Config.MAX_OTP_ATTEMPTS}")
            
            # Polling OTP t? mail
            otp = None
            poll_start = time.time()
            
            while time.time() - poll_start < 30:  # Poll 30s m?i attempt
                if self._should_stop():
                    return False
                otp = get_tiktok_otp(email, refresh_token, client_id, min_time=send_code_dt)
                
                if otp:
                    # Nh?p OTP
                    self.input_text(otp)
                    # Pause sau khi nh?p OTP
                    _sleep(5)
                    
                    # N?u v?n xu?t hi?n permission activity/dialog sau khi nh?p OTP
                    permission_found = self.wait_for_element(
                        resource_id="com.android.permissioncontroller:id/grant_dialog",
                        timeout=2.0
                    )
                    if not permission_found and self.check_activity("GrantPermissionsActivity"):
                        permission_found = True
                    if permission_found:
                        log.info("Post-OTP permission detected, running confirm sequence")
                        self.tap_ratio(0.51, 0.599)
                        _sleep(0.5)
                        self.tap_ratio(0.654, 0.39)
                        _sleep(0.5)
                        self.tap_ratio(0.503, 0.856)
                        _sleep(0.8)
                        # Re-input password then confirm
                        self.input_text(password)
                        _sleep(0.6)
                        self.tap_ratio(0.466, 0.371)
                        _sleep(1.5)
                    
                    # Ki?m tra dang nh?p thành công
                    if self.check_login_success():
                        log.success("Login successful!")
                        return True
                    
                    # Có OTP r?i th́ pause và d?ng, không l?p ti?p
                    log.warning("OTP entered, pausing without further retries")
                    return True
                
                _sleep(Config.OTP_POLL_INTERVAL)
            
            # Ki?m tra timeout 68s d? g?i l?i mă
            elapsed = time.time() - send_code_time
            if elapsed >= Config.OTP_TIMEOUT and not otp:
                log.warning(f"No OTP after {int(elapsed)}s, clicking resend...")
                self.tap_ratio(0.181, 0.338)  # Nút g?i l?i mă
                send_code_time = time.time()  # Reset timer
                send_code_dt = datetime.now().replace(second=0, microsecond=0)
                _sleep(2)
        
        log.error("OTP verification failed after max attempts")
        return False
    
    def check_login_success(self) -> bool:
        """Ki?m tra dang nh?p thành công"""
        try:
            # Ki?m tra m?t s? d?u hi?u dang nh?p thành công
            # Ví d?: Profile có avatar, có th? xem video, etc.
            _sleep(2)
            
            # Ki?m tra không c̣n ? màn h́nh login
            if not self.check_activity("SignUpOrLoginActivity"):
                if not self.check_activity("SparkActivity"):
                    return True
            
            return False
        except Exception:
            return False

    def post_login_actions(self, custom_link: Optional[str] = None):
        """Actions after successful login."""
        if self._should_stop():
            return
        log.info("Post-login: closing app...")
        self.close_tiktok()
        _sleep(2)
        log.info("Post-login: launching TikTok again...")
        self.launch_tiktok(clear_data=False, open_settings=False)
        _sleep(3)

        # Swipe 1-2 times
        self.random_swipe(count=random.randint(1, 2))
        _sleep(2)

        # Tap target coordinate
        self.tap_ratio(0.295, 0.905)
        _sleep(1)

        # Pull-to-refresh (reverse swipe)
        start_x = int(self.screen_width * 0.5)
        start_y = int(self.screen_height * 0.3)
        end_x = int(self.screen_width * 0.5)
        end_y = int(self.screen_height * 0.8)
        self.device.swipe(start_x, start_y, end_x, end_y, duration=0.15)
        log.info("Post-login: refresh swipe done.")
        if self._should_stop():
            return

        # Open a product link in background
        links = [
            "https://vt.tiktok.com/ZS91f13uCsfnd-WGnqb/",
            "https://vt.tiktok.com/ZS91fJYpjTWFM-axQ9h/",
            "https://vt.tiktok.com/ZS91fJ6aCt1aT-VTjhN/",
        ]
        link = custom_link.strip() if custom_link else random.choice(links)
        log.info(f"Opening link: {link}")
        self.open_url(link)

        # Wait for page to load
        _sleep(7.5)
        if self._should_stop():
            return

        # Tap buy button (random)
        buy_coords = [
            (0.671, 0.902),
            (0.577, 0.902),
            (0.889, 0.895),
            (0.664, 0.915),
        ]
        self.tap_random(buy_coords)
        # Wait for Order Submit screen before continuing
        log.info("Waiting for Order Submit screen...")
        order_ready = self.wait_for_element(
            resource_id="com.zhiliaoapp.musically:id/a5c",
            timeout=20.0
        )
        if not order_ready:
            order_ready = self.wait_for_element(
                resource_id="com.zhiliaoapp.musically:id/a5b",
                timeout=6.0
            )
        if not order_ready and self.check_activity(
            "com.ss.android.ugc.aweme.ecommerce.base.osp.page.OrderSubmitActivity"
        ):
            order_ready = True
        if order_ready:
            log.success("Order Submit screen detected")
        else:
            log.warning("Order Submit screen not detected, continuing anyway")
        _sleep(0.6)
        if self._should_stop():
            return

        # Tap add address entry point
        self.tap_ratio(0.466, 0.149)
        _sleep(0.5)

        # Input name
        self.tap_ratio(0.308, 0.332)
        _sleep(0.4)
        self.tap_ratio(0.919, 0.335)  # clear name
        _sleep(0.4)
        name_text = self._random_name()
        self.input_text(name_text)
        _sleep(0.6)
        if self._should_stop():
            return

        # Phone number
        self.tap_ratio(0.359, 0.439)
        _sleep(0.4)
        phone_text = self._random_phone()
        self.input_text(phone_text)
        _sleep(0.5)
        self.tap_ratio(0.238, 0.962)  # back
        _sleep(0.6)
        if self._should_stop():
            return

        # Strong long swipe (same as testadress)
        start_x = int(self.screen_width * 0.58)
        start_y = int(self.screen_height * 0.76)
        end_x = start_x
        end_y = int(self.screen_height * 0.2)
        self.device.swipe(start_x, start_y, end_x, end_y, duration=0.2)
        log.info(f"Swipe: ({start_x},{start_y}) -> ({end_x},{end_y})")
        _sleep(0.6)
        if self._should_stop():
            return

        # Address field
        self.tap_ratio(0.268, 0.534)
        _sleep(0.4)
        self.input_text("Phu Dien, Tan Phu, Dong Nai")
        _sleep(2.0)
        self.tap_ratio(0.352, 0.353)
        _sleep(0.5)
        self.tap_ratio(0.922, 0.283)
        _sleep(0.4)
        address_text = self._random_address(min_words=20)
        self.input_text(address_text)
        _sleep(0.6)
        if self._should_stop():
            return

        # Back and save
        self.tap_ratio(0.238, 0.969)
        _sleep(0.5)
        self.tap_ratio(0.503, 0.903)
        _sleep(1)

        log.info("Post-login: finished form, pausing here.")
        while True:
            if self._should_stop():
                return
            _sleep(60)

    def _random_name(self) -> str:
        words = [
            "minh", "hoang", "thanh", "linh", "nam", "hai", "khanh",
            "huy", "an", "phuc", "tu", "bao", "viet", "trung", "son",
            "lan", "mai", "hoa", "my", "ngoc"
        ]
        count = random.randint(3, 5)
        return " ".join(random.choice(words) for _ in range(count))

    def _random_phone(self) -> str:
        prefixes = [
            "96", "97", "98", "86", "32", "33", "34", "35", "36", "37", "38", "39",
            "90", "93", "89", "70", "76", "77", "78", "79",
            "91", "94", "88", "81", "82", "83", "84", "85",
        ]
        prefix = random.choice(prefixes)
        tail = "".join(str(random.randint(0, 9)) for _ in range(7))
        return prefix + tail

    def _random_address(self, min_words: int = 20) -> str:
        words = [
            "so", "nha", "duong", "ngo", "hem", "khu", "pho", "to",
            "thon", "ap", "xa", "phuong", "quan", "huyen", "tinh",
            "cho", "gan", "truoc", "sau", "ben", "cach", "ganh",
            "truong", "hoc", "benxe", "cong", "hoa", "tan", "phu",
            "dong", "nai", "thanh", "long", "buu", "son", "minh",
            "tien", "binh", "an", "phat", "loc", "yen"
        ]
        count = max(min_words, random.randint(min_words, min_words + 5))
        return " ".join(random.choice(words) for _ in range(count))
    
    # ========================================================================
    # MAIN FLOW
    # ========================================================================
    
    def run_full_flow(self, username: str, password: str, 
                      email: str, refresh_token: str, client_id: str,
                      custom_link: Optional[str] = None) -> bool:
        """
        Ch?y toàn b? lu?ng automation
        
        Args:
            username: TikTok username
            password: TikTok password
            email: Email d? nh?n OTP
            refresh_token: OAuth2 refresh token
            client_id: OAuth2 client ID
            
        Returns:
            True n?u thành công
        """
        try:
            if self._should_stop():
                return False
            # Giai do?n 1: M? app & tuong tác ban d?u
            if not self.phase1_initial_interaction():
                return False
            
            # Giai do?n 2: Đi?u hu?ng vào login
            if not self.phase2_navigate_to_login():
                return False
            
            # Giai do?n 3: Nh?p credentials
            if not self.phase3_input_credentials(username, password):
                return False
            
            # Giai do?n 4: Xác th?c OTP
            if not self.phase4_otp_verification(email, refresh_token, client_id, password=password):
                return False

            # Post-login actions
            self.post_login_actions(custom_link=custom_link)
            
            log.success("=" * 50)
            log.success("FULL FLOW COMPLETED SUCCESSFULLY!")
            log.success("=" * 50)
            return True
            
        except StopRequested:
            log.warning("Flow stopped immediately by user request.")
            return False
        except Exception as e:
            log.error(f"Flow error: {e}")
            return False


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def get_device_serial_from_key(pchanger: PchangerAPI, device_key: str) -> Optional[str]:
    """
    L?y device serial t? Pchanger API d?a trên device key
    
    Args:
        pchanger: PchangerAPI instance
        device_key: Key c?a thi?t b?
        
    Returns:
        Device serial ho?c None
    """
    try:
        result = pchanger.check_device_status(device_key)
        if result.get("status") == "true" or result.get("status") == True:
            return result.get("adb")
        return None
    except Exception as e:
        log.error(f"Cannot get device serial: {e}")
        return None


def _parse_user_pass_mail(raw: str) -> Optional[Tuple[str, str, str, str, str]]:
    """
    Parse input format:
    - New: user|pass|email
    - Old: user|pass|email|mail_pass|refresh_token|client_id (extra parts allowed)
    """
    parts = [p.strip() for p in raw.split("|") if p.strip()]
    if len(parts) < 3:
        return None
    username = parts[0]
    password = parts[1]
    mail_parts = parts[2:]
    email = mail_parts[0] if mail_parts else ""
    refresh_token = mail_parts[2] if len(mail_parts) > 2 else ""
    client_id = mail_parts[3] if len(mail_parts) > 3 else ""
    return username, password, email, refresh_token, client_id


def main():
    """Main function"""
    print("=" * 70)
    print("  TikTok Farm Automation")
    print("  Version: 1.0")
    print("=" * 70)
    print()
    
    try:
        # Only ask for user|pass|mail input
        raw_line = input("Nhap user|pass|mail: ").strip()
        parsed = _parse_user_pass_mail(raw_line)
        if not parsed:
            print("Error: Invalid format. Example: user|pass|mail")
            return
        username, password, email, refresh_token, client_id = parsed

        device_key = Config.DEFAULT_DEVICE_KEY
        print()
        print(f"Device Key: {device_key}")
        print()
        
        # Kh?i t?o Pchanger API
        pchanger = PchangerAPI()
        
        # L?y device serial t? Pchanger
        log.info("Getting device serial from Pchanger...")
        device_serial = get_device_serial_from_key(pchanger, device_key)
        
        if not device_serial:
            log.error("Cannot get device serial from Pchanger!")
            return
        
        log.success(f"Device Serial: {device_serial}")
        
        # GIAI ĐO?N 0: Chu?n b?
        log.info("=" * 50)
        log.info("PHASE 0: Preparation")
        log.info("=" * 50)

        # Ch? device s?n sàng
        if not pchanger.wait_for_device_ready(device_key):
            log.error("Device not ready, exiting...")
            return

        log.info(f"Processing: {username}")
        log.info(f"Email: {email}")
        log.info(f"Token: {refresh_token[:20]}..." if refresh_token else "Token: (empty)")

        # Kh?i t?o automation
        try:
            automation = TikTokAutomation(device_serial)
            device_model = automation.get_device_model()
            log.info(f"Device Model: {device_model}")
        except Exception as e:
            log.error(f"Cannot connect to device: {e}")
            return

        # Ch?y flow
        success = automation.run_full_flow(
            username=username,
            password=password,
            email=email,
            refresh_token=refresh_token,
            client_id=client_id
        )

        if success:
            log.info("Skipping backup (paused)")
        else:
            log.info("")
            log.info("Failed flow")

        
        print()
        print("=" * 70)
        print("  Script finished")
        print("=" * 70)
        
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\nError: {e}")


if __name__ == "__main__":
    main()


