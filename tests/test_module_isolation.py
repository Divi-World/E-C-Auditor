import ast

def _imports(path):
    with open(path, encoding='utf-8') as f:
        tree = ast.parse(f.read())
    return [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]

def test_geo_audit_has_no_cro_imports():
    imports = _imports("src/revenue_leak_engine/audit/geo_audit.py")
    assert not any("site_audit" in (m or "") or "report_generator" in (m or "") for m in imports)

def test_site_audit_has_no_geo_imports():
    imports = _imports("src/revenue_leak_engine/audit/site_audit.py")
    assert not any("geo_audit" in (m or "") for m in imports)
