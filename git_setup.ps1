$server = "root@93.188.160.121"
$repo = "https://github.com/caseycarlson11/peitools.git"
$dir = "C:\Users\ROG\Documents\Pacific Erectors\PEItools.com"

Write-Host "=== Step 1: Initialize git locally ==="
git -C $dir init
git -C $dir remote remove origin 2>$null
git -C $dir remote add origin $repo
git -C $dir add .
git -C $dir commit -m "Initial commit"
git -C $dir branch -M main
git -C $dir push -u origin main

Write-Host ""
Write-Host "=== Step 2: Deploy to server ==="
ssh $server "cd /var/www/panelmapper && git pull && docker build -t panelmapper . && docker stop panelmapper || true && docker rm panelmapper || true && docker run -d --name panelmapper -p 5000:5000 panelmapper"

Write-Host ""
Write-Host "=== Done! Check peitools.com ==="
