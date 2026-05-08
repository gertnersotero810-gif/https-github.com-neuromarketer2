from typing import TypedDict, Optional, List, Dict, Any

class AnomalyCandidate(TypedDict):
    metric: str          # 'ctr' | 'spend' | 'conversions' | 'impressions'
    campaign_id: str
    date: str
    value: float
    z_score: float       # отклонение в σ
    direction: str       # 'spike' | 'drop'

class AnomalyState(TypedDict):
    project_id: str
    tenant_id: str
    analysis_date: str
    metrics_snapshot: List[Dict[str, Any]]
    candidates: List[AnomalyCandidate]
    verified_anomalies: List[AnomalyCandidate]
    pending_approval: bool
    approval_payload: Optional[Dict[str, Any]]
    error: Optional[str]
