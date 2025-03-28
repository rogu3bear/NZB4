import os
import time
import psutil
import logging
import threading
import shutil
from typing import Dict, Any, List, Optional

# Import utilities
from utils.database import get_setting, save_setting, log_event
from utils.notifications import notify_disk_space_low, notify_system_error

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_CHECK_INTERVAL = 300  # 5 minutes
DEFAULT_DISK_SPACE_WARNING_THRESHOLD = 90  # 90% usage
DEFAULT_CPU_WARNING_THRESHOLD = 80  # 80% usage for sustained period
DEFAULT_MEMORY_WARNING_THRESHOLD = 90  # 90% usage

class SystemMonitor:
    def __init__(self):
        self.is_running = False
        self.monitor_thread = None
        self.last_cpu_warning = 0
        self.cpu_high_count = 0
        self.last_memory_warning = 0
        self.last_disk_warning = 0
        
        # Configure from settings
        self.check_interval = int(get_setting("monitor_check_interval", DEFAULT_CHECK_INTERVAL))
        self.disk_space_warning_threshold = int(get_setting("disk_space_warning_threshold", DEFAULT_DISK_SPACE_WARNING_THRESHOLD))
        self.cpu_warning_threshold = int(get_setting("cpu_warning_threshold", DEFAULT_CPU_WARNING_THRESHOLD))
        self.memory_warning_threshold = int(get_setting("memory_warning_threshold", DEFAULT_MEMORY_WARNING_THRESHOLD))
        
    def start(self):
        """Start the system monitor thread"""
        if self.is_running:
            logger.info("System monitor is already running")
            return
            
        logger.info("Starting system monitor")
        self.is_running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
    def stop(self):
        """Stop the system monitor thread"""
        if not self.is_running:
            return
            
        logger.info("Stopping system monitor")
        self.is_running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
            
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.is_running:
            try:
                self._check_system_health()
            except Exception as e:
                logger.error(f"Error in system monitor: {e}")
                
            # Sleep for the check interval
            time.sleep(self.check_interval)
            
    def _check_system_health(self):
        """Check system health metrics"""
        # Get current metrics
        metrics = self.get_system_metrics()
        
        # Check disk space
        self._check_disk_space(metrics)
        
        # Check CPU usage
        self._check_cpu_usage(metrics)
        
        # Check memory usage
        self._check_memory_usage(metrics)
        
        # Log metrics periodically
        log_event("SYSTEM_METRICS", metrics)
        
    def _check_disk_space(self, metrics: Dict[str, Any]):
        """Check disk space and notify if low"""
        disk_percent = metrics["disk"]["percent"]
        available_gb = metrics["disk"]["free_gb"]
        
        # Check if we're above the warning threshold
        if disk_percent >= self.disk_space_warning_threshold:
            # Don't spam warnings - only send once per hour
            current_time = time.time()
            if (current_time - self.last_disk_warning) > 3600:
                notify_disk_space_low(available_gb, disk_percent)
                self.last_disk_warning = current_time
                logger.warning(f"Low disk space: {available_gb:.2f}GB available ({disk_percent}% used)")
                
    def _check_cpu_usage(self, metrics: Dict[str, Any]):
        """Check CPU usage and notify if consistently high"""
        cpu_percent = metrics["cpu"]["percent"]
        
        # Check if we're above the warning threshold
        if cpu_percent >= self.cpu_warning_threshold:
            self.cpu_high_count += 1
            
            # If CPU has been high for 3 consecutive checks, send warning
            if self.cpu_high_count >= 3:
                current_time = time.time()
                # Don't spam warnings - only send once per hour
                if (current_time - self.last_cpu_warning) > 3600:
                    notify_system_error(f"CPU usage has been high ({cpu_percent}%) for an extended period")
                    self.last_cpu_warning = current_time
                    logger.warning(f"High CPU usage: {cpu_percent}% for extended period")
                    
                # Reset counter after notification
                self.cpu_high_count = 0
        else:
            # Reset counter if CPU usage drops below threshold
            self.cpu_high_count = 0
            
    def _check_memory_usage(self, metrics: Dict[str, Any]):
        """Check memory usage and notify if high"""
        memory_percent = metrics["memory"]["percent"]
        
        # Check if we're above the warning threshold
        if memory_percent >= self.memory_warning_threshold:
            current_time = time.time()
            # Don't spam warnings - only send once per hour
            if (current_time - self.last_memory_warning) > 3600:
                notify_system_error(f"Memory usage is high: {memory_percent}%")
                self.last_memory_warning = current_time
                logger.warning(f"High memory usage: {memory_percent}%")
    
    @staticmethod
    def get_system_metrics() -> Dict[str, Any]:
        """Get current system metrics"""
        try:
            # Get CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Get memory usage
            memory = psutil.virtual_memory()
            
            # Get disk usage for data directory
            data_path = os.path.dirname(get_setting("DB_FILE", "/config/jobs.db"))
            disk = shutil.disk_usage(data_path)
            disk_total_gb = disk.total / (1024 ** 3)
            disk_used_gb = disk.used / (1024 ** 3)
            disk_free_gb = disk.free / (1024 ** 3)
            disk_percent = (disk.used / disk.total) * 100
            
            # Get process info
            process = psutil.Process(os.getpid())
            process_cpu = process.cpu_percent(interval=None)
            process_memory = process.memory_info()
            
            # Build metrics dict
            metrics = {
                "timestamp": int(time.time()),
                "cpu": {
                    "percent": cpu_percent,
                    "process_percent": process_cpu
                },
                "memory": {
                    "total_mb": memory.total / (1024 ** 2),
                    "used_mb": memory.used / (1024 ** 2),
                    "free_mb": memory.available / (1024 ** 2),
                    "percent": memory.percent,
                    "process_mb": process_memory.rss / (1024 ** 2)
                },
                "disk": {
                    "total_gb": disk_total_gb,
                    "used_gb": disk_used_gb,
                    "free_gb": disk_free_gb,
                    "percent": disk_percent
                }
            }
            
            return metrics
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            # Return a minimal metrics dict
            return {
                "timestamp": int(time.time()),
                "error": str(e)
            }
    
    @staticmethod
    def check_job_resource_usage(job_id: str) -> Dict[str, Any]:
        """
        Check resource usage of a specific job process
        Returns details about process resource consumption
        """
        try:
            # Find process by checking for job ID in command line
            job_process = None
            for proc in psutil.process_iter(['pid', 'cmdline']):
                try:
                    cmdline = proc.info['cmdline']
                    if cmdline and job_id in ' '.join(cmdline):
                        job_process = proc
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            if not job_process:
                return {"error": "Process not found"}
            
            # Get process metrics
            metrics = {
                "pid": job_process.pid,
                "cpu_percent": job_process.cpu_percent(interval=0.5),
                "memory_mb": job_process.memory_info().rss / (1024 ** 2),
                "threads": job_process.num_threads(),
                "running_time": time.time() - job_process.create_time()
            }
            
            # Check if process exceeds limits
            max_cpu = int(get_setting("max_cpu_percent", 80))
            max_memory = int(get_setting("max_memory_mb", 1024))
            
            metrics["exceeds_cpu_limit"] = metrics["cpu_percent"] > max_cpu
            metrics["exceeds_memory_limit"] = metrics["memory_mb"] > max_memory
            
            return metrics
        except Exception as e:
            logger.error(f"Error checking job resource usage: {e}")
            return {"error": str(e)}

    @staticmethod
    def check_ffmpeg_installed() -> bool:
        """Check if ffmpeg is installed and available"""
        try:
            import subprocess
            result = subprocess.run(["ffmpeg", "-version"], 
                                    stdout=subprocess.PIPE, 
                                    stderr=subprocess.PIPE, 
                                    text=True, 
                                    check=False)
            return result.returncode == 0
        except Exception:
            return False
            
    @staticmethod
    def check_available_disk_space(required_mb: int, path: str = "/") -> Dict[str, Any]:
        """
        Check if there's enough disk space available
        Returns dict with space info and whether requirement is met
        """
        try:
            disk = shutil.disk_usage(path)
            free_mb = disk.free / (1024 ** 2)
            
            return {
                "free_mb": free_mb,
                "required_mb": required_mb,
                "has_enough_space": free_mb >= required_mb,
                "percent_used": (disk.used / disk.total) * 100
            }
        except Exception as e:
            logger.error(f"Error checking disk space: {e}")
            return {
                "error": str(e),
                "has_enough_space": False
            }

