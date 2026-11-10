from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from .models import TrafficSnapshot, TrafficStatus, Video
from .services.classifier import KMeansTrafficClassifier
from .services.video_processor import VideoProcessingService
from scripts.tracker_counter import VehicleTrackerCounter


class TrafficViewsTests(TestCase):
    def test_site_root_redirects_to_dashboard(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Traffic Monitoring Dashboard")

    def test_list_videos_returns_empty_list_for_new_project(self):
        response = self.client.get(reverse("traffic:videos"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["videos"], [])

    def test_dashboard_renders_csrf_token_for_api_posts(self):
        response = self.client.get(reverse("traffic:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertContains(response, "Quản lý video")
        self.assertContains(response, 'id="results-list"')
        self.assertContains(response, 'id="video-list"')
        self.assertContains(response, 'id="stream-select"')
        self.assertIn("csrftoken", response.cookies)

    def test_api_videos_requires_file_path_on_create(self):
        response = self.client.post(
            "/api/videos/",
            data={"title": "demo video"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("file_path", response.json()["error"])

    def test_api_videos_create_and_list_work(self):
        response = self.client.post(
            "/api/videos/",
            data={"title": "test video", "file_path": "/tmp/test.mp4", "duration": 10.5},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("video", response.json())

        list_response = self.client.get("/api/videos/")
        self.assertEqual(list_response.status_code, 200)
        self.assertGreaterEqual(len(list_response.json()["videos"]), 1)

    def test_api_traffic_endpoints_return_payloads(self):
        video = Video.objects.create(title="demo", file_path="/tmp/demo.mp4", duration=12.5)
        TrafficStatus.objects.create(
            video=video,
            status="Đông",
            status_label="Đông",
            vehicle_count=15,
        )

        current = self.client.get("/api/traffic/current/")
        self.assertEqual(current.status_code, 200)
        self.assertIn("status", current.json())

        history = self.client.get("/api/traffic/history/")
        self.assertEqual(history.status_code, 200)
        self.assertIn("history", history.json())
        self.assertEqual(history.json()["history"][0]["video_id"], video.id)

        stats = self.client.get("/api/traffic/stats/")
        self.assertEqual(stats.status_code, 200)
        self.assertIn("stats", stats.json())

    def test_stream_endpoint_rejects_video_outside_upload_storage(self):
        video = Video.objects.create(title="Local video", file_path="C:/private/video.mp4")

        response = self.client.get(f"/api/videos/{video.id}/stream/")

        self.assertEqual(response.status_code, 422)
        self.assertIn("đã upload", response.json()["error"])

    @patch("traffic.services.video_processor.VehicleTrackerCounter")
    def test_video_processing_runs_tracker_and_returns_persistable_results(self, tracker_class):
        source_path = Path(__file__).resolve().parents[1] / "manage.py"
        tracker_class.return_value.process_video.return_value = {
            "source": str(source_path),
            "output": "runs/counting/processed/test/annotated.mp4",
            "frames": 30,
            "counts": {"car": 2, "motorcycle": 1, "bus": 0, "truck": 0},
            "total": 3,
            "crossings": [
                {"track_id": 1, "class_name": "car", "timestamp": 1.0, "frame_index": 30},
                {"track_id": 2, "class_name": "motorcycle", "timestamp": 2.0, "frame_index": 60},
            ],
        }

        with TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                result = VideoProcessingService(source_path, video_id=7).process()
                output_path = Path(tracker_class.call_args.kwargs["output"])
                self.assertEqual(
                    output_path,
                    Path(media_root) / "processed" / "video_7" / "annotated.mp4",
                )

        tracker_class.assert_called_once()
        tracker_class.return_value.process_video.assert_called_once_with(source_path)
        self.assertEqual(result["counts"]["total"], 3)
        self.assertEqual(result["frames"], 30)
        self.assertIn("status", result)

    @patch("traffic.views.VideoProcessingService.process")
    def test_processing_api_persists_snapshot_and_status(self, process):
        process.return_value = {
            "counts": {"total": 4, "car": 2, "motorcycle": 1, "bus": 1, "truck": 0},
            "status": "Đông",
            "density": 0.4,
            "output": "annotated.mp4",
            "frames": 120,
        }
        video = Video.objects.create(title="demo", file_path="demo.mp4")

        response = self.client.post(f"/api/videos/{video.id}/process/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(TrafficSnapshot.objects.get(video=video).total_vehicles, 4)
        self.assertEqual(TrafficStatus.objects.get(video=video).status, "Đông")

    def test_processing_api_reports_missing_video(self):
        response = self.client.post("/api/videos/9999/process/")
        self.assertEqual(response.status_code, 404)

    def test_classifier_handles_single_window_from_short_video(self):
        result = KMeansTrafficClassifier().classify(
            {"car": 1, "motorcycle": 0, "bus": 0, "truck": 0, "total": 1},
            events=[{"track_id": 1, "class_name": "car", "timestamp": 1.0, "frame_index": 30}],
        )

        self.assertEqual(result["status"], "Bình thường")
        self.assertEqual(result["density"], 0.1)

    def test_default_counting_line_scales_to_video_dimensions(self):
        tracker = VehicleTrackerCounter.__new__(VehicleTrackerCounter)
        self.assertEqual(
            tracker.default_counting_line(854, 480),
            ((68, 326), (786, 326)),
        )

    def test_create_status_and_history_endpoints_work(self):
        video = Video.objects.create(title="demo", file_path="/tmp/demo.mp4", duration=12.5)
        TrafficStatus.objects.create(
            video=video,
            status="Bình thường",
            status_label="Bình thường",
            vehicle_count=8,
        )

        response = self.client.get(reverse("traffic:history"))
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.json()["history"]), 1)

        current = self.client.get(reverse("traffic:current"))
        self.assertEqual(current.status_code, 200)


class MediaServingTests(TransactionTestCase):
    @patch("traffic.views.LiveVehicleStream")
    def test_uploaded_video_can_be_selected_as_a_live_mjpeg_stream(self, stream_class):
        with TemporaryDirectory() as media_root:
            source_path = Path(media_root) / "videos" / "road.mp4"
            source_path.parent.mkdir(parents=True)
            source_path.write_bytes(b"video")
            with override_settings(MEDIA_ROOT=media_root):
                video = Video.objects.create(title="Uploaded road video", file_path=str(source_path))
                stream_class.return_value.frames.return_value = iter([
                    b"--frame\r\nContent-Type: image/jpeg\r\n\r\ntest\r\n",
                ])

                response = self.client.get(f"/api/videos/{video.id}/stream/")

                self.assertEqual(response.status_code, 200)
                self.assertTrue(response["Content-Type"].startswith("multipart/x-mixed-replace"))
                self.assertIn(b"--frame", next(iter(response.streaming_content)))
                response.close()
                stream_class.return_value.close.assert_called()
                stream_class.assert_called_once_with(str(source_path.resolve()), video)

    def test_api_upload_and_video_byte_ranges_work(self):
        with TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                response = self.client.post(
                    "/api/videos/",
                    data={
                        "title": "Uploaded clip",
                        "file": SimpleUploadedFile(
                            "traffic.mp4",
                            b"video bytes",
                            content_type="video/mp4",
                        ),
                    },
                )

                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.json()["video"]["title"], "Uploaded clip")
                self.assertTrue(Path(response.json()["video"]["file_path"]).is_file())
                video_url = response.json()["video"]["video_url"]
                self.assertEqual(video_url, "/media/videos/traffic.mp4")

                media_response = self.client.get(video_url, HTTP_RANGE="bytes=0-4")
                self.assertEqual(media_response.status_code, 206)
                self.assertEqual(media_response["Content-Range"], "bytes 0-4/11")
                try:
                    self.assertEqual(b"".join(media_response.streaming_content), b"video")
                finally:
                    media_response.close()

    def test_processed_video_is_exposed_as_a_playable_media_url(self):
        video = Video.objects.create(title="processed", file_path="/local/source.mp4")
        with TemporaryDirectory() as media_root:
            processed_path = Path(media_root) / "processed" / f"video_{video.id}" / "annotated.mp4"
            processed_path.parent.mkdir(parents=True)
            processed_path.write_bytes(b"annotated video")

            with override_settings(MEDIA_ROOT=media_root):
                response = self.client.get("/api/videos/")
                video_data = next(item for item in response.json()["videos"] if item["id"] == video.id)
                self.assertEqual(
                    video_data["processed_url"],
                    f"/media/processed/video_{video.id}/annotated.mp4",
                )

                media_response = self.client.get(video_data["processed_url"], HTTP_RANGE="bytes=2-6")
                self.assertEqual(media_response.status_code, 206)
                try:
                    self.assertEqual(b"".join(media_response.streaming_content), b"notat")
                finally:
                    media_response.close()
