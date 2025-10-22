import os, sys, random, datetime as dt
import cv2
import torch
import tkinter as tk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from PIL import Image, ImageTk
import RPi.GPIO as GPIO
import threading
import time
from pathlib import Path
import paho.mqtt.client as mqtt
import json
from utils.augmentations import letterbox

from models.common import DetectMultiBackend
from utils.general import non_max_suppression, scale_boxes
from utils.torch_utils import select_device

# ---------------- variabel global ----------------
suhu_update = None
xs = []
ys = []
SSR_PIN = 17

#------------setup path and device--------------
FILE = Path(__file__).resolve()
ROOT = FILE.parents[0]  # YOLOv5 root directory
sys.path.append(str(ROOT))

device = select_device('')
model = DetectMultiBackend(str(ROOT / 'weights/plastik/best.pt'), device=device)
stride, names, pt = model.stride, model.names, model.pt 
model.warmup(imgsz=(1, 3, 640, 640))

#------------------setup GPIO------------------
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
    def setwarnings(flag):pass
	@staticmethod
	def cleanup():pass

GPIO_AVAILABLE = True
try:
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(SSR_PIN, GPIO.OUT)
    GPIO.output(SSR_PIN, GPIO.LOW)
    GPIO_AVAILABLE = True
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

#--------------setup tkinter gui---------------
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
	global flag_connected
	flag_connected = 1
	client_subscription(client)
	print("Connected to MQTT server")
    
def on_disconnect(client, userdata, rc):
	global flag_connected
	flag_connected = 0
	print("Disconncted From MQTT server")
    
def client_subscription(client):
	client.subscribe("esp32/#")

def on_message(client, userdata, msg):
    global suhu_update
    topic = msg.topic
    payload = msg.payload.decode()
    
    print(f"[DEBUG] Topic: {topic}, Payload: {payload}")

    if topic == "esp32/suhu":
        try:
            data = json.loads(payload)
            suhu_val = data["temp_c"]
            suhu_update = suhu_val
            label_units.config(text=f"{suhu_val: .2f} ℃")
        except Exception:
            label_units.config(text=f"Error: {payload}")
            print("error suhu: ", e)

    elif topic == "esp32/daya":
        try:
            data = json.loads(payload)
            daya_val = data.get("daya_watt", 0.0)
            label_unitd2.config(text=f"{daya_val} Watt")
        except Exception:
            label_unitd2.config(text=f"Error: {payload}")
            print("error daya: ", e)

    elif topic == "esp32/alert":
        try:
            data = json.loads(payload)
            alert_val = data.get("alert", payload)
            label_alert.config(text=f"{alert_val}")
        except Exception:
            label_alert.config(text=f"{payload}")
            print("error alert: ", e)
        

#--------------------Frame YOLO--------------------------
import queue

frame_queue = queue.Queue(maxsize=1)

annotated_frame = None
class_text = "--"
process_text = "--"

worker_running = True
worker_lock = threading.Lock()

cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("Kamera tidak terdeteksi")
else:
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

def worker():
    global annotated_frame, class_text,process_text, worker_running
    while worker_running:
        try:
            frame = frame_queue.get(timeout=0.5)
        except queue.Empty:
            continue
            
        try:
            img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            im = torch.from_numpy(img).to(device)
            im = im.permute(2, 0, 1).float() / 255.0
            im = im.unsqueeze(0)
            
            pred = model(im)
            pred = non_max_suppression(pred, conf_thres=0.25, iou_thres=0.45)
            
            detected_class = None
            for det in pred:
                if len(det):
                    det[:, :4] = scale_boxes(im.shape[2:], det[:, :4], frame.shape).round()
                    cls_id = int(det[0, 5])
                    detected_class = names[cls_id]
                    
            if detected_class:
                kelas = detected_class.lower()
                if kelas == "plastik":
                    try:
                        GPIO.output(SSR_PIN, GPIO.HIGH)
                    except Exception:
                        pass
                    out_class = kelas
                    out_proc = "SHREDDER ON"
                else:
                    try:
                        GPIO.output(SSR_PIN, GPIO.LOW)
                    except Exception:
                        pass
                    out_class = kelas
                    out_proc = "SHREDDER OFF"
            else:
                try:
                    GPIO.output(SSR_PIN, GPIO.LOW)
                except Exception:
                    pass
                out_class = "--"
                out_proc = "--"
                
            annotated = frame.copy()
            cv2.putText(annotated, f"{out_class}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
            
            with worker_lock:
                annotated_frame = annotated
                class_text = out_class
                process_text = out_proc
            
        except Exception as e:
            print("Worker exception:", e)
        
t = threading.Thread(target=worker, daemon=True)
t.start()

def update_camera():
    global annotated_frame, class_text, process_text
    
    ret, frame = cap.read()
    if ret:
        try:
            frame_queue.put_nowait(frame)
        except queue.Full:
            try:
                _ = frame_queue.get_nowait()
            except Exveption:
                pass
            try: 
                frame_queue.put_nowait(frame)
            except Exception:
                pass
    with worker_lock:
        af = annotated_frame
        ct = class_text
        pt = process_text
        
    if af is not None:
        af_rgb = cv2.cvtColor(af, cv2.COLOR_BGR2RGB)
        pil_im = Image.fromarray(af_rgb).resize((400, 300))
        imgtk = ImageTk.PhotoImage(pil_im)
        
        label_v.configure(image=imgtk)
        label_v.imgtk = imgtk
        
    label_result.config(text=ct)
    label_process.config(text=pt)
    
    label_v.after(30, update_camera)
	
#-------------------jalankan GUI------------------------------
graf_update()
update_camera()
root.protocol("WM_DELETE_WINDOW", lambda: (cap.release(), GPIO.cleanup(), root.destroy()))
root.mainloop()
