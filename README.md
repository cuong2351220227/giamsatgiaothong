# 🚦 Hệ thống giám sát giao thông

Hệ thống sử dụng **YOLO + OpenCV + K-Means** để tự động nhận diện, đếm phương tiện và đánh giá tình trạng giao thông qua video.

## ✨ Chức năng chính

* 🚗 Nhận diện ô tô, xe máy, xe buýt, xe tải.
* 🔢 Đếm số lượng phương tiện theo thời gian.
* 📊 Phân loại giao thông: **Bình thường / Đông / Ùn tắc**.
* 💾 Lưu kết quả vào **PostgreSQL**.
* 🌐 Quản lý và hiển thị dữ liệu bằng **Django**.
* 📈 Trực quan hóa thống kê bằng **Chart.js**.
* 🎥 Upload và xử lý video giao thông.
* 📋 Xem lịch sử và so sánh kết quả xử lý.

---

## 🛠️ Công nghệ sử dụng

| Thành phần  | Công nghệ                   |
| ----------- | --------------------------- |
| Backend     | Django                      |
| AI          | YOLO                        |
| Xử lý video | OpenCV                      |
| Phân cụm    | K-Means                     |
| Database    | PostgreSQL                  |
| Frontend    | HTML, Bootstrap, JavaScript |
| Biểu đồ     | Chart.js                    |

---

## 🏗️ Kiến trúc hệ thống

```text
┌──────────────────┐
│  Video giao thông│
└────────┬─────────┘
         ↓
┌──────────────────┐
│      OpenCV      │
│ Đọc & xử lý video│
└────────┬─────────┘
         ↓
┌──────────────────┐
│       YOLO       │
│ Nhận diện xe     │
└────────┬─────────┘
         ↓
┌──────────────────┐
│ Vehicle Counter  │
│ Đếm phương tiện  │
└────────┬─────────┘
         ↓
┌──────────────────┐
│     K-Means      │
│ Phân tích mật độ │
└────────┬─────────┘
         ↓
┌──────────────────────────┐
│ Bình thường / Đông / Ùn │
└────────────┬─────────────┘
             ↓
        ┌───────────┐
        │  Django   │
        └─────┬─────┘
          ┌───┴────┐
          ↓        ↓
   PostgreSQL    Website
                  ↓
              Chart.js
```

---

# 📐 Phân tích & thiết kế hệ thống

## 1. Use Case Diagram

### Actor

* **Admin**: quản lý hệ thống, video và dữ liệu.
* **Người dùng**: upload video, xem kết quả và thống kê.

### Use Case chính

```text
                    ┌─────────────────────────┐
                    │ HỆ THỐNG GIÁM SÁT       │
                    │       GIAO THÔNG        │
                    │                         │
 Người dùng ───────►│ Đăng nhập               │
                    │                         │
 Người dùng ───────►│ Upload video            │
                    │                         │
 Người dùng ───────►│ Xử lý video             │
                    │       │                 │
                    │       ├─► Nhận diện YOLO│
                    │       ├─► Đếm phương tiện│
                    │       └─► K-Means       │
                    │                         │
 Người dùng ───────►│ Xem kết quả             │
                    │                         │
 Người dùng ───────►│ Xem thống kê            │
                    │                         │
 Người dùng ───────►│ Xem lịch sử             │
                    │                         │
 Admin ────────────►│ Quản lý video           │
 Admin ────────────►│ Quản lý dữ liệu         │
                    └─────────────────────────┘
```

---

## 2. Activity Diagram – Xử lý video

```text
        ┌─────────┐
        │ Bắt đầu │
        └────┬────┘
             ↓
      ┌──────────────┐
      │ Upload video │
      └──────┬───────┘
             ↓
      ┌──────────────┐
      │ Kiểm tra     │
      │ video        │
      └──────┬───────┘
             ↓
        Video hợp lệ?
         /         \
       Không        Có
        ↓           ↓
    Báo lỗi    Đọc frame
                    ↓
             Nhận diện YOLO
                    ↓
             Đếm phương tiện
                    ↓
             Tính mật độ
                    ↓
               K-Means
                    ↓
          Phân loại giao thông
                    ↓
          Lưu PostgreSQL
                    ↓
             Hiển thị kết quả
                    ↓
                 Kết thúc
```

