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
vacas_por_sala = {}

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
                salas = {codigo: [] for codigo in data}
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
        except Exception as e:
            print("Error cargando jugadores:", e)
            jugadores = {}


def guardar_salas():
    try:
        lista = list(salas.keys())
        with open(ARCHIVO_SALAS, "w") as f:
            json.dump(lista, f, indent=4)
    except Exception as e:
        print("Error guardando salas:", e)


def guardar_jugadores(forzado=False):
    global ultimo_guardado
    ahora = time.time()
    if not forzado and (ahora - ultimo_guardado < INTERVALO_GUARDADO):
        return

    ultimo_guardado = ahora
    try:
        with open(ARCHIVO_JUGADORES, "w") as f:
            json.dump(jugadores, f, indent=4)
    except Exception as e:
        print("Error guardando jugadores:", e)


def generar_codigo():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


def crear_vacas_para_sala(codigo):
    vacas_por_sala[codigo] = {}


async def loop_vacas():
    while True:
        await asyncio.sleep(0.1)

        for codigo, vacas in list(vacas_por_sala.items()):
            if codigo not in salas:
                continue

            for vid, v in list(vacas.items()):
                if v.get("siguiendo") is not None:
                    v["tiempo_seguir"] -= 0.1

                    if v["tiempo_seguir"] <= 0:
                        v["siguiendo"] = None
                    else:
                        player_obj = None
                        for ws2 in list(salas.get(codigo, [])):
                            if ws2 in clientes and str(clientes[ws2]["id"]) == str(v["siguiendo"]):
                                player_obj = clientes[ws2]
                                break

                        if player_obj:
                            dx = player_obj["x"] - v["x"]
                            dy = player_obj["y"] - v["y"]
                            dist = max((dx ** 2 + dy ** 2) ** 0.5, 0.01)

                            v["x"] += (dx / dist) * 6
                            v["y"] += (dy / dist) * 6
                            flip = dx < 0

                            await enviar_a_sala(codigo, {
                                "tipo": "npc_movimiento",
                                "id": vid,
                                "x": v["x"],
                                "y": v["y"],
                                "flip": flip,
                                "siguiendo": True
                            })
                        else:
                            await enviar_a_sala(codigo, {
                                "tipo": "npc_movimiento",
                                "id": vid,
                                "x": v["x"],
                                "y": v["y"],
                                "flip": False,
                                "siguiendo": False
                            })
                        continue

                v["tiempo"] -= 0.1
                if v["tiempo"] <= 0:
                    v["tiempo"] = random.uniform(1, 3)
                    v["dir_x"] = random.uniform(-1, 1)
                    v["dir_y"] = random.uniform(-1, 1)

                velocidad = 2
                v["x"] += v["dir_x"] * velocidad
                v["y"] += v["dir_y"] * velocidad
                flip = v["dir_x"] < 0

                await enviar_a_sala(codigo, {
                    "tipo": "npc_movimiento",
                    "id": vid,
                    "x": v["x"],
                    "y": v["y"],
                    "flip": flip,
                    "siguiendo": False
                })


async def loop_guardado_autoclean():
    while True:
        await asyncio.sleep(INTERVALO_GUARDADO)
        guardar_jugadores(forzado=True)


async def enviar_a_sala(codigo, data):
    if codigo not in salas:
        return

    mensaje = json.dumps(data)
    for ws in list(salas[codigo]):
        try:
            await ws.send(mensaje)
        except Exception:
            if ws in salas[codigo]:
                salas[codigo].remove(ws)


