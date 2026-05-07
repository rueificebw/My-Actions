@echo off
chcp 65001 >nul

echo.
echo ============================================
echo   CaiYun Mini-Program Auth Capture
echo ============================================
echo.

cd /d "%~dp0"
set "PYTHON=C:\Users\Administrator\.workbuddy\binaries\python\versions\3.14.3\python.exe"
set "MITMPROXY=C:\Users\Administrator\.workbuddy\binaries\python\versions\3.14.3\Scripts\mitmproxy.exe"
set "CAPTURE_SCRIPT=%~dp0capture_auth.py"
set "PROXY_PORT=8088"

if not exist "%MITMPROXY%" (
    echo [*] mitmproxy not found, installing...
    "%PYTHON%" -m pip install mitmproxy
    echo [OK] mitmproxy installed
)

echo [*] Checking CA certificate...
set "CERT_DIR=%USERPROFILE%\.mitmproxy"
if not exist "%CERT_DIR%\mitmproxy-ca-cert.cer" (
    echo [!] CA certificate not found, generating...
    start /B "" "%MITMPROXY%" -p %PROXY_PORT% --mode regular
    echo [*] Waiting for certificate generation...
    timeout /t 8 >nul
    taskkill /F /IM mitmproxy.exe 2>nul
    timeout /t 2 >nul
)

if exist "%CERT_DIR%\mitmproxy-ca-cert.cer" (
    echo [OK] CA certificate found
    echo [*] Installing CA certificate to system...
    certutil -addstore -f "ROOT" "%CERT_DIR%\mitmproxy-ca-cert.cer" >nul 2>&1
    echo [OK] CA certificate installed
) else (
    echo [ERR] CA certificate generation failed
    pause
    exit /b 1
)

echo.
echo [*] Setting system proxy to 127.0.0.1:%PROXY_PORT%...
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyEnable /t REG_DWORD /d 1 /f >nul 2>&1
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyServer /t REG_SZ /d "127.0.0.1:%PROXY_PORT%" /f >nul 2>&1
echo [OK] System proxy set

echo.
echo ============================================
echo   1. Close WeChat first, then open WeChat PC
echo   2. Enter China Mobile Cloud Disk mini-program
echo   3. Click Cloud Center or refresh page
echo   4. When [OK] captured appears, press Ctrl+C
echo.
echo   Press Ctrl+C to stop capture
echo   System proxy will be restored automatically
echo ============================================
echo.

cd /d "%~dp0"
"%MITMPROXY%" -s "%CAPTURE_SCRIPT%" -p %PROXY_PORT% --mode regular

echo.
echo [*] Capture stopped, restoring system proxy...
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyEnable /t REG_DWORD /d 0 /f >nul 2>&1
echo [OK] System proxy restored
echo.

if exist "%~dp0..\..\captured_auth.txt" (
    echo [OK] Authorization captured!
    type "%~dp0..\..\captured_auth.txt"
) else (
    echo [!] No Authorization captured, please retry
)

echo.
pause