---

## 3. Sequence Diagram – Xử lý video

```text
User        Django       OpenCV        YOLO       K-Means    PostgreSQL
 │             │            │            │            │           │
 │ Upload      │            │            │            │           │
 ├────────────►│            │            │            │           │
 │             │ Đọc video │            │            │           │
 │             ├───────────►│            │            │           │
 │             │            │ Frame      │            │           │
 │             │            ├───────────►│            │           │
 │             │            │            │ Detection  │           │
 │             │            │◄───────────┤            │           │
 │             │ Đếm xe     │            │            │           │
 │             ├─────────────────────────────────────►│           │
 │             │            │            │            │ Cluster   │
 │             │◄─────────────────────────────────────┤           │
 │             │ Lưu kết quả                                       │
 │             ├──────────────────────────────────────────────────►│
 │             │            │            │            │           │
 │◄────────────┤ Kết quả     │            │            │           │
```

---

## 4. Class Diagram

Các lớp chính của hệ thống:

```text
┌──────────────────────┐
│       Video          │
├──────────────────────┤
│ id                   │
│ name                 │
│ file_path            │
│ duration             │
│ created_at           │
├──────────────────────┤
│ upload()             │
│ process()            │
└──────────┬───────────┘
           │ 1
           │
           │ *
┌──────────▼───────────┐
│  VehicleDetection    │
├──────────────────────┤
│ id                   │
│ vehicle_type         │
│ confidence           │
│ x1, y1, x2, y2       │
│ timestamp            │
└──────────┬───────────┘
           │
           │ *
           │
┌──────────▼───────────┐
│   TrafficSnapshot    │
├──────────────────────┤
│ id                   │
│ vehicle_count        │
│ timestamp            │
│ density              │
└──────────┬───────────┘
           │ 1
           │
           │ 1
┌──────────▼───────────┐
│    TrafficStatus     │
├──────────────────────┤
│ id                   │
│ status               │
│ status_label         │
│ timestamp            │
└──────────────────────┘
```

---

## 5. ERD – Cơ sở dữ liệu

```text
┌───────────────┐
│     Video     │
├───────────────┤
│ PK id         │
│ name          │
│ file_path     │
│ duration      │
│ created_at    │
└───────┬───────┘
        │
        │ 1:N
        ↓
┌──────────────────────┐
│  VehicleDetection    │
├──────────────────────┤
│ PK id                │
│ FK video_id          │
│ vehicle_type         │
│ confidence            │
│ x1, y1, x2, y2       │
│ timestamp            │
└──────────────────────┘

        Video
          │
          │ 1:N
          ↓
┌──────────────────────┐
│   TrafficSnapshot    │
├──────────────────────┤
│ PK id                │
│ FK video_id          │
│ vehicle_count        │
│ density              │
│ timestamp            │
└──────────┬───────────┘
           │
           │ 1:1
           ↓
┌──────────────────────┐
│    TrafficStatus     │
├──────────────────────┤
│ PK id                │
│ FK snapshot_id       │
│ status               │
│ status_label         │
│ timestamp            │
└──────────────────────┘
```

---

## 6. Component Diagram

```text
┌──────────────────────────────────────────┐
│              Django System               │
│                                          │
│  ┌────────────┐     ┌────────────────┐  │
│  │ Web / API  │────►│ Video Processor │  │
│  └────────────┘     └───────┬────────┘  │
│                             ↓            │
│                      ┌─────────────┐     │
│                      │ YOLO Model  │     │
│                      └──────┬──────┘     │
│                             ↓            │
│                      ┌─────────────┐     │
│                      │   Counter   │     │
│                      └──────┬──────┘     │
│                             ↓            │
│                      ┌─────────────┐     │
│                      │  K-Means    │     │
│                      └─────────────┘     │
└───────────────────────┬──────────────────┘
                        ↓
                 ┌──────────────┐
                 │ PostgreSQL   │
                 └──────────────┘
```

---

## 7. Deployment Diagram

