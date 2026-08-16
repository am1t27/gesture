import os
import cv2

class GestureCapture:
    @staticmethod
    def save_gesture(name, mask_64):
        if not name:
            return False
        if not os.path.exists('./SampleGestures'):
            os.mkdir('./SampleGestures')
        
        img_name = f"./SampleGestures/{name}.png"
        cv2.imwrite(img_name, mask_64)
        return True
