from flask import Flask, send_from_directory, jsonify, request
from Crypto.Cipher import DES
from Crypto.Util.Padding import unpad
import binascii
import requests
from datetime import datetime
import csv
import os
import json
import sqlite3

app = Flask(__name__)

# DES 加解密設置
KEY = b"RAdWIMPs"  # 8 bytes key
IV = b"RAdWIMPs"   # 8 bytes IV

# 用於存儲已掃描發票的文件
SCANNED_INVOICES_FILE = 'scanned_invoices.json'
DB_NAME = 'invoices.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    conn.execute('''CREATE TABLE IF NOT EXISTS invoice_scans
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  scan_time TEXT,
                  invoice_number TEXT UNIQUE,
                  invoice_date TEXT,
                  amount INTEGER,
                  discount_hours INTEGER,
                  is_same_day TEXT)''')
    conn.close()

def load_scanned_invoices():
    if os.path.exists(SCANNED_INVOICES_FILE):
        with open(SCANNED_INVOICES_FILE, 'r') as f:
            return set(json.load(f))
    return set()

def save_scanned_invoices(invoices):
    with open(SCANNED_INVOICES_FILE, 'w') as f:
        json.dump(list(invoices), f)

scanned_invoices = load_scanned_invoices()

def decrypt(text):
    try:
        cipher = DES.new(KEY, DES.MODE_CBC, IV)
        decrypted = cipher.decrypt(binascii.unhexlify(text))
        result = unpad(decrypted, DES.block_size).decode('utf-8')
        print("Decrypted data:", result)
        return result
    except Exception as e:
        print(f"Decryption error: {str(e)}")
        return None

def get_taipei_time():
    try:
        response = requests.get("https://tw.piliapp.com/time-now/tw/taipei/")
        response.raise_for_status()
        taipei_time = response.text
        return datetime.strptime(taipei_time, "%Y-%m-%d %H:%M:%S")
    except Exception as e:
        print(f"Error fetching Taipei time: {str(e)}")
        return datetime.now()

def calculate_discount_hours(amount):
    return min(amount // 1000, 4)

def append_to_csv(data):
    filename = 'invoice_records.csv'
    file_exists = os.path.isfile(filename)
    
    with open(filename, 'a', newline='') as csvfile:
        fieldnames = ['掃描時間', '發票號碼', '發票日期', '消費金額', '可折抵停車時數', '是否為本日消費', '備註']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        if not file_exists:
            writer.writeheader()
        
        writer.writerow(data)

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/process_qr', methods=['POST'])
def process_qr():
    global scanned_invoices
    print("Received QR data:", request.json)
    qr_data = request.json['qr_data']
    current_time = get_taipei_time()
    
    try:
        if qr_data.startswith('YLC'):
            qr_data = qr_data[3:]
        
        decrypted_data = decrypt(qr_data)
        if not decrypted_data:
            csv_data = {
                '掃描時間': current_time.strftime("%Y/%m/%d/%H/%M/%S GMT+8"),
                '發票號碼': 'N/A',
                '發票日期': 'N/A',
                '消費金額': 0,
                '可折抵停車時數': 0,
                '是否為本日消費': 'N',
                '備註': 'QR Code格式有誤，無法辨識'
            }
            append_to_csv(csv_data)
            return jsonify({
                'success': False, 
                'message': 'QR Code格式有誤，無法辨識', 
                'remark': 'QR Code格式有誤，無法辨識',
                'clear_fields': True
            })

        parts = decrypted_data.strip('|').split('|')
        if len(parts) >= 5:
            amount = int(parts[3])
            invoice_number = parts[2]
            invoice_date = parts[4][:8]  # 只取日期部分 YYYYMMDD
            
            # 檢查發票是否已經掃描過（使用 SQLite）
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM invoice_scans WHERE invoice_number = ?", (invoice_number,))
            is_duplicate = cursor.fetchone() is not None or invoice_number in scanned_invoices
            
            current_date = current_time.strftime("%Y%m%d")
            is_today = "Y" if invoice_date == current_date else "N"
            discount_hours = calculate_discount_hours(amount)
            
            if is_duplicate:
                remark = '本發票今日已掃描過，勿重複折抵'
                success = False
                message = '這張發票已經掃描過了，請勿重複折抵停車!'
            else:
                remark = '掃描成功'
                success = True
                message = f'成功掃描發票！金額: {amount}元'
                
                # 將發票號碼添加到已掃描集合中
                scanned_invoices.add(invoice_number)
                save_scanned_invoices(scanned_invoices)
                
                # 插入數據到 SQLite 數據庫
                cursor.execute('''INSERT OR IGNORE INTO invoice_scans 
                                  (scan_time, invoice_number, invoice_date, amount, discount_hours, is_same_day) 
                                  VALUES (?, ?, ?, ?, ?, ?)''', 
                               (current_time.strftime("%Y/%m/%d/%H/%M/%S GMT+8"), 
                                invoice_number, invoice_date, amount, discount_hours, is_today))
                conn.commit()

            csv_data = {
                '掃描時間': current_time.strftime("%Y/%m/%d/%H/%M/%S GMT+8"),
                '發票號碼': invoice_number,
                '發票日期': invoice_date,
                '消費金額': amount,
                '可折抵停車時數': discount_hours,
                '是否為本日消費': is_today,
                '備註': remark
            }
            
            # 寫入 CSV 文件
            append_to_csv(csv_data)
            
            conn.close()
            
            return jsonify({
                'success': success, 
                'amount': amount, 
                'invoice_number': invoice_number,
                'invoice_date': invoice_date,
                'is_today': is_today,
                'discount_hours': discount_hours,
                'remark': remark,
                'message': message
            })
        else:
            csv_data = {
                '掃描時間': current_time.strftime("%Y/%m/%d/%H/%M/%S GMT+8"),
                '發票號碼': 'N/A',
                '發票日期': 'N/A',
                '消費金額': 0,
                '可折抵停車時數': 0,
                '是否為本日消費': 'N',
                '備註': 'QR Code格式有誤，無法辨識'
            }
            append_to_csv(csv_data)
            return jsonify({
                'success': False, 
                'message': '無效的 QR Code數據格式', 
                'remark': 'QR Code格式有誤，無法辨識',
                'clear_fields': True
            })
    except Exception as e:
        print(f"Error processing QR code: {str(e)}")
        csv_data = {
            '掃描時間': current_time.strftime("%Y/%m/%d/%H/%M/%S GMT+8"),
            '發票號碼': 'N/A',
            '發票日期': 'N/A',
            '消費金額': 0,
            '可折抵停車時數': 0,
            '是否為本日消費': 'N',
            '備註': 'QR Code格式有誤，無法辨識'
        }
        append_to_csv(csv_data)
        return jsonify({
            'success': False, 
            'message': f'處理 QR 碼時出錯: {str(e)}', 
            'remark': 'QR Code格式有誤，無法辨識',
            'clear_fields': True
        })

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0')