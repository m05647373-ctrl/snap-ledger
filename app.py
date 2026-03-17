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
    saved_api_key = st.session_state.user_settings.get("api_key", "")
    api_key = st.text_input("🔑 Google Gemini API Key:", value=saved_api_key, type="password")
    
    if api_key != saved_api_key:
        st.session_state.user_settings["api_key"] = api_key
        save_settings(st.session_state.user_settings)
        
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
    if st.button("🗑️ 清空所有账单数据", use_container_width=True):
        st.session_state.ledger_data = []
        save_data([]) 
        st.session_state.parsed_results = None
        st.session_state.review_index = 0
        st.session_state.uploader_key += 1
        st.success("数据已彻底清空！")
        st.rerun()

# ==========================================
# 4. 核心功能：AI 解析、去重与弹窗
# ==========================================
def analyze_receipt_with_ai(image, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = """
    你是一个极其精准的财务助手。请分析这张截图，提取图中【所有】的流水记录。
    请返回 JSON 数组 (Array)，金额保留两位小数的数字，去掉正负号：
    [ { "merchant": "星巴克", "type": "支出", "amount": 35.00, "time": "2026-03-11 14:30", "category": "餐饮" } ]
    """
    try:
        response = model.generate_content([prompt, image])
        result_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(result_text)
    except Exception as e:
        return {"error": str(e)}

# 【新增功能 1：智能去重逻辑】
def filter_duplicates(ai_results, ledger):
    filtered = []
    dup_count = 0
    for item in ai_results:
        is_dup = False
        for record in ledger:
            try:
                # 提取比对关键要素
                ai_amt = float(item.get('amount', 0))
                db_amt = float(record.get('金额 (¥)', 0))
                
                # 时间只比对到“天”（YYYY-MM-DD），因为AI有时识别的小时分钟会有误差
                ai_time = str(item.get('time', ''))[:10] 
                db_time = str(record.get('时间', ''))[:10]
                
                ai_merch = str(item.get('merchant', '')).lower()
                db_merch = str(record.get('商家', '')).lower()
                
                # 判定规则：同一天 + 金额完全相等 + 商家名字有包含关系
                if ai_amt == db_amt and ai_time == db_time and (ai_merch in db_merch or db_merch in ai_merch):
                    is_dup = True
                    break
            except:
                pass
                
        if is_dup:
            dup_count += 1
        else:
            filtered.append(item)
    return filtered, dup_count

@st.dialog("📝 逐条核对账单", width="large")
def confirm_dialog():
    res = st.session_state.parsed_results
    total = len(res)
    idx = st.session_state.review_index
    item = res[idx]
    
    # 【新增功能 2：一键确认剩余全部】
    if total - idx > 1: # 当剩下不止1条时，显示闪电按钮
        if st.button(f"⚡ 信任 AI：一键直接入账剩余的 {total - idx} 笔", type="secondary", use_container_width=True):
            formatted_rest = []
            for r in res[idx:]:
                formatted_rest.append({
                    "时间": r.get("time", ""),
                    "收支": r.get("type", "支出"),
                    "商家": r.get("merchant", ""),
                    "分类": r.get("category", "其他"),
                    "金额 (¥)": float(r.get("amount", 0.0))
                })
            st.session_state.ledger_data.extend(formatted_rest)
            save_data(st.session_state.ledger_data)
            
            # 清理状态并关闭弹窗
            st.session_state.parsed_results = None
            st.session_state.review_index = 0
            st.session_state.uploader_key += 1
            st.balloons()
            st.success("✅ 剩余账单已全部一键入账！")
            st.rerun()
            
    st.progress((idx + 1) / total)
    st.markdown(f"**进度：正在核对第 {idx + 1} 笔（共 {total} 笔）**")
    st.markdown("---")

    with st.form(key=f"review_form_{idx}"):
        amt_color = "#ff4b4b" if item.get("type", "支出") == "支出" else "#00c04b"
        st.markdown(f"""
        <div style='background-color: {amt_color}15; padding: 15px; border-radius: 10px; border-left: 6px solid {amt_color}; margin-bottom: 20px;'>
            <div style='font-size: 14px; color: #666;'>💰 AI 识别金额：</div>
            <div style='font-size: 32px; font-weight: 900; color: {amt_color};'>¥ {float(item.get('amount', 0.0)):.2f}</div>
        </div>
        """, unsafe_allow_html=True)
        
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
        
        btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 1.5])
        
        with btn_col1:
            btn_delete = st.form_submit_button("🗑️ 删除此条", use_container_width=True)
        with btn_col2:
            btn_prev = st.form_submit_button("⬅️ 返回上一条", use_container_width=True) if idx > 0 else False
        with btn_col3:
            btn_label = "➡️ 确认并核对下一条" if idx < total - 1 else "✅ 确认并保存！"
            btn_next = st.form_submit_button(btn_label, use_container_width=True, type="primary")
            
        if btn_delete:
            st.session_state.parsed_results.pop(idx)
            new_total = len(st.session_state.parsed_results)
            if new_total == 0:
                st.session_state.parsed_results = None
                st.session_state.review_index = 0
                st.session_state.uploader_key += 1 
                st.warning("所有识别结果均已删除。")
                st.rerun()
            elif idx >= new_total:
                st.session_state.ledger_data.extend(st.session_state.parsed_results)
                save_data(st.session_state.ledger_data)
                st.session_state.parsed_results = None
                st.session_state.review_index = 0
                st.session_state.uploader_key += 1 
                st.balloons()
                st.rerun()
            else:
                st.rerun()

        elif btn_prev:
            st.session_state.parsed_results[idx] = {
                "时间": time, "收支": tx_type, "商家": merchant, "分类": category, "金额 (¥)": amount
            }
            st.session_state.review_index -= 1 
            st.rerun()

        elif btn_next:
            st.session_state.parsed_results[idx] = {
                "时间": time, "收支": tx_type, "商家": merchant, "分类": category, "金额 (¥)": amount
            }
            if idx < total - 1:
                st.session_state.review_index += 1 
                st.rerun() 
            else:
                st.session_state.ledger_data.extend(st.session_state.parsed_results)
                save_data(st.session_state.ledger_data)
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
    
    df['金额 (¥)'] = pd.to_numeric(df['金额 (¥)'], errors='coerce').fillna(0.0)
    df['时间'] = pd.to_datetime(df['时间'], errors='coerce')
        
    df['日期'] = df['时间'].dt.date
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
                
                m_time = f_col4.text_input("时间", value="现时", help="保持为 '现时'，提交时将自动抓取精确到秒的当前时间")
                
                if st.form_submit_button("✅ 记一笔", use_container_width=True):
                    if m_amount <= 0:
                        st.error("金额不能为 0 呀！")
                    else:
                        final_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") if m_time == "现时" else m_time
                        new_record = {
                            "时间": final_time, "收支": m_type, "商家": m_merchant, 
                            "分类": m_category, "金额 (¥)": m_amount
                        }
                        st.session_state.ledger_data.append(new_record)
                        save_data(st.session_state.ledger_data)
                        st.success(f"已于 {final_time} 成功记录一笔 {m_amount} 元的{m_type}！")

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
                            raw_results = analyze_receipt_with_ai(image, api_key)
                            
                            # 【触发去重拦截】
                            if "error" not in raw_results:
                                filtered_results, dup_count = filter_duplicates(raw_results, st.session_state.ledger_data)
                                
                                if dup_count > 0:
                                    st.toast(f"🛡️ 已拦截 {dup_count} 条重复账单！", icon="🚫")
                                
                                if not filtered_results:
                                    st.warning("⚠️ 提取的账单已全部存在于库中，无新数据需导入。")
                                else:
                                    st.session_state.parsed_results = filtered_results
                                    st.session_state.review_index = 0
                                    st.rerun()
                            else:
                                st.error(f"解析失败: {raw_results['error']}")
                            
    if st.session_state.parsed_results is not None:
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
            st.info("📱 **操作指南**：可以直接在表格里编辑内容。勾选最右侧的『🗑️ 勾选删除』，然后点击最下方的大按钮即可保存修改或批量删除！")
            
            display_df = df.drop(columns=['日期'], errors='ignore').copy()
            display_df["🗑️ 勾选删除"] = False 
            
            edited_df = st.data_editor(
                display_df, 
                use_container_width=True, 
                num_rows="dynamic",
                hide_index=True, 
                column_config={
                    "🗑️ 勾选删除": st.column_config.CheckboxColumn("🗑️ 勾选删除", default=False),
                    "时间": st.column_config.DatetimeColumn("时间 (可排序)", format="YYYY-MM-DD HH:mm:ss"),
                    "金额 (¥)": st.column_config.NumberColumn("金额 (可排序)", format="%.2f")
                }
            )
            
            if st.button("删除 / 保存", type="primary", use_container_width=True):
                final_df = edited_df[edited_df["🗑️ 勾选删除"] == False].copy()
                final_df = final_df.drop(columns=["🗑️ 勾选删除"], errors='ignore')
                final_df['时间'] = pd.to_datetime(final_df['时间'], errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S')
                final_df['时间'] = final_df['时间'].fillna("")
                final_df = final_df.fillna("")
                
                st.session_state.ledger_data = final_df.to_dict(orient="records")
                save_data(st.session_state.ledger_data)
                st.success("✅ 修改与删除已永久生效！")
                st.rerun()

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
