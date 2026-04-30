with open(r'c:\Users\Dell\OneDrive\Desktop\Backend_PSS\patient_scheduling_system\authentication\views.py', 'r') as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        if "return Response(list(doctors)" in line:
            print(f"Line {i+1}: {repr(line)}")
