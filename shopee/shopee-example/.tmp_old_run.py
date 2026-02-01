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
    
    def 