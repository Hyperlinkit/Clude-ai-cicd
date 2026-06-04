#!/bin/bash
set -e

APP_DIR="/var/www/your-app"
APP_SERVICE="your-app"

echo "🚀 Deploying..."
cd $APP_DIR
git fetch origin && git reset --hard origin/main
pip install -r requirements.txt --quiet
sudo systemctl restart $APP_SERVICE
echo "✅ Deployment complete!"
