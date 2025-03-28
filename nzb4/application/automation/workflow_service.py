#!/usr/bin/env python3
"""
Workflow Application Service - Manages workflows and integrations
"""

import logging
import uuid
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from nzb4.config.settings import config
from nzb4.domain.automation.entities import (
    Workflow, WorkflowTrigger, WorkflowAction, WorkflowExecution, 
    WorkflowStatus, TriggerType, Integration, IntegrationType
)
from nzb4.domain.automation.services import (
    AutomationService, IntegrationService, WorkflowExecutorService
)
from nzb4.domain.automation.repositories import (
    WorkflowRepository, WorkflowExecutionRepository, IntegrationRepository
)
from nzb4.domain.automation.queries import (
    WorkflowByIdQuery, WorkflowsByStatusQuery, AllWorkflowsQuery,
    WorkflowExecutionByIdQuery, WorkflowExecutionsByWorkflowIdQuery,
    RecentWorkflowExecutionsQuery, IntegrationByIdQuery
)
from nzb4.infrastructure.n8n.n8n_manager import n8n_manager

logger = logging.getLogger(__name__)


class WorkflowApplicationService:
    """Application service for managing workflows and integrations"""
    
    def __init__(
        self,
        automation_service: AutomationService,
        workflow_repository: WorkflowRepository,
        execution_repository: WorkflowExecutionRepository,
        integration_repository: IntegrationRepository
    ):
        """Initialize the workflow application service"""
        self.automation_service = automation_service
        self.workflow_repository = workflow_repository
        self.execution_repository = execution_repository
        self.integration_repository = integration_repository
    
    # Workflow CRUD operations
    def create_workflow(
        self, 
        name: str, 
        description: str,
        trigger_type: TriggerType
    ) -> Workflow:
        """Create a new workflow"""
        logger.info(f"Creating new workflow: {name}")
        
        # Create a new workflow with a trigger
        workflow_id = str(uuid.uuid4())
        trigger = WorkflowTrigger(
            id=str(uuid.uuid4()),
            type=trigger_type,
            name=f"{name} Trigger",
            description=f"Trigger for {name}",
            parameters={},
            created_at=datetime.now()
        )
        
        workflow = Workflow(
            id=workflow_id,
            name=name,
            description=description,
            status=WorkflowStatus.DRAFT,
            triggers=[trigger],
            actions=[],
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # Save the workflow
        self.workflow_repository.save(workflow)
        
        # If we have an n8n integration and it's a webhook trigger, create an n8n workflow
        try:
            if trigger_type == TriggerType.WEBHOOK:
                # Check if n8n integration exists
                n8n_integrations = self.integration_repository.find_by_type(IntegrationType.N8N)
                if n8n_integrations and any(i.enabled for i in n8n_integrations):
                    n8n_integration = next(i for i in n8n_integrations if i.enabled)
                    
                    # Create webhook workflow in n8n
                    if n8n_manager.is_running():
                        n8n_workflow = n8n_manager.create_webhook_workflow(
                            name=name,
                            description=description
                        )
                        
                        # Update workflow with n8n workflow ID
                        workflow.metadata = {
                            "n8n_workflow_id": n8n_workflow.get("id")
                        }
                        self.workflow_repository.update(workflow)
                        
                        # Get webhook URL
                        webhook_url = n8n_manager.check_webhook_url(n8n_workflow.get("id"))
                        if webhook_url:
                            trigger.parameters["webhook_url"] = webhook_url
                            self.workflow_repository.update(workflow)
        except Exception as e:
            logger.error(f"Error creating n8n workflow: {e}")
        
        return workflow
    
    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """Get a workflow by ID"""
        return self.workflow_repository.find_by_id(WorkflowByIdQuery(id=workflow_id))
    
    def update_workflow(self, workflow: Workflow) -> Workflow:
        """Update a workflow"""
        logger.info(f"Updating workflow: {workflow.id}")
        
        # Update timestamp
        workflow.updated_at = datetime.now()
        
        # Save the workflow
        self.workflow_repository.update(workflow)
        
        # Update n8n workflow if available
        try:
            n8n_workflow_id = workflow.metadata.get("n8n_workflow_id")
            if n8n_workflow_id and n8n_manager.is_running():
                # Get the current n8n workflow
                n8n_workflow = n8n_manager.get_workflow(n8n_workflow_id)
                
                # Update basic properties
                n8n_workflow["name"] = workflow.name
                n8n_workflow["active"] = workflow.status == WorkflowStatus.ACTIVE
                if workflow.description:
                    n8n_workflow["description"] = workflow.description
                
                # Update the workflow in n8n
                n8n_manager.update_workflow(n8n_workflow_id, n8n_workflow)
        except Exception as e:
            logger.error(f"Error updating n8n workflow: {e}")
        
        return workflow
    
    def delete_workflow(self, workflow_id: str) -> bool:
        """Delete a workflow"""
        logger.info(f"Deleting workflow: {workflow_id}")
        workflow = self.get_workflow(workflow_id)
        
        if not workflow:
            logger.warning(f"Workflow not found: {workflow_id}")
            return False
        
        # Delete n8n workflow if available
        try:
            n8n_workflow_id = workflow.metadata.get("n8n_workflow_id")
            if n8n_workflow_id and n8n_manager.is_running():
                n8n_manager.delete_workflow(n8n_workflow_id)
        except Exception as e:
            logger.error(f"Error deleting n8n workflow: {e}")
        
        # Delete workflow executions
        executions = self.execution_repository.find_by_workflow_id(
            WorkflowExecutionsByWorkflowIdQuery(workflow_id=workflow_id)
        )
        for execution in executions:
            self.execution_repository.delete(execution.id)
        
        # Delete the workflow
        return self.workflow_repository.delete(workflow_id)
    
    def get_all_workflows(self, page: int = 1, page_size: int = 20) -> Tuple[List[Workflow], int]:
        """Get all workflows with pagination"""
        return self.workflow_repository.find_all(
            AllWorkflowsQuery(page=page, page_size=page_size)
        )
    
    def get_active_workflows(self) -> List[Workflow]:
        """Get all active workflows"""
        return self.workflow_repository.find_by_status(
            WorkflowsByStatusQuery(status=WorkflowStatus.ACTIVE)
        )
    
    # Workflow execution operations
    def execute_workflow(self, workflow_id: str, payload: Dict[str, Any] = None) -> WorkflowExecution:
        """Execute a workflow"""
        logger.info(f"Executing workflow: {workflow_id}")
        workflow = self.get_workflow(workflow_id)
        
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")
        
        if workflow.status != WorkflowStatus.ACTIVE:
            raise ValueError(f"Cannot execute inactive workflow: {workflow_id}")
        
        # Create a new execution record
        execution = WorkflowExecution(
            id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            status="RUNNING",
            started_at=datetime.now(),
            parameters=payload or {},
            result={},
            created_at=datetime.now()
        )
        
        # Save the execution
        self.execution_repository.save(execution)
        
        # Execute the workflow in the background
        try:
            self.automation_service.execute_workflow(workflow, execution, payload or {})
            
            # If the workflow is tied to n8n, execute it there too
            n8n_workflow_id = workflow.metadata.get("n8n_workflow_id")
            if n8n_workflow_id and n8n_manager.is_running():
                # Execute the workflow in n8n
                n8n_result = n8n_manager.execute_workflow(n8n_workflow_id, payload or {})
                
                # Update execution with n8n execution ID
                execution.metadata = {
                    "n8n_execution_id": n8n_result.get("id")
                }
                self.execution_repository.update(execution)
        except Exception as e:
            logger.error(f"Error executing workflow: {e}")
            execution.status = "FAILED"
            execution.completed_at = datetime.now()
            execution.result = {"error": str(e)}
            self.execution_repository.update(execution)
        
        return execution
    
    def get_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        """Get a workflow execution by ID"""
        return self.execution_repository.find_by_id(
            WorkflowExecutionByIdQuery(id=execution_id)
        )
    
    def get_workflow_executions(
        self,
        workflow_id: str,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[WorkflowExecution], int]:
        """Get executions for a workflow with pagination"""
        return self.execution_repository.find_by_workflow_id(
            WorkflowExecutionsByWorkflowIdQuery(
                workflow_id=workflow_id,
                page=page,
                page_size=page_size
            )
        )
    
    def get_recent_executions(
        self,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[WorkflowExecution], int]:
        """Get recent workflow executions with pagination"""
        return self.execution_repository.find_recent(
            RecentWorkflowExecutionsQuery(
                page=page,
                page_size=page_size
            )
        )
    
    # Workflow action operations
    def add_workflow_action(
        self,
        workflow_id: str,
        name: str,
        description: str,
        action_type: str,
        parameters: Dict[str, Any],
        position: int = None
    ) -> Workflow:
        """Add an action to a workflow"""
        logger.info(f"Adding action to workflow: {workflow_id}")
        workflow = self.get_workflow(workflow_id)
        
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")
        
        # Create a new action
        action = WorkflowAction(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            action_type=action_type,
            parameters=parameters,
            position=position if position is not None else len(workflow.actions),
            created_at=datetime.now()
        )
        
        # Add the action to the workflow
        workflow.add_action(action)
        
        # Save the workflow
        self.workflow_repository.update(workflow)
        
        return workflow
    
    def update_workflow_action(
        self,
        workflow_id: str,
        action_id: str,
        name: str = None,
        description: str = None,
        parameters: Dict[str, Any] = None,
        position: int = None
    ) -> Workflow:
        """Update an action in a workflow"""
        logger.info(f"Updating action {action_id} in workflow: {workflow_id}")
        workflow = self.get_workflow(workflow_id)
        
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")
        
        # Find the action
        action = next((a for a in workflow.actions if a.id == action_id), None)
        if not action:
            raise ValueError(f"Action not found: {action_id}")
        
        # Update the action
        if name:
            action.name = name
        if description:
            action.description = description
        if parameters:
            action.parameters = parameters
        if position is not None:
            action.position = position
        
        # Save the workflow
        self.workflow_repository.update(workflow)
        
        return workflow
    
    def remove_workflow_action(self, workflow_id: str, action_id: str) -> Workflow:
        """Remove an action from a workflow"""
        logger.info(f"Removing action {action_id} from workflow: {workflow_id}")
        workflow = self.get_workflow(workflow_id)
        
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")
        
        # Find the action
        action = next((a for a in workflow.actions if a.id == action_id), None)
        if not action:
            raise ValueError(f"Action not found: {action_id}")
        
        # Remove the action
        workflow.actions = [a for a in workflow.actions if a.id != action_id]
        
        # Reorder remaining actions
        for i, a in enumerate(sorted(workflow.actions, key=lambda x: x.position)):
            a.position = i
        
        # Save the workflow
        self.workflow_repository.update(workflow)
        
        return workflow
    
    # Workflow trigger operations
    def update_workflow_trigger(
        self,
        workflow_id: str,
        trigger_id: str,
        name: str = None,
        description: str = None,
        parameters: Dict[str, Any] = None,
        schedule: str = None
    ) -> Workflow:
        """Update a trigger in a workflow"""
        logger.info(f"Updating trigger {trigger_id} in workflow: {workflow_id}")
        workflow = self.get_workflow(workflow_id)
        
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")
        
        # Find the trigger
        trigger = next((t for t in workflow.triggers if t.id == trigger_id), None)
        if not trigger:
            raise ValueError(f"Trigger not found: {trigger_id}")
        
        # Update the trigger
        if name:
            trigger.name = name
        if description:
            trigger.description = description
        if parameters:
            trigger.parameters = parameters
        if schedule:
            trigger.schedule = schedule
        
        # Save the workflow
        self.workflow_repository.update(workflow)
        
        return workflow
    
    # Workflow status operations
    def activate_workflow(self, workflow_id: str) -> Workflow:
        """Activate a workflow"""
        logger.info(f"Activating workflow: {workflow_id}")
        workflow = self.get_workflow(workflow_id)
        
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")
        
        # Activate the workflow
        workflow.activate()
        
        # Save the workflow
        self.workflow_repository.update(workflow)
        
        # Activate n8n workflow if available
        try:
            n8n_workflow_id = workflow.metadata.get("n8n_workflow_id")
            if n8n_workflow_id and n8n_manager.is_running():
                # Get the current n8n workflow
                n8n_workflow = n8n_manager.get_workflow(n8n_workflow_id)
                
                # Set active state
                n8n_workflow["active"] = True
                
                # Update the workflow in n8n
                n8n_manager.update_workflow(n8n_workflow_id, n8n_workflow)
        except Exception as e:
            logger.error(f"Error activating n8n workflow: {e}")
        
        return workflow
    
    def deactivate_workflow(self, workflow_id: str) -> Workflow:
        """Deactivate a workflow"""
        logger.info(f"Deactivating workflow: {workflow_id}")
        workflow = self.get_workflow(workflow_id)
        
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")
        
        # Deactivate the workflow
        workflow.deactivate()
        
        # Save the workflow
        self.workflow_repository.update(workflow)
        
        # Deactivate n8n workflow if available
        try:
            n8n_workflow_id = workflow.metadata.get("n8n_workflow_id")
            if n8n_workflow_id and n8n_manager.is_running():
                # Get the current n8n workflow
                n8n_workflow = n8n_manager.get_workflow(n8n_workflow_id)
                
                # Set active state
                n8n_workflow["active"] = False
                
                # Update the workflow in n8n
                n8n_manager.update_workflow(n8n_workflow_id, n8n_workflow)
        except Exception as e:
            logger.error(f"Error deactivating n8n workflow: {e}")
        
        return workflow
    
    # Integration operations
    def get_integration(self, integration_id: str) -> Optional[Integration]:
        """Get an integration by ID"""
        return self.integration_repository.find_by_id(
            IntegrationByIdQuery(id=integration_id)
        )
    
    def get_n8n_status(self) -> Dict[str, Any]:
        """Get status information about the n8n integration"""
        return n8n_manager.get_status()
    
    def start_n8n(self) -> bool:
        """Start the n8n integration"""
        logger.info("Starting n8n integration")
        
        # Check if n8n is installed
        if not n8n_manager.is_installed():
            logger.info("n8n is not installed, installing now")
            try:
                n8n_manager.install()
            except Exception as e:
                logger.error(f"Error installing n8n: {e}")
                return False
        
        # Start n8n
        try:
            return n8n_manager.start()
        except Exception as e:
            logger.error(f"Error starting n8n: {e}")
            return False
    
    def stop_n8n(self) -> bool:
        """Stop the n8n integration"""
        logger.info("Stopping n8n integration")
        
        try:
            return n8n_manager.stop()
        except Exception as e:
            logger.error(f"Error stopping n8n: {e}")
            return False
    
    def restart_n8n(self) -> bool:
        """Restart the n8n integration"""
        logger.info("Restarting n8n integration")
        
        try:
            return n8n_manager.restart()
        except Exception as e:
            logger.error(f"Error restarting n8n: {e}")
            return False 