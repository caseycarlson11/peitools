@echo off
echo ============================================
echo  PEI Tools - Quick Deploy (code only)
echo  Use this for: app.py, templates, static,
echo  BlueprintLinker changes (no new packages)
echo.
echo  Use deploy.bat instead if you changed:
echo  requirements.txt or Dockerfile
echo ============================================
echo.

set SERVER=root@93.188.160.121
set REMOTE=/var/www/panelmapper

echo === Copying files to server ===
scp "C:\Users\ROG\Documents\Pacific Erectors\PEItools.com\app.py" %SERVER%:%REMOTE%/
scp -r "C:\Users\ROG\Documents\Pacific Erectors\PEItools.com\templates" %SERVER%:%REMOTE%/
scp -r "C:\Users\ROG\Documents\Pacific Erectors\PEItools.com\static" %SERVER%:%REMOTE%/
scp -r "C:\Users\ROG\Documents\Pacific Erectors\PEItools.com\BlueprintLinker" %SERVER%:%REMOTE%/

echo.
echo === Reloading server (no Docker rebuild) ===
ssh %SERVER% "docker exec panelmapper kill -HUP 1"

echo.
echo === Done! Check peitools.com ===
echo (Reload usually takes 3-5 seconds)
