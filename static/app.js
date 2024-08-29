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
    created() {
        // 從 localStorage 加載已掃描的發票
        const savedInvoices = localStorage.getItem('scannedInvoices');
        if (savedInvoices) {
            this.scannedInvoices = new Set(JSON.parse(savedInvoices));
        }
        
        // 從 localStorage 加載總金額和折抵時數
        const savedTotalAmount = localStorage.getItem('totalAmount');
        if (savedTotalAmount) {
            this.totalAmount = parseFloat(savedTotalAmount);
            this.discountHours = Math.min(Math.floor(this.totalAmount / 1000), 4);
        }
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
                }
            }
            if (this.scanning) {
                requestAnimationFrame(this.scan);
            }
        },
        processQRCode(data) {
            console.log("Processing QR code:", data);
            console.log("Current scanned invoices:", Array.from(this.scannedInvoices));
            
            const scanTime = new Date().toLocaleString('zh-TW', { timeZone: 'Asia/Taipei' });
            
            fetch('/process_qr', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ 
                    qr_data: data,
                    scan_time: scanTime
                })
            })
            .then(response => response.json())
            .then(result => {
                console.log("Received result from backend:", result);
                if (result.success) {
                    console.log("Checking invoice:", result.invoice_number);
                    if (!this.scannedInvoices.has(result.invoice_number)) {
                        console.log("New invoice detected, adding to scanned list");
                        this.totalAmount += result.amount;
                        this.discountHours = result.discount_hours;
                        this.scannedInvoices.add(result.invoice_number);
                        
                        // 更新 localStorage
                        localStorage.setItem('scannedInvoices', JSON.stringify(Array.from(this.scannedInvoices)));
                        localStorage.setItem('totalAmount', this.totalAmount.toString());
                        
                        console.log("Updated scanned invoices:", Array.from(this.scannedInvoices));
                        this.lastInvoiceNumber = result.invoice_number;
                        this.lastInvoiceDate = result.invoice_date;
                        this.isCurrentDate = result.is_today;
                        this.message = `成功掃描發票！金額: ${result.amount}元`;
                        this.showModal(`
                            <p>掃碼成功</p>
                            <p>消費金額：${result.amount} 元</p>
                            <p>可折抵停車時數：${this.discountHours} 小時</p>
                        `);
                    } else {
                        console.log("Invoice already scanned");
                        this.message = '這張發票已經掃描過了，請勿重複折抵停車!';
                        this.showModal(`
                            <p class="text-danger">本發票已掃描過，勿重複折抵</p>
                        `);
                    }
                } else {
                    console.log("QR code processing failed:", result.message);
                    this.message = result.message;
                    this.showModal(`
                        <p class="text-danger">QR Code無法解析</p>
                        <p>${result.message}</p>
                    `);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                this.message = '處理 QR 碼時出錯，請重新掃描';
                this.showModal(`
                    <p class="text-danger">處理 QR 碼時出錯</p>
                    <p>請重新掃描</p>
                `);
            });
        },
        resetCalculator() {
            console.log("Resetting calculator");
            this.totalAmount = 0;
            this.discountHours = 0;
            this.scannedInvoices.clear();
            
            // 清除 localStorage
            localStorage.removeItem('scannedInvoices');
            localStorage.removeItem('totalAmount');
            
            this.lastInvoiceNumber = '';
            this.lastInvoiceDate = '';
            this.isCurrentDate = '';
            this.message = '';
        },
        showModal(content) {
            const modalContent = document.getElementById('modalContent');
            if (modalContent) {
                modalContent.innerHTML = content;
                const modal = new bootstrap.Modal(document.getElementById('scanResultModal'));
                modal.show();
                
                // 添加監聽器，在模態框隱藏時重置掃描器
                document.getElementById('scanResultModal').addEventListener('hidden.bs.modal', this.resetScannerState);
            } else {
                console.error('Modal content element not found');
                alert(content);
            }
        },
        resetScannerState() {
            this.stopScanner();
            this.video.style.display = 'none';
            this.canvas.style.display = 'none';
            // 重置其他相關狀態...
        }
    }
});