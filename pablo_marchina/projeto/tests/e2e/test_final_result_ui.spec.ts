import { expect, test, type Route } from "@playwright/test";

const API = "http://localhost:8000";
const workflowId = "wf-release-contract-001";
const analysisRunId = "analysis-release-contract-001";
const startupId = "startup-release-contract-001";
const now = "2026-08-02T20:00:00Z";

const nodes = [
  "plan_search",
  "collect_sources",
  "extract_profile",
  "validate_evidence",
  "score_startup_probabilistic",
  "diagnose_gaps",
  "retrieve_nvidia_context",
  "enhance_contexts_with_techniques",
  "map_nvidia_technologies",
  "rank_recommendations",
  "rank_with_expected_utility",
  "generate_brief",
  "run_quality_gates",
  "write_decision_ledger",
].map((node_name, index) => ({
  id: `node-${index}`,
  workflow_run_id: workflowId,
  node_name,
  status: "completed",
  retry_count: 0,
  input_snapshot: {},
  output_snapshot: {},
  error_message: null,
  started_at: now,
  completed_at: now,
  created_at: now,
  updated_at: now,
}));

const recommendation = {
  recommendation_id: "rec-nim-001",
  nvidia_technology: "NVIDIA NIM",
  technology: "NVIDIA NIM",
  gap_id: "gap-inference-001",
  gap_type: "inference_performance_gap",
  recommendation_priority_score: 0.91,
  expected_utility: 0.88,
  expected_utility_rank: 1,
  confidence: 0.86,
  uncertainty: 0.1,
  implementation_complexity: 0.28,
  business_impact: 0.93,
  next_best_action: "Run an NVIDIA NIM latency benchmark",
  recommendation_action: "Run an NVIDIA NIM latency benchmark",
  production_allowed: true,
  supporting_evidence_ids: ["evidence-001"],
  supporting_rag_context_ids: ["context-001"],
};

const workflow = {
  id: workflowId,
  startup_id: startupId,
  discovery_candidate_id: null,
  analysis_run_id: analysisRunId,
  status: "completed",
  current_node: "finish",
  graph_version: "1.0",
  error_message: null,
  degraded_reason: null,
  state: {
    startup_profile: {
      name: "Release Contract AI",
      startup_name: "Release Contract AI",
      website: "https://release-contract.example.com",
      sector: "AI Infrastructure",
      product_summary: "Low-latency AI inference platform",
      technical_keywords: ["inference", "LLM", "GPU"],
    },
    scores: {
      probabilistic_score: 0.84,
      confidence: 0.86,
      uncertainty: 0.1,
      inception_fit: 0.89,
    },
    ranked_recommendations: [recommendation],
    nvidia_contexts: [
      {
        context_id: "context-001",
        product: "NVIDIA NIM",
        source_id: "nvidia-nim-docs",
        source_url: "https://docs.nvidia.com/nim/",
        relevance_score: 0.94,
        gap_types: ["inference_performance_gap"],
        content: "NVIDIA NIM provides optimized inference microservices for production deployment.",
      },
    ],
    node_outputs: {
      gap_output: {
        gaps: [
          {
            gap_id: "gap-inference-001",
            gap_type: "inference_performance_gap",
            severity_score: 0.87,
            confidence_score: 0.82,
            production_allowed: true,
            supporting_evidence_ids: ["evidence-001"],
          },
        ],
      },
      rag_output: {
        status: "passed",
        contexts_retrieved: 1,
        reranker_called: true,
      },
      nvidia_recommendation_result: {
        ranking_status: "passed",
        nvidia_recommendations: [recommendation],
      },
      rank_recommendations: {
        ranked_recommendations: [recommendation],
      },
    },
    completed_nodes: nodes.map((node) => node.node_name),
    degraded_nodes: [],
    failed_nodes: [],
  },
  nodes,
  started_at: now,
  completed_at: now,
  created_at: now,
  updated_at: now,
};

const corsHeaders = {
  "access-control-allow-origin": "http://127.0.0.1:5173",
  "access-control-allow-methods": "GET,POST,PATCH,OPTIONS",
  "access-control-allow-headers": "content-type",
};

async function mockJson(route: Route, body: unknown, status = 200): Promise<void> {
  await route.fulfill({
    status,
    contentType: "application/json",
    headers: corsHeaders,
    body: JSON.stringify(body),
  });
}

