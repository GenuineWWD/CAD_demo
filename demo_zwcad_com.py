import win32com.client
import pythoncom # 必须导入这个来处理 COM 数据类型
import math

def draw_with_zwcad():
    try:
        # 1. 连接中望CAD
        # 如果 ZCAD.Application 不行，就用 ZwCAD.Application
        try:
            app = win32com.client.GetActiveObject("ZwCAD.Application")
        except:
            app = win32com.client.Dispatch("ZwCAD.Application")
            
        app.Visible = True
        doc = app.ActiveDocument
        ms = doc.ModelSpace

        print("连接成功，正在绘制...")

        # 辅助函数：将 Python 列表转为 CAD 要求的双精度数组 VARIANT
        def p(x, y, z=0):
            return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, (x, y, z))

        # 2. 绘制一个简单的几何图形：正方形和内接圆
        size = 100
        
        # 绘制四条边（起点坐标，终点坐标）
        points = [
            (0, 0), (size, 0),
            (size, size), (0, size),
            (0, 0)
        ]
        
        for i in range(len(points)-1):
            start = p(points[i][0], points[i][1])
            end = p(points[i+1][0], points[i+1][1])
            ms.AddLine(start, end)

        # 3. 绘制中心圆
        center = p(size/2, size/2)
        ms.AddCircle(center, size/2)

        # 4. 这里的文字提醒
        text_pos = p(0, -20)
        ms.AddText("Python 自动绘制完成", text_pos, 10)

        print("绘制任务已完成！")

    except Exception as e:
        print(f"运行出错: {e}")

if __name__ == "__main__":
    draw_with_zwcad()