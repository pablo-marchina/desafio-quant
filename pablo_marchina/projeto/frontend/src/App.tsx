import { useState, useEffect, useCallback } from "react";
import type { ProductReadinessRead } from "./api/types";
import { getProductReadiness } from "./api/product";
import { SetupReadinessView } from "./components/SetupReadinessView";
import { CapabilitiesView } from "./components/CapabilitiesView";
import { StartupListView } from "./components/StartupListView";
import { StartupDetailPanel } from "./components/StartupDetailPanel";
import { AnalysisRunDetailView } from "./components/AnalysisRunDetailView";
import { OpportunitiesView } from "./components/OpportunitiesView";
import { DossierView } from "./components/DossierView";
import { DiscoveryView } from "./components/DiscoveryView";
import { WorkflowView } from "./components/WorkflowView";
import { ExportDeliveryView } from "./components/ExportDeliveryView";
import { QualityView } from "./components/QualityView";
import { HumanReviewView } from "./components/HumanReviewView";
import { PipelineFinalResultView } from "./components/PipelineFinalResultView";
import { RadarDashboardView } from "./components/RadarDashboardView";

type ActiveView =
  | "setup"
  | "capabilities"
  | "discovery"
  | "radarDashboard"
  | "startups"
  | "startupDetail"
  | "analysisRun"
  | "dossier"
  | "opportunities"
  | "workflow"
  | "exportDelivery"
  | "quality"
  | "humanReview"
  | "finalResult";

