"""Test to verify CPU and memory spike incidents are NOT escalated during orchestration."""

from __future__ import annotations

import asyncio
from orchestrator.verification import VerificationEngine
from orchestrator.graph import ProtocolState


def test_orchestrator_verification_for_cpu_spike() -> None:
    """Verify that CPU spike incidents with improved agent confidence are auto-remediatable."""
    engine = VerificationEngine()
    
    incident = {
        "incident_id": "INC-TEST001",
        "type": "cpu_spike",
        "severity": "high",
        "service_affected": "checkoutservice",
        "pod": "checkoutservice-75b9cd684f-7b4bm",
        "detected_at": "2024-01-01T12:00:00Z",
        "alert_name": "HighCPUUsage",
        "error_message": "Pod checkoutservice is using 91.5% CPU (threshold: 85.0%)",
        "metrics_snapshot": {"cpu_usage_pct": {"checkoutservice-75b9cd684f-7b4bm": 91.5}},
    }
    
    # Improved hypothesis from InvestigationAgent with higher confidence for metric-based detection
    hypothesis = {
        "root_cause": "Traffic surge or inefficient request path",
        "confidence": 0.85,  # InvestigationAgent now gives 0.85 for CPU spikes (metric-based)
        "evidence": [
            "CPU saturation is directly measured via Prometheus metrics with high fidelity",
            "Pod using 91.5% of available CPU (metric shows clear threshold breach)",
            "Metrics indicate sustained high usage pattern",
        ],
        "supporting_agents": ["InvestigationAgent", "DevOpsAgent"],
        "recommended_action": "Scale the deployment and inspect hot code paths or recent request pattern changes.",
    }
    
    result = engine.verify(incident, hypothesis, [])
    
    print(f"\nCPU Spike Verification Result:")
    print(f"  Agent Confidence: 0.85 (metric-based, high fidelity)")
    print(f"  Final Confidence: {result['confidence']}")
    print(f"  Can Auto-Remediate: {result['can_auto_remediate']}")
    print(f"  Should Suggest: {result['should_suggest_action']}")
    print(f"  Escalate to Human: {result['escalate_to_human']}")
    print(f"  Status: {result['status']}")
    
    # CPU spike should be auto-remediatable with improved agent confidence
    assert result['confidence'] >= 0.85, f"CPU spike should have confidence >= 0.85 from agents, got {result['confidence']}"
    assert result['can_auto_remediate'], "CPU spike should be auto-remediatable"
    assert not result["escalate_to_human"], "CPU spike should not escalate to human"


def test_orchestrator_verification_for_memory_spike() -> None:
    """Verify that memory spike incidents with improved agent confidence are auto-remediatable."""
    engine = VerificationEngine()
    
    incident = {
        "incident_id": "INC-TEST002",
        "type": "memory_spike",
        "severity": "high",
        "service_affected": "frontend",
        "pod": "frontend-694b9f76cd-l9cnb",
        "detected_at": "2024-01-01T12:00:00Z",
        "alert_name": "HighMemoryUsage",
        "error_message": "Pod frontend is using 768.0 MB memory (threshold: 500.0 MB)",
        "metrics_snapshot": {"memory_usage_mb": {"frontend-694b9f76cd-l9cnb": 768.0}},
    }
    
    # Improved hypothesis from InvestigationAgent with higher confidence for metric-based detection
    hypothesis = {
        "root_cause": "Memory leak or oversized working set",
        "confidence": 0.87,  # InvestigationAgent now gives 0.87 for memory spikes (metric-based)
        "evidence": [
            "Memory spike is directly measured via Prometheus metrics, indicating working set exceeded threshold",
            "Container memory working set: 768 MB > threshold: 500 MB",
            "Metrics indicate potential memory growth pattern",
        ],
        "supporting_agents": ["InvestigationAgent", "DevOpsAgent"],
        "recommended_action": "Restart the workload in the short term and inspect allocation-heavy code paths.",
    }
    
    result = engine.verify(incident, hypothesis, [])
    
    print(f"\nMemory Spike Verification Result:")
    print(f"  Agent Confidence: 0.87 (metric-based, high fidelity)")
    print(f"  Final Confidence: {result['confidence']}")
    print(f"  Can Auto-Remediate: {result['can_auto_remediate']}")
    print(f"  Should Suggest: {result['should_suggest_action']}")
    print(f"  Escalate to Human: {result['escalate_to_human']}")
    print(f"  Status: {result['status']}")
    
    # Memory spike should be auto-remediatable with improved agent confidence
    assert result['confidence'] >= 0.87, f"Memory spike should have confidence >= 0.87 from agents, got {result['confidence']}"
    assert result['can_auto_remediate'], "Memory spike should be auto-remediatable"
    assert not result["escalate_to_human"], "Memory spike should not escalate to human"
