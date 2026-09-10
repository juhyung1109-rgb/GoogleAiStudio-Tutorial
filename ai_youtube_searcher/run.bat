@echo off
chcp 65001 > nul
echo ========================================================
echo   AI ??? ??? (AI YouTube Searcher) ? ??? ?? ?...
echo ========================================================
cd /d "%~dp0"
call C:\Users\juhyung\miniconda\Scripts\activate.bat myenv
python -m uvicorn app:app --host 0.0.0.0 --port 8001 --reload
pause
