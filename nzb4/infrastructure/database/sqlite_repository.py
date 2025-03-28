#!/usr/bin/env python3
"""
SQLite implementation of the repository interfaces.
This provides concrete implementations of the repositories using SQLite.
"""

import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, Tuple
from uuid import UUID

from nzb4.domain.media.entities import (
    Media, MediaType, MediaSource, ConversionJob, 
    ConversionStatus, OutputFormat, VideoQuality, 
    ConversionOptions, MediaMetadata
)
from nzb4.domain.media.repositories import MediaRepository, ConversionJobRepository
from nzb4.domain.automation.entities import (
    Workflow, WorkflowExecution, Integration,
    WorkflowStatus, IntegrationType, TriggerType,
    WorkflowTrigger, WorkflowAction
)
from nzb4.domain.automation.repositories import (
    WorkflowRepository, WorkflowExecutionRepository, IntegrationRepository
)


class SQLiteDatabaseManager:
    """Manager for SQLite database operations"""
    
    def __init__(self, db_path: str):
        """Initialize with database path"""
        self.db_path = db_path
        self._ensure_directory_exists()
        self.initialize_database()
        
    def _ensure_directory_exists(self) -> None:
        """Ensure the directory for the database exists"""
        directory = os.path.dirname(self.db_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
    
    def get_connection(self) -> sqlite3.Connection:
        """Get a database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def initialize_database(self) -> None:
        """Initialize the database schema"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Create Media table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS media (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                source_type TEXT NOT NULL,
                media_type TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                metadata TEXT NOT NULL,
                status TEXT NOT NULL,
                downloaded_path TEXT,
                output_path TEXT,
                error_message TEXT,
                download_progress INTEGER NOT NULL,
                conversion_progress INTEGER NOT NULL
            )
            ''')
            
            # Create ConversionJob table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversion_jobs (
                id TEXT PRIMARY KEY,
                media_id TEXT NOT NULL,
                options TEXT NOT NULL,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                status TEXT NOT NULL,
                error_message TEXT,
                command TEXT,
                output_log TEXT NOT NULL,
                FOREIGN KEY (media_id) REFERENCES media (id)
            )
            ''')
            
            # Create Workflow table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS workflows (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                triggers TEXT NOT NULL,
                actions TEXT NOT NULL,
                status TEXT NOT NULL,
                metadata TEXT NOT NULL
            )
            ''')
            
            # Create WorkflowExecution table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS workflow_executions (
                id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                trigger_id TEXT,
                status TEXT NOT NULL,
                result TEXT NOT NULL,
                error TEXT,
                FOREIGN KEY (workflow_id) REFERENCES workflows (id)
            )
            ''')
            
            # Create Integration table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS integrations (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                config TEXT NOT NULL,
                is_enabled INTEGER NOT NULL
            )
            ''')
            
            # Create indices for better performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_media_status ON media (status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_media_type ON media (media_type)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_jobs_media_id ON conversion_jobs (media_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_jobs_status ON conversion_jobs (status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_workflows_status ON workflows (status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_executions_workflow_id ON workflow_executions (workflow_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_integrations_type ON integrations (type)')
            
            conn.commit()


class SQLiteMediaRepository(MediaRepository):
    """SQLite implementation of the MediaRepository interface"""
    
    def __init__(self, db_manager: SQLiteDatabaseManager):
        self.db_manager = db_manager
    
    def save(self, media: Media) -> Media:
        """Save a media entity to the repository"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Serialize metadata
            metadata_json = json.dumps(media.metadata.__dict__)
            
            cursor.execute('''
            INSERT OR REPLACE INTO media (
                id, source, source_type, media_type, created_at, updated_at,
                metadata, status, downloaded_path, output_path,
                error_message, download_progress, conversion_progress
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                media.id,
                media.source,
                media.source_type.name,
                media.media_type.name,
                media.created_at.isoformat(),
                media.updated_at.isoformat(),
                metadata_json,
                media.status.name,
                media.downloaded_path,
                media.output_path,
                media.error_message,
                media.download_progress,
                media.conversion_progress
            ))
            
            conn.commit()
            
        return media
    
    def get_by_id(self, media_id: Union[str, UUID]) -> Optional[Media]:
        """Get a media entity by ID"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM media WHERE id = ?', (str(media_id),))
            row = cursor.fetchone()
            
            if not row:
                return None
                
            return self._row_to_media(row)
    
    def get_all(self, limit: int = 100, offset: int = 0) -> List[Media]:
        """Get all media entities with pagination"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM media ORDER BY created_at DESC LIMIT ? OFFSET ?', 
                          (limit, offset))
            rows = cursor.fetchall()
            
            return [self._row_to_media(row) for row in rows]
    
    def get_by_status(self, status: ConversionStatus, limit: int = 100, offset: int = 0) -> List[Media]:
        """Get media entities by status"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT * FROM media 
            WHERE status = ? 
            ORDER BY created_at DESC 
            LIMIT ? OFFSET ?
            ''', (status.name, limit, offset))
            
            rows = cursor.fetchall()
            
            return [self._row_to_media(row) for row in rows]
    
    def get_by_type(self, media_type: MediaType, limit: int = 100, offset: int = 0) -> List[Media]:
        """Get media entities by type"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT * FROM media 
            WHERE media_type = ? 
            ORDER BY created_at DESC 
            LIMIT ? OFFSET ?
            ''', (media_type.name, limit, offset))
            
            rows = cursor.fetchall()
            
            return [self._row_to_media(row) for row in rows]
    
    def delete(self, media_id: Union[str, UUID]) -> bool:
        """Delete a media entity"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM media WHERE id = ?', (str(media_id),))
            conn.commit()
            
            return cursor.rowcount > 0
    
    def update_status(self, media_id: Union[str, UUID], status: ConversionStatus, 
                     error_message: Optional[str] = None) -> bool:
        """Update media status"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get current media
            cursor.execute('SELECT * FROM media WHERE id = ?', (str(media_id),))
            row = cursor.fetchone()
            
            if not row:
                return False
            
            # Update status
            cursor.execute('''
            UPDATE media 
            SET status = ?, error_message = ?, updated_at = ?
            WHERE id = ?
            ''', (
                status.name,
                error_message,
                datetime.now().isoformat(),
                str(media_id)
            ))
            
            conn.commit()
            
            return cursor.rowcount > 0
    
    def update_progress(self, media_id: Union[str, UUID], download_progress: Optional[int] = None,
                       conversion_progress: Optional[int] = None) -> bool:
        """Update media progress"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get current media
            cursor.execute('SELECT * FROM media WHERE id = ?', (str(media_id),))
            row = cursor.fetchone()
            
            if not row:
                return False
            
            # Determine values to update
            updates = []
            params = []
            
            if download_progress is not None:
                updates.append('download_progress = ?')
                params.append(max(0, min(100, download_progress)))
            
            if conversion_progress is not None:
                updates.append('conversion_progress = ?')
                params.append(max(0, min(100, conversion_progress)))
            
            if not updates:
                return False
            
            # Add updated_at and ID
            updates.append('updated_at = ?')
            params.append(datetime.now().isoformat())
            params.append(str(media_id))
            
            # Execute update
            cursor.execute(f'''
            UPDATE media 
            SET {', '.join(updates)}
            WHERE id = ?
            ''', params)
            
            conn.commit()
            
            return cursor.rowcount > 0
    
    def search(self, query: str, limit: int = 100, offset: int = 0) -> List[Media]:
        """Search for media entities"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Simple search implementation
            search_term = f'%{query}%'
            
            cursor.execute('''
            SELECT * FROM media 
            WHERE source LIKE ? OR media_type LIKE ?
            ORDER BY created_at DESC 
            LIMIT ? OFFSET ?
            ''', (search_term, search_term, limit, offset))
            
            rows = cursor.fetchall()
            
            return [self._row_to_media(row) for row in rows]
    
    def _row_to_media(self, row: sqlite3.Row) -> Media:
        """Convert a database row to a Media entity"""
        # Parse metadata
        metadata_dict = json.loads(row['metadata'])
        metadata = MediaMetadata(**metadata_dict)
        
        # Create Media object
        media = Media(
            id=row['id'],
            source=row['source'],
            source_type=MediaSource[row['source_type']],
            media_type=MediaType[row['media_type']],
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at']),
            metadata=metadata,
            status=ConversionStatus[row['status']],
            downloaded_path=row['downloaded_path'],
            output_path=row['output_path'],
            error_message=row['error_message'],
            download_progress=row['download_progress'],
            conversion_progress=row['conversion_progress']
        )
        
        return media


class SQLiteWorkflowRepository(WorkflowRepository):
    """SQLite implementation of the WorkflowRepository interface"""
    
    def __init__(self, db_manager: SQLiteDatabaseManager):
        self.db_manager = db_manager
    
    def save(self, workflow: Workflow) -> Workflow:
        """Save a workflow entity to the repository"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Serialize triggers
            triggers_json = json.dumps([self._trigger_to_dict(t) for t in workflow.triggers])
            
            # Serialize actions
            actions_json = json.dumps([self._action_to_dict(a) for a in workflow.actions])
            
            # Serialize metadata
            metadata_json = json.dumps(workflow.metadata)
            
            cursor.execute('''
            INSERT OR REPLACE INTO workflows (
                id, name, description, created_at, updated_at,
                triggers, actions, status, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                workflow.id,
                workflow.name,
                workflow.description,
                workflow.created_at.isoformat(),
                workflow.updated_at.isoformat(),
                triggers_json,
                actions_json,
                workflow.status.name,
                metadata_json
            ))
            
            conn.commit()
            
        return workflow
    
    def get_by_id(self, workflow_id: Union[str, UUID]) -> Optional[Workflow]:
        """Get a workflow entity by ID"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM workflows WHERE id = ?', (str(workflow_id),))
            row = cursor.fetchone()
            
            if not row:
                return None
                
            return self._row_to_workflow(row)
    
    def get_all(self, limit: int = 100, offset: int = 0) -> List[Workflow]:
        """Get all workflow entities with pagination"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM workflows ORDER BY created_at DESC LIMIT ? OFFSET ?', 
                          (limit, offset))
            rows = cursor.fetchall()
            
            return [self._row_to_workflow(row) for row in rows]
    
    def get_by_status(self, status: WorkflowStatus, limit: int = 100, offset: int = 0) -> List[Workflow]:
        """Get workflow entities by status"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT * FROM workflows 
            WHERE status = ? 
            ORDER BY created_at DESC 
            LIMIT ? OFFSET ?
            ''', (status.name, limit, offset))
            
            rows = cursor.fetchall()
            
            return [self._row_to_workflow(row) for row in rows]
    
    def delete(self, workflow_id: Union[str, UUID]) -> bool:
        """Delete a workflow entity"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM workflows WHERE id = ?', (str(workflow_id),))
            conn.commit()
            
            return cursor.rowcount > 0
    
    def update_status(self, workflow_id: Union[str, UUID], status: WorkflowStatus) -> bool:
        """Update workflow status"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
            UPDATE workflows 
            SET status = ?, updated_at = ?
            WHERE id = ?
            ''', (
                status.name,
                datetime.now().isoformat(),
                str(workflow_id)
            ))
            
            conn.commit()
            
            return cursor.rowcount > 0
    
    def search(self, query: str, limit: int = 100, offset: int = 0) -> List[Workflow]:
        """Search for workflow entities"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Simple search implementation
            search_term = f'%{query}%'
            
            cursor.execute('''
            SELECT * FROM workflows 
            WHERE name LIKE ? OR description LIKE ?
            ORDER BY created_at DESC 
            LIMIT ? OFFSET ?
            ''', (search_term, search_term, limit, offset))
            
            rows = cursor.fetchall()
            
            return [self._row_to_workflow(row) for row in rows]
    
    def _trigger_to_dict(self, trigger: WorkflowTrigger) -> Dict[str, Any]:
        """Convert a trigger to a dictionary for serialization"""
        return {
            'id': trigger.id,
            'type': trigger.type.name,
            'name': trigger.name,
            'description': trigger.description,
            'parameters': trigger.parameters,
            'schedule': trigger.schedule
        }
    
    def _dict_to_trigger(self, data: Dict[str, Any]) -> WorkflowTrigger:
        """Convert a dictionary to a WorkflowTrigger"""
        return WorkflowTrigger(
            id=data['id'],
            type=TriggerType[data['type']],
            name=data['name'],
            description=data.get('description'),
            parameters=data.get('parameters', {}),
            schedule=data.get('schedule')
        )
    
    def _action_to_dict(self, action: WorkflowAction) -> Dict[str, Any]:
        """Convert an action to a dictionary for serialization"""
        return {
            'id': action.id,
            'name': action.name,
            'description': action.description,
            'action_type': action.action_type,
            'parameters': action.parameters,
            'position': action.position
        }
    
    def _dict_to_action(self, data: Dict[str, Any]) -> WorkflowAction:
        """Convert a dictionary to a WorkflowAction"""
        return WorkflowAction(
            id=data['id'],
            name=data['name'],
            description=data.get('description'),
            action_type=data['action_type'],
            parameters=data.get('parameters', {}),
            position=data.get('position', 0)
        )
    
    def _row_to_workflow(self, row: sqlite3.Row) -> Workflow:
        """Convert a database row to a Workflow entity"""
        # Parse triggers
        triggers_data = json.loads(row['triggers'])
        triggers = [self._dict_to_trigger(t) for t in triggers_data]
        
        # Parse actions
        actions_data = json.loads(row['actions'])
        actions = [self._dict_to_action(a) for a in actions_data]
        
        # Parse metadata
        metadata = json.loads(row['metadata'])
        
        # Create Workflow object
        workflow = Workflow(
            id=row['id'],
            name=row['name'],
            description=row['description'],
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at']),
            triggers=triggers,
            actions=actions,
            status=WorkflowStatus[row['status']],
            metadata=metadata
        )
        
        return workflow


