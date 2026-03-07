import os
from dotenv import load_dotenv
load_dotenv()
from sqlalchemy import create_engine, text
from datetime import datetime
import time

engine = create_engine(os.environ["MYSQL_DATABASE_URI"])

with engine.connect() as conn:
    merchant = conn.execute(
        text("SELECT id, merchant_no FROM merchants WHERE merchant_name = :n"),
        {"n": "支付宝"}
    ).fetchone()

    if not merchant:
        print("ERROR: 找不到商户名称=支付宝")
    else:
        mid = merchant[0]
        mno = merchant[1]
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn.execute(text("""
            INSERT INTO orders (order_no, out_order_no, merchant_id, total_amount, pay_amount, fee, pay_type, status, pay_time)
            VALUES (:ono, :oout, :mid, 1000.00, 1000.00, 6.00, 'alipay', 1, :t)
        """), {"ono": f"TEST{datetime.now().strftime('%Y%m%d%H%M%S')}A", "oout": "TESTOUT001", "mid": mid, "t": now})

        time.sleep(1)
        now2 = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn.execute(text("""
            INSERT INTO orders (order_no, out_order_no, merchant_id, total_amount, pay_amount, fee, pay_type, status, pay_time)
            VALUES (:ono, :oout, :mid, 500.50, 500.50, 3.00, 'wechat', 1, :t)
        """), {"ono": f"TEST{datetime.now().strftime('%Y%m%d%H%M%S')}B", "oout": "TESTOUT002", "mid": mid, "t": now2})

        conn.commit()
        print(f"成功！商户 {mno} (id={mid}) 已插入 2 条今日订单：")
        print(f"  订单1: 1000.00 元 (alipay)")
        print(f"  订单2: 500.50 元 (wechat)")
