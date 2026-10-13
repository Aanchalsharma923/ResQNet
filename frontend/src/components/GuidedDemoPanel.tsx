import { useState, useEffect, useRef } from 'react';
import type { WSEvent, DemoState, DemoSummary } from '../types';
import {
  fetchDemoStatus, startDemo, nextDemoStage, prevDemoStage,
  stepDemoStage, resetDemo
} from '../services/api';

interface GuidedDemoPanelProps {
  events: WSEvent[];
}

const STAGES = [
  { id: 1, label: '1. Initial Mesh', short: 'Mesh Init' },
  { id: 2, label: '2. Dispatch SOS', short: 'SOS Sent' },
  { id: 3, label: '3. Hospital ACK', short: 'Return ACK' },
  { id: 4, label: '4. Relay Failure', short: 'Relay-B Down' },
  { id: 5, label: '5. Route Recovery', short: 'Alt Route (D)' },
  { id: 6, label: '6. Viva Defense', short: 'Results' },
];

const GuidedDemoPanel = ({ events }: GuidedDemoPanelProps) => {
  const [demoState, setDemoState] = useState<DemoState | null>(null);
  const [isExpanded, setIsExpanded] = useState(true);
  const [isAutoPlaying, setIsAutoPlaying] = useState(false);
  const [autoPlayTimer, setAutoPlayTimer] = useState(7);
  const [isLoading, setIsLoading] = useState(false);

  const autoPlayIntervalRef = useRef<any>(null);

  // Initial fetch of demo status
  useEffect(() => {
    fetchDemoStatus()
      .then(setDemoState)
      .catch(err => console.error('Failed to fetch demo state:', err));
  }, []);

  // Listen for WebSocket DEMO_STAGE_CHANGED events
  useEffect(() => {
    if (events.length > 0) {
      const latest = events[0];
      if (latest.type === 'DEMO_STAGE_CHANGED' && latest.data) {
        setDemoState(latest.data);
      }
    }
  }, [events]);

  // Handle Auto-Play countdown timer
  useEffect(() => {
    if (!isAutoPlaying) {
      if (autoPlayIntervalRef.current) {
        clearInterval(autoPlayIntervalRef.current);
        autoPlayIntervalRef.current = null;
      }
      setAutoPlayTimer(7);
      return;
    }

    autoPlayIntervalRef.current = setInterval(() => {
      setAutoPlayTimer(prev => {
        if (prev <= 1) {
          // Time to advance stage
          handleNextStage();
          return 7;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      if (autoPlayIntervalRef.current) {
        clearInterval(autoPlayIntervalRef.current);
      }
    };
  }, [isAutoPlaying, demoState?.current_stage]);

  const handleStartDemo = async () => {
    setIsLoading(true);
    try {
      const res = await startDemo();
      setDemoState(res);
    } catch (e) {
      console.error('Failed to start demo', e);
    } finally {
      setIsLoading(false);
    }
  };

  const handleNextStage = async () => {
    if (demoState && demoState.current_stage >= 6) {
      setIsAutoPlaying(false);
      return;
    }
    setIsLoading(true);
    try {
      const res = await nextDemoStage();
      setDemoState(res);
      setAutoPlayTimer(7);
    } catch (e) {
      console.error('Failed to advance demo stage', e);
    } finally {
      setIsLoading(false);
    }
  };

  const handlePrevStage = async () => {
    setIsLoading(true);
    try {
      const res = await prevDemoStage();
      setDemoState(res);
      setAutoPlayTimer(7);
    } catch (e) {
      console.error('Failed to step back demo stage', e);
    } finally {
      setIsLoading(false);
    }
  };

  const handleStepStage = async (stageNum: number) => {
    setIsLoading(true);
    try {
      const res = await stepDemoStage(stageNum);
      setDemoState(res);
      setAutoPlayTimer(7);
    } catch (e) {
      console.error('Failed to jump to stage', e);
    } finally {
      setIsLoading(false);
    }
  };

  const handleResetDemo = async () => {
    setIsAutoPlaying(false);
    setIsLoading(true);
    try {
      const res = await resetDemo();
      setDemoState(res);
      setAutoPlayTimer(7);
    } catch (e) {
      console.error('Failed to reset demo', e);
    } finally {
      setIsLoading(false);
    }
  };

  const currentStage = demoState?.current_stage || 1;
  const stageInfo = demoState?.stage_info;
  const summary: DemoSummary | null | undefined = demoState?.summary;

  return (
    <div className="guided-demo-container">
      {/* Demo Control Header Bar */}
      <div className="guided-demo-header">
        <div className="demo-header-title">
          <span className="demo-badge-live">LIVE VIVA DEMO</span>
          <span className="demo-title-text">
            Disaster Scenario Walkthrough & AODV Verification
          </span>
          <span className="demo-stage-indicator">
            Stage {currentStage} of 6
          </span>
        </div>

        <div className="demo-header-actions">
          <button
            type="button"
            className="demo-btn-secondary"
            onClick={() => setIsAutoPlaying(prev => !prev)}
            title={isAutoPlaying ? "Pause Auto-Advancing" : "Auto-Advance Stages for Viva"}
          >
            {isAutoPlaying ? `⏸ Pause (${autoPlayTimer}s)` : '▶ Auto-Play Demo'}
          </button>

          <button
            type="button"
            className="demo-btn-secondary"
            onClick={handleResetDemo}
            disabled={isLoading}
          >
            ↺ Reset
          </button>

          <button
            type="button"
            className="demo-btn-toggle"
            onClick={() => setIsExpanded(prev => !prev)}
          >
            {isExpanded ? '▲ Hide Guidance' : '▼ Show Guidance'}
          </button>
        </div>
      </div>

      {/* 6-Stage Progress Stepper Bar */}
      <div className="demo-stepper-bar">
        {STAGES.map(s => {
          const isActive = s.id === currentStage;
          const isPassed = s.id < currentStage;
          return (
            <button
              key={s.id}
              type="button"
              className={`demo-step-tab ${isActive ? 'active' : ''} ${isPassed ? 'passed' : ''}`}
              onClick={() => handleStepStage(s.id)}
              disabled={isLoading}
            >
              <span className="step-circle">{isPassed ? '✓' : s.id}</span>
              <span className="step-label">{s.label}</span>
            </button>
          );
        })}
      </div>

      {/* Detailed Guidance & Concept Breakdown (Collapsible) */}
      {isExpanded && stageInfo && (
        <div className="demo-detail-card">
          <div className="demo-detail-header">
            <div>
              <div className="demo-concept-badge">{stageInfo.concept}</div>
              <h3 className="demo-stage-title">{stageInfo.name}</h3>
            </div>
            <div className="demo-nav-btns">
              <button
                type="button"
                className="demo-nav-btn"
                onClick={handlePrevStage}
                disabled={currentStage <= 1 || isLoading}
              >
                ◀ Previous
              </button>
              {currentStage < 6 ? (
                <button
                  type="button"
                  className="demo-nav-btn primary"
                  onClick={handleNextStage}
                  disabled={isLoading}
                >
                  Next Stage ▶
                </button>
              ) : (
                <button
                  type="button"
                  className="demo-nav-btn success"
                  onClick={handleStartDemo}
                  disabled={isLoading}
                >
                  Restart Demo ↺
                </button>
              )}
            </div>
          </div>

          <p className="demo-scenario-text">
            <strong>Incident Scenario:</strong> {stageInfo.scenario}
          </p>

          <div className="demo-observations-box">
            <div className="box-title">🔍 Key Observations for Viva Examiner:</div>
            <ul className="observations-list">
              {stageInfo.observations.map((obs, idx) => (
                <li key={idx}>
                  <span className="obs-check">✓</span>
                  <span>{obs}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="demo-examiner-callout">
            <strong>Computer Networks Viva Principle:</strong> {stageInfo.examiner_notes}
          </div>

          {/* Stage 6 Viva Defense Summary Card */}
          {currentStage === 6 && summary && (
            <div className="demo-summary-section">
              <h4 className="summary-title">🎓 Final Demonstration Evaluation & Protocol Metrics</h4>
              <div className="summary-metrics-grid">
                <div className="summary-metric-card">
                  <span className="summary-metric-val green">{summary.pdr}</span>
                  <span className="summary-metric-lbl">Packet Delivery Ratio (PDR)</span>
                </div>
                <div className="summary-metric-card">
                  <span className="summary-metric-val cyan">{summary.sos_delivered} / {summary.sos_dispatched}</span>
                  <span className="summary-metric-lbl">SOS Delivered to Hospital</span>
                </div>
                <div className="summary-metric-card">
                  <span className="summary-metric-val green">{summary.acks_confirmed} / {summary.sos_delivered}</span>
                  <span className="summary-metric-lbl">Bidirectional ACKs Confirmed</span>
                </div>
                <div className="summary-metric-card">
                  <span className="summary-metric-val amber">{summary.recovery_time}</span>
                  <span className="summary-metric-lbl">Route Failover Recovery Time</span>
                </div>
                <div className="summary-metric-card">
                  <span className="summary-metric-val">{summary.active_route_at_conclusion.join(' → ') || 'N/A'}</span>
                  <span className="summary-metric-lbl">Active Route ({summary.hop_count} Hops)</span>
                </div>
                <div className="summary-metric-card">
                  <span className="summary-metric-val purple">{summary.rreq_count} RREQ / {summary.rrep_count} RREP</span>
                  <span className="summary-metric-lbl">Routing Control Overhead</span>
                </div>
              </div>

              <div className="summary-explanation-box">
                <strong>Runtime Execution Grounding:</strong> {summary.mode_explanation}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default GuidedDemoPanel;
