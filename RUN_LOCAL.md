# Hướng dẫn chạy dịch vụ Smart Campus Notification API - Lab 04

Tài liệu này hướng dẫn chi tiết cách cài đặt, chạy thử nghiệm cục bộ và đóng gói bằng Docker cho dịch vụ **Smart Campus Notification API (Dịch vụ Thông báo đa kênh - Nhóm 16)**.

---

## 1. Cấu hình môi trường

Đảm bảo bạn đã cài đặt:
- **Node.js** (LTS 20.x hoặc mới hơn)
- **Python** (Phiên bản gợi ý: **3.11** hoặc **3.12** để tránh lỗi biên dịch Rust của pydantic trên 3.14)
- **Docker Desktop** (Đang chạy)

Cài đặt dependencies cho Postman/Newman/Prism:
```bash
# Bỏ qua lỗi Execution Policy trong PowerShell bằng cách chạy trực tiếp qua cmd
cmd.exe /c "npm install"
```

---

## 2. Các bước chạy Cục bộ (Local - Không dùng Docker)

### Bước 2.1: Tạo và kích hoạt môi trường ảo Python
```bash
# Tạo môi trường ảo với Python 3.12 (hoặc 3.11)
py -3.12 -m venv .venv

# Kích hoạt môi trường ảo
# Trên Windows PowerShell:
.venv\Scripts\Activate.ps1
# Trên Windows Command Prompt (cmd):
.venv\Scripts\activate.bat
```

### Bước 2.2: Cài đặt thư viện Python
```bash
.venv\Scripts\pip.exe install -r requirements.txt
```

### Bước 2.3: Khởi chạy API
```bash
.venv\Scripts\uvicorn.exe notification_app.main:app --app-dir src --host 127.0.0.1 --port 8000
```

Kiểm tra API đã sẵn sàng:
Mở một terminal mới và chạy:
```bash
curl http://127.0.0.1:8000/health
```
Kết quả mong đợi nhận về:
```json
{"status":"ok","service":"notification-service","version":"1.0.0"}
```

---

## 3. Các bước chạy bằng Docker Container

### Bước 3.1: Build Docker Image
```bash
docker build -t fit4110/notification-service:lab04 .
```

### Bước 3.2: Khởi chạy Container
```bash
docker run --rm \
  --name fit4110-notification-lab04 \
  -p 8000:8000 \
  --env-file .env.example \
  fit4110/notification-service:lab04
```

Kiểm tra sức khỏe container bằng cách gọi:
```bash
curl http://localhost:8000/health
```

---

## 4. Chạy kiểm thử tự động Newman

Khi service đang hoạt động ở cổng `8000` (dù chạy Local hay trong Docker Container), hãy mở một terminal mới và chạy lệnh kiểm thử:

```bash
cmd.exe /c "npm run test:local"
```

### Kết quả mong đợi:
- Toàn bộ **37 assertions** trong **20 API requests** phải chạy thành công và đạt tỉ lệ **100% PASS** (0 thất bại).
- Báo cáo Newman kết quả kiểm thử dạng XML và HTML sẽ được tự động kết xuất vào thư mục:
  - `reports/newman-lab04-local.xml`
  - `reports/newman-lab04-local.html`

---

## 5. Lệnh nhanh (Makefile)

Nếu máy của bạn hỗ trợ `make`, bạn có thể dùng các lệnh rút gọn sau:
- `make install` - Cài đặt dependencies Node.js.
- `make build` - Xây dựng Docker Image cho Notification Service.
- `make run` - Khởi chạy Docker Container.
- `make test-docker` - Chạy bộ kiểm thử Newman trên container cổng 8000.
- `make stop` - Dừng container đang hoạt động.
- `make clean-reports` - Dọn sạch các file báo cáo cũ.
