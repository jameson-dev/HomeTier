# HomeTier

**Home Equipment Inventory Management & Automated Network Device Discovery**

A locally-hosted web application that helps you maintain an organized inventory of your home equipment and appliances, which automatically discovers devices on your network.

## 🚀 Features

- **Auto-Detect New Devices**: Periodic network scanning to discover new network devices
- **Inventory Management**: Keep track of network devices (routers, switches, smart devices), and appliances
- **Device Relationships**: Map device dependencies and connections
- **Warranty Tracking**: Monitor purchase dates and warranty expiration
- **Custom Notifications**: Filter alerts based on your preferences
- **Export & Backup**: Save your inventory as JSON or CSV

## 🐳 Quick Start with Docker

1. **Clone the repository**
   ```bash
   git clone https://github.com/jameson-dev/hometier.git
   cd hometier
   ```

2. **Run with Docker Compose**
   ```bash
   docker-compose up -d
   ```

3. **Access the application**
   Open your browser to `http://localhost:5000`

## Tech Stack

- **Backend**: Python, Flask, SQLite
- **Frontend**: HTML5, CSS3, JavaScript
- **Network Discovery**: scapy, nmap
- **Visualization**: networkx, pyvis
- **Deployment**: Docker

## Requirements
- Reasonable understanding of Docker and local app/web hosting
- Network access for device discovery

## Security Note

This application runs in host network mode to discover local network devices. It only scans your local network and stores data locally in an SQLite database.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.