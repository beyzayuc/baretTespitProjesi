from pathlib import Path

import cv2
from ultralytics import YOLO


PROJECT_DIR = Path(__file__).resolve().parent.parent
VIDEO_PATH = PROJECT_DIR / "test_videos" / "baretsiz.mp4"
HELMET_MODEL_PATH = PROJECT_DIR / "outputs" / "helmet_v1" / "weights" / "best.pt"
OUTPUT_PATH = PROJECT_DIR / "outputs" / "baret_tespit_sonucu.mp4"

PERSON_CONFIDENCE = 0.35
HELMET_CONFIDENCE = 0.50
HEAD_REGION_RATIO = 0.40


def point_inside_box(point_x, point_y, box):
    x1, y1, x2, y2 = box
    return x1 <= point_x <= x2 and y1 <= point_y <= y2


def main():
    if not VIDEO_PATH.exists():
        raise FileNotFoundError(f"Video bulunamadi: {VIDEO_PATH}")
    if not HELMET_MODEL_PATH.exists():
        raise FileNotFoundError(f"Baret modeli bulunamadi: {HELMET_MODEL_PATH}")

    print("Modeller yukleniyor...")
    person_model = YOLO("yolov8n.pt")
    helmet_model = YOLO(str(HELMET_MODEL_PATH))

    video = cv2.VideoCapture(str(VIDEO_PATH))
    if not video.isOpened():
        raise RuntimeError(f"Video acilamadi: {VIDEO_PATH}")

    width = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = video.get(cv2.CAP_PROP_FPS) or 25.0

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(OUTPUT_PATH),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )

    print("Video isleniyor. Erken cikmak icin Q tusuna basin.")

    while True:
        success, frame = video.read()
        if not success:
            break

        person_result = person_model.track(
            frame,
            persist=True,
            classes=[0],
            conf=PERSON_CONFIDENCE,
            imgsz=320,
            tracker="bytetrack.yaml",
            verbose=False,
        )[0]

        helmet_result = helmet_model.predict(
            frame,
            classes=[1],
            conf=HELMET_CONFIDENCE,
            imgsz=320,
            verbose=False,
        )[0]

        helmets = []
        if helmet_result.boxes is not None:
            for helmet_box in helmet_result.boxes.xyxy.cpu().tolist():
                hx1, hy1, hx2, hy2 = map(int, helmet_box)
                helmets.append((hx1, hy1, hx2, hy2))
                cv2.rectangle(frame, (hx1, hy1), (hx2, hy2), (0, 215, 255), 2)
                cv2.putText(
                    frame,
                    "BARET",
                    (hx1, max(20, hy1 - 7)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (0, 215, 255),
                    2,
                )

        if person_result.boxes is not None:
            person_boxes = person_result.boxes.xyxy.cpu().tolist()
            track_ids = (
                person_result.boxes.id.int().cpu().tolist()
                if person_result.boxes.id is not None
                else [-1] * len(person_boxes)
            )

            for person_box, track_id in zip(person_boxes, track_ids):
                px1, py1, px2, py2 = map(int, person_box)
                head_bottom = py1 + int((py2 - py1) * HEAD_REGION_RATIO)
                head_region = (px1, py1, px2, head_bottom)

                has_helmet = False
                for hx1, hy1, hx2, hy2 in helmets:
                    helmet_center_x = (hx1 + hx2) // 2
                    helmet_center_y = (hy1 + hy2) // 2
                    if point_inside_box(helmet_center_x, helmet_center_y, head_region):
                        has_helmet = True
                        break

                if has_helmet:
                    color = (0, 200, 0)
                    label = f"BARETLI ID:{track_id}"
                else:
                    color = (0, 0, 255)
                    label = f"BARETSIZ ID:{track_id}"

                cv2.rectangle(frame, (px1, py1), (px2, py2), color, 3)
                cv2.putText(
                    frame,
                    label,
                    (px1, max(25, py1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    color,
                    2,
                )

        writer.write(frame)
        cv2.imshow("Baret Tespit Sistemi", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            print("Kullanici islemi durdurdu.")
            break

    video.release()
    writer.release()
    cv2.destroyAllWindows()
    print(f"Tamamlandi. Sonuc: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()