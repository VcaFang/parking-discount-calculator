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
                if (result.success) {
                    if (!this.scannedInvoices.has(result.invoice_number)) {
                        this.totalAmount += result.amount;
                        this.discountHours = Math.min(Math.floor(this.totalAmount / 1000), 4);
                        this.scannedInvoices.add(result.invoice_number);
                        this.lastInvoiceNumber = result.invoice_number;
                        this.lastInvoiceDate = result.invoice_date;
                        this.isCurrentDate = result.is_today;
                        this.message = `成功掃描發票！金額: ${result.amount}元`;
                    } else {
                        this.message = '這張發票已經掃描過了，請勿重複折抵停車!';
                    }
                } else {
                    this.message = result.message;
                }
            })
            .catch(error => {
                console.error('Error:', error);
                this.message = '處理 QR 碼時出錯，請重新掃描';
            });
        },
        resetCalculator() {
            this.totalAmount = 0;
            this.discountHours = 0;
            this.scannedInvoices.clear();
            this.lastInvoiceNumber = '';
            this.lastInvoiceDate = '';
            this.isCurrentDate = '';
            this.message = '';
        }
    }
});