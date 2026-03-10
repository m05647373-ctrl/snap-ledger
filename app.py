import streamlit as st
from PIL import Image
import google.generativeai as genai
import json
import pandas as pd

# ==========================================
# 1. 页面基本配置 & 初始化记忆体
# ==========================================
st.set_page_config(page_title="咔嚓记账 - AI视觉记账", page_icon="📸", layout="centered")

if 'ledger_data' not in st.session_state:
    st.session_state.ledger_data = []

if 'parsed_results' not in st.session_state:
    st.session_state.parsed_results = None

st.title("📸 咔嚓记账 SnapLedger")

# ==========================================
# 2. 侧边栏设置
# ==========================================
with st.sidebar:
    st.header("⚙️ 设置")
    api_key = st.text_input("请输入 Google Gemini API Key:", type="password")
    st.markdown("---")
    
    if st.button("🗑️ 清空所有账单数据"):
        st.session_state.ledger_data = []
        st.session_state.parsed_results = None
        st.success("数据已清空！")

# ==========================================
# 3. 核心功能：AI 批量解析账单 (强化收支判断规则)
# ==========================================
def analyze_receipt_with_ai(image, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    # 【核心升级】加入了明确的 + / - 符号识别规则
    prompt = """
    你是一个极其精准的财务助手。请分析这张截图，提取图中【所有】的流水记录。
    
    【⚠️ 极其重要的收支判断规则】：
    1. 支出判断：如果金额数字前带有 "-" 号（如 -35.00），或者明确是付款、消费、买单，请必须判定 "type" 为 "支出"。
    2. 收入判断：如果金额数字前带有 "+" 号（如 +50.00），或者明确标注为收款、退款、转入、工资，请必须判定 "type" 为 "收入"。
    3. 如果没有符号，请根据商家名称或交易场景推断。
    
    请严格按照以下 JSON 数组 (Array) 格式返回，金额请去掉正负号，只保留绝对值数字：
    [
      {
        "merchant": "星巴克",
        "type": "支出",
        "amount": 35.00,
        "time": "2026-03-11 14:30",
        "category": "餐饮"
      },
      {
        "merchant": "微信转账",
        "type": "收入",
        "amount": 500.00,
        "time": "2026-03-11 09:00",
        "category": "转账"
      }
    ]
    * type 字段只能是 "支出" 或 "收入"。
    * 分类建议：餐饮、交通、购物、居住、娱乐、投资、工资、退款、转账、其他。
    如果图中只有一笔，也请放在数组 [ ] 内返回。禁止输出任何多余的解释文字和Markdown标记。
    """
    
    try:
        response = model.generate_content([prompt, image])
        result_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(result_text)
    except Exception as e:
        return {"error": str(e)}

# ==========================================
# 4. App 布局：双标签页交互
# ==========================================
tab1, tab2 = st.tabs(["📸 拍照记账", "📊 我的账本"])

# ----------------- 标签页 1：拍照记账 -----------------
with tab1:
    uploaded_file = st.file_uploader("上传截图/发票...", type=["jpg", "jpeg", "png", "webp"])

    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption="待解析图片", use_container_width=True)
        
        if not api_key:
            st.warning("⚠️ 请先在左侧边栏输入 API Key！")
        else:
            if st.button("🚀 开始智能批量录入"):
                with st.spinner("AI 正在光速解析账单，请稍候..."):
                    st.session_state.parsed_results = analyze_receipt_with_ai(image, api_key)
            
            if st.session_state.parsed_results is not None:
                results = st.session_state.parsed_results
                
                if isinstance(results, dict) and "error" in results:
                    st.error(f"解析失败: {results['error']}")
                else:
                    st.success(f"🎉 成功识别出 {len(results)} 笔账单！请核对：")
                    
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
                                "时间": time,
                                "收支": tx_type, 
                                "商家": merchant,
                                "分类": category,
                                "金额 (¥)": amount
                            })
                        
                        submit_btn = st.form_submit_button("✅ 全部确认并保存")
                        if submit_btn:
                            st.session_state.ledger_data.extend(verified_data)
                            st.session_state.parsed_results = None 
                            st.balloons() 
                            st.success("数据已成功存入账本！")

# ----------------- 标签页 2：我的账本 -----------------
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
