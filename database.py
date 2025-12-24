import sqlite3
import hashlib

DB_NAME = "portfolio.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users 
              (id INTEGER PRIMARY KEY AUTOINCREMENT, 
              username TEXT UNIQUE, 
              password TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS transactions 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  type TEXT, symbol TEXT, qty REAL, price REAL, com REAL, date TEXT,
                  FOREIGN KEY(user_id) REFERENCES users(id))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS withdrawals 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  amount REAL, date TEXT,
                  FOREIGN KEY(user_id) REFERENCES users(id))''')
    
    conn.commit()
    conn.close()

def make_hash(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    if make_hash(password) == hashed_text:
        return hashed_text
    return False

def add_user(username, password):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users(username, password) VALUES (?,?)',
                  (username, make_hash(password)))
        conn.comit()
        return True
    except:
        return False
    finally:
        conn.close()

def login_user(username, password):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute('SELECT * FROM users WHERE username = ? AND password = ?',
              (username, password))
    data = c.fetchall()
    conn.close()
    return data

def add_tx_db(user_id, tx_type, symbol, qty, price, com, date):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute('INSERT INTO transaction(user_id, type, symbol, qty, price, com, date) VALUES (?,?,?,?,?,?,?)',
              (user_id, tx_type, symbol, qty, price, com, date))
    conn.commit()
    conn.close()

def get_tx_db(user_id):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute('SELECT type, symbol, qty, price, com, date FROM transactions WHERE user_id = ?', (user_id,))
    data = c.fetchall()
    conn.close()

    return [dict(row) for row in data]

def add_wd_db(user_id, amount, date):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute('INSERT INTO withdrawals(user_id, amount, date VALUE(?, ?, ?)',
              (user_id, amount, date))
    conn.commit()
    conn.close()

def get_wd_db(user_id):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute('SELECT amount, date FROM withdrawals WHERE user_id = ?', (user_id))
    data = c.fetchall()
    conn.close()

    result = []
    for row in data:
        r = dict(row)
        r['type'] = 'WITHDRAW'
        result.append(r)

    return result