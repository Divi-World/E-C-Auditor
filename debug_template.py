with open('src/revenue_leak_engine/reporting/report_generator.py', 'r', encoding='utf-8') as f:
    gen = f.read()
with open('src/revenue_leak_engine/reporting/templates/report.html', 'r', encoding='utf-8') as f:
    html = f.read()

print('=== GENERATOR RENDER & NORMALIZATION ===')
start = gen.find('def generate_report')
if start != -1: print(gen[start:start+3500])

print('\n=== TEMPLATE ISSUE CARD HTML ===')
start = html.find('issue-card high')
if start != -1: print(html[start-50:start+800])
