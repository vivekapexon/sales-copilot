@echo off
echo ========================================
echo SALES-COPILOT Dependency Installation
echo ========================================
echo.

echo Step 1: Upgrading pip, setuptools, and wheel...
python -m pip install --upgrade pip setuptools wheel
echo.

echo Step 2: Installing Streamlit and utilities...
pip install streamlit>=1.28.0 python-dateutil>=2.8.2
echo.

echo Step 3: Attempting to install strands...
pip install strands --no-cache-dir
echo.

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ========================================
    echo WARNING: strands installation failed!
    echo ========================================
    echo.
    echo This is likely due to missing Visual C++ libraries.
    echo.
    echo SOLUTIONS:
    echo 1. Install Visual C++ Redistributable:
    echo    https://aka.ms/vs/17/release/vc_redist.x64.exe
    echo.
    echo 2. After installing, run this script again
    echo.
    echo 3. Or use the mock agent for testing:
    echo    The app will automatically use mock data
    echo.
    echo See TROUBLESHOOTING.md for more solutions
    echo ========================================
    pause
) else (
    echo.
    echo ========================================
    echo SUCCESS! All dependencies installed.
    echo ========================================
    echo.
    echo You can now run the application with:
    echo    streamlit run streamlit_app.py
    echo.
    echo Or simply double-click: run_app.bat
    echo ========================================
    pause
)
