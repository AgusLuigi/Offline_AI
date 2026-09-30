import json

nb = json.load(open('notebooks/ollama_model_download_utility.ipynb', encoding='utf-8'))
cells = nb['cells']
print('Total cells:', len(cells))
for i, cell in enumerate(cells):
    src = ''.join(cell['source'])
    ctype = cell['cell_type']
    print(f'=== Cell {i} ({ctype}) {len(src)} chars ===')
    print(src[:400])
    print()
