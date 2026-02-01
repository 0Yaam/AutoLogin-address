
# GET Code Mail With OAuth2 Token

API này cho phép lấy mã xác minh (OTP/Verification Code) từ các dịch vụ như Facebook, Instagram, Twitter, v.v., bằng cách sử dụng Refresh Token OAuth2.

### Thông tin Endpoint

* **Method:** `POST`
* **URL:** `https://tools.dongvanfb.net/api/get_code_oauth2`
* **Content-Type:** `application/json`

---

### Request Body

Gửi một request `POST` với dữ liệu JSON bao gồm các trường sau:

```json
{
    "email": "<EMAIL>",
    "refresh_token": "<REFRESH_TOKEN>",
    "client_id": "<CLIENT_ID>",
    "type": "<TYPE>"
}

```

#### Tham số chi tiết:

* **email** (string): Địa chỉ email cần lấy mã (Hotmail/Outlook).
* **refresh_token** (string): Token làm mới của tài khoản.
* **client_id** (string): Client ID của ứng dụng OAuth.
* **type** (string): Loại dịch vụ cần lấy mã. Các giá trị hỗ trợ bao gồm:

| Dịch vụ phổ biến | Các dịch vụ khác |
| --- | --- |
| `all` (Lấy tất cả) | `tiktok` |
| `facebook` | `amazon` |
| `instagram` | `lazada` |
| `twitter` | `kakaotalk` |
| `google` | `shopee` |
| `apple` | `telegram` |
|  | `wechat` |

---

### Ví dụ (Example)

#### 1. Request

```json
POST https://tools.dongvanfb.net/api/get_code_oauth2

{
    "email": "dsfsd45t4dfg@hotmail.com",
    "refresh_token": "M.C518_BAY.0.U.-CtLyFkvpx3K*0NhzBPs4WM*pnGJXJkiN6BRN90zWaaX0CsGNQifKlyVRku8uzJNqdEFTzvhhF7coNzQ1y8eWM6bAu9i4jGIWQojThUG9mRt5iOKtrNUYIpVIpzbNJmxg0ScX10OvSUpISzGHuiF6g7NPu1g7PJZKQYlraipFnfp7bbHNLN9CwhlsoN5FOWZsK!Otm5lIj6fETNXzFVKQvbaVKPJon1E1Qx*M4f3XFs8uIl*Ym*S41F9ivu3htQzEpxpsFT1vImq1mew*GeNPQj!fEkFE32GbyapC5b0YW07u2vbyXuqAttNDEaIv8O6ULdyBdeKUCjEh2AeYj32qp9k8TWBpYfCFlAbBhceLmumKYsYNIsUzlYaopWcE5ZIowDeVNYVFrbnFs5VH1keKWmDISe88bFfRzUW8OEhVW*f9!QMqOn8shv1YtWb3uquRJg$$",
    "client_id": "5464fghj-bnmm-jh56-56fh-454345sdff",
    "type": "tiktok"
}

```

#### 2. Response

```json
{
    "email": "tommiel@hotmail.com",
    "password": "bV1emc",
    "status": true,
    "code": "37589",
    "content": "37589 is your Facebook confirmation code",
    "date": "22:43 - 15/04/2022"
}

```
