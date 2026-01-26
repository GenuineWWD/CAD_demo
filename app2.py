import streamlit as st
import re
import sys
import io
import traceback
import logging
import math
import pythoncom
from pyautocad import Autocad, APoint, aDouble
from openai import OpenAI

# ================= 1. 配置区域 =================
API_KEY = "EMPTY" 
# BASE_URL = "http://10.184.17.223:12345/v1"
BASE_URL = "http://localhost:12345/v1"
MODEL_NAME = "Qwen3-8B"

# ================= 2. 日志与工具函数 =================

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

def extract_code(text):
    """仅提取代码用于执行"""
    pattern = r"```python\s*(.*?)\s*```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1)
    if "acad.model" in text or "APoint" in text:
        return text
    return ""

def render_assistant_msg(content):
    """
    【新增】专门的渲染函数：
    检测内容中是否有 Python 代码块，如果有，则将其放入折叠面板中。
    """
    # 使用正则将文本分割为：[前文, 代码, 后文]
    # re.split 会保留捕获组 () 中的内容
    pattern = r"```python\s*(.*?)\s*```"
    parts = re.split(pattern, content, flags=re.DOTALL)
    
    if len(parts) > 1:
        # parts[0] 是代码前的文字 (例如 "执行成功")
        # parts[1] 是被捕获的代码内容
        # parts[2] 是代码后的文字 (例如 "执行日志")
        
        if parts[0].strip():
            st.markdown(parts[0])
            
        # 核心修改：使用 expander 折叠代码
        with st.expander("📜 点击查看生成的 Python 代码", expanded=False):
            st.code(parts[1], language="python")
            
        if len(parts) > 2 and parts[2].strip():
            st.markdown(parts[2])
    else:
        # 如果没有代码块，直接显示全文
        st.markdown(content)

def execute_pyautocad_code(code_str):
    """执行 pyautocad 代码，包含 CoInitialize 修复"""
    pythoncom.CoInitialize() 

    old_stdout = sys.stdout
    redirected_output = sys.stdout = io.StringIO()
    
    acad_instance = None
    
    try:
        logger.info("Connecting to AutoCAD...")
        try:
            acad_instance = Autocad(create_if_not_exists=True)
            doc_name = acad_instance.doc.Name
            logger.info(f"Connected to: {doc_name}")
        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False, "❌ 无法连接到 AutoCAD。请确保软件已打开。", ""

        local_scope = {
            'acad': acad_instance, 
            'APoint': APoint, 
            'aDouble': aDouble,
            'math': math
        }

        # 自动追加视图刷新
        final_code = code_str + "\n\n# 系统自动追加：刷新视图\ntry:\n    acad.app.ZoomExtents()\n    acad.app.Update()\nexcept: pass"
        
        exec(final_code, globals(), local_scope)
        
        stdout_log = redirected_output.getvalue()
        return True, f"✅ 操作CAD绘制成功!请打开CAD软件查看结果 (文档: {doc_name})", stdout_log

    except Exception:
        error_msg = traceback.format_exc()
        logger.error(f"Execution logic failed: {error_msg}")
        return False, error_msg, redirected_output.getvalue()
    finally:
        sys.stdout = old_stdout
        try:
            pythoncom.CoUninitialize()
        except:
            pass

# ================= 3. 页面 UI 逻辑 =================

st.set_page_config(page_title="AutoCAD Live Agent", layout="wide", page_icon="🏗️")

CORE_INSTRUCTIONS = """
你是一个 Python pyautocad 库的专家。你的任务是将用户的自然语言转换为 Python 代码，直接在 AutoCAD 中绘图。

**运行环境说明：**
1. 变量 `acad`, `APoint`, `math` 已直接可用，无需导入。
2. 严禁使用 input()。
3. 必须使用 ActiveX API，如 `acad.model.AddLine`, `acad.model.AddCircle`。
4. 坐标点必须使用 `APoint(x, y)`。

请直接输出代码块。
"""

