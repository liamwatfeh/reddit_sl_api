"""
Background job queue system for handling long-running analysis tasks.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
import traceback

from app.core.logging import get_logger
from app.models.schemas import UnifiedAnalysisResponse

logger = get_logger(__name__)


class JobStatus(str, Enum):
    """Job status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class JobResult:
    """Container for job execution results."""
    job_id: str
    status: JobStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    progress: float = 0.0
    progress_message: str = "Initializing..."
    
    @property
    def processing_time(self) -> Optional[float]:
        """Calculate processing time in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        elif self.started_at:
            return (datetime.now() - self.started_at).total_seconds()
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert job result to dictionary for API responses."""
        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "processing_time": self.processing_time,
            "progress": self.progress,
            "progress_message": self.progress_message,
            "result": self.result,
            "error": self.error,
            "error_details": self.error_details
        }


class BackgroundJobQueue:
    """
    In-memory background job queue for handling long-running analysis tasks.
    
    This queue provides:
    - Asynchronous job execution
    - Job status tracking
    - Progress reporting
    - Result caching with TTL
    - Graceful error handling
    """
    
    def __init__(self, max_concurrent_jobs: int = 3, result_ttl_hours: int = 24):
        """
        Initialize the job queue.
        
        Args:
            max_concurrent_jobs: Maximum number of jobs running concurrently
            result_ttl_hours: Hours to keep completed job results
        """
        self.max_concurrent_jobs = max_concurrent_jobs
        self.result_ttl = timedelta(hours=result_ttl_hours)
        self.jobs: Dict[str, JobResult] = {}
        self.running_jobs: Dict[str, asyncio.Task] = {}
        self.job_semaphore = asyncio.Semaphore(max_concurrent_jobs)
        self._cleanup_task: Optional[asyncio.Task] = None
        self._start_cleanup_task()
        
        logger.info(f"Background job queue initialized with {max_concurrent_jobs} max concurrent jobs")
    
    def _start_cleanup_task(self) -> None:
        """Start the periodic cleanup task for expired results."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
    
    async def _periodic_cleanup(self) -> None:
        """Periodically clean up expired job results."""
        while True:
            try:
                await asyncio.sleep(3600)  # Clean up every hour
                await self._cleanup_expired_results()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error during job cleanup: {e}")
    
    async def _cleanup_expired_results(self) -> None:
        """Remove expired job results from memory."""
        current_time = datetime.now()
        expired_jobs = []
        
        for job_id, job_result in self.jobs.items():
            if (job_result.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED] and
                job_result.completed_at and 
                current_time - job_result.completed_at > self.result_ttl):
                expired_jobs.append(job_id)
        
        for job_id in expired_jobs:
            del self.jobs[job_id]
            logger.debug(f"Cleaned up expired job result: {job_id}")
        
        if expired_jobs:
            logger.info(f"Cleaned up {len(expired_jobs)} expired job results")
    
    async def submit_job(
        self, 
        job_func: Callable[..., Awaitable[Any]], 
        *args, 
        **kwargs
    ) -> str:
        """
        Submit a job to the background queue.
        
        Args:
            job_func: Async function to execute
            *args: Positional arguments for the job function
            **kwargs: Keyword arguments for the job function
            
        Returns:
            job_id: Unique identifier for tracking the job
        """
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        
        # Create job result entry
        job_result = JobResult(
            job_id=job_id,
            status=JobStatus.PENDING,
            created_at=datetime.now()
        )
        
        self.jobs[job_id] = job_result
        
        # Create and start the job task
        job_task = asyncio.create_task(self._execute_job(job_id, job_func, *args, **kwargs))
        self.running_jobs[job_id] = job_task
        
        logger.info(f"Job submitted: {job_id}")
        return job_id
    
    async def _execute_job(
        self, 
        job_id: str, 
        job_func: Callable[..., Awaitable[Any]], 
        *args, 
        **kwargs
    ) -> None:
        """
        Execute a job with proper error handling and status tracking.
        
        Args:
            job_id: Job identifier
            job_func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments
        """
        job_result = self.jobs[job_id]
        
        # Wait for available slot
        async with self.job_semaphore:
            try:
                job_result.status = JobStatus.RUNNING
                job_result.started_at = datetime.now()
                job_result.progress = 10.0
                job_result.progress_message = "Starting analysis..."
                
                logger.info(f"Job started: {job_id}")
                
                # Execute the job function
                result = await job_func(job_id, *args, **kwargs)
                
                # Mark as completed
                job_result.status = JobStatus.COMPLETED
                job_result.completed_at = datetime.now()
                job_result.result = result
                job_result.progress = 100.0
                job_result.progress_message = "Analysis completed successfully"
                
                logger.info(f"Job completed: {job_id} (took {job_result.processing_time:.2f}s)")
                
            except asyncio.CancelledError:
                job_result.status = JobStatus.CANCELLED
                job_result.completed_at = datetime.now()
                job_result.error = "Job was cancelled"
                job_result.progress_message = "Job cancelled"
                logger.warning(f"Job cancelled: {job_id}")
                raise
                
            except Exception as e:
                job_result.status = JobStatus.FAILED
                job_result.completed_at = datetime.now()
                job_result.error = str(e)
                job_result.error_details = {
                    "exception_type": type(e).__name__,
                    "traceback": traceback.format_exc()
                }
                job_result.progress_message = f"Job failed: {str(e)}"
                
                logger.error(f"Job failed: {job_id} - {str(e)}", exc_info=True)
                
            finally:
                # Clean up running job reference
                if job_id in self.running_jobs:
                    del self.running_jobs[job_id]
    
    def get_job_status(self, job_id: str) -> Optional[JobResult]:
        """
        Get the current status of a job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            JobResult if found, None otherwise
        """
        return self.jobs.get(job_id)
    
    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a running job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            True if job was cancelled, False if job not found or already completed
        """
        if job_id in self.running_jobs:
            task = self.running_jobs[job_id]
            if not task.done():
                task.cancel()
                logger.info(f"Job cancellation requested: {job_id}")
                return True
        return False
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get statistics about the job queue."""
        total_jobs = len(self.jobs)
        running_jobs = len(self.running_jobs)
        
        status_counts = {}
        for job in self.jobs.values():
            status_counts[job.status.value] = status_counts.get(job.status.value, 0) + 1
        
        return {
            "total_jobs": total_jobs,
            "running_jobs": running_jobs,
            "available_slots": self.max_concurrent_jobs - running_jobs,
            "max_concurrent_jobs": self.max_concurrent_jobs,
            "status_breakdown": status_counts,
            "result_ttl_hours": self.result_ttl.total_seconds() / 3600
        }
    
    async def shutdown(self) -> None:
        """Gracefully shutdown the job queue."""
        logger.info("Shutting down job queue...")
        
        # Cancel cleanup task
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Cancel all running jobs
        for job_id, task in self.running_jobs.items():
            if not task.done():
                task.cancel()
                logger.info(f"Cancelled job during shutdown: {job_id}")
        
        # Wait for all tasks to complete
        if self.running_jobs:
            await asyncio.gather(*self.running_jobs.values(), return_exceptions=True)
        
        logger.info("Job queue shutdown completed")


# Global job queue instance
_job_queue: Optional[BackgroundJobQueue] = None


def get_job_queue() -> BackgroundJobQueue:
    """Get or create the global job queue instance."""
    global _job_queue
    if _job_queue is None:
        from app.core.config import get_settings
        settings = get_settings()
        _job_queue = BackgroundJobQueue(
            max_concurrent_jobs=settings.max_concurrent_agents,
            result_ttl_hours=24
        )
    return _job_queue


async def update_job_progress(job_id: str, progress: float, message: str) -> None:
    """
    Update job progress (called from within job functions).
    
    Args:
        job_id: Job identifier
        progress: Progress percentage (0-100)
        message: Progress message
    """
    job_queue = get_job_queue()
    job_result = job_queue.get_job_status(job_id)
    if job_result:
        job_result.progress = progress
        job_result.progress_message = message
        logger.debug(f"Job {job_id} progress: {progress}% - {message}") 