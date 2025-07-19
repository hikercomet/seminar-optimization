@echo off
rem コミットメッセージの入力をユーザーに求める
set /p msg=コミットメッセージを入力してください: 
echo.

rem Git操作を実行
git add .
git commit -m "%msg%"
git push origin main

echo.
echo Git操作が完了しました！
pause