with st.sidebar:
    st.header("🏗️ 控制面板")
    if st.button("🗑️ 清除对话 / 新任务", type="primary"):
        st.session_state.messages = [] 
        st.rerun()
    st.divider()
    st.markdown("**状态:** 🟢 系统就绪")
    show_debug = st.checkbox("显示调试信息", value=True)

st.title("🏗️ AutoCAD 智能绘图助手")

if "messages" not in st.session_state:
    st.session_state.messages = []

# --- 渲染逻辑修改 ---
for msg in st.session_state.messages:
    if msg["role"] == "user":
        display_text = msg.get("display_content", msg["content"])
        st.chat_message("user").write(display_text)
    elif msg["role"] == "assistant" and not msg.get("is_error_fix", False):
        with st.chat_message("assistant"):
            # 【修改点 1】调用自定义渲染函数，而不是直接 write
            render_assistant_msg(msg["content"])

if prompt := st.chat_input("例如：画一个五角星"):
    
    if len(st.session_state.messages) == 0:
        full_content = f"{CORE_INSTRUCTIONS}\n\n--- 用户需求 ---\n{prompt}"
        new_msg = {
            "role": "user", 
            "content": full_content,        
            "display_content": prompt       
        }
    else:
        new_msg = {
            "role": "user", 
            "content": prompt
        }

    st.chat_message("user").write(new_msg.get("display_content", new_msg["content"]))
    st.session_state.messages.append(new_msg)

    with st.chat_message("assistant"):
        status_box = st.status("🤖 AI 正在思考与绘图...", expanded=True)
        
        api_messages = [
            {"role": m["role"], "content": m["content"]} 
            for m in st.session_state.messages
        ]

        current_api_messages = api_messages.copy()
        max_retries = 3
        attempt = 0
        success = False
        final_response = ""

        while attempt < max_retries:
            try:
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=current_api_messages,
                    temperature=0.7,
                    max_tokens=8192
                )
                
                content = response.choices[0].message.content
                print(response)
                code = extract_code(content)
                
                if show_debug:
                    # 在 status_box 里显示代码也折叠起来，保持整洁
                    status_box.write(f"**尝试 #{attempt+1} 生成完毕，准备执行...**")
                    # Debug 这里的代码可以不折叠，或者保持现状，看你想不想看过程
                    # 这里保持现状，方便调试

                if not code:
                    status_box.update(label="⚠️ 未检测到代码", state="complete")
                    final_response = content
                    success = True
                    break
                
                status_box.write(f"正在发送指令到 AutoCAD...")
                exec_success, result_msg, logs = execute_pyautocad_code(code)
                
                if exec_success:
                    success = True
                    status_box.update(label="✅ 绘图完成", state="complete", expanded=False)
                    
                    # 构造最终响应字符串，保持 Markdown 格式以便后续 regex 解析
                    final_response = f"**执行成功！**\n\n```python\n{code}\n```\n\n{result_msg}"
                    break
                else:
                    status_box.write(f"❌ 尝试 #{attempt+1} 失败: {result_msg}")
                    error_feedback = f"代码执行出错，请修复。错误信息：\n{result_msg}"
                    current_api_messages.append({"role": "assistant", "content": content})
                    current_api_messages.append({"role": "user", "content": error_feedback})
                    attempt += 1
            
            except Exception as e:
                status_box.update(label="💥 系统错误", state="error")
                st.error(f"发生未预期的错误: {e}")
                break
        
        if success:
            # 【修改点 2】实时输出时，也调用自定义渲染函数
            render_assistant_msg(final_response)
            st.session_state.messages.append({"role": "assistant", "content": final_response})
        else:
            fail_msg = "❌ 任务失败。"
            st.error(fail_msg)
            st.session_state.messages.append({"role": "assistant", "content": fail_msg})