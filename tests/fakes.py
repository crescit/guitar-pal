"""Duck-typed fakes for ultralytics YOLO and mediapipe HandLandmarker,
so ML-module control flow is testable without GPU/Metal/downloads."""
import numpy as np


# ---------------------------------------------------------------- ultralytics
class RowProxy:
    """Mimics a torch tensor element: .cpu() -> self, .numpy() -> ndarray."""
    def __init__(self, arr):
        self._arr = np.asarray(arr, dtype=np.float32)

    def cpu(self):
        return self

    def numpy(self):
        return self._arr


class FakeBoxes:
    def __init__(self, xyxy, conf):
        self.xyxy = [RowProxy(np.array(xyxy, dtype=np.float32))]
        self.conf = [float(conf)]

    def __len__(self):
        return 1

    def __getitem__(self, i):
        return self


class FakeKeypoints:
    def __init__(self, neck_xy=None, finger_xy=None):
        self.xy = [RowProxy(np.array(neck_xy, dtype=np.float32))] if neck_xy is not None else []
        self.data = [RowProxy(np.array(finger_xy, dtype=np.float32))] if finger_xy is not None else []
        self._len = max(len(self.xy), len(self.data))

    def __len__(self):
        return self._len


class EmptyBoxes:
    def __init__(self):
        self.xyxy = []
        self.conf = []

    def __len__(self):
        return 0


class FakeYoloResult:
    def __init__(self, boxes=None, keypoints=None):
        self.boxes = boxes if boxes is not None else EmptyBoxes()
        self.keypoints = keypoints or FakeKeypoints()


class FakeYOLO:
    """Scriptable stand-in for ultralytics.YOLO."""
    def __init__(self, path=None, result=None):
        self.path = path
        self.conf = 0.0
        self._result = result or FakeYoloResult()

    def _set(self, boxes=None, keypoints=None):
        self._result = FakeYoloResult(boxes, keypoints)

    def predict(self, frame, verbose=False, max_det=1, conf=0.0, device=None):
        self.conf = conf
        self.device = device
        return [self._result]

    def __call__(self, frame, verbose=False, conf=0.0, max_det=1, device=None):
        return [self._result]


# ---------------------------------------------------------------- mediapipe
class FakeLandmark:
    def __init__(self, x, y, z=0.0):
        self.x, self.y, self.z = x, y, z


class FakeHandedness:
    def __init__(self, name, score):
        self.category_name = name
        self.score = score


class FakeHandResult:
    def __init__(self, hand_landmarks=None, handedness=None):
        self.hand_landmarks = hand_landmarks or []
        self.handedness = handedness or []


class FakeLandmarker:
    def __init__(self, result=None, video_result=None):
        self.result = result or FakeHandResult()
        self.video_result = video_result or result or FakeHandResult()

    def detect(self, img):
        return self.result

    def detect_for_video(self, img, ts):
        return self.video_result


def make_hand_landmarks(points):
    """points: list of (x, y, z) normalized -> list of FakeLandmark (21)."""
    out = []
    for i in range(21):
        if i < len(points):
            p = points[i]
        else:
            p = (0.1 + 0.03 * i, 0.1 + 0.05 * i, 0.0)
        out.append(FakeLandmark(p[0], p[1], p[2] if len(p) > 2 else 0.0))
    return out
