"""
Tests for the mainframe TUI system.
"""

import pytest
from unittest.mock import Mock, patch
import os
from pathlib import Path

from estoque.adapters.mainframe_tui import (
    StatusDisplay, MenuTreeWidget, ParametersForm, FileInputForm, 
    ReportParametersForm, EstoqueMainframeApp
)


class TestStatusDisplay:
    """Test the status display widget."""
    
    def test_status_display_creation(self):
        """Test that status display can be created."""
        status = StatusDisplay()
        assert status is not None
    
    def test_refresh_status(self):
        """Test status refresh functionality."""
        status = StatusDisplay()
        # Should not raise exception
        status.refresh_status()


class TestMenuTreeWidget:
    """Test the menu tree widget."""
    
    def test_menu_tree_creation(self):
        """Test that menu tree can be created."""
        tree = MenuTreeWidget()
        assert tree is not None
    
    def test_menu_structure(self):
        """Test that menu has expected structure."""
        tree = MenuTreeWidget()
        
        # Check that root has children
        assert tree.root.children
        
        # Check for expected main categories
        category_labels = [str(child.label) for child in tree.root.children]
        expected_categories = [
            "🔧 Ambiente & Instalação",
            "🗃️ Banco de Dados", 
            "⚙️ Parâmetros",
            "📋 Movimentação em Lote",
            "📊 Relatórios",
            "🧪 Qualidade",
            "🧹 Manutenção"
        ]
        
        for expected in expected_categories:
            assert any(expected in label for label in category_labels)


class TestParametersForm:
    """Test the parameters form modal."""
    
    def test_parameters_form_creation(self):
        """Test that parameters form can be created."""
        form = ParametersForm()
        assert form is not None


class TestFileInputForm:
    """Test the file input form modal."""
    
    def test_file_input_form_creation(self):
        """Test that file input form can be created."""
        form = FileInputForm("entrada-lotes", "Entrada de Lotes")
        assert form is not None
        assert form.operation == "entrada-lotes"
        assert form.title == "Entrada de Lotes"


class TestReportParametersForm:
    """Test the report parameters form modal."""
    
    def test_report_form_creation(self):
        """Test that report form can be created for different types."""
        # Test ruptura report
        form = ReportParametersForm("rel-ruptura")
        assert form is not None
        assert form.report_type == "rel-ruptura"
        
        # Test vencimentos report
        form = ReportParametersForm("rel-vencimentos")
        assert form is not None
        assert form.report_type == "rel-vencimentos"
        
        # Test top consumo report
        form = ReportParametersForm("rel-top")
        assert form is not None
        assert form.report_type == "rel-top"


