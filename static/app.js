new Vue({
    el: '#app',
    delimiters: ['[[', ']]'],
    data: {
        video: null,
        canvas: null,
        context: null,
        scanning: false,
        batchScanning: false,
        batchCompleted: false,
        totalAmount: 0,
        discountHours: 0,
        validInvoices: 0,
        motorcycleCount: 0,
        scannedInvoices: new Set(),
        lastInvoiceNumber: '',
        lastInvoiceDate: '',
        isCurrentDate: '',
        message: '',
        scanResult: {
            status: '',
            message: ''
        },
        remark: '',
        batchId: null,
        batchResults: [],
        isVerified: false,
        userCode: '',
        errorMessage: ''
    },
    mounted() {
        console.log('Vue 實例已掛載');
    },
    methods: {
        verifyCode() {
            // 發送用戶輸入的代碼到後端進行驗證
            fetch('/verify_code', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ user_code: this.userCode })
            })
            .then(response => response.json())
            .then(result => {
                if (result.is_valid) {
                    this.isVerified = true; // 後端驗證通過，允許進入掃描頁面
                    this.errorMessage = '';
                } else {
                    this.errorMessage = '代碼驗證失敗，請重新輸入！';
                }
            })
            .catch(error => {
                console.error('驗證代碼時出錯:', error);
                this.errorMessage = '驗證代碼時出錯，請稍後再試。';
            });
        },
        // 在大約第300行之後添加
uploadImage(event) {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);
    formData.append('batch_id', this.batchId);

    fetch('/upload_image', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(result => {
        this.processQRResult(result);
    })
    .catch(error => {
        console.error('Error:', error);
        this.scanResult = {
            status: 'error',
            message: '處理圖片時出錯，請重試：' + error.message
        };
    });
},
        startBatchScan() {
            this.batchScanning = true;
            this.batchCompleted = false; // 確保在開始掃碼時 batchCompleted 為 false
            this.batchResults = [];
            this.resetCalculator();
            fetch('/start_batch', {
                method: 'POST'
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                this.batchId = data.batch_id;
                this.startScanner();
            })
            .catch(error => {
                console.error('開啟掃描時出錯:', error);
                this.message = '開啟掃描時出錯，請稍後再試。';
            });
        },
        initializeAllScanningMethods() {
            this.initializeBarcodeScanning();
            // 初始化其他掃描方法...
        },
        
        initializeBarcodeScanning() {
            // 重新绑定条码扫描事件
            document.removeEventListener('keypress', this.handleBarcodeInput);
            document.addEventListener('keypress', this.handleBarcodeInput);
        },
        stopBatchScan() {
            this.batchScanning = false;
            this.stopScanner();
        },
        continueScan() {
            this.startScanner();
        },
        completeBatch() {
            this.stopScanner();
            console.log('Current batch ID before sending to server:', this.batchId);
            console.log('User Code before sending to server:', this.userCode);  // 確認 user_code 的值
        
            fetch('/process_batch', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    batch_id: this.batchId,
                    user_code: this.userCode  // 傳遞用戶的通行代碼
                })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                console.log('Received response from server', response);
                return response.json();
            })
            .then(result => {
                console.log('Batch processing completed:', result);
                this.totalAmount = result.total_amount;
                this.discountHours = result.total_discount_hours;
                this.validInvoices = result.valid_invoices;
                this.motorcycleCount = result.motorcycle_count;
                this.batchCompleted = true;
        
                console.log('Updated data:', {
                    totalAmount: this.totalAmount,
                    discountHours: this.discountHours,
                    validInvoices: this.validInvoices,
                    motorcycleCount: this.motorcycleCount
                });
        
                this.$forceUpdate();
            })
            .catch(error => {
                console.error('處理批次掃描時出錯:', error);
                this.message = '處理批次掃描時出錯，請稍後再試。';
            });
        },
        
        resetBatch() {
            // 重置批次相關的數據
            this.batchId = null;
            this.totalAmount = 0;
            this.discountHours = 0;
            this.validInvoices = 0;
            this.motorcycleCount = 0;
            this.batchCompleted = false;
            this.batchScanning = false;
            // 可能需要調用後端的某個 API 來重置服務器端的批次狀態
            // 例如：
            // fetch('/reset_batch', { method: 'POST' })
            //     .then(() => console.log('Batch reset on server'))
            //     .catch(error => console.error('Error resetting batch:', error));
        },

// 修改大約第140行的processQRCode方法
processQRCode(data, inputType = 'qr') {
    console.log("Sending data to backend:", data);

    fetch('/process_qr', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
            qr_data: data, 
            batch_id: this.batchId,
            input_type: inputType
        })
    })
    .then(response => response.json())
    .then(result => {
        this.processQRResult(result);
    })
    .catch(error => {
        console.error('Error:', error);
        this.scanResult = {
            status: 'error',
            message: '處理數據時出錯，請重試：' + error.message
        };
    });
},

