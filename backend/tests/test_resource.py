import pytest
from app.tools.resource import resource_from_args

class TestResourceFromArgs:
    def test_email_read_with_email_id(self):
        assert resource_from_args('email.read', {'email_id': 'inv_001'}) == 'inv_001'
    
    def test_email_send_with_to(self):
        assert resource_from_args('email.send', {'to': 'attacker@evil.com'}) == 'attacker@evil.com'
    
    def test_email_send_with_both_email_id_and_to(self):
        # email_id takes precedence (first match)
        assert resource_from_args('email.send', {'email_id': 'x', 'to': 'y'}) == 'x'
    
    def test_email_send_no_args(self):
        assert resource_from_args('email.send', {}) == 'default'
    
    def test_file_read_with_path(self):
        assert resource_from_args('file.read', {'path': '/home/user/.env'}) == '/home/user/.env'
    
    def test_file_read_secret_with_path(self):
        assert resource_from_args('file.read_secret', {'path': '/home/user/.env'}) == '/home/user/.env'
    
    def test_web_read_with_url(self):
        assert resource_from_args('web.read', {'url': 'https://example.com'}) == 'https://example.com'
    
    def test_shell_execute_with_command(self):
        assert resource_from_args('shell.execute_mock', {'command': 'rm -rf /'}) == 'rm -rf /'
    
    def test_respond_to_user_returns_default(self):
        assert resource_from_args('respond_to_user', {'message': 'hi'}) == 'default'
    
    def test_unknown_tool_returns_default(self):
        assert resource_from_args('unknown.tool', {'foo': 'bar'}) == 'default'
    
    def test_empty_args_returns_default(self):
        assert resource_from_args('email.read', {}) == 'default'
