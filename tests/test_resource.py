import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from cloudmesh.ai.command.resource import resource_group

@pytest.fixture
def runner():
    return CliRunner()

def test_status_command_success(runner):
    """Test that 'status' command fetches data and prints a report."""
    with patch("cloudmesh.ai.command.resource.fetch_remote_data") as mock_fetch, \
         patch("cloudmesh.ai.command.resource.format_report") as mock_format:
        
        mock_fetch.return_value = "mocked raw data"
        mock_format.return_value = "Mocked Slurm Report"
        
        result = runner.invoke(resource_group, ["status", "--node", "test-node"])
        
        assert result.exit_code == 0
        assert "Mocked Slurm Report" in result.output
        mock_fetch.assert_called_once_with(node="test-node", host="uva", debug=False)

def test_status_command_ssh_failure(runner):
    """Test that 'status' command handles SSH failures."""
    with patch("cloudmesh.ai.command.resource.fetch_remote_data") as mock_fetch:
        # Simulate an SSH connection error
        mock_fetch.side_effect = Exception("SSH Connection Timeout")
        
        result = runner.invoke(resource_group, ["status", "--node", "bad-node"])
        
        # Since status_cmd calls sys.exit(1) on exception
        assert result.exit_code != 0

def test_status_command_watch_mode(runner):
    """Test that 'status' command in watch mode runs and can be stopped."""
    with patch("cloudmesh.ai.command.resource.fetch_remote_data") as mock_fetch, \
         patch("cloudmesh.ai.command.resource.format_report") as mock_format, \
         patch("time.sleep", side_effect=KeyboardInterrupt):
        
        mock_fetch.return_value = "mocked raw data"
        mock_format.return_value = "Mocked Slurm Report"
        
        # Use --watch. The mock time.sleep will raise KeyboardInterrupt to break the loop.
        result = runner.invoke(resource_group, ["status", "--watch", "--interval", "0.1"])
        
        assert "Exiting watch mode" in result.output
        assert mock_fetch.called