from pyzwcad import ZwCAD, APoint
acad = ZwCAD()
acad.prompt("Hello, ZWCAD from Python\n")
print(acad.doc.Name)
p1 = APoint(0, 0)
p2 = APoint(50, 25)
for i in range(5):
   acad.model.AddText(f'Hi {i}!', p1, 2.5)
   acad.model.AddLine(p1, p2)
   acad.model.AddCircle(p1, 10)
   p1.y += 10
for text in acad.iter_objects('Text'):
   print(f'Text: {text.TextString} at {text.InsertionPoint}')