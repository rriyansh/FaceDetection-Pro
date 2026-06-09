#!/usr/bin/env python3
"""
REYPROJECT – Control Mac with Hands, Mouth, Eyes + Air Drawing
- Both hands -> Open Terminal
- No hands -> Close Terminal
- Mouth open -> Open Safari
- Mouth closed -> Close Safari
- Eyes closed 5 sec -> Beep alert
- Index finger -> Draw | Index+Middle -> Erase
"""

import os
import time
import platform
import cv2
import mediapipe as mp
import numpy as np
import pygame
import subprocess

# ========== CONFIG ==========
EYE_CLOSED_ALERT_SEC = 5.0
DRAW_COLOR = (0, 255, 0)
DRAW_THICK = 4
ERASE_RADIUS = 25

# ========== INIT ==========
pygame.mixer.init()

def play_beep():
    try:
        sample_rate = 44100
        dur = 0.4
        freq = 880
        t = np.linspace(0, dur, int(sample_rate*dur))
        wave = 0.5 * np.sin(2*np.pi*freq*t)
        wave = (wave*32767).astype(np.int16)
        wave = np.stack([wave, wave], axis=1)
        sound = pygame.sndarray.make_sound(wave)
        sound.play()
    except:
        if platform.system() == "Windows":
            import winsound
            winsound.Beep(1000, 400)
        else:
            os.system('say "beep" &')

# ========== MEDIAPIPE ==========
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=2, min_detection_confidence=0.7)
mp_face = mp.solutions.face_mesh
face_mesh = mp_face.FaceMesh(refine_landmarks=True)
mp_draw = mp.solutions.drawing_utils

# ========== STATE ==========
last_terminal_state = None
last_safari_state = None
last_eye_alert = 0
eye_close_start = None
canvas = None
prev_point = None

def open_terminal():
    if platform.system() == "Windows":
        subprocess.Popen("start cmd", shell=True)
    else:
        subprocess.Popen("open -a Terminal", shell=True)
    print("[Action] Terminal Opened")

def close_terminal():
    if platform.system() == "Windows":
        os.system("taskkill /f /im cmd.exe")
    else:
        os.system("pkill Terminal")
    print("[Action] Terminal Closed")

def open_safari():
    if platform.system() != "Windows":
        subprocess.Popen("open -a Safari", shell=True)
        print("[Action] Safari Opened")

def close_safari():
    if platform.system() != "Windows":
        os.system("pkill Safari")
        print("[Action] Safari Closed")

def init_camera():
    for i in range(3):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            print(f"[✓] Camera found at index {i}")
            return cap
        cap.release()
    print("[!] No camera found. Check permissions.")
    return None

