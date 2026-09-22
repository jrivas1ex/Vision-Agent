@echo off
REM Run this on a Windows machine with Python 3.10+ installed.
REM Produces dist\VisionAgent\VisionAgent.exe

pip install -r requirements.txt
pip install pyinstaller

pyinstaller vision_agent.spec

echo.
echo Listo. El ejecutable quedo en dist\VisionAgent\VisionAgent.exe
echo Copia junto a el: vision_agent_config.ini, swatches\, fabric_part_images\, kova_models.csv
pause
