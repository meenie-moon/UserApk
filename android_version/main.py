import os
import json
import threading
import asyncio
from flask import Flask, render_template, request, jsonify
from telethon import TelegramClient
from kivy.app import App
from kivy.uix.modalview import ModalView
from kivy.clock import Clock

# --- Flask Backend ---
server = Flask(__name__)
DATA_DIR = ""

@server.route('/')
def index():
    return render_template('index.html')

@server.route('/api/get_data', methods=['POST', 'GET'])
def get_data():
    acc_path = os.path.join(DATA_DIR, "accounts.json")
    accounts = []
    if os.path.exists(acc_path):
        with open(acc_path, 'r') as f:
            accounts = json.load(f)
    return jsonify({"accounts": accounts, "status": "ok"})

@server.route('/api/broadcast', methods=['POST'])
def broadcast():
    data = request.json
    # Di sini kita akan memanggil fungsi Telethon
    # Untuk contoh ini kita kembalikan sukses dulu
    return jsonify({"status": f"Broadcast started for {data['acc']}"})

def run_server():
    server.run(host='127.0.0.1', port=5000)

# --- Kivy WebView Wrapper ---
# Kita gunakan Kivy hanya sebagai "bingkai" untuk membuka browser (WebView)
# Ini adalah metode paling stabil di Android

from kivy.uix.boxlayout import BoxLayout
from kivy.utils import platform

if platform == 'android':
    from jnius import autoclass
    from android.runnable import run_on_ui_thread
    WebView = autoclass('android.webkit.WebView')
    WebViewClient = autoclass('android.webkit.WebViewClient')
else:
    # Untuk testing di PC
    import webbrowser

class HybridApp(App):
    def build(self):
        self.data_dir = self.user_data_dir
        global DATA_DIR
        DATA_DIR = self.data_dir
        
        # Jalankan Flask di Thread terpisah
        threading.Thread(target=run_server, daemon=True).start()
        
        layout = BoxLayout()
        if platform == 'android':
            Clock.schedule_once(self.create_webview, 0)
        else:
            # Jika di PC, buka browser saja
            Clock.schedule_once(lambda dt: webbrowser.open('http://127.0.0.1:5000'), 2)
        
        return layout

    @run_on_ui_thread
    def create_webview(self, *args):
        activity = autoclass('org.kivy.android.PythonActivity').mActivity
        webview = WebView(activity)
        webview.getSettings().setJavaScriptEnabled(True)
        webview.getSettings().setDomStorageEnabled(True)
        webview.setWebViewClient(WebViewClient())
        activity.setContentView(webview)
        webview.loadUrl('http://127.0.0.1:5000')

if __name__ == '__main__':
    HybridApp().run()
