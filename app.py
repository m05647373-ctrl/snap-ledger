import streamlit as st
from PIL import Image
import google.generativeai as genai
import json
import pandas as pd

# ==========================================
# 1. 页面基本配置 & 初始化记忆体
# ==========================================
st.set_page_config(page_title="咔嚓记账 - AI视觉记账", page_icon="📸", layout="centered")

# 初始化全局账本数据 (永久存放在当前网页会话中)
if 'ledger_data' not in st.session_state:
    st.session_state.ledger_data = []

# 初始化临时解析结果 (为了解决确认表单突然消失的Bug)
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
    
    # 清空数据的危险操作
    if st.button("🗑️ 清空所有账单数据"):
        st.session_state.ledger_data = []
        st.session_state.parsed_results = None
        st.success("数据已清空！")

# ==========================================
# 3. 核心功能：AI 批量解析账单
# ==========================================
def analyze_receipt_with_ai(image, api_key):
    genai.configure(api_key=api_key)
    # 使用我们探测出来的、速度最快的模型
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = """
    你是一个智能财务助手。请分析这张图片，提取图片中【所有】的消费记录。
    如果是长截图或包含多笔账单，请逐一提取。
    请严格按照以下 JSON 数组 (Array) 格式返回，不要多余文字：
    [
      {
        "merchant": "商家名称1",
        "amount": 100.50,
        "time": "2026-03-11 14:30",
        "category": "餐饮"
      },
      {
        "merchant": "商家名称2",
        "amount": 25.00,
        "time": "2026-03-11 15:00",
        "category": "交通"
      }
    ]
    如果图中只有一笔消费，也请放在数组 [ ] 内返回。
    分类仅限：餐饮、交通、购物、居住、娱乐、投资、其他。
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
    uploaded_file = st.file_uploader("上传长截图/多条账单截图...", type=["jpg", "jpeg", "png", "webp"])

    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption="待解析图片", use_container_width=True)
        
        if not api_key:
            st.warning("⚠️ 请先在左侧边栏输入 API Key！")
        else:
            # 按钮：开始解析
            if st.button("🚀 开始智能批量录入"):
                with st.spinner("AI 正在光速解析所有账单，请稍候..."):
                    # 将解析结果存入临时记忆体，防止页面刷新丢失
                    st.session_state.parsed_results = analyze_receipt_with_ai(image, api_key)
            
            # 只要临时记忆体里有数据，就展示核对表单
            if st.session_state.parsed_results is not None:
                results = st.session_state.parsed_results
                
                if isinstance(results, dict) and "error" in results:
                    st.error(f"解析失败: {results['error']}")
                else:
                    st.success(f"🎉 成功识别出 {len(results)} 笔账单！请核对下面提取的信息：")
                    
                    # 动态生成表单
                    with st.form("batch_confirm_form"):
                        verified_data = []
                        for i, item in enumerate(results):
                            # 四列排布，整齐美观
                            cols = st.columns([2, 2, 2, 2])
                            merchant = cols[0].text_input(f"商家 {i+1}", value=item.get("merchant", ""), key=f"m_{i}")
                            amount = cols[1].number_input(f"金额 {i+1}", value=float(item.get("amount", 0.0)), format="%.2f", key=f"a_{i}")
                            time = cols[2].text_input(f"时间 {i+1}", value=item.get("time", ""), key=f"t_{i}")
                            category = cols[3].text_input(f"分类 {i+1}", value=item.get("category", "其他"), key=f"c_{i}")
                            
                            verified_data.append({
                                "时间": time,
                                "商家": merchant,
                                "分类": category,
                                "金额 (¥)": amount
                            })
                        
                        # 提交确认
                        submit_btn = st.form_submit_button("✅ 全部确认并保存")
                        if submit_btn:
                            # 1. 将核对后的数据追加到全局账本中
                            st.session_state.ledger_data.extend(verified_data)
                            # 2. 清空临时记忆体，隐藏表单，准备下一次记账
                            st.session_state.parsed_results = None 
                            st.balloons() # 放气球特效
                            st.success("数据已成功存入账本！请点击上方【📊 我的账本】查看。")

# ----------------- 标签页 2：我的账本 -----------------
with tab2:
    st.subheader("流水复盘看板")
    
    if not st.session_state.ledger_data:
        st.info("📭 当前账本空空如也，快去第一页上传账单吧！")
    else:
        # 转换为表格
        df = pd.DataFrame(st.session_state.ledger_data)
        total_expense = df["金额 (¥)"].sum()
        
        # 左右分列展示统计信息和下载按钮
        col1, col2 = st.columns([3, 1])
        with col1:
            st.metric(label="累计总支出", value=f"¥ {total_expense:.2f}")
        with col2:
            # 新增：导出数据功能
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 导出为 CSV",
                data=csv,
                file_name="我的账单流水.csv",
                mime="text/csv",
            )
        
        # 显示交互式表格
        st.data_editor(df, use_container_width=True, num_rows="dynamic")


