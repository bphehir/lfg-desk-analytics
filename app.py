import streamlit as st
import pandas as pd
import os
from datetime import datetime

# ==========================================
#       STREAMLIT PAGE INITIALIZATION
# ==========================================
st.set_page_config(
    page_title="LFG Desk Analytics Platform",
    page_icon="📊",
    layout="wide", 
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
        .block-container { padding-top: 1.5rem; padding-bottom: 1rem; padding-left: 3rem; padding-right: 3rem; }
        .metric-card {
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
            padding: 15px 20px;
            border-radius: 6px;
            margin-bottom: 20px;
        }
        .metric-title {
            font-family: 'Calibri', sans-serif;
            font-size: 11pt;
            color: #64748b;
            text-transform: uppercase;
            font-weight: 600;
            letter-spacing: 0.5px;
        }
        .metric-value {
            font-family: 'Calibri', sans-serif;
            font-size: 20pt;
            font-weight: 700;
            color: #0f172a;
            margin-top: 5px;
        }
    </style>
""", unsafe_allow_html=True)

def format_accounting(val, is_currency=True, is_percent=False, decimals=0):
    if pd.isna(val) or val == "" or val == "-":
        return "-"
    try:
        num = float(val)
        if num == 0:
            if is_percent: return "0.00%"
            if is_currency: return f"$0.00" if decimals > 0 else "$0"
            return "0"
            
        if is_percent:
            return f"{num * 100:.2f}%" if num < 1 else f"{num:.2f}%"
            
        if num < 0:
            abs_num = abs(num)
            if decimals > 0:
                return f"(${abs_num:,.{decimals}f})" if is_currency else f"({abs_num:,.{decimals}f})"
            else:
                return f"(${abs_num:,.0f})" if is_currency else f"({abs_num:,.0f})"
        else:
            if decimals > 0:
                return f"${num:,.{decimals}f}" if is_currency else f"{num:,.{decimals}f}"
            else:
                return f"${num:,.0f}" if is_currency else f"{num:,.0f}"
    except:
        return str(val)

# ==========================================
#             DATA LOADING (CLOUD API)
# ==========================================
import requests

# Your PythonAnywhere web credentials
PA_USER = "cNvbHgjPd"
PA_PASS = "NLjdsd89K"
URL = "https://ibn2025.pythonanywhere.com/data/LFG_Historical_Database.csv"

@st.cache_data(ttl=3600)  # Caches data for 1 hour so it stays fast but picks up nightly updates
def load_cloud_data():
    try:
        # Securely request the file from your PythonAnywhere storage
        response = requests.get(URL, auth=(PA_USER, PA_PASS))
        if response.status_code == 200:
            # Read the CSV stream directly into a pandas DataFrame
            from io import StringIO
            df_cloud = pd.read_csv(StringIO(response.text))
            df_cloud['Date'] = pd.to_datetime(df_cloud['Date'])
            return df_cloud
        else:
            st.error(f"Failed to fetch cloud database. Status Code: {response.status_code}")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Connection error to data feed: {str(e)}")
        return pd.DataFrame()

df = load_cloud_data()

# Fallback structure perfectly mirroring your real production database columns
if df.empty:
    st.warning("Displaying fallback framework snapshot.")
    df = pd.DataFrame({
        'Date': [pd.to_datetime('2026-06-12')]*6,
        'Account': ['Hehir', 'Hehir_Tax', 'Polverino', 'Polverino_Tax', 'LFG', 'Natale'],
        'Par Value': [4605000, -1750000, 7425000, 0, 1980000, 500000],
        'Mkt Value': [4067275.50, -1713932.50, 7526219.15, 0, 1933996.25, 485116.45],
        'DV01': [4231, 1348, 7000, 0, 2492, 294],
        'Cash PnL': [2727.80, 0, 6612.00, 0, 3350.00, 138.25],       # Fixed spelling
        'Daily Accrued': [205.37, 0, 972.98, 0, 249.50, 54.07],
        'Daily CoC': [-243.38, 0, -1248.77, 0, -253.37, -64.50],
        'Tickets': [11, 0, 3, 0, 1, 11],
        'Line Items': [24, 0, 13, 0, 3, 13],
        'Day Buy': [2280000, 0, 0, 0, 0, 60000],
        'Day Sell': [480000, 0, 1895000, 0, 500000, 85000],
        'Hedge Ratio': [0.246, 0, 0.184, 0, 0, 0]
    })
# ==========================================
#         HEADER & CONTROL PANEL
# ==========================================
st.title("LFG Fixed Income Desk Analytics")

min_date = df['Date'].min().date()
max_date = df['Date'].max().date()

col_date, col_spacer = st.columns([3, 7])
with col_date:
    date_selection = st.date_input(
        "Select Date Range:",
        value=(max_date, max_date),
        min_value=min_date,
        max_value=max_date
    )

# Handle single vs multiple date selections from the UI widget
if len(date_selection) == 2:
    start_date, end_date = date_selection
elif len(date_selection) == 1:
    start_date = end_date = date_selection[0]
else:
    start_date = end_date = max_date

# Filter underlying dataset down to selected run window
mask = (df['Date'].dt.date >= start_date) & (df['Date'].dt.date <= end_date)
range_df = df[mask].copy()

# ==========================================
#      DYNAMIC AGGREGATION ENGINE
# ==========================================
agg_rows = []
unique_accounts = range_df['Account'].unique()

for acct in unique_accounts:
    acct_df = range_df[range_df['Account'] == acct]
    
    # Position metrics grab the value from the LATEST date in the range
    latest_row = acct_df.sort_values('Date').iloc[-1]
    
    # Flow metrics SUM the values across the ENTIRE range
    sum_pnl = acct_df['Cash PnL'].sum()
    sum_accrued = acct_df['Daily Accrued'].sum()
    sum_buy = acct_df['Day Buy'].sum()
    sum_sell = acct_df['Day Sell'].sum()
    sum_tickets = acct_df['Tickets'].sum()
    
    # Safely coerce CoC in case of "-" text strings in the tax books
    sum_coc = pd.to_numeric(acct_df['Daily CoC'], errors='coerce').fillna(0).sum()

    agg_rows.append({
        'Account': acct,
        'Par Value': latest_row['Par Value'],
        'Mkt Value': latest_row['Mkt Value'],
        'DV01': latest_row['DV01'],
        'Hedge Ratio': latest_row.get('Hedge Ratio', 0),
        'Line Items': latest_row['Line Items'],
        'Day Buy': sum_buy,
        'Day Sell': sum_sell,
        'Cash PnL': sum_pnl,
        'Daily Accrued': sum_accrued,
        'Daily CoC': sum_coc,
        'Tickets': sum_tickets
    })

agg_df = pd.DataFrame(agg_rows)

if not agg_df.empty:
    # ==========================================
    #     TOP-LEVEL AGGREGATE RISK CARDS
    # ==========================================
    long_df = agg_df[~agg_df['Account'].str.contains('Tax', na=False)]

    long_par = long_df['Par Value'].sum()
    long_mkt = long_df['Mkt Value'].sum()
    total_pnl = agg_df['Cash PnL'].sum() 
    long_dv01 = long_df['DV01'].sum()

    card1, card2, card3, card4 = st.columns(4)
    with card1:
        st.markdown(f'<div class="metric-card"><div class="metric-title">Long Total Par</div><div class="metric-value">{format_accounting(long_par, is_currency=False)}</div></div>', unsafe_allow_html=True)
    with card2:
        st.markdown(f'<div class="metric-card"><div class="metric-title">Long Market Value</div><div class="metric-value">{format_accounting(long_mkt, is_currency=True)}</div></div>', unsafe_allow_html=True)
    with card3:
        st.markdown(f'<div class="metric-card"><div class="metric-title">Combined Cash PnL</div><div class="metric-value">{format_accounting(total_pnl, is_currency=True, decimals=2)}</div></div>', unsafe_allow_html=True)
    with card4:
        st.markdown(f'<div class="metric-card"><div class="metric-title">Long DV01</div><div class="metric-value">{format_accounting(long_dv01, is_currency=False)}</div></div>', unsafe_allow_html=True)

    # ==========================================
    #     CONSOLIDATED POSITION RECORD BLOCKS
    # ==========================================
    st.subheader("Performance & Position Grid Breakdown")

    ui_rows = []
    for _, r in agg_df.iterrows():
        acct = r['Account']
        
        display_name = acct
        if acct == "Hehir_Tax": display_name = "&nbsp;&nbsp;&nbsp;&nbsp;Hehir Hedge"
        elif acct == "Polverino_Tax": display_name = "&nbsp;&nbsp;&nbsp;&nbsp;Polverino Hedge"
        
        hr_val = r.get('Hedge Ratio', 0)
        coc_val = r.get('Daily CoC', 0)

        ui_rows.append({
            "Book": display_name,
            "Par Value": format_accounting(r['Par Value'], is_currency=False),
            "Mkt Value": format_accounting(r['Mkt Value'], is_currency=True),
            "Day Buy": format_accounting(r['Day Buy'], is_currency=False),
            "Day Sell": format_accounting(r['Day Sell'], is_currency=False),
            "PnL": format_accounting(r['Cash PnL'], is_currency=True, decimals=2),
            "Accrued": format_accounting(r['Daily Accrued'], is_currency=True, decimals=2),
            "CoC": format_accounting(coc_val, is_currency=True, decimals=2) if "Tax" not in acct and coc_val != 0 else "-",
            "DV01": format_accounting(r['DV01'], is_currency=False),
            "Hedge Ratio": format_accounting(hr_val, is_currency=False, is_percent=True) if hr_val > 0 and "Tax" not in acct else "-",
            "Line Items": str(int(r['Line Items'])),
            "Tickets": str(int(r['Tickets']))
        })

    ui_df = pd.DataFrame(ui_rows)
    account_order_mapping = {"Hehir": 0, "&nbsp;&nbsp;&nbsp;&nbsp;Hehir Hedge": 1, "Polverino": 2, "&nbsp;&nbsp;&nbsp;&nbsp;Polverino Hedge": 3, "LFG": 4, "Natale": 5}
    ui_df['sort_idx'] = ui_df['Book'].map(account_order_mapping)
    ui_df = ui_df.sort_values('sort_idx').drop(columns=['sort_idx'])

    columns_order = [
        "Book", "Par Value", "Mkt Value", "Day Buy", "Day Sell", 
        "PnL", "Accrued", "CoC", "DV01", "Hedge Ratio", "Line Items", "Tickets"
    ]
    ui_df = ui_df[columns_order]

    st.markdown(f"""
        <div style="width: 100%; overflow-x: auto;">
            <table style="width:100%; border-collapse: collapse; font-family: 'Calibri', sans-serif; font-size: 10.5pt; color: #1e293b;">
                <thead>
                    <tr style="background-color: #1e3a8a; color: #ffffff; font-weight: bold; font-size: 10pt;">
                        {"".join([f'<th style="padding: 10px; text-align: left;">{col}</th>' if i==0 else f'<th style="padding: 10px; text-align: right;">{col}</th>' for i, col in enumerate(columns_order)])}
                    </tr>
                </thead>
                <tbody>
                    {"".join([
                        f'<tr style="background-color: {"#f8fafc" if idx % 2 == 1 else "#ffffff"}; border: 1px solid #e2e8f0;">' + 
                        "".join([
                            f'<td style="padding: 10px; text-align: left; font-weight: bold; color: #0f172a;">{val}</td>' if i==0 
                            else f'<td style="padding: 10px; text-align: right; color: #000000;">{val}</td>' 
                            for i, val in enumerate(row)
                        ]) + "</tr>" 
                        for idx, row in enumerate(ui_df.values)
                    ])}
                </tbody>
            </table>
        </div>
    """, unsafe_allow_html=True)
else:
    st.warning("No data available for the selected date range.")