# Create a singleton instance
system_monitor = SystemMonitor()

def start_system_monitor():
    """Start the system monitoring thread"""
    system_monitor.start()

def stop_system_monitor():
    """Stop the system monitoring thread"""
    system_monitor.stop()

def get_system_info() -> Dict[str, Any]:
    """Get comprehensive system information"""
    try:
        # Get basic metrics
        metrics = system_monitor.get_system_metrics()
        
        # Add Python version
        import platform
        python_version = platform.python_version()
        
        # Add Docker info if available
        docker_info = {}
        try:
            import subprocess
            result = subprocess.run(["docker", "info"], 
                                    stdout=subprocess.PIPE, 
                                    stderr=subprocess.PIPE, 
                                    text=True, 
                                    check=False)
            if result.returncode == 0:
                docker_info["available"] = True
                # Extract some useful info from docker info output
                for line in result.stdout.splitlines():
                    if any(key in line for key in ["Server Version", "Containers", "Images"]):
                        key, value = line.strip().split(":", 1)
                        docker_info[key.strip()] = value.strip()
            else:
                docker_info["available"] = False
        except Exception:
            docker_info["available"] = False
        
        # Check for ffmpeg
        ffmpeg_available = system_monitor.check_ffmpeg_installed()
        
        # Build full system info
        info = {
            "metrics": metrics,
            "python_version": python_version,
            "ffmpeg_available": ffmpeg_available,
            "docker": docker_info,
            "timestamp": int(time.time())
        }
        
        return info
    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        return {"error": str(e)}

# Start the monitor if enabled in settings
if get_setting("system_monitoring_enabled", "true").lower() == "true":
    try:
        start_system_monitor()
    except Exception as e:
        logger.error(f"Error starting system monitor: {e}") 