export default function App() {
  const [activeView, setActiveView] = useState<ActiveView>("setup");
  const [ready, setReady] = useState<boolean | null>(null);
  const [selectedStartupId, setSelectedStartupId] = useState<string | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedWorkflowRunId, setSelectedWorkflowRunId] = useState<string | null>(null);

  const checkReadiness = useCallback(async () => {
    try {
      const r = await getProductReadiness();
      setReady(r.ready);
      if (r.ready) {
        setActiveView((current) => (current === "setup" ? "radarDashboard" : current));
      }
    } catch {
      setReady(false);
    }
  }, []);

  useEffect(() => {
    checkReadiness();
  }, [checkReadiness]);

  function navigateTo(view: string) {
    if (view === "setup" || view === "capabilities" || view === "discovery" || view === "radarDashboard" || view === "startups" || view === "opportunities" || view === "workflow" || view === "exportDelivery" || view === "quality" || view === "humanReview" || view === "finalResult") {
      setActiveView(view as ActiveView);
    }
  }

  function handleSelectStartup(id: string) {
    setSelectedStartupId(id);
    setActiveView("startupDetail");
  }

  function handleRunCreated(runId: string) {
    setSelectedRunId(runId);
    setActiveView("analysisRun");
  }

  function handlePipelineCreated(workflowId: string, analysisRunId: string | null) {
    setSelectedWorkflowRunId(workflowId);
    if (analysisRunId) setSelectedRunId(analysisRunId);
    setActiveView("finalResult");
  }

  function handleViewFinalResult(workflowId: string) {
    setSelectedWorkflowRunId(workflowId);
    setActiveView("finalResult");
  }

  function handleViewDossier(runId: string) {
    setSelectedRunId(runId);
    setActiveView("dossier");
  }

  function handleBackFromStartup() {
    setSelectedStartupId(null);
    setActiveView("startups");
  }

  function handleBackFromRun() {
    if (selectedStartupId) {
      setActiveView("startupDetail");
    } else {
      setActiveView("startups");
    }
  }

  function handleBackFromDossier() {
    setActiveView("analysisRun");
  }

  function handleSelectWorkflowRun(workflowId: string) {
    setSelectedWorkflowRunId(workflowId);
  }

  function handlePromoteToStartup(startupId: string) {
    setSelectedStartupId(startupId);
    setActiveView("startupDetail");
  }

  return (
    <div className="app-shell">
      <header className="top-header">
        <div className="top-header-left">
          <h1 className="app-title" onClick={() => navigateTo("setup")}>
            NVIDIA Startup AI Radar
          </h1>
          <span className="app-badge">Product UI</span>
          {ready === true && <span className="status-dot ok" title="Product ready" />}
          {ready === false && <span className="status-dot bad" title="Product not ready" />}
          {ready === null && <span className="status-dot loading" title="Checking..." />}
        </div>
        <nav className="top-nav">
          <button
            type="button"
            className={`nav-btn ${activeView === "setup" || activeView === "quality" ? "active" : ""}`}
            onClick={() => navigateTo("setup")}
          >
            Setup
          </button>
          <button
            type="button"
            className={`nav-btn ${activeView === "capabilities" ? "active" : ""}`}
            onClick={() => navigateTo("capabilities")}
          >
            Capabilities
          </button>
          <button
            type="button"
            className={`nav-btn ${activeView === "discovery" ? "active" : ""}`}
            onClick={() => navigateTo("discovery")}
          >
            Discovery
          </button>
          <button
            type="button"
            className={`nav-btn ${activeView === "radarDashboard" ? "active" : ""}`}
            onClick={() => navigateTo("radarDashboard")}
          >
            Radar Dashboard
          </button>
          <button
            type="button"
            className={`nav-btn ${activeView === "startups" || activeView === "startupDetail" ? "active" : ""}`}
            onClick={() => navigateTo("startups")}
          >
            Startups
          </button>
          <button
            type="button"
            className={`nav-btn ${activeView === "opportunities" ? "active" : ""}`}
            onClick={() => navigateTo("opportunities")}
          >
            Opportunities
          </button>
          <button
            type="button"
            className={`nav-btn ${activeView === "workflow" ? "active" : ""}`}
            onClick={() => navigateTo("workflow")}
          >
            Workflow
          </button>
          <button
            type="button"
            className={`nav-btn ${activeView === "finalResult" ? "active" : ""}`}
            onClick={() => navigateTo("finalResult")}
          >
            Final Result
          </button>
          <button
            type="button"
            className={`nav-btn ${activeView === "exportDelivery" ? "active" : ""}`}
            onClick={() => navigateTo("exportDelivery")}
          >
            Export
          </button>
          <button
            type="button"
            className={`nav-btn ${activeView === "humanReview" ? "active" : ""}`}
            onClick={() => navigateTo("humanReview")}
          >
            Review
          </button>
        </nav>
      </header>

      <main className="main-content">
        {activeView === "setup" && (
          <SetupReadinessView onNavigate={navigateTo} />
        )}

        {activeView === "quality" && <QualityView />}

        {activeView === "capabilities" && <CapabilitiesView />}

        {activeView === "discovery" && (
          <DiscoveryView
            onPromoteToStartup={handlePromoteToStartup}
            onSelectRun={handleRunCreated}
          />
        )}

        {activeView === "radarDashboard" && (
          <RadarDashboardView
            onSelectStartup={handleSelectStartup}
            onSelectRun={handleRunCreated}
          />
        )}

        {activeView === "startups" && (
          <StartupListView onSelectStartup={handleSelectStartup} />
        )}

        {activeView === "startupDetail" && selectedStartupId && (
          <StartupDetailPanel
            startupId={selectedStartupId}
            onBack={handleBackFromStartup}
            onRunCreated={handleRunCreated}
            onPipelineCreated={handlePipelineCreated}
          />
        )}

        {activeView === "analysisRun" && selectedRunId && (
          <AnalysisRunDetailView
            runId={selectedRunId}
            onBack={handleBackFromRun}
            onViewDossier={handleViewDossier}
          />
        )}

        {activeView === "dossier" && selectedRunId && (
          <DossierView
            runId={selectedRunId}
            onBack={handleBackFromDossier}
          />
        )}

        {activeView === "opportunities" && (
          <OpportunitiesView
            onSelectRun={handleRunCreated}
            onSelectStartup={handleSelectStartup}
          />
        )}

        {activeView === "workflow" && (
          <WorkflowView
            onSelectWorkflowRun={handleSelectWorkflowRun}
            selectedWorkflowRunId={selectedWorkflowRunId}
            onSelectStartup={handleSelectStartup}
            onViewFinalResult={handleViewFinalResult}
          />
        )}

        {activeView === "finalResult" && (
          <PipelineFinalResultView
            workflowId={selectedWorkflowRunId}
            onBackToWorkflow={() => setActiveView("workflow")}
            onSelectStartup={handleSelectStartup}
          />
        )}

        {activeView === "exportDelivery" && <ExportDeliveryView />}

        {activeView === "humanReview" && <HumanReviewView />}
      </main>
    </div>
  );
}
