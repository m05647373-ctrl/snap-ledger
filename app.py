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
# 2. 页面基本配置 & 状态初始化
# ==========================================
st.set_page_config(page_title="咔嚓记账 - 极简智能账本", page_icon="🦈", layout="centered")

# 隐藏顶部白条，让黄色面板更贴顶
st.markdown("<style>header {visibility: hidden;}</style>", unsafe_allow_html=True)

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
# 3. 侧边栏：设置与预算
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
        st.session_state.user_settings["target_savings"] = target_savings
        st.session_state.user_settings["target_expense"] = target_expense
        save_settings(st.session_state.user_settings)
    
    st.markdown("---")
    if st.button("🗑️ 清空所有账单数据", use_container_width=True):
        st.session_state.ledger_data = []
        save_data([]) 
        st.session_state.parsed_results = None
        st.session_state.review_index = 0
        st.session_state.uploader_key += 1
        st.success("数据已彻底清空！")
        st.rerun()

# ==========================================
# 4. 核心数据预处理 & 顶部黄色鲨鱼面板
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

# 顶部交互：动态切换月份
col_sel1, col_sel2 = st.columns([1, 4])
with col_sel1:
    selected_ym = st.selectbox("📅 切换月份", all_months, label_visibility="collapsed")

month_income = 0.0
month_expense = 0.0
if has_data:
    df_selected_month = df[df['月份'] == selected_ym]
    month_income = df_selected_month[df_selected_month["收支"] == "收入"]["金额 (¥)"].sum()
    month_expense = df_selected_month[df_selected_month["收支"] == "支出"]["金额 (¥)"].sum()

disp_year = selected_ym.split("-")[0] + "年"
disp_month = selected_ym.split("-")[1] + "月"

