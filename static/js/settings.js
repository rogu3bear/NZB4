document.addEventListener('DOMContentLoaded', function() {
    // Initialize UI components
    initNotifications();
    loadSettings();
    setupEventListeners();
});

// Notification handling
function initNotifications() {
    const notification = document.getElementById('notification');
    const notificationMessage = document.getElementById('notification-message');
    const notificationClose = document.getElementById('notification-close');
    
    if (notificationClose) {
        notificationClose.addEventListener('click', function() {
            notification.classList.add('hidden');
        });
    }
}

function showNotification(message, type = 'info') {
    const notification = document.getElementById('notification');
    const notificationMessage = document.getElementById('notification-message');
    
    if (notification && notificationMessage) {
        notificationMessage.textContent = message;
        notification.className = 'notification';
        notification.classList.add(type);
        notification.classList.remove('hidden');
        
        // Auto-hide after 5 seconds
        setTimeout(function() {
            notification.classList.add('hidden');
        }, 5000);
    }
}

// Load settings from server
function loadSettings() {
    fetch('/api/settings')
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to load settings');
            }
            return response.json();
        })
        .then(data => {
            populateSettingsForm(data);
        })
        .catch(error => {
            showNotification('Error loading settings: ' + error.message, 'error');
        });
}

// Populate settings form with data from server
function populateSettingsForm(settings) {
    // General settings
    setValue('maintenance_interval_hours', settings.maintenance_interval_hours || 24);
    setValue('job_retention_days', settings.job_retention_days || 30);
    setValue('max_cpu_percent', settings.max_cpu_percent || 80);
    setValue('max_memory_mb', settings.max_memory_mb || 1024);
    
    // Media output settings
    setValue('default_output_format', settings.default_output_format || 'mp4');
    setValue('video_quality', settings.video_quality || 'high');
    setValue('default_media_type', settings.default_media_type || 'movie');
    setCheckbox('keep_original_default', settings.keep_original_default === 'true');
    setValue('concurrent_conversions', settings.concurrent_conversions || 2);

    // Storage settings
    setValue('movies_output_dir', settings.movies_output_dir || '/complete/movies');
    setValue('tv_output_dir', settings.tv_output_dir || '/complete/tv');
    setValue('music_output_dir', settings.music_output_dir || '/complete/music');
    setValue('min_disk_space_mb', settings.min_disk_space_mb || 500);
    setCheckbox('auto_cleanup_temp', settings.auto_cleanup_temp === 'true');

    // Network settings
    setValue('download_speed_limit_kb', settings.download_speed_limit_kb || 0);
    setValue('max_connections', settings.max_connections || 10);
    setValue('retry_attempts', settings.retry_attempts || 3);
    setValue('connection_timeout', settings.connection_timeout || 30);
    setValue('proxy_url', settings.proxy_url || '');

    // UI settings
    setValue('ui_theme', settings.ui_theme || 'dark');
    setValue('jobs_per_page', settings.jobs_per_page || 20);
    setValue('default_view', settings.default_view || 'active');
    
    // Notification settings
    setCheckbox('notifications_enabled', settings.notifications_enabled === 'true');
    
    // Notification types
    const notificationTypes = (settings.notification_types || '').split(',');
    document.querySelectorAll('input[name="notification_types"]').forEach(checkbox => {
        checkbox.checked = notificationTypes.includes(checkbox.value);
    });
    
    // Email settings
    setCheckbox('email_notifications_enabled', settings.email_notifications_enabled === 'true');
    setValue('smtp_server', settings.smtp_server || '');
    setValue('smtp_port', settings.smtp_port || 587);
    setValue('smtp_username', settings.smtp_username || '');
    setValue('smtp_password', settings.smtp_password || '');
    setValue('notification_from_email', settings.notification_from_email || '');
    setValue('email_recipients', settings.email_recipients || '');
    
    // Webhook settings
    setCheckbox('webhook_notifications_enabled', settings.webhook_notifications_enabled === 'true');
    setValue('webhook_url', settings.webhook_url || '');
    setValue('webhook_headers', settings.webhook_headers || '{\n  "Content-Type": "application/json"\n}');
    setValue('webhook_payload_template', settings.webhook_payload_template || '{\n  "text": "{message}",\n  "type": "{notification_type}",\n  "job": "{id}"\n}');

    // Apply theme immediately if set
    if (settings.ui_theme) {
        applyTheme(settings.ui_theme);
    }
}

