环境准备：安装 Python 3.8+、MySQL 8.0
依赖安装：执行pip install -r requirements.txt
数据库配置：
创建数据库：CREATE DATABASE IF NOT EXISTS library_db DEFAULT CHARSET=utf8mb4;
执行仓库中sql/create_tables.sql文件中的建表语句
修改app.py中DB_CONFIG的user和password为本地 MySQL 账号密码
项目启动：执行python app.py
系统访问：浏览器打开http://127.0.0.1:5000即可使用
