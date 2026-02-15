@echo off
setlocal EnableDelayedExpansion

REM VibeWorker Skills CLI - Windows Version
REM Manage skills from the command line

REM Configuration
if "%VIBEWORKER_API_BASE%"=="" set VIBEWORKER_API_BASE=http://localhost:8088
if "%VIBEWORKER_SKILLS_DIR%"=="" set VIBEWORKER_SKILLS_DIR=%~dp0..\backend\skills

REM Parse command
set CMD=%1
if "%CMD%"=="" set CMD=help

if /i "%CMD%"=="list" goto cmd_list
if /i "%CMD%"=="search" goto cmd_search
if /i "%CMD%"=="install" goto cmd_install
if /i "%CMD%"=="uninstall" goto cmd_uninstall
if /i "%CMD%"=="remove" goto cmd_uninstall
if /i "%CMD%"=="update" goto cmd_update
if /i "%CMD%"=="upgrade" goto cmd_update
if /i "%CMD%"=="create" goto cmd_create
if /i "%CMD%"=="new" goto cmd_create
if /i "%CMD%"=="help" goto cmd_help
if /i "%CMD%"=="--help" goto cmd_help
if /i "%CMD%"=="-h" goto cmd_help

echo [ERROR] Unknown command: %CMD%
goto cmd_help

:cmd_list
set REMOTE=false
if /i "%2"=="--remote" set REMOTE=true
if /i "%2"=="-r" set REMOTE=true

if "%REMOTE%"=="true" (
    echo [INFO] Fetching remote skills...
    curl -s "%VIBEWORKER_API_BASE%/api/store/skills" | python -c "import json,sys;d=json.load(sys.stdin);skills=d.get('skills',[]);[print(f\"  [{'V' if s.get('is_installed') else ' '}] {s['name']} v{s['version']}\n      {s['description']}\n      Rating: {s['rating']:.1f}  Downloads: {s['downloads']}\n\") for s in skills] if skills else print('No remote skills found.')"
) else (
    echo [INFO] Fetching local skills...
    curl -s "%VIBEWORKER_API_BASE%/api/skills" | python -c "import json,sys;d=json.load(sys.stdin);skills=d.get('skills',[]);[print(f\"  * {s['name']}\n    {s['description']}\n    Location: {s['location']}\n\") for s in skills] if skills else print('No local skills installed.')"
)
goto end

:cmd_search
if "%2"=="" (
    echo [ERROR] Usage: skills.bat search ^<query^>
    goto end
)
echo [INFO] Searching for '%2'...
curl -s "%VIBEWORKER_API_BASE%/api/store/search?q=%2" | python -c "import json,sys;d=json.load(sys.stdin);results=d.get('results',[]);[print(f\"  [{'V' if s.get('is_installed') else ' '}] {s['name']} v{s['version']}\n      {s['description']}\n\") for s in results] if results else print('No skills found.')"
goto end

:cmd_install
if "%2"=="" (
    echo [ERROR] Usage: skills.bat install ^<skill_name^>
    goto end
)
echo [INFO] Installing skill '%2'...
curl -s -X POST "%VIBEWORKER_API_BASE%/api/store/install" -H "Content-Type: application/json" -d "{\"skill_name\": \"%2\"}" | python -c "import json,sys;d=json.load(sys.stdin);print(f\"[OK] Successfully installed {d.get('skill_name')} v{d.get('version')}\") if d.get('status')=='ok' else print(f\"[ERROR] {d.get('detail', d.get('message', 'Unknown error'))}\")"
goto end

:cmd_uninstall
if "%2"=="" (
    echo [ERROR] Usage: skills.bat uninstall ^<skill_name^>
    goto end
)
set /p CONFIRM="Are you sure you want to uninstall '%2'? [y/N]: "
if /i not "%CONFIRM%"=="y" (
    echo [INFO] Cancelled.
    goto end
)
echo [INFO] Uninstalling skill '%2'...
curl -s -X DELETE "%VIBEWORKER_API_BASE%/api/skills/%2" | python -c "import json,sys;d=json.load(sys.stdin);print('[OK] Successfully uninstalled') if d.get('status')=='ok' else print(f\"[ERROR] {d.get('detail', 'Unknown error')}\")"
goto end

:cmd_update
if "%2"=="" (
    echo [ERROR] Usage: skills.bat update ^<skill_name^> or skills.bat update --all
    goto end
)
if /i "%2"=="--all" (
    echo [INFO] Updating all skills...
    for /f "tokens=*" %%i in ('curl -s "%VIBEWORKER_API_BASE%/api/skills" ^| python -c "import json,sys;d=json.load(sys.stdin);[print(s['name']) for s in d.get('skills',[])]"') do (
        echo [INFO] Updating %%i...
        curl -s -X POST "%VIBEWORKER_API_BASE%/api/skills/%%i/update" > nul
    )
    echo [OK] Update complete.
) else (
    echo [INFO] Updating skill '%2'...
    curl -s -X POST "%VIBEWORKER_API_BASE%/api/skills/%2/update" | python -c "import json,sys;d=json.load(sys.stdin);print(f\"[OK] Updated to v{d.get('version')}\") if d.get('status')=='ok' else print(f\"[ERROR] {d.get('detail', 'Unknown error')}\")"
)
goto end

:cmd_create
if "%2"=="" (
    echo [ERROR] Usage: skills.bat create ^<skill_name^>
    goto end
)
set SKILL_NAME=%2
set SKILL_DIR=%VIBEWORKER_SKILLS_DIR%\%SKILL_NAME%

if exist "%SKILL_DIR%" (
    echo [ERROR] Skill '%SKILL_NAME%' already exists.
    goto end
)

echo [INFO] Creating skill template '%SKILL_NAME%'...
mkdir "%SKILL_DIR%"

(
echo ---
echo name: %SKILL_NAME%
echo description: %SKILL_NAME% skill description
echo ---
echo.
echo # %SKILL_NAME%
echo.
echo ## Description
echo.
echo Describe the skill functionality here.
echo.
echo ## Usage
echo.
echo ### Step 1: Prepare
echo.
echo Describe preparation steps...
echo.
echo ### Step 2: Execute
echo.
echo Describe execution steps...
echo.
echo ## Examples
echo.
echo - Example usage 1
echo - Example usage 2
) > "%SKILL_DIR%\SKILL.md"

echo [OK] Created skill template at %SKILL_DIR%
echo [INFO] Edit %SKILL_DIR%\SKILL.md to customize your skill.
goto end

:cmd_help
echo VibeWorker Skills CLI
echo.
echo Usage:
echo   skills.bat ^<command^> [options]
echo.
echo Commands:
echo   list [--remote]     List installed skills (or remote with --remote)
echo   search ^<query^>      Search for skills in the store
echo   install ^<name^>      Install a skill from the store
echo   uninstall ^<name^>    Uninstall an installed skill
echo   update ^<name^>       Update a skill (or --all for all skills)
echo   create ^<name^>       Create a new skill template
echo   help                Show this help message
echo.
echo Environment Variables:
echo   VIBEWORKER_API_BASE     Backend API URL (default: http://localhost:8088)
echo   VIBEWORKER_SKILLS_DIR   Skills directory path
echo.
echo Examples:
echo   skills.bat list --remote     # List all available skills
echo   skills.bat search weather    # Search for weather-related skills
echo   skills.bat install get_weather
echo   skills.bat create my_skill
goto end

:end
endlocal
