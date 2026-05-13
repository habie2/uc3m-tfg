#!/bin/bash
# Carga las variables (opcional si ya las tienes en el sistema)
export $(grep -v '^#' .env | xargs)

# Lanza psql usando las variables del .env
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -d $DB_NAME