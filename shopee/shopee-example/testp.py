import uiautomator2 as u2

d = u2.connect()
# Kích hoạt bàn phím của u2 (chỉ cần làm 1 lần)
d.set_fastinput_ime(True) 

# Gõ trực tiếp chữ có dấu
d.send_keys("Áo thun nam có dấu")

# Sau khi dùng xong có thể trả lại bàn phím mặc định nếu muốn
# d.set_fastinput_ime(False)