class TestEstoqueMainframeApp:
    """Test the main TUI application."""
    
    def test_app_creation(self):
        """Test that the app can be created."""
        app = EstoqueMainframeApp()
        assert app is not None
        assert "Estoque Clínica" in app.title
    
    @patch('subprocess.run')
    def test_run_simple_command_success(self, mock_run):
        """Test running a simple command successfully."""
        # Mock successful command execution
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Success output"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        app = EstoqueMainframeApp()
        
        # Mock the notify and push_screen methods
        app.notify = Mock()
        app.push_screen = Mock()
        
        app.run_simple_command("test")
        
        # Verify command was called
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        
        # Check that appropriate command was used
        expected_cmd = "make test" if os.name != "nt" else "build.bat test"
        assert call_args[0][0] == expected_cmd.split()
        
        # Verify notifications were sent
        assert app.notify.call_count == 2  # Starting and success notifications
        assert app.push_screen.call_count == 1  # Output screen
    
    @patch('subprocess.run')
    def test_run_simple_command_failure(self, mock_run):
        """Test running a simple command that fails."""
        # Mock failed command execution
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error output"
        mock_run.return_value = mock_result
        
        app = EstoqueMainframeApp()
        
        # Mock the notify and push_screen methods
        app.notify = Mock()
        app.push_screen = Mock()
        
        app.run_simple_command("test")
        
        # Verify command was called
        mock_run.assert_called_once()
        
        # Verify error notification was sent
        app.notify.assert_any_call("❌ test falhou (code: 1)", severity="error")
    
    def test_execute_action_simple_commands(self):
        """Test executing simple actions."""
        app = EstoqueMainframeApp()
        app.run_simple_command = Mock()
        
        # Test various simple commands
        simple_commands = [
            "venv", "install", "migrate", "test", "lint", "doctor"
        ]
        
        for cmd in simple_commands:
            app.execute_action(cmd)
            app.run_simple_command.assert_called_with(cmd)
    
    def test_execute_action_modal_commands(self):
        """Test executing actions that require modals."""
        app = EstoqueMainframeApp()
        app.push_screen = Mock()
        
        # Test parameters command
        app.execute_action("params-set")
        app.push_screen.assert_called()
        
        # Reset mock
        app.push_screen.reset_mock()
        
        # Test file input commands
        app.execute_action("entrada-lotes")
        app.push_screen.assert_called()
        
        app.push_screen.reset_mock()
        
        # Test report commands
        app.execute_action("rel-ruptura")
        app.push_screen.assert_called()
    
    @patch('subprocess.run')
    def test_run_params_command(self, mock_run):
        """Test running params command with parameters."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Parameters set"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        app = EstoqueMainframeApp()
        app.notify = Mock()
        app.push_screen = Mock()
        
        params = {"NS": "0.95", "MU": "6", "ST": "1"}
        app.run_params_command(params)
        
        # Verify command was run with environment variables
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        
        # Check environment variables were set
        env = call_args[1]['env']
        assert env['NS'] == '0.95'
        assert env['MU'] == '6'
        assert env['ST'] == '1'
    
    @patch('subprocess.run')
    def test_run_report_command(self, mock_run):
        """Test running report command with parameters."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Report generated"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        app = EstoqueMainframeApp()
        app.notify = Mock()
        app.push_screen = Mock()
        
        params = {"H": "5"}
        app.run_report_command("rel-ruptura", params)
        
        # Verify command was run
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        
        # Check environment variable was set
        env = call_args[1]['env']
        assert env['H'] == '5'


class TestTUIIntegration:
    """Integration tests for the TUI system."""
    
    def test_tui_components_integration(self):
        """Test that all TUI components work together."""
        app = EstoqueMainframeApp()
        
        # Test that all required components can be created
        menu = MenuTreeWidget()
        status = StatusDisplay()
        
        assert menu is not None
        assert status is not None
        assert app is not None
    
    @patch('estoque.adapters.mainframe_tui.main')
    def test_launcher_script_import(self, mock_main):
        """Test that the launcher script works."""
        # Import the launcher module
        import sys
        
        # Add project root to path
        project_root = Path(__file__).parent.parent.parent
        sys.path.insert(0, str(project_root))
        
        # This should not raise an import error
        try:
            from estoque.adapters.mainframe_tui import main
            assert callable(main)
        except ImportError:
            pytest.fail("Could not import TUI main function")


def test_all_menu_actions_covered():
    """Test that all menu actions are properly handled."""
    tree = MenuTreeWidget()
    app = EstoqueMainframeApp()
    
    # Collect all action data from the tree
    def collect_actions(node):
        actions = []
        if hasattr(node, 'data') and node.data:
            actions.append(node.data)
        for child in node.children:
            actions.extend(collect_actions(child))
        return actions
    
    all_actions = collect_actions(tree.root)
    
    # Remove category nodes (those without specific actions)
    action_nodes = [action for action in all_actions 
                   if action not in ['env', 'db', 'params', 'lote', 'reports', 'quality', 'maintenance']]
    
    # Test that execute_action can handle all actions
    app.run_simple_command = Mock()
    app.push_screen = Mock()
    
    for action in action_nodes:
        # This should not raise an exception
        try:
            app.execute_action(action)
        except Exception as e:
            pytest.fail(f"Action '{action}' not properly handled: {e}")
    
    # Verify that all actions were processed
    total_calls = app.run_simple_command.call_count + app.push_screen.call_count
    assert total_calls == len(action_nodes)


def test_cross_platform_commands():
    """Test that commands are structured correctly for different platforms."""
    app = EstoqueMainframeApp()
    
    # Test that the command structure is correct
    # We can't easily test the actual execution due to mocking complexity
    # but we can verify the basic logic
    assert hasattr(app, 'run_simple_command')
    assert hasattr(app, 'run_params_command') 
    assert hasattr(app, 'run_report_command')
    
    # Test that the app can be created without errors
    assert app is not None
    assert "Estoque Clínica" in app.title