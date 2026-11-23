import importlib.util
import os
import sys
import tkinter as tk
from pathlib import Path
m=Path(__file__).resolve().parents[1]/'OpenDStroke.py'
spec=importlib.util.spec_from_file_location('keyhalo',m)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
mod.WindowsInput.start=lambda self:None
app=mod.OpenDStrokeApp()
app.root.update()
app.root.after(350,lambda:None)
# Test every UI page on a real Tk display and configurable styles.
for page in ('Dashboard','Styles','Inputs','Overlay','Settings','About'):
    app.navigate(page)
    app.root.update()
    assert app.body.winfo_children(),page
app.update_theme('Light')
app.root.update()
app.navigate('Dashboard')
app.root.update()
app.update_theme('Dark')
app.root.update()
app.navigate('Overlay')
app.test_overlay()
app.set_opacity('67')
app.root.update()
assert app.overlay.rows == {'keyboard': ['Ctrl', 'Shift', 'S'], 'mouse': ['Left click ×2']}
assert {app.overlay.canvas.itemcget(item, 'text') for item in app.overlay.canvas.find_all()
        if app.overlay.canvas.type(item) == 'text'} == {'Ctrl', 'Shift', 'S', 'Left click ×2'}
assert abs(float(app.overlay.win.wm_attributes('-alpha')) - .67) < .01
app.overlay.clear_row('mouse')
assert app.overlay.rows['keyboard'] and not app.overlay.rows['mouse']
app.overlay.hide()
app.root.update()
app.close()
print('UI smoke test PASS')
