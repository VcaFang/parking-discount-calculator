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
        allowedCodes: ['AB1234', 'AB1235', 'AB0000','AA0000','BB1234'], // 允許的代碼列表
        errorMessage: ''
    },
    mounted() {
        console.log('Vue 實例已掛載');
    },
    methods: {
        verifyCode() {
            if (this.allowedCodes.includes(this.userCode)) {
                this.isVerified = true; // 驗證通過，允許進入掃描頁面
                this.errorMessage = '';
            } else {
                this.errorMessage = '代碼驗證失敗，請重新輸入！';
            }
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
            fetch('/process_batch', {
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

        processQRCode(data) {
            console.log("Sending QR data to backend:", data);
        
            fetch('/process_qr', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ qr_data: data, batch_id: this.batchId })
            })
            .then(response => response.json())
            .then(result => {
                console.log("Received result from backend:", result);
        
                if (result.is_valid) {
                    this.scanResult = {
                        status: 'success',
                        message: result.message
                    };
                } else {
                    this.scanResult = {
                        status: 'error',
                        message: result.message
                    };
                }
        
                this.$forceUpdate();
            })
            .catch(error => {
                console.error('Error:', error);
                this.scanResult = {
                    status: 'error',
                    message: '處理 QR 碼時出錯，請重新掃描：' + error.message
                };
            });
        },
        selectVehicleType(type) {
            fetch('/complete_batch', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    batch_id: this.batchId,
                    vehicle_type: type
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
        },
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

            navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } })
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