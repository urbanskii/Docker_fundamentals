import requests
import json
import urllib3
import time
from getpass import getpass

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configurações do Proxmox
proxmox_url = 'https://192.168.1.45:8006/api2/json'
node = 'front'
storage = 'local-lvm'

# Coleta do nome de usuário e senha do Proxmox
proxmox_user = input("Enter your Proxmox username: ")
proxmox_password = getpass("Enter your Proxmox password: ")

# Autenticação
response = requests.post(f'{proxmox_url}/access/ticket', data={
    'username': proxmox_user,
    'password': proxmox_password
}, verify=False)  # Ignora verificação SSL
response.raise_for_status()  # Garante que exceções sejam levantadas para códigos de erro HTTP
data = response.json()['data']
ticket = data['ticket']
csrf_token = data['CSRFPreventionToken']
headers = {
    'CSRFPreventionToken': csrf_token,
    'Cookie': f'PVEAuthCookie={ticket}'
}

# Função para criar container
def create_container(ct_id, hostname, ip_address):
    payload = {
        'vmid': ct_id,
        'hostname': hostname,
        'memory': 2048,
        'cores': 4,
        'swap': 2048,
        'ostemplate': 'local:vztmpl/ubuntu-22.04-standard_22.04-1_amd64.tar.zst',
        'password': 'root_password',
        'net0': f'name=eth0,bridge=vmbr1,ip={ip_address}/24,gw=192.168.0.1',
        'rootfs': 'local-lvm:20',  # Especifica o armazenamento e o tamanho do disco corretamente
        'start': 1
    }
    try:
        response = requests.post(f'{proxmox_url}/nodes/{node}/lxc', headers=headers, json=payload, verify=False)  # Alterando 'data' para 'json' para enviar como JSON
        response.raise_for_status()  # Garante que exceções sejam levantadas para códigos de erro HTTP
        print(response.json())
        return True
    except requests.exceptions.HTTPError as err:
        print(f"Erro ao criar container {hostname}: {err.response.text}")
        return False

# Função para executar script em um container
def execute_script_in_container(ct_id):
    script = '''#!/bin/bash

# Verifica se o arquivo de sinalização existe
if [ ! -f /var/log/installation_complete ]; then
    # Atualizações do sistema e instalação de pacotes
    apt update -y
    apt upgrade -y
    apt-get install -y ca-certificates curl
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc

    # Adiciona o repositório do Docker ao Apt sources
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
      tee /etc/apt/sources.list.d/docker.list > /dev/null

    apt-get update

    # Instalação do Docker e outros pacotes relacionados
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    # Criação do arquivo de sinalização para indicar que as instalações foram concluídas
    touch /var/log/installation_complete
fi'''
    
    payload = {'command': ['/bin/bash', '-c', script]}
    try:
        response = requests.post(f'{proxmox_url}/nodes/{node}/lxc/{ct_id}/exec', headers=headers, json=payload, verify=False)
        response.raise_for_status()
        print(f"Script execution in container {ct_id} successful")
    except requests.exceptions.HTTPError as err:
        print(f"Error executing script in container {ct_id}: {err.response.text}")

# Criar 4 containers
base_ip = '192.168.0.'
container_ids = []

for i in range(1, 5):
    ct_id = 200 + i
    hostname = f'docker{i}'
    ip_address = base_ip + str(30 + i - 1)
    if create_container(ct_id, hostname, ip_address):
        container_ids.append(ct_id)

# Aguarda 30 segundos após a criação de todos os contêineres
print("Waiting 30 seconds before executing scripts in containers...")
time.sleep(300)

# Executa o script em todos os contêineres criados
for ct_id in container_ids:
    execute_script_in_container(ct_id)
