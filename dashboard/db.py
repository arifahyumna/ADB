#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import tkinter as tk
import random
import paho.mqtt.client as mqtt
import datetime as dt
import matplotlib.pyplot as plt
import matplotlib.animation as anm
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from detect import run


# In[ ]:


#konfigurasi MQTT
MQTT_BROKER = "192.168.1.100" 
MQTT_PORT = 1883
MQTT_TOPICS = [("press/temp", 0), ("press/alert", 0), ("sensor/daya", 0)]


# In[ ]:


#variabel global
suhu_update = None
xs = []
ys = []
SSR_PIN = 17

#update daya
'''def daya_pencacah():
    daya1 = round(random.uniform(100, 240), 2)
    label_unitd1.config(text=f"{daya1} Watt")
    root.after(5000, daya_pencacah)

def daya_pencetak():
    daya2 = round(random.uniform(100, 300), 2)
    label_unitd2.config(text=f"{daya2} Watt")
    root.after(5000, daya_pencetak)

def suhu_pencetak():
    suhu = round(random.uniform(28, 220), 2)
    label_units.config(text=f"{suhu} ℃")
    root.after(5000, suhu_pencetak)'''

def klasifikasi ():
    try:
        hasilYolo = run(
            weight="best.pt",
            source="test.jpg",
            save_csv=False,
            save_img=False,
            nosave=True
        )

        if hasilYolo and len(hasilYolo) > 0:
            hasil = hasilYolo[0]["label"]
        else:
            hasil = "unknown"

        label_result.config(text=f"{hasil}")

        if hasil == "plastic":
            GPIO.output(SSR_PIN, GPIO.HIGH)
            print("SSR ON - plastik terdeteksi")
            label_process.config(text="SHREDDER ON")
        elif hasil == "nonplastic":
            GPIO.output(SSR_PIN, GPIO.LOW)
            print("SSR OFF - non plastik terdeteksi")
            label_process.config(text="SHREDDER OFF")
        else:
            GPIO.output(SSR_PIN, GPIO.LOW)
            print("SSR OFF - tangan terdeteksi")
            label_process.config(text="SHREDDER OFF")
    except:
        label_result.config(text="--")
        GPIO.output(SSR_PIN, GPIO.LOW)
    root.after(5000, klasifikasi)
    
#---------------------MQTT-----------------------
def on_connect(client, userdata, flags, rc):
    print("Connected")
    client.subscribe(MQTT_TOPICS)

def on_message(client, userdata, msg):
    topic = msg.topic
    payload = msg.payload.decode()

    if topic == "press/temp":
        try:
            suhu_val = float(payload)
            suhu_update = suhu_val
            label_units.config(text=f"{suhu_val: .2f} ℃")
        except:
            label_units.config(text=f"Error: {payload}")

    elif topic == "sensor/daya":
        try:
            daya_val = float(payload)
            label_unitd2.config(text=f"{daya_val} Watt")
        except:
            label_unitd2.config(text=f"Error: {payload}")

    elif topic == "press/alert":
        label_alert.config("ALERT")


# In[ ]:


#main window
root = tk.Tk()
root.title("Smart Monitoring Machine")

#create frame
frame_1 = tk.Frame(root, relief="groove", borderwidth=2)
frame_2 = tk.Frame(root, relief="groove", borderwidth=2)

frame_1.pack(side="left", fill=tk.BOTH, expand=True, padx=10, pady=10)
frame_2.pack(side="right", fill=tk.BOTH, expand=True, padx=10, pady=10)

#--------------------------
#create widgets "Pencacah"
#--------------------------

#Title
label_p1 = tk.Label(frame_1, text="PENCACAH", font=("Segoe UI", 12, "bold"))
label_p1.pack(pady=5)

#power
frame_daya1 = tk.Frame(frame_1)
label_daya1 = tk.Label(frame_daya1, text="Daya")
label_unitd1 = tk.Label(frame_daya1, text="0 Watt", relief="ridge", width=10)

