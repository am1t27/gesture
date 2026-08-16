"""
verify_model.py — check the recognition pipeline against the labelled dataset.

Run from the Source Code directory:

    .venv/bin/python verify_model.py

Two things are measured:

1. Classifier accuracy on Dataset/test_set, if that folder is present. This
   tests the model and the numpy inference engine on real labelled masks.
2. Segmentation accuracy on camera-like frames synthesised from those masks
   (lighting gradient, sensor noise, and both hand-darker and hand-lighter
   backgrounds). This tests the part that actually broke in practice: turning
   a webcam frame into the clean silhouette the model expects.

Skips gracefully when the dataset is not checked out — it is excluded from
git because it is 52,000 images.
"""
import os
import sys

import cv2
import numpy as np

from recognition_engine import RecognitionEngine, LABELS

TEST_SET = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'Dataset', 'test_set')
PER_CLASS = 10


def synth_roi(mask, dark_hand=True, rng=None):
    """Turn a binary training mask into a plausible 200x200 camera crop."""
    rng = rng or np.random.default_rng(0)
    height, width = mask.shape
    hand_v, background_v = (70, 190) if dark_hand else (200, 80)

    value = np.where(mask > 127, hand_v, background_v).astype(np.float32)
    ys, xs = np.mgrid[0:height, 0:width]
    value += 40 * (xs / width - 0.5) + 20 * (ys / height - 0.5)   # uneven light
    value += rng.normal(0, 8, value.shape)                        # sensor noise
    value = np.clip(value, 0, 255).astype(np.uint8)

    hsv = cv2.merge([np.full_like(value, 15), np.full_like(value, 90), value])
    bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    return cv2.resize(bgr, (200, 200), interpolation=cv2.INTER_LINEAR)


def main():
    if not os.path.isdir(TEST_SET):
        print(f"Dataset not found at {TEST_SET} — nothing to verify.")
        print("The dataset is excluded from git; copy Dataset/ in to run this.")
        return 0

    engine = RecognitionEngine()
    rng = np.random.default_rng(0)

    print("1. Classifier on labelled masks")
    correct = total = 0
    for index, letter in enumerate(LABELS):
        folder = os.path.join(TEST_SET, letter)
        if not os.path.isdir(folder):
            continue
        batch = []
        for name in sorted(os.listdir(folder))[:PER_CLASS]:
            image = cv2.imread(os.path.join(folder, name))
            if image is not None:
                batch.append(cv2.cvtColor(image, cv2.COLOR_BGR2RGB).astype(np.float32))
        if not batch:
            continue
        predictions = engine.classifier.predict(np.array(batch)).argmax(axis=1)
        correct += int((predictions == index).sum())
        total += len(batch)
    print(f"   {correct}/{total} correct ({100 * correct / total:.1f}%)\n")

    print("2. Full segmentation pipeline on synthetic camera frames")
    for description, dark_hand in [("hand darker than background", True),
                                   ("hand lighter than background", False)]:
        seg_correct = seg_total = 0
        for letter in LABELS:
            folder = os.path.join(TEST_SET, letter)
            if not os.path.isdir(folder):
                continue
            for name in sorted(os.listdir(folder))[:PER_CLASS]:
                mask = cv2.imread(os.path.join(folder, name), cv2.IMREAD_GRAYSCALE)
                if mask is None:
                    continue
                roi = synth_roi(mask, dark_hand, rng)
                segmented, _ = engine._segment(roi)
                small = cv2.resize(segmented, (64, 64), interpolation=cv2.INTER_AREA)
                small = np.where(small > 127, 255, 0).astype(np.uint8)
                predicted, _ = engine._classify(small)
                seg_correct += (predicted == letter)
                seg_total += 1
        print(f"   {description}: {seg_correct}/{seg_total} "
              f"({100 * seg_correct / seg_total:.1f}%)")

    print("\n3. Empty box is rejected rather than guessed")
    blank = np.full((200, 200), 185, np.float32)
    ys, xs = np.mgrid[0:200, 0:200]
    blank = np.clip(blank + 25 * (xs / 200 - 0.5) + rng.normal(0, 7, blank.shape), 0, 255)
    blank = blank.astype(np.uint8)
    hsv = cv2.merge([np.full_like(blank, 15), np.full_like(blank, 90), blank])
    _, separation = engine._segment(cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR))
    from recognition_engine import MIN_SEPARATION
    verdict = "rejected" if separation < MIN_SEPARATION else "ACCEPTED (bug)"
    print(f"   separation {separation:.1f} vs threshold {MIN_SEPARATION} — {verdict}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
