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
# 2. 页面基本配置 & 原生级 CSS
# ==========================================
st.set_page_config(page_title="咔嚓记账 - 极简智能账本", page_icon="🦈", layout="centered")

st.markdown("""
<style>
header {visibility: hidden;}

/* 原生手机底部导航栏特效 */
div[data-testid="stRadio"] {
    position: fixed;
    bottom: 0; left: 0; width: 100vw;
    background-color: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(15px);
    padding: 10px 0 calc(15px + env(safe-area-inset-bottom)) 0;
    box-shadow: 0 -4px 15px rgba(0,0,0,0.05);
    z-index: 9999; margin: 0;
}
div[data-testid="stRadio"] > label { display: none !important; }
div[role="radiogroup"] { display: flex; justify-content: space-evenly; width: 100%; }
/* 隐藏原生单选框的小圆圈 */
div[role="radiogroup"] label > div:first-child { display: none !important; }
div[role="radiogroup"] label { padding: 8px; font-weight: bold !important; border: none !important; background: transparent !important; }

.block-container { padding-bottom: 120px !important; padding-top: 10px !important; }

/* 优雅的月份选择器样式 */
div[data-baseweb="select"] > div {
    background-color: #f5f6f8 !important;
    border-radius: 12px !important;
    border: none !important;
    font-weight: 800 !important;
    font-size: 18px !important;
}
</style>
""", unsafe_allow_html=True)

if 'ledger_data' not in st.session_state: st.session_state.ledger_data = load_data()
if 'user_settings' not in st.session_state: st.session_state.user_settings = load_settings()
if 'parsed_results' not in st.session_state: st.session_state.parsed_results = None
if 'review_index' not in st.session_state: st.session_state.review_index = 0
if 'uploader_key' not in st.session_state: st.session_state.uploader_key = 0
if 'nav_radio' not in st.session_state: st.session_state.nav_radio = "📊 明细"

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
        st.rerun()

# ==========================================
# 4. 全局数据预处理 & 月份提炼
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
else:
    df = pd.DataFrame()
    all_months = [real_current_ym]

