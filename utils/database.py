#!/usr/bin/env python3
"""
Database utilities for persistent storage
"""

import os
import json
import sqlite3
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Union
import uuid

# Setup logging
logger = logging.getLogger(__name__)

# Database constants
DB_FILE = os.environ.get("DB_FILE", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "jobs.db"))  # Use local data directory for testing
DB_SCHEMA_VERSION = 1
DEFAULT_RETENTION_DAYS = 30

# Thread safety
db_lock = threading.RLock()

def dict_factory(cursor, row):
    """Convert row to dictionary for better JSON serialization"""
    d = {}
    for idx, col in enumerate(cursor.description):
        value = row[idx]
        # Handle special JSON fields
        if col[0] in ['output', 'error'] and value:
            try:
                value = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                # If it's not valid JSON, keep as is
                pass
        d[col[0]] = value
    return d

def init_db() -> None:
    """Initialize the database with tables if they don't exist"""
    with db_lock:
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            
            # Create jobs table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                media_source TEXT NOT NULL,
                media_type TEXT NOT NULL,
                output_format TEXT NOT NULL,
                keep_original BOOLEAN NOT NULL,
                status TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                end_time REAL,
                return_code INTEGER,
                output_file TEXT,
                output TEXT,
                error TEXT,
                cmd TEXT,
                hostname TEXT,
                user_agent TEXT,
                retried_from TEXT
            )
            ''')
            
            # Create settings table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at REAL NOT NULL
            )
            ''')
            
            # Initialize schema version
            cursor.execute('INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES (?, ?, ?)',
                          ('schema_version', str(DB_SCHEMA_VERSION), time.time()))
                          
            # Initialize job retention period
            cursor.execute('INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES (?, ?, ?)',
                          ('job_retention_days', str(DEFAULT_RETENTION_DAYS), time.time()))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Database initialized at {DB_FILE}")
            
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise

def get_db_connection() -> sqlite3.Connection:
    """Get a database connection with row factory set"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = dict_factory
    return conn

def save_job(job_data: Dict[str, Any]) -> bool:
    """Save job data to the database"""
    with db_lock:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Add or update timestamp
            job_data['updated_at'] = time.time()
            
            # Convert list outputs to JSON
            if 'output' in job_data and isinstance(job_data['output'], list):
                job_data['output'] = json.dumps(job_data['output'])
                
            # Get existing columns
            cursor.execute('PRAGMA table_info(jobs)')
            columns = [col['name'] for col in cursor.fetchall()]
            
            # Filter job_data to only include valid columns
            filtered_data = {k: v for k, v in job_data.items() if k in columns}
            
            # Create placeholders and values for SQL
            placeholders = ', '.join(['?' for _ in filtered_data])
            update_clauses = ', '.join([f'{k} = ?' for k in filtered_data])
            cols = ', '.join(filtered_data.keys())
            vals = list(filtered_data.values())
            
            # Insert or update job
            cursor.execute(f'''
            INSERT INTO jobs ({cols})
            VALUES ({placeholders})
            ON CONFLICT(id) DO UPDATE SET
            {update_clauses}
            ''', vals + vals)  # Double the values for both INSERT and UPDATE
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"Error saving job data: {e}")
            return False

def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Get job data from the database"""
    with db_lock:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM jobs WHERE id = ?', (job_id,))
            job = cursor.fetchone()
            
            conn.close()
            
            if job and 'output' in job and isinstance(job['output'], str):
                try:
                    job['output'] = json.loads(job['output'])
                except (json.JSONDecodeError, TypeError):
                    job['output'] = job['output'].split('\n') if job['output'] else []
            
            return job
            
        except Exception as e:
            logger.error(f"Error getting job data: {e}")
            return None

def delete_job(job_id: str) -> bool:
    """Delete job from the database"""
    with db_lock:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM jobs WHERE id = ?', (job_id,))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"Error deleting job: {e}")
            return False

