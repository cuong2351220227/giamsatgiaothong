import json
import mimetypes
import math
from pathlib import Path
import re
from urllib.parse import parse_qs

from django.conf import settings
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404, HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import render
from django.db import transaction
from django.utils.encoding import filepath_to_uri
from django.utils._os import safe_join
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
    media_root = Path(settings.MEDIA_ROOT).resolve()
    source_path = Path(video.file_path).resolve()
    try:
        source_relative_path = source_path.relative_to(media_root)
        video_url = f"{settings.MEDIA_URL}{filepath_to_uri(source_relative_path.as_posix())}"
    except ValueError:
        video_url = None

    processed_path = media_root / "processed" / f"video_{video.id}" / "annotated.mp4"
    processed_url = None
    if processed_path.is_file():
        processed_relative_path = processed_path.relative_to(media_root)
        processed_url = f"{settings.MEDIA_URL}{filepath_to_uri(processed_relative_path.as_posix())}"

    return {
        "id": video.id,
        "title": video.title,
        "file_path": video.file_path,
        "video_url": video_url,
        "processed_url": processed_url,
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


def media_file(request, path):
    try:
        media_path = Path(safe_join(str(settings.MEDIA_ROOT), path))
    except ValueError as exc:
        raise Http404 from exc
    if not media_path.is_file():
        raise Http404

    file_size = media_path.stat().st_size
    content_type = mimetypes.guess_type(media_path.name)[0] or "application/octet-stream"
    range_header = request.headers.get("Range")
    if range_header:
        match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip())
        if not match or not any(match.groups()) or file_size == 0:
            response = HttpResponse(status=416)
            response["Content-Range"] = f"bytes */{file_size}"
            response["Accept-Ranges"] = "bytes"
            return response

        range_start, range_end = match.groups()
        if range_start:
            start = int(range_start)
            end = int(range_end) if range_end else file_size - 1
        else:
            suffix_length = int(range_end)
            start = max(file_size - suffix_length, 0)
            end = file_size - 1
        if start >= file_size or end < start:
            response = HttpResponse(status=416)
            response["Content-Range"] = f"bytes */{file_size}"
            response["Accept-Ranges"] = "bytes"
            return response

        end = min(end, file_size - 1)
        remaining = end - start + 1

        def stream_range():
            with media_path.open("rb") as media:
                media.seek(start)
                bytes_left = remaining
                while bytes_left:
                    chunk = media.read(min(64 * 1024, bytes_left))
                    if not chunk:
                        break
                    bytes_left -= len(chunk)
                    yield chunk

        response = StreamingHttpResponse(stream_range(), status=206, content_type=content_type)
        response["Content-Length"] = str(remaining)
        response["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        response["Accept-Ranges"] = "bytes"
        return response

    response = FileResponse(media_path.open("rb"), content_type=content_type)
    response["Accept-Ranges"] = "bytes"
    return response


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
        "output_url": _media_url(result.get("output")),
        "frames": result.get("frames", 0),
    })


def _media_url(file_path):
    if not file_path:
        return None
    try:
        relative_path = Path(file_path).resolve().relative_to(Path(settings.MEDIA_ROOT).resolve())
    except ValueError:
        return None
    return f"{settings.MEDIA_URL}{filepath_to_uri(relative_path.as_posix())}"


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
