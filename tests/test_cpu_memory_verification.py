"""Tests for CPU spike and memory spike verification logic."""

from __future__ import annotations

from orchestrator.verification import VerificationEngine


def test_memory_spike_should_not_escalate_with_agent_confidence() -> None:
    """Memory spike incidents with agent-provided high confidence should not escalate."""
    engine = VerificationEngine()
    
    incident = {
        "type": "memory_spike",
        "service_affected": "cartservice",
        "error_message": "Pod cartservice is using 768.0 MB memory (threshold: 512.0 MB)",
    }
    
    # Improved confidence from InvestigationAgent (0.87) for metric-based memory detection
    hypothesis = {
        "root_cause": "Memory leak or oversized working set",
        "confidence": 0.87,
        "evidence": ["Logs indicate memory growth", "Metrics show sustained high usage"],
        "supporting_agents": ["InvestigationAgent"],
    }
    
    result = engine.verify(incident, hypothesis, [])
    
    # Should be auto-approved with agent-provided confidence
    assert result['can_auto_remediate'], "Memory spike should be auto-remediatable with 0.87 agent confidence"
    assert not result["escalate_to_human"], "Memory spike with 0.87 confidence should not escalate"


def test_cpu_spike_should_not_escalate_with_agent_confidence() -> None:
    """CPU spike incidents with agent-provided high confidence should not escalate."""
    engine = VerificationEngine()
    
    incident = {
        "type": "cpu_spike",
        "service_affected": "checkoutservice",
        "error_message": "Pod checkoutservice is using 91.5% CPU (threshold: 85.0%)",
    }
    
    # Improved confidence from InvestigationAgent (0.85) for metric-based CPU detection
    hypothesis = {
        "root_cause": "Traffic surge or inefficient request path",
        "confidence": 0.85,
        "evidence": ["Elevated CPU utilization", "Recent traffic pattern change"],
        "supporting_agents": ["InvestigationAgent"],
    }
    
    result = engine.verify(incident, hypothesis, [])
    
    # Should be auto-approved with agent-provided confidence
    assert result['can_auto_remediate'], "CPU spike should be auto-remediatable with 0.85 agent confidence"
    assert not result["escalate_to_human"], "CPU spike with 0.85 confidence should not escalate"


def test_deployment_unavailable_still_gets_confidence_boost() -> None:
    """Ensure deployment unavailable incidents still receive confidence boost."""
    engine = VerificationEngine()
    
    incident = {
        "type": "deployment_unavailable",
        "service_affected": "paymentservice",
    }
    
    hypothesis = {
        "root_cause": "Deployment rollout health issue",
        "confidence": 0.85,
        "evidence": ["Replicas unavailable", "Pod events indicate failed startup"],
    }
    
    result = engine.verify(incident, hypothesis, [])
    
    # Deployment unavailable should get boosted to near-auto threshold
    assert result["confidence"] >= 0.90, f"Deployment unavailable should receive confidence boost, got {result['confidence']}"
