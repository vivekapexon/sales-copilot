@echo off
echo ========================================
echo FIX STRANDS DLL ERROR
echo ========================================
echo.
echo The strands library requires Visual C++ Runtime.
echo This script will help you install it.
echo.
echo ========================================
echo STEP 1: Download Visual C++ Redistributable
echo ========================================
echo.
echo Opening download page in your browser...
echo Please download and install:
echo   - vc_redist.x64.exe (for 64-bit Python)
echo.
start https://aka.ms/vs/17/release/vc_redist.x64.exe
echo.
echo ========================================
echo STEP 2: Install the downloaded file
echo ========================================
echo.
echo 1. Run the downloaded vc_redist.x64.exe
echo 2. Follow the installation wizard
echo 3. Restart your computer (IMPORTANT!)
echo.
pause
echo.
echo ========================================
echo STEP 3: After restart, run this again
echo ========================================
echo.
echo After restarting, run this script again to test.
echo.
echo Testing strands import...
python -c "import strands; print('SUCCESS: strands is working!')" 2>nul
if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo SUCCESS! strands is working!
    echo ========================================
    echo.
    echo You can now run your Streamlit app:
    echo    streamlit run streamlit_app.py
    echo.
    echo The REAL Strategy Agent will be used!
    echo ========================================
) else (
    echo.
    echo ========================================
    echo strands is still not working
    echo ========================================
    echo.
    echo Please make sure you:
    echo 1. Installed Visual C++ Redistributable
    echo 2. Restarted your computer
    echo 3. Are using 64-bit Python with 64-bit VC++ Redist
    echo.
    echo If still not working, try:
    echo    pip uninstall strands
    echo    pip install strands --no-cache-dir
    echo ========================================
)
echo.
pause
