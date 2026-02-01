"""
TikTok Farm Automation Script
=============================
Script tự động hóa nuôi nick TikTok sử dụng uiautomator2, gspread và ADB.

Author: Automation Team
Package: com.zhiliaoapp.musically
"""

import os
import sys
import time
import random
import requests
from datetime import datetime
from typing import Optional, Tuple, List, Dict, Any

import uiautomator2 as u2
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    """Cấu hình cho TikTok automation"""
    
    # TikTok App
    TIKTOK_PACKAGE = "com.zhiliaoapp.musically"
    
    # API Endpoints
    MAIL_API_URL = "https://tools.dongvanfb.net/api/get_code_oauth2"
    PCHANGER_BASE_URL = "http://127.0.0.1:8080"
    
    # Google Sheets
    CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "credentials.json")
    SHEET_NAME = "TikTok Farm"  # Tên sheet Google
    SHEET_URL = "https://docs.google.com/spreadsheets/d/195HgTVjWlIrR41VBoHf90thTf1YSph6YCiCcYqxkdcg/edit?gid=0#gid=0"
    
    # Timeouts
    OTP_TIMEOUT = 68  # Giây trước khi gửi lại mã
    OTP_POLL_INTERVAL = 3  # Giây giữa các lần kiểm tra OTP
    MAX_OTP_ATTEMPTS = 5  # Số lần thử tối đa
    DEVICE_BUSY_TIMEOUT = 300  # Giây chờ device hết busy
    
    # Activities
    ACTIVITY_NEW_USER = "NewUserJourneyActivity"
    ACTIVITY_SIGNUP_LOGIN = "SignUpOrLoginActivity"
    ACTIVITY_SPARK = "com.bytedance.hybrid.spark.page.SparkActivity"


# ============================================================================
# LOGGING
# ============================================================================

