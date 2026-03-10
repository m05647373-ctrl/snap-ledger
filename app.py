import streamlit as st
from PIL import Image
import google.generativeai as genai
import json
import pandas as pd
import os
import datetime
import altair as alt  # Streamlit 内置的强大图表库

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
st.set_page_config(page_title="咔嚓记账 - AI与手动双核记账", page_icon="📸", layout="wide") # 改为宽屏以适配图表和分栏

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
    
    # 新增：月度预算设置
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

# ----------------- 标签页 1：记账录入 (左手动，右AI) -----------------
with tab1:
    # 将页面分为左右两列，比例为 1.5 : 1
    col_manual, col_ai = st.columns([1.5, 1], gap="large")

    # 左侧：手动输入界面
    with col_manual:
        st.subheader("✍️ 手动记账")
        with st.container(border=True): # 加上边框更好看
            with st.form("manual_entry_form", clear_on_submit=True):
                # 两列排布让表单更紧凑
                f_col1, f_col2 = st.columns(2)
                m_type = f_col1.radio("收支类型", ["支出", "收入"], horizontal=True)
                m_amount = f_col2.number_input("金额 (¥)", min_value=0.0, format="%.2f", step=10.0)
                
                m_merchant = st.text_input("商家名称 / 备注")
                
                f_col3, f_col4 = st.columns(2)
                m_category = f_col3.selectbox("分类", ["餐饮", "交通", "购物", "居住", "娱乐", "投资", "工资", "退款", "转账", "其他"])
                # 默认获取今天的日期和时间
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

    # 右侧：AI 上传界面
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
                            
    # 唤起弹窗逻辑
    if st.session_state.parsed_results is not None:
        if isinstance(st.session_state.parsed_results, dict) and "error" in st.session_state.parsed_results:
            st.error(f"解析失败: {st.session_state.parsed_results['error']}")
            st.session_state.parsed_results = None 
        else:
            confirm_dialog(st.session_state.parsed_results)

# ----------------- 标签页 2：财务看板 (图表与报警) -----------------
with tab2:
    st.subheader("流水分析与预警")
    
    if not st.session_state.ledger_data:
        st.info("📭 当前账本空空如也，快去录入你的第一笔账单吧！")
    else:
        df = pd.DataFrame(st.session_state.ledger_data)
        if "收支" not in df.columns:
            df["收支"] = "支出"
            
        # 提取日期用于按天画图
        df['日期'] = pd.to_datetime(df['时间'], errors='coerce').dt.date
            
        # 计算核心指标
        total_income = df[df["收支"] == "收入"]["金额 (¥)"].sum()
        total_expense = df[df["收支"] == "支出"]["金额 (¥)"].sum()
        balance = total_income - total_expense
        
        # --- 预算报警逻辑 ---
        st.markdown("### 🎯 预算监控")
        budget_pct = (total_expense / monthly_budget) * 100 if monthly_budget > 0 else 0
        
        # 进度条展示预算使用情况
        if total_expense > monthly_budget:
            st.error(f"🚨 **预算超标警告！** 本月预算 ¥{monthly_budget}，已支出 ¥{total_expense:.2f}，超支 ¥{(total_expense - monthly_budget):.2f}！")
            st.progress(1.0)
        elif budget_pct > 80:
            st.warning(f"⚠️ **预算告急！** 已使用预算的 {budget_pct:.1f}%。剩余额度：¥{(monthly_budget - total_expense):.2f}")
            st.progress(budget_pct / 100)
        else:
            st.success(f"✅ **预算健康！** 剩余额度：¥{(monthly_budget - total_expense):.2f}")
            st.progress(budget_pct / 100)
        
        st.markdown("---")
        
        # --- 顶部数据卡片 ---
        col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
        col1.metric("💰 总收入", f"¥ {total_income:.2f}")
        col2.metric("💸 总支出", f"¥ {total_expense:.2f}")
        col3.metric("💳 净结余", f"¥ {balance:.2f}")
        with col4:
            st.write("") 
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 导出CSV报表", data=csv, file_name="我的账单.csv", mime="text/csv")
            
        st.markdown("---")

        # --- 可视化图表区 ---
        df_expense = df[df["收支"] == "支出"]
        
        if not df_expense.empty:
            chart_col1, chart_col2 = st.columns(2)
            
            # 1. 饼状图：支出分类占比
            with chart_col1:
                st.markdown("**支出分类占比 (饼图)**")
                # 聚合分类数据
                category_expense = df_expense.groupby('分类')['金额 (¥)'].sum().reset_index()
                # 使用 Altair 画出高颜值甜甜圈饼图
                pie_chart = alt.Chart(category_expense).mark_arc(innerRadius=50).encode(
                    theta=alt.Theta(field="金额 (¥)", type="quantitative"),
                    color=alt.Color(field="分类", type="nominal", scale=alt.Scale(scheme="category20")),
                    tooltip=['分类', '金额 (¥)']
                ).properties(height=350)
                st.altair_chart(pie_chart, use_container_width=True)
                
            # 2. 曲线图：每日消费变化趋势
            with chart_col2:
                st.markdown("**每日支出变化趋势 (曲线图)**")
                # 聚合每日数据
                daily_expense = df_expense.groupby('日期')['金额 (¥)'].sum().reset_index()
                # 转换为标准时间格式以便画图
                daily_expense['日期'] = pd.to_datetime(daily_expense['日期'])
                
                line_chart = alt.Chart(daily_expense).mark_line(point=True, strokeWidth=3).encode(
                    x=alt.X('日期:T', title=''),
                    y=alt.Y('金额 (¥):Q', title='支出金额'),
                    tooltip=['日期:T', '金额 (¥):Q']
                ).properties(height=350)
                st.altair_chart(line_chart, use_container_width=True)
        else:
            st.info("尚无支出记录，暂无图表生成。")

        st.markdown("---")
        st.markdown("### 📝 账单明细流水")
        st.data_editor(df.drop(columns=['日期'], errors='ignore'), use_container_width=True, num_rows="dynamic")