// Apply theme
function applyTheme(theme) {
    const bodyEl = document.body;
    bodyEl.classList.remove('theme-dark', 'theme-light');
    
    if (theme === 'system') {
        // Check system preference
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
            bodyEl.classList.add('theme-dark');
        } else {
            bodyEl.classList.add('theme-light');
        }
    } else {
        bodyEl.classList.add('theme-' + theme);
    }
}

// Helper functions for form manipulation
function setValue(id, value) {
    const element = document.getElementById(id);
    if (element) {
        element.value = value;
    }
}

function setCheckbox(id, checked) {
    const element = document.getElementById(id);
    if (element) {
        element.checked = checked;
    }
}

// Set up event listeners for all buttons
function setupEventListeners() {
    // General settings save button
    const saveGeneralBtn = document.getElementById('save-general-settings');
    if (saveGeneralBtn) {
        saveGeneralBtn.addEventListener('click', saveGeneralSettings);
    }
    
    // Run maintenance button
    const runMaintenanceBtn = document.getElementById('run-maintenance');
    if (runMaintenanceBtn) {
        runMaintenanceBtn.addEventListener('click', runMaintenance);
    }
    
    // Media settings save button
    const saveMediaBtn = document.getElementById('save-media-settings');
    if (saveMediaBtn) {
        saveMediaBtn.addEventListener('click', saveMediaSettings);
    }
    
    // Storage settings save button
    const saveStorageBtn = document.getElementById('save-storage-settings');
    if (saveStorageBtn) {
        saveStorageBtn.addEventListener('click', saveStorageSettings);
    }
    
    // Network settings save button
    const saveNetworkBtn = document.getElementById('save-network-settings');
    if (saveNetworkBtn) {
        saveNetworkBtn.addEventListener('click', saveNetworkSettings);
    }
    
    // UI settings save button
    const saveUIBtn = document.getElementById('save-ui-settings');
    if (saveUIBtn) {
        saveUIBtn.addEventListener('click', saveUISettings);
    }
    
    // Notification settings save button
    const saveNotificationBtn = document.getElementById('save-notification-settings');
    if (saveNotificationBtn) {
        saveNotificationBtn.addEventListener('click', saveNotificationSettings);
    }
    
    // Email settings save button
    const saveEmailBtn = document.getElementById('save-email-settings');
    if (saveEmailBtn) {
        saveEmailBtn.addEventListener('click', saveEmailSettings);
    }
    
    // Test email button
    const testEmailBtn = document.getElementById('test-email');
    if (testEmailBtn) {
        testEmailBtn.addEventListener('click', testEmailNotification);
    }
    
    // Webhook settings save button
    const saveWebhookBtn = document.getElementById('save-webhook-settings');
    if (saveWebhookBtn) {
        saveWebhookBtn.addEventListener('click', saveWebhookSettings);
    }
    
    // Test webhook button
    const testWebhookBtn = document.getElementById('test-webhook');
    if (testWebhookBtn) {
        testWebhookBtn.addEventListener('click', testWebhookNotification);
    }
    
    // Theme change listener
    const themeSelect = document.getElementById('ui_theme');
    if (themeSelect) {
        themeSelect.addEventListener('change', function() {
            applyTheme(this.value);
        });
    }
}

// Save general settings
function saveGeneralSettings() {
    const settings = {
        maintenance_interval_hours: document.getElementById('maintenance_interval_hours').value,
        job_retention_days: document.getElementById('job_retention_days').value,
        max_cpu_percent: document.getElementById('max_cpu_percent').value,
        max_memory_mb: document.getElementById('max_memory_mb').value
    };
    
    saveSettings(settings, 'General settings saved successfully.');
}

// Save media output settings
function saveMediaSettings() {
    const settings = {
        default_output_format: document.getElementById('default_output_format').value,
        video_quality: document.getElementById('video_quality').value,
        default_media_type: document.getElementById('default_media_type').value,
        keep_original_default: document.getElementById('keep_original_default').checked,
        concurrent_conversions: document.getElementById('concurrent_conversions').value
    };
    
    saveSettings(settings, 'Media output settings saved successfully.');
}