processQRResult(result) {
    console.log("Received result from backend:", result);

    if (result.is_valid) {
        this.scanResult = {
            status: 'success',
            message: result.message
        };
        // 可以在這裡添加發票到本地列表的邏輯
        // this.batchResults.push(result);
    } else {
        this.scanResult = {
            status: 'error',
            message: result.message
        };
    }

    this.$forceUpdate();
},
        selectVehicleType(type) {
            if (type === 'cancel') {
                // 調用後端來取消批次寫入
                fetch('/cancel_batch', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        batch_id: this.batchId
                    })
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(() => {
                    // 重置計算器，回到掃描頁面
                    this.resetCalculator();
                    this.batchCompleted = false;
                    this.batchScanning = false;
                    console.log('Batch canceled successfully');
                    this.message = '批次已取消，未進行任何折抵。';
                })
                .catch(error => {
                    console.error('取消批次時出錯:', error);
                    this.message = '取消批次時出錯，請稍後再試。';
                });
            } else {
                // 其他車輛類型處理邏輯
                fetch('/complete_batch', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        batch_id: this.batchId,
                        vehicle_type: type,
                        user_code: this.userCode  
                    })
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(() => {
                    this.resetCalculator();
                    this.batchCompleted = false;
                    this.batchScanning = false;
                    console.log('Batch completed successfully with vehicle type:', type);
                    this.message = '批次處理完成，車輛類型已更新。';
                })
                .catch(error => {
                    console.error('完成批次掃描時出錯:', error);
                    this.message = '完成批次掃描時出錯，請稍後再試。';
                });
            }
        },
// 修改大約第200行的startScanner方法
startScanner() {
    console.log("嘗試啟動相機");
    this.video = document.getElementById('video');
    this.canvas = document.getElementById('canvas');
    if (!this.video || !this.canvas) {
        console.error("無法找到視頻或畫布元素");
        this.message = "無法找到視頻或畫布元素，請確保頁面正確加載。";
        return;
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        console.error("瀏覽器不支持 getUserMedia");
        this.message = "您的瀏覽器不支持相機功能，請嘗試使用其他瀏覽器。";
        return;
    }
    this.context = this.canvas.getContext('2d');

    navigator.mediaDevices.getUserMedia({ 
        video: { 
            facingMode: "environment",
            advanced: [{focusMode: "continuous"}]
        } 
    })
    .then((stream) => {
        this.video.srcObject = stream;
        this.video.setAttribute('playsinline', true);
        this.video.play();
        this.scanning = true;
        requestAnimationFrame(this.scan);
        this.video.style.display = 'block';
    })
    .catch((error) => {
        console.error("無法啟動相機:", error);
        this.message = "無法啟動相機，請確保您已授予相機權限。";
    });
},
// 在大約第350行之後添加
handleBarcodeInput(event) {
    console.log("event.key = " + event.key);
    console.log("this.barcodeInput = " + this.barcodeInput);
    if (event.key === 'Enter') {
        if (!this.batchId) {
            console.error("No active batch");
            this.message = "請先開始新的批次掃描";
            return;
        }
        // 處理完整的條碼
        
        this.processQRCode(this.barcodeInput, 'barcode');
        this.barcodeInput = '';  // 重置輸入

    } else {
        // 累積輸入
        this.barcodeInput += event.key;
    }
},
        stopScanner() {
            this.scanning = false;
            if (this.video && this.video.srcObject) {
                this.video.srcObject.getTracks().forEach(track => track.stop());
            }
            if (this.video) {
                this.video.style.display = 'none';
            }
        },
        scan() {
            if (this.video && this.video.readyState === this.video.HAVE_ENOUGH_DATA) {
                this.context.drawImage(this.video, 0, 0, this.canvas.width, this.canvas.height);
                const imageData = this.context.getImageData(0, 0, this.canvas.width, this.canvas.height);
                if (typeof jsQR === 'function') {
                    const code = jsQR(imageData.data, imageData.width, imageData.height, {
                        inversionAttempts: "dontInvert",
                    });

                    if (code) {
                        this.processQRCode(code.data);
                        this.stopScanner();
                    }
                } else {
                    console.error('jsQR 函數未定義，請確保已正確載入 jsQR 庫');
                    this.message = 'QR 掃描功能未正確載入，請刷新頁面重試。';
                    this.stopScanner();
                }
            }
            if (this.scanning) {
                requestAnimationFrame(this.scan);
            }
        },
        
    // 重置計算器的方法
    resetCalculator() {
        this.totalAmount = 0;
        this.discountHours = 0;
        this.validInvoices = 0;
        this.motorcycleCount = 0;
        this.scannedInvoices.clear();
        this.lastInvoiceNumber = '';
        this.lastInvoiceDate = '';
        this.isCurrentDate = '';
        this.message = '';
        this.scanResult = { status: '', message: '' };
        this.remark = '';
    }
}
});