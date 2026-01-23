"""
Shopee Auto Login Flow
======================
Automates the login flow with fixed coordinate taps and permission handling.

Notes:
- Hotmail API integration is a placeholder for now.
"""

import time
import msvcrt
import requests
import re
from typing import Optional, Tuple

from test import (
    ADBController,
    AutomationLogger,
    Config,
    DeviceStateManager,
    PopupHandler,
    UIElementFinder,
    normalize_text,
)


class AutoLoginFlow:
    def __init__(self, device_key: str, username: str, password: str, hotmail: str):
        self.device_key = device_key
        self.username = username
        self.password = password
        self.hotmail = hotmail

        self.config = Config()
        self.logger = AutomationLogger("AutoLogin")
        self.adb = ADBController()
        self.device_manager = DeviceStateManager(self.config.PCHANGER_BASE_URL, device_key)
        self.element_finder = UIElementFinder(self.adb)
        self.popup_handler = PopupHandler(self.adb, self.element_finder, self.config)

        self.serial: Optional[str] = None
        self.screen_width = 1080
        self.screen_height = 1920

    def _tap_ratio(self, x_ratio: float, y_ratio: float, wait: float = 0.0):
        x = int(self.screen_width * x_ratio)
        y = int(self.screen_height * y_ratio)
        self.logger.info(f"Tapping at ({x_ratio:.3f}, {y_ratio:.3f}) -> ({x}, {y})")
        self.adb.tap(self.serial, x, y)
        if wait > 0:
            time.sleep(wait)

    def _wait_for_text(self, text: str, timeout: Optional[float] = 60.0, interval: float = 1.0) -> bool:
        start_time = time.time()
        while True:
            elements = self.element_finder.find_by_text(
                self.serial, text, exact=False, normalize=True
            )
            if elements:
                return True
            if timeout is not None and time.time() - start_time >= timeout:
                return False
            time.sleep(interval)

    def _tap_by_text(self, text: str, timeout: Optional[float] = 60.0, interval: float = 1.0,
                     exact: bool = False) -> bool:
        start_time = time.time()
        while True:
            elements = self.element_finder.find_by_text(
                self.serial, text, exact=exact, normalize=True
            )
            visible = [
                el for el in elements
                if el.is_visible(self.screen_width, self.screen_height)
            ]
            if visible:
                cx, cy = visible[0].center
                self.logger.info(f"Tapping text '{text}' at ({cx}, {cy})")
                self.adb.tap(self.serial, cx, cy)
                return True
            if timeout is not None and time.time() - start_time >= timeout:
                return False
            time.sleep(interval)

    def _deny_permission_once(self, timeout: float = 15.0, interval: float = 0.5) -> bool:
        start_time = time.time()
        while time.time() - start_time < timeout:
            xml_content = self.adb.dump_ui_hierarchy(self.serial)
            if not xml_content.strip():
                time.sleep(interval)
                continue

            xml_norm = normalize_text(xml_content)
            deny_texts = ["KHONG CHO PHEP", "TU CHOI", "DENY", "DONT ALLOW", "DON'T ALLOW"]
            permission_present = (
                self.config.RESOURCE_ID_PERMISSION_MSG in xml_content
                or self.config.RESOURCE_ID_PERMISSION_DENY in xml_content
                or "CHO PHEP SHOPEE TRUY CAP" in xml_norm
            )

            if permission_present:
                deny_ids = [
                    "com.android.permissioncontroller:id/permission_deny_and_dont_ask_again_button",
                    self.config.RESOURCE_ID_PERMISSION_DENY,
                ]
                for deny_id in deny_ids:
                    elements = self.element_finder.find_elements(
                        self.serial, resource_id=deny_id
                    )
                    visible = [
                        el for el in elements
                        if el.is_visible(self.screen_width, self.screen_height)
                    ]
                    if visible:
                        cx, cy = visible[0].center
                        self.logger.info(f"Tapping deny button at ({cx}, {cy})")
                        self.adb.tap(self.serial, cx, cy)
                        return True

                for text in deny_texts:
                    elements = self.element_finder.find_by_text(
                        self.serial, text, exact=False, normalize=True
                    )
                    visible = [
                        el for el in elements
                        if el.is_visible(self.screen_width, self.screen_height)
                    ]
                    if visible:
                        cx, cy = visible[0].center
                        self.logger.info(f"Tapping deny text '{text}' at ({cx}, {cy})")
                        self.adb.tap(self.serial, cx, cy)
                        return True

                self.logger.info("Permission prompt detected, tapping deny fallback coordinate")
                self._tap_ratio(0.45, 0.757, wait=0.2)
                return True
            time.sleep(interval)
        return False

    def _wait_and_tap_resource_id(self, resource_id: str, fallback_ratio: Tuple[float, float] = None,
                                   timeout: float = 30.0, interval: float = 1.0) -> bool:
        """
        Wait for element by resource ID and tap it.
        
        Args:
            resource_id: Android resource ID to find
            fallback_ratio: Fallback tap coordinates if element not found
            timeout: Maximum wait time
            interval: Check interval
            
        Returns:
            True if element found and tapped, False otherwise
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
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

    def _placeholder_hotmail_fetch(self):
        self.logger.info("Hotmail API integration is not implemented yet.")
        self.logger.info("Captured hotmail value for future use.")

    def fetch_shopee_link_from_mail(self, mail_data: str, retry_interval: float = 5.0) -> Optional[str]:
        """
        Fetch Shopee verification link from mail using API.
        Mail format: email|password|token|uuid|smvmail
        Loops until a valid link is found.
        """
        if not mail_data:
            self.logger.error("No mail data provided")
            return None

        try:
            parts = mail_data.split('|')
            if len(parts) < 4:
                self.logger.error("Invalid mail format: need at least email|password|token|uuid")
                return None

            email = parts[0].strip()
            refresh_token = parts[2].strip()
            client_id = parts[3].strip()

            self.logger.info(f"Processing mail: {email}")
            self.logger.info(f"Client ID: {client_id}")

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
        while True:
            attempt += 1
            self.logger.info(f"Attempt {attempt}: Calling mail API...")

            try:
                response = requests.post(url, json=payload, timeout=15)

                if response.status_code != 200:
                    self.logger.warning(f"HTTP error: {response.status_code}. Retrying in {retry_interval}s...")
                    time.sleep(retry_interval)
                    continue

                data = response.json()

                if not data.get("status") or not data.get("messages"):
                    self.logger.warning(f"No messages found. Retrying in {retry_interval}s...")
                    time.sleep(retry_interval)
                    continue

                self.logger.info(f"Found {len(data['messages'])} messages. Searching for Shopee link...")

                for msg in data['messages']:
                    html_content = msg.get('message', '')
                    match = re.search(r'https://vn\.shp\.ee/dlink/[a-zA-Z0-9]+', html_content)

                    if match:
                        link_shopee = match.group(0)
                        self.logger.info(f"Found Shopee link: {link_shopee}")
                        return link_shopee

                self.logger.warning(f"No Shopee link found in messages. Retrying in {retry_interval}s...")
                time.sleep(retry_interval)

            except Exception as e:
                self.logger.warning(f"Error calling API: {e}. Retrying in {retry_interval}s...")
                time.sleep(retry_interval)

    def connect_device(self) -> bool:
        self.logger.info("Waiting for PChanger device to be ready (not busy)...")
        self.serial = self.device_manager.get_device_serial()
        if not self.serial:
            self.logger.error("Failed to get device serial from PChanger")
            return False

        if not self.adb.wait_for_device(self.serial, timeout=180):
            self.logger.error("Device not ready")
            return False

        self.screen_width, self.screen_height = self.adb.get_screen_size(self.serial)
        self.logger.info(f"Screen size: {self.screen_width}x{self.screen_height}")
        return True

    def run(self) -> bool:
        if not self.connect_device():
            return False

        self._placeholder_hotmail_fetch()

        self.logger.info("Launching Shopee app...")
        self.adb.unlock_screen(self.serial)
        time.sleep(0.2)
        self.adb.launch_app(self.serial, self.config.APP_PACKAGE)
        time.sleep(5.0)

        self._tap_ratio(0.705, 0.911, wait=1.75)
        self._tap_ratio(0.235, 0.280, wait=0.3)
        self.adb.input_text(self.serial, self.username)
        time.sleep(0.3)

        self._tap_ratio(0.237, 0.337, wait=0.3)
        self.adb.input_text(self.serial, self.password)
        time.sleep(0.3)

        self._tap_ratio(0.509, 0.410)

        self.logger.info("Waiting 5s before tapping email verification option...")
        time.sleep(8.0)
        self._tap_ratio(0.283, 0.228, wait=0.5)

        self.logger.info("Waiting 4s for permission prompt, then denying...")
        time.sleep(4.0)
        self._tap_ratio(0.48, 0.768, wait=2.0)

        self._tap_ratio(0.275, 0.535)

        # Wait 10s then fetch mail verification link
        self.logger.info("Waiting 10s before fetching mail verification link...")
        time.sleep(6.0)

        if self.hotmail:
            shopee_link = self.fetch_shopee_link_from_mail(self.hotmail)
            if shopee_link:
                self.logger.info(f"Successfully retrieved Shopee link: {shopee_link}")
                # Open link in browser on device using ADB
                self.logger.info("Opening Shopee link in browser on device...")
                self.adb.shell(self.serial, [
                    "am", "start", "-a", "android.intent.action.VIEW", 
                    "-d", shopee_link
                ])
                
                # Wait for Chrome First Run button and tap it
                self.logger.info("Waiting for Chrome First Run button...")
                chrome_fre_found = self._wait_and_tap_resource_id(
                    "com.android.chrome:id/fre_bottom_group",
                    fallback_ratio=(0.496, 0.885),
                    timeout=30.0
                )
                if chrome_fre_found:
                    self.logger.info("Tapped Chrome First Run button")
                else:
                    self.logger.info("Chrome First Run button not found, tapping fallback coordinate")
                    self._tap_ratio(0.496, 0.885)
                
                # Wait for Chrome location permission dialog
                self.logger.info("Waiting for Chrome location permission dialog...")
                location_dialog_found = self._wait_for_text(
                    "shopee.vn muốn sử dụng thông tin vị trí thiết bị của bạn",
                    timeout=60.0,
                    interval=1.0
                )
                if location_dialog_found:
                    self.logger.info("Chrome location dialog appeared, waiting 5s...")
                    time.sleep(2.5)
                else:
                    self.logger.warning("Chrome location dialog not found, continuing anyway...")
                
                # Return to Shopee app
                self.logger.info("Returning to Shopee app...")
                self.adb.launch_app(self.serial, self.config.APP_PACKAGE)
            else:
                self.logger.warning("Failed to retrieve Shopee link")
        else:
            self.logger.info("No hotmail data provided, skipping mail verification")
        # self.logger.info("waiting 2s and press back")
        # time.sleep(2.0)
        self.adb.press_keycode(self.serial, 4)
        self.logger.info("Auto login flow completed")
        return True


def main():
    print("=" * 70)
    print("  Shopee Auto Login Flow")
    print("=" * 70)
    print()

    device_key = "e8da52170928cf3"

    while True:
        username = input("Enter username: ").strip()
        if not username:
            print("Error: Username cannot be empty")
            continue

        password = input("Enter password: ").strip()
        if not password:
            print("Error: Password cannot be empty")
            continue

        print("Enter hotmail data (format: email|password|token|uuid|smvmail):")
        hotmail = input(">> ").strip()

        flow = AutoLoginFlow(device_key, username, password, hotmail)
        success = flow.run()

        print()
        if success:
            print("Auto login completed successfully")
        else:
            print("Auto login failed")

        print("Press ESC to exit, any other key to continue...")
        key = msvcrt.getch()
        if key == b"\x1b":
            break


if __name__ == "__main__":
    main()
