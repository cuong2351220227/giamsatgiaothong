# Hướng dẫn tạo Database và kết nối PostgreSQL

Tài liệu này hướng dẫn cách tạo cơ sở dữ liệu PostgreSQL cho dự án giám sát giao thông, đồng thời cấu hình kết nối từ Django hoặc script Python của bạn.

---

## 1. Yêu cầu

- PostgreSQL 14+ đã được cài đặt
- Có thể truy cập bằng `psql` hoặc pgAdmin
- Python đã cài các thư viện cần thiết trong dự án

---

## 2. Kiểm tra PostgreSQL đã chạy chưa

### Windows PowerShell

```powershell
pg_isready
```

Nếu PostgreSQL đang chạy, máy sẽ trả về trạng thái `accepting connections`.

Nếu lệnh không tồn tại, hãy kiểm tra PostgreSQL đã được cài đặt và đã chạy service PostgreSQL.

---

## 3. Tạo database và user

### Cách 1: Dùng `psql`

Mở terminal PostgreSQL hoặc PowerShell với quyền truy cập PostgreSQL:

```sql
CREATE DATABASE traffic_monitoring;
CREATE USER traffic_user WITH PASSWORD 'change-this-password';
GRANT ALL PRIVILEGES ON DATABASE traffic_monitoring TO traffic_user;
```

Nếu muốn đặt quyền truy cập chi tiết hơn:

```sql
ALTER USER traffic_user WITH SUPERUSER;
```

> Lưu ý: Trong môi trường thực tế nên dùng mật khẩu mạnh, không để mật khẩu thật trong mã nguồn.

---

### Cách 2: Dùng pgAdmin

1. Mở pgAdmin
2. Kết nối tới server PostgreSQL
3. Chuột phải vào `Databases` → `Create` → `Database`
4. Tạo database tên: `traffic_monitoring`
5. Kích hoạt `Login/Group Roles` và tạo user `traffic_user`
6. Thiết lập password và cấp quyền truy cập cho database vừa tạo

---

## 4. Cấu hình file `.env`

Tại thư mục gốc của dự án, tạo file `.env` dựa trên mẫu trong [.env.example](../.env.example).

Ví dụ nội dung:

```env
DJANGO_SECRET_KEY=change-this-secret-key
DJANGO_DEBUG=True

POSTGRES_DB=traffic_monitoring
POSTGRES_USER=traffic_user
POSTGRES_PASSWORD=change-this-password
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432

YOLO_MODEL_PATH=weights/best.pt
```

### Giá trị cần khớp với database vừa tạo

| Biến | Giá trị ví dụ |
|---|---|
| POSTGRES_DB | traffic_monitoring |
| POSTGRES_USER | traffic_user |
| POSTGRES_PASSWORD | change-this-password |
| POSTGRES_HOST | 127.0.0.1 |
| POSTGRES_PORT | 5432 |

> Không commit file `.env` lên Git. Chỉ giữ `.env.example` để tham khảo.

---

## 5. Cấu hình kết nối trong Django

Nếu dự án đang dùng Django, thiết lập trong file `settings.py` như sau:

```python
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('POSTGRES_DB', 'traffic_monitoring'),
        'USER': os.getenv('POSTGRES_USER', 'traffic_user'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD', 'change-this-password'),
        'HOST': os.getenv('POSTGRES_HOST', '127.0.0.1'),
        'PORT': os.getenv('POSTGRES_PORT', '5432'),
    }
}
```

Nếu project đang sử dụng biến môi trường từ `python-dotenv`, hãy đảm bảo đã load file `.env` trước khi gọi Django:

```python
from dotenv import load_dotenv
load_dotenv()
```

---

## 6. Tạo schema và chạy migration

Sau khi cấu hình xong, chạy các lệnh sau:

```powershell
python manage.py check
python manage.py migrate
```

Nếu chưa có superuser:

```powershell
python manage.py createsuperuser
```

Khởi động server:

```powershell
python manage.py runserver
```

Mở địa chỉ:

- http://127.0.0.1:8000/
- http://127.0.0.1:8000/admin/

---

## 7. Test kết nối PostgreSQL bằng Python

Bạn có thể kiểm tra nhanh bằng lệnh sau:

```powershell
python -c "import psycopg; conn = psycopg.connect(dbname='traffic_monitoring', user='traffic_user', password='change-this-password', host='127.0.0.1', port='5432'); print('Connected'); conn.close()"
```

Nếu kết nối thành công, sẽ in ra:

```text
Connected
```

---

## 8. Troubleshooting

### Lỗi: connection refused

Nguyên nhân thường gặp:

- PostgreSQL chưa chạy
- Host hoặc port sai
- Server chỉ chấp nhận localhost nhưng bạn đang dùng địa chỉ khác

Giải pháp:

```powershell
pg_isready
```

Kiểm tra lại `.env` và port `5432`.

### Lỗi: password authentication failed

Check lại:

- mật khẩu của `traffic_user`
- tên database khớp với `POSTGRES_DB`
- user dùng đúng username

### Lỗi: database does not exist

Chạy lại:

```sql
CREATE DATABASE traffic_monitoring;
```

---

## 9. Gợi ý cho dự án này

Với dự án giám sát giao thông, bạn nên dùng các bảng theo mô hình đề xuất như:

- `Video`
- `VehicleDetection`
- `TrafficSnapshot`
- `TrafficStatus`

Việc này giúp lưu trữ:

- video upload
- phát hiện phương tiện theo thời gian thực
- số lượng phương tiện đếm được
- trạng thái giao thông theo từng khoảng thời gian

---

## 10. Lệnh khởi tạo nhanh

Nếu muốn tạo database và cấu hình nhanh trong Windows PowerShell, bạn có thể dùng các lệnh sau:

```powershell
Copy-Item .env.example .env
```

Sau đó chỉnh sửa file `.env` theo đúng mật khẩu và tài khoản PostgreSQL của bạn.

---

## 11. Kết luận

Sau khi hoàn thành các bước trên, bạn đã:

- tạo database PostgreSQL
- tạo user truy cập
- cấu hình `.env`
- kết nối sang Django hoặc Python
- sẵn sàng lưu dữ liệu giám sát giao thông vào cơ sở dữ liệu

Nếu cần, bạn có thể tiếp tục tạo model Django và migration cho các bảng `Video`, `VehicleDetection`, `TrafficSnapshot`, `TrafficStatus` theo thiết kế mô hình của dự án.
