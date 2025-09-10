@echo off
echo ================================
echo   Patient Monitor Docker Setup  
echo ================================
echo.

if "%1"=="dev" (
    echo [INFO] Starting development environment...
    docker-compose -f docker-compose.dev.yml up --build -d
    echo.
    echo [SUCCESS] Services started!
    echo Web App: http://localhost:5000
    echo Adminer: http://localhost:8080
    goto end
)

if "%1"=="stop" (
    echo [INFO] Stopping services...
    docker-compose -f docker-compose.dev.yml down
    goto end
)

if "%1"=="logs" (
    echo [INFO] Showing logs...
    docker-compose -f docker-compose.dev.yml logs -f
    goto end
)

echo [ERROR] Usage: .\docker-run.bat [dev^|stop^|logs]
echo   dev  - Start development environment
echo   stop - Stop all services  
echo   logs - Show service logs

:end
pause
