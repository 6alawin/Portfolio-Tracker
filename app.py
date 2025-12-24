import streamlit as st
import yfinance as yf
from streamlit_autorefresh import st_autorefresh
import datetime 
import database as db
from function import add_transactions, get_holdings, calculate_port, add_withdrawal, port_history

st.set_page_config(page_title="My Portfolio", layout="wide")

db.init_db()

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

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.username = None
if 'show_register' not in st.session_state:
    st.session_state.show_register = False

# --- Pade Function ---

def register_page():
    col7, col8, col9 = st.columns([1,1,1])
    with col8:
        st.title('Register'.upper(), anchor=False, text_alignment="center")
        new_user = st.text_input("New Username")
        new_pass = st.text_input("New Password", type='password')
        
        col_reg_1, col_reg_2 = st.columns(2)
        
        with col_reg_1:
            if st.button('Confirm Register', use_container_width=True):
                if new_user and new_pass:
                    success = db.add_user(new_user, new_pass)
                    if success:
                        st.success("Register complete! Redirecting to login...")
                        st.session_state.show_register = False 
                        st.rerun()
                    else:
                        st.error('Username already taken')
                else:
                    st.warning('Please input information')
        
        with col_reg_2:
            if st.button("Back to Login", use_container_width=True):
                st.session_state.show_register = False
                st.rerun()

def login_page():
    col1, col2, col3 = st.columns([1, 1, 1])

    with col2:                              
        st.markdown("<h1 style='text-align: center;'>LOGIN PORT-TRACKER</h1>", unsafe_allow_html=True)
        username = st.text_input("Username")
        password = st.text_input("Password", type='password')

        if st.button("LOGIN", use_container_width=True):
            user_data = db.login_user(username, password)

            if user_data:
                st.session_state.logged_in = True
                st.session_state.user_id = user_data[0][0]
                st.session_state.username = username
                st.success(f'Welcome {username}!')
                st.rerun()
            else:
                st.error("Username or Password is wrong!")

        col4, col5, col6, col7 = st.columns([1,2,2,1])
        with col5:
            st.caption("If not have an account: ")
        with col6:

            if st.button("REGISTER"):
                st.session_state.show_register = True
                st.rerun()