class Logger:
    """Simple logger với màu sắc"""
    
    @staticmethod
    def info(msg: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [INFO] {msg}")
    
    @staticmethod
    def success(msg: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [SUCCESS] ✓ {msg}")
    
    @staticmethod
    def warning(msg: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [WARNING] ⚠ {msg}")
    
    @staticmethod
    def error(msg: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [ERROR] ✗ {msg}")


log = Logger()


# ============================================================================
# GOOGLE SHEETS HANDLER
# ============================================================================

class GoogleSheetsHandler:
    """Xử lý đọc/ghi Google Sheets"""
    
    def __init__(self, credentials_file: str, sheet_url_or_name: str):
        """
        Khởi tạo kết nối Google Sheets
        
        Args:
            credentials_file: Đường dẫn file credentials.json
            sheet_url_or_name: URL hoặc tên Google Sheet
        """
        self.credentials_file = credentials_file
        self.sheet_url_or_name = sheet_url_or_name
        self.client = None
        self.sheet = None
        self._connect()
    
    def _connect(self):
        """Kết nối đến Google Sheets"""
        try:
            scope = [
                "https://www.googleapis.com/auth/spreadsheets", # <-- Dùng cái này
                "https://www.googleapis.com/auth/drive"
            ]
            creds = ServiceAccountCredentials.from_json_keyfile_name(
                self.credentials_file, scope
            )
            self.client = gspread.authorize(creds)
            
            # Kiểm tra nếu là URL
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
        Lấy dòng tiếp theo chưa xử lý
        
        Returns:
            Tuple (row_number, user, password, mail) hoặc None
        """
        try:
            all_data = self.sheet.get_all_values()
            
            for idx, row in enumerate(all_data[1:], start=2):  # Bỏ qua header
                col_a = row[0] if len(row) > 0 else ""  # user|pass|mail
                col_b = row[1] if len(row) > 1 else ""  # Trạng thái
                
                # Nếu cột A có dữ liệu và cột B trống -> chưa xử lý
                if col_a and not col_b.strip():  # strip() để loại bỏ khoảng trắng
                    # Chỉ split 2 lần đầu, phần còn lại gom vào mail
                    parts = col_a.split("|", 2)
                    if len(parts) >= 3:
                        user = parts[0].strip()
                        password = parts[1].strip()
                        mail = parts[2].strip()  # Chứa toàn bộ: email|mail_pass|token|client_id
                        log.info(f"Found unprocessed row {idx}: {user}")
                        return (idx, user, password, mail)
            
            log.warning("No unprocessed rows found")
            return None
            
        except Exception as e:
            log.error(f"Error reading sheet: {e}")
            return None
    
    def update_status(self, row: int, status: str):
        """Cập nhật trạng thái cột B"""
        try:
            self.sheet.update_cell(row, 2, status)
            log.info(f"Updated row {row} status: {status}")
        except Exception as e:
            log.error(f"Failed to update status: {e}")
    
    def update_device_id(self, row: int, device_id: str):
        """Cập nhật Device ID cột C"""
        try:
            self.sheet.update_cell(row, 3, device_id)
        except Exception as e:
            log.error(f"Failed to update device ID: {e}")
    
    def update_backup_time(self, row: int, timestamp: str):
        """Cập nhật thời gian backup cột D"""
        try:
            self.sheet.update_cell(row, 4, timestamp)
        except Exception as e:
            log.error(f"Failed to update backup time: {e}")
    
    def update_backup_name(self, row: int, backup_name: str):
        """Cập nhật tên file backup cột E"""
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
        Kiểm tra trạng thái thiết bị
        
        Args:
            device_key: Key của thiết bị
            
        Returns:
            Dict với status và thông tin thiết bị
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
        Chờ thiết bị hết busy
        
        Args:
            device_key: Key thiết bị
            timeout: Thời gian chờ tối đa (giây)
            
        Returns:
            True nếu device sẵn sàng
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
            
            time.sleep(5)
        
        log.error(f"Device not ready after {timeout}s")
        return False
    
    def backup_device(self, device_key: str, backup_name: str) -> Optional[str]:
        """
        Tạo backup cho thiết bị
        
        Args:
            device_key: Key thiết bị
            backup_name: Tên file backup
            
        Returns:
            Tên backup nếu thành công, None nếu lỗi
        """
        try:
            # Chờ device sẵn sàng
            if not self.wait_for_device_ready(device_key):
                return None
            
            url = f"{self.base_url}/dev/{device_key}/backup?name={backup_name}"
            log.info(f"Creating backup: {backup_name}")
            
            response = requests.get(url, timeout=30)
            result = response.json()
            
            if result.get("status") == True:
                log.success(f"Backup initiated: {backup_name}")
                
                # Chờ backup hoàn tất (device hết busy)
                time.sleep(5)
                if self.wait_for_device_ready(device_key, timeout=600):
                    return backup_name
            else:
                log.error(f"Backup failed: {result.get('note', 'Unknown error')}")
            
            return None
            
        except Exception as e:
            log.error(f"Backup error: {e}")
            return None
    
    def get_devices(self) -> List[Dict]:
        """Lấy danh sách thiết bị"""
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
                   min_time: Optional[datetime] = None) -> Optional[str]:
    """
    Lấy mã OTP TikTok từ mail
    
    Args:
        email: Địa chỉ email
        refresh_token: OAuth2 refresh token
        client_id: OAuth2 client ID
        
    Returns:
        Mã OTP nếu tìm thấy, None nếu không
    """
    try:
        payload = {
            "email": email,
            "refresh_token": refresh_token,
            "client_id": client_id,
            "type": "tiktok"
        }
        
        response = requests.post(
            Config.MAIL_API_URL,
            json=payload,
            timeout=15
        )
        
        result = response.json()
        
        if result.get("status") == True and result.get("code"):
            code = result.get("code")
            mail_date = _parse_mail_date(result.get("date", ""))
            if min_time:
                if not mail_date:
                    log.warning("OTP date missing/unparseable, skipping")
                    return None
                # API chỉ có phút, nên so sánh theo phút
                min_time_floor = min_time.replace(second=0, microsecond=0)
                if mail_date < min_time_floor:
                    log.info(f"OTP is older than send time ({mail_date} < {min_time}), skipping")
                    return None
            log.success(f"Got OTP: {code}")
            return code
        
        return None
        
    except Exception as e:
        log.error(f"Mail API error: {e}")
        return None


# ============================================================================
# TIKTOK AUTOMATION
# ============================================================================

class TikTokAutomation:
    """Main class để điều khiển TikTok automation"""
    
    def __init__(self, device_serial: str):
        """
        Khởi tạo automation
        
        Args:
            device_serial: Serial number của thiết bị Android
        """
        self.device_serial = device_serial
        self.device = None
        self.screen_width = 1080
        self.screen_height = 1920
        self._connect_device()
    
    def _connect_device(self):
        """Kết nối đến thiết bị qua uiautomator2"""
        try:
            self.device = u2.connect(self.device_serial)
            info = self.device.info
            self.screen_width = info.get("displayWidth", 1080)
            self.screen_height = info.get("displayHeight", 1920)
            log.success(f"Connected to device: {self.device_serial}")
            log.info(f"Screen size: {self.screen_width}x{self.screen_height}")
        except Exception as e:
            log.error(f"Failed to connect device: {e}")
            raise
    
    def get_device_model(self) -> str:
        """Lấy tên model thiết bị"""
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
        Tap tại tọa độ theo tỷ lệ màn hình
        
        Args:
            x_ratio: Tỷ lệ X (0-1)
            y_ratio: Tỷ lệ Y (0-1)
            delay: Delay sau khi tap (giây)
        """
        x = int(x_ratio * self.screen_width)
        y = int(y_ratio * self.screen_height)
        self.device.click(x, y)
        log.info(f"Tapped at ({x_ratio:.3f}, {y_ratio:.3f}) -> ({x}, {y})")
        time.sleep(delay)
    
    def _adb_shell(self, args: List[str]):
        """Run adb shell command on the device."""
        import subprocess
        subprocess.run(
            ["adb", "-s", self.device_serial, "shell"] + args,
            capture_output=True
        )

    def tap_random(self, coords: List[Tuple[float, float]], delay: float = 0.3):
        """
        Tap ngẫu nhiên vào một trong các tọa độ
        
        Args:
            coords: List các tuple (x_ratio, y_ratio)
            delay: Delay sau khi tap
        """
        x_ratio, y_ratio = random.choice(coords)
        self.tap_ratio(x_ratio, y_ratio, delay)
    
    def random_swipe(self, count: int = None):
        """
        Thực hiện vuốt ngẫu nhiên
        
        Args:
            count: Số lần vuốt (None = random 3-5)
        """
        if count is None:
            count = random.randint(3, 5)
        
        log.info(f"Performing {count} random swipe(s)...")
        
        for i in range(count):
            # Random vị trí start/end (tránh sát trên/dưới)
            start_x = random.randint(int(self.screen_width * 0.2), int(self.screen_width * 0.8))
            start_y = random.randint(int(self.screen_height * 0.55), int(self.screen_height * 0.8))
            end_x = random.randint(int(self.screen_width * 0.2), int(self.screen_width * 0.8))
            end_y = random.randint(int(self.screen_height * 0.2), int(self.screen_height * 0.5))
            
            # Random duration (tránh hold lâu)
            duration = random.uniform(0.15, 0.35)
            
            self.device.swipe(start_x, start_y, end_x, end_y, duration=duration)
            log.info(f"Swipe {i+1}: ({start_x},{start_y}) -> ({end_x},{end_y})")
            time.sleep(3)
    
    def input_text(self, text: str):
        """Nhập text"""
        # Clear existing text: move cursor to end and long-press delete
        self._adb_shell(["input", "keyevent", "123"])  # KEYCODE_MOVE_END
        self._adb_shell(["input", "keyevent", "--longpress", "67"])  # KEYCODE_DEL

        escaped_text = str(text).replace(" ", "%s")
        self._adb_shell(["input", "text", escaped_text])
        log.info(f"Inputted text: {text}")
    
    def wait_for_element(self, xpath: str = None, text: str = None, 
                         resource_id: str = None, timeout: float = 10.0) -> bool:
        """
        Chờ element xuất hiện
        
        Args:
            xpath: XPath của element
            text: Text của element
            resource_id: Resource ID của element
            timeout: Thời gian chờ tối đa
            
        Returns:
            True nếu element xuất hiện
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
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
            time.sleep(0.5)
        
        return False
    
    def check_activity(self, activity_name: str) -> bool:
        """Kiểm tra activity hiện tại"""
        try:
            current = self.device.app_current()
            return activity_name in current.get("activity", "")
        except Exception:
            return False
    
    def launch_tiktok(self):
        """Mở app TikTok"""
        log.info("Opening Date settings...")
        self._adb_shell(["am", "start", "-a", "android.settings.DATE_SETTINGS"])
        time.sleep(1)
        self.tap_ratio(0.875, 0.286, delay=0.3)
        self.tap_ratio(0.34, 0.376, delay=0.3)
        self.tap_ratio(0.245, 0.341, delay=0.3)

        date_choice = random.choice([
            (0.241, 0.449),
            (0.34, 0.453),
            "text:3",
            (0.594, 0.445),
            (0.681, 0.449),
            (0.25, 0.5),
            (0.25, 0.558),
            (0.25, 0.596),
            (0.336, 0.497),
            (0.435, 0.558),
            (0.517, 0.592),
            (0.512, 0.537),
            (0.612, 0.541),
            (0.681, 0.55),
            (0.599, 0.587),
            (0.775, 0.592),
        ])
        if date_choice == "text:3" and self.device(text="3").exists:
            log.info("Tapping text '3' in Date settings")
            self.device(text="3").click()
            time.sleep(0.3)
        else:
            if date_choice == "text:3":
                date_choice = random.choice([
                    (0.241, 0.449),
                    (0.34, 0.453),
                    (0.594, 0.445),
                    (0.681, 0.449),
                    (0.25, 0.5),
                    (0.25, 0.558),
                    (0.25, 0.596),
                    (0.336, 0.497),
                    (0.435, 0.558),
                    (0.517, 0.592),
                    (0.512, 0.537),
                    (0.612, 0.541),
                    (0.681, 0.55),
                    (0.599, 0.587),
                    (0.775, 0.592),
                ])
            self.tap_ratio(date_choice[0], date_choice[1], delay=0.3)

        self.tap_ratio(0.758, 0.74, delay=0.6)
        log.info("Launching TikTok...")
        self.device.app_start(Config.TIKTOK_PACKAGE)
        time.sleep(3)
    
    def unlock_screen(self):
        """
        Mở khóa màn hình (copy từ shopee/test.py)
        Dùng ADB shell command trực tiếp
        """
        log.info("Unlocking screen...")
        import subprocess
        
        # Press menu button (keycode 82) - giống shopee
        subprocess.run(
            ["adb", "-s", self.device_serial, "shell", "input", "keyevent", "82"],
            capture_output=True
        )
        time.sleep(0.5)
        
        # Swipe up to unlock - giống shopee: swipe(500, 1000, 500, 200, 300)
        subprocess.run(
            ["adb", "-s", self.device_serial, "shell", "input", "swipe", "500", "1000", "500", "200", "300"],
            capture_output=True
        )
        log.success("Screen unlocked")
        time.sleep(0.5)
    
    # ========================================================================
    # GIAI ĐOẠN 1: MỞ APP & TƯƠNG TÁC BAN ĐẦU
    # ========================================================================
    
    def phase1_initial_interaction(self) -> bool:
        """
        Giai đoạn 1: Mở app và xử lý màn hình chào mừng
        
        Returns:
            True nếu thành công
        """
        log.info("=" * 50)
        log.info("PHASE 1: Initial Interaction")
        log.info("=" * 50)
        
        # Mở khóa màn hình trước
        self.unlock_screen()
        
        # Launch TikTok
        self.launch_tiktok()
        
        # Chờ màn hình chào mừng (1 trong 2 case)
        log.info("Waiting for welcome screen...")
        
        welcome_found = False
        for _ in range(20):  # Timeout 10s
            # Case 1: "Đồng ý và tiếp tục"
            if self.device(resourceId="com.zhiliaoapp.musically:id/e6h").exists:
                log.success("Found: 'Đồng ý và tiếp tục'")
                welcome_found = True
                break
            # Case 2: "Chào mừng bạn đến với TikTok"
            if self.device(resourceId="com.zhiliaoapp.musically:id/e6p").exists:
                log.success("Found: 'Chào mừng bạn đến với TikTok'")
                welcome_found = True
                break
            time.sleep(0.5)
        
        if not welcome_found:
            log.warning("Welcome screen not detected, continuing anyway...")
        
        # Chờ 2s trước khi tap
        time.sleep(2)
        
        # Click Random 1 trong các tọa độ
        coords_1 = [(0.775, 0.901), (0.646, 0.895), (0.254, 0.905), (0.452, 0.893)]
        self.tap_random(coords_1)
        time.sleep(2)
        
        time.sleep(2)
        
        # Click tiếp 1 trong các tọa độ
        coords_2 = [(0.232, 0.899), (0.155, 0.91)]
        self.tap_random(coords_2)
        
        time.sleep(2)
        
        # Thực hiện swipe ngẫu nhiên 1-3 lần
        self.random_swipe()
        
        time.sleep(2)
        
        log.success("Phase 1 completed")
        return True
    
    # ========================================================================
    # GIAI ĐOẠN 2: ĐIỀU HƯỚNG VÀO LOGIN
    # ========================================================================
    
    def phase2_navigate_to_login(self) -> bool:
        """
        Giai đoạn 2: Điều hướng vào màn hình đăng nhập
        
        Returns:
            True nếu thành công
        """
        log.info("=" * 50)
        log.info("PHASE 2: Navigate to Login")
        log.info("=" * 50)
        
        # Click nút Hồ sơ/Tôi
        log.info("Clicking Profile button...")
        self.tap_ratio(0.922, 0.694)
        time.sleep(2)
        
        # Click Random
        coords_3 = [(0.702, 0.903), (0.629, 0.907), (0.685, 0.905)]
        self.tap_random(coords_3)
        time.sleep(1)
        
        # Click tọa độ cố định
        self.tap_ratio(0.474, 0.341)
        time.sleep(2)
        
        # Click Random
        coords_4 = [(0.702, 0.119), (0.629, 0.119)]
        self.tap_random(coords_4)
        time.sleep(0.5)
        
        # Click Random tiếp
        coords_5 = [(0.418, 0.198), (0.133, 0.196)]
        self.tap_random(coords_5)
        time.sleep(1)
        
        log.success("Phase 2 completed")
        return True
    
    # ========================================================================
    # GIAI ĐOẠN 3: NHẬP USER & PASSWORD
    # ========================================================================
    
    def phase3_input_credentials(self, username: str, password: str) -> bool:
        """
        Giai đoạn 3: Nhập username và password
        
        Args:
            username: Tên đăng nhập
            password: Mật khẩu
            
        Returns:
            True nếu thành công
        """
        log.info("=" * 50)
        log.info("PHASE 3: Input Credentials")
        log.info("=" * 50)
        
        # Nhập username
        log.info(f"Inputting username: {username}")
        self.input_text(username)
        time.sleep(1)
        
        # Click Random để tiếp tục
        coords_6 = [(0.512, 0.552), (0.612, 0.566)]
        self.tap_random(coords_6)
        
        # Chờ màn hình password
        log.info("Waiting for password screen...")
        password_screen_found = self.wait_for_element(
            resource_id="com.zhiliaoapp.musically:id/ecc",
            timeout=10.0
        )
        
        if not password_screen_found:
            # Thử kiểm tra text
            password_screen_found = self.wait_for_element(
                text="Nhập mật khẩu",
                timeout=5.0
            )
        
        if password_screen_found:
            log.success("Password screen appeared")
        else:
            log.warning("Password screen not detected, continuing...")
        
        # Click Random vào ô password
        coords_7 = [(0.181, 0.234), (0.422, 0.246)]
        self.tap_random(coords_7)
        time.sleep(0.5)
        
        # Nhập password
        log.info("Inputting password...")
        self.input_text(password)
        time.sleep(1)
        
        # Click nút Đăng nhập
        coords_8 = [(0.461, 0.558), (0.702, 0.564)]
        self.tap_random(coords_8)
        # Nếu xuất hiện permission hỏi danh bạ thì xử lý nhanh
        permission_found = self.wait_for_element(
            resource_id="com.android.permissioncontroller:id/permission_message",
            timeout=2.0
        )
        if not permission_found:
            permission_found = self.wait_for_element(
                resource_id="com.android.permissioncontroller:id/permission_deny_button",
                timeout=2.0
            )
        if permission_found:
            log.info("Permission prompt detected, tapping deny coordinate")
            self.tap_ratio(0.512, 0.6, delay=1)
        time.sleep(5)
        
        log.success("Phase 3 completed")
        time.sleep(6)
        return True
    
    # ========================================================================
    # GIAI ĐOẠN 4: XÁC THỰC OTP
    # ========================================================================
    
    def phase4_otp_verification(self, email: str, refresh_token: str, client_id: str) -> bool:
        """
        Giai đoạn 4: Xác thực OTP qua mail
        
        Args:
            email: Email
            refresh_token: OAuth2 refresh token
            client_id: OAuth2 client ID
            
        Returns:
            True nếu xác thực thành công
        """
        log.info("=" * 50)
        log.info("PHASE 4: OTP Verification")
        log.info("=" * 50)
        
        # Chờ màn hình xác thực
        log.info("Waiting for verification screen...")
        verification_found = self.wait_for_element(
            resource_id="com.zhiliaoapp.musically:id/n6b",
            timeout=15.0
        )
        
        if not verification_found:
            log.warning("Verification screen not detected")
            # Kiểm tra xem đã đăng nhập thành công chưa
            time.sleep(3)
            if self.check_login_success():
                log.success("Already logged in!")
                return True
            return False
        
        log.success("Verification screen appeared")
        
        # Click vào ô OTP
        self.tap_ratio(0.53, 0.299)
        time.sleep(0.5)
        
        # Click nút Gửi mã
        log.info("Clicking 'Send Code' button...")
        self.tap_ratio(0.521, 0.853)
        
        # Bắt đầu timer (chỉ lấy OTP từ thời điểm này trở đi)
        send_code_time = time.time()
        send_code_dt = datetime.now().replace(second=0, microsecond=0)
        attempt = 0
        
        while attempt < Config.MAX_OTP_ATTEMPTS:
            attempt += 1
            log.info(f"OTP attempt {attempt}/{Config.MAX_OTP_ATTEMPTS}")
            
            # Polling OTP từ mail
            otp = None
            poll_start = time.time()
            
            while time.time() - poll_start < 30:  # Poll 30s mỗi attempt
                otp = get_tiktok_otp(email, refresh_token, client_id, min_time=send_code_dt)
                
                if otp:
                    # Nhập OTP
                    self.input_text(otp)
                    # Pause sau khi nhập OTP
                    time.sleep(5)
                    
                    # Kiểm tra đăng nhập thành công
                    if self.check_login_success():
                        log.success("Login successful!")
                        return True
                    
                    # Có OTP rồi thì pause và dừng, không lặp tiếp
                    log.warning("OTP entered, pausing without further retries")
                    return True
                
                time.sleep(Config.OTP_POLL_INTERVAL)
            
            # Kiểm tra timeout 68s để gửi lại mã
            elapsed = time.time() - send_code_time
            if elapsed >= Config.OTP_TIMEOUT and not otp:
                log.warning(f"No OTP after {int(elapsed)}s, clicking resend...")
                self.tap_ratio(0.181, 0.338)  # Nút gửi lại mã
                send_code_time = time.time()  # Reset timer
                send_code_dt = datetime.now().replace(second=0, microsecond=0)
                time.sleep(2)
        
        log.error("OTP verification failed after max attempts")
        return False
    
    def check_login_success(self) -> bool:
        """Kiểm tra đăng nhập thành công"""
        try:
            # Kiểm tra một số dấu hiệu đăng nhập thành công
            # Ví dụ: Profile có avatar, có thể xem video, etc.
            time.sleep(2)
            
            # Kiểm tra không còn ở màn hình login
            if not self.check_activity("SignUpOrLoginActivity"):
                if not self.check_activity("SparkActivity"):
                    return True
            
            return False
        except Exception:
            return False
    
    # ========================================================================
    # MAIN FLOW
    # ========================================================================
    
    def run_full_flow(self, username: str, password: str, 
                      email: str, refresh_token: str, client_id: str) -> bool:
        """
        Chạy toàn bộ luồng automation
        
        Args:
            username: TikTok username
            password: TikTok password
            email: Email để nhận OTP
            refresh_token: OAuth2 refresh token
            client_id: OAuth2 client ID
            
        Returns:
            True nếu thành công
        """
        try:
            # Giai đoạn 1: Mở app & tương tác ban đầu
            if not self.phase1_initial_interaction():
                return False
            
            # Giai đoạn 2: Điều hướng vào login
            if not self.phase2_navigate_to_login():
                return False
            
            # Giai đoạn 3: Nhập credentials
            if not self.phase3_input_credentials(username, password):
                return False
            
            # Giai đoạn 4: Xác thực OTP
            if not self.phase4_otp_verification(email, refresh_token, client_id):
                return False
            
            log.success("=" * 50)
            log.success("FULL FLOW COMPLETED SUCCESSFULLY!")
            log.success("=" * 50)
            return True
            
        except Exception as e:
            log.error(f"Flow error: {e}")
            return False


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def get_device_serial_from_key(pchanger: PchangerAPI, device_key: str) -> Optional[str]:
    """
    Lấy device serial từ Pchanger API dựa trên device key
    
    Args:
        pchanger: PchangerAPI instance
        device_key: Key của thiết bị
        
    Returns:
        Device serial hoặc None
    """
    try:
        result = pchanger.check_device_status(device_key)
        if result.get("status") == "true" or result.get("status") == True:
            return result.get("adb")
        return None
    except Exception as e:
        log.error(f"Cannot get device serial: {e}")
        return None


def main():
    """Main function"""
    print("=" * 70)
    print("  TikTok Farm Automation")
    print("  Version: 1.0")
    print("=" * 70)
    print()
    
    try:
        # Get user input
        device_key = input("Enter PChanger Device Key: ").strip()
        if not device_key:
            print("Error: Device key cannot be empty")
            return
        
        sheet_url = Config.SHEET_URL
        if not sheet_url:
            print("Error: Google Sheet name cannot be empty")
            return
        
        default_template = f"{datetime.now().strftime('%d-%m-%Y')}---"
        file_prefix = input(
            f"Enter backup name template (default: {default_template}): "
        ).strip()
        if not file_prefix:
            file_prefix = default_template
        
        start_num_input = input("Enter backup start index (default: 1): ").strip()
        if start_num_input:
            try:
                start_num = int(start_num_input)
                if start_num < 1:
                    print("Error: Backup start index must be at least 1")
                    return
            except ValueError:
                print("Error: Invalid backup start index format")
                return
        else:
            start_num = 1
        
        print()
        print(f"Device Key: {device_key}")
        print(f"File prefix: {file_prefix}")
        print(f"Starting number: {start_num}")
        print()
        
        # Khởi tạo Pchanger API
        pchanger = PchangerAPI()
        
        # Lấy device serial từ Pchanger
        log.info("Getting device serial from Pchanger...")
        device_serial = get_device_serial_from_key(pchanger, device_key)
        
        if not device_serial:
            log.error("Cannot get device serial from Pchanger!")
            return
        
        log.success(f"Device Serial: {device_serial}")
        
        # Khởi tạo Google Sheets
        try:
            sheets = GoogleSheetsHandler(Config.CREDENTIALS_FILE, sheet_url)
        except Exception as e:
            log.error(f"Cannot connect to Google Sheets: {e}")
            return
        
        # Counter cho tên file
        current_num = start_num
        
        # Vòng lặp xử lý nhiều tài khoản
        while True:
            # GIAI ĐOẠN 0: Chuẩn bị
            log.info("=" * 50)
            log.info(f"PHASE 0: Preparation (Account #{current_num})")
            log.info("=" * 50)
            
            # Chờ device sẵn sàng
            if not pchanger.wait_for_device_ready(device_key):
                log.error("Device not ready, exiting...")
                break
            
            # Lấy dữ liệu từ Sheet
            row_data = sheets.get_next_unprocessed_row()
            if not row_data:
                log.info("No more data to process")
                break
            
            row_num, username, password, mail_data = row_data
            
            # Parse mail data: email|mail_pass|token|client_id
            mail_parts = mail_data.split("|")
            email = mail_parts[0] if len(mail_parts) > 0 else ""
            # mail_pass = mail_parts[1] (không cần dùng)
            refresh_token = mail_parts[2] if len(mail_parts) > 2 else ""  # Token ở vị trí thứ 3
            client_id = mail_parts[3] if len(mail_parts) > 3 else ""  # Client ID ở vị trí thứ 4
            
            log.info(f"Processing: {username}")
            log.info(f"Email: {email}")
            log.info(f"Token: {refresh_token[:20]}..." if refresh_token else "Token: (empty)")
        
            # Cập nhật trạng thái đang xử lý
            sheets.update_status(row_num, "PROCESSING")
            
            # Khởi tạo automation
            try:
                automation = TikTokAutomation(device_serial)
                # Lấy tên model và ghi vào cột C
                device_model = automation.get_device_model()
                sheets.update_device_id(row_num, device_model)
                log.info(f"Device Model: {device_model}")
            except Exception as e:
                log.error(f"Cannot connect to device: {e}")
                sheets.update_status(row_num, f"ERROR: {e}")
                return
            
            # Chạy flow
            success = automation.run_full_flow(
                username=username,
                password=password,
                email=email,
                refresh_token=refresh_token,
                client_id=client_id
            )
            
            if success:
                # Tạm thời bỏ backup cho nhanh
                sheets.update_status(row_num, "SUCCESS (no backup)")
                log.info("Skipping backup (paused)")
                current_num += 1
            else:
                sheets.update_status(row_num, "FAILED")
                
                log.info("")
                log.info("Moving to next account...")
                time.sleep(2)
            
            break

        
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
