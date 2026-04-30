with open(r'c:\Users\Dell\OneDrive\Desktop\Backend_PSS\patient_scheduling_system\hospital\views.py', 'rb') as f:
    lines = f.readlines()
    line_91 = lines[90]
    print(line_91)
    print([hex(b) for b in line_91])
