#!/usr/bin/env python3
"""
Automation domain entities for the NZB4 application.
These classes represent core business objects related to automation workflows.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Dict, List, Optional, Any
import uuid


class WorkflowStatus(Enum):
    """Status of an automation workflow"""
    ACTIVE = auto()
    INACTIVE = auto()
    DRAFT = auto()
    ERROR = auto()
    DELETED = auto()


class TriggerType(Enum):
    """Types of workflow triggers"""
    MANUAL = auto()
    SCHEDULED = auto()
    WEBHOOK = auto()
    EVENT = auto()
    FILE_CHANGE = auto()
    API_CALL = auto()


class IntegrationType(Enum):
    """Types of external integrations"""
    N8N = auto()
    DOCKER = auto()
    EMAIL = auto()
    WEBHOOK = auto()
    DATABASE = auto()
    CUSTOM = auto()


@dataclass
class WorkflowTrigger:
    """Trigger configuration for a workflow"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: TriggerType
    name: str
    description: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    schedule: Optional[str] = None  # Cron expression for scheduled triggers
    
    def is_scheduled(self) -> bool:
        """Check if this is a scheduled trigger"""
        return self.type == TriggerType.SCHEDULED
    
    def is_event_based(self) -> bool:
        """Check if this is an event-based trigger"""
        return self.type == TriggerType.EVENT or self.type == TriggerType.WEBHOOK
    
    def is_manual(self) -> bool:
        """Check if this is a manual trigger"""
        return self.type == TriggerType.MANUAL


@dataclass
class WorkflowAction:
    """Action to be executed as part of a workflow"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: Optional[str] = None
    action_type: str  # Type of action (e.g., "http.request", "media.convert")
    parameters: Dict[str, Any] = field(default_factory=dict)
    position: int = 0  # Position in the workflow sequence


@dataclass
class Workflow:
    """Automation workflow definition"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    triggers: List[WorkflowTrigger] = field(default_factory=list)
    actions: List[WorkflowAction] = field(default_factory=list)
    status: WorkflowStatus = WorkflowStatus.DRAFT
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_trigger(self, trigger: WorkflowTrigger) -> None:
        """Add a trigger to this workflow"""
        self.triggers.append(trigger)
        self.updated_at = datetime.now()
    
    def add_action(self, action: WorkflowAction) -> None:
        """Add an action to this workflow"""
        action.position = len(self.actions)
        self.actions.append(action)
        self.updated_at = datetime.now()
    
    def activate(self) -> None:
        """Activate this workflow"""
        self.status = WorkflowStatus.ACTIVE
        self.updated_at = datetime.now()
    
    def deactivate(self) -> None:
        """Deactivate this workflow"""
        self.status = WorkflowStatus.INACTIVE
        self.updated_at = datetime.now()
    
    def is_active(self) -> bool:
        """Check if the workflow is active"""
        return self.status == WorkflowStatus.ACTIVE


@dataclass
class WorkflowExecution:
    """Record of a workflow execution"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workflow_id: str
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    trigger_id: Optional[str] = None
    status: str = "RUNNING"  # RUNNING, COMPLETED, FAILED
    result: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    
    def complete(self, result: Dict[str, Any]) -> None:
        """Mark execution as completed with result"""
        self.completed_at = datetime.now()
        self.status = "COMPLETED"
        self.result = result
    
    def fail(self, error: str) -> None:
        """Mark execution as failed with error"""
        self.completed_at = datetime.now()
        self.status = "FAILED"
        self.error = error


@dataclass
class Integration:
    """External integration configuration"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    type: IntegrationType
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    config: Dict[str, Any] = field(default_factory=dict)
    is_enabled: bool = True
    
    @classmethod
    def create_n8n_integration(cls, name: str, host: str, port: int) -> 'Integration':
        """Create an n8n integration"""
        return cls(
            name=name,
            type=IntegrationType.N8N,
            config={
                "host": host,
                "port": port,
                "url": f"http://{host}:{port}",
                "webhook_base_url": f"http://{host}:{port}/webhook/"
            }
        )
    
    def disable(self) -> None:
        """Disable this integration"""
        self.is_enabled = False
        self.updated_at = datetime.now()
    
    def enable(self) -> None:
        """Enable this integration"""
        self.is_enabled = True
        self.updated_at = datetime.now()
    
    def update_config(self, config: Dict[str, Any]) -> None:
        """Update integration configuration"""
        self.config.update(config)
        self.updated_at = datetime.now() 