// System status page JavaScript

document.addEventListener('DOMContentLoaded', function() {
    const systemStatus = document.getElementById('system-status');
    const diskStatus = document.getElementById('disk-status');
    const jobStats = document.getElementById('job-stats');
    const jobList = document.getElementById('job-list');
    
    // Load system status
    function loadStatus() {
        fetch('/api/status')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                updateSystemStatus(data.status);
                updateDiskStatus(data.status.disk);
                updateJobStats(data.status.jobs);
            } else {
                showError('Error loading system status');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showError('Error loading system status: ' + error.message);
        });
    }
    
    // Load job list
    function loadJobs() {
        fetch('/api/jobs')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                updateJobList(data.jobs);
            } else {
                jobList.innerHTML = '<p class="error">Error loading jobs</p>';
            }
        })
        .catch(error => {
            console.error('Error:', error);
            jobList.innerHTML = '<p class="error">Error loading jobs: ' + error.message + '</p>';
        });
    }
    
    // Update system status
    function updateSystemStatus(status) {
        const cpuStatus = getStatusClass(status.system.cpu_percent, 70, 90);
        const memoryStatus = getStatusClass(status.system.memory_percent, 70, 90);
        
        let html = `
            <div class="status-row">
                <div class="status-label">CPU Usage:</div>
                <div class="status-value ${cpuStatus}">
                    ${status.system.cpu_percent.toFixed(1)}%
                </div>
            </div>
            <div class="status-row">
                <div class="status-label">Memory Usage:</div>
                <div class="status-value ${memoryStatus}">
                    ${status.system.memory_percent.toFixed(1)}%
                </div>
            </div>
            <div class="status-row">
                <div class="status-label">System Time:</div>
                <div class="status-value">
                    ${status.system.time}
                </div>
            </div>
        `;
        
        systemStatus.innerHTML = html;
    }
    
    // Update disk status
    function updateDiskStatus(disk) {
        const diskStatus = getStatusClass(disk.used_percent, 70, 90);
        
        let html = `
            <div class="disk-usage">
                <div class="disk-bar">
                    <div class="disk-bar-fill ${diskStatus}" style="width: ${Math.min(100, disk.used_percent)}%"></div>
                </div>
                <div class="disk-info">
                    <span class="disk-percent ${diskStatus}">${disk.used_percent.toFixed(1)}%</span>
                    <span class="disk-details">
                        ${formatSize(disk.free_mb)} free of ${formatSize(disk.total_mb)}
                    </span>
                </div>
            </div>
        `;
        
        diskStatus.innerHTML = html;
    }
    
    // Update job statistics
    function updateJobStats(jobData) {
        let html = `
            <div class="stats-container">
                <div class="stat-box">
                    <div class="stat-value">${jobData.total}</div>
                    <div class="stat-label">Total Jobs</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value running">${jobData.running}</div>
                    <div class="stat-label">Running</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value pending">${jobData.pending}</div>
                    <div class="stat-label">Pending</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value completed">${jobData.completed}</div>
                    <div class="stat-label">Completed</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value failed">${jobData.failed}</div>
                    <div class="stat-label">Failed</div>
                </div>
            </div>
        `;
        
        jobStats.innerHTML = html;
    }
    
    // Update job list
    function updateJobList(jobs) {
        // Filter for active jobs (running and pending)
        const activeJobs = jobs.filter(job => ['running', 'pending'].includes(job.status));
        
        if (activeJobs.length === 0) {
            jobList.innerHTML = '<p>No active jobs</p>';
            return;
        }
        
        const jobsHtml = activeJobs.map(job => {
            let source = job.media_source;
            if (source.startsWith('/nzb/') || source.startsWith('/torrents/')) {
                source = source.split('/').pop();
            }
            
            // Format date
            const date = new Date(job.created_at * 1000);
            const dateString = date.toLocaleString();
            
            return `
                <div class="job-item ${job.status}">
                    <h3>
                        ${source}
                        <span class="job-status status-${job.status}">${job.status}</span>
                    </h3>
                    <p>Type: ${job.media_type}</p>
                    <p>Started: ${dateString}</p>
                    <div class="job-actions">
                        <a href="/job/${job.id}" class="btn">View Details</a>
                        <button class="btn cancel-job" data-id="${job.id}">Cancel</button>
                    </div>
                </div>
            `;
        }).join('');
        
        jobList.innerHTML = jobsHtml;
        
        // Add event listeners to cancel buttons
        document.querySelectorAll('.cancel-job').forEach(button => {
            button.addEventListener('click', function() {
                const jobId = this.getAttribute('data-id');
                cancelJob(jobId);
            });
        });
    }
    
    // Cancel a job
    function cancelJob(jobId) {
        if (!confirm('Are you sure you want to cancel this job?')) {
            return;
        }
        
        fetch(`/api/job/${jobId}/cancel`, {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                loadStatus();
                loadJobs();
            } else {
                alert('Error: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Error cancelling job: ' + error.message);
        });
    }
    
    // Helper function to get status class based on value
    function getStatusClass(value, warningThreshold, dangerThreshold) {
        if (value >= dangerThreshold) {
            return 'status-danger';
        } else if (value >= warningThreshold) {
            return 'status-warning';
        }
        return 'status-good';
    }
    
    // Helper function to format size
    function formatSize(mb) {
        if (mb < 1024) {
            return mb.toFixed(0) + ' MB';
        } else {
            return (mb / 1024).toFixed(2) + ' GB';
        }
    }
    
    // Show error message
    function showError(message) {
        systemStatus.innerHTML = `<p class="error">${message}</p>`;
        diskStatus.innerHTML = `<p class="error">${message}</p>`;
        jobStats.innerHTML = `<p class="error">${message}</p>`;
    }
    
    // Initial load
    loadStatus();
    loadJobs();
    
    // Refresh every 10 seconds
    setInterval(() => {
        loadStatus();
        loadJobs();
    }, 10000);
}); 