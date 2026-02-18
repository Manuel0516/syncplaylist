#!/bin/bash

echo "Starting YouTube-Spotify Sync Bot deployment process..."

# Variables
SERVER="manuel@zero-five.ddns.net"
PORT="2021"
DEST_PATH="/home/manuel/SyncPlaylist"
APP_NAME="sync_youtube_spotify"
PYTHON_ENV="/home/manuel/.venvs/sync_playlist/bin/python"  # Adjust if using a virtual environment

# Step 1: Sync files to the server using rsync
echo "Syncing files to the server..."
rsync -avz -e "ssh -p $PORT" ./ $SERVER:$DEST_PATH

# Step 2: Install dependencies on the server
echo "Installing dependencies on the server..."
ssh -p $PORT $SERVER "cd $DEST_PATH && pip install -r requirements.txt"

echo "Deployment completed successfully."
