from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import pymysql
import hashlib
import datetime
import random
import string

# === 初始化Flask应用 ===
app = Flask(__name__)
# 会话密钥，固定值即可
app.secret_key = "library_sys_2026_0103_complete"

# === MySQL数据库配置【必须修改这里！】===
DB_CONFIG = {
    "host": "localhost",        # 本地数据库固定localhost，不用改
    "user": "root",             # 你的MySQL账号，默认root
    "password": "123456",       # 改成你自己的MySQL登录密码！！！
    "database": "library_db",   # 数据库名，已创建好
    "charset": "utf8mb4"
}

# === 工具函数 ===
# 生成唯一编号（读者R-xxx / 图书B-xxx）
def generate_code(prefix):
    return prefix + ''.join(random.choices(string.digits, k=8))

# 数据库连接工具
def get_db_conn():
    conn = pymysql.connect(**DB_CONFIG)
    return conn

# MD5密码加密
def md5_encrypt(pwd):
    md5 = hashlib.md5()
    md5.update(pwd.encode('utf-8'))
    return md5.hexdigest()

# === 【页面路由】解决404核心 - 所有页面访问入口 ===
# 系统首页 → 登录页
@app.route('/')
def page_login():
    return render_template("login.html")

# 读者注册页面
@app.route('/register')
def page_register():
    return render_template("register.html")

# 读者个人中心（登录后进入）
@app.route('/reader_center')
def page_reader_center():
    if "reader_no" not in session:
        return redirect(url_for("page_login"))
    return render_template("reader_center.html")

# 图书入库页面（管理员）
@app.route('/book_warehousing')
def page_book_warehousing():
    if "admin_no" not in session and "reader_no" not in session:
        return redirect(url_for("page_login"))
    return render_template("book_warehousing.html")

# 图书查询页面
@app.route('/book_search')
def page_book_search():
    if "reader_no" not in session:
        return redirect(url_for("page_login"))
    return render_template("book_search.html")

# 借阅排行页面
@app.route('/rank')
def page_rank():
    return render_template("rank.html")

# === 【读者功能接口】注册/登录/信息修改 ===
# 1. 读者注册接口
@app.route('/api/reader/register', methods=['POST'])
def reader_register():
    data = request.form
    reader_no = generate_code("R-")
    username = data.get("username")
    password = md5_encrypt(data.get("password"))
    real_name = data.get("real_name")
    id_card = data.get("id_card")
    phone = data.get("phone")
    
    try:
        conn = get_db_conn()
        cursor = conn.cursor()
        # 校验账号/身份证号是否重复
        cursor.execute("SELECT * FROM sys_reader WHERE username=%s OR id_card=%s", (username, id_card))
        if cursor.fetchone():
            return jsonify({"code":400, "msg":"账号或身份证号已存在！"})
        # 插入注册数据
        sql = "INSERT INTO sys_reader(reader_no,username,password,real_name,id_card,phone) VALUES(%s,%s,%s,%s,%s,%s)"
        cursor.execute(sql, (reader_no, username, password, real_name, id_card, phone))
        conn.commit()
        return jsonify({"code":200, "msg":"注册成功！你的读者编号："+reader_no})
    except Exception as e:
        conn.rollback()
        return jsonify({"code":500, "msg":"注册失败："+str(e)})
    finally:
        cursor.close()
        conn.close()

# 2. 读者登录接口
@app.route('/api/reader/login', methods=['POST'])
def reader_login():
    data = request.form
    username = data.get("username")
    password = md5_encrypt(data.get("password"))
    
    try:
        conn = get_db_conn()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT * FROM sys_reader WHERE username=%s AND password=%s AND status=1", (username, password))
        reader = cursor.fetchone()
        if not reader:
            return jsonify({"code":400, "msg":"账号或密码错误，或账号已禁用！"})
        # 保存读者信息到会话
        session["reader_no"] = reader["reader_no"]
        session["username"] = reader["username"]
        session["real_name"] = reader["real_name"]
        return jsonify({"code":200, "msg":"登录成功！", "data":reader})
    except Exception as e:
        return jsonify({"code":500, "msg":"登录失败："+str(e)})
    finally:
        cursor.close()
        conn.close()