# ==========================================
# 5. AI 逻辑与去重处理
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
        if st.button(f"⚡ 一键入账剩余 {total - idx} 笔", type="secondary", use_container_width=True):
            formatted_rest = [{"时间": r.get("time", ""), "收支": r.get("type", "支出"), "商家": r.get("merchant", ""), "分类": r.get("category", "其他"), "金额 (¥)": float(r.get("amount", 0.0))} for r in res[idx:]]
            st.session_state.ledger_data.extend(formatted_rest)
            save_data(st.session_state.ledger_data)
            st.session_state.parsed_results = None
            st.session_state.review_index = 0
            st.session_state.uploader_key += 1
            st.rerun()
            
    st.progress((idx + 1) / total)
    
    with st.form(key=f"review_{idx}"):
        color = "#ff4b4b" if item.get("type", "支出") == "支出" else "#00c04b"
        st.markdown(f"<div style='background:{color}15; padding:15px; border-left:6px solid {color}; margin-bottom:15px;'><h2 style='margin:0; color:{color};'>¥ {float(item.get('amount', 0)):.2f}</h2></div>", unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns(3)
        merch = c1.text_input("🏪 商家", value=item.get("merchant", ""))
        opts = ["支出", "收入"]
        tx_type = c2.selectbox("🏷️ 类型", opts, index=opts.index(item.get("type", "支出")) if item.get("type") in opts else 0)
        amt = c3.number_input("✏️ 金额", value=float(item.get("amount", 0.0)), format="%.2f")
        
        c4, c5 = st.columns(2)
        tm = c4.text_input("⏰ 时间", value=item.get("time", ""))
        cat = c5.text_input("📂 分类", value=item.get("category", "其他"))
        
        b1, b2, b3 = st.columns([1, 1, 1.5])
        with b1: btn_del = st.form_submit_button("🗑️ 删除")
        with b2: btn_prev = st.form_submit_button("⬅️ 上一条") if idx > 0 else False
        with b3: btn_next = st.form_submit_button("✅ 下一条" if idx < total - 1 else "💾 保存", type="primary")
            
        if btn_del:
            st.session_state.parsed_results.pop(idx)
            if len(st.session_state.parsed_results) == 0: st.session_state.parsed_results = None; st.session_state.review_index = 0
            elif idx >= len(st.session_state.parsed_results):
                st.session_state.ledger_data.extend(st.session_state.parsed_results)
                save_data(st.session_state.ledger_data)
                st.session_state.parsed_results = None; st.session_state.review_index = 0
            st.rerun()

        elif btn_prev:
            st.session_state.parsed_results[idx] = {"时间": tm, "收支": tx_type, "商家": merch, "分类": cat, "金额 (¥)": amt}
            st.session_state.review_index -= 1; st.rerun()

        elif btn_next:
            st.session_state.parsed_results[idx] = {"时间": tm, "收支": tx_type, "商家": merch, "分类": cat, "金额 (¥)": amt}
            if idx < total - 1: st.session_state.review_index += 1 
            else:
                st.session_state.ledger_data.extend(st.session_state.parsed_results)
                save_data(st.session_state.ledger_data)
                st.session_state.parsed_results = None; st.session_state.review_index = 0
            st.rerun()

# ==========================================
# 6. 路由系统：完全隔离的页面渲染
# ==========================================
nav = st.session_state.nav_radio

if nav == "📊 明细":
    # --- 1. 明细主页：独享黄色数据大卡片 ---
    c_sel, _ = st.columns([1.5, 2])
    with c_sel:
        # 完美解决串行：用下拉框原生合并年份与月份，干净利落！
        selected_ym = st.selectbox(
            "📅 切换月份", 
            all_months, 
            label_visibility="collapsed", 
            format_func=lambda x: f"📅 {x.split('-')[0]}年 {x.split('-')[1]}月 ▾"
        )

    month_income = 0.0
    month_expense = 0.0
    if has_data:
        df_selected_month = df[df['月份'] == selected_ym]
        month_income = df_selected_month[df_selected_month["收支"] == "收入"]["金额 (¥)"].sum()
        month_expense = df_selected_month[df_selected_month["收支"] == "支出"]["金额 (¥)"].sum()

    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #fcd535, #facc22); padding: 25px 25px; border-radius: 20px; box-shadow: 0 8px 15px rgba(252, 213, 53, 0.3); margin-bottom: 25px; margin-top: 5px;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div style="text-align: left;">
                <div style="color: #666; font-size: 14px; margin-bottom: 5px;">本月收入 (¥)</div>
                <div style="color: #222; font-size: 32px; font-weight: 900;">{month_income:.2f}</div>
            </div>
            <div style="text-align: right;">
                <div style="color: #666; font-size: 14px; margin-bottom: 5px;">本月支出 (¥)</div>
                <div style="color: #222; font-size: 32px; font-weight: 900;">{month_expense:.2f}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if not has_data:
        st.info("📭 暂无流水，快去底部记一笔吧！")
    else:
        st.caption("💡 点击表头【时间↕】或【金额↕】即可自动排序。")
        display_df = df.drop(columns=['日期', '月份'], errors='ignore').copy()
        display_df["🗑️ 删"] = False 
        
        display_df['时间'] = pd.to_datetime(display_df['时间'], errors='coerce')
        display_df['金额 (¥)'] = pd.to_numeric(display_df['金额 (¥)'], errors='coerce')
        # 【神级优化】：默认按最新时间排序排列
        display_df = display_df.sort_values(by="时间", ascending=False).reset_index(drop=True)
        
        edited_df = st.data_editor(
            display_df, 
            use_container_width=True, 
            hide_index=True, 
            column_config={
                "🗑️ 删": st.column_config.CheckboxColumn("🗑️ 删", default=False, width="small"),
                "收支": st.column_config.SelectboxColumn("收支", options=["支出", "收入"], width="small"),
                "时间": st.column_config.DatetimeColumn("时间 ↕", format="YYYY-MM-DD HH:mm", width="medium"),
                "金额 (¥)": st.column_config.NumberColumn("金额 ↕", format="%.2f", width="small")
            }
        )
        
        if st.button("💾 保存表格修改 / 确认删除", type="primary", use_container_width=True):
            final_df = edited_df[edited_df["🗑️ 删"] == False].copy()
            final_df = final_df.drop(columns=["🗑️ 删"], errors='ignore')
            final_df['时间'] = pd.to_datetime(final_df['时间'], errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S')
            final_df = final_df.fillna("")
            st.session_state.ledger_data = final_df.to_dict(orient="records")
            save_data(st.session_state.ledger_data)
            st.success("✅ 操作已永久生效！")
            st.rerun()

elif nav == "✍️ 记账":
    # --- 2. 手动记账页：全局返回键 + 联动类别 ---
    if st.button("⬅️ 返回主页", use_container_width=True):
        st.session_state.nav_radio = "📊 明细"; st.rerun()
        
    st.subheader("✍️ 记录新账单")
    with st.container(border=True):
        # 拆除了表单！现在点击支出/收入，下方的分类会瞬间切换！
        m_type = st.radio("收支类型", ["支出", "收入"], horizontal=True)
        m_amount = st.number_input("金额 (¥)", min_value=0.0, format="%.2f")
        m_merchant = st.text_input("商家名称 / 备注")
        
        if m_type == "支出":
            cat_options = ["餐饮", "交通", "购物", "居住", "娱乐", "投资", "其他"]
        else:
            cat_options = ["工资", "理财", "兼职", "退款", "其他"]
            
        m_category = st.selectbox("分类", cat_options)
        m_time = st.text_input("时间", value="现时", help="保持为 '现时' 将自动抓取精确时间")
        
        if st.button("✅ 存入账本", use_container_width=True, type="primary"):
            if m_amount <= 0: st.error("金额不能为 0 呀！")
            else:
                final_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") if m_time == "现时" else m_time
                st.session_state.ledger_data.append({"时间": final_time, "收支": m_type, "商家": m_merchant, "分类": m_category, "金额 (¥)": m_amount})
                save_data(st.session_state.ledger_data)
                st.success(f"已成功入账：¥ {m_amount}！")
                st.session_state.nav_radio = "📊 明细"
                st.rerun()

elif nav == "📸 识图":
    # --- 3. AI 识图页：全局返回键 ---
    if st.button("⬅️ 返回主页", use_container_width=True):
        st.session_state.nav_radio = "📊 明细"; st.rerun()
        
    st.subheader("📸 AI 智能识图 (Gemini 2.5)")
    with st.container(border=True):
        uploaded_file = st.file_uploader("上传截图或小票", type=["jpg", "jpeg", "png", "webp"], key=f"uploader_{st.session_state.uploader_key}")
        if uploaded_file is not None:
            st.image(Image.open(uploaded_file), use_container_width=True)
            if not api_key: st.warning("⚠️ 请先在左侧抽屉设置 API Key")
            else:
                if st.button("🚀 开始解析", use_container_width=True, type="primary"):
                    with st.spinner("AI 全速解析中..."):
                        raw_results = analyze_receipt_with_ai(Image.open(uploaded_file), api_key)
                        if "error" not in raw_results:
                            filtered_results, dup_count = filter_duplicates(raw_results, st.session_state.ledger_data)
                            if dup_count > 0: st.toast(f"🛡️ 已拦截 {dup_count} 条重复账单！", icon="🚫")
                            if not filtered_results: st.warning("⚠️ 提取的账单全部是重复记录。")
                            else:
                                st.session_state.parsed_results = filtered_results
                                st.session_state.review_index = 0
                                st.rerun()
                        else: st.error(f"解析失败: {raw_results['error']}")
                        
    if st.session_state.parsed_results is not None: confirm_dialog() 

elif nav == "📈 分析":
    # --- 4. 数据图页：全局返回键 ---
    if st.button("⬅️ 返回主页", use_container_width=True):
        st.session_state.nav_radio = "📊 明细"; st.rerun()
        
    st.subheader("📈 财务深度分析")
    if not has_data:
        st.info("📭 暂无数据可分析")
    else:
        st.markdown("#### 🎯 当月预算防线")
        
        # 使用当前真实时间计算图表预算
        df_current = df[df['月份'] == real_current_ym]
        real_income = df_current[df_current["收支"] == "收入"]["金额 (¥)"].sum()
        real_expense = df_current[df_current["收支"] == "支出"]["金额 (¥)"].sum()
        real_balance = real_income - real_expense
        
        g1, g2 = st.columns(2)
        with g1:
            st.caption("💰 存款进度")
            sav_pct = max(0.0, min(1.0, real_balance / target_savings)) if target_savings > 0 else 0
            st.progress(sav_pct)
            st.write(f"¥{real_balance:.2f} / ¥{target_savings}")
        with g2:
            st.caption("💸 支出红线")
            exp_pct = min(1.0, real_expense / target_expense) if target_expense > 0 else 0
            st.progress(exp_pct)
            st.write(f"¥{real_expense:.2f} / ¥{target_expense}")
        
        st.markdown("---")
        exp_df = df[df["收支"] == "支出"]
        if not exp_df.empty:
            c1, c2 = st.columns(2)
            with c1:
                fig_pie = px.pie(exp_df.groupby('分类')['金额 (¥)'].sum().reset_index(), values='金额 (¥)', names='分类', hole=0.4, title="历史总支出分布")
                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig_pie, use_container_width=True)
            with c2:
                fig_line = px.line(exp_df.groupby('日期')['金额 (¥)'].sum().reset_index(), x='日期', y='金额 (¥)', markers=True, title="每日支出走势")
                st.plotly_chart(fig_line, use_container_width=True)

# ==========================================
# 7. 物理底部导航栏渲染
# ==========================================
st.radio(
    "底部导航", 
    ["📊 明细", "✍️ 记账", "📸 识图", "📈 分析"], 
    horizontal=True, 
    key="nav_radio",
    label_visibility="collapsed"
)
