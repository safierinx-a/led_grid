#!/bin/bash
# Deploy script for Raspberry Pi LED controller

# Configuration
PI_HOST=${PI_HOST:-"raspberrypi.local"}
PI_USER=${PI_USER:-"pi"}
PI_DIR=${PI_DIR:-"/home/pi/legrid-controller"}
SERVER_IP=${SERVER_IP:-"192.168.1.11"}
SERVER_PORT=${SERVER_PORT:-"4000"}

# Display settings
echo "Deploying to Raspberry Pi with these settings:"
echo "  Host: $PI_HOST"
echo "  User: $PI_USER"
echo "  Directory: $PI_DIR"
echo "  Server IP: $SERVER_IP"
echo "  Server Port: $SERVER_PORT"
echo ""

# Confirm deployment
read -p "Continue with deployment? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Deployment canceled."
  exit 1
fi

# Create remote directory
echo "Creating directory on Raspberry Pi..."
ssh $PI_USER@$PI_HOST "mkdir -p $PI_DIR"

# Copy controller files
echo "Copying controller files..."
scp raspberry-controller.py requirements.controller.txt $PI_USER@$PI_HOST:$PI_DIR/

# Create setup script on the Pi
echo "Creating setup script..."
cat > setup-controller.sh << EOF
#!/bin/bash
cd $PI_DIR
pip3 install -r requirements.controller.txt
chmod +x raspberry-controller.py
EOF

# Copy and execute setup script
scp setup-controller.sh $PI_USER@$PI_HOST:$PI_DIR/
ssh $PI_USER@$PI_HOST "chmod +x $PI_DIR/setup-controller.sh && $PI_DIR/setup-controller.sh"

# Create systemd service file
echo "Creating systemd service..."
cat > legrid-controller.service << EOF
[Unit]
Description=LED Grid Controller
After=network.target

[Service]
User=$PI_USER
WorkingDirectory=$PI_DIR
ExecStart=$PI_DIR/raspberry-controller.py --server-url ws://$SERVER_IP:$SERVER_PORT/controller/websocket
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Install service
scp legrid-controller.service $PI_USER@$PI_HOST:$PI_DIR/
ssh $PI_USER@$PI_HOST "sudo mv $PI_DIR/legrid-controller.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable legrid-controller && sudo systemctl restart legrid-controller"

# Clean up local temp files
rm setup-controller.sh legrid-controller.service

echo "Deployment complete! Controller service should now be running."
echo "To check status: ssh $PI_USER@$PI_HOST 'sudo systemctl status legrid-controller'"
echo "To view logs: ssh $PI_USER@$PI_HOST 'sudo journalctl -u legrid-controller -f'" 