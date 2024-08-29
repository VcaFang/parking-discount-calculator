from flask import Flask, send_from_directory, jsonify, request
from Crypto.Cipher import DES
from Crypto.Util.Padding import unpad
import binascii
import requests
from datetime import datetime
import csv
import os
import json

app = Flask(__name__)

# DES 加解密設置
KEY = b"RAdWIMPs"  # 8 bytes key
IV = b"RAdWIMPs"   # 8 bytes IV

# 用於存儲已掃描發票的文件
SCANNED_INVOICES_FILE = 'scanned_invoices.json'

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
        fieldnames = ['掃描時間', '發票號碼', '發票日期', '消費金額', '可折抵停車時數', '是否為本日消費']
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
    try:
        if qr_data.startswith('YLC'):
            qr_data = qr_data[3:]
        
        decrypted_data = decrypt(qr_data)
        if not decrypted_data:
            return jsonify({'success': False, 'message': 'QR Code格式有誤,無法辨識'})

        parts = decrypted_data.strip('|').split('|')
        if len(parts) >= 5:
            amount = int(parts[3])
            invoice_number = parts[2]
            invoice_date = parts[4][:8]  # 只取日期部分 YYYYMMDD
            
            # 檢查發票是否已經掃描過
            if invoice_number in scanned_invoices:
                return jsonify({'success': False, 'message': '這張發票已經掃描過了，請勿重複折抵停車!'})
            
            # 獲取當前台北時間
            current_time = get_taipei_time()
            current_date = current_time.strftime("%Y%m%d")
            
            is_today = "Y" if invoice_date == current_date else "N"
            discount_hours = calculate_discount_hours(amount)
            
            # 準備 CSV 數據
            csv_data = {
                '掃描時間': current_time.strftime("%Y/%m/%d/%H/%M/%S GMT+8"),
                '發票號碼': invoice_number,
                '發票日期': invoice_date,
                '消費金額': amount,
                '可折抵停車時數': discount_hours,
                '是否為本日消費': is_today
            }
            
            # 寫入 CSV 文件
            append_to_csv(csv_data)
            
            # 將發票號碼添加到已掃描集合中
            scanned_invoices.add(invoice_number)
            save_scanned_invoices(scanned_invoices)
            
            return jsonify({
                'success': True, 
                'amount': amount, 
                'invoice_number': invoice_number,
                'invoice_date': invoice_date,
                'is_today': is_today,
                'discount_hours': discount_hours
            })
        else:
            return jsonify({'success': False, 'message': '無效的 QR Code數據格式'})
    except Exception as e:
        print(f"Error processing QR code: {str(e)}")
        return jsonify({'success': False, 'message': f'處理 QR 碼時出錯: {str(e)}'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')