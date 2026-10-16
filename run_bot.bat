@echo off
chcp 65001 >nul
echo ========================================
echo    JAMAIKA CHECKER BOT - Local Run
echo ========================================
echo.

set /p BOT_TOKEN="Enter BOT_TOKEN: "
set /p ADMIN_ID="Enter ADMIN_ID (default: 6409122908): "

if "%ADMIN_ID%"=="" set ADMIN_ID=6409122908

echo.
echo Creating .env file...
echo BOT_TOKEN=%BOT_TOKEN% > .env
echo ADMIN_ID=%ADMIN_ID% >> .env

echo.
echo Installing dependencies...
pip install -r requirements.txt

echo.
echo Starting bot...
python bot.py

pause
