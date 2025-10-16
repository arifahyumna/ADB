#!/usr/bin/env python3
# coding: utf-8

import sys, os
import tkinter as tk
import random
import datetime as dt
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from PIL import Image, ImageTk
import cv2

# MQTT
try:
    import paho.mqtt.client as mqtt
except Exception as e:
    print("Module paho-mqtt tidak ditemukan. Install dengan: pip3 install paho-mqtt")
    raise

from ultralytics import YOLO
model = YOLO("vision/weights/plastik/best.pt")

# ---------------- MQTT konfigurasi ----------------
MQTT_BROKER = "172.20.10.2"
MQTT_PORT = 1883
MQTT_TOPICS = [("press/temp", 0), ("press/alert", 0), ("sensor/daya", 0)]

# ---------------- variabel global ----------------
suhu_update = None
xs = []
ys = []
SSR_PIN = 17

# ---------------- Setup GPIO (dengan fallback simulasi) ----------------
import RPi.GPIO as GPIO

class FakeGPIO:
    BCM = None
    OUT = None
    @staticmethod
    def setmode(mode):
        print("FakeGPIO: setmode", mode)
    @staticmethod
    def setup(pin, mode):
        print(f"FakeGPIO: setup pin {pin}")
    @staticmethod
    def output(pin, state):
        print(f"FakeGPIO: output pin {pin} state {state}")
    @staticmethod
    def setwarnings(flag):
        pass

GPIO_AVAILABLE = True
try:
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(SSR_PIN, GPIO.OUT)
except RuntimeError as e:
    # biasanya terjadi bila tidak menjalankan sebagai root atau hardware tidak tersedia
    print("RPi.GPIO runtime error:", e)
    print("Menggunakan FakeGPIO — GPIO tidak aktif pada perangkat ini.")
    GPIO = FakeGPIO()
    GPIO_AVAILABLE = False
except Exception as e:
    print("Error in setting up GPIO:", e)
    print("Menggunakan FakeGPIO.")
    GPIO = FakeGPIO()
    GPIO_AVAILABLE = False

# ---------------- Tkinter UI ----------------
root = tk.Tk()
root.title("Smart Monitoring Machine")

frame_1 = tk.Frame(root, relief="groove", borderwidth=2)
frame_2 = tk.Frame(root, relief="groove", borderwidth=2)

frame_1.pack(side="left", fill=tk.BOTH, expand=True, padx=10, pady=10)
frame_2.pack(side="right", fill=tk.BOTH, expand=True, padx=10, pady=10)

# Frame 1 - PENCACAH
label_p1 = tk.Label(frame_1, text="PENCACAH", font=("Segoe UI", 12, "bold"))
label_p1.pack(pady=5)

frame_daya1 = tk.Frame(frame_1)
label_daya1 = tk.Label(frame_daya1, text="Daya")
label_unitd1 = tk.Label(frame_daya1, text="0 Watt", relief="ridge", width=10)
label_daya1.pack(side="left", padx=5)
label_unitd1.pack(side="left", padx=5)
frame_daya1.pack(pady=5)

frame_vision = tk.Frame(frame_1, bg="gray", width=300, height=200)
label_v = tk.Label(frame_vision, text="Kamera")
frame_vision.pack(pady=5)
frame_vision.pack_propagate(False)
label_v.pack(expand=True)

frame_klas = tk.Frame(frame_1)
label_klas = tk.Label(frame_klas, text="Klasifikasi:")
label_result = tk.Label(frame_klas, text="--", relief="ridge", width=10)
frame_klas.pack(pady=10)
label_klas.pack(side="left", padx=5)
label_result.pack(side="left", padx=5)

frame_process = tk.Frame(frame_1)
label_process = tk.Label(frame_process, text="--", relief="ridge", width=40)
frame_process.pack(pady=15)
label_process.pack(side="left")

# Frame 2 - PENCETAK
label_p2 = tk.Label(frame_2, text="PENCETAK", font=("Segoe UI", 12, "bold"))
label_p2.pack(pady=5)

frame_daya2 = tk.Frame(frame_2)
label_daya2 = tk.Label(frame_daya2, text="Daya:")
label_unitd2 = tk.Label(frame_daya2, text="0 Watt", relief="ridge", width=10)
frame_daya2.pack(pady=5)
label_daya2.pack(side="left", padx=5)
label_unitd2.pack(side="left", padx=5)

frame_grafik = tk.Frame(frame_2, bg="gray", width=300, height=300)
label_graf = tk.Label(frame_grafik, text="Grafik Suhu")
frame_grafik.pack(pady=5)
frame_grafik.pack_propagate(False)
label_graf.pack(expand=True)

