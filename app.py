import streamlit as st
import yfinance as yf
from streamlit_autorefresh import st_autorefresh
import datetime 
from function import add_transactions, get_holdings, calculate_port, add_withdrawal, port_history

@st.cache_data(ttl=120)
def fetch_current_prices(symbols):
    prices = {}
    if not symbols: return prices

    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.fast_info
            prices[symbol] = data["last_price"]
        except:
            prices[symbol] = 0.0
    return prices

# --- Head ---
st.set_page_config(page_title="My Portfolio", layout="wide")
st_autorefresh(interval=120000, key="price_refresher") # Auto refresh ทุก 2 นาที
st.title("My Portfolio")

if "transactions" not in st.session_state:
    st.session_state.transactions = []
if "withdrawals" not in st.session_state:
    st.session_state.withdrawals = []

# --- Sidebar ---
st.sidebar.header("Add Transactions")

mode = st.sidebar.radio("Mode", ["Trade [BUY/SELL]", "Withdraw Fund"])

if mode == "Trade [BUY/SELL]":
    tx_type = st.sidebar.selectbox("Action", ["BUY","SELL"])
    tx_date = st.sidebar.date_input("Transaction Date", value=datetime.date.today())
    symbol = st.sidebar.text_input("Symbol (e.g. NVDA)").upper()
    qty = st.sidebar.number_input("Quantity", min_value=0.0000001, format="%.7f")
    price = st.sidebar.number_input("Price per Share", min_value=0.0)
    com = st.sidebar.number_input("Commission", min_value=0.0)
    
    submit = st.sidebar.button("Submit Trade")
    if submit:
        if not symbol or qty <= 0 or price <= 0:
            st.sidebar.error("Invalid input")
        else:
            if tx_type == "SELL":
                holdings = get_holdings(st.session_state.transactions)
                current_qty = holdings.get(symbol, {}).get("qty", 0)
                if qty > current_qty:
                    st.sidebar.error("Not enough shares!")
                    st.stop()

            add_transactions(st.session_state.transactions, tx_type, symbol, qty, price, com, date=tx_date.strftime("%Y-%m-%d"))
            st.success(f"Recorded {tx_type} {symbol} on {tx_date}")
            st.rerun()

elif mode == "Withdraw Fund":
    st.sidebar.info("Pull money back from Cash Cow")
    wd_date = st.sidebar.date_input("Withdrawal Date", value=datetime.date.today())
    amount = st.sidebar.number_input("Amount (USD)", min_value=0.0)

    if st.sidebar.button("Confirm Withdraw"):
        rev, _, _ = calculate_port(st.session_state.transactions)
        current_withdrawn = sum(w["amount"] for w in st.session_state.withdrawals)
        available_cash = rev - current_withdrawn

        if amount > available_cash:
            st.sidebar.error(f"Insufficient Cash! Available: ${available_cash:,.2f}")
        elif amount <= 0:
            st.sidebar.error("Amount must be > 0")
        else:
            add_withdrawal(st.session_state.withdrawals, amount, date=wd_date.strftime("%Y-%m-%d"))
            st.sidebar.success(f"Withdrew ${amount:,.2f} on {wd_date}")
            st.rerun()

# --- Calculation Zone ---
total_sell_revenue, total_invested, realized_pnl = calculate_port(st.session_state.transactions)
total_withdrawn = sum(w["amount"] for w in st.session_state.withdrawals)
cash_cow = total_sell_revenue - total_withdrawn

holdings = get_holdings(st.session_state.transactions)

if "current_prices" not in st.session_state:
    st.session_state.current_prices = {}

table = []
total_unrelized = 0.0
portfolio_value = 0.0

# ดึงราคาหุ้น
active_symbols = list(holdings.keys())
if active_symbols:
    # เช็คว่ามีราคาเดิมอยู่ไหม ถ้าไม่มีค่อยดึงใหม่ หรือถ้ากดปุ่ม Refresh
    if not st.session_state.current_prices: 
         st.session_state.current_prices = fetch_current_prices(active_symbols)

# สร้างตาราง Holdings
for symbol, data in holdings.items():
    qty = data["qty"]
    cost_basis_per_share = data["avg_cost"]
    current_price = st.session_state.current_prices.get(symbol, 0.0)

    market_value =  qty * current_price
    cost_basis_total = qty * cost_basis_per_share
    unrelized_pnl = market_value - cost_basis_total

    portfolio_value += market_value
    total_unrelized += unrelized_pnl

    table.append({
        "Symbol": symbol,
        "Quantity": round(qty, 7),
        "Avg Cost": round(cost_basis_per_share, 4),
        "Current Price": current_price,
        "Market Value": round(market_value, 2),
        "Unrelized P&L": round(unrelized_pnl, 2)
    })

# --- Interface ---
st.subheader("Portfolio Summary")

col1, col2, col3, col4 = st.columns(4)

col1.metric("Total Invested", f"${total_invested:,.2f}")
col2.metric("Portfolio Value", f"${portfolio_value:,.2f}")
col3.metric("Cash Cow (Available)", f"${cash_cow:,.2f}")
col4.metric("Realized P&L", f"${realized_pnl:,.2f} / {(realized_pnl / total_invested) * 100:,.2f}%")

# Chart Section
if st.session_state.transactions:
    try:
        with st.spinner("Calculating historical performance..."):
            df_chart = port_history(st.session_state.transactions)
        
        if not df_chart.empty:
            st.line_chart(df_chart, color=["#FF0000", "#00FF00"])
        else:
            st.info("Not enough data to plot chart yet.")
    except Exception as e:
        st.warning(f"Chart Error: {e}")
else:
    st.info("Add transaction to see performance graph.")

st.subheader("Current Holdings")
st.metric("Unrealized P&L", f"${total_unrelized:,.2f} / {(total_unrelized / total_invested) * 100:,.2f}%", delta=f"{total_unrelized:,.2f}")
st.caption("Price auto-updates every 2 minutes")

# --- ปุ่ม Refresh ที่แก้ไขแล้ว (แก้จุด Rerun รัวๆ) ---
if st.button("Refresh Price Now"):
    st.session_state.current_prices = fetch_current_prices(active_symbols)
    st.rerun()

st.divider()

col_main, col_side = st.columns([2, 1])

with col_main:
    st.subheader("📦 Current Holdings")
    st.dataframe(table, use_container_width=True)

    st.subheader("📜 Trade History")
    st.dataframe(st.session_state.transactions, use_container_width=True)

with col_side:
    st.subheader("💸 Withdrawal Log")
    if st.session_state.withdrawals:
        # แปลงเป็น DataFrame เพื่อความสวยงาม
        import pandas as pd
        df_wd = pd.DataFrame(st.session_state.withdrawals)
        st.dataframe(df_wd, use_container_width=True)
    else:
        st.info("No withdrawals yet.")