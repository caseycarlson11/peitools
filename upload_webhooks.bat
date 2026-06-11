@echo off
echo ============================================
echo  PEI Tools - Upload Discord webhooks
echo  Sends Jobs\.discord_webhooks.json to the
echo  server's persistent jobs volume.
echo  Enter password once when prompted.
echo ============================================
echo.

cd /d "C:\Users\ROG\Documents\Pacific Erectors\PEItools.com"

scp "Jobs\.discord_webhooks.json" root@93.188.160.121:/var/www/pei-jobs/.discord_webhooks.json

echo.
echo === Done! Field Report channels are live on peitools.com ===
pause
