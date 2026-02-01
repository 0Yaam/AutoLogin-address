import requests
import re
import webbrowser

def process_shopee_account():
    # --- 1. NHẬP DỮ LIỆU ĐẦU VÀO ---
    print("Dán chuỗi dữ liệu vào bên dưới (dạng Email|Pass|Token|ClientID|...):")
    raw_input = input(">> ").strip()

    if not raw_input:
        print("❌ Chưa nhập dữ liệu!")
        return

    # --- 2. TÁCH CHUỖI DỮ LIỆU ---
    try:
        parts = raw_input.split('|')
        
        # Kiểm tra xem có đủ các thành phần cần thiết không
        # Định dạng mong đợi: Email [0] | Pass [1] | Token [2] | ClientID [3] | ...
        if len(parts) < 4:
            print("❌ Lỗi định dạng: Chuỗi thiếu thông tin (cần ít nhất Email, Pass, Token, ClientID).")
            return

        email = parts[0].strip()
        # parts[1] là mật khẩu, API này không dùng mật khẩu nên bỏ qua
        refresh_token = parts[2].strip()
        client_id = parts[3].strip()

        print(f"\n[*] Đang xử lý: {email}")
        print(f"[*] Client ID: {client_id}")

    except Exception as e:
        print(f"❌ Lỗi khi tách chuỗi: {e}")
        return

    # --- 3. GỌI API ---
    url = "https://tools.dongvanfb.net/api/get_messages_oauth2"
    
    payload = {
        "email": email,
        "refresh_token": refresh_token,
        "client_id": client_id
    }

    try:
        print("[*] Đang gọi API lấy tin nhắn...")
        response = requests.post(url, json=payload, timeout=15)
        
        if response.status_code != 200:
            print(f"❌ Lỗi HTTP: {response.status_code}")
            return

        data = response.json()

        # Kiểm tra kết quả trả về
        if not data.get("status") or not data.get("messages"):
            print("❌ API báo lỗi hoặc không có tin nhắn (Token có thể đã chết).")
            return

        # --- 4. TÌM LINK & MỞ TRÌNH DUYỆT ---
        print(f"[*] Tìm thấy {len(data['messages'])} tin nhắn. Đang lọc link...")
        
        found = False
        allowed_sender = "info@security.shopee.vn"
        allowed_sender_lower = allowed_sender.lower()

        def _extract_sender_blob(message: dict) -> str:
            candidates = []
            for key in (
                "from", "fromEmail", "from_email", "fromAddress", "from_address",
                "sender", "sender_email", "email_from", "mail_from", "fromName", "from_name"
            ):
                value = message.get(key)
                if isinstance(value, str):
                    candidates.append(value)
                elif isinstance(value, dict):
                    for subkey in ("email", "address", "value"):
                        subval = value.get(subkey)
                        if isinstance(subval, str):
                            candidates.append(subval)
            headers = message.get("headers")
            if isinstance(headers, str):
                candidates.append(headers)
            elif isinstance(headers, dict):
                header_from = headers.get("From") or headers.get("from")
                if isinstance(header_from, str):
                    candidates.append(header_from)

            for cand in candidates:
                match = re.search(r'[\w\.\-\+]+@[\w\.\-]+\.\w+', cand)
                if match:
                    return match.group(0)

            for cand in candidates:
                if cand:
                    return cand
            return ""

        for msg in data['messages']:
            sender_blob = _extract_sender_blob(msg).lower()
            if allowed_sender_lower not in sender_blob:
                continue
            html_content = msg.get('message', '')
            
            # Regex tìm link Shopee dlink (chính xác nhất)
            match = re.search(r'https://vn\.shp\.ee/dlink/[a-zA-Z0-9]+', html_content)
            
            if match:
                link_shopee = match.group(0)
                print("\n" + "="*60)
                print(f"✅ TÌM THẤY LINK: {link_shopee}")
                print("="*60)
                
                print("[*] Đang tự động mở trình duyệt...")
                webbrowser.open(link_shopee)
                found = True
                break # Tìm thấy link mới nhất thì dừng

        if not found:
            print("❌ Không tìm thấy link đăng nhập (dlink) nào trong hộp thư.")

    except Exception as e:
        print(f"⚠️ Lỗi hệ thống: {e}")

if __name__ == "__main__":
    process_shopee_account()
    # Dòng này để giữ cửa sổ không bị tắt ngay nếu chạy file .exe hoặc click đúp
    input("\nẤn Enter để thoát...")