```text
┌──────────────────┐
│ Client / Browser │
│ Chrome, Edge     │
└────────┬─────────┘
         │ HTTP
         ↓
┌──────────────────────────┐
│       Django Server      │
│                          │
│ ┌────────┐ ┌──────────┐ │
│ │ Web/API│ │ AI Model │ │
│ └────────┘ └──────────┘ │
│      OpenCV + YOLO      │
└──────────┬───────────────┘
           │
           ↓
┌──────────────────────────┐
│       PostgreSQL         │
└──────────────────────────┘
```

---

# 📂 Cấu trúc dự án

```text
giamsatgiaothong/
├── README.md                  # Tài liệu chính
├── requirements.txt           # Phụ thuộc Python
├── .env.example               # Cấu hình mẫu, không chứa bí mật
├── scripts/                   # Lệnh huấn luyện, đánh giá và suy luận
│   ├── train.py
│   ├── verify_dataset.py
│   ├── inference_test.py
│   ├── evaluate_pretrained.py
│   ├── compare_models.py
│   └── setup_model.py
├── src/                       # Tiện ích kiểm tra và mã nguồn lõi
│   └── check_dataset.py
├── docs/                      # Mô tả dataset và ghi chú đánh giá
│   ├── dataset_description.md
│   ├── evaluation_notes.md
│   └── project_overview.md
├── data/                      # Dataset cục bộ, không commit
├── weights/                   # Model cục bộ, không commit
├── runs/                      # Kết quả chạy, không commit
└── test_samples/              # Video/ảnh kiểm thử cục bộ, không commit
```

---

# ⚙️ Cài đặt môi trường

## Yêu cầu

- Windows 10/11 và PowerShell.
- Python 3.10 trở lên. Môi trường đã kiểm tra với Python 3.13.
- Git.
- PostgreSQL 14 trở lên nếu sử dụng cơ sở dữ liệu PostgreSQL.
- Video giao thông và model YOLO đặt ở máy cục bộ.

## 1. Tạo và kích hoạt virtual environment

Mở PowerShell tại thư mục dự án:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Nếu PowerShell chặn script kích hoạt, chỉ áp dụng cho tài khoản hiện tại:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Sau đó chạy lại lệnh kích hoạt. Có thể dùng trực tiếp Python trong `.venv` mà không cần kích hoạt:

```powershell
.\.venv\Scripts\python.exe --version
```

## 2. Cài đặt thư viện Python

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Kiểm tra các thư viện chính:

```powershell
python -c "import cv2, django, numpy, pandas, sklearn; print('Environment OK')"
python -m pip check
```

## 3. Cấu hình biến môi trường

Tạo file `.env` từ file mẫu:

```powershell
Copy-Item .env.example .env
```

Mở `.env` và thay các giá trị mẫu, đặc biệt là `DJANGO_SECRET_KEY` và `POSTGRES_PASSWORD`. Không commit `.env` hoặc mật khẩu thật lên Git.

Các biến chính gồm:

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

## 4. Tạo cơ sở dữ liệu PostgreSQL

Đăng nhập PostgreSQL bằng `psql` hoặc pgAdmin và chạy:

```sql
CREATE DATABASE traffic_monitoring;
CREATE USER traffic_user WITH PASSWORD 'change-this-password';
GRANT ALL PRIVILEGES ON DATABASE traffic_monitoring TO traffic_user;
```

Đảm bảo thông tin trong `.env` trùng với tài khoản và cơ sở dữ liệu vừa tạo.

## 5. Khởi tạo và chạy Django

Khi `manage.py` đã có trong dự án, chạy:

