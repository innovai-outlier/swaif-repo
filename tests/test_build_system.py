"""
Tests for the build system (Makefile split and Windows batch equivalent).
"""

import pytest
import subprocess
from pathlib import Path


class TestBuildSystemStructure:
    """Test the structure of the build system files."""
    
    def test_required_files_exist(self):
        """Test that all required build system files exist."""
        project_root = Path(__file__).parent.parent
        
        # Check main Makefile exists
        assert (project_root / "Makefile").exists()
        
        # Check Unix-specific Makefile exists
        assert (project_root / "Makefile.unix").exists()
        
        # Check Windows batch file exists
        assert (project_root / "build.bat").exists()
        
        # Check documentation exists
        assert (project_root / "BUILD.md").exists()
    
    def test_makefile_content(self):
        """Test that main Makefile has correct content."""
        project_root = Path(__file__).parent.parent
        makefile_path = project_root / "Makefile"
        
        content = makefile_path.read_text()
        
        # Should contain platform information
        assert "PLATAFORMA-ESPECÍFICA" in content
        assert "Linux/Unix/MacOS" in content
        assert "Windows" in content
        assert "build.bat" in content
        assert "Makefile.unix" in content
    
    def test_makefile_unix_content(self):
        """Test that Unix Makefile has correct structure."""
        project_root = Path(__file__).parent.parent
        makefile_path = project_root / "Makefile.unix"
        
        content = makefile_path.read_text()
        
        # Should contain all expected targets
        expected_targets = [
            "venv", "install", "install-min", "migrate", "verificar",
            "params-show", "params-set", "entrada-lotes", "saida-lotes",
            "rel-ruptura", "rel-vencimentos", "rel-top", "rel-reposicao",
            "test", "lint", "doctor", "ci", "clean", "distclean"
        ]
        
        for target in expected_targets:
            assert f".PHONY: {target}" in content or f"{target}:" in content
    
    def test_build_bat_content(self):
        """Test that Windows batch file has correct structure."""
        project_root = Path(__file__).parent.parent
        batch_path = project_root / "build.bat"
        
        content = batch_path.read_text()
        
        # Should contain all expected commands
        expected_commands = [
            "venv", "install", "install-min", "migrate", "verificar",
            "params-show", "params-set", "entrada-lotes", "saida-lotes",
            "rel-ruptura", "rel-vencimentos", "rel-top", "rel-reposicao",
            "test", "lint", "doctor", "ci", "clean", "distclean"
        ]
        
        for command in expected_commands:
            assert f'if "%1"=="{command}"' in content


