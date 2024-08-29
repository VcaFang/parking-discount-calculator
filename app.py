from flask import Flask, render_template, jsonify, request
from Crypto.Cipher import DES
from Crypto.Util.Padding import unpad
import binascii
import requests
from datetime import datetime

app = Flask(__name__)

# DES 加解密設置
KEY = b"RAdWIMPs"  # 8 bytes key
IV = b"RAdWIMPs"   # 8 bytes IV

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
        response.raise_for_status()  # 如果請求失敗，這將引發異常
        taipei_time = response.text
        current_date = datetime.strptime(taipei_time, "%Y-%m-%d %H:%M:%S").strftime("%Y%m%d")
        return current_date
    except Exception as e:
        print(f"Error fetching Taipei time: {str(e)}")
        # 如果無法獲取台北時間，使用系統時間作為備選
        return datetime.now().strftime("%Y%m%d")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process_qr', methods=['POST'])
def process_qr():
    print("Received QR data:", request.json)
    qr_data = request.json['qr_data']
    try:
        if qr_data.startswith('YLC'):
            qr_data = qr_data[3:]
        
        decrypted_data = decrypt(qr_data)
        if not decrypted_data:
            return jsonify({'success': False, 'message': 'QR Code格式有誤,讀取失敗'})

        parts = decrypted_data.strip('|').split('|')
        if len(parts) >= 5:
            amount = int(parts[3])
            invoice_number = parts[2]
            invoice_date = parts[4][:8]  # 只取日期部分 YYYYMMDD
            
            # 獲取當前台北時間
            current_date = get_taipei_time()
            
            is_today = "Y" if invoice_date == current_date else "N"
            
            return jsonify({
                'success': True, 
                'amount': amount, 
                'invoice_number': invoice_number,
                'invoice_date': invoice_date,
                'is_today': is_today
            })
        else:
            return jsonify({'success': False, 'message': '無效的 QR 碼數據格式'})
    except Exception as e:
        print(f"Error processing QR code: {str(e)}")
        return jsonify({'success': False, 'message': f'處理 QR 碼時出錯: {str(e)}'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')