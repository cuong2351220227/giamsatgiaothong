# Checklist công việc K-Means

## ✅ Công việc đã hoàn thành

- [x] Xác định feature đầu vào cho K-Means
- [x] Chuẩn bị dữ liệu từ kết quả counting
- [x] Xử lý dữ liệu thu được và loại bỏ dữ liệu nhiễu
- [x] Chuẩn hóa feature (scaler)
- [x] Chọn K = 3
- [x] Huấn luyện K-Means
- [x] Xác định 3 cluster
- [x] Xác định cluster mật độ thấp
- [x] Xác định cluster mật độ vừa
- [x] Xác định cluster mật độ cao
- [x] Mapping cluster -> Bình thường / Đông / Ùn tắc
- [x] Kiểm tra kết quả phân loại lại trên dữ liệu mẫu
- [x] Lưu model K-Means và scaler ra file
- [x] Lưu phiên bản model và bảng mapping

## 📍 Mã nguồn liên quan

- [src/traffic_kmeans.py](../src/traffic_kmeans.py): triển khai mô hình và chuẩn hóa dữ liệu.
- [scripts/traffic_kmeans_analysis.py](../scripts/traffic_kmeans_analysis.py): script chạy phân tích lưu lượng theo K-Means.
- [runs/traffic_analysis](../runs/traffic_analysis): thư mục kết quả đầu ra của mô hình.

## ▶️ Cách chạy

```bash
python scripts/traffic_kmeans_analysis.py --source runs/counting/counting_summary.csv --output-dir runs/traffic_analysis --window-seconds 10 --k-clusters 3
```

Kết quả bao gồm:

- `traffic_features.csv`
- `traffic_statuses.csv`
- `traffic_kmeans_model.pkl`
- `cluster_mapping.json`
