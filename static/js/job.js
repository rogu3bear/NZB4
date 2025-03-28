// Job status page JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const jobHeader = document.getElementById('job-header');
    const progressContainer = document.getElementById('progress-container');
    const progressInner = document.getElementById('progress-inner');
    const statusText = document.getElementById('status-text');
    const jobMeta = document.getElementById('job-meta');
    const jobSource = document.getElementById('job-source');
    const jobMediaType = document.getElementById('job-media-type');
    const jobFormat = document.getElementById('job-format');
    const jobStarted = document.getElementById('job-started');
    const jobResult = document.getElementById('job-result');
    const resultMessage = document.getElementById('result-message');
    const downloadSection = document.getElementById('download-section');
    const downloadBtn = document.getElementById('download-btn');
    const outputText = document.getElementById('output-text');
    
    // Status update interval
    let updateInterval;
    let job = null;
    
    // Load job status
    function loadJobStatus() {
        fetch(`/api/job/${JOB_ID}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Update job data
                job = data.job;
                updateJobDisplay();
                
                // If job is complete (or failed or cancelled), stop polling
                if (['completed', 'failed', 'cancelled'].includes(job.status)) {
                    clearInterval(updateInterval);
                }
            } else {
                showError(data.error || 'Job not found');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showError('Error loading job status: ' + error.message);
        });
    }
    
    // Update job display
    function updateJobDisplay() {
        // Show job header with appropriate actions
        if (['running', 'pending'].includes(job.status)) {
            jobHeader.innerHTML = `
                <div class="header-content">
                    <h3>Job #${job.id.substring(0, 8)} - ${job.status.toUpperCase()}</h3>
                    <div class="job-actions">
                        <button id="cancel-btn" class="btn danger">Cancel Job</button>
                    </div>
                </div>
            `;
            
            // Add cancel button event listener
            document.getElementById('cancel-btn').addEventListener('click', cancelJob);
        } else if (['failed', 'cancelled'].includes(job.status)) {
            jobHeader.innerHTML = `
                <div class="header-content">
                    <h3>Job #${job.id.substring(0, 8)} - ${job.status.toUpperCase()}</h3>
                    <div class="job-actions">
                        <button id="retry-btn" class="btn primary">Retry Job</button>
                    </div>
                </div>
            `;
            
            // Add retry button event listener
            document.getElementById('retry-btn').addEventListener('click', retryJob);
        } else {
            jobHeader.innerHTML = `<h3>Job #${job.id.substring(0, 8)} - ${job.status.toUpperCase()}</h3>`;
        }
        
        // Update progress
        updateProgressBar();
        
        // Update metadata
        updateMetadata();
        
        // Update console output
        updateConsoleOutput();
        
        // Show result if completed, failed or cancelled
        updateResultSection();
    }
    
    function updateProgressBar() {
        progressContainer.classList.remove('hidden');
        
        if (job.status === 'running') {
            // Simulate progress based on output lines
            const progress = Math.min(90, (job.output.length / 50) * 100);
            progressInner.style.width = `${progress}%`;
            statusText.textContent = 'Processing...';
        } else if (job.status === 'completed') {
            progressInner.style.width = '100%';
            progressInner.style.backgroundColor = 'var(--success-color)';
            statusText.textContent = 'Completed';
        } else if (job.status === 'failed') {
            progressInner.style.width = '100%';
            progressInner.style.backgroundColor = 'var(--danger-color)';
            statusText.textContent = 'Failed';
        } else if (job.status === 'cancelled') {
            progressInner.style.width = '100%';
            progressInner.style.backgroundColor = 'var(--danger-color)';
            statusText.textContent = 'Cancelled';
        } else if (job.status === 'pending') {
            progressInner.style.width = '10%';
            statusText.textContent = 'Waiting to start...';
        }
    }
    
    function updateMetadata() {
        jobMeta.classList.remove('hidden');
        
        // Get source name (either media source or filename)
        let source = job.media_source;
        if (source.startsWith('/nzb/') || source.startsWith('/torrents/')) {
            source = source.split('/').pop();
        }
        
        jobSource.textContent = source;
        jobMediaType.textContent = job.media_type;
        jobFormat.textContent = job.output_format;
        
        // Format date
        const date = new Date(job.created_at * 1000);
        jobStarted.textContent = date.toLocaleString();
    }
    
    function updateConsoleOutput() {
        outputText.textContent = job.output.join('\n');
        
        // Scroll to bottom of console
        const console = document.querySelector('.console');
        console.scrollTop = console.scrollHeight;
    }
    
    function updateResultSection() {
        if (['completed', 'failed', 'cancelled'].includes(job.status)) {
            jobResult.classList.remove('hidden');
            
            if (job.status === 'completed') {
                resultMessage.textContent = 'Conversion completed successfully.';
                resultMessage.style.color = 'var(--success-color)';
                
                if (job.output_file) {
                    downloadSection.classList.remove('hidden');
                    // Get filename from path
                    const filename = job.output_file.split('/').pop();
                    // Remove previous listeners
                    downloadBtn.replaceWith(downloadBtn.cloneNode(true));
                    // Get the fresh button and add listener
                    const newDownloadBtn = document.getElementById('download-btn');
                    newDownloadBtn.addEventListener('click', function() {
                        window.location.href = `/uploads/${filename}`;
                    });
                }
            } else if (job.status === 'failed') {
                let errorMsg = 'Conversion failed. Check the console output for details.';
                if (job.error) {
                    errorMsg += ` Error: ${job.error}`;
                }
                resultMessage.textContent = errorMsg;
                resultMessage.style.color = 'var(--danger-color)';
            } else if (job.status === 'cancelled') {
                resultMessage.textContent = 'Job was cancelled by user.';
                resultMessage.style.color = 'var(--danger-color)';
            }
        }
    }
    
    // Cancel the current job
    function cancelJob() {
        if (!confirm('Are you sure you want to cancel this job?')) {
            return;
        }
        
        fetch(`/api/job/${JOB_ID}/cancel`, {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Refresh job data
                loadJobStatus();
            } else {
                alert('Error: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Error cancelling job: ' + error.message);
        });
    }
    
    // Retry a failed or cancelled job
    function retryJob() {
        if (!confirm('Are you sure you want to retry this job?')) {
            return;
        }
        
        fetch(`/api/job/${JOB_ID}/retry`, {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Redirect to the new job
                window.location.href = `/job/${data.job_id}`;
            } else {
                alert('Error: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Error retrying job: ' + error.message);
        });
    }
    
    // Show error message
    function showError(message) {
        jobHeader.innerHTML = `<p class="error">${message}</p>`;
        clearInterval(updateInterval);
    }
    
    // Initial load
    loadJobStatus();
    
    // Update every 2 seconds
    updateInterval = setInterval(loadJobStatus, 2000);
}); 