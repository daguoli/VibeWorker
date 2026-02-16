@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

:: VibeWorker 启动脚本 (Windows)
:: 用法: start.bat [start|stop|restart|status]

set "SCRIPT_DIR=%~dp0"
set "BACKEND_DIR=%SCRIPT_DIR%backend"
set "FRONTEND_DIR=%SCRIPT_DIR%frontend"

if "%1"=="" goto :start
if "%1"=="start" goto :start
if "%1"=="stop" goto :stop
if "%1"=="restart" goto :restart
if "%1"=="status" goto :status
if "%1"=="help" goto :help
if "%1"=="--help" goto :help
if "%1"=="-h" goto :help
goto :unknown

:start
echo [INFO] 启动 VibeWorker...
echo.

:: 启动后端
echo [INFO] 启动后端服务...
cd /d "%BACKEND_DIR%"

:: 检查虚拟环境
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

start "VibeWorker-Backend" /min cmd /c "python app.py"
echo [INFO] 后端启动中... http://localhost:8088

:: 启动前端
echo [INFO] 启动前端服务...
cd /d "%FRONTEND_DIR%"
start "VibeWorker-Frontend" /min cmd /c "npm run dev"
echo [INFO] 前端启动中... http://localhost:3000

echo.
echo ========== VibeWorker 启动完成 ==========
echo 后端: http://localhost:8088
echo 前端: http://localhost:3000
echo.
echo 提示: 服务运行在最小化窗口中，关闭窗口即可停止服务
echo ==========================================
goto :end

:stop
echo [INFO] 停止 VibeWorker...
echo.

:: 停止后端 (Python)
echo [INFO] 停止后端...
taskkill /FI "WINDOWTITLE eq VibeWorker-Backend*" /F >nul 2>&1
for /f "tokens=2" %%a in ('tasklist /fi "imagename eq python.exe" /v ^| findstr /i "app.py"') do (
    taskkill /PID %%a /F >nul 2>&1
)

:: 停止前端 (Node)
echo [INFO] 停止前端...
taskkill /FI "WINDOWTITLE eq VibeWorker-Frontend*" /F >nul 2>&1
for /f "tokens=2" %%a in ('tasklist /fi "imagename eq node.exe" /v ^| findstr /i "next"') do (
    taskkill /PID %%a /F >nul 2>&1
)

echo [INFO] VibeWorker 已停止
goto :end

:restart
echo [INFO] 重启 VibeWorker...
call :stop
timeout /t 2 /nobreak >nul
call :start
goto :end

:status
echo.
echo ========== VibeWorker 状态 ==========

:: 检查后端
tasklist /fi "imagename eq python.exe" /v 2>nul | findstr /i "app.py" >nul
if %errorlevel%==0 (
    echo 后端: [运行中] http://localhost:8088
) else (
    echo 后端: [未运行]
)

:: 检查前端
tasklist /fi "imagename eq node.exe" /v 2>nul | findstr /i "next" >nul
if %errorlevel%==0 (
    echo 前端: [运行中] http://localhost:3000
) else (
    echo 前端: [未运行]
)

echo =====================================
echo.
goto :end

:help
echo.
echo VibeWorker 启动脚本 (Windows)
echo.
echo 用法: %~nx0 [命令]
echo.
echo 命令:
echo   start     启动前后端 (默认)
echo   stop      停止前后端
echo   restart   重启前后端
echo   status    查看运行状态
echo   help      显示帮助信息
echo.
echo 示例:
echo   %~nx0           启动所有服务
echo   %~nx0 restart   重启所有服务
echo   %~nx0 status    查看状态
echo.
goto :end

:unknown
echo [ERROR] 未知命令: %1
echo 使用 '%~nx0 help' 查看帮助
goto :end

:end
endlocal
