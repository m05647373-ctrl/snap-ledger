import streamlit as st
from PIL import Image
import google.generativeai as genai
import json
import pandas as pd
import os
import datetime
import plotly.express as px

# ==========================================
# 1. 数据持久化：引入本地文件存储
# ==========================================
DATA_FILE = "ledger_data.json"
SETTINGS_FILE = "settings.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    # 新增：默认 API Key 为空字符串
    return {"target_savings": 2000.0, "target_expense": 3000.0, "api_key": ""}

def save_settings(settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

# ==========================================
# 2. 页面基本配置 & 状态初始化
# ==========================================
st.set_page_config(page_title="咔嚓记账 - 极简智能账本", page_icon="🦈", layout="centered")

if 'ledger_data' not in st.session_state:
    st.session_state.ledger_data = load_data()
if 'user_settings' not in st.session_state:
    st.session_state.user_settings = load_settings()
if 'parsed_results' not in st.session_state:
    st.session_state.parsed_results = None
if 'review_index' not in st.session_state:
    st.session_state.review_index = 0
if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

# ==========================================
# 3. 侧边栏：隐藏的高级设置 (新增 API Key 永久记忆)
# ==========================================
with st.sidebar:
    st.header("⚙️ 账户与设置")
    
    # 提取历史保存的 API Key
    saved_api_key = st.session_state.user_settings.get("api_key", "")
    
    # 将提取的值设为输入框的默认值
    api_key = st.text_input("🔑 Google Gemini API Key:", value=saved_api_key, type="password")
    
    # 如果用户输入了新的 Key，立刻存入本地文件！
    if api_key != saved_api_key:
        st.session_state.user_settings["api_key"] = api_key
        save_settings(st.session_state.user_settings)
        
    if api_key:
        st.success("✅ API Key 已安全保存在本地，下次打开免输入！")
    else:
        st.warning("💡 提示：请输入 API Key 以激活 AI 识图功能。")
        
    st.markdown("---")
    
    st.subheader("🎯 财务目标")
    current_savings = st.session_state.user_settings.get("target_savings", 2000.0)
    current_expense = st.session_state.user_settings.get("target_expense", 3000.0)
    
    target_savings = st.number_input("💰 本月预计存多少钱 (¥)", min_value=0.0, value=float(current_savings), step=500.0)
    target_expense = st.number_input("💸 本月最多花多少钱 (¥)", min_value=0.0, value=float(current_expense), step=500.0)
    
    if target_savings != current_savings or target_expense != current_expense:
        st.session_state.user_settings.update({"target_savings": target_savings, "target_expense": target_expense})
        save_settings(st.session_state.user_settings)
    
    st.markdown("---")
    if st.button("🗑️ 清空所有账单数据", use_container_width=True):
        st.session_state.ledger_data = []
        save_data([]) 
        st.session_state.parsed_results = None
        st.session_state.uploader_key += 1
        st.success("数据已彻底清空！")
        st.rerun()

# ==========================================
# 4. 核心预处理 & 当月数据计算 (鲨鱼记账头部)
# ==========================================
now = datetime.datetime.now()
current_month_str = now.strftime("%m月")
current_year_str = now.strftime("%Y年")

has_data = len(st.session_state.ledger_data) > 0

month_income = 0.0
month_expense = 0.0

if has_data:
    df = pd.DataFrame(st.session_state.ledger_data)
    if "收支" not in df.columns:
        df["收支"] = "支出"
    
    df['金额 (¥)'] = pd.to_numeric(df['金额 (¥)'], errors='coerce').fillna(0.0)
    df['时间'] = pd.to_datetime(df['时间'], errors='coerce')
    df['日期'] = df['时间'].dt.date
    df['月份'] = df['时间'].dt.strftime("%Y-%m")
    
    # 计算当月收支
    current_ym = now.strftime("%Y-%m")
    df_current_month = df[df['月份'] == current_ym]
    month_income = df_current_month[df_current_month["收支"] == "收入"]["金额 (¥)"].sum()
    month_expense = df_current_month[df_current_month["收支"] == "支出"]["金额 (¥)"].sum()
    
    # 历史总计
    total_income = df[df["收支"] == "收入"]["金额 (¥)"].sum()
    total_expense = df[df["收支"] == "支出"]["金额 (¥)"].sum()
    balance = total_income - total_expense
else:
    df = pd.DataFrame()
    total_income = total_expense = balance = 0.0

# ==========================================
# 5. UI 渲染：鲨鱼记账风格 Header
# ==========================================
st.markdown(f"""
<div style="background-color: #fcd535; padding: 25px 20px; border-radius: 20px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); margin-bottom: 25px;">
    <div style="color: #333; font-size: 20px; font-weight: bold; margin-bottom: 15px;">🦈 咔嚓记账</div>
    <div style="display: flex; justify-content: space-between; align-items: flex-end;">
        <div>
            <div style="color: #555; font-size: 14px;">{current_year_str}</div>
            <div style="color: #222; font-size: 32px; font-weight: bold;">{current_month_str} <span style="font-size:16px;">▾</span></div>
        </div>
        <div style="text-align: left; flex: 1; padding-left: 30px;">
            <div style="color: #555; font-size: 14px;">当月收入</div>
            <div style="color: #222; font-size: 24px; font-weight: 500;">{month_income:.2f}</div>
        </div>
        <div style="text-align: left; flex: 1;">
            <div style="color: #555; font-size: 14px;">当月支出</div>
            <div style="color: #222; font-size: 24px; font-weight: 500;">{month_expense:.2f}</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ==========================================
# 6. AI 弹窗逻辑
# ==========================================
def analyze_receipt_with_ai(image, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = """提取图中所有流水记录。返回 JSON 数组格式：
    [ { "merchant": "星巴克", "type": "支出", "amount": 35.00, "time": "2026-03-11 14:30", "category": "餐饮" } ]"""
    try:
        res = model.generate_content([prompt, image])
        return json.loads(res.text.replace("```json", "").replace("```", "").strip())
    except Exception as e:
        return {"error": str(e)}

@st.dialog("📝 AI账单逐条核对", width="large")
def confirm_dialog():
    res = st.session_state.parsed_results
    idx = st.session_state.review_index
    total = len(res)
    item = res[idx]
    
    st.progress((idx + 1) / total)
    st.caption(f"正在核对：第 {idx + 1} 笔 / 共 {total} 笔")

    with st.form(key=f"review_{idx}"):
        color = "#ff4b4b" if item.get("type", "支出") == "支出" else "#00c04b"
        st.markdown(f"""
        <div style='background: {color}15; padding: 15px; border-radius: 10px; border-left: 6px solid {color}; margin-bottom: 20px;'>
            <div style='font-size: 14px; color: #666;'>识别金额：</div>
            <div style='font-size: 32px; font-weight: 900; color: {color};'>¥ {float(item.get('amount', 0)):.2f}</div>
        </div>
        """, unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns(3)
        merch = c1.text_input("🏪 商家", value=item.get("merchant", ""))
        opts = ["支出", "收入"]
        m_type = c2.selectbox("🏷️ 类型", opts, index=opts.index(item.get("type", "支出")) if item.get("type") in opts else 0)
        amt = c3.number_input("✏️ 修改金额", value=float(item.get("amount", 0)), format="%.2f")
        
        c4, c5 = st.columns(2)
        tm = c4.text_input("⏰ 时间", value=item.get("time", ""))
        cat = c5.text_input("📂 分类", value=item.get("category", "其他"))
        
        st.markdown("---")
        b1, b2, b3 = st.columns([1, 1, 1.5])
        with b1:
            if st.form_submit_button("🗑️ 删除此条", use_container_width=True):
                st.session_state.parsed_results.pop(idx)
                if not st.session_state.parsed_results:
                    st.session_state.parsed_results = None
                st.session_state.review_index = max(0, idx - 1)
                st.rerun()
        with b2:
            if idx > 0 and st.form_submit_button("⬅️ 上一条", use_container_width=True):
                st.session_state.review_index -= 1
                st.rerun()
        with b3:
            btn_txt = "✅ 确认并保存" if idx == total - 1 else "➡️ 确认并下一条"
            if st.form_submit_button(btn_txt, use_container_width=True, type="primary"):
                st.session_state.parsed_results[idx] = {"时间": tm, "收支": m_type, "商家": merch, "分类": cat, "金额 (¥)": amt}
                if idx < total - 1:
                    st.session_state.review_index += 1
                else:
                    st.session_state.ledger_data.extend(st.session_state.parsed_results)
                    save_data(st.session_state.ledger_data)
                    st.session_state.parsed_results = None
                    st.session_state.review_index = 0
                    st.session_state.uploader_key += 1
                    st.balloons()
                st.rerun()

# ==========================================
# 7. UI 主体：四大核心 Tab
# ==========================================
tab_detail, tab_manual, tab_ai, tab_chart = st.tabs(["📊 财务明细", "➕ 记账", "📸 AI识图", "📈 数据表"])

# ----------------- Tab 1: 财务明细 -----------------
with tab_detail:
    if not has_data:
        st.info("📭 暂无数据，快去记一笔吧！")
    else:
        st.caption("💡 提示：可直接在表格修改，勾选最右侧复选框后点击底部按钮删除。")
        display_df = df.drop(columns=['日期', '月份'], errors='ignore').copy()
        display_df["🗑️ 勾选删除"] = False 
        
        edited_df = st.data_editor(
            display_df, 
            use_container_width=True, 
            num_rows="dynamic",
            hide_index=True,
            column_config={
                "🗑️ 勾选删除": st.column_config.CheckboxColumn("🗑️ 勾选删除", default=False),
                "时间": st.column_config.DatetimeColumn("时间", format="YYYY-MM-DD HH:mm:ss"),
                "金额 (¥)": st.column_config.NumberColumn("金额", format="%.2f")
            }
        )
        
        if st.button("💾 保存修改 / 批量删除", type="primary", use_container_width=True):
            final_df = edited_df[edited_df["🗑️ 勾选删除"] == False].copy()
            final_df = final_df.drop(columns=["🗑️ 勾选删除"], errors='ignore')
            final_df['时间'] = pd.to_datetime(final_df['时间'], errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S')
            final_df = final_df.fillna("")
            
            st.session_state.ledger_data = final_df.to_dict(orient="records")
            save_data(st.session_state.ledger_data)
            st.success("✅ 操作成功！")
            st.rerun()

# ----------------- Tab 2: 手动记账 -----------------
with tab_manual:
    with st.container(border=True):
        with st.form("manual_form", clear_on_submit=True):
            st.subheader("✍️ 记录一笔新账单")
            f1, f2 = st.columns(2)
            m_type = f1.radio("类型", ["支出", "收入"], horizontal=True)
            m_amt = f2.number_input("金额 (¥)", min_value=0.0, format="%.2f")
            m_merch = st.text_input("商家名称 / 备注")
            
            f3, f4 = st.columns(2)
            m_cat = f3.selectbox("分类", ["餐饮", "交通", "购物", "居住", "娱乐", "工资", "转账", "其他"])
            m_time_input = f4.text_input("时间", value="现时", help="保持 '现时' 将自动抓取当前精确时间")
            
            if st.form_submit_button("✅ 保存账单", use_container_width=True, type="primary"):
                if m_amt <= 0: st.error("金额不能为 0！")
                else:
                    final_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") if m_time_input == "现时" else m_time_input
                    st.session_state.ledger_data.append({"时间": final_time, "收支": m_type, "商家": m_merch, "分类": m_cat, "金额 (¥)": m_amt})
                    save_data(st.session_state.ledger_data)
                    st.success(f"已入账！")
                    st.rerun()

# ----------------- Tab 3: AI 识图 -----------------
with tab_ai:
    with st.container(border=True):
        st.subheader("📸 上传截图自动记账")
        up = st.file_uploader("支持微信/支付宝账单、消费小票", type=["jpg", "png", "jpeg"], key=f"up_{st.session_state.uploader_key}")
        if up:
            st.image(Image.open(up), use_container_width=True)
            if st.button("🚀 召唤 AI 解析", use_container_width=True, type="primary"):
                if not api_key: st.error("请先在左侧抽屉设置中输入 API Key")
                else:
                    with st.spinner("AI 正在施展魔法..."):
                        res = analyze_receipt_with_ai(Image.open(up), api_key)
                        if "error" in res: st.error(res["error"])
                        else:
                            st.session_state.parsed_results = res
                            st.session_state.review_index = 0
                            st.rerun()
                            
    if st.session_state.parsed_results: confirm_dialog()

# ----------------- Tab 4: 数据表 (图表与预算) -----------------
with tab_chart:
    if not has_data:
        st.info("暂无数据可分析")
    else:
        # 预算模块
        st.markdown("#### 🎯 当月预算监控")
        g1, g2 = st.columns(2)
        with g1:
            st.caption("💰 存款目标")
            sav_pct = max(0.0, min(1.0, balance / target_savings)) if target_savings > 0 else 0
            st.progress(sav_pct)
            st.write(f"当前结余: ¥{balance:.2f} / 目标: ¥{target_savings}")
        with g2:
            st.caption("💸 支出防线")
            exp_pct = min(1.0, month_expense / target_expense) if target_expense > 0 else 0
            st.progress(exp_pct)
            st.write(f"当月已花: ¥{month_expense:.2f} / 预算: ¥{target_expense}")
        
        st.markdown("---")
        # 图表模块
        exp_df = df[df["收支"] == "支出"]
        if not exp_df.empty:
            c1, c2 = st.columns(2)
            with c1:
                fig_pie = px.pie(exp_df.groupby('分类')['金额 (¥)'].sum().reset_index(), values='金额 (¥)', names='分类', hole=0.4, title="总支出分布")
                st.plotly_chart(fig_pie, use_container_width=True)
            with c2:
                fig_line = px.line(exp_df.groupby('日期')['金额 (¥)'].sum().reset_index(), x='日期', y='金额 (¥)', markers=True, title="每日支出趋势")
                st.plotly_chart(fig_line, use_container_width=True)