# 3. 读者个人信息修改接口
@app.route('/api/reader/update', methods=['POST'])
def reader_update():
    if "reader_no" not in session:
        return jsonify({"code":401, "msg":"请先登录！"})
    data = request.form
    reader_no = session["reader_no"]
    phone = data.get("phone")
    email = data.get("email")
    address = data.get("address")
    new_pwd = data.get("new_pwd")
    
    try:
        conn = get_db_conn()
        cursor = conn.cursor()
        update_sql = "UPDATE sys_reader SET phone=%s, email=%s, address=%s"
        params = [phone, email, address]
        if new_pwd:  # 可选修改密码
            update_sql += ", password=%s"
            params.append(md5_encrypt(new_pwd))
        update_sql += " WHERE reader_no=%s"
        params.append(reader_no)
        cursor.execute(update_sql, params)
        conn.commit()
        return jsonify({"code":200, "msg":"个人信息修改成功！"})
    except Exception as e:
        conn.rollback()
        return jsonify({"code":500, "msg":"修改失败："+str(e)})
    finally:
        cursor.close()
        conn.close()

# 4. 读者退出登录
@app.route('/api/reader/logout')
def reader_logout():
    session.clear()
    return redirect(url_for("page_login"))

# === 【图书功能接口】入库/查询 ===
# 1. 图书入库接口（核心）
@app.route('/api/book/warehousing', methods=['POST'])
def book_warehousing():
    if "reader_no" not in session:
        return jsonify({"code":401, "msg":"请先登录！"})
    data = request.form
    book_no = generate_code("B-")
    book_name = data.get("book_name")
    author = data.get("author")
    publisher = data.get("publisher")
    isbn = data.get("isbn")
    category = data.get("category")
    price = data.get("price")
    total_num = int(data.get("total_num"))
    
    try:
        conn = get_db_conn()
        cursor = conn.cursor()
        # 校验ISBN唯一性
        cursor.execute("SELECT * FROM book_info WHERE isbn=%s", (isbn,))
        if cursor.fetchone():
            return jsonify({"code":400, "msg":"该ISBN图书已入库，请勿重复添加！"})
        # 执行入库
        sql = "INSERT INTO book_info(book_no,book_name,author,publisher,isbn,category,price,total_num,stock) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)"
        cursor.execute(sql, (book_no, book_name, author, publisher, isbn, category, price, total_num, total_num))
        conn.commit()
        return jsonify({"code":200, "msg":"图书入库成功！图书编号："+book_no})
    except Exception as e:
        conn.rollback()
        return jsonify({"code":500, "msg":"入库失败："+str(e)})
    finally:
        cursor.close()
        conn.close()

