import streamlit as st
import json
import re
import sys
import io
import traceback
import ezdxf
import os
import matplotlib.pyplot as plt
import logging

from openai import OpenAI
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

# ================= 配置区域 =================
API_KEY = "EMPTY"
# 请确保你的 LLM 服务地址正确
BASE_URL = "http://10.184.17.223:12345/v1" 
MODEL_NAME = "Qwen3-8B"
OUTPUT_FILE = "generated_drawing.dxf"

# === 核心：隐藏的指令 (注入到 API 请求中，不在前端显示) ===
HIDDEN_INSTRUCTION = f"""
你是一个 Python ezdxf 库的专家。你的任务是根据用户的自然语言描述编写 Python 代码。
1. 直接输出可执行的 Python 代码。
2. 必须导入 ezdxf。
3. 创建新图纸使用 ezdxf.new()。
4. **最后必须将图纸保存为 '{OUTPUT_FILE}'**。
5. 不要做任何需要用户键盘输入的操作 (如 input())。
6. 尽量使用常见的 ezdxf 操作，确保兼容性。
7. 如果之前有报错，请根据报错信息修正代码。
--------------------------------------------------
用户需求：
"""

# === 日志配置 ===
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("CAD_Agent")

@st.cache_resource
def get_client():
    return OpenAI(api_key=API_KEY, base_url=BASE_URL)

client = get_client()

# ================= 工具函数 =================

def extract_code(text):
    """从 LLM 回复中提取 Python 代码块"""
    pattern = r"```python\s*(.*?)\s*```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1)
    if "import ezdxf" in text:
        return text
    return ""

def execute_ezdxf_code(code_str):
    """执行生成的代码"""
    old_stdout = sys.stdout
    redirected_output = sys.stdout = io.StringIO()
    local_scope = {}
    
    try:
        # 确保每次执行前清理旧文件
        if os.path.exists(OUTPUT_FILE):
            os.remove(OUTPUT_FILE)

        logger.info("Executing generated code...")
        # 警告：exec 存在安全风险，仅在受控环境使用
        exec(code_str, globals(), local_scope)
        
        stdout_log = redirected_output.getvalue()
        
        if os.path.exists(OUTPUT_FILE):
            logger.info("Execution successful, file generated.")
            return True, "执行成功", stdout_log
        else:
            logger.warning("Execution finished but file not found.")
            return False, f"代码执行没有报错，但未检测到 {OUTPUT_FILE} 文件生成。请确保代码包含 doc.saveas('{OUTPUT_FILE}')。", stdout_log
            
    except Exception:
        error_msg = traceback.format_exc()
        logger.error(f"Execution failed: {error_msg}")
        return False, error_msg, redirected_output.getvalue()
    finally:
        sys.stdout = old_stdout

def render_dxf_to_image(dxf_path):
    """将 DXF 文件渲染为 matplotlib 图片流"""
    try:
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
        
        # 创建图形上下文
        fig = plt.figure(dpi=150) # DPI 这里的清晰度
        ax = fig.add_axes([0, 0, 1, 1])
        ctx = RenderContext(doc)
        out = MatplotlibBackend(ax)
        
        # 渲染
        Frontend(ctx, out).draw_layout(msp, finalize=True)
        
        # 保存到内存
        img_buffer = io.BytesIO()
        fig.savefig(img_buffer, format='png', bbox_inches='tight')
        plt.close(fig) # 释放内存
        img_buffer.seek(0)
        return img_buffer, None
    except Exception as e:
        logger.error(f"Image rendering failed: {e}")
        return None, str(e)

def build_api_messages(ui_messages):
    """
    构建 API 消息列表：
    找到第一条用户消息，并在其内容前拼接 HIDDEN_INSTRUCTION。
    这样用户在界面上看不到这一大段提示词，但模型能看到。
    """
    api_msgs = []
    
    # 找到第一条 role='user' 的消息索引
    first_user_idx = -1
    for i, msg in enumerate(ui_messages):
        if msg["role"] == "user":
            first_user_idx = i
            break
            
    for i, msg in enumerate(ui_messages):
        new_msg = msg.copy() # 浅拷贝，不影响 Session State
        if i == first_user_idx:
            new_msg["content"] = HIDDEN_INSTRUCTION + new_msg["content"]
        api_msgs.append(new_msg)
        
    return api_msgs

# ================= 页面主逻辑 =================

st.set_page_config(page_title="Auto-CAD Agent", layout="wide", page_icon="🏗️")

# === 侧边栏：控制面板 ===
with st.sidebar:
    st.header("🛠️ 控制面板")
    
    if st.button("🗑️ 清除上下文 / 开始新任务", type="primary"):
        st.session_state.messages = [] # 清空历史
        if os.path.exists(OUTPUT_FILE):
            try: os.remove(OUTPUT_FILE)
            except: pass
        st.rerun() # 强制刷新页面
    
    st.divider()
    show_debug = st.checkbox("显示实时调试面板", value=True, help="显示代码生成、报错和重试的详细日志")
    st.markdown(f"**Current Model:** `{MODEL_NAME}`")

st.title("🏗️ 智能 CAD 绘图助手")

