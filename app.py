import streamlit as st
from PIL import Image
import google.generativeai as genai
import json
import pandas as pd
import os
import datetime
import plotly.express as px  # 换用更强大的 Plotly 交互图表库

# ==========================================
# 1. 数据持久化：引入本地文件存储
# ==========================================
DATA_FILE = "ledger_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ==========================================
# 2. 页面基本配置 & 状态初始化
# ==========================================
st.set_page_config(page_title="咔嚓记账 - AI与手动双核记账", page_icon="📸", layout="wide")

if 'ledger_data' not in st.session_state:
    st.session_state.ledger_data = load_data()

if 'parsed_results' not in st.session_state:
    st.session_state.parsed_results = None

if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

st.title("📸 咔嚓记账 SnapLedger")

# ==========================================
# 3. 侧边栏设置 (增加预算功能)
# ==========================================
with st.sidebar:
    st.header("⚙️ 全局设置")
    api_key = st.text_input("请输入 Google Gemini API Key:", type="password")
    st.markdown("---")
    
    st.subheader("🎯 财务目标")
    monthly_budget = st.number_input("设定本月预算 (¥)", min_value=0.0, value=3000.0, step=100.0)
    
    st.markdown("---")
    if st.button("🗑️ 清空所有账单数据"):
        st.session_state.ledger_data = []
        save_data([]) 
        st.session_state.parsed_results = None
        st.session_state.uploader_key += 1
        st.success("数据已彻底清空！")
        st.rerun()