frame_suhu = tk.Frame(frame_2)
label_suhu = tk.Label(frame_suhu, text="Suhu:")
label_units = tk.Label(frame_suhu, text="0 ℃", relief="ridge", width=10)
frame_suhu.pack(pady=10)
label_suhu.pack(side="left", padx=5)
label_units.pack(side="left", padx=5)

frame_alert = tk.Frame(frame_2)
label_alert = tk.Label(frame_alert, text="--", relief="ridge", width=40)
frame_alert.pack(pady=15)
label_alert.pack(side="left")

# ---------------- Grafik setup ----------------
fig, ax = plt.subplots(figsize=(4, 3))
canvas = FigureCanvasTkAgg(fig, master=frame_grafik)
canvas_widget = canvas.get_tk_widget()
canvas_widget.pack(pady=5)

ax.set_title("Monitoring Suhu Pencetak", fontsize=10, pad=10)
ax.set_xlabel("Waktu", fontsize=5)
ax.set_ylabel("Suhu (°C)", fontsize=5)
ax.grid(True, linestyle="--", alpha=0.6)

def update_plot(value):
    # 'value' bisa None jika belum ada update suhu
    xs.append(dt.datetime.now().strftime('%H:%M:%S'))
    ys.append(value if value is not None else 0)

    # hanya simpan 10 data terakhir
    xs[:] = xs[-10:]
    ys[:] = ys[-10:]

    # draw
    ax.clear()
    ax.plot(xs, ys, marker='o')
    ax.set_title("Monitoring Suhu Press Heater")
    ax.set_xlabel("Waktu")
    ax.set_ylabel("Suhu (°C)")
    ax.grid(True)
    plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
    fig.tight_layout()
    canvas.draw()

def graf_update():
    # gunakan global suhu_update
    global suhu_update
    update_plot(suhu_update)
    # panggil lagi tiap 5000 ms
    root.after(5000, graf_update)

# ---------------- MQTT callbacks ----------------
def on_connect(client, userdata, flags, rc):
    print("Connected to MQTT broker (rc =", rc, ")")
    client.subscribe(MQTT_TOPICS)

def on_message(client, userdata, msg):
    global suhu_update
    topic = msg.topic
    payload = msg.payload.decode()

    if topic == "press/temp":
        try:
            suhu_val = float(payload)
            suhu_update = suhu_val
            label_units.config(text=f"{suhu_val: .2f} ℃")
        except Exception:
            label_units.config(text=f"Error: {payload}")

    elif topic == "sensor/daya":
        try:
            daya_val = float(payload)
            label_unitd2.config(text=f"{daya_val} Watt")
        except Exception:
            label_unitd2.config(text=f"Error: {payload}")

    elif topic == "press/alert":
        label_alert.config(text="ALERT")

#----------------------Camera + YOLO Preview----------------
cap = cv2.VideoCapture(0)

def update_camera():
    ret, frame = cap.read()
    if ret:
        results = model.predict(frame, conf=0.25, imgsz=250, verbose=False,)
        
        for r in results:
            boxes = r.boxes
            names = r.names
            if len(boxes) > 0:
                cls_id = int(boxes.cls[0])
                detected_class = names[cls_id]
                break

        if detected_class:
            kelas = detected_class.lower()
            label_result.config(text=kelas)
            if kelas == "plastik":
                GPIO.output(SSR_PIN, GPIO.HIGH)
                label_process.config(text="SHREDDER ON")
            elif kelas in ["hand", "non plastik"]:
                GPIO.output(SSR_PIN, GPIO.LOW)
                label_process.config(text="SHREDDER OFF")

        else:
            GPIO.output(SSR_PIN, GPIO.LOW)
            label_result.config(text="--")
            label_process.config(text="--")

        annotated = results[0].plot()
        frame_rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
        imgtk = ImageTk.PhotoImage(Image.fromarray(frame_rgb).resize((300, 200)))
        label_v.imgtk = imgtk
        label_v.configure(image=imgtk)

    root.after(100, update_camera)

# ---------------- MQTT setup ----------------
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

try:
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()
except Exception as e:
    print("MQTT connection failed:", e)

# ---------------- Jalankan loops ----------------
# mulai klasifikasi loop & grafik loop
root.after(1000, update_camera)   # start klasifikasi setelah 1s
root.after(1000, graf_update)   # start grafik update setelah 1s

root.mainloop()

cap.release()
cv2.destroyAllWindows()