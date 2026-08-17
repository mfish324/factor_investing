@echo off
cd /d "C:\Users\matto\projects\finance\factor_investing"
"C:\Users\matto\AppData\Local\Programs\Python\Python313\python.exe" -m trading.scheduler --model six_factor --frequency quarterly --check-and-run >> "results\trading_logs\scheduler_task.log" 2>&1
