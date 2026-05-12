import pandas as pd
import glob
import unicodedata
import re
import os
import psycopg2
from psycopg2 import sql
from sqlalchemy import create_engine

# --- CONFIGURACIÓN DE CONEXIÓN ---
# Se utilizan variables de entorno (definidas en el .env de Docker)
DB_USER = os.environ.get("POSTGRES_USER")
DB_PASS = os.environ.get("POSTGRES_PASSWORD") 
DB_HOST = os.environ.get("POSTGRES_HOST")
DB_PORT = os.environ.get("POSTGRES_PORT")
DB_NAME = os.environ.get("POSTGRES_DB")

def preparar_entorno_db():
    """Conecta a Postgres para crear la DB y las tablas desde cero."""
    print("0. Configurando Base de Datos y Tablas...")
    
    # 1. Crear la Base de Datos (si no existe)
    # Nos conectamos a la db 'postgres' (la que viene por defecto) para poder crear la nueva
    conn = psycopg2.connect(dbname='postgres', user=DB_USER, password=DB_PASS, host=DB_HOST, port=DB_PORT)
    conn.autocommit = True
    cursor = conn.cursor()
    
    try:
        cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DB_NAME)))
        print(f" -> Base de datos '{DB_NAME}' creada exitosamente.")
    except psycopg2.errors.DuplicateDatabase:
        print(f" -> La base de datos '{DB_NAME}' ya existe. Continuando...")
    finally:
        cursor.close()
        conn.close()

    # 2. Crear las Tablas (Conectándonos ahora a la DB real)
    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST, port=DB_PORT)
    conn.autocommit = True
    cursor = conn.cursor()

    # Script SQL para borrar y crear todo segun tu diagrama
    script_tablas = f"""
    DROP TABLE IF EXISTS adjudicacion CASCADE;
    DROP TABLE IF EXISTS grancompra CASCADE;
    DROP TABLE IF EXISTS detallecompra CASCADE;
    DROP TABLE IF EXISTS producto CASCADE;
    DROP TABLE IF EXISTS proveedor CASCADE;
    DROP TABLE IF EXISTS institucion CASCADE;
    DROP TABLE IF EXISTS convenio CASCADE;
    DROP TABLE IF EXISTS licitacion CASCADE;
    DROP TABLE IF EXISTS ordencompra CASCADE;

    CREATE TABLE ordencompra (
        codigooc TEXT PRIMARY KEY,
        nombreoc TEXT,
        fechaenviooc TIMESTAMP,
        fechainvitacion TIMESTAMP,
        fechafininvitacion TIMESTAMP,
        estadooc TEXT
    );

    CREATE TABLE licitacion (
        nrolicitacionpublica TEXT PRIMARY KEY
    );

    CREATE TABLE convenio (
        idconveniomarco INT PRIMARY KEY,
        conveniomarco TEXT
    );

    CREATE TABLE institucion (
        rutunidadcompra VARCHAR(12) PRIMARY KEY,
        institucion TEXT,
        unidadcompra TEXT,
        razonsocialcomprador TEXT,
        direccionunidadcompra TEXT,
        comunaunidadcompra TEXT
    );

    CREATE TABLE proveedor (
        rutproveedor VARCHAR(12) PRIMARY KEY,
        nombreproveedor TEXT
    );

    CREATE TABLE producto (
        idproductocm INT PRIMARY KEY,
        nombreproducto TEXT,
        tipoproducto TEXT,
        preciotienda INT
    );

    CREATE TABLE detallecompra (
        iddetallecompra INT PRIMARY KEY,
        precioofertaespecial INT,
        descuentoaplicado INT,
        cantidadfinal INT,
        precioofertafinal INT,
        idproductocm INT REFERENCES producto(idproductocm)
    );

    CREATE TABLE grancompra (
        idgrancompra INT PRIMARY KEY,
        codigooc TEXT REFERENCES ordencompra(codigooc),
        nrolicitacionpublica TEXT REFERENCES licitacion(nrolicitacionpublica),
        idconveniomarco INT REFERENCES convenio(idconveniomarco),
        rutunidadcompra VARCHAR(12) REFERENCES institucion(rutunidadcompra)
    );

    CREATE TABLE adjudicacion (
        idgrancompra INT REFERENCES grancompra(idgrancompra),
        rutproveedor VARCHAR(12) REFERENCES proveedor(rutproveedor),
        iddetallecompra INT REFERENCES detallecompra(iddetallecompra),
        adjudicado TEXT
    );
    """
    
    try:
        cursor.execute(script_tablas)
        print(" -> Tablas creadas/reiniciadas exitosamente segun el diagrama.")
    except Exception as e:
        print(f" -> Error creando tablas: {e}")
    finally:
        cursor.close()
        conn.close()

