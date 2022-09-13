# Comandos Úteis

## Comandos docker

### docker run  
Executa uma imagem ex: 
```
docker run hello-world
```
Ou 
```
docker run ubuntu /bin/bash
```
Obs.: Este último baixa a imagem do ubunto e roda o bash para executarmos comandos.

### Redirecionamento de porta 
```
docker run -d -p 8080:80 nginx
```
Obs.: Toda vez que eu acessar a porta 8080 ele redireciona para a 80 do servidor nginx.

### Executando. nomeando a imagem e redirecionando a porta em uma linha.
```
docker run --name nginx -d -p 8080:80 nginx
```

### docker ps  
Ver os containers em execução.

### docker ps -a 
Mostra os containers que estavam rodando e agora estão parados.

### docker start 
Iniciar algum container que estava parado ex: 
```
docker start <container id ou name>
```
  
### docker stop
Parar o container ex: 
```
docker stop <container id ou name>
```
  
### docker rm
Remover do histórico ex: 
```  
docker rm -f <container id ou name>
```
Obs.: Ao remover o container e recriar perdemos as alterações.

### docker exec
Executar comando dentro do container ex: 
```
docker exec <name ex: nginx> ls
```
O Comanto -it entra de forma interativa permitindo programar no container ex: 
```
docker exec -it nginx bash
```
Obs.:A Partir deste momento estamos logado no container, control +d sai do container.
  
### docker images
Ver as imagens instaladas em meu computador.

### docker build
Criar uma imagem a partir de um docker file ex: 
```
docker build -t <nome da imagem/tag> .
```
Obs.: O ponto representa o dockerfile dentro da pasta  [docker build -t projeto_teste/golang-app-docker .]
  
### docker-compose down
Mata tudo o que subimos no arquivo docker-compose.yaml.
  
### docker rmi
Deletar a imagem do seu docker ex: 
```
docker rmi nginx
```
### docker system prune -a 
Limpa Todas as Imagens, Contêineres, Volumes e Redes não Utilizadas ou Pendentes.
  
### reapontando volumes 
Editar a variável dentro do docker-compose.yaml.
``` 
volumes: - ./nginx:/usr/share/nginx/html
```