async def enviar_lista_jugadores(codigo):
    if codigo not in salas:
        return

    lista = []
    for ws in list(salas[codigo]):
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
            except Exception:
                print("JSON inválido")
                continue

            tipo = data.get("tipo", "")
            player_id = data.get("id")

            tipos_sin_id = ["listar_salas", "listar_jugadores"]
            if tipo not in tipos_sin_id and not player_id:
                if ws in clientes:
                    player_id = clientes[ws]["id"]
                else:
                    continue

            if tipo == "crear_sala":
                codigo = generar_codigo()
                salas[codigo] = [ws]
                crear_vacas_para_sala(codigo)

                if player_id in jugadores:
                    jugador_data = jugadores[player_id]
                    nombre = jugador_data.get("nombre", "Jugador")
                    pos = jugador_data.get("salas", {}).get(codigo, {})
                    x = pos.get("x", 100)
                    y = pos.get("y", 100)
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
                await ws.send(json.dumps({"tipo": "sala_creada", "codigo": codigo}))
                print("Sala creada:", codigo)
                await enviar_lista_jugadores(codigo)

            elif tipo == "unirse_sala":
                codigo = data.get("codigo", "")
                if codigo not in salas:
                    await ws.send(json.dumps({"tipo": "error", "mensaje": "Sala no existe"}))
                    continue

                if ws not in salas[codigo]:
                    salas[codigo].append(ws)

                if codigo not in vacas_por_sala:
                    crear_vacas_para_sala(codigo)

                if player_id in jugadores:
                    jugador_data = jugadores[player_id]
                    nombre = jugador_data.get("nombre", "Jugador")
                    pos = jugador_data.get("salas", {}).get(codigo, {})
                    x = pos.get("x", 100)
                    y = pos.get("y", 100)
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

                await ws.send(json.dumps({"tipo": "unido", "codigo": codigo}))
                print("Jugador unido a", codigo)
                await enviar_lista_jugadores(codigo)

            elif tipo == "listar_salas":
                await ws.send(json.dumps({"tipo": "salas", "salas": list(salas.keys())}))

            elif tipo == "listar_jugadores":
                codigo = data.get("codigo", "")
                if codigo in salas:
                    await enviar_lista_jugadores(codigo)

            elif tipo == "spawn_npc":
                if ws not in clientes:
                    continue
                codigo = clientes[ws]["sala"]

                if codigo not in vacas_por_sala:
                    vacas_por_sala[codigo] = {}

                vaca_id = data.get("id")
                vaca = {
                    "x": data.get("x", 100),
                    "y": data.get("y", 100),
                    "dir_x": random.uniform(-1, 1),
                    "dir_y": random.uniform(-1, 1),
                    "tiempo": random.uniform(1, 3),
                    "siguiendo": None,
                    "tiempo_seguir": 0
                }
                vacas_por_sala[codigo][vaca_id] = vaca
                print("🐄 Vaca creada:", vaca_id, "en sala", codigo)

                await enviar_a_sala(codigo, {
                    "tipo": "npc_movimiento",
                    "id": vaca_id,
                    "x": vaca["x"],
                    "y": vaca["y"],
                    "flip": False
                })

            elif tipo == "alimentar_vaca":
                if ws not in clientes:
                    continue
                codigo = clientes[ws]["sala"]
                vaca_id = data.get("vaca_id")
                player_id = clientes[ws]["id"]

                if codigo in vacas_por_sala and vaca_id in vacas_por_sala[codigo]:
                    vaca = vacas_por_sala[codigo][vaca_id]
                    vaca["siguiendo"] = player_id
                    vaca["tiempo_seguir"] = 20
                    print(f"🐄 {vaca_id} ahora sigue a {player_id}")

            elif tipo == "chat":
                if ws not in clientes:
                    continue
                codigo = clientes[ws]["sala"]
                nombre = clientes[ws]["nombre"]
                mensaje = str(data.get("mensaje", "")).strip()[:120]

                if mensaje:
                    print(f"💬 {nombre}: {mensaje}")
                    await enviar_a_sala(codigo, {
                        "tipo": "chat",
                        "nombre": nombre,
                        "mensaje": mensaje
                    })

            elif tipo == "movimiento":
                if ws not in clientes:
                    continue
                codigo = clientes[ws]["sala"]
                c = clientes[ws]

                c["x"] = data.get("x", c["x"])
                c["y"] = data.get("y", c["y"])
                c["nombre"] = data.get("nombre", c["nombre"])
                c["progreso"] = data.get("progreso", c["progreso"])
                c["nivel"] = data.get("nivel", c["nivel"])
                c["flip"] = data.get("flip", c["flip"])

                if player_id not in jugadores:
                    jugadores[player_id] = {"nombre": c["nombre"], "salas": {}}

                jugadores[player_id]["nombre"] = c["nombre"]
                jugadores[player_id].setdefault("salas", {})[codigo] = {
                    "x": c["x"],
                    "y": c["y"]
                }

                data["nombre"] = c["nombre"]
                await enviar_a_sala(codigo, data)

            elif tipo == "ataque":
                if ws not in clientes:
                    continue
                codigo = clientes[ws]["sala"]
                jugador_id = clientes[ws]["id"]
                await enviar_a_sala(codigo, {
                    "tipo": "ataque",
                    "id": jugador_id,
                    "x": clientes[ws]["x"],
                    "y": clientes[ws]["y"]
                })

            elif tipo == "portal":
                if ws not in clientes:
                    continue
                codigo = clientes[ws]["sala"]
                portal_id = int(data.get("portal", 0))
                visible = bool(data.get("visible", False))
                await enviar_a_sala(codigo, {
                    "tipo": "portal",
                    "portal": portal_id,
                    "visible": visible
                })

            elif tipo == "muerte":
                if ws not in clientes:
                    continue
                codigo = clientes[ws]["sala"]
                jugador_id = clientes[ws]["id"]
                await enviar_a_sala(codigo, {
                    "tipo": "muerte",
                    "id": jugador_id
                })

    except Exception as e:
        print("Error en conexión:", e)

    finally:
        if ws in clientes:
            codigo = clientes[ws]["sala"]
            jugador_id = clientes[ws].get("id")

            if codigo in salas:
                if ws in salas[codigo]:
                    salas[codigo].remove(ws)

                if len(salas[codigo]) == 0:
                    del salas[codigo]
                    if codigo in vacas_por_sala:
                        del vacas_por_sala[codigo]
                    guardar_salas()
                else:
                    await enviar_a_sala(codigo, {
                        "tipo": "jugador_salio",
                        "id": jugador_id
                    })
                    await enviar_lista_jugadores(codigo)

            del clientes[ws]


async def responder_http(path, request_headers):
    upgrade = request_headers.get("Upgrade", "").lower()
    if upgrade == "websocket":
        return None

    body = b"Servidor online"
    return (
        200,
        [("Content-Type", "text/plain"), ("Content-Length", str(len(body)))],
        body
    )


async def main():
    cargar_salas()
    cargar_jugadores()
    print("Servidor iniciado en puerto", PORT)

    asyncio.create_task(loop_vacas())
    asyncio.create_task(loop_guardado_autoclean())

    async with websockets.serve(
        manejar,
        "0.0.0.0",
        PORT,
        process_request=responder_http
    ):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
