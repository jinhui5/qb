import psycopg2
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 连接数据库
def get_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

# 获取用户信息
def get_user_info(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT username, usdt_balance, cny_balance FROM users WHERE user_id = %s", (user_id,))
    user_info = cur.fetchone()
    cur.close()
    conn.close()
    return user_info

# 插入用户信息（首次启动时）
def add_user_to_db(user_id, username):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (user_id, username, usdt_balance, cny_balance) 
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (user_id) DO NOTHING;
    """, (user_id, username, 0.00, 0.00))  # 初始余额为 0
    conn.commit()
    cur.close()
    conn.close()
