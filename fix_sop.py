import pathlib, ast

p = pathlib.Path("src/revenue_leak_engine/pipeline.py")
t = p.read_text("utf-8")

SM = "# ENTERPRISE SNIPPET INJECTION: Force JSON-LD into the HTML report"
EM = "# DETERMINISTIC OPPORTUNITY TIER"
si = t.find(SM)
ei = t.find(EM)

if si == -1 or ei == -1:
    print("[!] Markers not found"); exit(1)

# Build the new block as a list of lines
B = []
B.append("# ENTERPRISE SNIPPET INJECTION: Issue-Specific Platform-Native SOPs")
B.append('            platform = geo_findings.get("platform_detected", "unknown")')
B.append("            issue_sops = {")
B.append('                "missing_organization_entity": {')
B.append('                    "shopify": "<strong>Exact Path:</strong> <code>layout/theme.liquid</code> (paste in &lt;head&gt;).<br><strong>Validation:</strong> Test Homepage via Schema Markup Validator.<br><strong>Rollback:</strong> Revert via Theme History.",')
B.append('                    "woocommerce": "<strong>Exact Path:</strong> <code>header.php</code> or Yoast/RankMath Global Schema.<br><strong>Validation:</strong> Test Homepage via Schema Markup Validator.<br><strong>Rollback:</strong> Restore via FTP.",')
B.append('                    "bigcommerce": "<strong>Exact Path:</strong> <code>Storefront &gt; Script Manager</code>.<br><strong>Validation:</strong> Rich Results Test.<br><strong>Rollback:</strong> Delete script.",')
B.append('                    "magento": "<strong>Exact Path:</strong> <code>header.phtml</code> or XML layout.<br><strong>Validation:</strong> Rich Results Test + cache flush.<br><strong>Rollback:</strong> Git revert."')
B.append("                },")
B.append('                "incomplete_product_schema": {')
B.append('                    "shopify": "<strong>Exact Path:</strong> <code>sections/main-product.liquid</code>.<br><strong>Validation:</strong> Rich Results Test + Schema Validator.<br><strong>Rollback:</strong> Theme History.",')
B.append('                    "woocommerce": "<strong>Exact Path:</strong> <code>single-product.php</code> or Yoast/RankMath.<br><strong>Validation:</strong> Rich Results Test.<br><strong>Rollback:</strong> FTP restore.",')
B.append('                    "bigcommerce": "<strong>Exact Path:</strong> <code>templates/components/products/product-view.html</code>.<br><strong>Validation:</strong> Rich Results Test.<br><strong>Rollback:</strong> Revert theme.",')
B.append('                    "magento": "<strong>Exact Path:</strong> <code>catalog_product_view.xml</code> layout.<br><strong>Validation:</strong> Rich Results Test + cache flush.<br><strong>Rollback:</strong> Remove XML update."')
B.append("                },")
B.append('                "missing_answerability_content": {')
B.append('                    "shopify": "<strong>Admin Path:</strong> <code>Settings &gt; Policies</code>. Expand to &gt;200 words. Create FAQ Page via <code>Online Store &gt; Pages</code>.",')
B.append('                    "woocommerce": "<strong>Admin Path:</strong> <code>Pages &gt; Add New</code>. Create Shipping, Returns, FAQ pages (&gt;200 words). Link in Footer Menu.",')
B.append('                    "bigcommerce": "<strong>Admin Path:</strong> <code>Storefront &gt; Web Pages</code>. Create policy and FAQ pages.",')
B.append('                    "magento": "<strong>Admin Path:</strong> <code>Content &gt; Pages</code>. Create policy and FAQ CMS blocks."')
B.append("                },")
B.append('                "ai_crawlers_blocked": {')
B.append('                    "shopify": "<strong>Exact Path:</strong> Create <code>templates/robots.txt.liquid</code>. Append AI bot allow rules (GPTBot, ClaudeBot, PerplexityBot, Applebot-Extended).",')
B.append('                    "woocommerce": "<strong>Exact Path:</strong> Yoast SEO &gt; Tools &gt; File Editor OR edit root <code>robots.txt</code> via FTP. Append AI bot allow rules.",')
B.append('                    "bigcommerce": "<strong>Exact Path:</strong> Edit root <code>robots.txt</code> via FTP/SSH. Append AI bot allow rules.",')
B.append('                    "magento": "<strong>Exact Path:</strong> Edit <code>pub/robots.txt</code> via SSH/FTP. Append AI bot allow rules."')
B.append("                }")
B.append("            }")
B.append('            for issue in geo_findings.get("issues", []):')
B.append('                code = issue.get("code", "")')
B.append('                sop_text = issue_sops.get(code, {}).get(platform, "<strong>Implementation:</strong> Inject JSON-LD into global &lt;head&gt; template.<br><strong>Validation:</strong> Rich Results Test.<br><strong>Rollback:</strong> Git/CMS history.")')
B.append("                inst_html = f'<div style=\"background:rgba(59, 130, 246, 0.1); padding:10px; border-radius:6px; margin:15px 0 5px 0; font-size:13px; color:#93c5fd; border:1px solid rgba(59,130,246,0.3);\"><strong>Platform Guide ({platform.title()}):</strong> {sop_text}</div>'")
B.append('                if "fix_snippet" in issue:')
B.append("                    safe_snippet = issue[\"fix_snippet\"].replace(\"&\", \"&amp;\").replace(\"<\", \"&lt;\").replace(\">\", \"&gt;\")")
B.append("                    snippet_html = f'{inst_html}<pre style=\"background:#020617;color:#e2e8f0;padding:15px;border-radius:6px;overflow-x:auto;font-size:13px;line-height:1.5;border:1px solid #334155;\"><code>{safe_snippet}</code></pre>'")
B.append("                    issue[\"fix\"] = issue.get(\"fix\", \"\") + snippet_html")

new_block = chr(10).join(B) + chr(10)
t = t[:si] + new_block + t[ei:]

try:
    ast.parse(t)
    p.write_text(t, "utf-8")
    print("[OK] pipeline.py rewritten with Issue-Specific Multi-Platform SOPs. AST valid.")
except SyntaxError as e:
    print(f"[FATAL] Syntax error: {e}")