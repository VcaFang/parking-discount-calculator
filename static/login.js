new Vue({
    el: '#login-app',
    data: {
        userCode: '',
        loginError: ''
    },
    methods: {
        login() {
            if (this.userCode.length !== 6) {
                this.loginError = '請輸入6位數人員代碼';
                return;
            }
            fetch('/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ user_code: this.userCode })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    window.location.href = '/main';  // 登入成功，重定向到主頁
                } else {
                    this.loginError = data.message;
                }
            })
            .catch(error => {
                console.error('Login error:', error);
                this.loginError = '登入失敗，請稍後再試';
            });
        }
    }
});