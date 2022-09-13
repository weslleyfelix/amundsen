# Comandos Úteis

## Comandos docker

#### docker run  
executa uma imagem ex: 
```
docker run hello-world
```
ou 
```
docker run ubuntu /bin/bash
```
Obs.: este último baixa a imagem do ubunto e roda o bash para executarmos comandos

#### redirecionamento de porta 
```
docker run -d -p 8080:80 nginx
```
Obs.: Toda vez que eu acessar a porta 8080 ele redireciona para a 80 do servidor nginx 

####Executando. nomeando a imagem e redirecionando a porta em uma linha
```
docker run --name nginx -d -p 8080:80 nginx
```

docker ps  = ver os containers em execução;
docker ps -a =  mostra os containers que estavam rodando e agora estão parados
docker start =  iniciar algum container que estava parado ex: [docker start <container id ou name>]
docker stop = parar o container ex [docker stop <container id ou name>]
docker rm = remover do historico ex: [docker rm <container id ou name>]
Obs.: Ao remover o container e recriar perdemos as alterações [docker rm -f <container id ou name>]

docker exec = executar comando dentro do container ex : [docker exec <name ex: nginx> ls ]
Obs.: o comanto -it entra de forma interativa permitindo programar no container ex: [docker exec -it nginx bash ] = a partir deste momento estamos logado no container, control +d sai do container

docker images = ver as imagens instaladas em meu computador.

docker build = criar uma imagem a partir de um docker file ex: [docker build -t <nome da imagem/tag> .]
Obs.: O ponto representa o dockerfile dentro da pasta  [docker build -t projeto_teste/golang-app-docker .]
reapontando volumes = volumes: - ./nginx:/usr/share/nginx/html
docker-compose down = mata tudo o que subimos no arquivo docker-compose.yaml
docker rmi = deletar a imagem do seu docker ex [docker rmi nginx]
docker system prune -a = Limpando Todas as Imagens, Contêineres, Volumes e Redes não Utilizadas ou Pendentes