# ========== MAIN ==========
def main():
    global canvas, prev_point, last_terminal_state, last_safari_state, last_eye_alert, eye_close_start
    
    cap = init_camera()
    if cap is None:
        return
    
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 60)
    
    cv2.namedWindow("ReyProject", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("ReyProject", 640, 480)
    
    print("\n" + "="*40)
    print("REYPROJECT ACTIVE")
    print("👐 Both hands -> Open Terminal")
    print("🙅 No hands -> Close Terminal")
    print("👄 Mouth open -> Open Safari")
    print("👄 Mouth closed -> Close Safari")
    print("😴 Eyes closed 5s -> Beep")
    print("✍️ Index finger -> Draw | Index+Middle -> Erase")
    print("Press 'c' to clear drawing, 'q' to quit")
    print("="*40 + "\n")
    
    fps = 0
    fcnt = 0
    ftime = time.time()
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("[!] Frame grab failed, retrying...")
            time.sleep(0.1)
            continue
        
        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        if canvas is None:
            canvas = np.zeros_like(frame)
        
        hand_result = hands.process(rgb)
        face_result = face_mesh.process(rgb)
        now = time.time()
        
        # --- Hands: terminal + drawing ---
        num_hands = 0
        if hand_result.multi_hand_landmarks:
            num_hands = len(hand_result.multi_hand_landmarks)
            hand_lm = hand_result.multi_hand_landmarks[0]
            mp_draw.draw_landmarks(frame, hand_lm, mp_hands.HAND_CONNECTIONS)
            
            h, w, _ = frame.shape
            index_tip = hand_lm.landmark[8]
            ix, iy = int(index_tip.x * w), int(index_tip.y * h)
            index_up = hand_lm.landmark[8].y < hand_lm.landmark[6].y
            middle_up = hand_lm.landmark[12].y < hand_lm.landmark[10].y
            
            if index_up and not middle_up:
                if prev_point:
                    cv2.line(canvas, prev_point, (ix, iy), DRAW_COLOR, DRAW_THICK)
                prev_point = (ix, iy)
            elif index_up and middle_up:
                cv2.circle(frame, (ix, iy), ERASE_RADIUS, (0,0,0), -1)
                cv2.circle(canvas, (ix, iy), ERASE_RADIUS, (0,0,0), -1)
                prev_point = None
            else:
                prev_point = None
        else:
            prev_point = None
        
        # Terminal control
        if num_hands >= 2:
            if last_terminal_state != "open":
                open_terminal()
                last_terminal_state = "open"
        else:
            if last_terminal_state != "closed":
                close_terminal()
                last_terminal_state = "closed"
        
        cv2.putText(frame, f"Hands: {num_hands}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,0), 1)
        
        # --- Mouth: safari control ---
        mouth_open = False
        if face_result.multi_face_landmarks:
            lm = face_result.multi_face_landmarks[0].landmark
            upper_lip = lm[13]
            lower_lip = lm[14]
            mouth_dist = abs(upper_lip.y - lower_lip.y)
            if mouth_dist > 0.03:
                mouth_open = True
            for idx in [13,14,78,308]:
                x = int(lm[idx].x * frame.shape[1])
                y = int(lm[idx].y * frame.shape[0])
                cv2.circle(frame, (x, y), 2, (0,255,255), -1)
        
        if mouth_open:
            if last_safari_state != "open":
                open_safari()
                last_safari_state = "open"
        else:
            if last_safari_state != "closed":
                close_safari()
                last_safari_state = "closed"
        
        cv2.putText(frame, f"Mouth: {'OPEN' if mouth_open else 'CLOSED'}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0) if mouth_open else (0,0,255), 1)
        
        # --- Eyes: closure alert ---
        eyes_closed = False
        if face_result.multi_face_landmarks:
            lm = face_result.multi_face_landmarks[0].landmark
            left_ratio = abs(lm[159].y - lm[145].y)
            right_ratio = abs(lm[386].y - lm[374].y)
            avg_ratio = (left_ratio + right_ratio) / 2.0
            if avg_ratio < 0.01:
                eyes_closed = True
            for idx in [159,145,386,374]:
                x = int(lm[idx].x * frame.shape[1])
                y = int(lm[idx].y * frame.shape[0])
                cv2.circle(frame, (x, y), 2, (0,255,255), -1)
        
        if eyes_closed:
            if eye_close_start is None:
                eye_close_start = now
            else:
                closed_dur = now - eye_close_start
                if closed_dur >= EYE_CLOSED_ALERT_SEC and (now - last_eye_alert) > 3:
                    play_beep()
                    last_eye_alert = now
                    print(f"[ALERT] Eyes closed {closed_dur:.1f}s")
            cv2.putText(frame, "Eyes: CLOSED", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2)
        else:
            eye_close_start = None
            cv2.putText(frame, "Eyes: OPEN", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2)
        
        # Merge canvas
        frame = cv2.addWeighted(frame, 0.7, canvas, 0.3, 0)
        
        # FPS
        fcnt += 1
        if now - ftime >= 1:
            fps = fcnt
            fcnt = 0
            ftime = now
        cv2.putText(frame, f"FPS:{fps}", (frame.shape[1]-70, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,0), 1)
        
        cv2.imshow("ReyProject", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('c'):
            canvas = np.zeros_like(frame)
            print("[✓] Drawing cleared")
    
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
