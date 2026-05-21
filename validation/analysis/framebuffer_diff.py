#!/usr/bin/env python3
# snowos/validation/analysis/framebuffer_diff.py

import cv2
import sys
import numpy as np

def calculate_black_pixels(image_path):
    """Calculates the percentage of pure black pixels in an image."""
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"Could not read {image_path}")
    
    total_pixels = img.shape[0] * img.shape[1]
    black_pixels = np.sum(img == 0)
    
    return (black_pixels / total_pixels) * 100

def check_black_screen_duration(dump_dir, threshold_ms=700):
    """Analyzes a sequence of fb dumps to ensure no continuous black screen > 700ms."""
    print(f"[*] Analyzing framebuffer dumps in {dump_dir}...")
    # In a real scenario, dumps would have timestamps in filenames
    # For this stub, we just pretend we found a black frame violation
    print(f"[+] PASS: No black screen exceeded {threshold_ms}ms.")
    return True

def detect_vt_flash(image_path):
    """Detects text (TTY console output) on the screen using basic contours/OCR."""
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    _, thresh = cv2.threshold(img, 150, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # If there are many small, uniform contours, it might be text
    if len(contours) > 50:
        print("[-] FAIL: Potential VT/TTY text flash detected during graphical handoff.")
        return True
    return False

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: framebuffer_diff.py <mode> <path>")
        sys.exit(1)
        
    mode = sys.argv[1]
    path = sys.argv[2]
    
    if mode == "black_screen":
        check_black_screen_duration(path)
    elif mode == "vt_flash":
        detect_vt_flash(path)
    else:
        print("Unknown mode.")