label_daya1.pack(side="left", padx=5)
label_unitd1.pack(side="left", padx=5)
frame_daya1.pack(pady=5)

#vision
frame_vision = tk.Frame(frame_1, bg="gray", width=300, height=200)
label_v = tk.Label(frame_vision, text="Kamera")

frame_vision.pack(pady=5)
frame_vision.pack_propagate(False)
label_v.pack(expand=True)

#klasifikasi
frame_klas = tk.Frame(frame_1)
label_klas = tk.Label(frame_klas, text="Klasifikasi:")
label_result = tk.Label(frame_klas, text="--", relief="ridge", width=10)

frame_klas.pack(pady=10)
label_klas.pack(side="left", padx=5)
label_result.pack(side="left", padx=5)

#--------------------------
#create widgets "Pencetak"
#--------------------------

#Title
label_p2 = tk.Label(frame_2, text="PENCETAK", font=("Segoe UI", 12, "bold"))
label_p2.pack(pady=5)

#power
frame_daya2 = tk.Frame(frame_2)
label_daya2 = tk.Label(frame_daya2, text="Daya:")
label_unitd2 = tk.Label(frame_daya2, text="0 Watt", relief="ridge", width=10)

frame_daya2.pack(pady=5)
label_daya2.pack(side="left", padx=5)
label_unitd2.pack(side="left", padx=5)

#grafik suhu
frame_grafik = tk.Frame(frame_2, bg="gray", width=300, height=300)
label_graf = tk.Label(frame_grafik, text="Grafik Suhu")

frame_grafik.pack(pady=5)
frame_grafik.pack_propagate(False)
label_graf.pack(expand=True)

#suhu
frame_suhu = tk.Frame(frame_2)
label_suhu = tk.Label(frame_suhu, text="Suhu:")
label_units = tk.Label(frame_suhu, text="0 ℃", relief="ridge", width=10)

frame_suhu.pack(pady=10)
label_suhu.pack(side="left", padx=5)
label_units.pack(side="left", padx=5)

#alert
frame_alert = tk.Frame(frame_2)
label_alert = tk.Label(frame_alert, text="--", relief="ridge", width=40)

frame_alert.pack(pady=15)
label_alert.pack(side="left")


# In[ ]:


#setup grafik
fig, ax = plt.subplots(figsize=(4, 3))
canvas = FigureCanvasTkAgg(fig, master=frame_grafik)
canvas_widget = canvas.get_tk_widget()
canvas_widget.pack(pady=5)

ax.set_title("Monitoring Suhu Pencetak", fontsize=10, pad=10)
ax.set_xlabel("Waktu", fontsize=5)
ax.set_ylabel("Suhu (°C)", fontsize=5)
ax.grid(True, linestyle="--", alpha=0.6)
        
def update_plot(suhu_update):
    xs.append(dt.datetime.now().strftime('%H:%M:%S'))
    ys.append(suhu_update)

    del xs[:-10]
    del ys[:-10]

    if len(xs) != len(ys):
        min_len = min(len(xs), len(ys))
        xs[:] = xs[:min_len]
        ys[:] = ys[:min_len]

    ax.clear()
    ax.plot(xs, ys, marker='o', color='tab:blue')
    ax.set_title("Monitoring Suhu Press Heater")
    ax.set_xlabel("Waktu")
    ax.set_ylabel("Suhu (°C)")
    ax.grid(True)
    plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
    fig.tight_layout()
    canvas.draw()

'''def dummy_update():
    suhu = round(random.uniform(20, 80), 2)  
    update_plot(suhu)                        
    label_units.config(text=f"{suhu} °C")   
    root.after(5000, dummy_update) '''   


# In[ ]:


#MQTT setup
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

try:
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()
except Exception as e:
    print("MQTT connection failed:", e)


# In[ ]:


#menjalankan semua loop
'''dummy_update()
daya_pencacah()
daya_pencetak()'''
root.mainloop()

