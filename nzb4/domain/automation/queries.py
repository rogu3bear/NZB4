#!/usr/bin/env python3
"""
Query models for the Automation domain
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime

from nzb4.domain.automation.entities import WorkflowStatus, TriggerType, IntegrationType


@dataclass
class WorkflowByIdQuery:
    """Query to find a workflow by its ID"""
    id: str


@dataclass
class WorkflowByNameQuery:
    """Query to find a workflow by its name"""
    name: str


@dataclass
class WorkflowsByStatusQuery:
    """Query to find workflows by their status"""
    status: WorkflowStatus


@dataclass
class WorkflowsByTriggerTypeQuery:
    """Query to find workflows by their trigger type"""
    trigger_type: TriggerType


@dataclass
class AllWorkflowsQuery:
    """Query to fetch all workflows, optionally paginated"""
    page: int = 1
    page_size: int = 20
    sort_by: str = "created_at"
    sort_order: str = "desc"


@dataclass
class WorkflowSearchQuery:
    """Query to search for workflows by keyword across multiple fields"""
    keyword: str
    fields: Optional[List[str]] = None
    page: int = 1
    page_size: int = 20


@dataclass
class WorkflowExecutionByIdQuery:
    """Query to find a workflow execution by its ID"""
    id: str


@dataclass
class WorkflowExecutionsByWorkflowIdQuery:
    """Query to find executions for a specific workflow"""
    workflow_id: str
    status: Optional[str] = None
    page: int = 1
    page_size: int = 20
    sort_by: str = "started_at"
    sort_order: str = "desc"


@dataclass
class RecentWorkflowExecutionsQuery:
    """Query to find recent workflow executions"""
    since: Optional[datetime] = None
    status: Optional[str] = None
    page: int = 1
    page_size: int = 20


@dataclass
class IntegrationByIdQuery:
    """Query to find an integration by its ID"""
    id: str


@dataclass
class IntegrationByTypeQuery:
    """Query to find integrations by their type"""
    integration_type: IntegrationType


@dataclass
class AllIntegrationsQuery:
    """Query to fetch all integrations"""
    active_only: bool = False


@dataclass
class WebhookUrlQuery:
    """Query to get the webhook URL for a workflow"""
    workflow_id: str


@dataclass
class ScheduledWorkflowsQuery:
    """Query to get all scheduled workflows"""
    active_only: bool = True


@dataclass
class TriggerWorkflowQuery:
    """Query with parameters to trigger a workflow execution"""
    workflow_id: str
    payload: Dict[str, Any] 