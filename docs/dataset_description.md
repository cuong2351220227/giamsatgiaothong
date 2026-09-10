# Mô tả dataset

## 1. Tổng quan

Dataset được sử dụng cho đề tài **Hệ thống giám sát giao thông bằng YOLO**. Đây là dataset object detection có sẵn, được tải từ Roboflow và lưu tại:

```text
data/external_dataset/
```

Thông tin nguồn:

- Tên dataset: `vehicle detection`
- Phiên bản: `v9`
- Nguồn: [Roboflow Vehicle Detection](https://universe.roboflow.com/vehicle-avnyy/vehicle-detection-x5epo/dataset/9)
- License: `CC BY 4.0`
- Tổng số ảnh: `2704`
- Kích thước sau tiền xử lý: `640 x 640`
- Định dạng annotation: YOLO object detection

Dataset đã có sẵn ba tập `train`, `valid` và `test`. Vì vậy, không chia lại hoặc di chuyển dữ liệu trong phạm vi bước này.

## 2. Cấu trúc thư mục

```text
data/external_dataset/
├── data.yaml
├── README.dataset.txt
├── README.roboflow.txt
├── train/
│   ├── images/
│   └── labels/
├── valid/
│   ├── images/
│   └── labels/
└── test/
    ├── images/
    └── labels/
```

Trong mỗi tập:

- `images/` chứa ảnh đầu vào.
- `labels/` chứa annotation tương ứng dưới dạng tệp `.txt`.
- Ảnh và label tương ứng có cùng tên, chỉ khác phần mở rộng.

## 3. File `data.yaml`

Nội dung chính của file cấu hình:

```yaml
train: ../train/images
val: ../valid/images
test: ../test/images

nc: 4
names: ['bus', 'car', 'motorbike', 'truck']
```

Do `data.yaml` nằm trong `data/external_dataset/`, các đường dẫn trên trỏ đến:

| Tập | Đường dẫn |
|---|---|
| Train | `data/external_dataset/train/images/` |
| Validation | `data/external_dataset/valid/images/` |
| Test | `data/external_dataset/test/images/` |

## 4. Class và class ID

Dataset có 4 class:

| Class ID | Tên trong dataset | Ý nghĩa |
|---:|---|---|
| 0 | `bus` | Xe buýt |
| 1 | `car` | Ô tô |
| 2 | `motorbike` | Xe máy |
| 3 | `truck` | Xe tải |

Các class này phù hợp với bốn nhóm phương tiện cần nhận diện trong đề tài. Tuy nhiên, thứ tự ID của dataset **không giống** thứ tự đề tài ban đầu (`0=car`, `1=motorcycle`, `2=bus`, `3=truck`). Khi huấn luyện hoặc xử lý kết quả, phải sử dụng mapping trong `data.yaml`; không được tự giả định ID theo thứ tự khác.

Tên `motorbike` trong dataset được hiểu là `motorcycle` theo yêu cầu của đề tài.

## 5. Thống kê số lượng ảnh

| Tập dữ liệu | Số ảnh | Số label | Tỷ lệ trên toàn bộ ảnh |
|---|---:|---:|---:|
| Train | 1.896 | 1.896 | 70,12% |
| Validation | 538 | 538 | 19,90% |
| Test | 270 | 270 | 9,99% |
| **Tổng cộng** | **2.704** | **2.704** | **100%** |

Các ảnh hiện có đều sử dụng phần mở rộng `.jpg`.

## 6. Thống kê object theo class

| Class ID | Class | Train | Validation | Test | Tổng |
|---:|---|---:|---:|---:|---:|
| 0 | bus | 605 | 185 | 70 | 860 |
| 1 | car | 2.751 | 783 | 401 | 3.935 |
| 2 | motorbike | 4.335 | 1.247 | 663 | 6.245 |
| 3 | truck | 1.953 | 556 | 242 | 2.751 |
| **Tổng** |  | **9.644** | **2.771** | **1.376** | **13.791** |

Dataset có sự chênh lệch số lượng object giữa các class. Class `motorbike` có nhiều object nhất, còn `bus` có ít object nhất. Đây là yếu tố cần lưu ý khi đánh giá precision, recall và mAP theo từng class.

## 7. Định dạng annotation YOLO

Mỗi dòng trong một file label có dạng:

```text
class_id x_center y_center width height
```

Trong đó:

- `class_id` là ID của class.
- `x_center`, `y_center` là tâm bounding box.
- `width`, `height` là chiều rộng và chiều cao bounding box.
- Các tọa độ được chuẩn hóa trong khoảng từ `0` đến `1` theo kích thước ảnh.

Ví dụ:

```text
0 0.31796875 0.51796875 0.2046875 0.3375
```

Dòng trên biểu diễn một object thuộc class `bus`.

## 8. Kết quả kiểm tra chất lượng

Chương trình kiểm tra tại [src/check_dataset.py](../src/check_dataset.py) đã được chạy trên toàn bộ dataset.

Kết quả:

- Không có ảnh không có label tương ứng.
- Không có label không có ảnh tương ứng.
- Không có class ID ngoài khoảng hợp lệ `0..3`.
- Không có tọa độ bounding box ngoài khoảng `[0, 1]`.
- Không có dòng label sai format.
- Không có bounding box có chiều rộng hoặc chiều cao không hợp lệ.

Dataset đủ điều kiện để chuyển sang bước huấn luyện YOLO sau khi hoàn thành các bước chuẩn bị cần thiết.

## 9. Cách kiểm tra lại

Từ thư mục gốc của project, kích hoạt môi trường ảo rồi chạy:

```powershell
python src/check_dataset.py
```

Chương trình chỉ đọc dataset và in báo cáo ra màn hình; không sửa, xóa hoặc di chuyển bất kỳ file nào.

## 10. Kết luận

Dataset hiện tại phù hợp với đề tài vì chứa bốn loại phương tiện: xe buýt, ô tô, xe máy và xe tải. Dataset đã được chia sẵn thành `train`, `valid` và `test`, có file `data.yaml`, có annotation YOLO hợp lệ và không cần chia lại ở bước mô tả dataset.