from flask import Flask, send_from_directory, jsonify, request
from Crypto.Cipher import DES
from Crypto.Util.Padding import unpad
from collections import defaultdict
import binascii
import requests
import csv
import os
import json
import sqlite3
from datetime import datetime, timedelta, timezone
import msvcrt  # 用於 Windows 文件鎖定

app = Flask(__name__, static_url_path='/static', static_folder='static')
# DES 加解密設置
KEY = b"RAdWIMPs"  # 8 bytes key
IV = b"RAdWIMPs"   # 8 bytes IV

DB_NAME = 'invoices.db'

# 全局變量，用於存儲每個批次的發票
batch_invoices = defaultdict(set)

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
    conn.execute('''CREATE TABLE IF NOT EXISTS batches
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  batch_id TEXT UNIQUE,
                  start_time TEXT,
                  status TEXT)''')
    conn.close()

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

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
    conn = get_db_connection()
    try:
        conn.execute("INSERT INTO batches (batch_id, start_time, status) VALUES (?, ?, ?)",
                     (batch_id, datetime.now().isoformat(), 'started'))
        conn.commit()
        batch_invoices[batch_id] = set()  # 初始化該批次的發票集合
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return jsonify({'error': 'Failed to start batch'}), 500
    finally:
        conn.close()
    return jsonify({'batch_id': batch_id})

@app.route('/process_qr', methods=['POST'])
def process_qr():
    qr_data = request.json['qr_data']
    batch_id = request.json['batch_id']
    return jsonify(process_single_qr(qr_data, batch_id))