```powershell
python manage.py check
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Mở website tại <http://127.0.0.1:8000/> và trang quản trị tại <http://127.0.0.1:8000/admin/>.

## 6. Dữ liệu video và model YOLO

Tạo các thư mục dữ liệu cục bộ nếu cần:

```powershell
New-Item -ItemType Directory -Force dataset\train, dataset\test, weights
```

Đặt model vào `weights\best.pt` hoặc cập nhật `YOLO_MODEL_PATH` trong `.env`. Video, dataset và model được Git bỏ qua vì có thể lớn hoặc chứa dữ liệu riêng tư.

## 7. Chạy các script

Các lệnh dưới đây được chạy từ thư mục gốc dự án:

Toàn bộ đường dẫn dữ liệu và model trong mã nguồn đều được tạo bằng `pathlib` từ thư mục dự án hoặc dùng đường dẫn tương đối. Không cần sửa đường dẫn khi chuyển dự án giữa các máy; chỉ cần đặt `data/`, `weights/` và `test_samples/` đúng vị trí như cấu trúc trên.

```powershell
python scripts\verify_dataset.py
python src\check_dataset.py
python scripts\train.py --help
python scripts\inference_test.py --help
```

### Pipeline xử lý video và RTSP

Module `scripts/pipeline_detector.py` nhận diện 4 loại phương tiện, hỗ trợ frame skipping, hiển thị FPS/count HUD và ghi video kết quả. Model mặc định là `final_weights/vehicle_detector_best.pt`.

```powershell
python scripts\pipeline_detector.py `
       --source test_samples\videos\traffic.mp4 `
       --skip-frames 2 `
       --conf 0.35 `
       --iou 0.45
```

Có thể truyền URL camera RTSP thay cho đường dẫn video:

```powershell
python scripts\pipeline_detector.py --source "rtsp://user:password@camera-ip:554/stream"
```

Video kết quả được ghi vào `runs/detect/pipeline_output.mp4`; log theo từng frame được ghi vào `runs/detect/detection_summary.json` và `runs/detect/detection_summary.csv`.

### Tracking và đếm xe qua vạch

Module `scripts/tracker_counter.py` dùng ByteTrack để duy trì ID, vẽ quỹ đạo và đếm mỗi phương tiện một lần khi tâm đáy bounding box cắt qua vạch.

Module cũng dùng `weights/yolo11n.pt` (COCO) để loại các box `motorbike` chồng mạnh lên box `person`. Đây là bộ lọc giảm nhận diện nhầm trong lúc chạy; để sửa tận gốc, cần bổ sung ảnh người làm hard negative hoặc thêm class `person` rồi huấn luyện lại model custom.

```powershell
python scripts\tracker_counter.py `
       --source test_samples\videos\17604987-hd_1920_1080_30fps.mp4 `
       --line-coords 100,800,1820,800 `
       --conf 0.35
```

`--line-coords` dùng tọa độ pixel theo kích thước video. Với video mẫu `1920x1080`, vạch ở `y=800` nằm trên mặt đường; không nên dùng `y=360` vì đó là vùng phía trên các phương tiện.

Có thể truyền tọa độ vạch dạng JSON:

```powershell
python scripts\tracker_counter.py `
       --source "rtsp://user:password@camera-ip:554/stream" `
       --line-coords "[[320,360],[960,360]]"
```

Video được ghi vào `runs/counting/counted_output.mp4`; báo cáo tổng kết được ghi vào `runs/counting/counting_summary.json` và `runs/counting/counting_summary.csv`.

## Xử lý lỗi thường gặp

- **Không nhận lệnh `python`**: cài Python và chọn tùy chọn thêm Python vào `PATH`.
- **Không kích hoạt được `.venv`**: chạy `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
- **Không kết nối được PostgreSQL**: kiểm tra PostgreSQL đang chạy, host, port, user, password và tên database trong `.env`.
- **OpenCV không đọc được video**: kiểm tra đường dẫn, định dạng video và quyền truy cập file.

---

# 📊 Đánh giá hệ thống

* **Precision / Recall / mAP**: đánh giá YOLO.
* **Counting Error**: đánh giá độ chính xác đếm phương tiện.
* **Classification Accuracy**: đánh giá 3 trạng thái giao thông.
* Kiểm tra khả năng xử lý video và lưu dữ liệu.

---

# 🚀 Hướng phát triển

* Bổ sung **YOLO Tracking** để hạn chế đếm trùng.
* Huấn luyện YOLO với dữ liệu giao thông địa phương.
* Cải thiện đặc trưng và thuật toán K-Means.
* So sánh nhiều mô hình nhận diện.
* Hỗ trợ camera trực tiếp.
* Docker hóa hệ thống.

> ⚠️ Không commit mật khẩu, dữ liệu cá nhân, video có bản quyền hoặc file model lớn lên GitHub.
