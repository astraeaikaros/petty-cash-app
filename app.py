import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import re

st.set_page_config(page_title="零用金系統", layout="wide")

# 隱藏右上角選單與頁尾，並美化資料表與整體風格
custom_style = """
    <style>
    #MainMenu, footer, header {visibility: hidden;}
    .css-1rs6os.edgvbvh3 {padding-top: 2rem;}
    .stApp {background-color: #f9f9f9; font-family: 'Microsoft JhengHei', sans-serif;}
    h1, h2, h3, h4, h5, h6 {color: #30475e;}
    .stButton>button {
        background-color: #1976d2;
        color: white;
        border-radius: 0.5rem;
        padding: 0.4rem 1rem;
        border: none;
    }
    .stButton>button:hover {
        background-color: #1565c0;
    }
    .stDataFrameContainer {
        border-radius: 0.5rem;
        overflow: hidden;
        box-shadow: 0 0 10px rgba(0,0,0,0.05);
        display: flex;
        justify-content: center;
    }
    .stMarkdown {font-size: 1.1rem;}
    table td, table th {
        text-align: center !important;
        vertical-align: middle !important;
    }
    </style>
"""
st.markdown(custom_style, unsafe_allow_html=True)

# 建立 SQLite 資料庫連線
conn = sqlite3.connect("data.db", check_same_thread=False)

def create_table():
    conn.execute("""
        CREATE TABLE IF NOT EXISTS petty_cash (
            日期 TEXT,
            姓名 TEXT,
            機構摘要 TEXT,
            莊交辦摘要 TEXT,
            陳交辦摘要 TEXT,
            各機構金額 REAL,
            自用金額 REAL,
            総金額 REAL,
            上傳時間 TEXT
        )
    """)
    conn.commit()

create_table()

# 預設頁面為查詢資料
page = st.sidebar.radio("請選擇功能", ["🔍 查詢資料", "📥 匯入資料"])

if page == "📥 匯入資料":
    st.title("📥 匯入零用金資料")
    uploaded_file = st.file_uploader("📂 請拖曳或點擊以上傳 Excel 檔案（副檔名為 .xlsx）", type=["xlsx"], label_visibility="visible")

    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file, sheet_name=0, skiprows=3, dtype=str)
            df = df.iloc[:, :8]  # 只保留前 8 欄

            df = df.rename(columns={
                df.columns[0]: '日期',
                df.columns[1]: '姓名',
                df.columns[2]: '機構摘要',
                df.columns[3]: '莊交辦摘要',
                df.columns[4]: '陳交辦摘要',
                df.columns[5]: '各機構金額',
                df.columns[6]: '自用金額',
                df.columns[7]: '總金額_原始'
            })

            df['姓名'] = df['姓名'].ffill()
            df['各機構金額'] = pd.to_numeric(df['各機構金額'], errors='coerce').fillna(0)
            df['自用金額'] = pd.to_numeric(df['自用金額'], errors='coerce').fillna(0)
            df['總金額'] = df['各機構金額'] + df['自用金額']
            df['上傳時間'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 過濾出正確的日期格式資料
            total_rows = len(df)
            df = df[
                df['日期'].notna() &
                df['日期'].str.match(r"^\d{2,3}\.\d{2}\.\d{2}$")
            ]
            valid_rows = len(df)
            skipped_rows = total_rows - valid_rows

            for col in ['機構摘要', '莊交辦摘要', '陳交辦摘要']:
                df[col] = df[col].fillna('').astype(str).str.strip()

            st.dataframe(df)

            if st.button("📥 匯入資料"):
                df_to_save = df[['日期', '姓名', '機構摘要', '莊交辦摘要', '陳交辦摘要', '各機構金額', '自用金額', '總金額', '上傳時間']]
                df_to_save.to_sql("petty_cash", conn, if_exists="append", index=False)
                st.success(f"✅ 成功寫入資料，共 {len(df_to_save)} 筆")
                if skipped_rows > 0:
                    st.warning(f"⚠️ 有 {skipped_rows} 筆資料因日期格式錯誤未匯入。")

        except Exception as e:
            st.error(f"❌ 讀取檔案失敗：{e}")

elif page == "🔍 查詢資料":
    st.title("🔍 杏和零用金查詢")
    df_result = pd.read_sql_query("SELECT * FROM petty_cash", conn)

    # 日期轉換
    def convert_to_datetime(date_str):
        try:
            match = re.match(r"^(\d{2,3})\.(\d{1,2})\.(\d{1,2})$", date_str)
            if match:
                year, month, day = match.groups()
                year = int(year)
                year = year + 1911 if year < 1911 else year
                return datetime(year, int(month), int(day))
        except:
            pass
        return pd.NaT

    df_result['日期_轉換'] = df_result['日期'].apply(convert_to_datetime)

    if df_result['日期_轉換'].notna().sum() == 0:
        st.warning("⚠️ 沒有可辨識的日期欄位，請確認資料格式正確。")
        st.stop()

    min_date = df_result['日期_轉換'].min()
    max_date = df_result['日期_轉換'].max()
    start_date, end_date = st.date_input("📅 請選擇日期區間", [min_date, max_date])

    df_result = df_result[(df_result['日期_轉換'] >= pd.to_datetime(start_date)) & (df_result['日期_轉換'] <= pd.to_datetime(end_date))]

    # 新增姓名篩選
    unique_names = df_result['姓名'].dropna().unique().tolist()
    selected_name = st.selectbox("👤 請選擇姓名 (可選)", ["全部"] + unique_names)
    if selected_name != "全部":
        df_result = df_result[df_result['姓名'] == selected_name]

    col1, col2, col3 = st.columns(3)
    with col1:
        filter_mechanism = st.checkbox("機構")
    with col2:
        filter_dr_zhuang = st.checkbox("DR莊交辦")
    with col3:
        filter_dr_chen = st.checkbox("DR陳交辦")

    if filter_mechanism or filter_dr_zhuang or filter_dr_chen:
        condition = pd.Series(False, index=df_result.index)
        if filter_mechanism:
            condition |= df_result['機構摘要'].str.strip() != ''
        if filter_dr_zhuang:
            condition |= df_result['莊交辦摘要'].str.strip() != ''
        if filter_dr_chen:
            condition |= df_result['陳交辦摘要'].str.strip() != ''
        df_result = df_result[condition]

    df_result['摘要'] = (
        df_result['機構摘要'].fillna('') +
        df_result['莊交辦摘要'].fillna('') +
        df_result['陳交辦摘要'].fillna('')
    )

    # 顯示查詢結果
    st.write(f"🔎 查詢結果共 {len(df_result)} 筆")
    df_result['民國日期'] = df_result['日期_轉換'].apply(lambda x: f"{x.year - 1911}.{x.month:02}.{x.day:02}" if pd.notna(x) else "")
    df_display = df_result[['民國日期', '姓名', '摘要', '各機構金額', '自用金額', '總金額', '上傳時間']].copy()
    df_display.index = df_display.index + 1  # 索引從 1 開始
    st.dataframe(df_display, use_container_width=True)

    st.markdown("---")
    st.markdown(f"💰 **總金額合計：{df_result['總金額'].sum():,.0f} 元**")
