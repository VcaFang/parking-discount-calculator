new Vue({
    el: '#app',
    delimiters: ['[[', ']]'],
    data: {
        video: null,
        canvas: null,
        context: null,
        scanning: false,
        totalAmount: 0,
        discountHours: 0,
        scannedInvoices: new Set(),
        lastInvoiceNumber: '',
        lastInvoiceDate: '',
        isCurrentDate: '',
        message: '',
        scanResult: {
            status: '',
            message: ''
        },
        remark: ''
    },
    methods: {
        startScanner() {
            this.video = document.getElementById('video');
            this.canvas = document.getElementById('canvas');
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
            this.video.style.display = 'none';
        },
        scan() {
            if (this.video.readyState === this.video.HAVE_ENOUGH_DATA) {
                this.context.drawImage(this.video, 0, 0, this.canvas.width, this.canvas.height);
                const imageData = this.context.getImageData(0, 0, this.canvas.width, this.canvas.height);
                const code = jsQR(imageData.data, imageData.width, imageData.height, {
                    inversionAttempts: "dontInvert",
                });

                if (code) {
                    this.processQRCode(code.data);
                    this.stopScanner();
                }
            }
            if (this.scanning) {
                requestAnimationFrame(this.scan);
            }
        },
        processQRCode(data) {
            console.log("Sending QR data to backend:", data);
            fetch('/process_qr', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ qr_data: data })
            })
            .then(response => response.json())
            .then(result => {
                console.log("Received result from backend:", result);
                if (result.success || (!result.success && result.remark.includes('已掃描過'))) {
                    // 無論是新掃描還是重複掃描，都顯示完整信息
                    this.totalAmount = result.amount;
                    this.discountHours = result.discount_hours;
                    this.lastInvoiceNumber = result.invoice_number;
                    this.lastInvoiceDate = result.invoice_date;
                    this.isCurrentDate = result.is_today;
                    this.message = result.message;
                    this.scanResult = {
                        status: result.success ? 'success' : 'warning',
                        message: result.remark
                    };
                } else {
                    // QR Code 格式錯誤或其他錯誤
                    this.totalAmount = 0;
                    this.discountHours = 0;
                    this.lastInvoiceNumber = 'N/A';
                    this.lastInvoiceDate = 'N/A';
                    this.isCurrentDate = 'N';
                    this.scanResult = {
                        status: 'error',
                        message: result.remark
                    };
                    this.message = result.message;
                }
                this.remark = result.remark;
            })
            .catch(error => {
                console.error('Error:', error);
                this.message = '處理 QR 碼時出錯，請重新掃描';
                this.scanResult = {
                    status: 'error',
                    message: '處理 QR 碼時出錯，請重新掃描'
                };
                this.remark = 'QR Code格式有誤，無法辨識';
                this.totalAmount = 0;
                this.discountHours = 0;
                this.lastInvoiceNumber = 'N/A';
                this.lastInvoiceDate = 'N/A';
                this.isCurrentDate = 'N';
            });
        },
        resetCalculator() {
            this.totalAmount = 0;
            this.discountHours = 0;
            this.scannedInvoices.clear();
            this.lastInvoiceNumber = 'N/A';
            this.lastInvoiceDate = 'N/A';
            this.isCurrentDate = 'N';
            this.message = '';
            this.scanResult = { status: '', message: '' };
            this.remark = '';
        }
    }
});