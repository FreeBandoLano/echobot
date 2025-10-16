"""Task queue manager for automated pipeline processing - now using shared database."""

import logging
import threading
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from enum import Enum
from dataclasses import dataclass

from config import Config
from database import db
from sqlalchemy import text

# Set up logging
logger = logging.getLogger(__name__)

class TaskType(Enum):
    """Types of tasks in the pipeline."""
    TRANSCRIBE_BLOCK = "transcribe_block"
    SUMMARIZE_BLOCK = "summarize_block"
    EMAIL_BLOCK_SUMMARY = "email_block_summary"
    CREATE_DAILY_DIGEST = "create_daily_digest"
    EMAIL_DAILY_DIGEST = "email_daily_digest"

class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"

@dataclass
class Task:
    """Represents a task in the queue."""
    id: Optional[int]
    task_type: TaskType
    block_id: Optional[int]
    show_date: Optional[str]
    parameters: Dict
    status: TaskStatus
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    retry_count: int
    max_retries: int
    error_message: Optional[str]

class TaskManager:
    """Manages automated task execution and state transitions."""
    
    def __init__(self):
        self.running = False
        self.worker_thread = None
        self.task_handlers = {}
        # Use shared database connection - tables created in database.py
        self._register_handlers()
    
    def _register_handlers(self):
        """Register task type handlers."""
        from transcription import transcriber
        from summarization import summarizer
        from email_service import email_service
        
        self.task_handlers = {
            TaskType.TRANSCRIBE_BLOCK: self._handle_transcribe_block,
            TaskType.SUMMARIZE_BLOCK: self._handle_summarize_block,
            TaskType.EMAIL_BLOCK_SUMMARY: self._handle_email_block_summary,
            TaskType.CREATE_DAILY_DIGEST: self._handle_create_daily_digest,
            TaskType.EMAIL_DAILY_DIGEST: self._handle_email_daily_digest,
        }
    
    def start(self):
        """Start the task manager worker."""
        if self.running:
            logger.warning("Task manager already running")
            return
        
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        logger.info("Task manager started")
    
    def stop(self):
        """Stop the task manager worker."""
        self.running = False
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=10)
        logger.info("Task manager stopped")
    
    def add_task(self, task_type: TaskType, block_id: Optional[int] = None, 
                 show_date: Optional[str] = None, parameters: Dict = None,
                 max_retries: int = 3) -> int:
        """Add a new task to the queue."""
        if parameters is None:
            parameters = {}
        
        with db.get_connection() as conn:
            # Check for duplicate tasks to prevent race conditions
            if db.use_azure_sql:
                query = text("""
                    SELECT id FROM tasks 
                    WHERE task_type = :task_type AND block_id = :block_id 
                    AND status IN ('pending', 'running', 'retry')
                """)
                result = conn.execute(query, {
                    'task_type': task_type.value,
                    'block_id': block_id
                }).fetchone()
            else:
                query = """
                    SELECT id FROM tasks 
                    WHERE task_type = ? AND block_id = ? 
                    AND status IN ('pending', 'running', 'retry')
                """
                result = conn.execute(query, (task_type.value, block_id)).fetchone()
            
            if result:
                existing_id = result[0]
                logger.info(f"Task {task_type.value} for block {block_id} already exists (id={existing_id})")
                return existing_id
            
            # Insert new task
            created_at = datetime.now()
            
            if db.use_azure_sql:
                query = text("""
                    INSERT INTO tasks (task_type, block_id, show_date, parameters, 
                                     status, created_at, max_retries)
                    OUTPUT INSERTED.id
                    VALUES (:task_type, :block_id, :show_date, :parameters, 
                           :status, :created_at, :max_retries)
                """)
                result = conn.execute(query, {
                    'task_type': task_type.value,
                    'block_id': block_id,
                    'show_date': show_date,
                    'parameters': json.dumps(parameters),
                    'status': TaskStatus.PENDING.value,
                    'created_at': created_at,
                    'max_retries': max_retries
                }).fetchone()
                if result and result[0] is not None:
                    task_id = int(result[0])
                    logger.info(f"Successfully inserted task with OUTPUT INSERTED.id: {task_id}")
                else:
                    logger.error("OUTPUT INSERTED.id returned None")
                    raise Exception("Failed to get task_id from OUTPUT INSERTED.id")
            else:
                query = """
                    INSERT INTO tasks (task_type, block_id, show_date, parameters, 
                                     status, created_at, max_retries)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """
                cursor = conn.execute(query, (
                    task_type.value,
                    block_id,
                    show_date,
                    json.dumps(parameters),
                    TaskStatus.PENDING.value,
                    created_at.isoformat(),
                    max_retries
                ))
                task_id = cursor.lastrowid
            
            conn.commit()
        
        logger.info(f"Added task {task_id}: {task_type.value}")
        return task_id
    
    def _worker_loop(self):
        """Main worker loop to process tasks."""
        logger.info("Task manager worker started")
        
        while self.running:
            try:
                # Get next pending task
                task = self._get_next_task()
                
                if task:
                    self._execute_task(task)
                else:
                    # No tasks available, wait
                    time.sleep(5)
                    
            except Exception as e:
                logger.error(f"Worker loop error: {e}")
                time.sleep(10)
    
    def _get_next_task(self) -> Optional[Task]:
        """Get the next pending task from the queue."""
        with db.get_connection() as conn:
            if db.use_azure_sql:
                query = text("""
                    SELECT TOP 1 * FROM tasks 
                    WHERE status IN ('pending', 'retry')
                    ORDER BY created_at ASC
                """)
                result = conn.execute(query).fetchone()
            else:
                query = """
                    SELECT * FROM tasks 
                    WHERE status IN ('pending', 'retry')
                    ORDER BY created_at ASC
                    LIMIT 1
                """
                result = conn.execute(query).fetchone()
            
            if not result:
                return None
            
            # Convert row to Task object
            row = dict(result._mapping) if hasattr(result, '_mapping') else dict(zip(result.keys(), result))
            
            return Task(
                id=row['id'],
                task_type=TaskType(row['task_type']),
                block_id=row['block_id'],
                show_date=row['show_date'],
                parameters=json.loads(row['parameters']) if row['parameters'] else {},
                status=TaskStatus(row['status']),
                created_at=row['created_at'] if isinstance(row['created_at'], datetime) else datetime.fromisoformat(str(row['created_at'])),
                started_at=row['started_at'] if not row['started_at'] or isinstance(row['started_at'], datetime) else datetime.fromisoformat(str(row['started_at'])),
                completed_at=row['completed_at'] if not row['completed_at'] or isinstance(row['completed_at'], datetime) else datetime.fromisoformat(str(row['completed_at'])),
                retry_count=row['retry_count'],
                max_retries=row['max_retries'],
                error_message=row['error_message']
            )
    
    def _execute_task(self, task: Task):
        """Execute a single task."""
        logger.info(f"Executing task {task.id}: {task.task_type.value}")
        print(f"🔄 Processing Task #{task.id}: {task.task_type.value}")
        
        # Mark task as running
        self._update_task_status(task.id, TaskStatus.RUNNING, started_at=datetime.now())
        
        try:
            # Get handler for task type
            handler = self.task_handlers.get(task.task_type)
            if not handler:
                raise ValueError(f"No handler for task type: {task.task_type}")
            
            # Execute the task
            result = handler(task)
            
            if result:
                # Task completed successfully
                self._update_task_status(task.id, TaskStatus.COMPLETED, 
                                       completed_at=datetime.now())
                print(f"✅ Task #{task.id} completed successfully")
                logger.info(f"Task {task.id} completed successfully")
                
                # Schedule next task in pipeline if applicable
                self._schedule_next_pipeline_task(task)
            else:
                # Task failed
                print(f"❌ Task #{task.id} failed")
                self._handle_task_failure(task, "Task handler returned False")
                
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Task #{task.id} failed with error: {error_msg}")
            logger.error(f"Task {task.id} failed: {error_msg}")
            self._handle_task_failure(task, error_msg)
    
    def _handle_task_failure(self, task: Task, error_message: str):
        """Handle task failure with retry logic."""
        if task.retry_count < task.max_retries:
            # Schedule retry
            retry_count = task.retry_count + 1
            self._update_task_status(task.id, TaskStatus.RETRY, 
                                   error_message=error_message,
                                   retry_count=retry_count)
            logger.warning(f"Task {task.id} will retry ({retry_count}/{task.max_retries})")
        else:
            # Max retries exceeded
            self._update_task_status(task.id, TaskStatus.FAILED, 
                                   error_message=error_message,
                                   completed_at=datetime.now())
            logger.error(f"Task {task.id} failed permanently after {task.max_retries} retries")
    
    def _update_task_status(self, task_id: int, status: TaskStatus, 
                           started_at: Optional[datetime] = None,
                           completed_at: Optional[datetime] = None,
                           error_message: Optional[str] = None,
                           retry_count: Optional[int] = None):
        """Update task status in database."""
        updates = {'status': status.value}
        
        if started_at:
            updates['started_at'] = started_at
        if completed_at:
            updates['completed_at'] = completed_at
        if error_message:
            updates['error_message'] = error_message
        if retry_count is not None:
            updates['retry_count'] = retry_count
        
        with db.get_connection() as conn:
            if db.use_azure_sql:
                set_clause = ', '.join([f"{k} = :{k}" for k in updates.keys()])
                query = text(f"UPDATE tasks SET {set_clause} WHERE id = :task_id")
                updates['task_id'] = task_id
                conn.execute(query, updates)
            else:
                set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
                query = f"UPDATE tasks SET {set_clause} WHERE id = ?"
                conn.execute(query, tuple(list(updates.values()) + [task_id]))
            
            conn.commit()
    
    def _schedule_next_pipeline_task(self, completed_task: Task):
        """Schedule the next task in the processing pipeline."""
        if completed_task.task_type == TaskType.TRANSCRIBE_BLOCK:
            # After transcription, schedule summarization
            self.add_task(TaskType.SUMMARIZE_BLOCK, block_id=completed_task.block_id, show_date=completed_task.show_date)
            
        elif completed_task.task_type == TaskType.SUMMARIZE_BLOCK:
            # After summarization, NO LONGER schedule individual block emails
            # Only schedule daily digest when all blocks are complete
            logger.info(f"Block {completed_task.block_id} summarized - skipping individual email")
            
            # Check if this was the last block of the day - schedule daily digest
            if completed_task.show_date:
                self._check_schedule_daily_digest(completed_task.show_date)
    
    def _check_schedule_daily_digest(self, show_date: str):
        """Check if all blocks are complete and schedule daily digest."""
        from datetime import date
        from config import Config
        
        # Check if task_manager should handle digest creation
        if Config.DIGEST_CREATOR not in ['task_manager', 'both']:
            logger.info(f"🚫 Task manager skipping digest creation (DIGEST_CREATOR={Config.DIGEST_CREATOR})")
            return
        
        # Skip if daily digest is disabled
        if not Config.ENABLE_DAILY_DIGEST:
            logger.info(f"Daily digest is disabled, skipping digest creation for {show_date}")
            return
        
        # Get all blocks for the date
        date_obj = datetime.strptime(show_date, '%Y-%m-%d').date()
        blocks = db.get_blocks_by_date(date_obj)
        completed_blocks = [b for b in blocks if b['status'] == 'completed']
        
        # Expected number of blocks for a full show day (A, B, C, D)
        expected_block_count = len(Config.BLOCKS)
        
        # Check if all EXPECTED blocks are completed
        # This prevents premature digest creation when only some blocks have been recorded
        logger.info(f"📊 Digest check for {show_date}: {len(completed_blocks)}/{expected_block_count} blocks completed ({len(blocks)} exist)")
        
        # Only schedule digest if we have all expected blocks AND they're all completed
        if len(completed_blocks) >= expected_block_count and len(completed_blocks) == len(blocks):
            # Check if digest task already exists
            with db.get_connection() as conn:
                if db.use_azure_sql:
                    query = text("""
                        SELECT COUNT(*) as count FROM tasks 
                        WHERE task_type = :task_type AND show_date = :show_date 
                        AND status NOT IN ('failed')
                    """)
                    result = conn.execute(query, {
                        'task_type': TaskType.CREATE_DAILY_DIGEST.value,
                        'show_date': show_date
                    }).fetchone()
                    count = result[0]
                else:
                    query = """
                        SELECT COUNT(*) FROM tasks 
                        WHERE task_type = ? AND show_date = ? 
                        AND status NOT IN ('failed')
                    """
                    result = conn.execute(query, (TaskType.CREATE_DAILY_DIGEST.value, show_date)).fetchone()
                    count = result[0]
                
                if count == 0:
                    logger.info(f"✅ All {len(completed_blocks)} blocks complete for {show_date} - scheduling digest creation")
                    self.add_task(TaskType.CREATE_DAILY_DIGEST, show_date=show_date)
                else:
                    logger.info(f"Digest task already exists for {show_date}")
    
    # Task Handlers
    def _handle_transcribe_block(self, task: Task) -> bool:
        """Handle block transcription task."""
        from transcription import transcriber
        
        if not task.block_id:
            raise ValueError("Block ID required for transcription task")
        
        result = transcriber.transcribe_block(task.block_id)
        return result is not None
    
    def _handle_summarize_block(self, task: Task) -> bool:
        """Handle block summarization task."""
        from summarization import summarizer
        
        if not task.block_id:
            raise ValueError("Block ID required for summarization task")
        
        result = summarizer.summarize_block(task.block_id)
        return result is not None
    
    def _handle_email_block_summary(self, task: Task) -> bool:
        """Handle block summary email task."""
        from email_service import email_service
        
        if not task.block_id:
            raise ValueError("Block ID required for email task")
        
        return email_service.send_block_summary(task.block_id)
    
    def _handle_create_daily_digest(self, task: Task) -> bool:
        """Handle daily digest creation task."""
        from summarization import summarizer
        from datetime import datetime
        
        if not task.show_date:
            raise ValueError("Show date required for daily digest task")
        
        date_obj = datetime.strptime(task.show_date, '%Y-%m-%d').date()
        result = summarizer.create_daily_digest(date_obj)
        
        if result:
            # Schedule email for the digest
            self.add_task(TaskType.EMAIL_DAILY_DIGEST, show_date=task.show_date)
            return True
        return False
    
    def _handle_email_daily_digest(self, task: Task) -> bool:
        """Handle daily digest email task."""
        from email_service import email_service
        from datetime import datetime
        
        if not task.show_date:
            raise ValueError("Show date required for digest email task")
        
        date_obj = datetime.strptime(task.show_date, '%Y-%m-%d').date()
        return email_service.send_daily_digest(date_obj)
    
    def get_task_status(self, task_id: int) -> Optional[Dict]:
        """Get status of a specific task."""
        with db.get_connection() as conn:
            if db.use_azure_sql:
                query = text("SELECT * FROM tasks WHERE id = :task_id")
                result = conn.execute(query, {'task_id': task_id}).fetchone()
            else:
                query = "SELECT * FROM tasks WHERE id = ?"
                result = conn.execute(query, (task_id,)).fetchone()
            
            if result:
                return dict(result._mapping) if hasattr(result, '_mapping') else dict(zip(result.keys(), result))
        return None
    
    def get_pending_tasks(self) -> List[Dict]:
        """Get all pending tasks."""
        with db.get_connection() as conn:
            if db.use_azure_sql:
                query = text("""
                    SELECT * FROM tasks 
                    WHERE status IN ('pending', 'running', 'retry')
                    ORDER BY created_at ASC
                """)
                results = conn.execute(query).fetchall()
            else:
                query = """
                    SELECT * FROM tasks 
                    WHERE status IN ('pending', 'running', 'retry')
                    ORDER BY created_at ASC
                """
                results = conn.execute(query).fetchall()
            
            return [dict(row._mapping) if hasattr(row, '_mapping') else dict(zip(row.keys(), row)) for row in results]
    
    def clear_old_tasks(self, days: int = 30):
        """Clear completed/failed tasks older than specified days."""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        with db.get_connection() as conn:
            if db.use_azure_sql:
                query = text("""
                    DELETE FROM tasks 
                    WHERE status IN ('completed', 'failed') 
                    AND created_at < :cutoff_date
                """)
                result = conn.execute(query, {'cutoff_date': cutoff_date})
                deleted_count = result.rowcount
            else:
                query = """
                    DELETE FROM tasks 
                    WHERE status IN ('completed', 'failed') 
                    AND created_at < ?
                """
                result = conn.execute(query, (cutoff_date.isoformat(),))
                deleted_count = result.rowcount
            
            conn.commit()
        
        logger.info(f"Cleared {deleted_count} old tasks")
        return deleted_count

# Global task manager instance
task_manager = TaskManager()

if __name__ == "__main__":
    # Test the task manager
    logging.basicConfig(level=logging.INFO)
    
    task_manager.start()
    
    # Add a test task
    task_id = task_manager.add_task(TaskType.TRANSCRIBE_BLOCK, block_id=1)
    print(f"Added test task: {task_id}")
    
    # Wait a bit
    time.sleep(5)
    
    # Check status
    status = task_manager.get_task_status(task_id)
    print(f"Task status: {status}")
    
    task_manager.stop()
