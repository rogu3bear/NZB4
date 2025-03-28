#!/usr/bin/env python3
"""
Domain services for automation handling.
These services implement business logic for workflow automation.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Union
from uuid import UUID

from .entities import (
    Workflow, WorkflowExecution, Integration,
    WorkflowAction, WorkflowTrigger, WorkflowStatus,
    TriggerType, IntegrationType
)
from .repositories import WorkflowRepository, IntegrationRepository


class WorkflowExecutorService(ABC):
    """Service for executing workflows"""
    
    @abstractmethod
    def execute_workflow(self, workflow_id: Union[str, UUID], 
                        trigger_data: Optional[Dict[str, Any]] = None) -> WorkflowExecution:
        """
        Execute a workflow
        
        Args:
            workflow_id: ID of the workflow to execute
            trigger_data: Data that triggered the workflow
            
        Returns:
            WorkflowExecution: The execution record
        """
        pass
    
    @abstractmethod
    def get_execution_status(self, execution_id: Union[str, UUID]) -> Dict[str, Any]:
        """
        Get status of a workflow execution
        
        Args:
            execution_id: ID of the workflow execution
            
        Returns:
            Dict: Status information
        """
        pass
    
    @abstractmethod
    def cancel_execution(self, execution_id: Union[str, UUID]) -> bool:
        """
        Cancel a workflow execution
        
        Args:
            execution_id: ID of the workflow execution
            
        Returns:
            bool: True if cancelled successfully, False otherwise
        """
        pass


class IntegrationService(ABC):
    """Service for managing external integrations"""
    
    @abstractmethod
    def register_integration(self, name: str, integration_type: IntegrationType, 
                           config: Dict[str, Any]) -> Integration:
        """
        Register a new integration
        
        Args:
            name: Name of the integration
            integration_type: Type of the integration
            config: Configuration for the integration
            
        Returns:
            Integration: The created integration
        """
        pass
    
    @abstractmethod
    def update_integration(self, integration_id: Union[str, UUID], 
                         config: Dict[str, Any]) -> Integration:
        """
        Update an integration
        
        Args:
            integration_id: ID of the integration
            config: New configuration
            
        Returns:
            Integration: The updated integration
        """
        pass
    
    @abstractmethod
    def get_integration(self, integration_id: Union[str, UUID]) -> Optional[Integration]:
        """
        Get an integration by ID
        
        Args:
            integration_id: ID of the integration
            
        Returns:
            Optional[Integration]: The integration if found
        """
        pass
    
    @abstractmethod
    def get_integrations_by_type(self, integration_type: IntegrationType) -> List[Integration]:
        """
        Get all integrations of a specific type
        
        Args:
            integration_type: Type of integrations to get
            
        Returns:
            List[Integration]: List of integrations
        """
        pass
    
    @abstractmethod
    def delete_integration(self, integration_id: Union[str, UUID]) -> bool:
        """
        Delete an integration
        
        Args:
            integration_id: ID of the integration
            
        Returns:
            bool: True if deleted successfully, False otherwise
        """
        pass


class N8nIntegrationService(IntegrationService):
    """Service for n8n integration"""
    
    def __init__(self, integration_repo: IntegrationRepository):
        self.integration_repo = integration_repo
    
    def register_integration(self, name: str, integration_type: IntegrationType, 
                           config: Dict[str, Any]) -> Integration:
        """Register a new n8n integration"""
        if integration_type != IntegrationType.N8N:
            raise ValueError("This service only supports n8n integrations")
        
        # Validate required config
        required_fields = ["host", "port"]
        for field in required_fields:
            if field not in config:
                raise ValueError(f"Missing required config field: {field}")
        
        # Create the integration
        integration = Integration(
            name=name,
            type=IntegrationType.N8N,
            config=config
        )
        
        # Save and return
        return self.integration_repo.save(integration)
    
    def update_integration(self, integration_id: Union[str, UUID], 
                         config: Dict[str, Any]) -> Integration:
        """Update an n8n integration"""
        integration = self.integration_repo.get_by_id(integration_id)
        if not integration:
            raise ValueError(f"Integration not found: {integration_id}")
        
        if integration.type != IntegrationType.N8N:
            raise ValueError("This service only supports n8n integrations")
        
        # Update config
        integration.update_config(config)
        
        # Save and return
        return self.integration_repo.save(integration)
    
    def get_integration(self, integration_id: Union[str, UUID]) -> Optional[Integration]:
        """Get an n8n integration by ID"""
        integration = self.integration_repo.get_by_id(integration_id)
        if integration and integration.type != IntegrationType.N8N:
            return None
        return integration
    
    def get_integrations_by_type(self, integration_type: IntegrationType) -> List[Integration]:
        """Get all n8n integrations"""
        if integration_type != IntegrationType.N8N:
            return []
        return self.integration_repo.get_by_type(IntegrationType.N8N)
    
    def delete_integration(self, integration_id: Union[str, UUID]) -> bool:
        """Delete an n8n integration"""
        integration = self.integration_repo.get_by_id(integration_id)
        if not integration or integration.type != IntegrationType.N8N:
            return False
        
        return self.integration_repo.delete(integration_id)
    
    def get_n8n_status(self, integration_id: Union[str, UUID]) -> Dict[str, Any]:
        """
        Get status of an n8n instance
        
        Args:
            integration_id: ID of the n8n integration
            
        Returns:
            Dict: Status information
        """
        integration = self.get_integration(integration_id)
        if not integration:
            return {"error": "Integration not found"}
        
        # This would normally call the n8n API to get status
        # For now, we'll just return a dummy status
        return {
            "id": str(integration.id),
            "name": integration.name,
            "status": "running" if integration.is_enabled else "stopped",
            "url": integration.config.get("url", ""),
            "version": integration.config.get("version", "unknown")
        }
    
    def create_n8n_workflow(self, integration_id: Union[str, UUID], 
                          workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a workflow in n8n
        
        Args:
            integration_id: ID of the n8n integration
            workflow_data: Workflow data
            
        Returns:
            Dict: Created workflow information
        """
        integration = self.get_integration(integration_id)
        if not integration:
            return {"error": "Integration not found"}
        
        # This would normally call the n8n API to create a workflow
        # For now, we'll just return a dummy response
        return {
            "id": "12345",
            "name": workflow_data.get("name", "Unnamed Workflow"),
            "active": False,
            "created": True
        }