# 绝美黄色数据面板（置顶显示）
st.markdown(f"""
<div style="background-color: #fcd535; padding: 25px 30px; border-radius: 20px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); margin-bottom: 25px;">
    <div style="color: #333; font-size: 20px; font-weight: bold; margin-bottom: 15px;">🦈 咔嚓记账</div>
    <div style="display: flex; justify-content: space-between; align-items: flex-end;">
        <div>
            <div style="color: #555; font-size: 14px;">{disp_year}</div>
            <div style="color: #222; font-size: 32px; font-weight: bold;">{disp_month}</div>
        </div>
        <div style="text-align: left; flex: 1; padding-left: 50px;">
            <div style="color: #555; font-size: 14px;">本月收入</div>
            <div style="color: #222; font-size: 24px; font-weight: 500;">{month_income:.2f}</div>
        </div>
        <div style="text-align: left; flex: 1;">
            <div style="color: #555; font-size: 14px;">本月支出</div>
            <div style="color: #222; font-size: 24px; font-weight: 500;">{month_expense:.2f}</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ==========================================
# 5. AI 解析、去重与核对弹窗 (2.5 引擎)
# ==========================================
def analyze_receipt_with_ai(image, api_key):
    genai.configure(api_key=api_key)
    # 【已升级】正式采用 2.5 flash 超强引擎
    model = genai.GenerativeModel('gemini-2.5-flash')
    prompt = """提取图中所有流水记录。返回 JSON 数组格式：
    [ { "merchant": "星巴克", "type": "支出", "amount": 35.00, "time": "2026-03-11 14:30", "category": "餐饮" } ]"""
    try:
        res = model.generate_content([prompt, image])
        return json.loads(res.text.replace("```json", "").replace("```", "").strip())
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
        m_type = c2.selectbox("🏷️ 类型", opts, index=opts.index(item.get("type", "支出")) if item.get("type") in opts else 0)
        amt = c3.number_input("✏️ 修改金额", value=float(item.get("amount", 0)), format="%.2f")
        
        c4, c5 = st.columns(2)
        tm = c4.text_input("⏰ 时间", value=item.get("time", ""))
        cat = c5.text_input("📂 分类", value=item.get("category", "其他"))
        
        b1, b2, b3 = st.columns([1, 1, 1.5])
        with b1: 
            if st.form_submit_button("🗑️ 删除此条", use_container_width=True):
                st.session_state.parsed_results.pop(idx)
                if not st.session_state.parsed_results: st.session_state.parsed_results = None
                st.session_state.review_index = max(0, idx - 1)
                st.rerun()
        with b2: 
            if idx > 0 and st.form_submit_button("⬅️ 上一条", use_container_width=True):
                st.session_state.review_index -= 1
                st.rerun()
        with b3: 
            btn_txt = "✅ 确认并保存全部" if idx == total - 1 else "➡️ 确认并下一条"
            if st.form_submit_button(btn_txt, use_container_width=True, type="primary"):
                st.session_state.parsed_results[idx] = {"时间": tm, "收支": m_type, "商家": merch, "分类": cat, "金额 (¥)": amt}
                if idx < total - 1: st.session_state.review_index += 1
                else:
                    st.session_state.ledger_data.extend(st.session_state.parsed_results)
                    save_data(st.session_state.ledger_data)
                    st.session_state.parsed_results = None
                    st.session_state.review_index = 0
                    st.session_state.uploader_key += 1
                    st.balloons()
                st.rerun()

# ==========================================
# 6. 四大操作栏 (原生 Tabs，稳定可靠)
# ==========================================
# 【重点修复】：采用了最稳定的组件布局，名称完美契合你的要求！
tab_detail, tab_manual, tab_ai, tab_chart = st.tabs(["📊 财务明细", "✍️ 记账录入", "📸 图片识别", "📈 数据图"])

# ----------------- 操作区 1: 财务明细 -----------------
with tab_detail:
    if not has_data:
        st.info("📭 暂无流水，快去记一笔吧！")
    else:
        st.caption("💡 可在下方表格直接修改，勾选最右侧复选框后，点击底部按钮即可永久删除。")
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
        
        if st.button("💾 确认删除 / 保存修改", type="primary", use_container_width=True):
            final_df = edited_df[edited_df["🗑️ 勾选删除"] == False].copy()
            final_df = final_df.drop(columns=["🗑️ 勾选删除"], errors='ignore')
            final_df['时间'] = pd.to_datetime(final_df['时间'], errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S')
            final_df = final_df.fillna("")
            
            st.session_state.ledger_data = final_df.to_dict(orient="records")
            save_data(st.session_state.ledger_data)
            st.success("✅ 操作已永久生效！")
            st.rerun()

# ----------------- 操作区 2: 记账录入 -----------------
with tab_manual:
    with st.container(border=True):
        with st.form("manual_form", clear_on_submit=True):
            f1, f2 = st.columns(2)
            m_type = f1.radio("类型", ["支出", "收入"], horizontal=True)
            m_amt = f2.number_input("金额 (¥)", min_value=0.0, format="%.2f")
            m_merch = st.text_input("商家名称 / 备注")
            
            f3, f4 = st.columns(2)
            m_cat = f3.selectbox("分类", ["餐饮", "交通", "购物", "居住", "娱乐", "工资", "退款", "转账", "其他"])
            m_time_input = f4.text_input("时间", value="现时", help="保持 '现时' 将自动抓取当前精确时间")
            
            if st.form_submit_button("✅ 保存这笔账单", use_container_width=True, type="primary"):
                if m_amt <= 0: st.error("金额不能为 0！")
                else:
                    final_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") if m_time_input == "现时" else m_time_input
                    st.session_state.ledger_data.append({"时间": final_time, "收支": m_type, "商家": m_merch, "分类": m_cat, "金额 (¥)": m_amt})
                    save_data(st.session_state.ledger_data)
                    st.success(f"已入账！")
                    st.rerun()

# ----------------- 操作区 3: 图片识别 -----------------
with tab_ai:
    with st.container(border=True):
        st.caption("📸 支持上传微信、支付宝账单截图或实体小票")
        up = st.file_uploader("请选择图片文件", type=["jpg", "png", "jpeg"], key=f"up_{st.session_state.uploader_key}")
        if up:
            st.image(Image.open(up), use_container_width=True)
            if st.button("🚀 呼叫 AI 智能识别", use_container_width=True, type="primary"):
                if not api_key: st.error("请先在左侧抽屉设置中输入 API Key")
                else:
                    with st.spinner("AI 大脑运转中 (Gemini 2.5 Flash)..."):
                        res = analyze_receipt_with_ai(Image.open(up), api_key)
                        if "error" in res: st.error(res["error"])
                        else:
                            filtered_results, dup_count = filter_duplicates(res, st.session_state.ledger_data)
                            if dup_count > 0: st.toast(f"🛡️ 已为您拦截 {dup_count} 条重复账单！", icon="🚫")
                            if not filtered_results: st.warning("⚠️ 提取的账单已全部存在于库中。")
                            else:
                                st.session_state.parsed_results = filtered_results
                                st.session_state.review_index = 0
                                st.rerun()
                                
    if st.session_state.parsed_results: confirm_dialog()

# ----------------- 操作区 4: 数据图 -----------------
with tab_chart:
    if not has_data:
        st.info("暂无数据可分析")
    else:
        month_balance = month_income - month_expense
        st.markdown(f"#### 🎯 【{disp_month}】预算监控")
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
