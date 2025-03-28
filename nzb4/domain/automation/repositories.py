#!/usr/bin/env python3
"""
Repository interfaces for the Automation domain.
These define abstract classes for data access operations.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Union
from uuid import UUID

from .entities import (
    Workflow, WorkflowExecution, Integration, 
    WorkflowStatus, IntegrationType
)


class WorkflowRepository(ABC):
    """Repository interface for Workflow entities"""
    
    @abstractmethod
    def save(self, workflow: Workflow) -> Workflow:
        """Save a workflow entity to the repository"""
        pass
    
    @abstractmethod
    def get_by_id(self, workflow_id: Union[str, UUID]) -> Optional[Workflow]:
        """Get a workflow entity by ID"""
        pass
    
    @abstractmethod
    def get_all(self, limit: int = 100, offset: int = 0) -> List[Workflow]:
        """Get all workflow entities with pagination"""
        pass
    
    @abstractmethod
    def get_by_status(self, status: WorkflowStatus, limit: int = 100, offset: int = 0) -> List[Workflow]:
        """Get workflow entities by status"""
        pass
    
    @abstractmethod
    def delete(self, workflow_id: Union[str, UUID]) -> bool:
        """Delete a workflow entity"""
        pass
    
    @abstractmethod
    def update_status(self, workflow_id: Union[str, UUID], status: WorkflowStatus) -> bool:
        """Update workflow status"""
        pass
    
    @abstractmethod
    def search(self, query: str, limit: int = 100, offset: int = 0) -> List[Workflow]:
        """Search for workflow entities"""
        pass


class WorkflowExecutionRepository(ABC):
    """Repository interface for WorkflowExecution entities"""
    
    @abstractmethod
    def save(self, execution: WorkflowExecution) -> WorkflowExecution:
        """Save a workflow execution to the repository"""
        pass
    
    @abstractmethod
    def get_by_id(self, execution_id: Union[str, UUID]) -> Optional[WorkflowExecution]:
        """Get a workflow execution by ID"""
        pass
    
    @abstractmethod
    def get_by_workflow_id(self, workflow_id: Union[str, UUID], limit: int = 100, offset: int = 0) -> List[WorkflowExecution]:
        """Get all executions for a workflow"""
        pass
    
    @abstractmethod
    def get_recent_executions(self, limit: int = 100) -> List[WorkflowExecution]:
        """Get recent workflow executions"""
        pass
    
    @abstractmethod
    def delete(self, execution_id: Union[str, UUID]) -> bool:
        """Delete a workflow execution"""
        pass
    
    @abstractmethod
    def update_status(self, execution_id: Union[str, UUID], status: str, 
                     result: Optional[Dict[str, Any]] = None,
                     error: Optional[str] = None) -> bool:
        """Update execution status"""
        pass
    
    @abstractmethod
    def cleanup_old_executions(self, days_to_keep: int = 30) -> int:
        """Clean up old workflow executions"""
        pass


class IntegrationRepository(ABC):
    """Repository interface for Integration entities"""
    
    @abstractmethod
    def save(self, integration: Integration) -> Integration:
        """Save an integration entity to the repository"""
        pass
    
    @abstractmethod
    def get_by_id(self, integration_id: Union[str, UUID]) -> Optional[Integration]:
        """Get an integration entity by ID"""
        pass
    
    @abstractmethod
    def get_all(self, limit: int = 100, offset: int = 0) -> List[Integration]:
        """Get all integration entities with pagination"""
        pass
    
    @abstractmethod
    def get_by_type(self, integration_type: IntegrationType, limit: int = 100, offset: int = 0) -> List[Integration]:
        """Get integration entities by type"""
        pass
    
    @abstractmethod
    def delete(self, integration_id: Union[str, UUID]) -> bool:
        """Delete an integration entity"""
        pass
    
    @abstractmethod
    def update_config(self, integration_id: Union[str, UUID], config: Dict[str, Any]) -> bool:
        """Update integration configuration"""
        pass
    
    @abstractmethod
    def update_status(self, integration_id: Union[str, UUID], is_enabled: bool) -> bool:
        """Update integration status"""
        pass 