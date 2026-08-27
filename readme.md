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
├── manage.py
├── requirements.txt
├── .env
├── README.md
│
├── config/
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
│
├── traffic/
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   ├── admin.py
│   │
│   ├── services/
│   │   ├── video_processor.py
│   │   ├── detector.py
│   │   ├── counter.py
│   │   └── classifier.py
│   │
│   ├── templates/
│   └── static/
│       ├── css/
│       └── js/
│
├── dataset/
│   ├── train/
│   └── test/
│
└── weights/
    └── best.pt
```

---

# ⚙️ Cài đặt

### 1. Tạo môi trường ảo

```bash
python -m venv .venv
```

Windows:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 2. Cài đặt thư viện

```bash
pip install -r requirements.txt
```

### 3. Cấu hình PostgreSQL

```sql
CREATE DATABASE traffic_monitoring;
CREATE USER traffic_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE traffic_monitoring TO traffic_user;
```

Tạo `.env` và cấu hình database, YOLO model.

### 4. Chạy hệ thống

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Truy cập:

```text
http://127.0.0.1:8000/
```

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
