import cv2
#kamera = cv2.VideoCapture(0)
#while
resim = cv2.imread("islemci.jpg")
cv2.imwrite("islemciResmi.jpg", resim)
cv2.waitKey(0)
cv2.destroyAllWindows()