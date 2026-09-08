
from ultralytics import YOLO
import cv2, os, time
proj = os.path.expanduser("~")+"/Documents/Projects/guitar-buddy"
img = cv2.imread(proj+"/data/parlour.jpg")
print("img", img.shape)
t0=time.time()
m = YOLO(proj+"/models/Guitar-Detection.pt")
print("model loaded in", round(time.time()-t0,1), "s")
r = m.predict(img, conf=0.25, verbose=False)
boxes = r[0].boxes
print("detections:", len(boxes))
for b in boxes:
    print("  cls", int(b.cls[0]), "conf", round(float(b.conf[0]),3), "xyxy", [round(x,1) for x in b.xyxy[0].tolist()])
ann = r[0].plot()
cv2.imwrite(proj+"/data/parlour_yolo.jpg", ann)
print("annotated saved")
