"""
Unit tests for the Flask API

These tests verify that API endpoints function correctly, validate input properly,
and provide appropriate responses for both successful and error cases.
"""

import json
import unittest
from unittest.mock import patch, MagicMock
import tempfile
import os

# Import the Flask application
from app import app


class TestAPIEndpoints(unittest.TestCase):
    """Test the API endpoints in the Flask application"""

    def setUp(self):
        """Set up the test client and configure app for testing"""
        app.config['TESTING'] = True
        app.config['DEBUG'] = False
        self.client = app.test_client()
        
        # Create temp directories for testing
        self.temp_dir = tempfile.mkdtemp()
        self.output_dir = os.path.join(self.temp_dir, "output")
        self.download_dir = os.path.join(self.temp_dir, "download")
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.download_dir, exist_ok=True)
        
        # Override app config for testing
        app.config['OUTPUT_DIR'] = self.output_dir
        app.config['DOWNLOAD_DIR'] = self.download_dir

    def tearDown(self):
        """Clean up after tests"""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_status_endpoint(self):
        """Test the /status endpoint returns correct information"""
        response = self.client.get('/status')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        # Check that the response contains the expected fields
        self.assertEqual(data['status'], 'operational')
        self.assertIn('version', data)
        self.assertEqual(data['output_dir'], self.output_dir)
        self.assertEqual(data['download_dir'], self.download_dir)

    def test_convert_endpoint_missing_source(self):
        """Test /convert endpoint with missing source_path"""
        response = self.client.post(
            '/convert',
            data=json.dumps({"target_format": "mp4"}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)
        self.assertIn('source_path', data['error'])

    def test_convert_endpoint_invalid_format(self):
        """Test /convert endpoint with invalid target_format"""
        response = self.client.post(
            '/convert',
            data=json.dumps({
                "source_path": "/path/to/file.nzb",
                "target_format": "invalid"
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)
        self.assertIn('target format', data['error'].lower())

    @patch('app.validate_media_source')
    def test_convert_endpoint_invalid_source(self, mock_validate):
        """Test /convert endpoint with invalid source_path"""
        # Mock validation to return invalid
        mock_validate.return_value = (False, "Invalid source path")
        
        response = self.client.post(
            '/convert',
            data=json.dumps({
                "source_path": "/invalid/path",
                "target_format": "mp4"
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)
        self.assertEqual(data['error'], "Invalid source path")

    @patch('app.process_media')
    @patch('app.validate_media_source')
    def test_convert_endpoint_success(self, mock_validate, mock_process):
        """Test /convert endpoint with valid input data"""
        # Mock validation to return valid
        mock_validate.return_value = (True, "Valid source")
        
        # Mock the processing function
        output_path = os.path.join(self.output_dir, "output.mp4")
        mock_process.return_value = output_path
        
        response = self.client.post(
            '/convert',
            data=json.dumps({
                "source_path": "/path/to/valid.nzb",
                "target_format": "mp4"
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        # Check response format
        self.assertIn('message', data)
        self.assertEqual(data['message'], "Conversion successful")
        self.assertIn('output', data)
        self.assertEqual(data['output'], output_path)
        self.assertIn('format', data)
        self.assertEqual(data['format'], "mp4")
        self.assertIn('processing_time', data)

    @patch('app.process_media')
    @patch('app.validate_media_source')
    def test_convert_endpoint_processing_error(self, mock_validate, mock_process):
        """Test /convert endpoint with processing error"""
        # Mock validation to return valid
        mock_validate.return_value = (True, "Valid source")
        
        # Mock the processing function to raise an exception
        mock_process.side_effect = Exception("Processing error")
        
        response = self.client.post(
            '/convert',
            data=json.dumps({
                "source_path": "/path/to/valid.nzb",
                "target_format": "mp4"
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.data)
        
        # Check error response
        self.assertIn('error', data)
        self.assertEqual(data['error'], "An error occurred during conversion")
        self.assertIn('request_id', data)

    def test_convert_endpoint_invalid_json(self):
        """Test /convert endpoint with invalid JSON payload"""
        response = self.client.post(
            '/convert',
            data="This is not JSON",
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)
        self.assertIn('Invalid JSON', data['error'])

    def test_not_found_handler(self):
        """Test 404 Not Found handler"""
        response = self.client.get('/nonexistent-endpoint')
        
        self.assertEqual(response.status_code, 404)
        # Check if Flask default 404 handler works
        self.assertIn(b'Not Found', response.data)

    def test_rate_limiting(self):
        """Test rate limiting on the /convert endpoint"""
        # Make multiple requests to trigger rate limiting
        for _ in range(10):
            self.client.post(
                '/convert',
                data=json.dumps({"source_path": "/path/to/file.nzb"}),
                content_type='application/json'
            )
            
        # The next request should be rate limited
        response = self.client.post(
            '/convert',
            data=json.dumps({"source_path": "/path/to/file.nzb"}),
            content_type='application/json'
        )
        
        # Check for rate limit response
        self.assertEqual(response.status_code, 429)
        data = json.loads(response.data)
        self.assertIn('error', data)
        self.assertIn('Rate limit', data['error'])


if __name__ == '__main__':
    unittest.main() 