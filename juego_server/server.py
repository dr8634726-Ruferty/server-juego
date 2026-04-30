import asyncio
import websockets
import json
import random
import string
import sqlite3
import os

# ==========================
# CONFIG
# ==========================
PORT = int(os.environ.get("PORT", 8765"))

clientes = {}
salas = {}

DB = "juego.db"


# ==========================
# SQLITE
# ==========================
def iniciar_db():

    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS salas (
        codigo TEXT PRIMARY KEY
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS jugadores (
        id TEXT PRIMARY KEY,
        nombre TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS posiciones (
        jugador_id TEXT,
        sala TEXT,
        x INTEGER,
        y INTEGER,
        PRIMARY KEY (jugador_id, sala)
    )
    """)

    conn.commit()
    conn.close()


# ==========================
# SALAS
# ==========================
def cargar_salas():
    global salas

    salas = {}

    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    filas = cur.execute("SELECT codigo FROM salas").fetchall()

    for row in filas:
        salas[row[0]] = []

    conn.close()

    print("Salas cargadas:", list(salas.keys()))


def guardar_sala(codigo):

    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute(
        "INSERT OR IGNORE INTO salas (codigo) VALUES (?)",
        (codigo,)
    )

    conn.commit()
    conn.close()


# ==========================
# JUGADORES
# ==========================
def guardar_jugador(player_id, nombre):

    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute("""
    INSERT OR REPLACE INTO jugadores (id,nombre)
    VALUES (?,?)
    """, (player_id, nombre))

    conn.commit()
    conn.close()


def guardar_posicion(player_id, sala, x, y):

    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute("""
    INSERT OR REPLACE INTO posiciones (jugador_id,sala,x,y)
    VALUES (?,?,?,?)
    """, (player_id, sala, x, y))

    conn.commit()
    conn.close()


def cargar_posicion(player_id, sala):

    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    fila = cur.execute("""
    SELECT x,y FROM posiciones
    WHERE jugador_id=? AND sala=?
    """, (player_id, sala)).fetchone()

    conn.close()

    if fila:
        return fila[0], fila[1]

    return 100, 100


def cargar_nombre(player_id):

    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    fila = cur.execute("""
    SELECT nombre FROM jugadores
    WHERE id=?
    """, (player_id,)).fetchone()

    conn.close()

    if fila:
        return fila[0]

    return "Jugador"


# ==========================
# CODIGO SALA
# ==========================
def generar_codigo():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


# ==========================
# ENVIAR A SALA
# ==========================
async def enviar_a_sala(codigo, data):

    if codigo not in salas:
        return

    mensaje = json.dumps(data)

    for ws in list(salas[codigo]):
        try:
            await ws.send(mensaje)
        except:
            if ws in salas[codigo]:
                salas[codigo].remove(ws)


# ==========================
# LISTA JUGADORES
# ==========================
async def enviar_lista_jugadores(codigo):

    if codigo not in salas:
        return

    lista = []

    for ws in salas[codigo]:

        if ws in clientes:

            c = clientes[ws]

            lista.append({
                "id": c["id"],
                "nombre": c["nombre"],
                "x": c["x"],
                "y": c["y"],
                "progreso": c.get("progreso", 0),
                "nivel": c.get("nivel", 0),
                "flip": c.get("flip", False)
            })

    await enviar_a_sala(codigo, {
        "tipo": "lista_jugadores",
        "jugadores": lista
    })


# ==========================
# CLIENTE
# ==========================
async def manejar(ws):

    print("Cliente conectado")

    try:

        async for mensaje in ws:

            try:
                data = json.loads(mensaje)
            except:
                continue

            tipo = data.get("tipo", "")
            player_id = data.get("id")

            # ==================
            # CREAR SALA
            # ==================
            if tipo == "crear_sala":

                codigo = generar_codigo()

                salas[codigo] = [ws]
                guardar_sala(codigo)

                nombre = data.get("nombre", "Jugador")

                guardar_jugador(player_id, nombre)

                x, y = cargar_posicion(player_id, codigo)

                clientes[ws] = {
                    "sala": codigo,
                    "id": player_id,
                    "nombre": nombre,
                    "x": x,
                    "y": y,
                    "progreso": 0,
                    "nivel": 0,
                    "flip": False
                }

                await ws.send(json.dumps({
                    "tipo": "sala_creada",
                    "codigo": codigo
                }))

                await enviar_lista_jugadores(codigo)

            # ==================
            # UNIRSE
            # ==================
            elif tipo == "unirse_sala":

                codigo = data.get("codigo", "")

                if codigo not in salas:

                    await ws.send(json.dumps({
                        "tipo": "error",
                        "mensaje": "Sala no existe"
                    }))
                    continue

                if ws not in salas[codigo]:
                    salas[codigo].append(ws)

                nombre = cargar_nombre(player_id)

                if nombre == "Jugador":
                    nombre = data.get("nombre", "Jugador")

                guardar_jugador(player_id, nombre)

                x, y = cargar_posicion(player_id, codigo)

                clientes[ws] = {
                    "sala": codigo,
                    "id": player_id,
                    "nombre": nombre,
                    "x": x,
                    "y": y,
                    "progreso": 0,
                    "nivel": 0,
                    "flip": False
                }

                await ws.send(json.dumps({
                    "tipo": "unido",
                    "codigo": codigo
                }))

                await enviar_lista_jugadores(codigo)

            # ==================
            # LISTAR SALAS
            # ==================
            elif tipo == "listar_salas":

                await ws.send(json.dumps({
                    "tipo": "salas",
                    "salas": list(salas.keys())
                }))

            # ==================
            # LISTAR JUGADORES
            # ==================
            elif tipo == "listar_jugadores":

                codigo = data.get("codigo", "")

                await enviar_lista_jugadores(codigo)

            # ==================
            # MOVIMIENTO
            # ==================
            elif tipo == "movimiento":

                if ws not in clientes:
                    continue

                c = clientes[ws]
                codigo = c["sala"]

                c["x"] = data.get("x", c["x"])
                c["y"] = data.get("y", c["y"])
                c["progreso"] = data.get("progreso", 0)
                c["nivel"] = data.get("nivel", 0)
                c["flip"] = data.get("flip", False)

                guardar_jugador(player_id, c["nombre"])
                guardar_posicion(player_id, codigo, c["x"], c["y"])

                data["nombre"] = c["nombre"]

                await enviar_a_sala(codigo, data)
                await enviar_lista_jugadores(codigo)

    except Exception as e:
        print("Desconectado:", e)

    finally:

        if ws in clientes:

            codigo = clientes[ws]["sala"]
            jugador_id = clientes[ws]["id"]

            if codigo in salas and ws in salas[codigo]:
                salas[codigo].remove(ws)

                await enviar_a_sala(codigo, {
                    "tipo": "jugador_salio",
                    "id": jugador_id
                })

                await enviar_lista_jugadores(codigo)

            del clientes[ws]


# ==========================
# MAIN
# ==========================
async def main():

    iniciar_db()
    cargar_salas()

    print("Servidor iniciado en puerto", PORT)

    async with websockets.serve(manejar, "0.0.0.0", PORT):
        await asyncio.Future()


asyncio.run(main())