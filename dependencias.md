## Deletar o docker-compose
```
        sudo apt-get purge docker-compose
        sudo rm -rf /var/lib/docker-compose
        sudo rm -rf /usr/local/bin/docker-compose
```
##### Deletar o docker
```
        sudo apt-get update
        sudo apt-get purge docker-ce docker-ce-cli containerd.io
        sudo rm -rf /var/lib/docker
        sudo rm -rf /var/lib/containerd
```
obs.: Deletar caso tenha sido instalado anteriormente

##### Instalação do Docker no Ubunto 20.04.4

``` 
    sudo apt-get update
    sudo apt-get remove docker docker-engine docker.io containerd runc
    sudo apt-get update
```

instalando dependencias
```  
    sudo apt-get install apt-transport-https ca-certificates curl gnupg lsb-release
```

para fins de segurança, adicione a chave GPG oficial do Docker.
```
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

    echo \
    "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
    $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
```

instalando o docker
```
    sudo apt-get update
    sudo apt-get install docker-ce docker-ce-cli containerd.io
```

##### Instalação do docker-compose 1.29.2-1 no ubunto 20.04.4
```
    sudo apt update
    sudo apt upgrade
    sudo curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/bin/docker-compose
```

permissão
```
    sudo chmod +x /usr/bin/docker-compose
```

##### Criando o repositorio do projeto

   mkdir repo-amundsen
   chmod -R repo-amundsen
   cd repo-amundsen

##### docker-compose.yaml

   - criar uma pasta para baixar o dockerfile do amundsen git clone --recursive https://github.com/amundsen-io/amundsen.git, apos o download copie o conteudo centralizando em um unico arquivo.
   - criar uma pasta para baixar o dockerfile do airflow git clone https://github.com/danilosousadba/airflow.git, apos o download copiar o conteudo para mesclar em um unico arquivo e alterar a versão para 2.2.2
   - arquivo final em: https://github.com/weslleyfelix/amundsen.git

   docker-compose up -d = subir imagem
