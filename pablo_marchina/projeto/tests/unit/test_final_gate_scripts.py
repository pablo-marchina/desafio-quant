from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

from scripts import check_benchmark_type_policy, check_final_release_zip, package_final_release, prove_final_product
from src.governance.artifacts import build_initial_evidence_pack

ROOT = Path(__file__).resolve().parents[2]


def test_candidate_catalog_gate_passes_for_generated_pack(tmp_path: Path) -> None:
    roadmap = tmp_path / "roadmap.md"
    roadmap.write_text(
        "## 8. Candidate Catalog\n\n"
        "```\n"
        "AI code review\n"
        "```\n",
        encoding="utf-8",
    )
    build_initial_evidence_pack(evidence_dir=tmp_path, roadmap_path=roadmap)
    result = subprocess.run(
        [sys.executable, "scripts/check_candidate_catalog.py", "--catalog", str(tmp_path / "candidate_catalog.csv")],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "PASS" in result.stdout


def test_lineage_gate_requires_artifacts(tmp_path: Path) -> None:
    build_initial_evidence_pack(evidence_dir=tmp_path)
    result = subprocess.run(
        [sys.executable, "scripts/check_lineage_coverage.py", "--evidence-dir", str(tmp_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_security_release_gate_requires_artifacts(tmp_path: Path) -> None:
    build_initial_evidence_pack(evidence_dir=tmp_path)
    result = subprocess.run(
        [sys.executable, "scripts/check_security_release.py", "--evidence-dir", str(tmp_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "blocking status" in result.stdout


def test_prove_final_product_quick_writes_summary(tmp_path: Path) -> None:
    summary = {
        "generated_at": "2026-06-23T00:00:00+00:00",
        "mode": "quick",
        "final_status": "FAIL",
        "total_gates": 1,
        "passed": 0,
        "failed": 1,
        "warnings": 0,
        "blocked_by_environment": 0,
        "results": [
            {
                "label": "python scripts/check_security_release.py",
                "returncode": 1,
                "required": True,
                "status": "FAIL",
                "stdout_tail": "",
                "stderr_tail": "",
            }
        ],
    }
    prove_final_product._write_readiness_reports(tmp_path, summary)

    assert (tmp_path / "final_proof_summary.json").is_file()
    assert (tmp_path / "product_readiness_report.md").is_file()


def test_full_real_service_status_is_projected_to_readiness_summary(tmp_path: Path) -> None:
    (tmp_path / "real_service_proof_report.json").write_text(
        '{"status":"BLOCKED_BY_ENVIRONMENT"}',
        encoding="utf-8",
    )
    result = {
        "label": "python scripts/real_service_proof.py --product-like-acceptance",
        "returncode": 0,
        "required": False,
        "status": "PASS",
        "stdout_tail": "",
        "stderr_tail": "",
    }

    enriched = prove_final_product._enrich_real_service_status(result, tmp_path)
    summary = {
        "generated_at": "2026-06-22T00:00:00+00:00",
        "mode": "full",
        "final_status": "BLOCKED_BY_ENVIRONMENT",
        "total_gates": 1,
        "passed": 0,
        "failed": 0,
        "warnings": 0,
        "blocked_by_environment": 1,
        "results": [enriched],
    }
    prove_final_product._write_readiness_reports(tmp_path, summary)

    assert enriched["status"] == "BLOCKED_BY_ENVIRONMENT"
    assert (tmp_path / "final_proof_summary.json").is_file()
    assert (tmp_path / "product_readiness_report.json").is_file()


def test_package_final_release_uses_allowlist_and_writes_reports(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    evidence_dir = repo / "final_case_evidence"
    (repo / "src").mkdir(parents=True)
    (repo / "node_modules").mkdir(parents=True)
    evidence_dir.mkdir(parents=True)
    (repo / "README.md").write_text("readme\n", encoding="utf-8")
    (repo / ".env").write_text("SECRET=value\n", encoding="utf-8")
    (repo / ".env.production.example").write_text("APP_MODE=product\n", encoding="utf-8")
    (repo / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (repo / "node_modules" / "package.txt").write_text("bad\n", encoding="utf-8")

    output = repo / "release" / "academy-nvidia-final-product.zip"
    package_final_release.build_final_release(repo, output, evidence_dir)

    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
    assert "README.md" in names
    assert "src/app.py" in names
    assert ".env.production.example" in names
    assert ".env" not in names
    assert "node_modules/package.txt" not in names
    assert (evidence_dir / "final_release_manifest.json").is_file()
    assert (evidence_dir / "no_env_in_release_report.json").is_file()


def test_check_final_release_zip_fails_for_forbidden_entry(tmp_path: Path) -> None:
    zip_path = tmp_path / "bad.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr(".env", "SECRET=value\n")

    report = check_final_release_zip.check_final_release_zip(zip_path)

    assert report["status"] == "FAIL"
    assert report["violations"][0]["reason"] == "forbidden_artifact"


def test_benchmark_type_policy_blocks_proxy_promotion(tmp_path: Path) -> None:
    (tmp_path / "candidate_catalog.csv").write_text(
        "candidate_id,name,category,benchmark_type\n" "proxy,Proxy Tool,Release,PROXY\n",
        encoding="utf-8",
    )
    (tmp_path / "output_value_benchmark_report.json").write_text(
        '{"decisions":[{"candidate_id":"proxy","benchmark_type":"PROXY","promotion_allowed":true}]}',
        encoding="utf-8",
    )

    failures = check_benchmark_type_policy.validate_benchmark_type_policy(tmp_path)

    assert failures
    assert "proxy" in failures[0]
