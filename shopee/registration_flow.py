"""
Registration flow extracted from test.py.
"""

import base64
import random
import re
import time
import xml.etree.ElementTree as ET
from typing import Optional

import requests
import cv2
import numpy as np

try:
    import uiautomator2 as u2
    U2_AVAILABLE = True
except ImportError:
    U2_AVAILABLE = False
    print("[WARNING] uiautomator2 not available. Install: pip install uiautomator2")


class RegistrationFlow:
    def __init__(self, automation):
        self._ctx = automation
        self.adb = automation.adb
        self.sms = automation.sms
        self.config = automation.config
        self.popup_handler = automation.popup_handler
        self.captcha_solver = automation.captcha_solver
        self.logger = automation.logger
        self._click_visible_product = automation._click_visible_product

    @property
    def serial(self):
        return self._ctx.serial

    @property
    def screen_width(self):
        return self._ctx.screen_width

    @property
    def screen_height(self):
        return self._ctx.screen_height

    def navigate_to_login_screen(self):
        """
        Navigate to the login screen via the Notification tab.
        """
        self.logger.info("Navigating to login via Notification tab...")

        # Sử dụng tọa độ trực tiếp từ weditor: (0.694, 0.912)
        x_notification = int(self.screen_width * 0.694)
        y_notification = int(self.screen_height * 0.912)
        self.logger.info(f"Tapping Notification tab at coordinates: ({x_notification}, {y_notification})")
        self.adb.tap(self.serial, x_notification, y_notification)

        time.sleep(3)

        self.logger.info("Tapping registration entry from Notification tab...")
        reg_x = int(self.screen_width * 0.671)
        reg_y = int(self.screen_height * 0.921)
        self.adb.tap(self.serial, reg_x, reg_y)
        time.sleep(5)  # Đợi màn hình registration load

        xml_check = self.adb.dump_ui_hierarchy(self.serial)

        if self.config.RESOURCE_ID_PHONE_INPUT not in xml_check:
            self.logger.info("Not at phone input yet, looking for explicit Login button...")
            login_keywords = ["Dang nhap", "Login", "Log In"]
            for kw in login_keywords:
                btns = self.popup_handler._find_by_text_from_xml(xml_check, kw)
                visible_btns = [b for b in btns if b.is_visible(self.screen_width, self.screen_height)]
                if visible_btns:
                    cx, cy = visible_btns[0].center
                    self.adb.tap(self.serial, cx, cy)
                    time.sleep(2)
                    break




    
    def run_from_notification(self) -> bool:
        """Tap Notification tab at (0.694, 0.912) then continue registration flow."""
        self.navigate_to_login_screen()
        return self.perform_registration_flow()

    def perform_registration_flow(self):
        """
        Flow: rent phone -> input phone -> click continue -> PAUSE (KHÔNG thuê OTP).
        """
        self.logger.section("Registration Flow (PAUSE after Continue)")

        # Step 1: Thuê số điện thoại - RETRY cho đến khi thành công
        self.logger.info("Step 1: Renting phone number (with retry)...")
        
        session_id = None
        phone_number = None
        max_rent_retries = 10  # thử tối đa 10 lần rent số mới
        rent_delay = 5  # chờ 5s giữa các lần retry
        
        for rent_attempt in range(1, max_rent_retries + 1):
            self.logger.info(f"📞 Rent attempt {rent_attempt}/{max_rent_retries}...")
            
            session_id, phone_number = self.sms.rent_number()
            
            if phone_number:
                self.logger.info(f"✓ Successfully rented number: {phone_number} (Session: {session_id})")
                break  # thành công → thoát loop
            else:
                self.logger.warning(f"⚠ Rent failed (attempt {rent_attempt}/{max_rent_retries})")
                if rent_attempt < max_rent_retries:
                    self.logger.info(f"Retrying in {rent_delay}s...")
                    time.sleep(rent_delay)
                else:
                    self.logger.error("❌ Max rent retries reached - cannot get phone number!")
                    self.logger.error("Possible reasons:")
                    self.logger.error("  - API key invalid or expired")
                    self.logger.error("  - Service out of numbers")
                    self.logger.error("  - Network/connectivity issue")
                    return False  # dừng toàn bộ flow nếu không có số
        
        # Nếu sau tất cả vẫn không có số → fail
        if not phone_number:
            self.logger.error("❌ Cannot proceed without phone number!")
            return False

        # Step 2: Nhập số điện thoại - ENHANCED với uiautomator2
        self.logger.info(f"Step 2: Entering phone number {phone_number}...")
        
        if not U2_AVAILABLE:
            self.logger.error("⚠ uiautomator2 không cài → không input được!")
            self.logger.error("Install: pip install uiautomator2")
            return False
        
        try:
            device_u2 = u2.connect(self.serial)
            self.logger.info("✓ U2 connected for phone input")
        except Exception as e:
            self.logger.error(f"✗ Cannot connect uiautomator2: {e}")
            return False
        
        phone_input_found = False
        
        # === METHOD 1: Tìm bằng resource-id chính xác ===
        self.logger.info("Trying Method 1: resource-id...")
        resource_ids_to_try = [
            "com.shopee.vn:id/cret_edit_text",
            "com.shopee.vn:id/et_phone",
            "com.shopee.vn:id/phone_input",
            "com.shopee.vn:id/edit_phone",
            "com.shopee.vn:id/etPhone",
            "com.shopee.vn:id/phone_number",
            "com.shopee.vn:id/input_phone",
        ]
        
        for res_id in resource_ids_to_try:
            try:
                element = device_u2(resourceId=res_id)
                if element.exists:
                    self.logger.info(f"✓ Found phone input by resource-id: {res_id}")
                    element.click()
                    time.sleep(0.3)
                    element.set_text(phone_number)
                    phone_input_found = True
                    break
            except Exception as e:
                self.logger.debug(f"resource-id {res_id} not found: {e}")
        
        # === METHOD 2: Tìm EditText có hint về số điện thoại ===
        if not phone_input_found:
            self.logger.info("Trying Method 2: EditText with phone-related hint...")
            try:
                # Tìm EditText có hint chứa từ khóa
                hints_to_try = ["số điện thoại", "phone", "nhập số", "điện thoại", "sdt", "mobile"]
                edit_texts = device_u2(className="android.widget.EditText")
                
                if edit_texts.exists:
                    count = edit_texts.count
                    self.logger.info(f"Found {count} EditText element(s)")
                    
                    for i in range(count):
                        try:
                            et = edit_texts[i]
                            info = et.info
                            hint = info.get('text', '') or info.get('contentDescription', '') or ''
                            hint_lower = hint.lower()
                            
                            self.logger.debug(f"EditText[{i}]: hint='{hint}'")
                            
                            # Check nếu hint match hoặc EditText trống (likely phone input)
                            is_phone_field = any(kw in hint_lower for kw in hints_to_try) or hint == ''
                            
                            if is_phone_field and et.info.get('enabled', True):
                                self.logger.info(f"✓ Found phone input EditText[{i}] with hint: '{hint}'")
                                et.click()
                                time.sleep(0.3)
                                et.set_text(phone_number)
                                phone_input_found = True
                                break
                        except Exception as e:
                            self.logger.debug(f"Error checking EditText[{i}]: {e}")
            except Exception as e:
                self.logger.warning(f"Method 2 failed: {e}")
        
        # === METHOD 3: Tìm EditText đầu tiên visible trên màn hình ===
        if not phone_input_found:
            self.logger.info("Trying Method 3: First visible EditText...")
            try:
                edit_texts = device_u2(className="android.widget.EditText")
                if edit_texts.exists:
                    for i in range(edit_texts.count):
                        try:
                            et = edit_texts[i]
                            bounds = et.info.get('bounds', {})
                            
                            # Check if visible on screen
                            top = bounds.get('top', 0)
                            bottom = bounds.get('bottom', 0)
                            
                            if top > 0 and bottom < self.screen_height and et.info.get('enabled', True):
                                self.logger.info(f"✓ Found visible EditText[{i}] at bounds: {bounds}")
                                et.click()
                                time.sleep(0.3)
                                et.set_text(phone_number)
                                phone_input_found = True
                                break
                        except Exception as e:
                            self.logger.debug(f"Error with EditText[{i}]: {e}")
            except Exception as e:
                self.logger.warning(f"Method 3 failed: {e}")
        
        # === METHOD 4: XPath fallback ===
        if not phone_input_found:
            self.logger.info("Trying Method 4: XPath patterns...")
            xpaths_to_try = [
                '//android.widget.EditText[@resource-id="com.shopee.vn:id/cret_edit_text"]',
                '//android.widget.EditText[contains(@resource-id,"phone")]',
                '//android.widget.EditText[contains(@resource-id,"edit")]',
                '//android.widget.EditText[1]',  # First EditText
                '//android.widget.LinearLayout//android.widget.EditText',
            ]
            
            for xpath in xpaths_to_try:
                try:
                    element = device_u2.xpath(xpath)
                    if element.exists:
                        self.logger.info(f"✓ Found phone input by XPath: {xpath}")
                        element.click()
                        time.sleep(0.3)
                        # XPath element dùng set_text khác
                        device_u2.send_keys(phone_number)
                        phone_input_found = True
                        break
                except Exception as e:
                    self.logger.debug(f"XPath {xpath} not found: {e}")
        
        # === METHOD 5: Coordinate fallback - tap vào vùng thường có phone input ===
        if not phone_input_found:
            self.logger.info("Trying Method 5: Coordinate tap fallback...")
            # Shopee phone input thường ở khoảng 30-40% từ top
            tap_x = int(self.screen_width * 0.5)
            tap_y = int(self.screen_height * 0.35)
            
            self.logger.info(f"Tapping at coordinates ({tap_x}, {tap_y})...")
            device_u2.click(tap_x, tap_y)
            time.sleep(0.5)
            
            # Thử input text trực tiếp
            device_u2.send_keys(phone_number)
            phone_input_found = True  # Assume success, will check later
        
        if phone_input_found:
            self.logger.info(f"✓ Phone number {phone_number} entered successfully")
            time.sleep(1)
        else:
            # Debug: dump UI hierarchy để xem có gì
            self.logger.error(f"❌ Cannot find phone input field!")
            self.logger.info("Dumping UI hierarchy for debug...")
            
            try:
                xml_content = device_u2.dump_hierarchy()
                
                # Log các EditText tìm thấy
                if "EditText" in xml_content:
                    self.logger.warning("EditText exists in UI hierarchy")
                    import re
                    edit_texts = re.findall(r'resource-id="([^"]*)"[^>]*class="android\.widget\.EditText"', xml_content)
                    if edit_texts:
                        self.logger.info(f"EditText resource-ids found: {edit_texts}")
                else:
                    self.logger.warning("No EditText found in UI!")
                
                # Check current activity
                current_app = device_u2.app_current()
                self.logger.info(f"Current app: {current_app}")
                
            except Exception as e:
                self.logger.error(f"Debug dump failed: {e}")
            
            return False

        # Step 3: Nhấn nút Tiếp theo - ENHANCED với uiautomator2
        self.logger.info("Step 3: Clicking Continue button...")
        
        continue_clicked = False
        
        # === METHOD 1: resource-id ===
        self.logger.info("Trying Continue Method 1: resource-id...")
        continue_ids = [
            "com.shopee.vn:id/btn_continue",
            "com.shopee.vn:id/btn_next",
            "com.shopee.vn:id/continue_btn",
            "com.shopee.vn:id/next_btn",
            "com.shopee.vn:id/btnContinue",
            "com.shopee.vn:id/btnNext",
        ]
        
        for res_id in continue_ids:
            try:
                btn = device_u2(resourceId=res_id)
                if btn.exists:
                    self.logger.info(f"✓ Found Continue by resource-id: {res_id}")
                    btn.click()
                    continue_clicked = True
                    break
            except Exception as e:
                self.logger.debug(f"Continue resource-id {res_id} not found")
        
        # === METHOD 2: Tìm Button/TextView có text "Tiếp tục", "Continue", "Tiếp theo" ===
        if not continue_clicked:
            self.logger.info("Trying Continue Method 2: text matching...")
            continue_texts = ["Tiếp tục", "Tiếp theo", "Continue", "Next", "TIẾP TỤC", "TIẾP THEO"]
            
            for txt in continue_texts:
                try:
                    btn = device_u2(text=txt)
                    if btn.exists:
                        self.logger.info(f"✓ Found Continue by text: '{txt}'")
                        btn.click()
                        continue_clicked = True
                        break
                    
                    # Thử textContains
                    btn = device_u2(textContains=txt)
                    if btn.exists:
                        self.logger.info(f"✓ Found Continue by textContains: '{txt}'")
                        btn.click()
                        continue_clicked = True
                        break
                except Exception as e:
                    self.logger.debug(f"Continue text '{txt}' not found")
        
        # === METHOD 3: Tìm Button class có enabled=true ở phần dưới màn hình ===
        if not continue_clicked:
            self.logger.info("Trying Continue Method 3: Button in lower screen area...")
            try:
                buttons = device_u2(className="android.widget.Button")
                if buttons.exists:
                    for i in range(buttons.count):
                        try:
                            btn = buttons[i]
                            info = btn.info
                            bounds = info.get('bounds', {})
                            top = bounds.get('top', 0)
                            
                            # Button ở nửa dưới màn hình và enabled
                            if top > self.screen_height * 0.5 and info.get('enabled', True):
                                text = info.get('text', '')
                                self.logger.info(f"✓ Found Button[{i}] at lower screen: '{text}'")
                                btn.click()
                                continue_clicked = True
                                break
                        except:
                            pass
            except Exception as e:
                self.logger.warning(f"Method 3 failed: {e}")
        
        # === METHOD 4: Coordinate fallback ===
        if not continue_clicked:
            self.logger.info("Trying Continue Method 4: Coordinate tap...")
            # Nút Continue thường ở khoảng 85-90% từ top
            tap_x = int(self.screen_width * 0.5)
            tap_y = int(self.screen_height * 0.85)
            
            self.logger.info(f"Tapping Continue at ({tap_x}, {tap_y})...")
            device_u2.click(tap_x, tap_y)
            continue_clicked = True

        if continue_clicked:
            self.logger.info("✓ Tapped Continue button.")
            time.sleep(2)  # Chờ 2s trước khi bắt đầu detect
        else:
            self.logger.error("❌ Could not find Continue button.")
            return False

        # Step 4: Tap vào vị trí captcha cố định (skip detect)
        self.logger.info("Step 4: Waiting 7s for captcha to appear...")
        time.sleep(7)
        
        # Tap vào vị trí captcha slider cố định (0.691, 0.357)
        captcha_tap_x = int(self.screen_width * 0.691)
        captcha_tap_y = int(self.screen_height * 0.357)
        self.logger.info(f"Tapping captcha area at ({captcha_tap_x}, {captcha_tap_y})...")
        device_u2.click(captcha_tap_x, captcha_tap_y)
        time.sleep(2)
        
        self.logger.info("🚀 Starting captcha solver...")
        success = self._solve_captcha_flow(session_id, phone_number)
        if not success:
            self.logger.error("✗ Captcha solving failed")
            return False
        
        # Flow hoàn tất thành công!
        self.logger.info("")
        self.logger.info("="*70)
        self.logger.info("✓ REGISTRATION FLOW COMPLETED SUCCESSFULLY!")
        self.logger.info("="*70)
        self.logger.info(f"📱 Phone: {phone_number}")
        self.logger.info(f"🔑 Password: {getattr(self, '_last_registered_password', 'N/A')}")
        self.logger.info("="*70)
        
        return True
    
    def _solve_captcha_flow(self, session_id: str, phone_number: str) -> bool:
        """
        Detect and solve captcha, handle verification popup, get OTP and input it.
        
        Args:
            session_id: SMS session ID for OTP retrieval
            phone_number: Phone number for logging
            
        Returns:
            True if captcha solved and OTP inputted successfully
        """
        if not U2_AVAILABLE:
            self.logger.error("uiautomator2 required for captcha solving!")
            self.logger.error("Install: pip install uiautomator2")
            return False
        
        try:
            # Connect uiautomator2
            self.logger.info("Connecting uiautomator2...")
            device_u2 = u2.connect(self.serial)
            self.logger.info(f"✓ U2 connected to {self.serial}")
            
            # Captcha regions (from captcha_solver_v2.py)
            CROP_REGION = {"left": 0.161, "top": 0.390, "right": 0.843, "bottom": 0.569}
            SLIDER_REGION = {"left": 0.164, "top": 0.578, "right": 0.843, "bottom": 0.633}
            SLIDER_HANDLE_OFFSET = 0.06
            
            # Calculate coordinates
            y = int((SLIDER_REGION["top"] + SLIDER_REGION["bottom"]) / 2 * self.screen_height)
            start_x = int((SLIDER_REGION["left"] + SLIDER_HANDLE_OFFSET) * self.screen_width)
            
            # Retry loop (max 10 attempts for robustness)
            max_retries = 10
            captcha_solved = False
            
            for retry in range(max_retries):
                self.logger.info(f"\n{'='*60}")
                self.logger.info(f"🔄 CAPTCHA ATTEMPT {retry + 1}/{max_retries}")
                self.logger.info(f"{'='*60}")
                
                # Capture screenshot
                screen_path = "/sdcard/screen_captcha.png"
                self.adb.shell(self.serial, ["screencap", "-p", screen_path])
                local_path = "temp_captcha.png"
                self.adb._execute(["-s", self.serial, "pull", screen_path, local_path])
                
                # Crop background region
                img = cv2.imread(local_path)
                if img is None:
                    self.logger.error("Failed to read screenshot")
                    time.sleep(1.5)
                    continue
                
                h, w = img.shape[:2]
                x1 = int(CROP_REGION["left"] * w)
                y1 = int(CROP_REGION["top"] * h)
                x2 = int(CROP_REGION["right"] * w)
                y2 = int(CROP_REGION["bottom"] * h)
                background = img[y1:y2, x1:x2]
                
                # Encode to base64
                _, buffer = cv2.imencode('.jpg', background, [cv2.IMWRITE_JPEG_QUALITY, 85])
                bg_b64 = base64.b64encode(buffer).decode('utf-8')
                
                # Human thinking delay
                time.sleep(random.uniform(0.8, 2.0))
                
                # Create API task
                task_id = self._create_captcha_task(bg_b64)
                if not task_id:
                    self.logger.error("Failed to create task")
                    time.sleep(2.0)
                    continue
                
                # Perform continuous gesture with API polling
                success_gesture = self._perform_continuous_gesture(
                    device_u2, start_x, y, task_id
                )
                
                if not success_gesture:
                    self.logger.error("Gesture failed")
                    time.sleep(2.0)
                    continue
                
                # Wait for server validation (longer wait)
                self.logger.info("Waiting 4-6s for server validation...")
                time.sleep(random.uniform(4.0, 6.0))
                
                # Check if captcha is gone
                if not self._is_captcha_still_present(device_u2):
                    self.logger.info("\n" + "="*60)
                    self.logger.info(f"✓ CAPTCHA SOLVED SUCCESSFULLY after {retry + 1} attempt(s)!")
                    self.logger.info("="*60)
                    captcha_solved = True
                    break
                
                self.logger.warning(f"Captcha still present after attempt {retry + 1}, retrying...")
                time.sleep(random.uniform(3.0, 5.0))  # Longer delay between retries
            
            if not captcha_solved:
                self.logger.error("\n" + "="*60)
                self.logger.error("✗ MAX RETRIES REACHED - CAPTCHA FAILED")
                self.logger.error("="*60)
                return False
            
            # === XỬ LÝ POPUP XÁC THỰC SAU CAPTCHA (Zalo HOẶC Shopee gọi điện – chỉ 1 trong 2) ===
            self.logger.info("\nWaiting for verification method popup (Zalo or Shopee call)...")
            time.sleep(3.0)
            
            handled = False
            max_attempts = 5
            
            for attempt in range(max_attempts):
                self.logger.info(f"\n[Popup Check {attempt + 1}/{max_attempts}]")
                
                # Thử detect và xử lý Zalo popup
                zalo_result = self._detect_and_handle_zalo_popup(device_u2)
                if zalo_result == "handled":
                    self.logger.info("✓ Zalo verification popup handled successfully")
                    handled = True
                    break
                elif zalo_result == "found_but_failed":
                    self.logger.warning("⚠ Found Zalo popup but failed to handle")
                    # Tiếp tục retry
                
                # Thử detect và xử lý Shopee call popup
                shopee_result = self._detect_and_handle_shopee_call_popup(device_u2)
                if shopee_result == "handled":
                    self.logger.info("✓ Shopee call verification popup handled successfully")
                    handled = True
                    break
                elif shopee_result == "found_but_failed":
                    self.logger.warning("⚠ Found Shopee call popup but failed to handle")
                    # Tiếp tục retry
                
                if attempt < max_attempts - 1:
                    self.logger.info(f"⏳ No popup detected yet, waiting 2s before retry...")
                    time.sleep(2.0)
            
            if not handled:
                self.logger.warning("⚠ No Zalo or Shopee call popup detected after waiting – proceeding to OTP polling anyway")
            
            # === BẮT ĐẦU POLLING OTP (120s timeout từ lúc xử lý popup) ===
            verification_start_time = time.time()
            self.logger.info("")
            self.logger.info("="*60)
            self.logger.info("📩 Starting OTP polling (max 120s)...")
            self.logger.info("="*60)
            
            otp = None
            poll_interval = 5  # Poll mỗi 5s
            
            while time.time() - verification_start_time < 120:
                elapsed = int(time.time() - verification_start_time)
                self.logger.info(f"[{elapsed}s/120s] Checking for OTP...")
                
                # Poll 1 lần, không retry nội bộ
                otp = self.sms.get_otp(session_id, max_retries=1, retry_interval=0)
                
                if otp:
                    self.logger.info(f"✓ Received OTP: {otp}")
                    break
                
                self.logger.info(f"No OTP yet, waiting {poll_interval}s...")
                time.sleep(poll_interval)
            
            # Nếu hết 120s mà chưa có OTP → tap resend
            if not otp:
                self.logger.warning("")
                self.logger.warning("⚠ No OTP after 120s → Tapping resend OTP...")
                resend_x = int(self.screen_width * 0.608)
                resend_y = int(self.screen_height * 0.372)
                device_u2.click(resend_x, resend_y)
                self.logger.info(f"Tapped resend at ({resend_x}, {resend_y})")
                time.sleep(2)
                
                # Poll thêm 60s sau resend
                self.logger.info("Polling additional 60s after resend...")
                additional_start = time.time()
                while time.time() - additional_start < 60:
                    elapsed = int(time.time() - additional_start)
                    self.logger.info(f"[Resend {elapsed}s/60s] Checking for OTP...")
                    
                    otp = self.sms.get_otp(session_id, max_retries=1, retry_interval=0)
                    if otp:
                        self.logger.info(f"✓ Received OTP after resend: {otp}")
                        break
                    
                    time.sleep(poll_interval)
            
            # === INPUT OTP ===
            if otp:
                self.logger.info("")
                self.logger.info("="*60)
                self.logger.info(f"⌨️ Inputting OTP: {otp}")
                self.logger.info("="*60)
                
                # Focus bằng tap coordinates trước
                focus_x = int(self.screen_width * 0.492)
                focus_y = int(self.screen_height * 0.286)
                self.logger.info(f"Tapping OTP field at ({focus_x}, {focus_y}) to focus...")
                device_u2.click(focus_x, focus_y)
                time.sleep(0.5)
                
                # Thử input bằng resource-id chính xác
                otp_field = device_u2(resourceId="com.shopee.vn:id/otpVerificationCode")
                if otp_field.exists:
                    otp_field.set_text(otp)
                    self.logger.info("✓ OTP inputted via resource-id")
                else:
                    # Fallback: send_keys trực tiếp
                    self.logger.info("Resource-id not found, using send_keys fallback...")
                    device_u2.send_keys(otp)
                    self.logger.info("✓ OTP inputted via send_keys fallback")
                
                time.sleep(2.0)
                self.logger.info("✓ OTP input completed – Waiting for password setup screen...")
                
                # === BƯỚC CUỐI: THIẾT LẬP MẬT KHẨU SAU KHI NHẬN OTP ===
                self.logger.info("\nWaiting for 'Thiết Lập Mật Khẩu' screen...")
                
                # Chờ tối đa 30s cho màn hình set password hiện
                password_screen_found = False
                max_wait_password = 30
                check_interval_pw = 2
                
                for _ in range(max_wait_password // check_interval_pw):
                    try:
                        # Thử nhiều cách detect
                        title = device_u2(text="Thiết Lập Mật Khẩu")
                        if not title.exists:
                            title = device_u2(textContains="Thiết Lập Mật Khẩu")
                        if not title.exists:
                            title = device_u2(textContains="Thiếp Lập Mật Khẩu")  # fallback typo
                        if not title.exists:
                            title = device_u2(textContains="Mật Khẩu")
                        
                        if title.exists:
                            self.logger.info("✓ 'Thiết Lập Mật Khẩu' screen detected")
                            password_screen_found = True
                            break
                    except:
                        pass
                    
                    time.sleep(check_interval_pw)
                
                if not password_screen_found:
                    self.logger.error("✗ Password setup screen not appeared after 30s")
                    return False
                
                # Mật khẩu mặc định
                password = "ThanhThi88@"
                
                self.logger.info(f"Using default password: {password}")
                
                # Focus field bằng tap coordinates (an toàn)
                focus_pw_x = int(self.screen_width * 0.334)
                focus_pw_y = int(self.screen_height * 0.269)
                self.logger.info(f"Tapping password field at ({focus_pw_x}, {focus_pw_y}) to focus...")
                device_u2.click(focus_pw_x, focus_pw_y)
                time.sleep(0.8)
                
                # Input password bằng resource-id
                password_field = device_u2(resourceId="com.shopee.vn:id/cret_edit_text")
                if password_field.exists:
                    password_field.set_text(password)
                    self.logger.info("✓ Password inputted via resource-id")
                else:
                    # Fallback send_keys
                    device_u2.send_keys(password)
                    self.logger.info("✓ Password inputted via send_keys fallback")
                
                time.sleep(1.0)
                
                # Nhấn nút Continue
                self.logger.info("Clicking final Continue button...")
                continue_btn = device_u2(resourceId="com.shopee.vn:id/btnContinue")
                if continue_btn.exists:
                    continue_btn.click()
                    self.logger.info("✓ Final Continue tapped")
                else:
                    # Fallback text
                    continue_btn = device_u2(text="Tiếp tục")
                    if not continue_btn.exists:
                        continue_btn = device_u2(textContains="Tiếp tục")
                    if continue_btn.exists:
                        continue_btn.click()
                        self.logger.info("✓ Final Continue tapped via text")
                    else:
                        self.logger.error("Cannot find final Continue button")
                        return False
                
                time.sleep(5.0)  # Chờ đăng ký hoàn tất
                
                # === BƯỚC CUỐI + 1: Skip "Xác thực Đăng nhập Nhanh" bằng Back ===
                self.logger.info("\nSkipping 'Xác thực Đăng nhập Nhanh' screen...")
                time.sleep(4)  # Chờ 4s
                
                # Nhấn Back để skip
                self.logger.info("Pressing Back button to skip quick login...")
                device_u2.press("back")
                self.logger.info("✓ Back pressed")
                
                time.sleep(2.0)
                
                # === SAU KHI SKIP QUICK LOGIN: TAP + LƯỚT + SẢN PHẨM + PAUSE ===
                self.logger.info("\nTapping at (0.105, 0.91)...")
                tap_x = int(self.screen_width * 0.105)
                tap_y = int(self.screen_height * 0.91)
                device_u2.click(tap_x, tap_y)
                time.sleep(1.5)
                
                # Lướt 2-3 lần
                self.logger.info("Scrolling...")
                num_swipes = random.randint(2, 3)
                for _ in range(num_swipes):
                    x = random.randint(int(self.screen_width * 0.3), int(self.screen_width * 0.7))
                    y1 = random.randint(int(self.screen_height * 0.7), int(self.screen_height * 0.8))
                    y2 = random.randint(int(self.screen_height * 0.25), int(self.screen_height * 0.4))
                    device_u2.swipe(x, y1, x, y2, duration=0.3)
                    time.sleep(random.uniform(0.3, 0.5))
                
                # Nhấn sản phẩm (dùng _click_visible_product)
                self.logger.info("Clicking on a product...")
                self._click_visible_product()
                time.sleep(1.0)
                
                # Lướt 1 lần bên trong sản phẩm
                self.logger.info("Scrolling once inside product page...")
                x = random.randint(int(self.screen_width * 0.3), int(self.screen_width * 0.7))
                y1 = random.randint(int(self.screen_height * 0.7), int(self.screen_height * 0.8))
                y2 = random.randint(int(self.screen_height * 0.25), int(self.screen_height * 0.4))
                device_u2.swipe(x, y1, x, y2, duration=0.3)
                time.sleep(random.uniform(0.8, 1.2))
                
                # === HOÀN TẤT ĐĂNG KÝ ===
                self.logger.info("")
                self.logger.info("="*80)
                self.logger.info("✓✓✓ ĐĂNG KÝ TÀI KHOẢN SHOPEE THÀNH CÔNG HOÀN TOÀN!")
                self.logger.info(f"   📱 Phone: {phone_number}")
                self.logger.info(f"   🔑 Password: {password}")
                self.logger.info("="*80)
                
                # Lưu thông tin account vào biến instance để dùng sau
                self._last_registered_password = password
                
                # === PAUSE TẠI ĐÂY ===
                self.logger.info("")
                self.logger.info("="*80)
                self.logger.info("⏸  TOOL PAUSED - Đăng ký xong, dừng tại đây")
                self.logger.info("="*80)
                
                while True:
                    time.sleep(3600)
            else:
                self.logger.error("")
                self.logger.error("="*60)
                self.logger.error("✗ Failed to receive OTP even after resend")
                self.logger.error("="*60)
                return False
            
        except Exception as e:
            self.logger.error(f"Captcha solving flow failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _create_captcha_task(self, bg_base64: str) -> Optional[str]:
        """
        Create captcha task via Achicaptcha API.
        
        Args:
            bg_base64: Base64 encoded background image
            
        Returns:
            Task ID if successful, None otherwise
        """
        try:
            url = "https://api.achicaptcha.com/createTask"
            payload = {
                "clientKey": self.config.CAPTCHA_API_KEY,
                "task": {
                    "type": "ShopeeCaptchaTask",
                    "image": bg_base64,
                    "subType": "slider"
                }
            }
            
            response = requests.post(url, json=payload, timeout=30)
            result = response.json()
            
            if result.get("errorId") != 0:
                self.logger.error(f"API error: {result.get('errorDescription', 'Unknown')}")
                return None
            
            task_id = result.get("taskId")
            self.logger.info(f"Task created: {task_id}")
            return task_id
            
        except Exception as e:
            self.logger.error(f"Failed to create task: {e}")
            return None
    
    def _get_task_result_once(self, task_id: str) -> Optional[str]:
        """
        Poll captcha task result once.
        
        Args:
            task_id: Task ID from create task
            
        Returns:
            Distance string if ready, None if still processing or error
        """
        try:
            url = "https://api.achicaptcha.com/getTaskResult"
            payload = {
                "clientKey": self.config.CAPTCHA_API_KEY,
                "taskId": task_id
            }
            
            response = requests.post(url, json=payload, timeout=10)
            result = response.json()
            
            if result.get("errorId") == 0 and result.get("status") == "ready":
                solution = result.get("solution")
                return solution
            
            return None
            
        except Exception as e:
            self.logger.error(f"Poll error: {e}")
            return None
    
    def _perform_continuous_gesture(self, device_u2, start_x: int, y: int, task_id: str) -> bool:
        """
        Perform continuous gesture while polling API (from captcha_solver_v2.py).
        
        Args:
            device_u2: Uiautomator2 device instance
            start_x: Starting X coordinate
            y: Y coordinate (fixed)
            task_id: API task ID
            
        Returns:
            True if successful
        """
        try:
            # Touch down
            device_u2.touch.down(start_x, y)
            current_x, current_y = start_x, y
            
            # Initial hold
            time.sleep(random.uniform(0.8, 2.0))
            
            # Poll loop (max 50 attempts ~100s)
            wiggle_count = 0
            for attempt in range(50):
                # Poll API first
                distance = self._get_task_result_once(task_id)
                
                if distance:
                    # Got result - move to target
                    try:
                        distance_px = int(distance)
                    except:
                        self.logger.error(f"Invalid distance: {distance}")
                        device_u2.touch.up(int(current_x), int(current_y))
                        return False
                    
                    # Calculate target with scale factor
                    CROP_REGION = {"left": 0.161, "right": 0.843}
                    SLIDER_REGION = {"left": 0.164, "right": 0.843}
                    
                    bg_width_ratio = CROP_REGION["right"] - CROP_REGION["left"]
                    slider_width_ratio = SLIDER_REGION["right"] - SLIDER_REGION["left"]
                    scale_factor = slider_width_ratio / bg_width_ratio
                    
                    scaled_distance = distance_px * scale_factor
                    end_x = start_x + scaled_distance + random.uniform(-5, 5)
                    end_x = max(int(SLIDER_REGION["left"] * self.screen_width), 
                               min(int(SLIDER_REGION["right"] * self.screen_width), end_x))
                    
                    # Smooth movement with decreasing jitter
                    steps = random.randint(25, 35)
                    for i in range(steps):
                        progress = (i + 1) / steps
                        new_x = current_x + (end_x - current_x) * progress
                        
                        # Decreasing jitter
                        jitter_y = random.uniform(-3, 3) * (1 - progress * 0.7)
                        new_y = current_y + jitter_y
                        
                        device_u2.touch.move(int(new_x), int(new_y))
                        current_x, current_y = new_x, new_y
                        time.sleep(random.uniform(0.008, 0.015))
                    
                    # Overshoot 70% of time
                    if random.random() < 0.7:
                        overshoot = random.uniform(15, 35)
                        device_u2.touch.move(int(current_x + overshoot), int(current_y))
                        time.sleep(random.uniform(0.05, 0.12))
                        
                        # Correct back
                        correction_steps = random.randint(3, 6)
                        for i in range(correction_steps):
                            new_x = current_x + overshoot - (overshoot * (i + 1) / correction_steps)
                            device_u2.touch.move(int(new_x), int(current_y))
                            time.sleep(random.uniform(0.01, 0.03))
                        current_x = end_x
                    
                    # Release
                    device_u2.touch.up(int(current_x), int(current_y))
                    self.logger.info(f"✓ Gesture completed: {start_x} → {int(current_x)}")
                    return True
                
                # No result yet - wiggle or hold
                if wiggle_count % 2 == 0:
                    # Hold
                    time.sleep(random.uniform(0.6, 1.5))
                else:
                    # Wiggle
                    wiggle_dx = random.uniform(15, 40) * random.choice([-1, 1])
                    wiggle_dy = random.uniform(-4, 4)
                    new_x = current_x + wiggle_dx
                    new_y = current_y + wiggle_dy
                    device_u2.touch.move(int(new_x), int(new_y))
                    current_x, current_y = new_x, new_y
                    time.sleep(random.uniform(0.3, 0.8))
                
                wiggle_count += 1
            
            # Timeout
            self.logger.error("Gesture timeout")
            device_u2.touch.up(int(current_x), int(current_y))
            return False
            
        except Exception as e:
            self.logger.error(f"Gesture error: {e}")
            return False
    
    def _is_captcha_still_present(self, device_u2) -> bool:
        """
        Check if captcha still present bằng detect fullscreen WebView + dark background.
        
        Args:
            device_u2: Uiautomator2 device instance
            
        Returns:
            True if captcha STILL present (need retry), False if gone
        """
        try:
            # Cách 1: Fullscreen WebView detection
            webviews = device_u2(className="android.webkit.WebView")
            if webviews.exists:
                try:
                    count = webviews.count
                    for i in range(count):
                        try:
                            wv = webviews[i]
                            info = wv.info
                            bounds = info.get('bounds', {})
                            if bounds:
                                w = bounds.get('right', 0) - bounds.get('left', 0)
                                h = bounds.get('bottom', 0) - bounds.get('top', 0)
                                
                                w_ratio = w / self.screen_width if self.screen_width > 0 else 0
                                h_ratio = h / self.screen_height if self.screen_height > 0 else 0
                                
                                # Nếu còn WebView lớn (>60% width, >30% height) → captcha còn
                                if w_ratio > 0.60 and h_ratio > 0.30:
                                    self.logger.warning(f"✗ Captcha STILL PRESENT (WebView {i}: {w_ratio:.0%}x{h_ratio:.0%})")
                                    return True
                        except:
                            pass
                except:
                    pass
            
            # Cách 2: Dark background fallback
            try:
                temp_screen = "/sdcard/captcha_check.png"
                local_temp = "captcha_check.png"
                
                self.adb.shell(self.serial, ["screencap", "-p", temp_screen])
                self.adb._execute(["-s", self.serial, "pull", temp_screen, local_temp])
                
                if os.path.exists(local_temp):
                    img = cv2.imread(local_temp)
                    if img is not None:
                        h, w = img.shape[:2]
                        center = img[int(h*0.35):int(h*0.65), int(w*0.1):int(w*0.9)]
                        avg_bgr = cv2.mean(center)[:3]
                        
                        # Nếu nền tối (captcha overlay) → còn captcha
                        if avg_bgr[0] < 90 and avg_bgr[1] < 90 and avg_bgr[2] < 90:
                            self.logger.warning(f"✗ Captcha STILL PRESENT (dark background BGR≈{tuple(map(int, avg_bgr))})")
                            try:
                                os.remove(local_temp)
                            except:
                                pass
                            try:
                                self.adb.shell(self.serial, ["rm", temp_screen])
                            except:
                                pass
                            return True
                    
                    try:
                        os.remove(local_temp)
                    except:
                        pass
                
                try:
                    self.adb.shell(self.serial, ["rm", temp_screen])
                except:
                    pass
            except Exception as e:
                self.logger.debug(f"Dark background check error: {e}")
                pass  # Nếu check color fail → không ảnh hưởng
            
            self.logger.info("✓ Captcha GONE - Solved successfully!")
            return False
            
        except Exception as e:
            self.logger.warning(f"Captcha check error: {e} → Assume STILL PRESENT to be safe")
            return True  # Error → assume còn để retry, tránh miss
    
    def _handle_zalo_verification_flow(self, device_u2) -> bool:
        """
        DEPRECATED - use _detect_and_handle_zalo_popup instead.
        Kept for backward compatibility.
        """
        result = self._detect_and_handle_zalo_popup(device_u2)
        return result == "handled"
    
    def _detect_and_handle_zalo_popup(self, device_u2) -> str:
        """
        Detect and handle Zalo verification popup after captcha success.
        
        Args:
            device_u2: Uiautomator2 device instance
            
        Returns:
            "handled": Found popup and handled successfully
            "not_found": No popup detected
            "found_but_failed": Found popup but failed to handle
        """
        try:
            self.logger.info("Checking for Zalo verification popup...")
            
            # Check for Zalo popup by title
            popup_title = device_u2(
                resourceId="com.shopee.vn:id/txt_title",
                textContains="Mã xác thực đã được gửi"
            )
            
            if not popup_title.exists:
                popup_title = device_u2(textContains="Mã xác thực đã được gửi")
            
            if not popup_title.exists:
                popup_title = device_u2(textContains="gửi qua Zalo")
            
            if not popup_title.exists:
                self.logger.info("  → No Zalo popup detected")
                return "not_found"
            
            self.logger.info("⚠ Zalo popup detected! Handling...")
            
            # Click "Phương thức khác"
            btn_other = device_u2(resourceId="com.shopee.vn:id/buttonDefaultNegative")
            if not btn_other.exists:
                btn_other = device_u2(text="Phương thức khác")
            if not btn_other.exists:
                btn_other = device_u2(textContains="Phương thức khác")
            
            if btn_other.exists:
                btn_other.click()
                self.logger.info("  ✓ Clicked 'Phương thức khác'")
                time.sleep(1.8)
            else:
                self.logger.error("  ✗ Cannot find 'Phương thức khác' button")
                return "found_but_failed"
            
            # Select "Tin nhắn" (SMS)
            sms_button = device_u2(text="Tin nhắn")
            if not sms_button.exists:
                sms_button = device_u2(xpath='//android.widget.TextView[@text="Tin nhắn"]')
            if not sms_button.exists:
                sms_button = device_u2(textContains="Tin nhắn")
            
            if sms_button.exists:
                sms_button.click()
                time.sleep(2.0)
                self.logger.info("  ✓ Selected SMS verification")
                return "handled"
            else:
                self.logger.error("  ✗ Cannot find 'Tin nhắn' button")
                return "found_but_failed"
            
        except Exception as e:
            self.logger.error(f"Zalo handler error: {e}")
            return "found_but_failed"

    def _handle_shopee_call_verification_popup(self, device_u2) -> bool:
        """
        DEPRECATED - use _detect_and_handle_shopee_call_popup instead.
        Kept for backward compatibility.
        """
        result = self._detect_and_handle_shopee_call_popup(device_u2)
        return result == "handled"
    
    def _detect_and_handle_shopee_call_popup(self, device_u2) -> str:
        """
        Detect and handle popup: "Phát hiện hoạt động bất thường. Shopee sẽ gọi đến số điện thoại của bạn..."
        → Nhấn "Đồng ý"
        
        Args:
            device_u2: Uiautomator2 device instance
            
        Returns:
            "handled": Found popup and handled successfully
            "not_found": No popup detected
            "found_but_failed": Found popup but failed to handle
        """
        try:
            self.logger.info("Checking for 'Shopee will call' verification popup...")
            
            # Detect bằng text title đặc trưng
            title = device_u2(
                resourceId="com.shopee.vn:id/txt_title",
                textContains="Phát hiện hoạt động bất thường"
            )
            
            if not title.exists:
                title = device_u2(
                    resourceId="com.shopee.vn:id/txt_title",
                    textContains="Shopee sẽ gọi đến số điện thoại"
                )
            
            if not title.exists:
                # Thử tìm bằng text không có resource-id
                title = device_u2(textContains="Phát hiện hoạt động bất thường")
            
            if not title.exists:
                title = device_u2(textContains="Shopee sẽ gọi đến")
            
            if not title.exists:
                title = device_u2(textContains="gọi đến số điện thoại")
            
            if not title.exists:
                self.logger.info("  → No 'Shopee call' popup detected")
                return "not_found"
            
            self.logger.info("⚠ Detected 'Shopee will call' popup! Handling...")
            
            # Nhấn nút Đồng ý
            btn_agree = device_u2(resourceId="com.shopee.vn:id/buttonDefaultPositive")
            if not btn_agree.exists:
                btn_agree = device_u2(text="Đồng ý")
            if not btn_agree.exists:
                btn_agree = device_u2(textContains="Đồng ý")
            if not btn_agree.exists:
                btn_agree = device_u2(text="OK")
            if not btn_agree.exists:
                btn_agree = device_u2(textContains="OK")
            if not btn_agree.exists:
                # Fallback: tìm button ở nửa dưới màn hình
                buttons = device_u2(className="android.widget.Button")
                if buttons.exists:
                    for i in range(buttons.count):
                        try:
                            btn = buttons[i]
                            info = btn.info
                            bounds = info.get('bounds', {})
                            top = bounds.get('top', 0)
                            if top > self.screen_height * 0.5:
                                btn_agree = btn
                                break
                        except:
                            pass
            
            if btn_agree and (hasattr(btn_agree, 'exists') and btn_agree.exists or not hasattr(btn_agree, 'exists')):
                btn_agree.click()
                self.logger.info("  ✓ Đã nhấn 'Đồng ý' – Chờ Shopee gọi điện đọc mã")
                time.sleep(2.0)
                return "handled"
            else:
                self.logger.error("  ✗ Không tìm thấy nút 'Đồng ý'")
                return "found_but_failed"
                
        except Exception as e:
            self.logger.error(f"Error handling Shopee call popup: {e}")
            return "found_but_failed"


class _StandaloneAutomation:
    def __init__(self, adb, sms, config, popup_handler, captcha_solver, logger,
                 serial: str, screen_width: int, screen_height: int):
        self.adb = adb
        self.sms = sms
        self.config = config
        self.popup_handler = popup_handler
        self.captcha_solver = captcha_solver
        self.logger = logger
        self.serial = serial
        self.screen_width = screen_width
        self.screen_height = screen_height

    def _click_visible_product(self):
        positions = [
            (0.073, 0.554),
            (0.926, 0.57),
            (0.038, 0.455),
        ]
        pos_x, pos_y = random.choice(positions)
        tap_x = int(self.screen_width * pos_x)
        tap_y = int(self.screen_height * pos_y)
        self.logger.info(f"Tapping product at ({tap_x}, {tap_y})...")
        self.adb.tap(self.serial, tap_x, tap_y)


def _select_serial(adb, config):
    device_key = input("Enter PChanger Device Key (leave blank to use connected device): ").strip()
    if device_key:
        from test import DeviceStateManager
        device_manager = DeviceStateManager(config.PCHANGER_BASE_URL, device_key)
        serial = device_manager.get_device_serial()
        if not serial:
            print("Error: could not get device serial from PChanger.")
        return serial

    devices = adb.get_connected_devices()
    if not devices:
        print("Error: no ADB devices found.")
        return None
    if len(devices) == 1:
        return devices[0]

    print("Connected devices:")
    for idx, serial in enumerate(devices, 1):
        print(f"{idx}. {serial}")
    choice = input("Choose device by number or enter serial: ").strip()
    if choice.isdigit():
        num = int(choice)
        if 1 <= num <= len(devices):
            return devices[num - 1]
    return choice or None


def main():
    from test import ADBController, UIElementFinder, PopupHandler, SMSClient, ShopeeCaptchaSolver, Config, AutomationLogger

    config = Config()
    logger = AutomationLogger("RegistrationFlowRunner")
    adb = ADBController()
    serial = _select_serial(adb, config)
    if not serial:
        return

    if not adb.wait_for_device(serial, timeout=180):
        print("Error: device not ready.")
        return

    screen_width, screen_height = adb.get_screen_size(serial)
    sms_client = SMSClient(config.SMS_API_URL, config.SMS_API_KEY)
    element_finder = UIElementFinder(adb)
    popup_handler = PopupHandler(adb, element_finder, config)
    captcha_solver = ShopeeCaptchaSolver(config.CAPTCHA_API_KEY)

    ctx = _StandaloneAutomation(
        adb,
        sms_client,
        config,
        popup_handler,
        captcha_solver,
        logger,
        serial,
        screen_width,
        screen_height,
    )
    flow = RegistrationFlow(ctx)
    success = flow.run_from_notification()
    if success:
        print("Registration flow completed.")
    else:
        print("Registration flow failed.")


if __name__ == "__main__":
    main()
