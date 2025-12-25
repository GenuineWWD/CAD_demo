import math
from pyautocad import Autocad, APoint

def draw_mechanical_flower():
    # 1. 自动连接到当前打开的 AutoCAD 实例
    try:
        acad = Autocad(create_if_not_exists=True)
        print(f"已连接到 AutoCAD: {acad.doc.Name}")
    except Exception as e:
        print("无法连接到 AutoCAD，请确保 AutoCAD 已打开。")
        return

    # 2. 定义基本参数
    center_x, center_y = 0, 0
    center = APoint(center_x, center_y)
    base_radius = 50          # 中心圆半径
    arm_length = 150          # 辐射臂长度
    num_petals = 12           # 花瓣（辐射臂）的数量
    
    print("开始绘图...")

    # 3. 绘制中心圆
    # AddCircle(圆心, 半径)
    acad.model.AddCircle(center, base_radius)
    
    # 绘制中心的一个小装饰圆
    acad.model.AddCircle(center, base_radius / 4)

    # 4. 循环绘制辐射结构
    for i in range(num_petals):
        # 计算角度 (将角度转换为弧度)
        angle_deg = i * (360 / num_petals)
        angle_rad = math.radians(angle_deg)

        # 计算这一条臂的终点坐标
        # x = r * cos(theta), y = r * sin(theta)
        end_x = center_x + arm_length * math.cos(angle_rad)
        end_y = center_y + arm_length * math.sin(angle_rad)
        end_point = APoint(end_x, end_y)

        # 绘制连接线
        # AddLine(起点, 终点)
        line = acad.model.AddLine(center, end_point)
        
        # 绘制末端的圆圈（像花瓣或齿轮）
        petal_radius = 20
        acad.model.AddCircle(end_point, petal_radius)
        
        # 在末端圆圈里再画一个小圆
        acad.model.AddCircle(end_point, petal_radius / 3)

    # 5. 添加文字说明
    # 文字位置放在图案下方
    text_pos = APoint(center_x - 60, center_y - arm_length - 40)
    text_height = 15
    text_content = "Python AutoCAD Art"
    
    # AddText(内容, 插入点, 字高)
    acad.model.AddText(text_content, text_pos, text_height)

    # 6. 提示完成
    # ZoomExtents 会自动缩放视图以显示所有绘制的物体
    acad.app.ZoomExtents()
    print("绘图完成！请查看 AutoCAD 窗口。")

if __name__ == "__main__":
    draw_mechanical_flower()