"""
Unit tests for validation utilities

These tests verify that validation and sanitization functions work correctly
and handle edge cases appropriately.
"""

import os
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from nzb4.utils.validation import (
    validate_request_data,
    validate_media_source,
    sanitize_path,
    sanitize_filename,
    is_path_traversal,
    validate_output_directory
)


class TestRequestDataValidation(unittest.TestCase):
    """Test validation of API request data"""

    def test_empty_data(self):
        """Test validation with empty data"""
        is_valid, message = validate_request_data({})
        self.assertFalse(is_valid)
        self.assertIn("Empty request data", message)

    def test_missing_source_path(self):
        """Test validation with missing source_path"""
        is_valid, message = validate_request_data({"target_format": "mp4"})
        self.assertFalse(is_valid)
        self.assertIn("Missing required field: source_path", message)

    def test_empty_source_path(self):
        """Test validation with empty source_path"""
        is_valid, message = validate_request_data({"source_path": ""})
        self.assertFalse(is_valid)
        self.assertIn("source_path cannot be empty", message)

    def test_invalid_target_format(self):
        """Test validation with invalid target_format"""
        is_valid, message = validate_request_data({
            "source_path": "/path/to/file.nzb",
            "target_format": "invalid"
        })
        self.assertFalse(is_valid)
        self.assertIn("Invalid target_format", message)

    def test_valid_request(self):
        """Test validation with valid request data"""
        is_valid, message = validate_request_data({
            "source_path": "/path/to/file.nzb",
            "target_format": "mp4"
        })
        self.assertTrue(is_valid)
        self.assertIn("Valid request data", message)


class TestMediaSourceValidation(unittest.TestCase):
    """Test validation of media sources (files, URLs)"""

    def setUp(self):
        """Set up temporary files for testing"""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create a valid media file
        self.valid_media_file = os.path.join(self.temp_dir, "valid.mp4")
        with open(self.valid_media_file, "w") as f:
            f.write("test content")
        
        # Create a non-media file
        self.invalid_media_file = os.path.join(self.temp_dir, "invalid.txt")
        with open(self.invalid_media_file, "w") as f:
            f.write("test content")

    def tearDown(self):
        """Clean up temporary files"""
        shutil.rmtree(self.temp_dir)

    def test_empty_source(self):
        """Test validation with empty source"""
        is_valid, message = validate_media_source("")
        self.assertFalse(is_valid)
        self.assertIn("Media source cannot be empty", message)

    def test_valid_url(self):
        """Test validation with valid URL"""
        is_valid, message = validate_media_source("https://example.com/file.mp4")
        self.assertTrue(is_valid)
        self.assertIn("Valid URL", message)

    def test_invalid_url(self):
        """Test validation with invalid URL"""
        is_valid, message = validate_media_source("http://")
        self.assertFalse(is_valid)
        self.assertIn("Invalid URL format", message)

    def test_unsupported_url_scheme(self):
        """Test validation with unsupported URL scheme"""
        is_valid, message = validate_media_source("ftp2://example.com/file.mp4")
        self.assertFalse(is_valid)
        self.assertIn("Invalid URL format", message)

    @patch('os.path.isfile')
    @patch('os.access')
    def test_valid_file_path(self, mock_access, mock_isfile):
        """Test validation with valid file path"""
        # Mock file checks
        mock_isfile.return_value = True
        mock_access.return_value = True
        
        is_valid, message = validate_media_source(self.valid_media_file)
        self.assertTrue(is_valid)
        self.assertIn("Valid file path", message)

    def test_nonexistent_file(self):
        """Test validation with nonexistent file"""
        is_valid, message = validate_media_source("/path/to/nonexistent.mp4")
        self.assertFalse(is_valid)
        self.assertIn("Source not found", message)

    def test_search_term(self):
        """Test validation with search term"""
        is_valid, message = validate_media_source("movie title 2023")
        self.assertTrue(is_valid)
        self.assertIn("Valid search term", message)


class TestPathSanitization(unittest.TestCase):
    """Test path and filename sanitization functions"""

    def test_sanitize_path_empty(self):
        """Test sanitizing an empty path"""
        self.assertEqual(sanitize_path(""), "")

    def test_sanitize_path_normal(self):
        """Test sanitizing a normal path"""
        sanitized = sanitize_path("/path/to/file.mp4")
        self.assertEqual(sanitized, "file_mp4")

    def test_sanitize_path_special_chars(self):
        """Test sanitizing a path with special characters"""
        sanitized = sanitize_path("/path/to/file with spaces & symbols!.mp4")
        self.assertEqual(sanitized, "file_with_spaces___symbols__mp4")

    def test_sanitize_filename_empty(self):
        """Test sanitizing an empty filename"""
        self.assertEqual(sanitize_filename(""), "")

    def test_sanitize_filename_normal(self):
        """Test sanitizing a normal filename"""
        sanitized = sanitize_filename("file.mp4")
        self.assertEqual(sanitized, "file.mp4")

    def test_sanitize_filename_special_chars(self):
        """Test sanitizing a filename with special characters"""
        sanitized = sanitize_filename("file with spaces & symbols!.mp4")
        self.assertEqual(sanitized, "file_with_spaces___symbols_.mp4")

    def test_path_traversal_detection(self):
        """Test path traversal detection"""
        self.assertTrue(is_path_traversal("../../../etc/passwd"))
        self.assertTrue(is_path_traversal("folder/../../file.txt"))
        self.assertFalse(is_path_traversal("/normal/path/file.txt"))


class TestOutputDirectoryValidation(unittest.TestCase):
    """Test output directory validation"""

    def setUp(self):
        """Set up temporary directory"""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create subdirectory with the correct permissions
        self.writable_dir = os.path.join(self.temp_dir, "writable")
        os.makedirs(self.writable_dir)
        
        # Create a file (not a directory)
        self.file_path = os.path.join(self.temp_dir, "file.txt")
        with open(self.file_path, "w") as f:
            f.write("test content")

    def tearDown(self):
        """Clean up temporary directory"""
        shutil.rmtree(self.temp_dir)

    def test_valid_existing_directory(self):
        """Test validation with existing directory"""
        is_valid, message = validate_output_directory(self.writable_dir)
        self.assertTrue(is_valid)
        self.assertIn("Valid output directory", message)

    def test_nonexistent_directory_creation(self):
        """Test validation with nonexistent directory (should create it)"""
        new_dir = os.path.join(self.temp_dir, "new_directory")
        is_valid, message = validate_output_directory(new_dir)
        self.assertTrue(is_valid)
        self.assertIn("Valid output directory", message)
        self.assertTrue(os.path.exists(new_dir))

    def test_file_not_directory(self):
        """Test validation with a file path (not a directory)"""
        is_valid, message = validate_output_directory(self.file_path)
        self.assertFalse(is_valid)
        self.assertIn("Path exists but is not a directory", message)

    @patch('os.access')
    def test_non_writable_directory(self, mock_access):
        """Test validation with non-writable directory"""
        # Mock access check to return False for write permission
        mock_access.return_value = False
        
        is_valid, message = validate_output_directory(self.writable_dir)
        self.assertFalse(is_valid)
        self.assertIn("Directory is not writable", message)


if __name__ == '__main__':
    unittest.main() 