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
    return {"target_savings": 2000.0, "target_expense": 3000.0, "api_key": ""}

def save_settings(settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

# ==========================================
# 2. 页面基本配置 & 沉浸式高级 CSS 魔法
# ==========================================
st.set_page_config(page_title="咔嚓记账 - 极简智能账本", page_icon="🦈", layout="centered")

st.markdown("""
<style>
/* 隐藏顶部默认 Header，视野更开阔 */
header {visibility: hidden;}

/* --- 🌟 UI升级：原生级底部悬浮导航栏 --- */
div[data-testid="stRadio"] {
    position: fixed;
    bottom: 0;
    left: 0;
    width: 100vw;
    background-color: rgba(255, 255, 255, 0.90); /* 微微透明 */
    backdrop-filter: blur(15px); /* 苹果级毛玻璃特效 */
    padding: 12px 0 calc(15px + env(safe-area-inset-bottom)) 0;
    border-top: 1px solid rgba(0,0,0,0.05); /* 顶部极其细腻的分割线 */
    box-shadow: 0 -5px 20px rgba(0,0,0,0.03);
    z-index: 9999;
    margin: 0;
}
/* 隐藏标题 */
div[data-testid="stRadio"] > label { display: none !important; }
/* 均分按钮空间 */
div[role="radiogroup"] { display: flex; justify-content: space-evenly; width: 100%; gap: 0; }
/* 🔥 隐藏默认的单选框圆点，让它看起来像真正的 App 按钮！ */
div[role="radiogroup"] label > div:first-child { display: none !important; }
/* 优化按钮文字的排版和点击区域 */
div[role="radiogroup"] label { 
    flex-direction: column; 
    justify-content: center; 
    align-items: center; 
    padding: 8px 10px;
    background: transparent !important;
    border: none !important;
    font-weight: 600 !important;
}

/* 底部防遮挡留白 */
.block-container { padding-bottom: 130px !important; padding-top: 10px !important; }

/* --- 完美融入的鲨鱼黄头部 --- */
section.main div[data-testid="stHorizontalBlock"]:first-of-type {
    background-color: #fcd535;
    padding: 25px 20px 20px 20px;
    border-radius: 24px; /* 更圆润更可爱 */
    box-shadow: 0 8px 20px rgba(252, 213, 53, 0.2); /* 增加同色系发光阴影 */
    margin-bottom: 30px;
    align-items: center;
}
section.main div[data-testid="stHorizontalBlock"]:first-of-type div[data-baseweb="select"] > div {
    background-color: transparent !important;
    border: none !important;
    box-shadow: none !important;
    cursor: pointer;
}
section.main div[data-testid="stHorizontalBlock"]:first-of-type div[data-baseweb="select"] span {
    font-size: 38px !important;
    font-weight: 900 !important;
    color: #222 !important;
}
section.main div[data-testid="stHorizontalBlock"]:first-of-type div[data-testid="stMetric"] label {
    color: #666 !important;
    font-size: 13px !important;
}
section.main div[data-testid="stHorizontalBlock"]:first-of-type div[data-testid="stMetric"] div {
    color: #222 !important;
    font-size: 26px !important;
    font-weight: 700 !important;
}
</style>
""", unsafe_allow_html=True)

if 'ledger_data' not in st.session_state: st.session_state.ledger_data = load_data()
if 'user_settings' not in st.session_state: st.session_state.user_settings = load_settings()
if 'parsed_results' not in st.session_state: st.session_state.parsed_results = None
if 'review_index' not in st.session_state: st.session_state.review_index = 0
if 'uploader_key' not in st.session_state: st.session_state.uploader_key = 0

# ==========================================
# 3. 侧边栏设置
# ==========================================
with st.sidebar:
    st.header("⚙️ 账户与设置")
    saved_api_key = st.session_state.user_settings.get("api_key", "")
    api_key = st.text_input("🔑 Google Gemini API Key:", value=saved_api_key, type="password")
    if api_key != saved_api_key:
        st.session_state.user_settings["api_key"] = api_key
        save_settings(st.session_state.user_settings)
        
    st.markdown("---")
    st.subheader("🎯 财务目标")
    current_savings = st.session_state.user_settings.get("target_savings", 2000.0)
    current_expense = st.session_state.user_settings.get("target_expense", 3000.0)
    target_savings = st.number_input("💰 每月预计存多少钱 (¥)", min_value=0.0, value=float(current_savings), step=500.0)
    target_expense = st.number_input("💸 每月最多花多少钱 (¥)", min_value=0.0, value=float(current_expense), step=500.0)
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
# 4. 全局数据预处理 & 月份计算
# ==========================================
has_data = len(st.session_state.ledger_data) > 0
now = datetime.datetime.now()
real_current_ym = now.strftime("%Y-%m")

if has_data:
    df = pd.DataFrame(st.session_state.ledger_data)
    if "收支" not in df.columns: df["收支"] = "支出"
    
    df['金额 (¥)'] = pd.to_numeric(df['金额 (¥)'], errors='coerce').fillna(0.0)
    df['时间'] = pd.to_datetime(df['时间'], errors='coerce')
    df['日期'] = df['时间'].dt.date
    df['月份'] = df['时间'].dt.strftime("%Y-%m")
    
    all_months = sorted(df['月份'].dropna().unique().tolist(), reverse=True)
    if real_current_ym not in all_months: all_months.insert(0, real_current_ym)
    
    total_income_all = df[df["收支"] == "收入"]["金额 (¥)"].sum()
    total_expense_all = df[df["收支"] == "支出"]["金额 (¥)"].sum()
    balance_all = total_income_all - total_expense_all
else:
    df = pd.DataFrame()
    all_months = [real_current_ym]
    total_income_all = total_expense_all = balance_all = 0.0

# ==========================================
# 5. 🔥 核心修复：把导航栏提前到最前面，彻底消灭滞后感！
# ==========================================
nav_options = ["📊 明细", "✍️ 记账", "📸 识图", "📈 分析"]

# 直接在这里获取用户的点击，后面的代码立马就能用这个最新的状态，0延迟！
current_nav = st.radio(
    "底部导航", 
    nav_options, 
    horizontal=True, 
    label_visibility="collapsed"
)

# ==========================================
# 6. 顶部组件：鲨鱼黄卡片
# ==========================================
header_c1, header_c2, header_c3 = st.columns([1.5, 1, 1])

with header_c1:
    disp_year = all_months[0].split("-")[0] + "年"
    st.markdown(f"<div style='color:#555; font-size:14px; margin-bottom:-15px; padding-left:15px;'>{disp_year}</div>", unsafe_allow_html=True)
    
    selected_ym = st.selectbox(
        "月份", 
        all_months, 
        label_visibility="collapsed",
        format_func=lambda x: x.split("-")[1] + "月 ▾"
    )

month_income = 0.0
month_expense = 0.0
if has_data:
    df_selected_month = df[df['月份'] == selected_ym]
    month_income = df_selected_month[df_selected_month["收支"] == "收入"]["金额 (¥)"].sum()
    month_expense = df_selected_month[df_selected_month["收支"] == "支出"]["金额 (¥)"].sum()

with header_c2:
    st.metric("本月收入", f"{month_income:.2f}")
with header_c3:
    st.metric("本月支出", f"{month_expense:.2f}")

# ==========================================
# 7. AI 逻辑与去重处理 (2.5 引擎)
# ==========================================
def analyze_receipt_with_ai(image, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    prompt = """提取图中所有流水记录。返回 JSON 数组格式：
    [ { "merchant": "星巴克", "type": "支出", "amount": 35.00, "time": "2026-03-11 14:30", "category": "餐饮" } ]"""
    try:
        response = model.generate_content([prompt, image])
        return json.loads(response.text.replace("```json", "").replace("```", "").strip())
    except Exception as e:
        return {"error": str(e)}

def filter_duplicates(ai_results, ledger):
    filtered, dup_count = [], 0
    for item in ai_results:
        is_dup = False
        for record in ledger:
            try:
                if float(item.get('amount', 0)) == float(record.get('金额 (¥)', 0)) and \
                   str(item.get('time', ''))[:10] == str(record.get('时间', ''))[:10]:
                    is_dup = True
                    break
            except: pass
        if is_dup: dup_count += 1
        else: filtered.append(item)
    return filtered, dup_count

@st.dialog("📝 AI账单逐条核对", width="large")
def confirm_dialog():
    res = st.session_state.parsed_results
    total = len(res)
    idx = st.session_state.review_index
    item = res[idx]
    
    if total - idx > 1: 
        if st.button(f"⚡ 信任 AI：一键直接入账剩余的 {total - idx} 笔", type="secondary", use_container_width=True):
            formatted_rest = [{"时间": r.get("time", ""), "收支": r.get("type", "支出"), "商家": r.get("merchant", ""), "分类": r.get("category", "其他"), "金额 (¥)": float(r.get("amount", 0.0))} for r in res[idx:]]
            st.session_state.ledger_data.extend(formatted_rest)
            save_data(st.session_state.ledger_data)
            st.session_state.parsed_results = None
            st.session_state.review_index = 0
            st.session_state.uploader_key += 1
            st.balloons()
            st.success("✅ 剩余账单已全部一键入账！")
            st.rerun()
            
    st.progress((idx + 1) / total)
    st.caption(f"正在核对：第 {idx + 1} 笔 / 共 {total} 笔")

    with st.form(key=f"review_{idx}"):
        color = "#ff4b4b" if item.get("type", "支出") == "支出" else "#00c04b"
        st.markdown(f"""
        <div style='background: {color}15; padding: 15px; border-radius: 10px; border-left: 6px solid {color}; margin-bottom: 20px;'>
            <div style='font-size: 32px; font-weight: 900; color: {color};'>¥ {float(item.get('amount', 0)):.2f}</div>
        </div>
        """, unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns(3)
        merch = c1.text_input("🏪 商家", value=item.get("merchant", ""))
        opts = ["支出", "收入"]
        tx_type = c2.selectbox("🏷️ 类型", opts, index=opts.index(item.get("type", "支出")) if item.get("type") in opts else 0)
        amt = c3.number_input("✏️ 金额", value=float(item.get("amount", 0.0)), format="%.2f")
        
        c4, c5 = st.columns(2)
        tm = c4.text_input("⏰ 时间", value=item.get("time", ""))
        cat = c5.text_input("📂 分类", value=item.get("category", "其他"))
        
        b1, b2, b3 = st.columns([1, 1, 1.5])
        with b1: btn_del = st.form_submit_button("🗑️ 删除此条")
        with b2: btn_prev = st.form_submit_button("⬅️ 上一条") if idx > 0 else False
        with b3: btn_next = st.form_submit_button("✅ 确认并下一条" if idx < total - 1 else "💾 全部保存", type="primary")
            
        if btn_del:
            st.session_state.parsed_results.pop(idx)
            if len(st.session_state.parsed_results) == 0:
                st.session_state.parsed_results = None
                st.session_state.review_index = 0
                st.session_state.uploader_key += 1 
            elif idx >= len(st.session_state.parsed_results):
                st.session_state.ledger_data.extend(st.session_state.parsed_results)
                save_data(st.session_state.ledger_data)
                st.session_state.parsed_results = None
                st.session_state.review_index = 0
                st.session_state.uploader_key += 1 
                st.balloons()
            st.rerun()

        elif btn_prev:
            st.session_state.parsed_results[idx] = {"时间": tm, "收支": tx_type, "商家": merch, "分类": cat, "金额 (¥)": amt}
            st.session_state.review_index -= 1 
            st.rerun()

        elif btn_next:
            st.session_state.parsed_results[idx] = {"时间": tm, "收支": tx_type, "商家": merch, "分类": cat, "金额 (¥)": amt}
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
# 8. 主体内容渲染 (毫无迟滞的页面切换)
# ==========================================

if current_nav == "📊 明细":
    if not has_data:
        st.info("📭 暂无流水，快去记一笔吧！")
    else:
        st.caption("💡 点击表头【时间↕】或【金额↕】即可排序。勾选最右侧可删除数据。")
        display_df = df.drop(columns=['日期', '月份'], errors='ignore').copy()
        display_df["🗑️ 勾选删除"] = False 
        display_df['时间'] = pd.to_datetime(display_df['时间'], errors='coerce')
        display_df['金额 (¥)'] = pd.to_numeric(display_df['金额 (¥)'], errors='coerce')
        
        edited_df = st.data_editor(
            display_df, 
            use_container_width=True, 
            num_rows="dynamic",
            hide_index=True, 
            column_config={
                "🗑️ 勾选删除": st.column_config.CheckboxColumn("🗑️ 勾选删除", default=False),
                "时间": st.column_config.DatetimeColumn("时间 ↕", format="YYYY-MM-DD HH:mm:ss"),
                "金额 (¥)": st.column_config.NumberColumn("金额 ↕", format="%.2f")
            }
        )
        
        if st.button("💾 确认删除 / 保存修改", type="primary", use_container_width=True):
            final_df = edited_df[edited_df["🗑️ 勾选删除"] == False].copy()
            final_df = final_df.drop(columns=["🗑️ 勾选删除"], errors='ignore')
            final_df['时间'] = pd.to_datetime(final_df['时间'], errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S')
            final_df = final_df.fillna("")
            st.session_state.ledger_data = final_df.to_dict(orient="records")
            save_data(st.session_state.ledger_data)
            st.success("✅ 操作已永久生效！")
            st.rerun()

elif current_nav == "✍️ 记账":
    with st.container(border=True):
        with st.form("manual_entry_form", clear_on_submit=True):
            f_col1, f_col2 = st.columns(2)
            m_type = f_col1.radio("收支类型", ["支出", "收入"], horizontal=True)
            m_amount = f_col2.number_input("金额 (¥)", min_value=0.0, format="%.2f", step=10.0)
            m_merchant = st.text_input("商家名称 / 备注")
            f_col3, f_col4 = st.columns(2)
            m_category = f_col3.selectbox("分类", ["餐饮", "交通", "购物", "居住", "娱乐", "投资", "工资", "退款", "转账", "其他"])
            m_time = f_col4.text_input("时间", value="现时", help="保持为 '现时' 将自动抓取精确时间")
            
            if st.form_submit_button("✅ 保存这笔账单", use_container_width=True, type="primary"):
                if m_amount <= 0: st.error("金额不能为 0 呀！")
                else:
                    final_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") if m_time == "现时" else m_time
                    st.session_state.ledger_data.append({"时间": final_time, "收支": m_type, "商家": m_merchant, "分类": m_category, "金额 (¥)": m_amount})
                    save_data(st.session_state.ledger_data)
                    st.success(f"已成功入账：¥ {m_amount}！")
                    st.rerun()

elif current_nav == "📸 识图":
    with st.container(border=True):
        uploaded_file = st.file_uploader("支持微信/支付宝截图与小票", type=["jpg", "jpeg", "png", "webp"], key=f"uploader_{st.session_state.uploader_key}")
        if uploaded_file is not None:
            st.image(Image.open(uploaded_file), use_container_width=True)
            if not api_key:
                st.warning("⚠️ 请先在左侧抽屉设置 API Key")
            else:
                if st.button("🚀 呼叫大模型提取 (Gemini 2.5)", use_container_width=True, type="primary"):
                    with st.spinner("2.5 超强引擎全速解析中..."):
                        raw_results = analyze_receipt_with_ai(Image.open(uploaded_file), api_key)
                        if "error" not in raw_results:
                            filtered_results, dup_count = filter_duplicates(raw_results, st.session_state.ledger_data)
                            if dup_count > 0: st.toast(f"🛡️ 已拦截 {dup_count} 条重复账单！", icon="🚫")
                            if not filtered_results: st.warning("⚠️ 提取的账单已全部存在于库中。")
                            else:
                                st.session_state.parsed_results = filtered_results
                                st.session_state.review_index = 0
                                st.rerun()
                        else:
                            st.error(f"解析失败: {raw_results['error']}")
                        
    if st.session_state.parsed_results is not None: confirm_dialog() 

elif current_nav == "📈 分析":
    if not has_data:
        st.info("📭 暂无数据可分析")
    else:
        disp_month_text = selected_ym.split("-")[1] + "月"
        month_balance = month_income - month_expense
        st.markdown(f"#### 🎯 【{disp_month_text}】预算防线")
        g1, g2 = st.columns(2)
        with g1:
            st.caption("💰 本月存款进度")
            sav_pct = max(0.0, min(1.0, month_balance / target_savings)) if target_savings > 0 else 0
            st.progress(sav_pct)
            st.write(f"¥{month_balance:.2f} / ¥{target_savings}")
        with g2:
            st.caption("💸 本月支出红线")
            exp_pct = min(1.0, month_expense / target_expense) if target_expense > 0 else 0
            st.progress(exp_pct)
            st.write(f"¥{month_expense:.2f} / ¥{target_expense}")
        
        st.markdown("---")
        exp_df = df[df["收支"] == "支出"]
        if not exp_df.empty:
            c1, c2 = st.columns(2)
            with c1:
                fig_pie = px.pie(exp_df.groupby('分类')['金额 (¥)'].sum().reset_index(), values='金额 (¥)', names='分类', hole=0.4, title="所有历史支出分布")
                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig_pie, use_container_width=True)
            with c2:
                fig_line = px.line(exp_df.groupby('日期')['金额 (¥)'].sum().reset_index(), x='日期', y='金额 (¥)', markers=True, title="每日支出趋势")
                st.plotly_chart(fig_line, use_container_width=True)
