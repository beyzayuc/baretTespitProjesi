import cv2

kamera = cv2.VideoCapture(0)

if not kamera.isOpened():
    print("Kamera açılamadı.")
    raise SystemExit

while True:
    basarili, goruntu = kamera.read()

    if not basarili:
        print("Kameradan görüntü alınamadı.")
        break

    cv2.imshow("Kamera Testi", goruntu)

    # q tuşuna basınca kapat
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

kamera.release()
cv2.destroyAllWindows()