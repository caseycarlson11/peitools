@echo off
echo ============================================
echo  PEI Tools - Upload Push-to-Discord config
echo  Sends the Discord webhooks (and the
echo  transcription API key, if present) to the
echo  server's persistent jobs volume.
echo  Enter password once per file when prompted.
echo ============================================
echo.

cd /d "C:\Users\ROG\Documents\Pacific Erectors\PEItools.com"

scp "Jobs\.discord_webhooks.json" root@93.188.160.121:/var/www/pei-jobs/.discord_webhooks.json

if exist "Jobs\.openai_key.txt" (
    scp "Jobs\.openai_key.txt" root@93.188.160.121:/var/www/pei-jobs/.openai_key.txt
)

if exist "Jobs\.discord_bot_token.txt" (
    scp "Jobs\.discord_bot_token.txt" root@93.188.160.121:/var/www/pei-jobs/.discord_bot_token.txt
)

if exist "Jobs\.todo_view_tokens.json" (
    scp "Jobs\.todo_view_tokens.json" root@93.188.160.121:/var/www/pei-jobs/.todo_view_tokens.json
)

echo.
echo === Done! Push to Discord config is live on peitools.com ===
pause
