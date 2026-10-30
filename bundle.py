import pathlib

with open('full_codebase.txt', 'w', encoding='utf-8') as out:
    for p in pathlib.Path('.').rglob('*'):
        if p.is_dir(): 
            continue
        
        f = p.as_posix()
        if '__pycache__' in f or 'results/raw/' in f: 
            continue
            
        try:
            if f.endswith('.py'):
                out.write(f"\n=== FILE: {f} ===\n```python\n{p.read_text(errors='ignore')}\n```\n")
            elif p.name in ['pyproject.toml', 'uv.lock', 'requirements.txt', 'setup_vm.sh']:
                out.write(f"\n=== FILE: {f} ===\n```text\n{p.read_text(errors='ignore')}\n```\n")
            elif f.endswith('.md'):
                out.write(f"\n=== DOCUMENTATION FILE: {f} ===\n{p.read_text(errors='ignore')}\n")
            elif f.endswith('.csv'):
                out.write(f"\n=== DATASET FILE: {f} ===\n```csv\n{p.read_text(errors='ignore')}\n```\n")
        except Exception:
            continue

print("Successfully compiled into full_codebase.txt!")
