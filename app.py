import streamlit as st
from PIL import Image
import google.generativeai as genai
import json
import pandas as pd

# ==========================================
# 1. 页面基本配置 & 初始化“数据库”
# ==========================================
st.set_page_config(page_title="咔嚓记账 - AI视觉记账", page_icon="📸", layout="centered")

# 使用 Streamlit 的 session_state 在内存中临时保存账单数据
if 'ledger_data' not in st.session_state:
    st.session_state.ledger_data = []

st.title("📸 咔嚓记账 SnapLedger")

# ==========================================
# 2. 侧边栏设置
# ==========================================
with st.sidebar:
    st.header("⚙️ 设置")
    api_key = st.text_input("请输入 Google Gemini API Key:", type="password")
    st.markdown("---")
    # 添加一个清空数据的按钮
    if st.button("🗑️ 清空所有账单数据"):
        st.session_state.ledger_data = []
        st.success("数据已清空！")

# ==========================================
# 3. 核心功能：AI 批量解析账单
# ==========================================
def analyze_receipt_with_ai(image, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    # 【核心修改 1】修改 Prompt，要求返回 JSON 数组 (Array)，支持多条数据
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
        return json.loads(result_text) # 现在返回的是一个包含多个字典的列表 (List)
    except Exception as e:
        return {"error": str(e)}

# ==========================================
# 4. App 布局：使用 Tabs 拆分“记账”和“看账”
# ==========================================
tab1, tab2 = st.tabs(["📸 拍照记账", "📊 我的账本"])

with tab1:
    uploaded_file = st.file_uploader("上传长截图/多条账单截图...", type=["jpg", "jpeg", "png", "webp"])

    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption="待解析图片", use_container_width=True)
        
        if not api_key:
            st.warning("⚠️ 请先在左侧输入 API Key！")
        else:
            if st.button("🚀 开始智能批量录入"):
                with st.spinner("AI 正在解析所有账单，请稍候..."):
                    results = analyze_receipt_with_ai(image, api_key)
                    
                    if isinstance(results, dict) and "error" in results:
                        st.error(f"解析失败: {results['error']}")
                    else:
                        st.success(f"🎉 成功识别出 {len(results)} 笔账单！")
                        
                        # 遍历结果，并使用表单让用户确认修改
                        with st.form("batch_confirm_form"):
                            st.write("请核对以下解析结果：")
                            
                            # 创建空列表，用于存储用户核对后的数据
                            verified_data = []
                            
                            # 动态生成每一行账单的输入框
                            for i, item in enumerate(results):
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
                            
                            # 提交按钮
                            if st.form_submit_button("✅ 全部确认并保存"):
                                # 【核心修改 2】将确认后的数据追加到全局的 session_state 列表中
                                st.session_state.ledger_data.extend(verified_data)
                                st.balloons()
                                st.success("数据已成功存入账本！请点击上方【📊 我的账本】查看。")

with tab2:
    st.subheader("流水复盘看板")
    
    # 检查是否有数据
    if not st.session_state.ledger_data:
        st.info("📭 当前账本空空如也，快去记一笔吧！")
    else:
        # 使用 Pandas 将数据列表转换为 DataFrame (数据表)
        df = pd.DataFrame(st.session_state.ledger_data)
        
        # 计算总支出
        total_expense = df["金额 (¥)"].sum()
        
        # 显示统计指标
        st.metric(label="累计总支出", value=f"¥ {total_expense:.2f}")
        
        # 显示可交互的表格 (用户甚至可以在表格里再次修改或排序)
        st.data_editor(df, use_container_width=True, num_rows="dynamic")




