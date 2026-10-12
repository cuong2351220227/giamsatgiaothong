import json
import math
from pathlib import Path
from urllib.parse import parse_qs

from django.conf import settings
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.shortcuts import render
from django.db import transaction
from django.views.decorators.http import require_http_methods
from django.utils.text import get_valid_filename

from .models import TrafficSnapshot, TrafficStatus, Video
from .services import VideoProcessingService

MAX_VIDEO_UPLOAD_BYTES = 500 * 1024 * 1024
VIDEO_UPLOAD_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}


def _parse_json_body(request):
    body = request.body.decode("utf-8") if request.body else ""
    if not body.strip():
        return {}

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        pairs = parse_qs(body, keep_blank_values=True)
        if not pairs:
            raise ValueError("Request body phải là JSON hợp lệ.")

        data = {key: values[0] if len(values) == 1 else values for key, values in pairs.items()}
    else:
        if not isinstance(data, dict):
            raise ValueError("Request body phải là object JSON.")
        return data

    if not isinstance(data, dict):
        raise ValueError("Request body phải là object JSON.")

    return data


def _serialize_video(video):
    return {
        "id": video.id,
        "title": video.title,
        "file_path": video.file_path,
        "duration": video.duration,
        "created_at": video.created_at.isoformat(),
    }


def _serialize_status(entry):
    return {
        "id": entry.id,
        "video": entry.video.title,
        "status": entry.status,
        "status_label": entry.status_label,
        "vehicle_count": entry.vehicle_count,
        "captured_at": entry.captured_at.isoformat(),
    }


def dashboard(request):
    return render(request, "traffic/dashboard.html")


def healthcheck(request):
    return JsonResponse({"status": "ok", "app": "traffic"})


@require_http_methods(["GET", "POST"])
def videos(request):
    if request.method == "POST":
        uploaded_file = None
        if request.content_type == "multipart/form-data":
            payload = request.POST
            uploaded_file = request.FILES.get("file")
            if uploaded_file is None:
                return JsonResponse({"error": "Vui lòng chọn file video."}, status=400)
            extension = Path(uploaded_file.name).suffix.lower()
            if extension not in VIDEO_UPLOAD_EXTENSIONS:
                return JsonResponse({"error": "Định dạng video không được hỗ trợ."}, status=400)
            if uploaded_file.size <= 0 or uploaded_file.size > MAX_VIDEO_UPLOAD_BYTES:
                return JsonResponse({"error": "File video phải lớn hơn 0 và không vượt quá 500 MB."}, status=400)
        else:
            try:
                payload = _parse_json_body(request)
            except ValueError as exc:
                return JsonResponse({"error": str(exc)}, status=400)

        title = payload.get("title")
        if uploaded_file is not None:
            title = title or Path(uploaded_file.name).stem
            safe_name = get_valid_filename(Path(uploaded_file.name).name)
            stored_name = default_storage.save(f"videos/{safe_name}", uploaded_file)
            file_path = str(Path(default_storage.path(stored_name)))
        else:
            file_path = payload.get("file_path")
            if not isinstance(file_path, str) or not file_path.strip():
                return JsonResponse({"error": "Thiếu hoặc không hợp lệ: file_path."}, status=400)
            title = title or Path(file_path).stem or "video"

        if not isinstance(title, str) or not title.strip():
            title = "video"

        try:
            duration = float(payload.get("duration", 0.0))
        except (TypeError, ValueError):
            return JsonResponse({"error": "duration phải là số."}, status=400)
        if not math.isfinite(duration) or duration < 0:
            return JsonResponse({"error": "duration phải là số không âm hợp lệ."}, status=400)

        video = Video.objects.create(
            title=title,
            file_path=file_path,
            duration=duration,
        )
        return JsonResponse({
            "message": "Video created",
            "video": _serialize_video(video),
        }, status=201)

    videos_list = [_serialize_video(item) for item in Video.objects.order_by("-created_at")]
    return JsonResponse({"videos": videos_list})


def api_videos(request):
    return videos(request)


@require_http_methods(["GET"])
def current(request):
    latest = TrafficStatus.objects.select_related("video").order_by("-captured_at").first()
    if latest is None:
        return JsonResponse({
            "video": None,
            "status": "Bình thường",
            "status_label": "Bình thường",
            "vehicle_count": 0,
            "captured_at": None,
        }, status=200)

    return JsonResponse({
        "video": latest.video.title,
        "status": latest.status,
        "status_label": latest.status_label,
        "vehicle_count": latest.vehicle_count,
        "captured_at": latest.captured_at.isoformat(),
    })


def api_traffic_current(request):
    return current(request)


@require_http_methods(["GET"])
def history(request):
    rows = TrafficStatus.objects.select_related("video").order_by("-captured_at")[:20]
    history = [_serialize_status(item) for item in rows]
    return JsonResponse({"history": history})


def api_traffic_history(request):
    return history(request)


@require_http_methods(["GET"])
def stats(request):
    snapshots = TrafficSnapshot.objects.order_by("-captured_at")[:20]
    payload = [{
        "id": item.id,
        "video_id": item.video_id,
        "total_vehicles": item.total_vehicles,
        "car_count": item.car_count,
        "motorcycle_count": item.motorcycle_count,
        "bus_count": item.bus_count,
        "truck_count": item.truck_count,
        "density": item.density,
        "captured_at": item.captured_at.isoformat(),
    } for item in snapshots]
    return JsonResponse({"stats": payload})


def api_traffic_stats(request):
    return stats(request)


def _process_video_record(video):
    try:
        result = VideoProcessingService(video.file_path, video_id=video.id).process()
    except (OSError, ValueError) as exc:
        return JsonResponse({"error": str(exc)}, status=422)

    counts = result.get("counts", {})
    status_label = result.get("status", "Bình thường")
    try:
        with transaction.atomic():
            snapshot = TrafficSnapshot.objects.create(
                video=video,
                total_vehicles=int(counts.get("total", 0)),
                car_count=int(counts.get("car", 0)),
                motorcycle_count=int(counts.get("motorcycle", 0)),
                bus_count=int(counts.get("bus", 0)),
                truck_count=int(counts.get("truck", 0)),
                density=float(result.get("density", 0.0)),
            )
            TrafficStatus.objects.create(
                video=video,
                status=status_label,
                status_label=status_label,
                vehicle_count=int(snapshot.total_vehicles),
            )
    except (TypeError, ValueError) as exc:
        return JsonResponse({"error": f"Kết quả xử lý không hợp lệ: {exc}"}, status=500)

    return JsonResponse({
        "message": "Video processed",
        "video_id": video.id,
        "status": status_label,
        "counts": counts,
        "density": snapshot.density,
        "output": result.get("output"),
        "frames": result.get("frames", 0),
    })


@require_http_methods(["POST"])
def process_video(request, video_id=None):
    if video_id is not None:
        try:
            video = Video.objects.get(pk=video_id)
        except Video.DoesNotExist:
            return JsonResponse({"error": "Không tìm thấy video."}, status=404)
        return _process_video_record(video)

    try:
        payload = _parse_json_body(request)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    video_path = payload.get("file_path")
    if not isinstance(video_path, str) or not video_path.strip():
        return JsonResponse({"error": "Thiếu hoặc không hợp lệ: file_path."}, status=400)

    video, _ = Video.objects.get_or_create(
        file_path=video_path,
        defaults={"title": Path(video_path).stem or "video"},
    )
    return _process_video_record(video)