def main_page():
    st_autorefresh(interval=120000, key="price_refresher") # Auto refresh ทุก 2 นาที
    st.title("My Portfolio")

    current_user_id = st.session_state.user_id

    transactions = db.get_tx_db(current_user_id)
    withdrawals = db.get_wd_db(current_user_id)

    def delete_callback(tx_id):
        import database as db
        db.delete_tx_db(tx_id)
        st.toast(f"✅ ลบรายการ {tx_id} แล้ว! (กำลังรีเฟรช...)")

    # --- Sidebar ---
    st.sidebar.title(f'User {st.session_state.username}')
    if st.sidebar.button('Logout'):
        st.session_state.logged_in = False
        st.session_state.user_id = None
        st.rerun()
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
                    holdings = get_holdings(transactions)
                    current_qty = holdings.get(symbol, {}).get("qty", 0)
                    if qty > current_qty:
                        st.sidebar.error("Not enough shares!")
                        st.stop()

                db.add_tx_db(current_user_id, tx_type, symbol, qty, price, com, date=tx_date.strftime("%Y-%m-%d"))
                st.success(f"Recorded {tx_type} {symbol} on {tx_date}")
                st.rerun()

    elif mode == "Withdraw Fund":
        st.sidebar.info("Pull money back from Cash Cow")
        wd_date = st.sidebar.date_input("Withdrawal Date", value=datetime.date.today())
        amount = st.sidebar.number_input("Amount (USD)", min_value=0.0)

        if st.sidebar.button("Confirm Withdraw"):
            rev, _, _ = calculate_port(transactions)
            current_withdrawn = sum(w["amount"] for w in withdrawals)
            available_cash = rev - current_withdrawn

            if amount > available_cash:
                st.sidebar.error(f"Insufficient Cash! Available: ${available_cash:,.2f}")
            elif amount <= 0:
                st.sidebar.error("Amount must be > 0")
            else:
                db.add_wd_db(current_user_id, amount, date=wd_date.strftime("%Y-%m-%d"))
                st.sidebar.success(f"Withdrew ${amount:,.2f} on {wd_date}")
                st.rerun()

    # --- Calculation Zone ---
    total_sell_revenue, total_invested, realized_pnl = calculate_port(transactions)
    total_withdrawn = sum(w["amount"] for w in withdrawals)
    cash_cow = total_sell_revenue - total_withdrawn

    holdings = get_holdings(transactions)

    if "current_prices" not in st.session_state:
        st.session_state.current_prices = {}

    table = []
    total_unrelized = 0.0
    portfolio_value = 0.0
    if total_invested > 0:
        roi_unrealized = (total_unrelized / total_invested) * 100
        roi_relized = (realized_pnl / total_invested) * 100
    else:
        roi_unrealized = 0.0
        roi_relized = 0.0

    # ดึงราคาหุ้น
    active_symbols = list(holdings.keys())
    current_prices = fetch_current_prices(active_symbols)

    if active_symbols:
        # เช็คว่ามีราคาเดิมอยู่ไหม ถ้าไม่มีค่อยดึงใหม่ หรือถ้ากดปุ่ม Refresh
        if not st.session_state.current_prices: 
            st.session_state.current_prices = current_prices

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
    col4.metric("Realized P&L", f"${realized_pnl:,.2f} / {roi_relized:,.2f}%")

    # Chart Section
    if transactions:
        try:
            with st.spinner("Calculating historical performance..."):
                df_chart = port_history(transactions)
            
            if not df_chart.empty:
                st.line_chart(df_chart, color=["#FF0000", "#00FF00"])
        except:
            st.info("Chart needs more data.")

    st.subheader("Current Holdings")
    st.metric("Unrealized P&L", f"${total_unrelized:,.2f} / {roi_unrealized:,.2f}%", delta=f"{total_unrelized:,.2f}")
    st.caption("Price auto-updates every 2 minutes")

    # --- ปุ่ม Refresh ที่แก้ไขแล้ว (แก้จุด Rerun รัวๆ) ---
    if st.button("Refresh Price Now"):
        st.session_state.current_prices = current_prices
        st.rerun()

    import pandas as pd 

    st.divider() # ขีดเส้นคั่นหน่อย
    
    col_main, col_side = st.columns([2, 1])

    with col_main:
        st.subheader("📦 Current Holdings")
        st.dataframe(table, use_container_width=True)

        st.divider() # เส้นคั่น

        # 1. สร้างพื้นที่ว่างๆ รอไว้ "ข้างบน" ตาราง (เอาไว้โชว์ปุ่มลบ)
        action_container = st.container()

        st.subheader("📜 Trade History")
        
        if transactions:
            df_tx = pd.DataFrame(transactions)
            
            # จัดเรียง ID ไว้หน้าสุด
            cols = ['id'] + [c for c in df_tx.columns if c != 'id']
            df_tx = df_tx[cols]

            # 2. แสดงตาราง (เมื่อคลิกเลือก มันจะไป trig ให้โค้ดทำงานต่อ)
            event_tx = st.dataframe(
                df_tx,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",           # คลิกปุ๊บ รีรันโค้ดรอบนึงเพื่อโชว์ปุ่ม
                selection_mode="single-row",
                key="history_table"
            )
            
            # 3. เช็คว่ามีการเลือกบรรทัดไหม
            if len(event_tx.selection.rows) > 0:
                selected_idx = event_tx.selection.rows[0]
                tx_id_delete = df_tx.iloc[selected_idx]['id']
                
                # 4. ย้อนกลับไปใส่ปุ่มใน "พื้นที่ว่างข้างบน" ที่เราจองไว้ (action_container)
                with action_container:
                    # สร้างกรอบสีแดงเตือน
                    with st.chat_message("assistant", avatar="🗑️"):
                        st.write(f"⚠️ **ต้องการลบรายการ ID: {tx_id_delete} ใช่ไหม?**")
                        
                        # ปุ่มยืนยันลบ
                        if st.button("ยืนยันการลบ (Confirm Delete)", type="primary"):
                            db.delete_tx_db(tx_id_delete) # ลบใน Database
                            st.toast(f"❌ ลบรายการ {tx_id_delete} เรียบร้อย!")
                            
                            # สำคัญมาก! ต้องสั่ง sleep นิดนึงแล้ว rerun ไม่งั้นมันจะเร็วไปจน database ตามไม่ทัน
                            import time
                            time.sleep(0.5) 
                            st.rerun() # รีโหลดหน้าจอทันที
        else:
            st.info("No trade history.")

    with col_side:
        # ทำเหมือนกันกับฝั่ง Withdraw (ถ้าต้องการ)
        st.subheader("💸 Withdrawal Log")
        # ... (โค้ดส่วน Withdraw ถ้าจะแก้ก็ใช้ logic เดียวกันครับ) ...
        if withdrawals:
            df_wd = pd.DataFrame(withdrawals)
            cols_wd = ['id'] + [c for c in df_wd.columns if c != 'id']
            df_wd = df_wd[cols_wd]
            
            # สร้างพื้นที่จองสำหรับปุ่มลบถอนเงิน
            wd_action_container = st.container()

            event_wd = st.dataframe(
                df_wd,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="wd_table"
            )

            if len(event_wd.selection.rows) > 0:
                wd_idx = event_wd.selection.rows[0]
                wd_id_delete = df_wd.iloc[wd_idx]['id']
                
                with action_container:
                    # สร้างกรอบสีแดง
                    with st.chat_message("assistant", avatar="🗑️"):
                        st.write(f"⚠️ **ต้องการลบรายการ ID: {tx_id_delete} ใช่ไหม?**")
                        
                        # 👇 แก้ตรงนี้! ใช้ on_click แทน
                        st.button(
                            "ยืนยันการลบ (Confirm Delete)", 
                            type="primary",
                            on_click=delete_callback,  # เรียกฟังก์ชันลบ
                            args=(tx_id_delete,)       # ส่ง ID ไปให้ฟังก์ชัน
                        )
        else:
            st.info("No withdrawals.")

if st.session_state.logged_in:
    main_page()
else:
    if st.session_state.show_register:
        register_page()
    else:
        login_page()