
import subprocess
import sys
from pathlib import Path


class TestGEOSyntax:
    """Verify GEO-related Python files compile without errors. CRO is NOT tested here."""

    def test_pipeline_syntax(self):
        r = subprocess.run(
            [sys.executable, "-m", "py_compile", "src/revenue_leak_engine/pipeline.py"],
            capture_output=True, text=True
        )
        assert r.returncode == 0, f"pipeline.py syntax error: {r.stderr}"

    def test_geo_audit_syntax(self):
        r = subprocess.run(
            [sys.executable, "-m", "py_compile", "src/revenue_leak_engine/audit/geo_audit.py"],
            capture_output=True, text=True
        )
        assert r.returncode == 0, f"geo_audit.py syntax error: {r.stderr}"

    def test_llm_tracker_syntax(self):
        r = subprocess.run(
            [sys.executable, "-m", "py_compile", "src/revenue_leak_engine/audit/llm_citation_tracker.py"],
            capture_output=True, text=True
        )
        assert r.returncode == 0, f"llm_citation_tracker.py syntax error: {r.stderr}"

    def test_geo_report_generator_syntax(self):
        r = subprocess.run(
            [sys.executable, "-m", "py_compile", "src/revenue_leak_engine/reporting/geo_report_generator.py"],
            capture_output=True, text=True
        )
        assert r.returncode == 0, f"geo_report_generator.py syntax error: {r.stderr}"


class TestGEOImportChain:
    """Verify GEO modules import cleanly without circular dependencies."""

    def test_pipeline_import(self):
        r = subprocess.run(
            [sys.executable, "-c", "import sys; sys.path.insert(0, 'src'); from revenue_leak_engine.pipeline import run"],
            capture_output=True, text=True
        )
        assert r.returncode == 0, f"pipeline import failed: {r.stderr}"

    def test_geo_audit_import(self):
        r = subprocess.run(
            [sys.executable, "-c", "import sys; sys.path.insert(0, 'src'); from revenue_leak_engine.audit.geo_audit import audit_geo"],
            capture_output=True, text=True
        )
        assert r.returncode == 0, f"geo_audit import failed: {r.stderr}"

    def test_llm_tracker_import(self):
        r = subprocess.run(
            [sys.executable, "-c", "import sys; sys.path.insert(0, 'src'); from revenue_leak_engine.audit.llm_citation_tracker import query_llm_citation"],
            capture_output=True, text=True
        )
        assert r.returncode == 0, f"llm_tracker import failed: {r.stderr}"


class TestGEOCodeIntegrity:
    """Verify specific GEO code patterns exist or are absent as required."""

    def read_pipeline(self):
        return Path("src/revenue_leak_engine/pipeline.py").read_text(encoding="utf-8")

    def read_tracker(self):
        return Path("src/revenue_leak_engine/audit/llm_citation_tracker.py").read_text(encoding="utf-8")

    def read_geo(self):
        return Path("src/revenue_leak_engine/audit/geo_audit.py").read_text(encoding="utf-8")

    def test_sov_data_injected(self):
        t = self.read_pipeline()
        assert "query_llm_citation(domain, core_prod_for_llm, sov_data)" in t

    def test_ghost_track_eradicated(self):
        t = self.read_pipeline()
        assert "track_llm_citations" not in t

    def test_phase8_self_contained(self):
        t = self.read_pipeline()
        assert "chart_conn = sqlite3.connect(CACHE_DB)" in t

    def test_homepage_html_present(self):
        t = self.read_geo()
        assert "homepage_html" in t

    def test_clean_domain_present(self):
        t = self.read_tracker()
        assert "clean_domain" in t

    def test_error_signals_present(self):
        t = self.read_tracker()
        assert "error_signals" in t

    def test_no_ghost_agency_dashboard_import(self):
        t = self.read_pipeline()
        assert "from revenue_leak_engine.reporting.agency_dashboard" not in t

    def test_no_ghost_generate_call(self):
        t = self.read_pipeline()
        assert "generate_agency_dashboard()" not in t
        assert "run_competitor_benchmark()" not in t
        assert "generate_hyper_personalized_outreach()" not in t
        assert "dispatch_webhooks()" not in t


class TestGEOFunctionSignatures:
    """Verify GEO core function signatures are intact."""

    def test_audit_geo_signature(self):
        r = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, 'src'); "
             "import inspect; "
             "from revenue_leak_engine.audit.geo_audit import audit_geo; "
             "sig = inspect.signature(audit_geo); "
             "assert 'domain' in sig.parameters"],
            capture_output=True, text=True
        )
        assert r.returncode == 0, f"audit_geo signature broken: {r.stderr}"

    def test_geo_opportunity_score_signature(self):
        r = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, 'src'); "
             "import inspect; "
             "from revenue_leak_engine.audit.geo_audit import geo_opportunity_score; "
             "sig = inspect.signature(geo_opportunity_score); "
             "assert 'geo_findings' in sig.parameters"],
            capture_output=True, text=True
        )
        assert r.returncode == 0, f"geo_opportunity_score signature broken: {r.stderr}"

    def test_query_llm_citation_signature(self):
        r = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, 'src'); "
             "import inspect; "
             "from revenue_leak_engine.audit.llm_citation_tracker import query_llm_citation; "
             "sig = inspect.signature(query_llm_citation); "
             "assert 'domain' in sig.parameters"],
            capture_output=True, text=True
        )
        assert r.returncode == 0, f"query_llm_citation signature broken: {r.stderr}"


class TestGEOConfiguration:
    """Verify configuration is valid."""

    def test_niche_presets_exist(self):
        r = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, 'src'); "
             "from revenue_leak_engine.config import NICHE_PRESETS; "
             "assert len(NICHE_PRESETS) > 0"],
            capture_output=True, text=True
        )
        assert r.returncode == 0, f"NICHE_PRESETS missing: {r.stderr}"

    def test_project_root_exists(self):
        r = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, 'src'); "
             "from revenue_leak_engine.config import PROJECT_ROOT; "
             "assert PROJECT_ROOT.exists()"],
            capture_output=True, text=True
        )
        assert r.returncode == 0, f"PROJECT_ROOT broken: {r.stderr}"


class TestGEOPhaseMarkers:
    """Verify phase markers exist in pipeline.py."""

    def read_pipeline(self):
        return Path("src/revenue_leak_engine/pipeline.py").read_text(encoding="utf-8")

    def test_phase8_present(self):
        t = self.read_pipeline()
        assert "PHASE 8: DASHBOARD DATA INJECTION" in t

    def test_phase2_present(self):
        t = self.read_pipeline()
        assert "PHASE 2: SAVE GEO HISTORY" in t

    def test_phase3_present(self):
        t = self.read_pipeline()
        assert "PHASE 3: " in t

    def test_phase13_present(self):
        t = self.read_pipeline()
        assert "PHASE 13: " in t
