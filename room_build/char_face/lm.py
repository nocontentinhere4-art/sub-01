import mediapipe as mp, numpy as np, sys
from mediapipe.tasks.python import vision, BaseOptions
_det = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
    base_options=BaseOptions(model_asset_path=__file__.rsplit('/',1)[0]+'/face_landmarker.task'), num_faces=1,
    min_face_detection_confidence=0.2, min_face_presence_confidence=0.2))
def landmarks(path_or_arr):
    im = mp.Image.create_from_file(path_or_arr) if isinstance(path_or_arr,str) else mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(path_or_arr[...,:3]))
    r = _det.detect(im)
    if not r.face_landmarks: return None
    return np.array([[p.x*im.width, p.y*im.height] for p in r.face_landmarks[0]])
if __name__ == '__main__':
    for f in sys.argv[1:]:
        l = landmarks(f); print(f.split('/')[-1], None if l is None else (l.shape, l.min(0).round(), l.max(0).round()))