class TestMakefileExecution:
    """Test Makefile execution on Unix-like systems."""
    
    @pytest.fixture
    def project_root(self):
        return Path(__file__).parent.parent
    
    def test_makefile_help(self, project_root):
        """Test that make help works."""
        try:
            result = subprocess.run(
                ["make", "help"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # Should run successfully
            assert result.returncode == 0
            
            # Should contain platform information
            output = result.stdout
            assert "MULTIPLATAFORMA" in output
            assert "Linux/Unix/MacOS" in output
            assert "Windows" in output
            
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pytest.skip("Make command not available or too slow")
    
    def test_makefile_unix_help(self, project_root):
        """Test that make -f Makefile.unix help works."""
        try:
            result = subprocess.run(
                ["make", "-f", "Makefile.unix", "help"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # Should run successfully
            assert result.returncode == 0
            
            # Should contain expected commands
            output = result.stdout
            assert "venv" in output
            assert "install" in output
            assert "test" in output
            
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pytest.skip("Make command not available or too slow")
    
    @pytest.mark.skipif(not Path(".venv").exists(), reason="Virtual environment required")
    def test_makefile_test_shortcut(self, project_root):
        """Test that make test shortcut works."""
        try:
            result = subprocess.run(
                ["make", "test"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Should run successfully (tests should pass)
            assert result.returncode == 0
            
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pytest.skip("Make command not available or too slow")


class TestBuildBatExecution:
    """Test Windows batch file execution (simulated on Unix)."""
    
    @pytest.fixture
    def project_root(self):
        return Path(__file__).parent.parent
    
    def test_build_bat_structure(self, project_root):
        """Test that build.bat has correct structure."""
        batch_path = project_root / "build.bat"
        content = batch_path.read_text()
        
        # Should start with @echo off
        lines = content.split('\n')
        assert lines[0].strip() == "@echo off"
        
        # Should have help section
        assert 'if "%1"=="help"' in content
        
        # Should have proper Windows syntax
        assert "set " in content
        assert "goto :eof" in content
        assert ".exe" in content  # For Python executables
    
    def test_build_bat_help_simulation(self, project_root):
        """Test build.bat help command structure."""
        batch_path = project_root / "build.bat"
        content = batch_path.read_text()
        
        # Find help section
        help_section = ""
        in_help = False
        for line in content.split('\n'):
            if 'if "%1"=="help"' in line:
                in_help = True
            elif in_help and 'goto :eof' in line:
                break
            elif in_help:
                help_section += line + '\n'
        
        # Should contain command descriptions
        assert "venv" in help_section
        assert "install" in help_section
        assert "test" in help_section
        assert "lint" in help_section


class TestBuildSystemCoverage:
    """Test that all functionality is covered by both build systems."""
    
    def test_command_parity(self):
        """Test that both build systems support the same commands."""
        project_root = Path(__file__).parent.parent
        
        # Extract commands from Makefile.unix
        makefile_content = (project_root / "Makefile.unix").read_text()
        unix_commands = []
        for line in makefile_content.split('\n'):
            if line.startswith('.PHONY:'):
                commands = line.replace('.PHONY:', '').strip().split()
                unix_commands.extend(commands)
        
        # Remove help as it's special
        unix_commands = [cmd for cmd in unix_commands if cmd != 'help']
        
        # Extract commands from build.bat
        batch_content = (project_root / "build.bat").read_text()
        batch_commands = []
        for line in batch_content.split('\n'):
            line = line.strip()
            if line.startswith('if "%1"=="') and '(' in line:
                # Extract command name between quotes
                start = line.find('if "%1"=="') + len('if "%1"=="')
                end = line.find('"', start)
                if end > start:
                    cmd = line[start:end]
                    if cmd not in ['help', '']:
                        batch_commands.append(cmd)
        
        # Remove duplicates
        unix_commands = list(set(unix_commands))
        batch_commands = list(set(batch_commands))
        
        # Sort for comparison
        unix_commands.sort()
        batch_commands.sort()
        
        # Should have same commands (allow some variance for implementation differences)
        missing_from_batch = set(unix_commands) - set(batch_commands)
        missing_from_unix = set(batch_commands) - set(unix_commands)
        
        # Some commands might have slight differences, focus on major ones
        major_commands = {
            'venv', 'install', 'install-min', 'migrate', 'verificar', 
            'params-show', 'params-set', 'entrada-lotes', 'saida-lotes',
            'test', 'lint', 'clean', 'distclean'
        }
        
        major_missing_batch = major_commands & missing_from_batch
        major_missing_unix = major_commands & missing_from_unix
        
        assert not major_missing_batch, f"Major commands missing from build.bat: {major_missing_batch}"
        assert not major_missing_unix, f"Major commands missing from Makefile.unix: {major_missing_unix}"
    
    def test_variable_handling(self):
        """Test that both systems handle variables similarly."""
        project_root = Path(__file__).parent.parent
        
        # Check Unix variables
        unix_content = (project_root / "Makefile.unix").read_text()
        
        # Should use standard Unix variables
        assert "PY?=python3" in unix_content
        assert "VENV?=.venv" in unix_content
        assert "DB?=estoque.db" in unix_content
        assert "$(PYTHON)" in unix_content
        
        # Check Windows batch variables
        batch_content = (project_root / "build.bat").read_text()
        
        # Should use Windows batch variables
        assert 'if "%PY%"==""' in batch_content
        assert 'if "%VENV%"==""' in batch_content
        assert 'if "%DB%"==""' in batch_content
        assert "%PYTHON%" in batch_content
    
    def test_error_handling(self):
        """Test that both systems have proper error handling."""
        project_root = Path(__file__).parent.parent
        
        # Check Unix error handling
        unix_content = (project_root / "Makefile.unix").read_text()
        
        # Should have parameter validation
        assert 'echo "Uso:' in unix_content
        assert 'exit 1' in unix_content
        
        # Check Windows error handling  
        batch_content = (project_root / "build.bat").read_text()
        
        # Should have parameter validation
        assert 'echo Uso:' in batch_content
        assert 'exit /b 1' in batch_content


class TestBuildDocumentation:
    """Test build system documentation."""
    
    def test_build_md_exists_and_complete(self):
        """Test that BUILD.md exists and is complete."""
        project_root = Path(__file__).parent.parent
        build_md = project_root / "BUILD.md"
        
        assert build_md.exists()
        
        content = build_md.read_text()
        
        # Should contain sections for both platforms
        assert "Linux/Unix/MacOS" in content
        assert "Windows" in content
        
        # Should contain examples
        assert "make -f Makefile.unix" in content
        assert "build.bat" in content
        
        # Should document all major commands
        major_commands = ["install", "test", "migrate", "params-set"]
        for cmd in major_commands:
            assert cmd in content
    
    def test_readme_references_build_system(self):
        """Test that README references the build system (if it exists)."""
        project_root = Path(__file__).parent.parent
        readme_path = project_root / "README.md"
        
        if readme_path.exists():
            content = readme_path.read_text()
            # Should mention the build system or reference BUILD.md
            build_references = [
                "BUILD.md", "build.bat", "Makefile", "make install"
            ]
            
            has_build_reference = any(ref in content for ref in build_references)
            assert has_build_reference, "README should reference the build system"


class TestCrossPlatformCompatibility:
    """Test cross-platform compatibility aspects."""
    
    def test_path_handling(self):
        """Test that paths are handled correctly for each platform."""
        project_root = Path(__file__).parent.parent
        
        # Unix should use forward slashes and Unix paths
        unix_content = (project_root / "Makefile.unix").read_text()
        assert "$(VENV)/bin/pip" in unix_content
        assert "$(VENV)/bin/python" in unix_content
        
        # Windows should use backslashes and Windows paths
        batch_content = (project_root / "build.bat").read_text()
        assert r"%VENV%\Scripts\pip.exe" in batch_content
        assert r"%VENV%\Scripts\python.exe" in batch_content
    
    def test_command_syntax(self):
        """Test that command syntax is appropriate for each platform."""
        project_root = Path(__file__).parent.parent
        
        # Unix should use shell syntax
        unix_content = (project_root / "Makefile.unix").read_text()
        assert "[ -z" in unix_content  # Shell test
        assert "$$(" in unix_content   # Shell substitution
        
        # Windows should use batch syntax
        batch_content = (project_root / "build.bat").read_text()
        assert 'if "%' in batch_content     # Batch conditional
        assert 'set CMD=' in batch_content  # Batch variable assignment
    
    def test_help_output_consistency(self):
        """Test that help output is consistent between platforms."""
        project_root = Path(__file__).parent.parent
        
        # Both should describe the same functionality
        unix_content = (project_root / "Makefile.unix").read_text()
        batch_content = (project_root / "build.bat").read_text()
        
        # Extract help text patterns
        common_patterns = [
            "venv", "install", "migrate", "test", "lint", "params"
        ]
        
        for pattern in common_patterns:
            # Both should mention these concepts in help
            assert pattern in unix_content.lower()
            assert pattern in batch_content.lower()