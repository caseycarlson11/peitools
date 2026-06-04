@echo off
echo ============================================
echo  PEI Tools - Quick Deploy
echo  Enter password once when prompted
echo ============================================
echo.

cd /d "C:\Users\ROG\Documents\Pacific Erectors\PEItools.com"

echo === Sending files and deploying (enter password once) ===
tar -czf - app.py packing_list_engine.py templates static BlueprintLinker | ssh root@93.188.160.121 "tar -xzf - -C /var/www/panelmapper && docker cp /var/www/panelmapper/app.py panelmapper:/app/app.py && docker cp /var/www/panelmapper/packing_list_engine.py panelmapper:/app/packing_list_engine.py && docker cp /var/www/panelmapper/templates panelmapper:/app/ && docker cp /var/www/panelmapper/static panelmapper:/app/ && docker cp /var/www/panelmapper/BlueprintLinker panelmapper:/app/ && (docker exec panelmapper sh -c 'kill -HUP 1' 2>/dev/null || docker restart panelmapper) && echo Done"

echo.
echo === Check peitools.com ===
