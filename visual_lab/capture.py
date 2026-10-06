"""Manual RGB capture using Replicator, avoiding the deprecated Camera wrapper.

A capture advances rendering, NOT simulation time. Inference is synchronous while
paused. This convenient simulation protocol is not a real-time robot solution.
"""
from __future__ import annotations
from .core import LabError
from .png import encode_array

class SceneCamera:
    def __init__(self, config: dict):
        import omni.replicator.core as rep
        import omni.timeline
        self.rep = rep
        self.timeline = omni.timeline.get_timeline_interface()
        self.config = config
        rep.orchestrator.set_capture_on_play(False)
        self.camera = rep.create.camera(position=tuple(config["position"]),
            look_at=tuple(config["look_at"]), focal_length=float(config["focal_length_mm"]))
        self.product = rep.create.render_product(self.camera, tuple(config["resolution"]))
        self.annotator = rep.AnnotatorRegistry.get_annotator("rgb", device="cpu")
        self.annotator.attach([self.product])

    def png(self) -> bytes:
        import numpy as np
        self.timeline.pause()
        start = float(self.timeline.get_current_time())
        data = None
        # A new render, rather than blindly reusing a cached last frame.
        for _ in range(3):
            self.rep.orchestrator.step(delta_time=0.0, pause_timeline=True,
                rt_subframes=self.config["rt_subframes"], wait_for_render=True)
            data = self.annotator.get_data()
            if isinstance(data, dict):
                data = data.get("data")
            if data is not None:
                array = np.asarray(data)
                if array.ndim == 3 and array.size > 0:
                    break
        end = float(self.timeline.get_current_time())
        if abs(end - start) > 1e-7:
            raise LabError(f"Zero-time capture changed timeline from {start} to {end}")
        if data is None:
            raise LabError("RGB annotator returned no data; check renderer/GPU/assets")
        array = np.asarray(data)
        w, h = self.config["resolution"]
        if array.shape not in {(h, w, 3), (h, w, 4)}:
            raise LabError(f"Unexpected RGB shape {array.shape}, expected {(h,w,3)} or RGBA")
        if array.dtype != np.uint8 or np.max(array[:, :, :3]) == 0:
            raise LabError("Camera produced invalid/all-black image; inspect scene, light and camera pose")
        return encode_array(array)

    def close(self) -> None:
        self.annotator.detach([self.product])
        self.product.destroy()