# 初始化对话历史 (纯净版，不含系统提示词)
if "messages" not in st.session_state:
    st.session_state.messages = []

# 1. 展示历史消息
for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.chat_message("user").write(msg["content"])
    elif msg["role"] == "assistant" and not msg.get("is_error_fix", False):
        st.chat_message("assistant").write(msg["content"])

# 2. 处理用户输入
if prompt := st.chat_input("例如：画一个中心在(0,0)，半径为50的圆"):
    
    # 前端展示
    st.chat_message("user").write(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    logger.info(f"New User Request: {prompt}")

    with st.chat_message("assistant"):
        status_container = st.empty()
        status_container.info("🤖 正在思考并编写代码...")

        max_retries = 3
        attempt = 0
        success = False
        final_response_text = ""
        generated_image = None
        
        # 初始化 msg，防止 NameError
        msg = "未知错误 (未收到代码或执行被中断)"

        # 构建发送给 API 的消息 (包含隐藏指令)
        current_api_messages = build_api_messages(st.session_state.messages)

        while attempt < max_retries:
            debug_container = st.empty()
            
            try:
                logger.info(f"--- Attempt {attempt + 1} Start ---")
                
                # 调用 LLM
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=current_api_messages,
                    temperature=0.7,
                    max_tokens=8192
                )
                llm_content = response.choices[0].message.content
                code = extract_code(llm_content)
                
                # === Debug 面板展示 ===
                if show_debug:
                    with debug_container.expander(f"🔍 第 {attempt + 1} 次尝试详情 (Debug Log)", expanded=False):
                        if attempt == 0:
                            st.caption("ℹ️ 实际发给模型的 User Prompt (首行包含隐藏指令):")
                            for m in current_api_messages:
                                if m['role'] == 'user':
                                    st.code(m['content'][:200] + "...", language="text")
                                    break
                        st.markdown("**模型回复:**")
                        st.code(llm_content, language="markdown")
                        st.markdown("**提取代码:**")
                        st.code(code, language="python")
                
                if not code:
                    logger.info("No code found in response.")
                    final_response_text = llm_content
                    success = True
                    break

                status_container.info(f"⚙️ 正在执行代码 (第 {attempt + 1} 次尝试)...")
                
                # 执行代码
                exec_success, msg, logs = execute_ezdxf_code(code)

                # 补充执行结果到 Debug 面板
                if show_debug:
                    with debug_container.expander(f"🔍 第 {attempt + 1} 次尝试详情 (Debug Log)", expanded=False):
                        st.markdown("**执行结果:**")
                        if logs: st.text(f"Stdout:\n{logs}")
                        if exec_success: st.success("Success")
                        else: st.error(f"Failed:\n{msg}")

                if exec_success:
                    success = True
                    final_response_text = f"✅ 绘图成功！\n\n*生成的代码逻辑：*\n```python\n{code}\n```"
                    
                    status_container.info("🎨 正在生成预览图...")
                    img_buffer, img_err = render_dxf_to_image(OUTPUT_FILE)
                    if img_buffer:
                        generated_image = img_buffer
                    else:
                        logger.error(f"Preview failed: {img_err}")
                        final_response_text += f"\n\n⚠️ 预览生成失败: {img_err}"
                    break # 成功跳出循环
                else:
                    # === 自动修正逻辑 ===
                    logger.warning(f"Attempt {attempt + 1} failed.")
                    error_feedback = f"执行代码报错：\n{msg}\n请修复代码并确保保存为 {OUTPUT_FILE}。"
                    
                    # 将本次失败的对话加入到临时的 API 上下文中
                    current_api_messages.append({"role": "assistant", "content": llm_content})
                    current_api_messages.append({"role": "user", "content": error_feedback})
                    
                    attempt += 1
            
            except Exception as e:
                # 捕获系统级异常 (如 API 连接断开)
                msg = f"系统错误: {str(e)}"
                status_container.error(msg)
                if show_debug: st.exception(e)
                break

        status_container.empty() # 清除进度条
        
        if success:
            st.markdown(final_response_text)
            
            # 布局：下载按钮 和 预览
            col1, col2 = st.columns([1, 1])
            with col1:
                if os.path.exists(OUTPUT_FILE):
                    with open(OUTPUT_FILE, "rb") as file:
                        st.download_button(
                            label="📥 下载 .dxf 原文件",
                            data=file,
                            file_name="drawing.dxf",
                            mime="application/dxf"
                        )
            
            if generated_image:
                with st.expander("👁️ 点击预览生成效果 (图片)", expanded=True):
                    st.image(generated_image, caption="DXF 渲染预览", use_container_width=True)
            
            # 将助手的最终回复存入 Session State (用于展示)
            st.session_state.messages.append({"role": "assistant", "content": final_response_text})
            
        else:
            # 失败处理，此时 msg 必定已被赋值
            logger.error("Task failed after retries.")
            fail_msg = f"❌ 任务失败，已达最大重试次数。\n错误详情：\n```{msg}```"
            st.error(fail_msg)
            st.session_state.messages.append({"role": "assistant", "content": fail_msg})