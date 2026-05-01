import asyncio
import websockets
import json
import random
import string
import os
import time

PORT = int(os.environ.get("PORT", 8765))

clientes = {}
salas = {}

ARCHIVO_SALAS = "salas.json"
ARCHIVO_JUGADORES = "jugadores.json"

jugadores = {}


ultimo_guardado = 0
INTERVALO_GUARDADO = 5  



def cargar_salas():
    global salas

    if os.path.exists(ARCHIVO_SALAS):
        try:
            with open(ARCHIVO_SALAS, "r") as f:
                data = json.load(f)

                salas = {}

                for codigo in data:
                    salas[codigo] = []

                print("Salas cargadas:", list(salas.keys()))

        except Exception as e:
            print("Error cargando salas:", e)
            salas = {}



def cargar_jugadores():
    global jugadores

    if os.path.exists(ARCHIVO_JUGADORES):
        try:
            with open(ARCHIVO_JUGADORES, "r") as f:
                jugadores = json.load(f)
                print("Jugadores cargados:", len(jugadores))
        except:
            jugadores = {}



def guardar_salas():
    try:
        lista = list(salas.keys())

        with open(ARCHIVO_SALAS, "w") as f:
            json.dump(lista, f, indent=4)

    except Exception as e:
        print("Error guardando salas:", e)



def guardar_jugadores():
    global ultimo_guardado

    ahora = time.time()

    if ahora - ultimo_guardado < INTERVALO_GUARDADO:
        return

    ultimo_guardado = ahora

    try:
        with open(ARCHIVO_JUGADORES, "w") as f:
            json.dump(jugadores, f, indent=4)
    except Exception as e:
        print("Error guardando jugadores:", e)



def generar_codigo():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))



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
                "x": c.get("x", 0),
                "y": c.get("y", 0),
                "progreso": c.get("progreso", 0),
                "nivel": c.get("nivel", 0),
                "flip": c.get("flip", False)
            })

    await enviar_a_sala(codigo, {
        "tipo": "lista_jugadores",
        "jugadores": lista
    })



async def manejar(ws):

    print("Cliente conectado")

    try:

        async for mensaje in ws:

            try:
                data = json.loads(mensaje)
            except:
                print("JSON inválido")
                continue

            tipo = data.get("tipo", "")
            player_id = data.get("id")

            if not player_id and tipo not in ["listar_salas", "listar_jugadores"]:
                continue


            if tipo == "crear_sala":

                codigo = generar_codigo()
                salas[codigo] = [ws]

                if player_id in jugadores:
                    jugador_data = jugadores[player_id]
                    nombre = jugador_data.get("nombre", "Jugador")

                    if codigo in jugador_data.get("salas", {}):
                        pos = jugador_data["salas"][codigo]
                        x = pos.get("x", 100)
                        y = pos.get("y", 100)
                    else:
                        x = 100
                        y = 100
                else:
                    x = 100
                    y = 100
                    nombre = data.get("nombre", "Jugador")

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

                guardar_salas()

                await ws.send(json.dumps({
                    "tipo": "sala_creada",
                    "codigo": codigo
                }))

                print("Sala creada:", codigo)

                await enviar_lista_jugadores(codigo)


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

                if player_id in jugadores:
                    jugador_data = jugadores[player_id]
                    nombre = jugador_data.get("nombre", "Jugador")

                    if codigo in jugador_data.get("salas", {}):
                        pos = jugador_data["salas"][codigo]
                        x = pos.get("x", 100)
                        y = pos.get("y", 100)
                    else:
                        x = 100
                        y = 100
                else:
                    x = 100
                    y = 100
                    nombre = data.get("nombre", "Jugador")

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

                print("Jugador unido a", codigo)

                await enviar_lista_jugadores(codigo)


            elif tipo == "listar_salas":

                await ws.send(json.dumps({
                    "tipo": "salas",
                    "salas": list(salas.keys())
                }))


            elif tipo == "listar_jugadores":

                codigo = data.get("codigo", "")

                if codigo in salas:
                    await enviar_lista_jugadores(codigo)

            elif tipo == "movimiento":

                if ws not in clientes:
                    continue

                codigo = clientes[ws]["sala"]
                c = clientes[ws]

                
                if "x" in data:
                    c["x"] = data["x"]

                if "y" in data:
                    c["y"] = data["y"]

                if "progreso" in data:
                    c["progreso"] = data["progreso"]

                if "nivel" in data:
                    c["nivel"] = data["nivel"]

                if "flip" in data:
                    c["flip"] = data["flip"]

                if player_id not in jugadores:
                    jugadores[player_id] = {
                        "nombre": c["nombre"],
                        "salas": {}
                    }

                jugadores[player_id].setdefault("salas", {})

                jugadores[player_id]["salas"][codigo] = {
                    "x": c["x"],
                    "y": c["y"]
                }

                guardar_jugadores()

                data["nombre"] = c["nombre"]

                await enviar_a_sala(codigo, data)
                await enviar_lista_jugadores(codigo)

    except Exception as e:
        print("Cliente desconectado:", e)

    finally:

        if ws in clientes:

            codigo = clientes[ws]["sala"]
            jugador_id = clientes[ws].get("id")

            if codigo in salas:

                if ws in salas[codigo]:
                    salas[codigo].remove(ws)

                await enviar_a_sala(codigo, {
                    "tipo": "jugador_salio",
                    "id": jugador_id
                })

                await enviar_lista_jugadores(codigo)

                # eliminar sala vacía
                #if len(salas[codigo]) == 0:
                    #del salas[codigo]
                    #print("Sala eliminada:", codigo)

            del clientes[ws]

            guardar_salas()
            guardar_jugadores()


async def responder_http(path, request_headers):
    body = b"Servidor online"
    return (
        200,
        [("Content-Type", "text/plain")],
        body
    )

async def main():

    cargar_salas()
    cargar_jugadores()

    print("Servidor iniciado en puerto", PORT)

    async with websockets.serve(
        manejar,
        "0.0.0.0",
        PORT,
        process_request=responder_http
    ):
        await asyncio.Future()


asyncio.run(main())
