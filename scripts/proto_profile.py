
import sys, cv2, numpy as np
sys.path.insert(0,"src")
from guitar_detector import GuitarDetector
from scipy.signal import find_peaks
img = cv2.imread("data/townshend.jpg")
if img.shape[1]>1200:
    s=1200/img.shape[1]; img=cv2.resize(img,(1200,int(img.shape[0]*s)))
det=GuitarDetector()
g=det.detect_guitar(img); n=det.detect_neck(g)
neck=det.neck_frame
gray=cv2.cvtColor(neck,cv2.COLOR_BGR2GRAY)
blur=cv2.GaussianBlur(gray,(5,5),sigmaX=1.0)
clahe=cv2.createCLAHE(clipLimit=2.0,tileGridSize=(8,8)).apply(blur)
grad=cv2.Scharr(clahe,cv2.CV_64F,1,0)
col=np.mean(cv2.convertScaleAbs(grad),axis=0)
smooth=cv2.GaussianBlur(col.reshape(1,-1).astype(np.float32),(31,1),sigmaX=3.0).flatten()
thr=np.percentile(smooth,85)
peaks,props=find_peaks(smooth,height=thr,prominence=5,distance=10)
print("neck shape",neck.shape)
print("num peaks",len(peaks))
print("peak xs",peaks)
print("proms",props["prominences"].round(1))
# try lower percentile to get more peaks
for t in (75,65,55,45):
    thr2=np.percentile(smooth,t)
    p2,_=find_peaks(smooth,height=thr2,prominence=5,distance=10)
    print(f"thr {t}: {len(p2)} peaks, xs={p2}")