def get_all_jobs(limit: int = 100) -> List[Dict[str, Any]]:
    """Get all jobs with a limit"""
    with db_lock:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT id, media_source, media_type, output_format, status, 
                   created_at, updated_at, end_time, output_file, error
            FROM jobs
            ORDER BY created_at DESC
            LIMIT ?
            ''', (limit,))
            
            jobs = cursor.fetchall()
            
            conn.close()
            return jobs
            
        except Exception as e:
            logger.error(f"Error getting all jobs: {e}")
            return []

def get_active_jobs() -> List[Dict[str, Any]]:
    """Get all active jobs (running or pending)"""
    with db_lock:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT *
            FROM jobs
            WHERE status IN ('running', 'pending')
            ORDER BY created_at DESC
            ''')
            
            jobs = cursor.fetchall()
            
            for job in jobs:
                if 'output' in job and isinstance(job['output'], str):
                    try:
                        job['output'] = json.loads(job['output'])
                    except (json.JSONDecodeError, TypeError):
                        job['output'] = job['output'].split('\n') if job['output'] else []
            
            conn.close()
            return jobs
            
        except Exception as e:
            logger.error(f"Error getting active jobs: {e}")
            return []

def get_job_stats() -> Dict[str, int]:
    """Get job statistics"""
    with db_lock:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) as running,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled
            FROM jobs
            ''')
            
            stats = cursor.fetchone()
            
            conn.close()
            return stats
            
        except Exception as e:
            logger.error(f"Error getting job stats: {e}")
            return {
                'total': 0,
                'pending': 0,
                'running': 0,
                'completed': 0,
                'failed': 0,
                'cancelled': 0
            }

def cleanup_old_jobs(days: int = None) -> int:
    """Clean up jobs older than specified days"""
    with db_lock:
        try:
            if days is None:
                # Get setting from database
                conn = get_db_connection()
                cursor = conn.cursor()
                
                cursor.execute('SELECT value FROM settings WHERE key = ?', ('job_retention_days',))
                result = cursor.fetchone()
                conn.close()
                
                days = int(result['value']) if result else DEFAULT_RETENTION_DAYS
            
            # Calculate cutoff timestamp
            cutoff_time = time.time() - (days * 86400)  # 86400 seconds in a day
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Get count of jobs to be deleted
            cursor.execute('''
            SELECT COUNT(*)
            FROM jobs
            WHERE created_at < ? AND status NOT IN ('running', 'pending')
            ''', (cutoff_time,))
            
            count = cursor.fetchone()['COUNT(*)']
            
            # Delete old jobs
            cursor.execute('''
            DELETE FROM jobs
            WHERE created_at < ? AND status NOT IN ('running', 'pending')
            ''', (cutoff_time,))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Cleaned up {count} jobs older than {days} days")
            return count
            
        except Exception as e:
            logger.error(f"Error cleaning up old jobs: {e}")
            return 0

def update_setting(key: str, value: str) -> bool:
    """Update a setting in the database"""
    with db_lock:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
            INSERT OR REPLACE INTO settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ''', (key, value, time.time()))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"Error updating setting: {e}")
            return False

def get_setting(key: str, default: str = None) -> str:
    """Get a setting from the database"""
    with db_lock:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
            result = cursor.fetchone()
            
            conn.close()
            
            if result:
                return result['value']
            return default
            
        except Exception as e:
            logger.error(f"Error getting setting: {e}")
            return default

def get_all_settings() -> Dict[str, str]:
    """Get all settings from the database"""
    with db_lock:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT key, value FROM settings')
            results = cursor.fetchall()
            
            conn.close()
            
            return {row['key']: row['value'] for row in results}
            
        except Exception as e:
            logger.error(f"Error getting all settings: {e}")
            return {}

