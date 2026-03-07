import os
import pymysql
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def init_database():
    uri = os.environ.get("MYSQL_DATABASE_URI")
    if not uri:
        print("错误: 未在 .env 中发现 MYSQL_DATABASE_URI")
        return

    # 解析 URI 以获取基础连接信息 (不含数据库名)
    # 格式: mysql+pymysql://root:123456@localhost:3306/merchant_db
    try:
        base_uri_parts = uri.split("/")
        db_name = base_uri_parts[-1]
        base_conn_info = "/".join(base_uri_parts[:-1])
        
        # 1. 连接 MySQL 服务器 (不指定数据库) 以检查并创建数据库
        # 注意：这里假设使用 pymysql
        auth_part = base_uri_parts[2] # root:123456@localhost:3306
        user_pass, host_port = auth_part.split("@")
        user, password = user_pass.split(":")
        host, port = host_port.split(":")
        
        conn = pymysql.connect(
            host=host,
            user=user,
            password=password,
            port=int(port)
        )
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` DEFAULT CHARACTER SET utf8mb4;")
        print(f"数据库 `{db_name}` 已存在或创建成功。")
        conn.close()
        
        # 2. 使用 SQLAlchemy 连接到指定的数据库并创建表
        engine = create_engine(uri)
        
        with engine.connect() as connection:
            # 商户表
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS merchants (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    merchant_no VARCHAR(32) UNIQUE NOT NULL COMMENT '商户号',
                    merchant_name VARCHAR(128) NOT NULL COMMENT '商户名称',
                    short_name VARCHAR(64) COMMENT '商户简称',
                    merchant_type TINYINT DEFAULT 1 COMMENT '1-个体, 2-企业',
                    contact_name VARCHAR(32) COMMENT '联系人',
                    contact_phone VARCHAR(20) COMMENT '联系电话',
                    business_license VARCHAR(64) COMMENT '营业执照号',
                    address VARCHAR(255) COMMENT '详细地址',
                    status TINYINT DEFAULT 1 COMMENT '0-待审核, 1-正常, 2-冻结',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """))
            
            # 订单表
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS orders (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    order_no VARCHAR(64) UNIQUE NOT NULL COMMENT '系统订单号',
                    out_order_no VARCHAR(64) COMMENT '商户外部订单号',
                    merchant_id INT NOT NULL COMMENT '关联商户ID',
                    total_amount DECIMAL(10, 2) NOT NULL COMMENT '总金额',
                    pay_amount DECIMAL(10, 2) COMMENT '实付金额',
                    fee DECIMAL(10, 2) DEFAULT 0.00 COMMENT '手续费',
                    currency VARCHAR(10) DEFAULT 'CNY',
                    pay_type VARCHAR(32) COMMENT '支付方式: alipay, wechat, unionpay',
                    status TINYINT DEFAULT 0 COMMENT '0-未支付, 1-支付成功, 2-支付失败, 3-已退款',
                    pay_time DATETIME COMMENT '支付完成时间',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_merchant (merchant_id),
                    INDEX idx_order_no (order_no)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """))
            
            # 人员表
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS personnel (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    merchant_id INT COMMENT '所属商户ID (0或NULL为平台管理人员)',
                    username VARCHAR(64) UNIQUE NOT NULL COMMENT '登录账号',
                    password_hash VARCHAR(255) NOT NULL,
                    real_name VARCHAR(32) COMMENT '真实姓名',
                    role VARCHAR(32) DEFAULT 'cashier' COMMENT 'admin, cashier, accountant',
                    mobile VARCHAR(20) COMMENT '手机号',
                    status TINYINT DEFAULT 1 COMMENT '1-启用, 0-禁用',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_merchant_person (merchant_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """))
            
            # 结算流水表
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS settlement_logs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    settlement_no VARCHAR(64) UNIQUE NOT NULL COMMENT '结算流水号',
                    merchant_id INT NOT NULL COMMENT '关联商户ID',
                    total_amount DECIMAL(10, 2) NOT NULL COMMENT '结算总金额',
                    total_fee DECIMAL(10, 2) DEFAULT 0.00 COMMENT '手续费',
                    net_amount DECIMAL(10, 2) NOT NULL COMMENT '实结金额',
                    bank_name VARCHAR(128) COMMENT '开户名/银行名',
                    bank_card_no VARCHAR(32) COMMENT '银行卡号',
                    status TINYINT DEFAULT 0 COMMENT '0-待结算, 1-结算中, 2-结算成功, 3-结算失败',
                    settlement_time DATETIME COMMENT '结算处理时间',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_merchant_settle (merchant_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """))
            
            # 提交事务
            connection.commit()
            print("各业务表 (商户、订单、人员、结算流水) 已完成初始化。")

            # 3. 插入 10 条测试数据
            print("正在插入测试数据...")
            
            # 插入商户
            for i in range(1, 11):
                connection.execute(text(f"""
                    INSERT INTO merchants (merchant_no, merchant_name, short_name, merchant_type, contact_name, contact_phone, status)
                    VALUES ('M100{i}', '测试商户{i}', '商户{i}', {1 if i % 2 == 0 else 2}, '联系人{i}', '1380000000{i-1}', 1)
                """))
            
            # 插入人员
            for i in range(1, 11):
                role = 'admin' if i == 1 else ('accountant' if i % 3 == 0 else 'cashier')
                connection.execute(text(f"""
                    INSERT INTO personnel (merchant_id, username, password_hash, real_name, role, mobile)
                    VALUES ({i}, 'user{i}', 'hash_placeholder_{i}', '员工{i}', '{role}', '1390000000{i-1}')
                """))

            # 插入订单
            import random
            from datetime import datetime, timedelta
            for i in range(1, 11):
                amount = round(random.uniform(10.0, 1000.0), 2)
                fee = round(amount * 0.006, 2)
                connection.execute(text(f"""
                    INSERT INTO orders (order_no, out_order_no, merchant_id, total_amount, pay_amount, fee, pay_type, status, pay_time)
                    VALUES ('ORD2026030600{i}', 'OUT{i}abc', {random.randint(1, 10)}, {amount}, {amount}, {fee}, 'alipay', 1, '{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}')
                """))

            # 插入结算流水
            for i in range(1, 11):
                total = round(random.uniform(5000.0, 20000.0), 2)
                fee = round(total * 0.006, 2)
                net = total - fee
                connection.execute(text(f"""
                    INSERT INTO settlement_logs (settlement_no, merchant_id, total_amount, total_fee, net_amount, bank_name, bank_card_no, status)
                    VALUES ('SETTLE20260300{i}', {i}, {total}, {fee}, {net}, '招商银行', '622202******{1231+i}', 1)
                """))

            connection.commit()
            print("10 条测试数据已成功插入各表。")
            
    except Exception as e:
        print(f"操作数据库失败: {e}")

if __name__ == "__main__":
    init_database()