# ==========================================
# 4. 核心功能：AI 解析与确认弹窗
# ==========================================
def analyze_receipt_with_ai(image, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    prompt = """
    你是一个极其精准的财务助手。请分析这张截图，提取图中【所有】的流水记录。
    1. 支出：金额前有 "-" 号，或明确是付款、消费。
    2. 收入：金额前有 "+" 号，或明确是收款、退款、工资。
    请返回 JSON 数组 (Array)，金额保留两位小数的数字，去掉正负号：
    [ { "merchant": "星巴克", "type": "支出", "amount": 35.00, "time": "2026-03-11 14:30", "category": "餐饮" } ]
    """
    try:
        response = model.generate_content([prompt, image])
        result_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(result_text)
    except Exception as e:
        return {"error": str(e)}

@st.dialog("📝 核对并保存 AI 提取的账单", width="large")
def confirm_dialog(results):
    st.info("💡 请核对 AI 提取的信息，修改无误后点击最下方的保存按钮。")
    with st.form("batch_confirm_form"):
        verified_data = []
        for i, item in enumerate(results):
            cols = st.columns([2, 1.5, 2, 2.5, 1.5])
            merchant = cols[0].text_input(f"商家 {i+1}", value=item.get("merchant", ""), key=f"m_{i}")
            
            type_options = ["支出", "收入"]
            default_type = item.get("type", "支出")
            type_index = type_options.index(default_type) if default_type in type_options else 0
            tx_type = cols[1].selectbox(f"收支 {i+1}", options=type_options, index=type_index, key=f"type_{i}")
            
            amount = cols[2].number_input(f"金额 {i+1}", value=float(item.get("amount", 0.0)), format="%.2f", key=f"a_{i}")
            time = cols[3].text_input(f"时间 {i+1}", value=item.get("time", ""), key=f"t_{i}")
            category = cols[4].text_input(f"分类 {i+1}", value=item.get("category", "其他"), key=f"c_{i}")
            
            verified_data.append({
                "时间": time, "收支": tx_type, "商家": merchant, "分类": category, "金额 (¥)": amount
            })
        
        if st.form_submit_button("✅ 确认无误，保存进账本！"):
            st.session_state.ledger_data.extend(verified_data)
            save_data(st.session_state.ledger_data)
            st.session_state.parsed_results = None
            st.session_state.uploader_key += 1 
            st.balloons()
            st.rerun()

# ==========================================
# 5. App 布局：录入页面 & 数据看板
# ==========================================
tab1, tab2 = st.tabs(["📝 记账录入", "📊 财务看板"])

# ----------------- 标签页 1：记账录入 -----------------
with tab1:
    col_manual, col_ai = st.columns([1.5, 1], gap="large")

    with col_manual:
        st.subheader("✍️ 手动记账")
        with st.container(border=True):
            with st.form("manual_entry_form", clear_on_submit=True):
                f_col1, f_col2 = st.columns(2)
                m_type = f_col1.radio("收支类型", ["支出", "收入"], horizontal=True)
                m_amount = f_col2.number_input("金额 (¥)", min_value=0.0, format="%.2f", step=10.0)
                m_merchant = st.text_input("商家名称 / 备注")
                f_col3, f_col4 = st.columns(2)
                m_category = f_col3.selectbox("分类", ["餐饮", "交通", "购物", "居住", "娱乐", "投资", "工资", "退款", "转账", "其他"])
                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                m_time = f_col4.text_input("时间", value=now_str)
                
                if st.form_submit_button("✅ 记一笔", use_container_width=True):
                    if m_amount <= 0:
                        st.error("金额不能为 0 呀！")
                    else:
                        new_record = {
                            "时间": m_time, "收支": m_type, "商家": m_merchant, 
                            "分类": m_category, "金额 (¥)": m_amount
                        }
                        st.session_state.ledger_data.append(new_record)
                        save_data(st.session_state.ledger_data)
                        st.success(f"成功记录一笔 {m_amount} 元的{m_type}！")

    with col_ai:
        st.subheader("📸 AI 拍照提取")
        with st.container(border=True):
            uploaded_file = st.file_uploader("上传截图或发票自动解析...", type=["jpg", "jpeg", "png", "webp"], key=f"uploader_{st.session_state.uploader_key}")

            if uploaded_file is not None:
                image = Image.open(uploaded_file)
                st.image(image, caption="待解析图片", use_container_width=True)
                if not api_key:
                    st.warning("⚠️ 请先在左侧设置 API Key")
                else:
                    if st.button("🚀 智能解析提取", use_container_width=True, type="primary"):
                        with st.spinner("AI 正在光速解析，马上就好..."):
                            st.session_state.parsed_results = analyze_receipt_with_ai(image, api_key)
                            st.rerun()
                            
    if st.session_state.parsed_results is not None:
        if isinstance(st.session_state.parsed_results, dict) and "error" in st.session_state.parsed_results:
            st.error(f"解析失败: {st.session_state.parsed_results['error']}")
            st.session_state.parsed_results = None 
        else:
            confirm_dialog(st.session_state.parsed_results)

# ----------------- 标签页 2：财务看板 (模块化分离) -----------------
with tab2:
    if not st.session_state.ledger_data:
        st.info("📭 当前账本空空如也，快去录入你的第一笔账单吧！")
    else:
        df = pd.DataFrame(st.session_state.ledger_data)
        if "收支" not in df.columns:
            df["收支"] = "支出"
            
        df['日期'] = pd.to_datetime(df['时间'], errors='coerce').dt.date
            
        total_income = df[df["收支"] == "收入"]["金额 (¥)"].sum()
        total_expense = df[df["收支"] == "支出"]["金额 (¥)"].sum()
        balance = total_income - total_expense
        
        # 【模块 1：预算监控】---------------------------------
        with st.container(border=True):
            st.subheader("🎯 预算监控")
            budget_pct = (total_expense / monthly_budget) * 100 if monthly_budget > 0 else 0
            if total_expense > monthly_budget:
                st.error(f"🚨 **预算超标！** 本月预算 ¥{monthly_budget}，已支出 ¥{total_expense:.2f}，超支 ¥{(total_expense - monthly_budget):.2f}！")
                st.progress(1.0)
            elif budget_pct > 80:
                st.warning(f"⚠️ **预算告急！** 已使用 {budget_pct:.1f}%。剩余：¥{(monthly_budget - total_expense):.2f}")
                st.progress(budget_pct / 100)
            else:
                st.success(f"✅ **预算健康！** 剩余额度：¥{(monthly_budget - total_expense):.2f}")
                st.progress(budget_pct / 100)
        
        # 【模块 2：核心收支指标】---------------------------------
        with st.container(border=True):
            st.subheader("💡 核心指标")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("💰 总收入", f"¥ {total_income:.2f}")
            col2.metric("💸 总支出", f"¥ {total_expense:.2f}")
            col3.metric("💳 净结余", f"¥ {balance:.2f}")
            with col4:
                st.write("") 
                csv = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 导出CSV报表", data=csv, file_name="我的账单.csv", mime="text/csv", use_container_width=True)

        # 【模块 3：可视化图表区】---------------------------------
        df_expense = df[df["收支"] == "支出"]
        if not df_expense.empty:
            with st.container(border=True):
                st.subheader("📈 支出分析")
                
                # 为了让图表足够大，我们上下排列而不是左右挤在一起
                chart_col1, chart_col2 = st.columns(2)
                
                with chart_col1:
                    category_expense = df_expense.groupby('分类')['金额 (¥)'].sum().reset_index()
                    # Plotly 甜甜圈图，天生支持显示精确数值和百分比！
                    fig_pie = px.pie(category_expense, values='金额 (¥)', names='分类', hole=0.4, title="支出分类占比")
                    fig_pie.update_traces(textposition='inside', textinfo='percent+label', hovertemplate="%{label}<br>金额: ¥%{value:.2f}<br>占比: %{percent}")
                    st.plotly_chart(fig_pie, use_container_width=True)
                    
                with chart_col2:
                    daily_expense = df_expense.groupby('日期')['金额 (¥)'].sum().reset_index()
                    daily_expense['日期'] = pd.to_datetime(daily_expense['日期'])
                    # Plotly 折线图，鼠标放上去就能看具体哪天花了多少钱，甚至能框选放大！
                    fig_line = px.line(daily_expense, x='日期', y='金额 (¥)', markers=True, title="每日支出趋势")
                    fig_line.update_traces(hovertemplate='日期: %{x}<br>支出: ¥%{y:.2f}')
                    st.plotly_chart(fig_line, use_container_width=True)

        # 【模块 4：详细流水表格】---------------------------------
        with st.container(border=True):
            st.subheader("📝 账单流水明细")
            st.data_editor(df.drop(columns=['日期'], errors='ignore'), use_container_width=True, num_rows="dynamic")