def run_db_maintenance() -> Dict[str, Any]:
    """Run database maintenance tasks"""
    with db_lock:
        try:
            # Start with cleaning up old jobs
            deleted_count = cleanup_old_jobs()
            
            # Run VACUUM to reclaim space
            conn = sqlite3.connect(DB_FILE)
            conn.execute('VACUUM')
            conn.close()
            
            # Get database file size
            db_size = os.path.getsize(DB_FILE) if os.path.exists(DB_FILE) else 0
            
            return {
                'success': True,
                'deleted_jobs': deleted_count,
                'db_size_bytes': db_size,
                'db_size_mb': round(db_size / (1024 * 1024), 2),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error running database maintenance: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

# Ensure DB directory exists
def ensure_db_directory():
    """Ensure the database directory exists"""
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    
# Initialize database at module load
ensure_db_directory()
init_db()

# Job Operations
def save_job(job_data: Dict[str, Any]) -> str:
    """
    Save a job to the database
    Returns the job ID
    """
    conn = get_db_connection()
    try:
        # Ensure we have required fields
        if "id" not in job_data:
            job_data["id"] = str(uuid.uuid4())
        
        current_time = int(time.time())
        if "created_at" not in job_data:
            job_data["created_at"] = current_time
        
        job_data["updated_at"] = current_time
        
        # Convert complex data types to JSON
        if "meta" in job_data and isinstance(job_data["meta"], dict):
            job_data["meta"] = json.dumps(job_data["meta"])
        
        # Prepare fields for insert/update
        fields = [
            "id", "title", "status", "source", "output_path",
            "created_at", "updated_at", "completed_at",
            "progress", "meta", "log"
        ]
        
        # Filter to existing fields
        existing_fields = []
        values = []
        for field in fields:
            if field in job_data:
                existing_fields.append(field)
                values.append(job_data[field])
        
        # Check if job exists
        cur = conn.cursor()
        cur.execute("SELECT id FROM jobs WHERE id = ?", (job_data["id"],))
        exists = cur.fetchone() is not None
        
        if exists:
            # Update
            set_clause = ", ".join([f"{field} = ?" for field in existing_fields])
            query = f"UPDATE jobs SET {set_clause} WHERE id = ?"
            values.append(job_data["id"])
            cur.execute(query, values)
        else:
            # Insert
            placeholders = ", ".join(["?"] * len(existing_fields))
            fields_str = ", ".join(existing_fields)
            query = f"INSERT INTO jobs ({fields_str}) VALUES ({placeholders})"
            cur.execute(query, values)
        
        conn.commit()
        return job_data["id"]
    except sqlite3.Error as e:
        logger.error(f"Error saving job: {e}")
        raise
    finally:
        conn.close()

def update_job_status(job_id: str, status: str, progress: Optional[int] = None) -> bool:
    """Update a job's status and optionally its progress"""
    conn = get_db_connection()
    try:
        timestamp = int(time.time())
        query = "UPDATE jobs SET status = ?, updated_at = ?"
        params = [status, timestamp]
        
        # If completed or failed, set completed_at
        if status in ["completed", "failed", "cancelled"]:
            query += ", completed_at = ?"
            params.append(timestamp)
        
        # If progress provided, update it
        if progress is not None:
            query += ", progress = ?"
            params.append(progress)
        
        query += " WHERE id = ?"
        params.append(job_id)
        
        conn.execute(query, params)
        conn.commit()
        
        # Add to audit log
        log_event("JOB_STATUS_CHANGE", {
            "job_id": job_id,
            "status": status,
            "progress": progress
        })
        
        return True
    except sqlite3.Error as e:
        logger.error(f"Error updating job status: {e}")
        return False
    finally:
        conn.close()

def update_job_progress(job_id: str, progress: int) -> bool:
    """Update a job's progress percentage (0-100)"""
    conn = get_db_connection()
    try:
        conn.execute(
            "UPDATE jobs SET progress = ?, updated_at = ? WHERE id = ?",
            (progress, int(time.time()), job_id)
        )
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Error updating job progress: {e}")
        return False
    finally:
        conn.close()

def update_job_log(job_id: str, log_text: str, append: bool = True) -> bool:
    """Update a job's log"""
    conn = get_db_connection()
    try:
        if append:
            # Get existing log
            cur = conn.cursor()
            cur.execute("SELECT log FROM jobs WHERE id = ?", (job_id,))
            result = cur.fetchone()
            
            if result and result["log"]:
                log_text = result["log"] + "\n" + log_text
        
        conn.execute(
            "UPDATE jobs SET log = ?, updated_at = ? WHERE id = ?",
            (log_text, int(time.time()), job_id)
        )
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Error updating job log: {e}")
        return False
    finally:
        conn.close()

def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Get a job by ID"""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        job = cur.fetchone()
        
        if job:
            # Convert JSON strings back to objects
            if job.get("meta"):
                try:
                    job["meta"] = json.loads(job["meta"])
                except json.JSONDecodeError:
                    pass  # Leave as string if invalid JSON
                    
            return job
        return None
    except sqlite3.Error as e:
        logger.error(f"Error getting job: {e}")
        return None
    finally:
        conn.close()

def get_all_jobs(
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    sort_by: str = "created_at",
    sort_dir: str = "DESC"
) -> List[Dict[str, Any]]:
    """Get all jobs with optional filtering and pagination"""
    conn = get_db_connection()
    try:
        query = "SELECT * FROM jobs"
        params = []
        
        if status:
            query += " WHERE status = ?"
            params.append(status)
        
        # Validate sort parameters to prevent SQL injection
        valid_sort_fields = ["created_at", "updated_at", "completed_at", "title", "status", "progress"]
        valid_sort_dirs = ["ASC", "DESC"]
        
        if sort_by not in valid_sort_fields:
            sort_by = "created_at"
        if sort_dir not in valid_sort_dirs:
            sort_dir = "DESC"
        
        query += f" ORDER BY {sort_by} {sort_dir}"
        query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cur = conn.cursor()
        cur.execute(query, params)
        jobs = cur.fetchall()
        
        # Convert JSON strings back to objects
        for job in jobs:
            if job.get("meta"):
                try:
                    job["meta"] = json.loads(job["meta"])
                except json.JSONDecodeError:
                    pass  # Leave as string if invalid JSON
        
        return jobs
    except sqlite3.Error as e:
        logger.error(f"Error getting jobs: {e}")
        return []
    finally:
        conn.close()

def delete_job(job_id: str) -> bool:
    """Delete a job by ID"""
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        conn.execute("DELETE FROM notifications WHERE job_id = ?", (job_id,))
        conn.commit()
        
        # Add to audit log
        log_event("JOB_DELETED", {"job_id": job_id})
        
        return True
    except sqlite3.Error as e:
        logger.error(f"Error deleting job: {e}")
        return False
    finally:
        conn.close()

def cleanup_old_jobs(days: int = 30) -> int:
    """Delete jobs older than the specified number of days"""
    conn = get_db_connection()
    try:
        # Only delete completed, failed, or cancelled jobs
        cutoff_time = int(time.time()) - (days * 86400)
        cur = conn.cursor()
        
        # First get IDs to log them
        cur.execute(
            "SELECT id FROM jobs WHERE status IN ('completed', 'failed', 'cancelled') AND created_at < ?",
            (cutoff_time,)
        )
        jobs = cur.fetchall()
        job_ids = [job["id"] for job in jobs]
        
        # Delete jobs
        cur.execute(
            "DELETE FROM jobs WHERE status IN ('completed', 'failed', 'cancelled') AND created_at < ?",
            (cutoff_time,)
        )
        
        # Delete related notifications
        if job_ids:
            placeholders = ",".join(["?" for _ in job_ids])
            cur.execute(f"DELETE FROM notifications WHERE job_id IN ({placeholders})", job_ids)
        
        conn.commit()
        
        # Log the cleanup
        cleaned = cur.rowcount
        if cleaned > 0:
            log_event("JOBS_CLEANUP", {
                "count": cleaned, 
                "older_than_days": days,
                "job_ids": job_ids
            })
            
        return cleaned
    except sqlite3.Error as e:
        logger.error(f"Error cleaning up old jobs: {e}")
        return 0
    finally:
        conn.close()

# Settings Operations
def get_setting(key: str, default: Any = None) -> Any:
    """Get a setting value by key"""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
        result = cur.fetchone()
        
        if result:
            return result["value"]
        return default
    except sqlite3.Error as e:
        logger.error(f"Error getting setting: {e}")
        return default
    finally:
        conn.close()

def save_setting(key: str, value: Any) -> bool:
    """Save a setting value"""
    conn = get_db_connection()
    try:
        # Convert value to string if it's not already
        if not isinstance(value, str):
            value = str(value)
            
        timestamp = int(time.time())
        
        # Check if setting exists
        cur = conn.cursor()
        cur.execute("SELECT key FROM settings WHERE key = ?", (key,))
        exists = cur.fetchone() is not None
        
        if exists:
            conn.execute(
                "UPDATE settings SET value = ?, updated_at = ? WHERE key = ?",
                (value, timestamp, key)
            )
        else:
            conn.execute(
                "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
                (key, value, timestamp)
            )
            
        conn.commit()
        
        # Log setting change
        log_event("SETTING_CHANGED", {"key": key})
        
        return True
    except sqlite3.Error as e:
        logger.error(f"Error saving setting: {e}")
        return False
    finally:
        conn.close()

def get_all_settings() -> Dict[str, str]:
    """Get all settings as a dictionary"""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT key, value FROM settings")
        settings = cur.fetchall()
        
        return {item["key"]: item["value"] for item in settings}
    except sqlite3.Error as e:
        logger.error(f"Error getting all settings: {e}")
        return {}
    finally:
        conn.close()

# Notification Operations
def add_notification(notification_type: str, message: str, job_id: Optional[str] = None) -> int:
    """Add a notification to the database"""
    conn = get_db_connection()
    try:
        timestamp = int(time.time())
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO notifications (type, message, job_id, created_at) VALUES (?, ?, ?, ?)",
            (notification_type, message, job_id, timestamp)
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.Error as e:
        logger.error(f"Error adding notification: {e}")
        return 0
    finally:
        conn.close()

def get_unread_notifications(limit: int = 100) -> List[Dict[str, Any]]:
    """Get unread notifications"""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM notifications WHERE is_read = 0 ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
        return cur.fetchall()
    except sqlite3.Error as e:
        logger.error(f"Error getting unread notifications: {e}")
        return []
    finally:
        conn.close()

def mark_notification_read(notification_id: int) -> bool:
    """Mark a notification as read"""
    conn = get_db_connection()
    try:
        conn.execute(
            "UPDATE notifications SET is_read = 1 WHERE id = ?",
            (notification_id,)
        )
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Error marking notification as read: {e}")
        return False
    finally:
        conn.close()

def mark_all_notifications_read() -> bool:
    """Mark all notifications as read"""
    conn = get_db_connection()
    try:
        conn.execute("UPDATE notifications SET is_read = 1")
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Error marking all notifications as read: {e}")
        return False
    finally:
        conn.close()

# Audit log
def log_event(event_type: str, event_data: Dict[str, Any]) -> bool:
    """Log an event to the audit log"""
    conn = get_db_connection()
    try:
        timestamp = int(time.time())
        
        # Convert event data to JSON
        event_json = json.dumps(event_data)
        
        conn.execute(
            "INSERT INTO audit_log (event_type, event_data, created_at) VALUES (?, ?, ?)",
            (event_type, event_json, timestamp)
        )
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Error logging event: {e}")
        return False
    except Exception as e:
        logger.error(f"Error serializing event data: {e}")
        return False
    finally:
        conn.close()

def get_audit_log(
    event_type: Optional[str] = None,
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """Get audit log entries with optional filtering"""
    conn = get_db_connection()
    try:
        query = "SELECT * FROM audit_log"
        params = []
        conditions = []
        
        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)
            
        if start_time:
            conditions.append("created_at >= ?")
            params.append(start_time)
            
        if end_time:
            conditions.append("created_at <= ?")
            params.append(end_time)
            
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
            
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        cur = conn.cursor()
        cur.execute(query, params)
        events = cur.fetchall()
        
        # Parse JSON data
        for event in events:
            if event.get("event_data"):
                try:
                    event["event_data"] = json.loads(event["event_data"])
                except json.JSONDecodeError:
                    pass  # Leave as string if invalid JSON
                    
        return events
    except sqlite3.Error as e:
        logger.error(f"Error getting audit log: {e}")
        return []
    finally:
        conn.close()

# Utility functions
def get_job_count_by_status() -> Dict[str, int]:
    """Get count of jobs grouped by status"""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT status, COUNT(*) as count FROM jobs GROUP BY status")
        results = cur.fetchall()
        
        counts = {"pending": 0, "processing": 0, "completed": 0, "failed": 0, "cancelled": 0}
        for row in results:
            counts[row["status"]] = row["count"]
            
        return counts
    except sqlite3.Error as e:
        logger.error(f"Error getting job counts: {e}")
        return {"pending": 0, "processing": 0, "completed": 0, "failed": 0, "cancelled": 0}
    finally:
        conn.close()

def get_active_job_count() -> int:
    """Get count of active jobs (pending or processing)"""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) as count FROM jobs WHERE status IN ('pending', 'processing')"
        )
        result = cur.fetchone()
        
        return result["count"] if result else 0
    except sqlite3.Error as e:
        logger.error(f"Error getting active job count: {e}")
        return 0
    finally:
        conn.close()

def can_start_new_job() -> bool:
    """Check if a new job can be started based on concurrency limits"""
    try:
        max_concurrent = int(get_setting("max_concurrent_jobs", 2))
        active_count = get_active_job_count()
        
        return active_count < max_concurrent
    except Exception as e:
        logger.error(f"Error checking if new job can be started: {e}")
        return False

def run_maintenance() -> Dict[str, Any]:
    """Run maintenance tasks"""
    try:
        start_time = time.time()
        results = {
            "success": True,
            "jobs_cleaned": 0,
            "elapsed_seconds": 0,
            "errors": []
        }
        
        # Get retention period
        try:
            retention_days = int(get_setting("job_retention_days", 30))
        except (ValueError, TypeError):
            retention_days = 30
            results["errors"].append("Invalid job_retention_days setting, using default of 30")
        
        # Clean up old jobs
        try:
            results["jobs_cleaned"] = cleanup_old_jobs(retention_days)
        except Exception as e:
            results["errors"].append(f"Error cleaning up old jobs: {str(e)}")
            results["success"] = False
        
        # Update maintenance timestamp
        save_setting("last_maintenance", int(time.time()))
        
        # Log maintenance
        log_event("MAINTENANCE_RUN", {
            "jobs_cleaned": results["jobs_cleaned"],
            "retention_days": retention_days
        })
        
        results["elapsed_seconds"] = round(time.time() - start_time, 2)
        return results
    except Exception as e:
        logger.error(f"Error running maintenance: {e}")
        return {
            "success": False,
            "jobs_cleaned": 0,
            "elapsed_seconds": 0,
            "errors": [str(e)]
        }

def check_maintenance_needed() -> bool:
    """Check if maintenance should be run"""
    try:
        last_maintenance = int(get_setting("last_maintenance", 0))
        interval_hours = int(get_setting("maintenance_interval_hours", 24))
        
        # Convert to seconds
        interval_seconds = interval_hours * 3600
        current_time = int(time.time())
        
        return (current_time - last_maintenance) >= interval_seconds
    except Exception as e:
        logger.error(f"Error checking maintenance status: {e}")
        return False 