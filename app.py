import streamlit as st
from PIL import Image
import google.generativeai as genai
import json
import pandas as pd
import os

# ==========================================
# 1. 数据持久化：引入本地文件存储
# ==========================================
DATA_FILE = "ledger_data.json"

def load_data():
    """从本地 JSON 文件读取账本数据"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_data(data):
    """将账本数据保存到本地 JSON 文件"""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ==========================================
# 2. 页面基本配置 & 状态初始化
# ==========================================
st.set_page_config(page_title="咔嚓记账 - AI视觉记账", page_icon="📸", layout="centered")

# 从本地文件加载真实数据，不再怕刷新！
if 'ledger_data' not in st.session_state:
    st.session_state.ledger_data = load_data()

if 'parsed_results' not in st.session_state:
    st.session_state.parsed_results = None

# 用于强制清空上传图片的组件状态
if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

st.title("📸 咔嚓记账 SnapLedger")

# ==========================================
# 3. 侧边栏设置
# ==========================================
with st.sidebar:
    st.header("⚙️ 设置")
    api_key = st.text_input("请输入 Google Gemini API Key:", type="password")
    st.markdown("---")
    
    if st.button("🗑️ 清空所有账单数据"):
        st.session_state.ledger_data = []
        save_data([]) # 同时清空本地文件
        st.session_state.parsed_results = None
        st.session_state.uploader_key += 1
        st.success("数据已彻底清空！")
        st.rerun()

# ==========================================
# 4. 核心功能：AI 解析
# ==========================================
def analyze_receipt_with_ai(image, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = """
    你是一个极其精准的财务助手。请分析这张截图，提取图中【所有】的流水记录。
    
    【⚠️ 收支判断规则】：
    1. 支出：金额前有 "-" 号，或明确是付款、消费。
    2. 收入：金额前有 "+" 号，或明确是收款、退款、工资。
    3. 如果没有符号，根据商家推断。
    
    请严格返回 JSON 数组 (Array)，金额去掉正负号：
    [
      { "merchant": "星巴克", "type": "支出", "amount": 35.00, "time": "2026-03-11 14:30", "category": "餐饮" }
    ]
    """
    try:
        response = model.generate_content([prompt, image])
        result_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(result_text)
    except Exception as e:
        return {"error": str(e)}

# ==========================================
# 5. 核心体验升级：独立的核对弹窗 (Dialog)
# ==========================================
@st.dialog("📝 核对并保存账单", width="large")
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
        
        # 弹窗内的提交按钮
        if st.form_submit_button("✅ 确认无误，保存进账本！"):
            # 1. 更新数据并写入本地文件
            st.session_state.ledger_data.extend(verified_data)
            save_data(st.session_state.ledger_data)
            
            # 2. 清空状态，准备迎接下一张图
            st.session_state.parsed_results = None
            st.session_state.uploader_key += 1 # 变更 Key，强制清空刚才上传的图片
            
            # 3. 放气球并刷新页面，关闭弹窗
            st.balloons()
            st.rerun()

# ==========================================
# 6. App 布局：拍照记账 & 我的账本
# ==========================================
tab1, tab2 = st.tabs(["📸 拍照记账", "📊 我的账本"])

with tab1:
    # 使用动态 Key，当我们保存成功后，改变 Key 就能让它变回干净的初始状态
    uploaded_file = st.file_uploader("上传截图/发票...", type=["jpg", "jpeg", "png", "webp"], key=f"uploader_{st.session_state.uploader_key}")

    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        # 把图片缩小一点展示，防止太占地方
        st.image(image, caption="待解析图片", width=300)
        
        if not api_key:
            st.warning("⚠️ 请先在左侧边栏输入 API Key！")
        else:
            if st.button("🚀 开始智能提取", use_container_width=True):
                with st.spinner("AI 正在光速解析，马上就好..."):
                    # 解析完后，把结果存入临时记忆体
                    st.session_state.parsed_results = analyze_receipt_with_ai(image, api_key)
                    # 强行刷新页面，触发弹窗弹出
                    st.rerun()
            
    # 如果检测到临时记忆体里有解析结果，立刻唤起弹窗！
    if st.session_state.parsed_results is not None:
        if isinstance(st.session_state.parsed_results, dict) and "error" in st.session_state.parsed_results:
            st.error(f"解析失败: {st.session_state.parsed_results['error']}")
            st.session_state.parsed_results = None # 失败后清空，允许重试
        else:
            confirm_dialog(st.session_state.parsed_results)

with tab2:
    st.subheader("流水复盘看板")
    
    if not st.session_state.ledger_data:
        st.info("📭 当前账本空空如也，快去第一页上传账单吧！")
    else:
        df = pd.DataFrame(st.session_state.ledger_data)
        
        if "收支" not in df.columns:
            df["收支"] = "支出"
            
        total_income = df[df["收支"] == "收入"]["金额 (¥)"].sum()
        total_expense = df[df["收支"] == "支出"]["金额 (¥)"].sum()
        balance = total_income - total_expense
        
        col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
        col1.metric("💰 总收入", f"¥ {total_income:.2f}")
        col2.metric("💸 总支出", f"¥ {total_expense:.2f}")
        col3.metric("💳 净结余", f"¥ {balance:.2f}")
        
        with col4:
            st.write("") 
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(label="📥 导出CSV", data=csv, file_name="我的账单流水.csv", mime="text/csv")
        
        st.markdown("---")
        st.data_editor(df, use_container_width=True, num_rows="dynamic")
