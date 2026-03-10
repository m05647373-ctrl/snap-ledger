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
    return {"target_savings": 2000.0, "target_expense": 3000.0}

def save_settings(settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

# ==========================================
# 2. 页面基本配置 & 状态初始化
# ==========================================
st.set_page_config(page_title="咔嚓记账 - AI与手动双核记账", page_icon="📸", layout="wide")

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

st.title("📸 咔嚓记账 SnapLedger")

# ==========================================
# 3. 侧边栏设置
# ==========================================
with st.sidebar:
    st.header("⚙️ 全局设置")
    api_key = st.text_input("请输入 Google Gemini API Key:", type="password")
    st.markdown("---")
    
    st.subheader("🎯 我的财务目标")
    current_savings = st.session_state.user_settings.get("target_savings", 2000.0)
    current_expense = st.session_state.user_settings.get("target_expense", 3000.0)
    
    target_savings = st.number_input("💰 本月预计存多少钱 (¥)", min_value=0.0, value=float(current_savings), step=500.0)
    target_expense = st.number_input("💸 本月最多花多少钱 (¥)", min_value=0.0, value=float(current_expense), step=500.0)
    
    if target_savings != current_savings or target_expense != current_expense:
        st.session_state.user_settings["target_savings"] = target_savings
        st.session_state.user_settings["target_expense"] = target_expense
        save_settings(st.session_state.user_settings)
    
    st.markdown("---")
    if st.button("🗑️ 清空所有账单数据"):
        st.session_state.ledger_data = []
        save_data([]) 
        st.session_state.parsed_results = None
        st.session_state.review_index = 0
        st.session_state.uploader_key += 1
        st.success("数据已彻底清空！")
        st.rerun()

# ==========================================
# 4. 核心功能：AI 解析与【带删除功能的翻页弹窗】
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

@st.dialog("📝 逐条核对账单", width="large")
def confirm_dialog():
    results = st.session_state.parsed_results
    total = len(results)
    idx = st.session_state.review_index
    item = results[idx]
    
    st.progress((idx + 1) / total)
    st.markdown(f"**进度：正在核对第 {idx + 1} 笔（共 {total} 笔）**")
    st.markdown("---")

    with st.form(key=f"review_form_{idx}"):
        
        # 金额高亮卡片
        amt_color = "#ff4b4b" if item.get("type", "支出") == "支出" else "#00c04b"
        st.markdown(f"""
        <div style='background-color: {amt_color}15; padding: 15px; border-radius: 10px; border-left: 6px solid {amt_color}; margin-bottom: 20px;'>
            <div style='font-size: 14px; color: #666;'>💰 AI 识别金额：</div>
            <div style='font-size: 32px; font-weight: 900; color: {amt_color};'>¥ {float(item.get('amount', 0.0)):.2f}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # 输入区
        col1, col2, col3 = st.columns([1, 1, 1])
        merchant = col1.text_input("🏪 商家名称", value=item.get("merchant", ""))
        
        type_options = ["支出", "收入"]
        default_type = item.get("type", "支出")
        tx_type = col2.selectbox("🏷️ 收支类型", options=type_options, index=type_options.index(default_type) if default_type in type_options else 0)
        
        amount = col3.number_input("✏️ 修改金额 (如无误请略过)", value=float(item.get("amount", 0.0)), format="%.2f")
        
        col4, col5 = st.columns([1, 1])
        time = col4.text_input("⏰ 交易时间", value=item.get("time", ""))
        category = col5.text_input("📂 分类", value=item.get("category", "其他"))
        
        st.markdown("---")
        
        # 【体验升级】双按钮排布：左边删除，右边保存/下一步
        btn_col1, btn_col2 = st.columns([1, 2])
        
        with btn_col1:
            btn_delete = st.form_submit_button("🗑️ 误识别，删除此条", use_container_width=True)
            
        with btn_col2:
            btn_label = "➡️ 确认并核对下一条" if idx < total - 1 else "✅ 全部确认，保存进账本！"
            btn_next = st.form_submit_button(btn_label, use_container_width=True, type="primary")
            
        # --- 按钮逻辑处理 ---
        if btn_delete:
            # 1. 踢出当前这条错误数据
            st.session_state.parsed_results.pop(idx)
            new_total = len(st.session_state.parsed_results)
            
            # 2. 判断删除后的走向
            if new_total == 0:
                # 全删光了
                st.session_state.parsed_results = None
                st.session_state.review_index = 0
                st.session_state.uploader_key += 1 
                st.warning("所有识别结果均已删除。")
                st.rerun()
            elif idx >= new_total:
                # 删掉的是最后一条，把前面已经存活的存进账本
                st.session_state.ledger_data.extend(st.session_state.parsed_results)
                save_data(st.session_state.ledger_data)
                
                st.session_state.parsed_results = None
                st.session_state.review_index = 0
                st.session_state.uploader_key += 1 
                st.balloons()
                st.rerun()
            else:
                # 删掉的是中间的，idx不用动，自然会显示新的一条
                st.rerun()

        elif btn_next:
            # 保存当前用户的修改回结果数组中
            st.session_state.parsed_results[idx] = {
                "时间": time, "收支": tx_type, "商家": merchant, "分类": category, "金额 (¥)": amount
            }
            
            if idx < total - 1:
                st.session_state.review_index += 1 
                st.rerun() 
            else:
                # 全都核对完了，写入全局账本
                st.session_state.ledger_data.extend(st.session_state.parsed_results)
                save_data(st.session_state.ledger_data)
                
                # 状态重置，关闭弹窗
                st.session_state.parsed_results = None
                st.session_state.review_index = 0
                st.session_state.uploader_key += 1 
                st.balloons()
                st.rerun()

# ==========================================
# 5. 全局数据预处理
# ==========================================
has_data = len(st.session_state.ledger_data) > 0

if has_data:
    df = pd.DataFrame(st.session_state.ledger_data)
    if "收支" not in df.columns:
        df["收支"] = "支出"
        
    df['日期'] = pd.to_datetime(df['时间'], errors='coerce').dt.date
    total_income = df[df["收支"] == "收入"]["金额 (¥)"].sum()
    total_expense = df[df["收支"] == "支出"]["金额 (¥)"].sum()
    balance = total_income - total_expense
else:
    df = pd.DataFrame()
    total_income = total_expense = balance = 0.0

# ==========================================
# 6. App 布局：三大独立板块
# ==========================================
tab1, tab2, tab3 = st.tabs(["📝 记账录入", "📊 财务明细", "📈 数据图"])

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
                            st.session_state.review_index = 0
                            st.rerun()
                            
    if st.session_state.parsed_results is not None:
        if isinstance(st.session_state.parsed_results, dict) and "error" in st.session_state.parsed_results:
            st.error(f"解析失败: {st.session_state.parsed_results['error']}")
            st.session_state.parsed_results = None 
        else:
            confirm_dialog() 

# ----------------- 标签页 2：财务明细 -----------------
with tab2:
    if not has_data:
        st.info("📭 当前账本空空如也，快去录入你的第一笔账单吧！")
    else:
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

        with st.container(border=True):
            st.subheader("📝 账单流水明细")
            st.data_editor(df.drop(columns=['日期'], errors='ignore'), use_container_width=True, num_rows="dynamic")

# ----------------- 标签页 3：数据图 -----------------
with tab3:
    if not has_data:
        st.info("📭 还没有数据哦，记几笔账再来看图表吧！")
    else:
        with st.container(border=True):
            st.subheader("🎯 财务目标监控进度")
            goal_col1, goal_col2 = st.columns(2, gap="large")
            
            with goal_col1:
                st.markdown("##### 💰 存款目标 (看结余)")
                if target_savings > 0:
                    saving_pct = max(0.0, min(1.0, balance / target_savings)) 
                    if balance >= target_savings:
                        st.success(f"🎉 **目标达成！** 已存下 ¥{balance:.2f}，超额完成 ¥{(balance - target_savings):.2f}！")
                        st.progress(1.0)
                    elif balance > 0:
                        st.info(f"⏳ **努力攒钱中...** 当前结余 ¥{balance:.2f}，距离目标还差 ¥{(target_savings - balance):.2f}。")
                        st.progress(saving_pct)
                    else:
                        st.error(f"🚨 **存款告急！** 当前为负资产/月光状态，结余 ¥{balance:.2f}。")
                        st.progress(0.0)
                else:
                    st.write("尚未设置存款目标。")

            with goal_col2:
                st.markdown("##### 💸 支出预算 (看红线)")
                if target_expense > 0:
                    expense_pct = min(1.0, total_expense / target_expense)
                    if total_expense > target_expense:
                        st.error(f"🚨 **预算已超标！** 额度 ¥{target_expense}，已花 ¥{total_expense:.2f}，超支 ¥{(total_expense - target_expense):.2f}！")
                        st.progress(1.0)
                    elif expense_pct > 0.8:
                        st.warning(f"⚠️ **预算告急！** 已花掉 {expense_pct*100:.1f}%，只剩 ¥{(target_expense - total_expense):.2f} 可以花了！")
                        st.progress(expense_pct)
                    else:
                        st.success(f"✅ **预算健康！** 已花 ¥{total_expense:.2f}，还有 ¥{(target_expense - total_expense):.2f} 的安全额度。")
                        st.progress(expense_pct)
                else:
                    st.write("尚未设置支出预算。")

        df_expense = df[df["收支"] == "支出"]
        if not df_expense.empty:
            with st.container(border=True):
                st.subheader("📈 支出深度分析")
                
                chart_col1, chart_col2 = st.columns(2)
                
                with chart_col1:
                    category_expense = df_expense.groupby('分类')['金额 (¥)'].sum().reset_index()
                    fig_pie = px.pie(category_expense, values='金额 (¥)', names='分类', hole=0.4, title="支出分类占比")
                    fig_pie.update_traces(textposition='inside', textinfo='percent+label', hovertemplate="%{label}<br>金额: ¥%{value:.2f}<br>占比: %{percent}")
                    st.plotly_chart(fig_pie, use_container_width=True)
                    
                with chart_col2:
                    daily_expense = df_expense.groupby('日期')['金额 (¥)'].sum().reset_index()
                    daily_expense['日期'] = pd.to_datetime(daily_expense['日期'])
                    fig_line = px.line(daily_expense, x='日期', y='金额 (¥)', markers=True, title="每日支出趋势")
                    fig_line.update_traces(hovertemplate='日期: %{x}<br>支出: ¥%{y:.2f}')
                    st.plotly_chart(fig_line, use_container_width=True)
        else:
            st.info("还没有记录任何支出，暂无法生成分析图表。")
