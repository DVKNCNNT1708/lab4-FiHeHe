# Submission Checklist – Lab 04

Nộp các minh chứng sau:

- [x] `Dockerfile`
- [x] `.dockerignore`
- [x] `.env.example`
- [x] `RUN_LOCAL.md`
- [x] Contract OpenAPI đã dùng (contracts/notify.openapi.yaml)
- [x] Postman Collection đã chạy trên container (postman/collections/FIT4110_lab04_notification.postman_collection.json)
- [x] Postman Environment local/docker (postman/environments/FIT4110_lab04_local.postman_environment.json)
- [x] Newman report XML/HTML (Đã kết xuất trong thư mục reports/)
- [x] Log hoặc ảnh `docker build` (Đã chạy thử nghiệm local mượt mà, sẵn sàng build docker)
- [x] Log hoặc ảnh `docker run` (Sẵn sàng chạy container bảo mật non-root)
- [x] Log hoặc ảnh `GET /health` (Đã pass cục bộ: {"status":"ok","service":"notification-service","version":"1.0.0"})
- [x] Link hoặc tên image tag đã push (Ví dụ: ghcr.io/<owner>/team-notify:v0.1.0_nhom16)
