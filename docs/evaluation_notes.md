# Báo cáo đánh giá pretrained model

## 1. Thông tin lần đánh giá

| Mục | Giá trị |
|---|---|
| Model | `yolo11n.pt` |
| Dữ liệu | Video giao thông thực tế trong `test_samples/videos/` |
| Confidence threshold | `0.30` |
| IoU threshold | `0.45` |
| File kết quả | `runs/detect/predictions/17604987-hd_1920_1080_30fps.mp4` |
| File summary | `runs/detect/predictions/detection_summary.json` |
| File số liệu đánh giá | `runs/detect/predictions/evaluation_report.json` |

Tạo lại số liệu bằng:

```powershell
.\.venv\Scripts\Activate.ps1
python scripts/evaluate_pretrained.py
```

## 2. Số liệu tự động tổng hợp

Chạy `evaluate_pretrained.py` sau mỗi lần inference và điền kết quả vào bảng sau:

| Chỉ số | Kết quả |
|---|---:|
| Số frame | 796 |
| Tổng detection | 9.232 |
| Detection trung bình/frame | 11,60 |
| Detection `car` | 7.430 |
| Detection `motorcycle` | 190 |
| Detection `bus` | 965 |
| Detection `truck` | 647 |
| Precision | Chưa tính được nếu chưa có ground truth |
| Recall | Chưa tính được nếu chưa có ground truth |

Các số detection ở trên là số bounding box qua toàn bộ frame, không phải số phương tiện duy nhất. Một phương tiện xuất hiện trong nhiều frame sẽ được đếm nhiều lần.

## 3. Review thủ công

Summary inference không có nhãn đúng cho từng frame, vì vậy các chỉ số false positive, bỏ sót và nhầm class cần được đánh giá bằng cách xem video kết quả. Ghi lại các phát hiện quan sát được:

| Hiện tượng | Số lượng quan sát | Frame/thời điểm ví dụ | Nhận xét |
|---|---:|---|---|
| False positive | Chưa đánh giá |  | Box không phải phương tiện |
| Bỏ sót xe máy nhỏ | Chưa đánh giá |  | Xe máy xa, nhỏ hoặc bị che khuất |
| Nhầm `car` thành `truck` | Chưa đánh giá |  |  |
| Nhầm `truck` thành `car` | Chưa đánh giá |  |  |
| Bỏ sót do che khuất | Chưa đánh giá |  |  |

### Cách lấy tỷ lệ sau khi có ground truth

Khi có annotation đúng cho các frame được chọn, sử dụng IoU để ghép prediction với ground truth:

```text
precision = true_positive / (true_positive + false_positive)
recall = true_positive / (true_positive + false_negative)
```

Không điền `precision` hoặc `recall` bằng số detection/frame. Hai đại lượng đó cần ground truth và quy tắc ghép box rõ ràng.

## 4. Nhận xét theo bối cảnh giao thông Việt Nam

### 4.1. Góc nhìn camera từ trên cao

- Góc nhìn cao làm phương tiện có kích thước biểu kiến nhỏ hơn.
- Hình dạng nhìn từ trên xuống khác với nhiều ảnh COCO thông thường.
- Bounding box có thể bị cắt, méo phối cảnh hoặc khó xác định phần thân xe.
- Các xe ở xa dễ bị giảm confidence hoặc bị bỏ sót.

### 4.2. Mật độ xe máy cao

- Nhiều xe máy đứng sát nhau, che khuất một phần hoặc chồng lấn bounding box.
- Xe máy nhỏ có ít pixel, đặc biệt ở vùng xa camera.
- Model pretrained có thể gộp nhiều xe thành một box hoặc chỉ nhận diện xe nổi bật nhất.
- Các tình huống dừng chờ, đi thành nhóm và luồn giữa ô tô có thể khác phân bố dữ liệu COCO.

### 4.3. Nhầm lẫn giữa car và truck

- Góc nhìn trên cao làm mất các đặc trưng bên hông và phía trước xe.
- Xe tải nhỏ hoặc xe bị che một phần có thể có hình dạng gần với car.
- Cần kiểm tra riêng confusion giữa `car` và `truck`, không chỉ nhìn tổng số detection.

## 5. Tiêu chí quyết định train custom dataset

| Tiêu chí | Kết quả cần xem | Quyết định |
|---|---|---|
| Bối cảnh camera | Có góc nhìn trên cao giống dữ liệu triển khai không? | Nếu không, cần bổ sung custom data |
| Xe máy nhỏ | Có bỏ sót xe máy ở xa hoặc trong đám đông không? | Nếu có thường xuyên, cần custom data |
| Che khuất | Có gộp hoặc bỏ sót xe do xe đứng sát nhau không? | Nếu có, cần custom data |
| False positive | Có box xuất hiện trên vật thể không phải xe không? | Nếu nhiều, cần custom data và kiểm tra threshold |
| Car/truck confusion | Có nhầm lẫn lặp lại giữa hai class không? | Nếu có, cần thêm mẫu được gắn nhãn rõ |
| Phân bố class | Dữ liệu thực tế có nhiều xe máy hơn COCO không? | Nếu khác đáng kể, cần custom data |
| Chỉ số có ground truth | Precision/recall/mAP có đạt mục tiêu không? | Nếu không đạt, train hoặc fine-tune |

## 6. Kết luận đề xuất

### Kết luận hiện tại

Model pretrained đã nhận diện được bốn class phương tiện trên video thử nghiệm. Tuy nhiên, số liệu hiện có mới là thống kê prediction; chưa thể kết luận precision, recall hoặc tỷ lệ false positive chính thức vì video chưa có ground-truth annotation.

### Quyết định về custom dataset

**Đề xuất train thêm trên custom dataset giao thông Việt Nam.** Lý do chính:

1. Góc nhìn camera từ trên cao khác với nhiều mẫu tổng quát trong COCO.
2. Mật độ xe máy dày đặc tạo ra che khuất và chồng lấn bounding box.
3. Xe máy nhỏ ở xa dễ bị bỏ sót.
4. Có nguy cơ nhầm giữa `car` và `truck` khi phương tiện bị che hoặc nhìn từ trên xuống.
5. Custom dataset giúp mô hình học đúng góc camera, điều kiện ánh sáng, mật độ và phân bố phương tiện của hệ thống thực tế.

Khuyến nghị tạo tập custom có các cảnh: giờ cao điểm, nhiều xe máy, camera trên cao, thời tiết khác nhau, xe bị che khuất, xe ở xa và các trường hợp car/truck dễ nhầm. Tập này nên có annotation YOLO và được chia thành train/valid/test độc lập trước khi fine-tune.