document.addEventListener('DOMContentLoaded', function() {
  // Elements
  const form = document.getElementById('convert-form');
  const jobsList = document.getElementById('jobs-list');
  const refreshBtn = document.getElementById('refresh-jobs');
  const consoleSection = document.getElementById('console-output');
  const outputContent = document.getElementById('output-content');
  const progressBar = document.getElementById('progress-bar');
  const statusText = document.getElementById('status-text');
  const cancelBtn = document.getElementById('cancel-job');
  const notification = document.getElementById('notification');
  const notificationMessage = document.getElementById('notification-message');
  const notificationClose = document.getElementById('notification-close');
  
  // Current job tracking
  let currentJobId = null;
  let jobPollInterval = null;
  
  // Initialize
  initializeApp();
  
  function initializeApp() {
    // Load user preferences from settings
    loadUserPreferences();
    
    // Set up event listeners
    setupEventListeners();
    
    // Load recent jobs
    loadRecentJobs();
  }
  
  function setupEventListeners() {
    // Form submission
    if (form) {
      form.addEventListener('submit', handleFormSubmit);
    }
    
    // Refresh jobs button
    if (refreshBtn) {
      refreshBtn.addEventListener('click', loadRecentJobs);
    }
    
    // Cancel job button
    if (cancelBtn) {
      cancelBtn.addEventListener('click', cancelCurrentJob);
    }
    
    // Notification close button
    if (notificationClose) {
      notificationClose.addEventListener('click', function() {
        notification.classList.add('hidden');
      });
    }
  }
  
  function loadUserPreferences() {
    // Load settings from server and apply to form
    fetch('/api/settings')
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          const settings = data.settings;
          
          // Set default media type
          const mediaTypeSelect = document.getElementById('media-type');
          if (mediaTypeSelect && settings.default_media_type) {
            mediaTypeSelect.value = settings.default_media_type;
          }
          
          // Set default output format
          const outputFormatSelect = document.getElementById('output-format');
          if (outputFormatSelect && settings.default_output_format) {
            outputFormatSelect.value = settings.default_output_format;
          }
          
          // Set keep original checkbox
          const keepOriginalCheckbox = document.getElementById('keep-original');
          if (keepOriginalCheckbox && settings.keep_original_default === 'true') {
            keepOriginalCheckbox.checked = true;
          }
          
          // Apply theme
          if (settings.ui_theme) {
            document.body.classList.remove('theme-dark', 'theme-light');
            document.body.classList.add('theme-' + settings.ui_theme);
          }
        }
      })
      .catch(error => {
        console.error('Error loading settings:', error);
      });
  }
  
  function handleFormSubmit(e) {
    e.preventDefault();
    
    // Show console output section
    consoleSection.style.display = 'block';
    
    // Reset console
    outputContent.textContent = 'Starting conversion...';
    progressBar.style.width = '0%';
    statusText.textContent = 'Initializing...';
    
    // Get form data
    const formData = new FormData(form);
    
    // Check if file was uploaded
    const fileInput = document.getElementById('file-upload');
    if (fileInput && fileInput.files.length > 0) {
      formData.append('file', fileInput.files[0]);
    }
    
    // Submit form
    fetch('/api/convert', {
      method: 'POST',
      body: formData
    })
    .then(response => {
      if (!response.ok) {
        return response.json().then(data => {
          throw new Error(data.error || 'Server error');
        });
      }
      return response.json();
    })
    .then(data => {
      if (data.success && data.job_id) {
        currentJobId = data.job_id;
        showNotification('Conversion job started successfully', 'success');
        
        // Start polling for job status
        pollJobStatus(data.job_id);
      } else {
        outputContent.textContent = 'Error: ' + (data.error || 'Unknown error');
        statusText.textContent = 'Failed to start job';
        showNotification('Failed to start conversion', 'error');
      }
    })
    .catch(error => {
      outputContent.textContent = 'Error: ' + error.message;
      statusText.textContent = 'Failed to start job';
      showNotification(error.message, 'error');
    });
  }
  
  function pollJobStatus(jobId) {
    // Clear any existing interval
    if (jobPollInterval) {
      clearInterval(jobPollInterval);
    }
    
    // Set up polling
    jobPollInterval = setInterval(() => {
      fetch('/api/job/' + jobId)
        .then(response => response.json())
        .then(data => {
          if (data.success && data.job) {
            updateJobDisplay(data.job);
            
            // If job is no longer running or pending, stop polling
            if (data.job.status !== 'running' && data.job.status !== 'pending') {
              clearInterval(jobPollInterval);
              jobPollInterval = null;
              
              // Refresh job list
              loadRecentJobs();
              
              // Show notification based on status
              if (data.job.status === 'completed') {
                showNotification('Conversion completed successfully', 'success');
              } else if (data.job.status === 'failed') {
                showNotification('Conversion failed: ' + (data.job.error || 'Unknown error'), 'error');
              } else if (data.job.status === 'cancelled') {
                showNotification('Conversion cancelled', 'info');
              }
            }
          } else {
            outputContent.textContent += '\nError fetching job status';
          }
        })
        .catch(error => {
          outputContent.textContent += '\nError: ' + error.message;
          clearInterval(jobPollInterval);
          jobPollInterval = null;
        });
    }, 2000);
  }
  
  function updateJobDisplay(job) {
    // Update console output
    if (job.output && Array.isArray(job.output)) {
      outputContent.textContent = job.output.join('\n');
      // Auto-scroll to bottom
      outputContent.scrollTop = outputContent.scrollHeight;
    }
    
    // Update status
    statusText.textContent = 'Status: ' + job.status;
    
    // Update progress bar based on status
    let progressWidth = '0%';
    if (job.status === 'completed') {
      progressWidth = '100%';
      statusText.textContent = 'Conversion completed successfully';
      // Add download link if available
      if (job.output_file) {
        const downloadPath = '/uploads/' + job.output_file.replace(/^\/complete\/?/, '');
        statusText.innerHTML += ` | <a href="${downloadPath}" target="_blank">Download File</a>`;
      }
    } else if (job.status === 'failed') {
      progressWidth = '100%';
      statusText.textContent = 'Conversion failed: ' + (job.error || 'Unknown error');
    } else if (job.status === 'cancelled') {
      progressWidth = '100%';
      statusText.textContent = 'Conversion cancelled';
    } else if (job.status === 'pending') {
      progressWidth = '10%';
    } else if (job.status === 'running') {
      // Estimate progress based on output
      // This is a rough estimate since we don't have exact progress data
      progressWidth = estimateProgressFromOutput(job.output) + '%';
    }
    
    // Apply progress bar width
    progressBar.style.width = progressWidth;
    
    // Set progress bar color based on status
    progressBar.className = '';
    if (job.status === 'completed') {
      progressBar.classList.add('status-good');
    } else if (job.status === 'failed' || job.status === 'cancelled') {
      progressBar.classList.add('status-danger');
    } else {
      progressBar.classList.add('status-warning');
    }
  }
  
  function estimateProgressFromOutput(output) {
    if (!output || !Array.isArray(output)) return 20;
    
    // Look for progress indicators in the output
    let maxProgress = 20; // Default minimum progress when running
    
    for (const line of output) {
      // Look for percentage indicators
      const percentMatch = line.match(/(\d+)%/);
      if (percentMatch) {
        const percent = parseInt(percentMatch[1], 10);
        if (!isNaN(percent) && percent > maxProgress && percent <= 100) {
          maxProgress = percent;
        }
      }
      
      // Look for download progress
      if (line.includes('Download complete')) {
        maxProgress = Math.max(maxProgress, 50);
      }
      
      // Look for conversion progress
      if (line.includes('Converting')) {
        maxProgress = Math.max(maxProgress, 60);
      }
      
      // Final processing
      if (line.includes('Processing complete')) {
        maxProgress = Math.max(maxProgress, 90);
      }
    }
    
    return maxProgress;
  }
  
  function cancelCurrentJob() {
    if (!currentJobId) {
      showNotification('No active job to cancel', 'error');
      return;
    }
    
    fetch('/api/job/' + currentJobId + '/cancel', {
      method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
      if (data.success) {
        statusText.textContent = 'Cancelling job...';
        showNotification('Job cancellation requested', 'info');
      } else {
        showNotification('Failed to cancel job: ' + (data.error || 'Unknown error'), 'error');
      }
    })
    .catch(error => {
      showNotification('Error cancelling job: ' + error.message, 'error');
    });
  }
  
  function loadRecentJobs() {
    if (!jobsList) return;
    
    jobsList.innerHTML = '<p class="loading">Loading recent jobs...</p>';
    
    fetch('/api/jobs')
      .then(response => response.json())
      .then(data => {
        if (data.success && data.jobs) {
          displayJobs(data.jobs);
        } else {
          jobsList.innerHTML = '<p class="error">Failed to load recent jobs</p>';
        }
      })
      .catch(error => {
        jobsList.innerHTML = '<p class="error">Error: ' + error.message + '</p>';
      });
  }
  
  function displayJobs(jobs) {
    if (!jobsList) return;
    
    if (jobs.length === 0) {
      jobsList.innerHTML = '<p>No jobs found</p>';
      return;
    }
    
    let html = '';
    for (const job of jobs) {
      const jobTime = new Date(job.created_at * 1000).toLocaleString();
      
      html += `
        <div class="job-item ${job.status}">
          <h3>
            ${job.media_source.substring(0, 30)}${job.media_source.length > 30 ? '...' : ''}
            <span class="job-status status-${job.status}">${job.status}</span>
          </h3>
          <p>Type: ${job.media_type} | Format: ${job.output_format}</p>
          <p>Created: ${jobTime}</p>
          <div class="job-actions">
            <a href="/job/${job.id}" class="btn">View Details</a>
            ${job.status === 'failed' || job.status === 'cancelled' ? 
              `<button class="btn" onclick="retryJob('${job.id}')">Retry</button>` : ''}
          </div>
        </div>
      `;
    }
    
    jobsList.innerHTML = html;
  }
  
  function showNotification(message, type = 'info') {
    if (!notification || !notificationMessage) return;
    
    notificationMessage.textContent = message;
    notification.className = 'notification';
    notification.classList.add(type);
    notification.classList.remove('hidden');
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
      notification.classList.add('hidden');
    }, 5000);
  }
  
  // Make retry function globally available
  window.retryJob = function(jobId) {
    fetch('/api/job/' + jobId + '/retry', {
      method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
      if (data.success) {
        showNotification('Job restarted successfully', 'success');
        
        // If we have a new job ID, start polling
        if (data.job_id) {
          currentJobId = data.job_id;
          
          // Show console section
          consoleSection.style.display = 'block';
          outputContent.textContent = 'Restarting job...';
          progressBar.style.width = '0%';
          statusText.textContent = 'Initializing...';
          
          // Start polling for job status
          pollJobStatus(data.job_id);
        }
        
        // Refresh job list
        loadRecentJobs();
      } else {
        showNotification('Failed to restart job: ' + (data.error || 'Unknown error'), 'error');
      }
    })
    .catch(error => {
      showNotification('Error restarting job: ' + error.message, 'error');
    });
  };
}); 