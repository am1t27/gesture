import os
import cv2

class SentenceEngine:
    def __init__(self):
        self.finalBuffer = []
        self.append_text = ""
        self.new_text = ""
        self.counts = 0

    def append_character(self, char, mask_64):
        self.counts += 1
        self.append_text += char
        self.new_text += char
        
        if not os.path.exists('./TempGest'):
            os.mkdir('./TempGest')
            
        img_names = f"./TempGest/{self.counts}{char}.png"
        cv2.imwrite(img_names, mask_64)

        self.finalBuffer.append(self.append_text)
        self.append_text = ""
        
        return self.new_text

    def save_sentence(self):
        if len(self.finalBuffer) >= 1:
            with open("temp.txt", "w") as f:
                for i in self.finalBuffer:
                    f.write(i)
        
    def clear(self):
        self.finalBuffer = []
        self.append_text = ""
        self.new_text = ""
        self.counts = 0
