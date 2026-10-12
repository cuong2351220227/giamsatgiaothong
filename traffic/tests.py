from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
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
        self.assertIn("csrftoken", response.cookies)

    def test_api_videos_requires_file_path_on_create(self):
        response = self.client.post(
            "/api/videos/",
            data={"title": "demo video"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("file_path", response.json()["error"])

    def test_api_videos_uploads_selected_video_file(self):
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

        stats = self.client.get("/api/traffic/stats/")
        self.assertEqual(stats.status_code, 200)
        self.assertIn("stats", stats.json())

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

        result = VideoProcessingService(source_path, video_id=7).process()

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