# --- FUNCIONES DE LIMPIEZA (Tus funciones originales) ---

def estandarizar_texto(df):
    cols_texto = df.select_dtypes(include=['object', 'string']).columns
    for col in cols_texto:
        df[col] = df[col].astype(str).str.upper().str.strip()
        df[col] = df[col].str.replace('Ñ', 'N', regex=False)
        def quitar_acentos(texto):
            if pd.isna(texto) or texto == 'NAN': return None
            texto_norm = unicodedata.normalize('NFKD', str(texto))
            return "".join([c for c in texto_norm if not unicodedata.combining(c)])
        df[col] = df[col].apply(quitar_acentos)
    return df

def limpiar_enteros(df, columnas):
    for col in columnas:
        if col in df.columns:
            col_temporal = df[col].astype(str).str.replace('.', '', regex=False)
            df[col] = pd.to_numeric(col_temporal, errors='coerce').astype('Int64')
    return df

def formatear_rut(rut):
    if pd.isna(rut) or str(rut).strip() == '' or str(rut).strip() == 'NAN': return rut
    rut_str = str(rut).upper()
    rut_limpio = re.sub(r'[^0-9K]', '', rut_str)
    if len(rut_limpio) < 2: return rut
    cuerpo = rut_limpio[:-1]
    dv = rut_limpio[-1]
    try:
        cuerpo_formateado = f"{int(cuerpo):,}".replace(',', '.')
        return f"{cuerpo_formateado}-{dv}"
    except ValueError: return rut

