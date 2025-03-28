#!/usr/bin/env python3
"""
macOS App Launcher for Universal Media Converter
This script creates a basic macOS app wrapper for the Universal Media Converter
"""

import os
import sys
import subprocess
import webbrowser
import time
import threading
import platform
import shutil
import logging
import tkinter as tk
from tkinter import messagebox, simpledialog

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Ensure we're running on macOS
if platform.system() != "Darwin":
    print("This launcher is only for macOS")
    sys.exit(1)

class MediaConverterApp:
    def __init__(self):
        self.process = None
        self.root = None
        self.status_var = None
        self.server_port = 8000
        self.running = False
        
    def check_dependencies(self):
        """Check if required dependencies are installed"""
        # Check Python version
        if sys.version_info < (3, 7):
            messagebox.showerror("Error", "Python 3.7 or higher is required")
            return False
            
        # Check if pip is available
        try:
            subprocess.run([sys.executable, "-m", "pip", "--version"], 
                           check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError:
            messagebox.showerror("Error", "pip is not installed")
            return False
            
        # Check for required modules
        required_modules = ["flask", "psutil", "requests"]
        missing_modules = []
        
        for module in required_modules:
            try:
                __import__(module)
            except ImportError:
                missing_modules.append(module)
                
        if missing_modules:
            response = messagebox.askyesno(
                "Missing Dependencies",
                f"The following Python modules are missing: {', '.join(missing_modules)}\n\nWould you like to install them now?"
            )
            
            if response:
                try:
                    subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing_modules)
                    messagebox.showinfo("Success", "Dependencies installed successfully")
                except subprocess.CalledProcessError:
                    messagebox.showerror("Error", "Failed to install dependencies")
                    return False
            else:
                return False
        
        return True
    
    def start_server(self):
        """Start the web server in a subprocess"""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        server_script = os.path.join(script_dir, "web_interface.py")
        
        if not os.path.exists(server_script):
            messagebox.showerror("Error", f"Server script not found: {server_script}")
            return False
        
        try:
            # Start server process
            self.process = subprocess.Popen(
                [sys.executable, server_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # Wait for server to start
            for line in iter(self.process.stdout.readline, ''):
                if "Running on" in line:
                    self.running = True
                    # Open web browser
                    webbrowser.open(f"http://localhost:{self.server_port}")
                    break
                    
            if not self.running:
                # Timeout after 30 seconds
                time.sleep(30)
                if self.process.poll() is None:  # Still running
                    self.running = True
                    webbrowser.open(f"http://localhost:{self.server_port}")
                else:
                    messagebox.showerror("Error", "Failed to start server")
                    return False
            
            self.update_status("Server running")
            return True
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start server: {str(e)}")
            logger.error(f"Error starting server: {e}")
            return False
    
    def stop_server(self):
        """Stop the running server"""
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                
        self.running = False
        self.update_status("Server stopped")
    
    def update_status(self, message):
        """Update status in the UI"""
        if self.status_var:
            self.status_var.set(message)
            
    def create_app_interface(self):
        """Create a simple Tkinter interface"""
        self.root = tk.Tk()
        self.root.title("Universal Media Converter")
        self.root.geometry("400x300")
        
        # Set up the main window
        self.root.configure(padx=20, pady=20)
        
        # App title and description
        tk.Label(self.root, text="Universal Media Converter", font=("Helvetica", 16, "bold")).pack(pady=10)
        tk.Label(self.root, text="Convert media from various sources to your preferred format").pack(pady=5)
        
        # Status display
        self.status_var = tk.StringVar(value="Ready")
        status_frame = tk.Frame(self.root)
        status_frame.pack(pady=20, fill=tk.X)
        
        tk.Label(status_frame, text="Status:").pack(side=tk.LEFT, padx=5)
        tk.Label(status_frame, textvariable=self.status_var).pack(side=tk.LEFT, padx=5)
        
        # Buttons
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=10)
        
        start_button = tk.Button(button_frame, text="Start Server", command=self.handle_start)
        start_button.pack(side=tk.LEFT, padx=10)
        
        stop_button = tk.Button(button_frame, text="Stop Server", command=self.stop_server)
        stop_button.pack(side=tk.LEFT, padx=10)
        
        open_button = tk.Button(button_frame, text="Open in Browser", command=self.open_browser)
        open_button.pack(side=tk.LEFT, padx=10)
        
        # Set up close behavior
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
    def handle_start(self):
        """Handle the start button click"""
        if not self.running:
            self.update_status("Starting server...")
            threading.Thread(target=self.start_server, daemon=True).start()
    
    def open_browser(self):
        """Open the web browser to the application"""
        if self.running:
            webbrowser.open(f"http://localhost:{self.server_port}")
        else:
            messagebox.showinfo("Info", "Server is not running. Please start the server first.")
            
    def on_close(self):
        """Handle window close event"""
        if self.running:
            if messagebox.askyesno("Confirm", "Server is still running. Do you want to stop it and exit?"):
                self.stop_server()
                self.root.destroy()
        else:
            self.root.destroy()
    
    def run(self):
        """Main entry point"""
        if not self.check_dependencies():
            return
            
        self.create_app_interface()
        self.root.mainloop()


if __name__ == "__main__":
    app = MediaConverterApp()
    app.run() 