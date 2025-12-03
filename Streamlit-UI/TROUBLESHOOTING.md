# Troubleshooting Guide for SALES-COPILOT

## DLL Load Failed Error (Windows)

### Error Message
```
DLL load failed while importing strands: The specified module could not be found.
```

### Root Cause
The `strands` library has native dependencies that require Visual C++ runtime libraries on Windows.

### Solutions (Try in order)

#### Solution 1: Install Visual C++ Redistributable
1. Download and install Microsoft Visual C++ Redistributable:
   - **64-bit**: https://aka.ms/vs/17/release/vc_redist.x64.exe
   - **32-bit**: https://aka.ms/vs/17/release/vc_redist.x86.exe

2. Restart your computer

3. Reinstall strands:
   ```bash
   pip uninstall strands
   pip install strands --no-cache-dir
   ```

#### Solution 2: Upgrade pip and setuptools
```bash
python -m pip install --upgrade pip setuptools wheel
pip install strands --no-cache-dir
```

#### Solution 3: Use a Different Python Version
The issue might be specific to your Python version. Try:
- Python 3.9 or 3.10 (most stable for Windows)
- Avoid Python 3.12+ as some packages may not be compatible yet

```bash
# Check your Python version
python --version

# If needed, install a different version from python.org
```

#### Solution 4: Install from Source (Advanced)
If pre-built wheels don't work, try building from source:

```bash
pip install --upgrade pip setuptools wheel
pip install strands --no-binary :all:
```

#### Solution 5: Use Virtual Environment
Create a fresh virtual environment:

```bash
# Create new virtual environment
python -m venv venv_sales_copilot

# Activate it
venv_sales_copilot\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

#### Solution 6: Check for Conflicting DLLs
Sometimes other installed software can cause DLL conflicts:

1. Check your PATH environment variable for conflicting DLLs
2. Temporarily rename or remove other Python installations
3. Try running from a clean command prompt (not Anaconda/Conda)

## Alternative: Mock Agent for Testing UI

If you can't resolve the strands issue immediately, you can test the UI with a mock agent:

1. Create `Strategy-Agent/mock_strategy_agent.py`:

```python
def run_strategy_agent(nlq: str):
    """Mock strategy agent for testing"""
    return {
        "Agent": "MockAgent",
        "message": "This is a mock response for testing the UI",
        "query": nlq,
        "note": "Install strands to use the real agent"
    }
```

2. Update `utils/agent_integration.py` to import the mock:

```python
try:
    from strategy_agent import run_strategy_agent
except ImportError:
    try:
        from mock_strategy_agent import run_strategy_agent
        print("Using mock agent for testing")
    except ImportError:
        run_strategy_agent = None
```

## Other Common Issues

### Port Already in Use
```bash
# Use a different port
streamlit run streamlit_app.py --server.port 8502
```

### Module Not Found Errors
```bash
# Reinstall all dependencies
pip install -r requirements.txt --force-reinstall
```

### Chat History Not Saving
- Check that `chat_history/` directory exists
- Verify write permissions on the directory
- Check disk space

### Streamlit Won't Start
```bash
# Clear Streamlit cache
streamlit cache clear

# Update Streamlit
pip install --upgrade streamlit
```

## Getting Help

If none of these solutions work:

1. **Check your Python environment:**
   ```bash
   python --version
   pip list
   ```

2. **Check for error details:**
   - Look at the full error traceback
   - Check Windows Event Viewer for system errors

3. **System Information:**
   - Windows version
   - Python version
   - Whether you're using Anaconda/Miniconda
   - Any antivirus software that might block DLLs

4. **Alternative Approach:**
   - Consider using WSL (Windows Subsystem for Linux)
   - Use Docker container
   - Use a cloud-based Python environment

## Contact

For additional support, provide:
- Full error message and traceback
- Python version (`python --version`)
- Operating system details
- Output of `pip list`
