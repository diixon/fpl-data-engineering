# Azure Deployment Guide

## Why Azure?

I chose Azure for this project because it offers a robust, enterprise-grade ecosystem that aligns with standard Data Engineering practices. While the pipeline runs locally via Docker Compose, deploying it to the cloud proves that the architecture is production-ready.

## Architecture Overview

For the cloud deployment, I split the architecture into two managed services:

1. **Azure Database for PostgreSQL**: A managed database service. I chose this over running Postgres in a container because it handles backups, patching, and high availability automatically.
2. **Azure Virtual Machine (VM)**: A Linux VM to host the Docker containers (Airflow Webserver and Scheduler). I chose a VM over Azure Container Instances (ACI) because Airflow needs persistent storage for logs and DAGs, which is easier to manage on a VM.

## 1. Database Deployment (Azure PostgreSQL)

I use the Flexible Server option for better cost control and configuration.

1. Go to the Azure Portal and search for **Azure Database for PostgreSQL Flexible Server**.
2. Click **Create**.
3. Set the **Server name** (e.g., `fpl-postgres-server`).
4. Set **Admin username** and **Password** (I save these securely, as they replace the local `.env` credentials).
5. Under **Compute + Storage**, I choose the **Burstable, B1ms** tier. This is the cheapest tier and is more than enough for this project's data volume (\~600 players, \~380 fixtures).
6. Under **Networking**, I enable **Public access** and add my current IP address to the firewall rules. This allows me to connect via DBeaver locally and allows the Azure VM to connect later.
7. Once deployed, I connect to the database using DBeaver and run the SQL scripts from my `sql/` folder to create the tables.

## 2. Airflow Deployment (Azure Virtual Machine)

To run Airflow 24/7 without relying on my local machine, I deploy it on a Linux VM.

1. In the Azure Portal, I create a **Virtual Machine**.
2. Image: **Ubuntu Server 22.04 LTS**.
3. Size: **Standard_B2s** (2 vCPUs, 4GB RAM). Airflow's LocalExecutor needs at least 4GB of RAM to run smoothly.
4. I download the SSH key or set a password.
5. I connect to the VM via SSH:&#x20;
   ```bash
   ssh azureuser@<your-vm-public-ip>

   ```

I install Docker and Docker Compose on the VM:



bash sudo apt-get update sudo apt-get install docker.io docker-compose -y sudo usermod -aG docker $USER newgrp docker I clone my GitHub repository to the VM:



bash git clone [https://github.com/diixon/fpl-data-engineering.git](https://github.com/diixon/fpl-data-engineering.git) cd fpl-data-engineering I update the .env file in the VM. I change DB_HOST to point to the Azure PostgreSQL server address. I change DB_USER and DB_PASSWORD to the Azure DB credentials.



I run the pipeline:



bash docker-compose up -d I access the Airflow UI at http\://:8080 (username: admin, password: admin).



text

---

### Your Exact Steps to Execute Now:

1. **Save the Files**: Copy the content above and save them exactly as named in your project folder. Make sure `init-db.sh` is saved with **LF line endings** (I recommend using VS Code, or use the PowerShell command I gave you earlier).
2. **Clean and Rebuild**: Open your Command Prompt in the project folder and run these commands in order:&#x20;
   ```cmd
   docker-compose down -v

   ```

   (This deletes the old, broken database volume).



	```cmd
	docker-compose up -d --build
	
	```
	
	(This builds the new image and starts the containers fresh).