// Save storage settings
function saveStorageSettings() {
    const settings = {
        movies_output_dir: document.getElementById('movies_output_dir').value,
        tv_output_dir: document.getElementById('tv_output_dir').value,
        music_output_dir: document.getElementById('music_output_dir').value,
        min_disk_space_mb: document.getElementById('min_disk_space_mb').value,
        auto_cleanup_temp: document.getElementById('auto_cleanup_temp').checked
    };
    
    saveSettings(settings, 'Storage settings saved successfully.');
}

// Save network settings
function saveNetworkSettings() {
    const settings = {
        download_speed_limit_kb: document.getElementById('download_speed_limit_kb').value,
        max_connections: document.getElementById('max_connections').value,
        retry_attempts: document.getElementById('retry_attempts').value,
        connection_timeout: document.getElementById('connection_timeout').value,
        proxy_url: document.getElementById('proxy_url').value
    };
    
    saveSettings(settings, 'Network settings saved successfully.');
}

// Save UI settings
function saveUISettings() {
    const settings = {
        ui_theme: document.getElementById('ui_theme').value,
        jobs_per_page: document.getElementById('jobs_per_page').value,
        default_view: document.getElementById('default_view').value
    };
    
    // Apply theme immediately
    applyTheme(settings.ui_theme);
    
    saveSettings(settings, 'UI settings saved successfully.');
}

// Save notification settings
function saveNotificationSettings() {
    // Get notification types that are checked
    const notificationTypes = [];
    document.querySelectorAll('input[name="notification_types"]:checked').forEach(checkbox => {
        notificationTypes.push(checkbox.value);
    });
    
    const settings = {
        notifications_enabled: document.getElementById('notifications_enabled').checked,
        notification_types: notificationTypes.join(',')
    };
    
    saveSettings(settings, 'Notification settings saved successfully.');
}

// Save email settings
function saveEmailSettings() {
    const settings = {
        email_notifications_enabled: document.getElementById('email_notifications_enabled').checked,
        smtp_server: document.getElementById('smtp_server').value,
        smtp_port: document.getElementById('smtp_port').value,
        smtp_username: document.getElementById('smtp_username').value,
        smtp_password: document.getElementById('smtp_password').value,
        notification_from_email: document.getElementById('notification_from_email').value,
        email_recipients: document.getElementById('email_recipients').value
    };
    
    saveSettings(settings, 'Email settings saved successfully.');
}

// Save webhook settings
function saveWebhookSettings() {
    const settings = {
        webhook_notifications_enabled: document.getElementById('webhook_notifications_enabled').checked,
        webhook_url: document.getElementById('webhook_url').value,
        webhook_headers: document.getElementById('webhook_headers').value,
        webhook_payload_template: document.getElementById('webhook_payload_template').value
    };
    
    saveSettings(settings, 'Webhook settings saved successfully.');
}

// Common function to save settings to the server
function saveSettings(settings, successMessage) {
    fetch('/api/settings', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(settings)
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Failed to save settings');
        }
        return response.json();
    })
    .then(data => {
        showNotification(successMessage, 'success');
    })
    .catch(error => {
        showNotification('Error saving settings: ' + error.message, 'error');
    });
}

// Run maintenance
function runMaintenance() {
    fetch('/api/maintenance', {
        method: 'POST'
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Failed to run maintenance');
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            showNotification(`Maintenance completed. ${data.jobs_cleaned} jobs cleaned. (${data.elapsed_seconds}s)`, 'success');
        } else {
            showNotification('Maintenance failed: ' + (data.errors ? data.errors.join(', ') : 'Unknown error'), 'error');
        }
    })
    .catch(error => {
        showNotification('Error running maintenance: ' + error.message, 'error');
    });
}

// Test email notification
function testEmailNotification() {
    fetch('/api/test/email', {
        method: 'POST'
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Failed to send test email');
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            showNotification('Test email sent successfully.', 'success');
        } else {
            showNotification('Failed to send test email: ' + data.error, 'error');
        }
    })
    .catch(error => {
        showNotification('Error sending test email: ' + error.message, 'error');
    });
}

// Test webhook notification
function testWebhookNotification() {
    fetch('/api/test/webhook', {
        method: 'POST'
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Failed to send test webhook');
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            showNotification('Test webhook sent successfully.', 'success');
        } else {
            showNotification('Failed to send test webhook: ' + data.error, 'error');
        }
    })
    .catch(error => {
        showNotification('Error sending test webhook: ' + error.message, 'error');
    });
} 