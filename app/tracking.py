from pathlib import Path
import cv2


def associate_people(people, detections):
    """One head per tracked person; no guessed IDs when tracking is absent."""
    pairs = []
    for i, p in enumerate(people):
        x1,y1,x2,y2 = p['box']
        w,h = max(1,x2-x1),max(1,y2-y1)
        for j,d in enumerate(detections):
            if d['class'] not in ('head','helmet','uncertain'):
                continue
            a,b,c,e = d['box']
            cx,cy=(a+c)/2,(b+e)/2
            if x1-.05*w <= cx <= x2+.05*w and y1-.05*h <= cy <= y1+.5*h:
                cost=abs(cx-(x1+x2)/2)/w + abs(cy-(y1+.15*h))/h
                pairs.append((cost,i,j))
    used_people,used_heads=set(),set()
    result=[{**p,'state':'unknown'} for p in people]
    for _,i,j in sorted(pairs):
        if i not in used_people and j not in used_heads:
            result[i]['state']=detections[j]['class']
            used_people.add(i);used_heads.add(j)
    return result


class PersonTracker:
    def __init__(self, path):
        from ultralytics import YOLO
        if not Path(path).is_file():
            raise FileNotFoundError('Kişi takip modeli bulunamadı.')
        self.model = YOLO(str(path))

    def update(self, frame, detections):
        r = self.model.track(frame, persist=True, classes=[0], conf=.35, imgsz=640, tracker='bytetrack.yaml', verbose=False, device='cpu')[0]
        people = []
        if r.boxes is not None and r.boxes.id is not None:
            for box,tid in zip(r.boxes.xyxy.cpu().tolist(),r.boxes.id.int().cpu().tolist()):
                people.append({'track_id':int(tid),'box':box})
        return associate_people(people,detections)

    @staticmethod
    def draw(frame, tracks):
        colors={'head':(0,0,255),'helmet':(40,200,40),'uncertain':(0,190,255),'unknown':(0,190,255)}
        labels={'head':'BARETSIZ','helmet':'BARETLI','uncertain':'KARARSIZ','unknown':'GORUNTU YETERSIZ'}
        for t in tracks:
            a,b,c,d=map(int,t['box']);color=colors[t['state']]
            cv2.rectangle(frame,(a,b),(c,d),color,2)
            cv2.putText(frame,f"ID:{t['track_id']} {labels[t['state']]}",(a,max(20,b-8)),cv2.FONT_HERSHEY_SIMPLEX,.6,color,2)