test("final cockpit presents the complete persisted pipeline result", async ({ page }) => {
  await page.route(`${API}/**`, async (route) => {
    if (route.request().method() === "OPTIONS") {
      await route.fulfill({ status: 204, headers: corsHeaders });
      return;
    }

    const url = new URL(route.request().url());
    const path = url.pathname;

    if (path === "/product/readiness") {
      return mockJson(route, {
        ready: true,
        blocking_missing_config: [],
        optional_missing_config: [],
        unavailable_capabilities: [],
        degraded_capabilities: [],
        health_checks: [],
        setup_checklist: [],
        user_messages: [],
      });
    }
    if (path === "/workflows/product-runs" && route.request().method() === "GET") {
      return mockJson(route, { items: [workflow], total: 1, offset: 0, limit: 50 });
    }
    if (path === `/workflows/product-runs/${workflowId}`) {
      return mockJson(route, workflow);
    }
    if (path === `/analysis-runs/${analysisRunId}`) {
      return mockJson(route, {
        id: analysisRunId,
        startup_id: startupId,
        status: "completed",
        error_message: null,
        degraded_reason: null,
        started_at: now,
        completed_at: now,
        pipeline_version: "orchestration_graph+v1",
        corpus_version: "nvidia-corpus-release",
        input_snapshot: {},
        output_snapshot: workflow.state,
        scores: [
          { id: "score-001", score_type: "probabilistic", value: 0.84, confidence: "high", components: {}, missing_evidence: [] },
        ],
        gaps: workflow.state.node_outputs.gap_output.gaps,
        nvidia_mappings: [recommendation],
        readiness_checks: [],
        action_brief_id: "brief-001",
        claim_summary: { total_claims: 1, supported_claims: 1, unsupported_claims: 0, evidence_coverage: 1 },
        dossier_summary: { dossier_available: true, dossier_id: "dossier-001" },
        created_at: now,
        updated_at: now,
      });
    }
    if (path === `/analysis-runs/${analysisRunId}/evidence-bundle`) {
      const claim = {
        id: "claim-001",
        startup_id: startupId,
        analysis_run_id: analysisRunId,
        claim_text: "The startup operates a production AI inference platform.",
        claim_type: "production_readiness_claim",
        support_level: "supported",
        confidence: "high",
        evidence_refs: [{ evidence_id: "evidence-001" }],
        used_in_score: true,
        used_in_gap: true,
        used_in_mapping: true,
        used_in_brief: true,
        review_status: "approved",
        reviewer_notes: "",
        metadata: {},
        created_at: now,
        updated_at: now,
      };
      return mockJson(route, {
        analysis_run_id: analysisRunId,
        startup_id: startupId,
        readiness: "ready",
        confidence: "high",
        claims: { supported: [claim], weak: [], unsupported: [], critical: [claim] },
        evidence_coverage: {
          total_claims: 1,
          supported_claims: 1,
          weak_claims: 0,
          unsupported_claims: 0,
          evidence_coverage: 1,
          unsupported_claim_rate: 0,
        },
        missing_evidence: [],
        contradictions: [],
        degraded_checks: [],
      });
    }
    if (path === `/analysis-runs/${analysisRunId}/brief`) {
      return mockJson(route, {
        id: "brief-001",
        analysis_run_id: analysisRunId,
        version: 1,
        schema_version: "runtime_quantitative_brief_v1",
        brief_json: { top_recommendations: [recommendation] },
        brief_markdown: "# Executive recommendation\nAdopt NVIDIA NIM and validate latency with a production benchmark.",
        is_latest: true,
        created_at: now,
        updated_at: now,
      });
    }
    if (path === `/analysis-runs/${analysisRunId}/quality-summary`) {
      return mockJson(route, {
        analysis_run_id: analysisRunId,
        overall_status: "passed",
        total_metrics: 6,
        passed_metrics: 6,
        failed_metrics: 0,
        warning_metrics: 0,
        evidence_coverage: 1,
        unsupported_claim_rate: 0,
        actionability_score: 0.92,
        export_readiness_score: 1,
        degraded_reason: null,
        metrics: [],
      });
    }
    if (path === `/analysis-runs/${analysisRunId}/dossier`) {
      return mockJson(route, {
        id: "dossier-001",
        analysis_run_id: analysisRunId,
        version: 1,
        schema_version: "activation_dossier_v1",
        dossier_json: { recommended_motion: "technical_validation" },
        dossier_markdown: "# Activation Dossier\nRun the NVIDIA NIM benchmark and measure p95 latency.",
        is_latest: true,
        evidence_coverage: 1,
        unsupported_claim_count: 0,
        top_activation_playbook_id: "playbook-001",
        recommended_motion: "technical_validation",
        review_status: "approved",
        created_at: now,
        updated_at: now,
      });
    }
    if (path === `/analysis-runs/${analysisRunId}/dossier/markdown`) {
      return mockJson(route, {
        markdown: "# Activation Dossier\nRun the NVIDIA NIM benchmark and measure p95 latency.",
        dossier_id: "dossier-001",
        version: 1,
      });
    }
    if (path === `/analysis-runs/${analysisRunId}/opportunity-score`) {
      return mockJson(route, {
        id: "opportunity-001",
        analysis_run_id: analysisRunId,
        score_version: "1.0",
        opportunity_score: 0.88,
        score_tier: "high",
        components: {},
        penalties: [],
        penalty_total: 0,
        evidence_refs: ["evidence-001"],
        recommended_action: "Run an NVIDIA NIM latency benchmark",
        reasoning: "High expected utility with strong evidence and RAG support.",
        created_at: now,
        updated_at: now,
      });
    }

    return mockJson(route, { detail: `Unhandled mocked endpoint: ${path}` }, 404);
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Workflow" }).click();
  await expect(page.getByRole("heading", { name: "Workflow Runs" })).toBeVisible();
  await page.locator("tbody tr").first().getByRole("button", { name: "Final Result" }).click();

  await expect(page.getByRole("heading", { name: "Final Pipeline Result" })).toBeVisible();
  await expect(page.getByText("Release Contract AI").first()).toBeVisible();
  await expect(page.getByText("NVIDIA NIM").first()).toBeVisible();
  await expect(page.getByText("The startup operates a production AI inference platform.").first()).toBeVisible();
  await expect(page.getByText(/optimized inference microservices/)).toBeVisible();
  await expect(page.getByText("passed", { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/Adopt NVIDIA NIM and validate latency/)).toBeVisible();
  await expect(page.getByText(/measure p95 latency/)).toBeVisible();
  await expect(page.getByText("No ranked recommendations have been persisted yet.")).toHaveCount(0);
});
