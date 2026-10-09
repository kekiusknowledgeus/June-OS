import asyncio
import uuid
from .tools import N


class Camera:
    def __init__(self, config):
        self.config = config

    async def capture(self, device=0):
        if self.config.privacy or not self.config.camera_enabled:
            raise PermissionError("Camera disabled")
        def take():
            try:
                import cv2
            except ImportError:
                raise RuntimeError("Camera backend unavailable: install june-os[camera]")
            cam = cv2.VideoCapture(device, cv2.CAP_DSHOW)
            try:
                if not cam.isOpened():
                    raise RuntimeError("Camera not connected or in use")
                ok, frame = cam.read()
                if not ok:
                    raise RuntimeError("Camera returned no frame")
                path = self.config.root / "data/captures" / (uuid.uuid4().hex + ".png")
                if not cv2.imwrite(str(path), frame):
                    raise RuntimeError("Unable to save camera image")
                return {"path": str(path), "source": "camera", "device": device}
            finally:
                cam.release()
        return await asyncio.to_thread(take)

    def register(self, registry):
        registry.add("camera.capture", "Capture one explicitly enabled camera frame locally", self.capture, {"device": N}, sensor="camera")
