// Main page JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const sourceTypeSelect = document.getElementById('source-type');
    const searchInputGroup = document.getElementById('search-input-group');
    const fileInputGroup = document.getElementById('file-input-group');
    const conversionForm = document.getElementById('conversion-form');
    const mediaSource = document.getElementById('media-source');
    const fileUpload = document.getElementById('file-upload');
    const submitBtn = document.getElementById('submit-btn');
    const loader = document.getElementById('loader');
    const jobsList = document.getElementById('jobs-list');
    
    // Add system status link to header
    const header = document.querySelector('header');
    const systemStatusLink = document.createElement('nav');
    systemStatusLink.innerHTML = '<a href="/status" class="btn">System Status</a>';
    header.appendChild(systemStatusLink);
    
    // Toggle between search and file input
    sourceTypeSelect.addEventListener('change', function() {
        if (this.value === 'search') {
            searchInputGroup.classList.remove('hidden');
            fileInputGroup.classList.add('hidden');
        } else {
            searchInputGroup.classList.add('hidden');
            fileInputGroup.classList.remove('hidden');
        }
    });
    
    // Handle form submission
    conversionForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        // Validate input
        const sourceType = sourceTypeSelect.value;
        
        if (sourceType === 'search' && !mediaSource.value.trim()) {
            alert('Please enter a search term or URL');
            return;
        }
        
        if (sourceType === 'file' && !fileUpload.files.length) {
            alert('Please select a file to upload');
            return;
        }
        
        // Validate file size before uploading
        if (sourceType === 'file' && fileUpload.files[0].size > 50 * 1024 * 1024) { // 50MB
            alert('File is too large. Maximum size is 50MB.');
            return;
        }
        
        // Show loader, hide form
        conversionForm.classList.add('hidden');
        loader.classList.remove('hidden');
        
        // Create form data
        const formData = new FormData();
        formData.append('media_type', document.getElementById('media-type').value);
        formData.append('output_format', document.getElementById('output-format').value);
        formData.append('keep_original', document.getElementById('keep-original').checked);
        
        if (sourceType === 'search') {
            formData.append('media_source', mediaSource.value.trim());
        } else {
            formData.append('file', fileUpload.files[0]);
        }
        
        // Submit form
        fetch('/api/convert', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Redirect to job status page
                window.location.href = `/job/${data.job_id}`;
            } else {
                // Show error
                alert('Error: ' + (data.error || 'Unknown error'));
                // Hide loader, show form
                loader.classList.add('hidden');
                conversionForm.classList.remove('hidden');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Error submitting conversion: ' + error.message);
            // Hide loader, show form
            loader.classList.add('hidden');
            conversionForm.classList.remove('hidden');
        });
    });
    
    // Load recent jobs
    function loadRecentJobs() {
        fetch('/api/jobs')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                renderJobs(data.jobs);
            } else {
                jobsList.innerHTML = '<p class="error">Error loading jobs: ' + (data.error || 'Unknown error') + '</p>';
            }
        })
        .catch(error => {
            console.error('Error:', error);
            jobsList.innerHTML = '<p class="error">Error loading jobs: ' + error.message + '</p>';
        });
    }
    
    // Render jobs list
    function renderJobs(jobs) {
        if (!jobs.length) {
            jobsList.innerHTML = '<p>No jobs yet. Start a conversion to see results.</p>';
            return;
        }
        
        // Only show the 5 most recent jobs on the main page
        const recentJobs = jobs.slice(0, 5);
        
        const jobsHtml = recentJobs.map(job => {
            // Get source name (either media source or filename)
            let source = job.media_source;
            if (source.startsWith('/nzb/') || source.startsWith('/torrents/')) {
                source = source.split('/').pop();
            }
            
            // Format date
            const date = new Date(job.created_at * 1000);
            const dateString = date.toLocaleString();
            
            // Prepare actions based on job status
            let actionButtons = `<a href="/job/${job.id}" class="btn">View Details</a>`;
            
            // Add additional buttons based on status
            if (['running', 'pending'].includes(job.status)) {
                actionButtons += `<button class="btn danger cancel-job" data-id="${job.id}">Cancel</button>`;
            } else if (['failed', 'cancelled'].includes(job.status)) {
                actionButtons += `<button class="btn primary retry-job" data-id="${job.id}">Retry</button>`;
            }
            
            return `
                <div class="job-item ${job.status}">
                    <h3>
                        ${source}
                        <span class="job-status status-${job.status}">${job.status}</span>
                    </h3>
                    <p>Type: ${job.media_type}</p>
                    <p>Started: ${dateString}</p>
                    <div class="job-actions">
                        ${actionButtons}
                    </div>
                </div>
            `;
        }).join('');
        
        jobsList.innerHTML = jobsHtml;
        
        // Add event listeners to action buttons
        document.querySelectorAll('.cancel-job').forEach(button => {
            button.addEventListener('click', function() {
                cancelJob(this.getAttribute('data-id'));
            });
        });
        
        document.querySelectorAll('.retry-job').forEach(button => {
            button.addEventListener('click', function() {
                retryJob(this.getAttribute('data-id'));
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
                // Reload the jobs list
                loadRecentJobs();
            } else {
                alert('Error: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Error cancelling job: ' + error.message);
        });
    }
    
    // Retry a job
    function retryJob(jobId) {
        if (!confirm('Are you sure you want to retry this job?')) {
            return;
        }
        
        fetch(`/api/job/${jobId}/retry`, {
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
    
    // Initial load
    loadRecentJobs();
    
    // Check for jobs in progress and refresh accordingly
    function refreshInterval() {
        fetch('/api/jobs')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Check if there are any running jobs
                const hasRunningJobs = data.jobs.some(job => 
                    job.status === 'running' || job.status === 'pending'
                );
                
                // Refresh more frequently if there are running jobs
                if (hasRunningJobs) {
                    setTimeout(loadRecentJobs, 5000); // 5 seconds
                } else {
                    setTimeout(loadRecentJobs, 30000); // 30 seconds
                }
                
                // Schedule next interval check
                setTimeout(refreshInterval, 30000);
            }
        })
        .catch(error => {
            console.error('Error checking jobs:', error);
            // Retry after 30 seconds on error
            setTimeout(refreshInterval, 30000);
        });
    }
    
    // Start the refresh interval
    refreshInterval();
}); 