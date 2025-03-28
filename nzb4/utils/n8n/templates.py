"""
HTML templates for n8n setup GUI
"""

# Main setup page template
SETUP_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>n8n Setup</title>
    <style>
        :root {
            --primary-color: #ff6c2f;
            --secondary-color: #6a67ce;
            --background-color: #ffffff;
            --text-color: #333333;
            --border-color: #dddddd;
            --success-color: #4caf50;
            --warning-color: #ff9800;
            --error-color: #f44336;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: var(--text-color);
            background-color: var(--background-color);
            margin: 0;
            padding: 20px;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        h1 {
            color: var(--primary-color);
            margin-top: 0;
            border-bottom: 2px solid var(--border-color);
            padding-bottom: 10px;
        }
        h2 {
            color: var(--secondary-color);
        }
        .status-card {
            background-color: #f9f9f9;
            border-left: 4px solid var(--primary-color);
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 4px;
        }
        .status-success {
            border-left-color: var(--success-color);
        }
        .status-warning {
            border-left-color: var(--warning-color);
        }
        .status-error {
            border-left-color: var(--error-color);
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 500;
        }
        input[type="text"], input[type="number"], select {
            width: 100%;
            padding: 10px;
            border: 1px solid var(--border-color);
            border-radius: 4px;
            font-size: 16px;
        }
        button {
            background-color: var(--primary-color);
            color: white;
            border: none;
            padding: 12px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
            font-weight: 500;
        }
        button:hover {
            background-color: #e55a20;
        }
        .button-secondary {
            background-color: var(--secondary-color);
        }
        .button-secondary:hover {
            background-color: #5552b5;
        }
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }
        .status-on {
            background-color: var(--success-color);
        }
        .status-off {
            background-color: var(--error-color);
        }
        .actions {
            display: flex;
            justify-content: space-between;
            margin-top: 30px;
        }
        .action-button {
            flex: 1;
            margin: 0 10px;
        }
        .action-button:first-child {
            margin-left: 0;
        }
        .action-button:last-child {
            margin-right: 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>n8n Integration Setup</h1>

        <div class="status-card {{status_class}}">
            <h2>Status</h2>
            <p><strong>Installed:</strong> 
                <span class="status-indicator {{installed_class}}"></span>
                {{installed_status}}
            </p>
            <p><strong>Running:</strong> 
                <span class="status-indicator {{running_class}}"></span>
                {{running_status}}
            </p>
            {% if is_installed %}
            <p><strong>Version:</strong> {{version}}</p>
            <p><strong>URL:</strong> <a href="{{url}}" target="_blank">{{url}}</a></p>
            {% endif %}
        </div>

        <form method="post" action="/n8n/setup">
            <div class="form-group">
                <label for="n8n_data_dir">Data Directory:</label>
                <input type="text" id="n8n_data_dir" name="n8n_data_dir" value="{{data_dir}}" required>
            </div>

            <div class="form-group">
                <label for="n8n_port">Port:</label>
                <input type="number" id="n8n_port" name="n8n_port" value="{{port}}" min="1024" max="65535" required>
            </div>

            <div class="form-group">
                <label for="n8n_install_type">Installation Type:</label>
                <select id="n8n_install_type" name="n8n_install_type">
                    <option value="docker" {% if install_type == 'docker' %}selected{% endif %}>Docker (Recommended)</option>
                    <option value="npm" {% if install_type == 'npm' %}selected{% endif %}>npm</option>
                </select>
            </div>

            <div class="actions">
                {% if not is_installed %}
                <button type="submit" name="action" value="install" class="action-button">Install n8n</button>
                {% else %}
                    {% if is_running %}
                    <button type="submit" name="action" value="stop" class="action-button">Stop n8n</button>
                    {% else %}
                    <button type="submit" name="action" value="start" class="action-button">Start n8n</button>
                    {% endif %}
                    <button type="submit" name="action" value="open" class="action-button button-secondary">Open n8n</button>
                    <button type="submit" name="action" value="uninstall" class="action-button" onclick="return confirm('Are you sure you want to uninstall n8n? This will not delete your data.')">Uninstall</button>
                {% endif %}
            </div>
        </form>
    </div>
</body>
</html>
"""

# Processing template (for long-running operations)
PROCESSING_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="3;url={{redirect_url}}">
    <title>Processing...</title>
    <style>
        :root {
            --primary-color: #ff6c2f;
            --background-color: #ffffff;
            --text-color: #333333;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: var(--text-color);
            background-color: var(--background-color);
            margin: 0;
            padding: 20px;
            text-align: center;
        }
        .container {
            max-width: 600px;
            margin: 0 auto;
            padding: 30px;
        }
        h1 {
            color: var(--primary-color);
        }
        .loader {
            border: 5px solid #f3f3f3;
            border-top: 5px solid var(--primary-color);
            border-radius: 50%;
            width: 50px;
            height: 50px;
            animation: spin 2s linear infinite;
            margin: 20px auto;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>{{title}}</h1>
        <div class="loader"></div>
        <p>{{message}}</p>
        <p>Please wait, you will be redirected automatically...</p>
    </div>
</body>
</html>
""" 