def ejecutar_etl_total():
    # 1. Preparar la DB (Crear todo)
    preparar_entorno_db()

    print("\n1. Leyendo archivos originales...")
    archivos_procesos = glob.glob("Cuatrimestre_*/*.csv")
    df_procesos = pd.concat([pd.read_csv(f, sep=';', encoding='utf-8', low_memory=False) for f in archivos_procesos], ignore_index=True)
    
    archivos_prov = glob.glob("Proveedores/Info_Principales_Proveedores_2025*.csv")
    df_prov_raw = pd.concat([pd.read_csv(f, sep=';', encoding='utf-8', low_memory=False) for f in archivos_prov], ignore_index=True)
    
    print("2. Estandarizando y Limpiando datos...")
    df_procesos.columns = df_procesos.columns.str.strip()
    df_prov_raw.columns = df_prov_raw.columns.str.strip()

    df_procesos = estandarizar_texto(df_procesos)
    df_prov_raw = estandarizar_texto(df_prov_raw)

    # Renombrado inteligente
    for col in df_procesos.columns:
        if 'LICITACION' in str(col).upper(): df_procesos = df_procesos.rename(columns={col: 'NroLicitacionPublica'})
    for col in df_prov_raw.columns:
        col_str = str(col).upper()
        if 'RUT' in col_str: df_prov_raw = df_prov_raw.rename(columns={col: 'RutProveedor'})
        elif 'NOMBRE' in col_str: df_prov_raw = df_prov_raw.rename(columns={col: 'NombreProveedor'})

    df_procesos['RutProveedor'] = df_procesos['RutProveedor'].apply(formatear_rut)
    df_prov_raw['RutProveedor'] = df_prov_raw['RutProveedor'].apply(formatear_rut)
    df_procesos['RutUnidadCompra'] = df_procesos['RutUnidadCompra'].apply(formatear_rut)

    if 'IdDetalleCompra' not in df_procesos.columns:
        df_procesos['IdDetalleCompra'] = range(1, len(df_procesos) + 1)

    cols_int = ['IdProductoCM', 'PrecioTienda', 'IdConvenioMarco', 'PrecioOfertaEspecial', 
                'DescuentoAplicado', 'CantidadFinal', 'PrecioOfertaFinal', 'IdGranCompra']
    df_procesos = limpiar_enteros(df_procesos, cols_int)

    # Fechas con el fix de format='mixed'
    cols_fechas = ['FechaEnvioOC', 'FechaInvitacion', 'FechaFinInvitacion']
    for col in cols_fechas:
        if col in df_procesos.columns:
            df_procesos[col] = df_procesos[col].astype(str).str.strip()
            df_procesos[col] = df_procesos[col].replace(['nan', 'NAN', 'NONE', 'None', ''], pd.NA)
            df_procesos[col] = pd.to_datetime(df_procesos[col], errors='coerce', dayfirst=True, format='mixed')

    print("3. Preparando DataFrames para PostgreSQL...")

    df_proveedor = pd.concat([df_prov_raw[['RutProveedor', 'NombreProveedor']], df_procesos[['RutProveedor', 'NombreProveedor']]]).dropna(subset=['RutProveedor']).drop_duplicates(subset=['RutProveedor'])
    df_producto = df_procesos[['IdProductoCM', 'NombreProducto', 'TipoProducto', 'PrecioTienda']].dropna(subset=['IdProductoCM']).drop_duplicates(subset=['IdProductoCM'])
    df_oc = df_procesos[['CodigoOC', 'NombreOC', 'FechaEnvioOC', 'FechaInvitacion', 'FechaFinInvitacion', 'EstadoOC']].dropna(subset=['CodigoOC']).drop_duplicates(subset=['CodigoOC'])
    df_licitacion = df_procesos[['NroLicitacionPublica']].dropna(subset=['NroLicitacionPublica']).drop_duplicates(subset=['NroLicitacionPublica'])
    df_convenio = df_procesos[['IdConvenioMarco', 'ConvenioMarco']].dropna(subset=['IdConvenioMarco']).drop_duplicates(subset=['IdConvenioMarco'])
    
    df_institucion = df_procesos[['RutUnidadCompra', 'Institucion', 'UnidadCompra', 'RazonSocialComprador', 'DireccionUnidadCompra', 'ComunaUnidadCompra']].dropna(subset=['RutUnidadCompra']).drop_duplicates(subset=['RutUnidadCompra'])
    df_institucion['DireccionUnidadCompra'] = df_institucion['DireccionUnidadCompra'].fillna('NO OBTENIDO / NO ENCONTRADO').replace(['NAN', 'NONE', ''], 'NO OBTENIDO / NO ENCONTRADO')

    df_detalle = df_procesos[['IdDetalleCompra', 'PrecioOfertaEspecial', 'DescuentoAplicado', 'CantidadFinal', 'PrecioOfertaFinal', 'IdProductoCM']].dropna(subset=['IdDetalleCompra']).drop_duplicates(subset=['IdDetalleCompra'])
    df_grancompra = df_procesos[['IdGranCompra', 'CodigoOC', 'NroLicitacionPublica', 'IdConvenioMarco', 'RutUnidadCompra']].dropna(subset=['IdGranCompra']).drop_duplicates(subset=['IdGranCompra'])
    df_adjudicacion = df_procesos[['IdGranCompra', 'RutProveedor', 'IdDetalleCompra', 'Adjudicado']].dropna(subset=['IdGranCompra', 'RutProveedor'])

    print("4. Iniciando Carga masiva en PostgreSQL...")
    cadena_conexion = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    
    try:
        engine = create_engine(cadena_conexion)
        tablas_a_cargar = [
            ('proveedor', df_proveedor), ('producto', df_producto), ('ordencompra', df_oc),
            ('licitacion', df_licitacion), ('convenio', df_convenio), ('institucion', df_institucion),
            ('detallecompra', df_detalle), ('grancompra', df_grancompra), ('adjudicacion', df_adjudicacion)
        ]

        for nombre_tabla, df_final in tablas_a_cargar:
            df_final.columns = df_final.columns.str.lower()
            print(f" -> Cargando {nombre_tabla} ({len(df_final)} filas)...")
            df_final.to_sql(nombre_tabla, engine, if_exists='append', index=False)
            print(f"    [OK] {nombre_tabla} cargada.")

    except Exception as e:
        print(f" Error durante la carga: {e}")

    print("\n¡PROCESO COMPLETO EXITOSO! Base de datos creada, tablas listas y datos cargados. 🚀")

if __name__ == "__main__":
    ejecutar_etl_total()