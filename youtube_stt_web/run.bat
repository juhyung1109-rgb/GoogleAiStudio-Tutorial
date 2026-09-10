@echo off
chcp 65001 > nul
echo ========================================================
echo   YouTube Audio & Gemini STT 웹 서비스 시작 중...
echo ========================================================
cd /d "%~dp0"
call C:\Users\juhyung\miniconda\Scripts\activate.bat myenv
python app.py
pause
