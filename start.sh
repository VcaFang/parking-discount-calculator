#!/bin/bash

# 初始化數據庫（如果需要的話）
python -c "from app import init_db; init_db()"

# 使用 gunicorn 啟動應用
gunicorn --bind 0.0.0.0:8080 app:app