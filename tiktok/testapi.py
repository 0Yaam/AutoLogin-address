import json
import requests


def extract_json_object(text: str):
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    snippet = text[start:end + 1]
    try:
        return json.loads(snippet)
    except Exception:
        return None


def main():
    email = input("Nhap email: ").strip()
    if not email:
        print("Email trống.")
        return

    url = "https://mailvip.net/index.php"
    params = {"action": "get_tempm", "email": email}
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=20)
    except Exception as e:
        print(f"Lỗi gọi API: {e}")
        return

    try:
        data = resp.json()
    except Exception:
        data = extract_json_object(resp.text)

    if data is None:
        print("Không parse được JSON. Response thô:")
        print(resp.text)
        return

    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
