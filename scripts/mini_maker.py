import os
import json
import csv
import sys

def crear_archivo_mini(ruta_archivo):
    # Separar el nombre del archivo y su extensión
    nombre_base, extension = os.path.splitext(ruta_archivo)
    extension = extension.lower()
    
    # Crear el nombre del nuevo archivo
    ruta_salida = f"{nombre_base}_mini{extension}"

    # Procesar archivo JSON
    if extension == '.json':
        try:
            with open(ruta_archivo, 'r', encoding='utf-8') as f:
                datos = json.load(f)
            
            # Verificamos que el JSON sea una lista de objetos
            if isinstance(datos, list):
                datos_mini = datos[:10] # Tomamos los primeros 10
            else:
                print("Error: El archivo JSON principal debe ser una lista [...] para extraer los primeros 10 elementos.")
                return

            with open(ruta_salida, 'w', encoding='utf-8') as f:
                json.dump(datos_mini, f, indent=4, ensure_ascii=False)
            
            print(f"¡Éxito! Archivo guardado como: {ruta_salida}")

        except FileNotFoundError:
            print(f"Error: No se encontró el archivo '{ruta_archivo}'.")
        except Exception as e:
            print(f"Error al procesar el JSON: {e}")

    # Procesar archivo CSV
    elif extension == '.csv':
        try:
            with open(ruta_archivo, 'r', encoding='utf-8') as f_in:
                lector = csv.reader(f_in)
                filas_mini = []
                
                # Extraer el encabezado + 10 filas de datos (11 líneas en total)
                for i, fila in enumerate(lector):
                    if i < 11: 
                        filas_mini.append(fila)
                    else:
                        break
            
            with open(ruta_salida, 'w', encoding='utf-8', newline='') as f_out:
                escritor = csv.writer(f_out)
                escritor.writerows(filas_mini)

            print(f"¡Éxito! Archivo guardado como: {ruta_salida}")

        except FileNotFoundError:
            print(f"Error: No se encontró el archivo '{ruta_archivo}'.")
        except Exception as e:
            print(f"Error al procesar el CSV: {e}")
            
    else:
        print(f"Formato '{extension}' no soportado. Por favor, usa un archivo .json o .csv")

# --- Bloque principal de ejecución ---
if __name__ == "__main__":
    # Comprobamos si el usuario ha pasado el nombre del archivo como argumento
    if len(sys.argv) < 2:
        print("Uso incorrecto.")
        print("Debes ejecutar el programa así: python programa.py <nombre_del_archivo>")
    else:
        # sys.argv[1] contiene el primer argumento que le pasas después de programa.py
        archivo_entrada = sys.argv[1]
        crear_archivo_mini(archivo_entrada)