class N8nWorkflowExecutor(WorkflowExecutorService):
    """n8n implementation of the workflow executor service"""
    
    def __init__(self, n8n_service: N8nIntegrationService, workflow_repo: WorkflowRepository):
        self.n8n_service = n8n_service
        self.workflow_repo = workflow_repo
    
    def execute_workflow(self, workflow_id: Union[str, UUID], 
                       trigger_data: Optional[Dict[str, Any]] = None) -> WorkflowExecution:
        """Execute a workflow using n8n"""
        workflow = self.workflow_repo.get_by_id(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")
        
        # Create an execution record
        execution = WorkflowExecution(workflow_id=str(workflow_id))
        
        # This would normally call the n8n API to execute the workflow
        # For now, we'll just simulate completion
        execution.complete({"message": "Workflow executed successfully"})
        
        return execution
    
    def get_execution_status(self, execution_id: Union[str, UUID]) -> Dict[str, Any]:
        """Get status of a workflow execution"""
        # This would normally query the n8n API for execution status
        # For now, we'll just return a dummy status
        return {
            "id": str(execution_id),
            "status": "completed",
            "startedAt": "2023-01-01T00:00:00Z",
            "finishedAt": "2023-01-01T00:00:01Z",
            "data": {"message": "Workflow executed successfully"}
        }
    
    def cancel_execution(self, execution_id: Union[str, UUID]) -> bool:
        """Cancel a workflow execution"""
        # This would normally call the n8n API to cancel an execution
        # For now, we'll just return success
        return True


class AutomationService:
    """
    High-level service for automation workflows
    """
    
    def __init__(
        self,
        workflow_repo: WorkflowRepository,
        integration_repo: IntegrationRepository,
        executor: WorkflowExecutorService
    ):
        self.workflow_repo = workflow_repo
        self.integration_repo = integration_repo
        self.executor = executor
    
    def create_workflow(self, name: str, description: Optional[str] = None) -> Workflow:
        """
        Create a new workflow
        
        Args:
            name: Name of the workflow
            description: Description of the workflow
            
        Returns:
            Workflow: The created workflow
        """
        workflow = Workflow(name=name, description=description)
        return self.workflow_repo.save(workflow)
    
    def add_trigger(self, workflow_id: Union[str, UUID], 
                   trigger_type: TriggerType, name: str,
                   parameters: Dict[str, Any]) -> Workflow:
        """
        Add a trigger to a workflow
        
        Args:
            workflow_id: ID of the workflow
            trigger_type: Type of trigger
            name: Name of the trigger
            parameters: Trigger parameters
            
        Returns:
            Workflow: The updated workflow
        """
        workflow = self.workflow_repo.get_by_id(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")
        
        trigger = WorkflowTrigger(type=trigger_type, name=name, parameters=parameters)
        workflow.add_trigger(trigger)
        
        return self.workflow_repo.save(workflow)
    
    def add_action(self, workflow_id: Union[str, UUID], name: str,
                  action_type: str, parameters: Dict[str, Any]) -> Workflow:
        """
        Add an action to a workflow
        
        Args:
            workflow_id: ID of the workflow
            name: Name of the action
            action_type: Type of action
            parameters: Action parameters
            
        Returns:
            Workflow: The updated workflow
        """
        workflow = self.workflow_repo.get_by_id(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")
        
        action = WorkflowAction(name=name, action_type=action_type, parameters=parameters)
        workflow.add_action(action)
        
        return self.workflow_repo.save(workflow)
    
    def activate_workflow(self, workflow_id: Union[str, UUID]) -> Workflow:
        """
        Activate a workflow
        
        Args:
            workflow_id: ID of the workflow
            
        Returns:
            Workflow: The updated workflow
        """
        workflow = self.workflow_repo.get_by_id(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")
        
        workflow.activate()
        return self.workflow_repo.save(workflow)
    
    def deactivate_workflow(self, workflow_id: Union[str, UUID]) -> Workflow:
        """
        Deactivate a workflow
        
        Args:
            workflow_id: ID of the workflow
            
        Returns:
            Workflow: The updated workflow
        """
        workflow = self.workflow_repo.get_by_id(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")
        
        workflow.deactivate()
        return self.workflow_repo.save(workflow)
    
    def execute_workflow(self, workflow_id: Union[str, UUID], 
                       trigger_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a workflow
        
        Args:
            workflow_id: ID of the workflow
            trigger_data: Data for the trigger
            
        Returns:
            Dict: Execution status
        """
        workflow = self.workflow_repo.get_by_id(workflow_id)
        if not workflow:
            return {"error": "Workflow not found"}
        
        try:
            execution = self.executor.execute_workflow(workflow_id, trigger_data)
            return {
                "execution_id": str(execution.id),
                "status": execution.status,
                "started_at": execution.started_at.isoformat(),
                "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
                "result": execution.result,
                "error": execution.error
            }
        except Exception as e:
            return {"error": str(e)}
    
    def get_active_workflows(self) -> List[Dict[str, Any]]:
        """
        Get all active workflows
        
        Returns:
            List[Dict]: List of active workflows
        """
        workflows = self.workflow_repo.get_by_status(WorkflowStatus.ACTIVE)
        result = []
        
        for workflow in workflows:
            result.append({
                "id": str(workflow.id),
                "name": workflow.name,
                "description": workflow.description,
                "created_at": workflow.created_at.isoformat(),
                "updated_at": workflow.updated_at.isoformat(),
                "trigger_count": len(workflow.triggers),
                "action_count": len(workflow.actions)
            })
            
        return result 