def process_single_qr(qr_data, batch_id):
    try:
        current_time = get_taipei_time()
        current_date = current_time.strftime("%Y%m%d")

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

        # 檢查1: 批次內重複檢查
        if invoice_number in batch_invoices[batch_id]:
            return {
                'is_valid': False,
                'message': '此發票在本批次中已經掃描過了',
                'remark': '批次內重複掃描'
            }

        # 檢查2: 數據庫重複檢查
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT invoice_number FROM invoice_scans WHERE invoice_number = ? AND invoice_date = ?",
                       (invoice_number, invoice_date))
        if cursor.fetchone():
            conn.close()
            return {
                'is_valid': False,
                'message': '這張發票已經掃描過了，請勿重複折抵停車!',
                'remark': '本發票今日已掃描過，勿重複折抵'
            }

        # 如果通過了所有檢查，將發票號碼添加到當前批次的集合中
        batch_invoices[batch_id].add(invoice_number)

        # 同時，我們可以在另一個字典中存儲完整的發票信息
        if 'invoice_data' not in batch_invoices:
            batch_invoices['invoice_data'] = {}
        batch_invoices['invoice_data'][invoice_number] = {
            'invoice_date': invoice_date,
            'amount': amount,
            'store_id': parts[5] if len(parts) > 5 else 'N/A',
            'crm_id': parts[6] if len(parts) > 6 else 'N/A'
        }

        conn.close()
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
    
    if batch_id not in batch_invoices or 'invoice_data' not in batch_invoices:
        return jsonify({'error': 'Invalid batch ID or no invoice data'}), 400

    invoices = [batch_invoices['invoice_data'][inv_num] for inv_num in batch_invoices[batch_id]]
    
    total_amount = sum(invoice['amount'] for invoice in invoices)
    total_discount_hours = min(total_amount // 1000, 4)
    valid_invoices = len(invoices)
    motorcycle_count = min(total_amount // 200, 10)

    response_data = {
        'results': invoices,
        'total_amount': total_amount,
        'total_discount_hours': total_discount_hours,
        'valid_invoices': valid_invoices,
        'motorcycle_count': motorcycle_count,
        'batch_id': batch_id
    }

    conn = get_db_connection()
    try:
        # 更新批次狀態
        conn.execute("UPDATE batches SET status = ? WHERE batch_id = ?", ('processed', batch_id))
        conn.commit()
    except Exception as e:
        print(f"Error updating batch status: {str(e)}")
    finally:
        conn.close()

    return jsonify(response_data)

# 新增取消批次的路由
@app.route('/cancel_batch', methods=['POST'])
def cancel_batch():
    data = request.get_json()
    batch_id = data.get('batch_id')

    try:
        # 這裡需要根據你的邏輯來處理批次取消
        # 例如，將該批次從數據庫中移除，或標記為「未處理」
        # 若用到了CSV文件，可以選擇不寫入該批次數據

        # 假設你有一個函數可以處理批次刪除/取消
        cancel_batch_in_database(batch_id)
        
        return jsonify({"message": "Batch canceled successfully"}), 200
    except Exception as e:
        print(f"Error canceling batch: {e}")
        return jsonify({"error": "Failed to cancel batch"}), 500

# 假設的取消批次函數
def cancel_batch_in_database(batch_id):
    # 這裡添加你的邏輯來處理數據庫或CSV的數據取消
    # 比如可以從數據庫中刪除該批次記錄
    pass

@app.route('/complete_batch', methods=['POST'])
def complete_batch():
    batch_id = request.json['batch_id']
    vehicle_type = request.json['vehicle_type']
    
    if batch_id not in batch_invoices or 'invoice_data' not in batch_invoices:
        return jsonify({'error': 'Invalid batch ID or no invoice data'}), 400

    conn = get_db_connection()
    try:
        conn.execute("BEGIN TRANSACTION")
        
        # 獲取批次中的所有發票
        invoice_numbers = batch_invoices[batch_id]
        
        for invoice_number in invoice_numbers:
            invoice_data = batch_invoices['invoice_data'][invoice_number]
            conn.execute('''INSERT INTO invoice_scans 
                            (batch_id, scan_time, invoice_number, invoice_date, amount, is_same_day, store_id, crm_id, vehicle_type)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                         (batch_id, datetime.now().isoformat(), invoice_number, invoice_data['invoice_date'], 
                          invoice_data['amount'], 'Y', invoice_data['store_id'], invoice_data['crm_id'], vehicle_type))
        
        # 更新批次狀態
        conn.execute("UPDATE batches SET status = ? WHERE batch_id = ?", ('completed', batch_id))
        
        conn.commit()
        
        # 獲取更新後的發票記錄用於CSV寫入
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM invoice_scans WHERE batch_id = ?", (batch_id,))
        results = cursor.fetchall()

        # 寫入 CSV
        write_to_csv([dict(row) for row in results])
        
        # 清理批次數據
        del batch_invoices[batch_id]
        del batch_invoices['invoice_data']
        
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        print(f"Error completing batch: {str(e)}")
        return jsonify({'error': f'Failed to complete batch: {str(e)}'}), 500
    finally:
        conn.close()

def write_to_csv(results):
    filename = 'invoice_records.csv'
    fieldnames = ['掃描批次編號', '掃描時間', '發票號碼', '發票日期', '消費金額', '店家編號', 'CRM專櫃編號', '本次折抵車輛類型', 'Remark']
    
    with open(filename, 'a', newline='') as csvfile:
        try:
            msvcrt.locking(csvfile.fileno(), msvcrt.LK_LOCK, 1)  # 鎖定文件
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            if csvfile.tell() == 0:
                writer.writeheader()
            for result in results:
                writer.writerow({
                    '掃描批次編號': result['batch_id'],
                    '掃描時間': result['scan_time'],
                    '發票號碼': result['invoice_number'],
                    '發票日期': result['invoice_date'],
                    '消費金額': result['amount'],
                    '店家編號': result['store_id'],
                    'CRM專櫃編號': result['crm_id'],
                    '本次折抵車輛類型': result['vehicle_type'],
                    'Remark': ''
                })
        finally:
            msvcrt.locking(csvfile.fileno(), msvcrt.LK_UNLCK, 1)  # 解鎖文件

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)