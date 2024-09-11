# 使用官方 Python 運行時作為父鏡像
FROM python:3.9-slim-buster

# 設置工作目錄
WORKDIR /app

# 將當前目錄內容複製到容器中的 /app
COPY . /app

# 安裝必要的包
RUN pip install --no-cache-dir -r requirements.txt

# 安裝 sqlite3
RUN apt-get update && apt-get install -y sqlite3

# 確保腳本可執行
RUN chmod +x /app/start.sh

# 設置環境變量
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0

# 對外暴露 8080 端口
EXPOSE 8080

# 運行應用
CMD ["/app/start.sh"]