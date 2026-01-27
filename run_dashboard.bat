@echo off
echo Starting GTIN Quality Dashboard...
echo.
call venv\Scripts\activate.bat
streamlit run gtin_dashboard.py
pause