# 2. 图书多条件查询接口
@app.route('/api/book/search', methods=['POST'])
def book_search():
    data = request.form
    keyword = data.get("keyword", "")
    category = data.get("category", "")
    status = data.get("status", "")
    
    try:
        conn = get_db_conn()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        sql = "SELECT * FROM book_info WHERE 1=1"
        params = []
        if keyword:
            sql += " AND (book_name LIKE %s OR author LIKE %s OR isbn LIKE %s)"
            params.extend([f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"])
        if category:
            sql += " AND category = %s"
            params.append(category)
        if status:
            sql += " AND status = %s"
            params.append(status)
        cursor.execute(sql, params)
        books = cursor.fetchall()
        return jsonify({"code":200, "msg":"查询成功", "data":books})
    except Exception as e:
        return jsonify({"code":500, "msg":"查询失败："+str(e)})
    finally:
        cursor.close()
        conn.close()

# === 【借阅功能接口】借书/还书/续借/罚款 ===
# 1. 图书借阅接口
@app.route('/api/borrow/borrow_book', methods=['POST'])
def borrow_book():
    if "reader_no" not in session:
        return jsonify({"code":401, "msg":"请先登录！"})
    reader_no = session["reader_no"]
    book_no = request.form.get("book_no")
    borrow_time = datetime.datetime.now()
    expire_time = borrow_time + datetime.timedelta(days=30)  # 默认借阅30天
    
    try:
        conn = get_db_conn()
        cursor = conn.cursor()
        conn.begin()
        # 校验1：图书是否可借
        cursor.execute("SELECT stock,status FROM book_info WHERE book_no=%s", (book_no,))
        book = cursor.fetchone()
        if not book or book[1]==0 or book[0]==0:
            return jsonify({"code":400, "msg":"图书无库存或已下架！"})
        # 校验2：是否超借阅上限
        cursor.execute("SELECT COUNT(*) FROM borrow_record WHERE reader_no=%s AND status=1", (reader_no,))
        borrow_count = cursor.fetchone()[0]
        cursor.execute("SELECT borrow_limit FROM sys_reader WHERE reader_no=%s", (reader_no,))
        borrow_limit = cursor.fetchone()[0]
        if borrow_count >= borrow_limit:
            return jsonify({"code":400, "msg":"已达最大借阅数量上限！"})
        # 校验3：是否有未缴罚款
        cursor.execute("SELECT COUNT(*) FROM fine_record WHERE reader_no=%s AND fine_status=1", (reader_no,))
        fine_count = cursor.fetchone()[0]
        if fine_count > 0:
            return jsonify({"code":400, "msg":"存在未缴纳罚款，禁止借书！"})
        
        # 执行借阅操作
        cursor.execute("UPDATE book_info SET stock=stock-1, borrow_num=borrow_num+1 WHERE book_no=%s", (book_no,))
        cursor.execute("INSERT INTO borrow_record(book_no,reader_no,expire_time) VALUES(%s,%s,%s)", (book_no, reader_no, expire_time))
        conn.commit()
        return jsonify({"code":200, "msg":f"借书成功！应归还时间：{expire_time.strftime('%Y-%m-%d')}"})
    except Exception as e:
        conn.rollback()
        return jsonify({"code":500, "msg":"借书失败："+str(e)})
    finally:
        cursor.close()
        conn.close()

# 2. 图书归还接口 + 自动生成逾期罚款
@app.route('/api/borrow/return_book', methods=['POST'])
def return_book():
    if "reader_no" not in session:
        return jsonify({"code":401, "msg":"请先登录！"})
    borrow_id = request.form.get("borrow_id")
    actual_return_time = datetime.datetime.now()
    
    try:
        conn = get_db_conn()
        cursor = conn.cursor()
        conn.begin()
        # 查询借阅记录
        cursor.execute("SELECT book_no,reader_no,expire_time FROM borrow_record WHERE id=%s AND status=1", (borrow_id,))
        borrow = cursor.fetchone()
        if not borrow:
            return jsonify({"code":400, "msg":"借阅记录不存在或已归还！"})
        book_no, reader_no, expire_time = borrow
        
        # 计算逾期天数和罚款金额（0.5元/天）
        overdue_days = max(0, (actual_return_time - expire_time).days)
        fine_amount = round(overdue_days * 0.5, 2)
        
        # 更新图书库存和借阅状态
        cursor.execute("UPDATE book_info SET stock=stock+1, borrow_num=borrow_num-1 WHERE book_no=%s", (book_no,))
        borrow_status = 3 if overdue_days>0 else 2
        cursor.execute("UPDATE borrow_record SET actual_return_time=%s, status=%s WHERE id=%s", (actual_return_time, borrow_status, borrow_id))
        
        # 逾期则生成罚款记录
        if overdue_days > 0:
            cursor.execute("INSERT INTO fine_record(borrow_id,reader_no,book_no,overdue_days,fine_amount) VALUES(%s,%s,%s,%s,%s)",
                           (borrow_id, reader_no, book_no, overdue_days, fine_amount))
        
        conn.commit()
        if overdue_days > 0:
            return jsonify({"code":200, "msg":f"还书成功！逾期{overdue_days}天，需缴纳罚款{fine_amount}元"})
        return jsonify({"code":200, "msg":"还书成功！"})
    except Exception as e:
        conn.rollback()
        return jsonify({"code":500, "msg":"还书失败："+str(e)})
    finally:
        cursor.close()
        conn.close()

# 3. 图书续借接口（单本限续1次）
@app.route('/api/borrow/renew_book', methods=['POST'])
def renew_book():
    if "reader_no" not in session:
        return jsonify({"code":401, "msg":"请先登录！"})
    borrow_id = request.form.get("borrow_id")
    
    try:
        conn = get_db_conn()
        cursor = conn.cursor()
        # 校验续借条件
        cursor.execute("SELECT renew_num,expire_time,status FROM borrow_record WHERE id=%s", (borrow_id,))
        borrow = cursor.fetchone()
        if borrow[0] >=1:
            return jsonify({"code":400, "msg":"该图书已续借1次，不可再次续借！"})
        if borrow[2] != 1:
            return jsonify({"code":400, "msg":"仅未归还且未逾期的图书可续借！"})
        
        # 执行续借：归还时间顺延30天
        new_expire = borrow[1] + datetime.timedelta(days=30)
        cursor.execute("UPDATE borrow_record SET expire_time=%s, renew_num=1 WHERE id=%s", (new_expire, borrow_id))
        conn.commit()
        return jsonify({"code":200, "msg":f"续借成功！新归还时间：{new_expire.strftime('%Y-%m-%d')}"})
    except Exception as e:
        conn.rollback()
        return jsonify({"code":500, "msg":"续借失败："+str(e)})
    finally:
        cursor.close()
        conn.close()

# 4. 罚款缴纳接口
@app.route('/api/fine/pay', methods=['POST'])
def pay_fine():
    if "reader_no" not in session:
        return jsonify({"code":401, "msg":"请先登录！"})
    fine_id = request.form.get("fine_id")
    
    try:
        conn = get_db_conn()
        cursor = conn.cursor()
        cursor.execute("UPDATE fine_record SET fine_status=2, pay_time=%s WHERE id=%s AND fine_status=1", (datetime.datetime.now(), fine_id))
        conn.commit()
        return jsonify({"code":200, "msg":"罚款缴纳成功！已解锁借阅权限"})
    except Exception as e:
        conn.rollback()
        return jsonify({"code":500, "msg":"缴纳失败："+str(e)})
    finally:
        cursor.close()
        conn.close()

# === 【统计排行接口】借阅排行/数据统计 ===
# 1. 热门图书借阅排行TOP10
@app.route('/api/stat/book_rank')
def book_rank():
    try:
        conn = get_db_conn()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        sql = """SELECT b.book_name, b.author, b.book_no, COUNT(br.id) as borrow_count 
                 FROM borrow_record br 
                 LEFT JOIN book_info b ON br.book_no=b.book_no 
                 GROUP BY br.book_no 
                 ORDER BY borrow_count DESC LIMIT 10"""
        cursor.execute(sql)
        data = cursor.fetchall()
        return jsonify({"code":200, "msg":"查询成功", "data":data})
    except Exception as e:
        return jsonify({"code":500, "msg":"查询失败："+str(e)})
    finally:
        cursor.close()
        conn.close()

# 2. 读者借阅排行TOP10
@app.route('/api/stat/reader_rank')
def reader_rank():
    try:
        conn = get_db_conn()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        sql = """SELECT r.real_name, r.reader_no, COUNT(br.id) as borrow_count 
                 FROM borrow_record br 
                 LEFT JOIN sys_reader r ON br.reader_no=r.reader_no 
                 GROUP BY br.reader_no 
                 ORDER BY borrow_count DESC LIMIT 10"""
        cursor.execute(sql)
        data = cursor.fetchall()
        return jsonify({"code":200, "msg":"查询成功", "data":data})
    except Exception as e:
        return jsonify({"code":500, "msg":"查询失败："+str(e)})
    finally:
        cursor.close()
        conn.close()

# === 启动项目 ===
if __name__ == '__main__':
    # 开启调试模式，修改代码自动重启，端口固定5000
    app.run(debug=True, host="0.0.0.0", port=5000)