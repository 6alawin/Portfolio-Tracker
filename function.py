import datetime
import pandas as pd
import yfinance as yf
import streamlit as st # เพิ่ม import นี้

def add_transactions(transactions, tx_type, symbol, qty, price, com, date=None):
    record_date = date if date else datetime.datetime.now().strftime("%Y-%m-%d")
    transactions.append({
        "type": tx_type,
        "symbol": symbol,
        "qty": qty,
        "price": price,
        "com": com,
        "date": record_date
    })

def add_withdrawal(withdrawals, amount, date=None):
    withdrawals.append({
        "type": "WITHDRAW",
        "amount": amount,
        "timestamp": date if date else datetime.datetime.now().strftime("%Y-%m-%d")
    })

def get_holdings(transactions):
    holdings = {}
    for tx in transactions:
        s = tx.get("symbol")
        q = tx.get("qty", 0.0)
        p = tx.get("price", 0.0)
        c = tx.get("com", 0.0)
        t_type = tx.get("type")

        if s and t_type:
            if s not in holdings:
                holdings[s] = {"qty": 0.0, "total_cost": 0.0}

            if t_type == "BUY":
                holdings[s]["qty"] += q
                holdings[s]["total_cost"] += q * p + c

            elif t_type == "SELL":
                if holdings[s]["qty"] > 0:
                    avg = holdings[s]["total_cost"] / holdings[s]["qty"]
                    holdings[s]["qty"] -= q
                    holdings[s]["total_cost"] -= avg * q

    return {
        s: {
            "qty": v["qty"],
            "avg_cost": v["total_cost"] / v["qty"] if v["qty"] > 0 else 0
        }
        for s, v in holdings.items()
        if v["qty"] > 0
    }

def calculate_port(transactions):
    total_sell_revenue = 0.0
    realized_pnl = 0.0
    total_invested = 0.0
    temp_holdings = {}

    for tx in transactions:
        # แก้ไขคำผิด (tpye -> type)
        t_type = tx.get("type") 
        symbol = tx.get("symbol")
        qty = tx.get("qty", 0.0)
        price = tx.get("price", 0.0)
        com = tx.get("com", 0.0)

        if t_type == "BUY":
            cost = (qty * price) + com
            
            # *** ลบบรรทัด add_transactions ที่ซ้ำซ้อนออกแล้ว ***
            
            if symbol not in temp_holdings:
                temp_holdings[symbol] = {"qty": 0.0, "total_cost": 0.0}
            
            temp_holdings[symbol]["qty"] += qty
            temp_holdings[symbol]["total_cost"] += cost
            
        elif t_type == "SELL":
            revenue = (qty * price) - com
            total_sell_revenue += revenue

            if symbol in temp_holdings and temp_holdings[symbol]["qty"] > 0:
                avg_cost = temp_holdings[symbol]["total_cost"] / temp_holdings[symbol]["qty"]
                cost_of_sold = avg_cost * qty

                trade_pnl = revenue - cost_of_sold 
                realized_pnl += trade_pnl

                temp_holdings[symbol]["qty"] -= qty
                temp_holdings[symbol]["total_cost"] -= cost_of_sold

    for symbol, data in temp_holdings.items():
        if data["qty"] > 0:
            total_invested += data["total_cost"]

    return total_sell_revenue, total_invested, realized_pnl

# --- S&P 500 Cache (24 ชั่วโมง) ---
@st.cache_data(ttl=86400) 
def fetch_sp500_data(start_date):
    try:
        return yf.download("^GSPC", start=start_date, progress=False)['Close']
    except:
        return pd.Series(dtype='float64')

def port_history(transactions):
    if not transactions: return pd.DataFrame()
    df_tx = pd.DataFrame(transactions)

    if 'date' not in df_tx.columns:
        df_tx['date'] = datetime.datetime.now().strftime("%Y-%m-%d")
    else:
        df_tx['date'] = df_tx['date'].fillna(datetime.datetime.now().strftime("%Y-%m-%d"))

    df_tx['date'] = pd.to_datetime(df_tx['date'])
    if df_tx.empty: return pd.DataFrame()

    start_date = df_tx["date"].min()

    symbols = list(set(t['symbol'] for t in transactions if t.get('symbol')))
    symbols = [s for s in symbols if s] 
    
    # ดึง S&P 500 จาก Cache
    sp500_data = fetch_sp500_data(start_date)

    try:
        if not symbols:
             data = pd.DataFrame()
        else:
             data = yf.download(symbols, start=start_date, progress=False)['Close']
    except:
        return pd.DataFrame()

    if not sp500_data.empty:
        if isinstance(data, pd.Series): data = data.to_frame()
        if not data.empty:
             if isinstance(sp500_data, pd.Series): sp500_data = sp500_data.to_frame(name="^GSPC")
             combined_data = data.join(sp500_data, how='outer')
             data = combined_data
        else:
             data = sp500_data.to_frame(name="^GSPC")

    if data.empty: return pd.DataFrame()
    
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    
    daily_value = []
    
    for date in data.index:
        current_txs = df_tx[df_tx["date"] <= date].to_dict('records')
        cash_cow = 0.0
        temp_hold = {}

        for tx in current_txs:
            symbol = tx.get("symbol")
            qty = tx.get("qty", 0.0)
            price = tx.get("price", 0.0)
            com = tx.get("com", 0.0)
            t_type = tx.get("type")

            if t_type == "BUY":
                cost = (qty * price) + com
                if symbol not in temp_hold: temp_hold[symbol] = {"qty": 0.0, "cost": 0.0}
                temp_hold[symbol]["qty"] += qty
                temp_hold[symbol]["cost"] += cost
            
            elif t_type == "SELL":
                revenue = (qty * price) - com
                cash_cow += revenue
                if symbol in temp_hold and temp_hold[symbol]["qty"] > 0:
                    avg_cost = temp_hold[symbol]["cost"] / temp_hold[symbol]["qty"]
                    cost_of_sold = avg_cost * qty
                    temp_hold[symbol]["qty"] -= qty
                    temp_hold[symbol]["cost"] -= cost_of_sold
            
            elif t_type == "WITHDRAW":
                cash_cow -= tx.get("amount", 0.0)
        
        stock_value = 0.0
        current_invested = 0.0

        for s, info in temp_hold.items():
            if info['qty'] > 0:
                if s in data.columns:
                    val = data.loc[date, s]
                    price = val if not pd.isna(val) else 0.0
                else: price = 0.0
                
                stock_value += info['qty'] * price
                current_invested += info['cost']

        net_worth = stock_value + cash_cow
        roi = ((net_worth - current_invested) / current_invested * 100) if current_invested > 0 else 0.0

        daily_value.append({
            'Date': date,
            'My Portfolio (%)': roi
        })

    if not daily_value: return pd.DataFrame()

    df_result = pd.DataFrame(daily_value).set_index('Date')

    if '^GSPC' in data.columns:
        valid_sp = data['^GSPC'].dropna()
        if not valid_sp.empty:
            start_val = valid_sp.iloc[0]
            if start_val > 0:
                 df_result['S&P 500 (%)'] = ((data['^GSPC'] - start_val) / start_val) * 100

    return df_result