from flask import Flask, send_from_directory, jsonify, request
from Crypto.Cipher import DES
from Crypto.Util.Padding import unpad
import binascii
import requests
import csv
import os
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from collections import OrderedDict

app = Flask(__name__, static_url_path='/static', static_folder='static')
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
                  batch_id TEXT,
                  scan_time TEXT,
                  invoice_number TEXT UNIQUE,
                  invoice_date TEXT,
                  amount INTEGER,
                  is_same_day TEXT,
                  store_id TEXT,
                  crm_id TEXT,
                  vehicle_type TEXT)''')
    conn.close()

# 全局變量用於存儲批次結果
batch_results = {}
batch_invoices = {}  # 新增：用於存儲每個批次的發票

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
    return datetime.now(timezone(timedelta(hours=8)))

@app.route('/')
def index():
    return send_from_directory('.', 'main.html')

@app.route('/start_batch', methods=['POST'])
def start_batch():
    batch_id = datetime.now().strftime("%Y%m%d%H%M%S")
    batch_results[batch_id] = []
    batch_invoices[batch_id] = OrderedDict()  # 使用 OrderedDict 來保持插入順序
    print(f"Starting new batch: {batch_id}")
    return jsonify({'batch_id': batch_id})

@app.route('/process_qr', methods=['POST'])
def process_qr():
    qr_data = request.json['qr_data']
    batch_id = request.json['batch_id']
    return jsonify(process_single_qr(qr_data, batch_id))

def process_single_qr(qr_data, batch_id):
    current_time = get_taipei_time()
    current_date = current_time.strftime("%Y%m%d")

    try:
        if qr_data.startswith('YLC'):
            qr_data = qr_data[3:]
        
        decrypted_data = decrypt(qr_data)
        if not decrypted_data:
            return {
                'is_valid': False,
                'message': 'QR Code格式有誤，非商場QR碼',
                'remark': 'QR Code格式有誤，無法辨識'
            }

        parts = decrypted_data.strip('|').split('|')
        if len(parts) < 5:
            return {
                'is_valid': False,
                'message': 'QR Code格式有誤，非商場QR碼',
                'remark': 'QR Code格式有誤，無法辨識'
            }

        amount = int(parts[3])
        invoice_number = parts[2]
        invoice_date = parts[4][:8]  # 只取日期部分 YYYYMMDD
        
        is_today = invoice_date == current_date

        if not is_today:
            return {
                'is_valid': False,
                'message': '非本日消費，不予計算',
                'remark': '非本日消費，不予計算'
            }

        if invoice_number in batch_invoices[batch_id]:
            return {
                'is_valid': False,
                'message': '此發票在本批次中已經掃描過了',
                'remark': '批次內重複掃描'
            }

        # 檢查資料庫內是否已經存在該發票
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT invoice_number FROM invoice_scans WHERE invoice_number = ? AND invoice_date = ?", (invoice_number, invoice_date))
        db_result = cursor.fetchone()
        conn.close()

        if db_result:
            print(f"Invoice {invoice_number} already exists in database.")
            return {
                'is_valid': False,
                'message': '這張發票已經掃描過了，請勿重複折抵停車!',
                'remark': '本發票今日已掃描過，勿重複折抵'
            }

        invoice_data = {
            '掃描批次編號': batch_id,
            '掃描時間': current_time.strftime("%Y/%m/%d/%H:%M:%S GMT+8"),
            '發票號碼': invoice_number,
            '發票日期': invoice_date,
            '消費金額': amount,
            '店家編號': parts[5] if len(parts) > 5 else 'N/A',
            'CRM專櫃編號': parts[6] if len(parts) > 6 else 'N/A',
            '本次折抵車輛類型': '',
            'Remark': ''
        }
        batch_results[batch_id].append(invoice_data)
        batch_invoices[batch_id][invoice_number] = invoice_data

        return {
            'is_valid': True,
            'amount': amount,
            'invoice_number': invoice_number,
            'invoice_date': invoice_date,
            'message': f'本次有效消費金額為{amount}元'
        }
    except Exception as e:
        print(f"Error processing QR code: {str(e)}")
        return {
            'is_valid': False,
            'message': f'處理 QR 碼時出錯: {str(e)}',
            'remark': 'QR Code格式有誤，無法辨識'
        }

@app.route('/process_batch', methods=['POST'])
def process_batch():
    batch_id = request.json['batch_id']
    if batch_id not in batch_invoices:
        return jsonify({'error': 'Invalid batch ID'}), 400

    results = list(batch_invoices[batch_id].values())
    total_amount = sum(result['消費金額'] for result in results)
    total_discount_hours = min(total_amount // 1000, 4)
    valid_invoices = len(results)
    
    # 计算可折抵机车停车台数
    motorcycle_count = min(total_amount // 200, 10)

    response_data = {
        'results': results,
        'total_amount': total_amount,
        'total_discount_hours': total_discount_hours,
        'valid_invoices': valid_invoices,
        'motorcycle_count': motorcycle_count,
        'batch_id': batch_id
    }

    print(f"批次處理結果: {response_data}")
    return jsonify(response_data)

@app.route('/complete_batch', methods=['POST'])
def complete_batch():
    batch_id = request.json['batch_id']
    vehicle_type = request.json['vehicle_type']
    
    if batch_id not in batch_invoices:
        return jsonify({'error': 'Invalid batch ID'}), 400

    # 更新批次結果中的車輛類型
    for invoice in batch_invoices[batch_id].values():
        invoice['本次折抵車輛類型'] = vehicle_type

    # 寫入CSV
    write_to_csv(batch_invoices[batch_id].values())

    # 更新數據庫
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    for invoice in batch_invoices[batch_id].values():
        cursor.execute('''INSERT OR REPLACE INTO invoice_scans 
                          (batch_id, scan_time, invoice_number, invoice_date, amount, is_same_day, store_id, crm_id, vehicle_type) 
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                       (batch_id, invoice['掃描時間'], invoice['發票號碼'], invoice['發票日期'], 
                        invoice['消費金額'], 'Y', 
                        invoice['店家編號'], invoice['CRM專櫃編號'], vehicle_type))
    conn.commit()
    conn.close()

    # 清理批次結果
    del batch_results[batch_id]
    del batch_invoices[batch_id]
    
    print(f"完成批次: {batch_id}, 車輛類型: {vehicle_type}")
    return jsonify({'success': True})

def write_to_csv(results):
    filename = 'invoice_records.csv'
    file_exists = os.path.isfile(filename)
    
    with open(filename, 'a', newline='') as csvfile:
        fieldnames = ['掃描批次編號', '掃描時間', '發票號碼', '發票日期', '消費金額', '店家編號', 'CRM專櫃編號', '本次折抵車輛類型', 'Remark']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        if not file_exists:
            writer.writeheader()
        
        for result in results:
            writer.writerow(result)

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)