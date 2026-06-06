@echo off
echo === Syncing files to git folder ===
robocopy "C:\Users\ROG\Documents\Pacific Erectors\PEItools.com" C:\temp\peitools /E /XD Jobs /XF landing_preview.html upload_app.ps1 upload_cmd.txt /NFL /NDL /NJH /NJS

echo === Pushing to GitHub ===
cd /d C:\temp\peitools
git add .
git commit -m "Update %date% %time%"
git push origin main

echo === Deploying to server ===
ssh root@93.188.160.121 "cd /var/www/panelmapper && git fetch origin && git reset --hard origin/main && git clean -fd && docker build --no-cache -t panelmapper . && docker stop panelmapper; docker rm panelmapper; docker run -d --name panelmapper -p 5000:5000 -v /var/www/pei-jobs:/app/jobs panelmapper"

echo === Done! Check peitools.com ===
