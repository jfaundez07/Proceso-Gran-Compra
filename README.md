# Proceso Gran Compra

### Paso 1: Levantar el proyecto y ejecutar el ETL  
Iniciar los contenedores (PostgreSQL y Python) en segundo plano:
```bash
docker compose up --build -d
```
Ver el progreso del script de Python en tiempo real mirando los logs de ese contenedor:
```bash
docker compose logs -f etl
```

### Paso 2: Verificar las tablas en la Base de Datos
Conectarse directamente a la base de datos dentro del contenedor y listar las tablas creadas:
```bash
docker exec -it postgres_db psql -U postgres -d grandes_compras -c "\dt"
```
Para entrar de forma interactiva y analizar los datos:
```bash
docker exec -it postgres_db psql -U postgres -d grandes_compras
```
### Paso 3: Detener y limpiar el proyecto
Apagar los contenedores y remover las redes creadas por el orquestador:
```bash
docker compose down
```
*(Opcional) Para detener el proyecto y **además** borrar los datos la base de datos de PostgreSQL para empezar desde cero en la próxima ejecución, añadir el flag `-v` a ese comando (que borra el volumen `pgdata`):*
```bash
docker compose down -v
```