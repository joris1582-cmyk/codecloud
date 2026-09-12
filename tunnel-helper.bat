@echo off
title CodeCloud - Cloudflare Tunnel (School Access)
echo =======================================================
echo    Exposing CodeCloud to the Internet for School Access
echo =======================================================
echo.
echo Running free Cloudflare Quick Tunnel on port 3050...
echo (No account or router port forwarding needed!)
echo.
echo Look for the link ending in: .trycloudflare.com
echo.
npx -y cloudflared tunnel --url http://localhost:3050
pause