class SQLiteIntegrationRepository(IntegrationRepository):
    """SQLite implementation of the IntegrationRepository interface"""
    
    def __init__(self, db_manager: SQLiteDatabaseManager):
        self.db_manager = db_manager
    
    def save(self, integration: Integration) -> Integration:
        """Save an integration entity to the repository"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Serialize config
            config_json = json.dumps(integration.config)
            
            cursor.execute('''
            INSERT OR REPLACE INTO integrations (
                id, name, type, created_at, updated_at,
                config, is_enabled
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                integration.id,
                integration.name,
                integration.type.name,
                integration.created_at.isoformat(),
                integration.updated_at.isoformat(),
                config_json,
                1 if integration.is_enabled else 0
            ))
            
            conn.commit()
            
        return integration
    
    def get_by_id(self, integration_id: Union[str, UUID]) -> Optional[Integration]:
        """Get an integration entity by ID"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM integrations WHERE id = ?', (str(integration_id),))
            row = cursor.fetchone()
            
            if not row:
                return None
                
            return self._row_to_integration(row)
    
    def get_all(self, limit: int = 100, offset: int = 0) -> List[Integration]:
        """Get all integration entities with pagination"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM integrations ORDER BY created_at DESC LIMIT ? OFFSET ?', 
                          (limit, offset))
            rows = cursor.fetchall()
            
            return [self._row_to_integration(row) for row in rows]
    
    def get_by_type(self, integration_type: IntegrationType, limit: int = 100, offset: int = 0) -> List[Integration]:
        """Get integration entities by type"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT * FROM integrations 
            WHERE type = ? 
            ORDER BY created_at DESC 
            LIMIT ? OFFSET ?
            ''', (integration_type.name, limit, offset))
            
            rows = cursor.fetchall()
            
            return [self._row_to_integration(row) for row in rows]
    
    def delete(self, integration_id: Union[str, UUID]) -> bool:
        """Delete an integration entity"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM integrations WHERE id = ?', (str(integration_id),))
            conn.commit()
            
            return cursor.rowcount > 0
    
    def update_config(self, integration_id: Union[str, UUID], config: Dict[str, Any]) -> bool:
        """Update integration configuration"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get current integration
            cursor.execute('SELECT * FROM integrations WHERE id = ?', (str(integration_id),))
            row = cursor.fetchone()
            
            if not row:
                return False
            
            # Merge config
            current_config = json.loads(row['config'])
            current_config.update(config)
            
            # Update config
            cursor.execute('''
            UPDATE integrations 
            SET config = ?, updated_at = ?
            WHERE id = ?
            ''', (
                json.dumps(current_config),
                datetime.now().isoformat(),
                str(integration_id)
            ))
            
            conn.commit()
            
            return cursor.rowcount > 0
    
    def update_status(self, integration_id: Union[str, UUID], is_enabled: bool) -> bool:
        """Update integration status"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
            UPDATE integrations 
            SET is_enabled = ?, updated_at = ?
            WHERE id = ?
            ''', (
                1 if is_enabled else 0,
                datetime.now().isoformat(),
                str(integration_id)
            ))
            
            conn.commit()
            
            return cursor.rowcount > 0
    
    def _row_to_integration(self, row: sqlite3.Row) -> Integration:
        """Convert a database row to an Integration entity"""
        # Parse config
        config = json.loads(row['config'])
        
        # Create Integration object
        integration = Integration(
            id=row['id'],
            name=row['name'],
            type=IntegrationType[row['type']],
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at']),
            config=config,
            is_enabled=bool(row['is_enabled'])
        )
        
        return integration 