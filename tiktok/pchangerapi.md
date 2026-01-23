# Pchanger Device API

Tài liệu dành cho khách hàng – gọi API nội bộ để điều khiển tác vụ trên thiết bị (Random, Change, Backup, Restore, …). Tất cả endpoint đều là `GET` và trả về JSON.

## Tổng quan

* **Base URL:** `http://<PC-IP>:8080`
* **Namespace theo thiết bị:** `/dev/{key}/...`
* **Định dạng:** `application/json`
* **Mạng:** PC & điện thoại ở cùng LAN

## Gợi ý sử dụng

* Dùng trình duyệt/cURL/Postman để thử nhanh.
* Tham số query cần URL-encode (vd: dấu cách = `%20`).
* Nếu nhận `{"status":false,"note":"device busy"}` → đợi tác vụ hiện tại hoàn tất rồi gọi lại.

---

## Danh sách endpoint

### GET `/dev/{key}/device`

Kiểm tra trạng thái và thông tin thiết bị đang gắn `{key}`.

```http
# Ví dụ
GET http://127.0.0.1:8080/dev/bd4f93575cadfb7/device

# Phản hồi OK
{"status":"true","adb":"566215dabbfafd","key":"bd4f93575cadfb7"}

# Bận
{"status":false,"note":"device busy"}

```

### GET `/dev/{key}/random`

Random thông tin trước khi Change (cập nhật trực tiếp lên UI).

```http
# Ví dụ
GET http://127.0.0.1:8080/dev/bd4f93575cadfb7/random

# Phản hồi
{"status":true,"note":"Random"}

# Bận
{"status":false,"note":"device busy"}

```

### GET `/dev/{key}/change`

Kích hoạt quy trình thay đổi (ghi info, reboot, cài APK…).

```http
# Ví dụ
GET http://127.0.0.1:8080/dev/bd4f93575cadfb7/change
GET http://127.0.0.1:8080/dev/544876fad182321/change?lat=123.32&lon=23.321

# Phản hồi
{"status":true,"note":"Waiting for change"}

# Bận
{"status":false,"note":"device busy"}

```

### GET `/dev/{key}/backup?name=<tên>`

Tạo bản sao lưu với tên chỉ định. Tên chỉ chấp nhận `[A-Za-z0-9._-]{1,64}`.

```http
# Ví dụ
GET http://127.0.0.1:8080/dev/bd4f93575cadfb7/backup?name=PixelBackup01

# Phản hồi
{"status":true,"note":"Waiting for backup"}

# Lỗi tên
{"status":false,"note":"Lỗi kí tự, đừng sử dụng kí tự đặc biệt."}

# Bận
{"status":false,"note":"device busy"}

```

### GET `/dev/{key}/restore?name=<tên>`

Khôi phục từ bản backup đã tồn tại (tên phải khớp danh sách hiện có).

```http
# Ví dụ
GET http://127.0.0.1:8080/dev/bd4f93575cadfb7/restore?name=PixelBackup01

# Phản hồi
{"status":true,"note":"Waiting for restore"}

# Không tìm thấy
{"status":false,"note":"không tìm thấy file"}

# Bận
{"status":false,"note":"device busy"}

```

### GET `/devices`

Danh sách tất cả bản backup hiện có trên máy chủ.

```http
# Ví dụ
GET http://127.0.0.1:8080/dev/devices 

# Phản hồi
[{"serialTWRP":"224a1e9734037ece","serialOnline":"a85c1a8b941184","Process":false,"state":"ONLINE","key":"544876fad182321"}]

# Không tìm thấy
[]

```

### GET `/list_backup`
Danh sách tất cả bản backup hiện có trên máy chủ.

```http
# Ví dụ
GET http://127.0.0.1:8080/list_backup

# Phản hồi mẫu
[
  {"last_restore":"08/10/25 22:26:47","total":0,"address":"F:\\Tool\\S9-12.1\\backup\\new\\776979430-4ALNAN","date_created":"08/10/25 22:26:47","name":"776979430-4ALNAN","id":4},
  {"last_restore":"14/10/25 00:14:12","total":1,"address":"F:\\Tool\\S9-12.1\\backup\\new\\776940090-A20881","date_created":"08/10/25 19:19:40","name":"776940090-A20881","id":3}
]

```

Trả về một mảng JSON. Mỗi phần tử gồm: `id`, `name`, `date_created`, `last_restore`, `total`, `address`.

---

## Mã trạng thái & lưu ý

| Tình huống | HTTP | Nội dung JSON |
| --- | --- | --- |
| Nhận lệnh thành công | 200 | `{"status":true,"note":"..."}` |
| Thiết bị bận | 200/409 | `{"status":false,"note":"device busy"}` |
| Sai phương thức | 405 | — |
| Tham số thiếu/không hợp lệ | 400 | `{"status":false,"note":"invalid ..."}` |

Hiện tại server trả 200 cho nhiều tình huống. Nếu muốn rõ ràng hơn với ứng dụng tích hợp, có thể đổi các trường hợp lỗi thành 4xx/409.