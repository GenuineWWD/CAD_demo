import os
import matplotlib.pyplot as plt
import ezdxf
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

def sanitize_filename(name):
    """清理文件名，防止保存时出错"""
    return "".join([c for c in name if c.isalnum() or c in (' ', '_', '-')]).strip()

def extract_blocks_to_images(dxf_path, output_dir="block_images"):
    # 1. 检查文件
    if not os.path.exists(dxf_path):
        print(f"错误: 找不到文件 {dxf_path}")
        return

    # 2. 创建输出目录
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"已创建输出目录: {output_dir}")

    # 3. 读取DXF
    try:
        doc = ezdxf.readfile(dxf_path)
        print(f"成功读取文件: {dxf_path}")
    except Exception as e:
        print(f"读取DXF文件失败: {e}")
        return

    # 准备渲染上下文
    try:
        ctx = RenderContext(doc)
    except Exception as e:
        print(f"初始化渲染上下文失败: {e}")
        return
    
    count = 0
    print("开始提取元件块...")

    # 4. 遍历所有块 (Blocks)
    for block in doc.blocks:
        # 过滤掉布局和匿名块（以*开头）
        if block.name.startswith('*'):
            continue
        
        block_name = block.name
        safe_name = sanitize_filename(block_name)
        if not safe_name:
            safe_name = f"unknown_block_{count}"

        print(f"正在处理: {block_name} ...", end="")

        # 创建绘图对象
        fig = plt.figure()
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_axis_off() # 隐藏坐标轴

        try:
            # 设置后端
            out = MatplotlibBackend(ax)
            frontend = Frontend(ctx, out)

            # ---【核心修改点】---
            # 原来的 draw_layout 会找打印设置导致报错
            # 改用 draw_entities，直接画里面的线条，不处理打印属性
            frontend.draw_entities(block)
            # --------------------
            
            # 结束绘制
            out.finalize()
            ax.autoscale(True)
            
            # 保持比例 (防止空块报错)
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()
            if xlim[1] > xlim[0] and ylim[1] > ylim[0]:
                ax.set_aspect('equal', 'datalim')

            # 保存图片
            output_path = os.path.join(output_dir, f"{safe_name}.png")
            fig.savefig(output_path, dpi=300, bbox_inches='tight', pad_inches=0.1)
            print(f" 成功")
            count += 1

        except Exception as e:
            # 打印具体的错误信息，方便调试
            print(f" 失败 ({e})")
        finally:
            plt.close(fig)

    print(f"\n全部完成! 共保存了 {count} 张元件图片。")


if __name__ == "__main__":
    # 请在这里修改您的DXF文件路径
    dxf_file = r"D:\work\power\daquan\A21232_0322_一次系统图.dxf"
    
    extract_blocks_to_images(dxf_file,'output')