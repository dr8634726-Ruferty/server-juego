import asyncio
import websockets
import json
import random
import string
import os
import time

# =========================================================
# CONFIGURACIÓN
# =========================================================

PORT = int(os.environ.get("PORT", 8765))

clientes = {}
salas = {}
vacas_por_sala = {}

ARCHIVO_SALAS = "salas.json"
ARCHIVO_JUGADORES = "jugadores.json"

jugadores = {}

ultimo_guardado = 0
INTERVALO_GUARDADO = 5


# =========================================================
# CARGAR SALAS
# =========================================================

def cargar_salas():

    global salas

    if os.path.exists(ARCHIVO_SALAS):

        try:

            with open(ARCHIVO_SALAS, "r") as f:

                data = json.load(f)

                salas = {}

                for codigo in data:

                    salas[codigo] = []

                print(
                    "Salas cargadas:",
                    list(salas.keys())
                )

        except Exception as e:

            print(
                "Error cargando salas:",
                e
            )

            salas = {}


# =========================================================
# CARGAR JUGADORES
# =========================================================

def cargar_jugadores():

    global jugadores

    if os.path.exists(ARCHIVO_JUGADORES):

        try:

            with open(
                ARCHIVO_JUGADORES,
                "r"
            ) as f:

                jugadores = json.load(f)

                print(
                    "Jugadores cargados:",
                    len(jugadores)
                )

        except Exception as e:

            print(
                "Error cargando jugadores:",
                e
            )

            jugadores = {}


# =========================================================
# GUARDAR SALAS
# =========================================================

def guardar_salas():

    try:

        lista = list(
            salas.keys()
        )

        with open(
            ARCHIVO_SALAS,
            "w"
        ) as f:

            json.dump(
                lista,
                f,
                indent=4
            )

    except Exception as e:

        print(
            "Error guardando salas:",
            e
        )


# =========================================================
# GUARDAR JUGADORES
# =========================================================

def guardar_jugadores():

    global ultimo_guardado

    ahora = time.time()

    if ahora - ultimo_guardado < INTERVALO_GUARDADO:

        return

    ultimo_guardado = ahora

    try:

        with open(
            ARCHIVO_JUGADORES,
            "w"
        ) as f:

            json.dump(
                jugadores,
                f,
                indent=4
            )

    except Exception as e:

        print(
            "Error guardando jugadores:",
            e
        )


# =========================================================
# GENERAR CÓDIGO
# =========================================================

def generar_codigo():

    return ''.join(
        random.choices(
            string.ascii_uppercase + string.digits,
            k=6
        )
    )


# =========================================================
# CREAR VACAS PARA SALA
# =========================================================

def crear_vacas_para_sala(codigo):

    vacas_por_sala[codigo] = {}

    for i in range(0):

        vaca_id = f"vaca_{i}"

        vacas_por_sala[codigo][vaca_id] = {

            "x": random.randint(
                100,
                400
            ),

            "y": random.randint(
                100,
                400
            ),

            "dir_x": random.uniform(
                -1,
                1
            ),

            "dir_y": random.uniform(
                -1,
                1
            ),

            "tiempo": random.uniform(
                1,
                3
            ),

            "siguiendo": None,

            "tiempo_seguir": 0
        }


# =========================================================
# LOOP DE VACAS
# =========================================================

async def loop_vacas():

    while True:

        await asyncio.sleep(0.1)

        for codigo, vacas in list(
            vacas_por_sala.items()
        ):

            # -------------------------------------------------
            # EVITAR ERROR SI LA SALA YA NO EXISTE
            # -------------------------------------------------

            if codigo not in salas:

                continue

            for vid, v in list(
                vacas.items()
            ):

                # =================================================
                # SI ESTÁ SIGUIENDO A UN PLAYER
                # =================================================

                if v.get("siguiendo") is not None:

                    v["tiempo_seguir"] -= 0.1

                    if v["tiempo_seguir"] <= 0:

                        v["siguiendo"] = None

                    else:

                        player_obj = None

                        print(
                            "DEBUG buscando player:",
                            v["siguiendo"]
                        )

                        for ws2 in list(
                            salas[codigo]
                        ):

                            if ws2 in clientes:

                                if str(
                                    clientes[ws2]["id"]
                                ) == str(
                                    v["siguiendo"]
                                ):

                                    player_obj = clientes[ws2]

                                    break

                        # =================================================
                        # PLAYER ENCONTRADO
                        # =================================================

                        if player_obj:

                            dx = (
                                player_obj["x"]
                                - v["x"]
                            )

                            dy = (
                                player_obj["y"]
                                - v["y"]
                            )

                            dist = max(
                                (
                                    dx ** 2
                                    +
                                    dy ** 2
                                ) ** 0.5,
                                0.01
                            )

                            v["x"] += (
                                dx / dist
                            ) * 6

                            v["y"] += (
                                dy / dist
                            ) * 6

                            flip = dx < 0

                            await enviar_a_sala(
                                codigo,
                                {
                                    "tipo": "npc_movimiento",

                                    "id": vid,

                                    "x": v["x"],

                                    "y": v["y"],

                                    "flip": flip,

                                    "siguiendo": True
                                }
                            )

                        else:

                            await enviar_a_sala(
                                codigo,
                                {
                                    "tipo": "npc_movimiento",

                                    "id": vid,

                                    "x": v["x"],

                                    "y": v["y"],

                                    "flip": False,

                                    "siguiendo": True
                                }
                            )

                            continue

                    continue

                # =================================================
                # CAMBIAR DIRECCIÓN
                # =================================================

                v["tiempo"] -= 0.1

                if v["tiempo"] <= 0:

                    v["tiempo"] = random.uniform(
                        1,
                        3
                    )

                    v["dir_x"] = random.uniform(
                        -1,
                        1
                    )

                    v["dir_y"] = random.uniform(
                        -1,
                        1
                    )

                # =================================================
                # MOVER
                # =================================================

                velocidad = 2

                v["x"] += (
                    v["dir_x"]
                    * velocidad
                )

                v["y"] += (
                    v["dir_y"]
                    * velocidad
                )

                # =================================================
                # FLIP
                # =================================================

                flip = v["dir_x"] < 0

                # =================================================
                # ENVIAR A LA SALA
                # =================================================

                await enviar_a_sala(
                    codigo,
                    {
                        "tipo": "npc_movimiento",

                        "id": vid,

                        "x": v["x"],

                        "y": v["y"],

                        "flip": flip,

                        "siguiendo":
                            v.get(
                                "siguiendo"
                            ) is not None
                    }
                )


# =========================================================
# ENVIAR A TODA LA SALA
# =========================================================

async def enviar_a_sala(
    codigo,
    data
):

    if codigo not in salas:

        return

    mensaje = json.dumps(
        data
    )

    for ws in list(
        salas[codigo]
    ):

        try:

            await ws.send(
                mensaje
            )

        except Exception:

            if ws in salas[codigo]:

                salas[codigo].remove(
                    ws
                )


# =========================================================
# ENVIAR LISTA DE JUGADORES
# =========================================================

async def enviar_lista_jugadores(
    codigo
):

    if codigo not in salas:

        return

    lista = []

    ahora = time.time()

    for ws in list(
        salas[codigo]
    ):

        if ws in clientes:

            c = clientes[ws]

            # =================================================
            # TIEMPO CONECTADO
            # =================================================

            hora_conexion = c.get(
                "hora_conexion",
                ahora
            )

            tiempo_conectado = int(
                ahora
                -
                hora_conexion
            )

            lista.append({

                "id": c["id"],

                "nombre": c["nombre"],

                "x": c.get(
                    "x",
                    0
                ),

                "y": c.get(
                    "y",
                    0
                ),

                "progreso": c.get(
                    "progreso",
                    0
                ),

                "nivel": c.get(
                    "nivel",
                    0
                ),

                "flip": c.get(
                    "flip",
                    False
                ),

                "tiempo_conectado":
                    tiempo_conectado
            })

    await enviar_a_sala(
        codigo,
        {
            "tipo":
                "lista_jugadores",

            "jugadores":
                lista
        }
    )


# =========================================================
# MANEJAR CLIENTE
# =========================================================

async def manejar(ws):

    print(
        "Cliente conectado"
    )

    try:

        async for mensaje in ws:

            try:

                data = json.loads(
                    mensaje
                )

            except Exception:

                print(
                    "JSON inválido"
                )

                continue

            tipo = data.get(
                "tipo",
                ""
            )

            player_id = data.get(
                "id"
            )

            # =================================================
            # TIPOS QUE NO NECESITAN ID
            # =================================================

            tipos_sin_id = [

                "listar_salas",

                "listar_jugadores"
            ]

            if (
                tipo not in tipos_sin_id
                and not player_id
            ):

                if ws in clientes:

                    player_id = clientes[
                        ws
                    ]["id"]

                else:

                    continue

            # =================================================
            # CREAR SALA
            # =================================================

            if tipo == "crear_sala":

                codigo = generar_codigo()

                salas[codigo] = [
                    ws
                ]

                crear_vacas_para_sala(
                    codigo
                )

                if player_id in jugadores:

                    jugador_data = jugadores[
                        player_id
                    ]

                    nombre = jugador_data.get(
                        "nombre",
                        "Jugador"
                    )

                    if codigo in jugador_data.get(
                        "salas",
                        {}
                    ):

                        pos = jugador_data[
                            "salas"
                        ][codigo]

                        x = pos.get(
                            "x",
                            100
                        )

                        y = pos.get(
                            "y",
                            100
                        )

                    else:

                        x = 100
                        y = 100

                else:

                    x = 100
                    y = 100

                    nombre = data.get(
                        "nombre",
                        "Jugador"
                    )

                clientes[ws] = {

                    "sala":
                        codigo,

                    "id":
                        player_id,

                    "nombre":
                        nombre,

                    "x":
                        x,

                    "y":
                        y,

                    "progreso":
                        0,

                    "nivel":
                        0,

                    "flip":
                        False,

                    "hora_conexion":
                        time.time()
                }

                guardar_salas()

                await ws.send(
                    json.dumps(
                        {
                            "tipo":
                                "sala_creada",

                            "codigo":
                                codigo
                        }
                    )
                )

                print(
                    "Sala creada:",
                    codigo
                )

                await enviar_lista_jugadores(
                    codigo
                )

            # =================================================
            # UNIRSE A SALA
            # =================================================

            elif tipo == "unirse_sala":

                codigo = data.get(
                    "codigo",
                    ""
                )

                if codigo not in salas:

                    await ws.send(
                        json.dumps(
                            {
                                "tipo":
                                    "error",

                                "mensaje":
                                    "Sala no existe"
                            }
                        )
                    )

                    continue

                if ws not in salas[codigo]:

                    salas[codigo].append(
                        ws
                    )

                if codigo not in vacas_por_sala:

                    crear_vacas_para_sala(
                        codigo
                    )

                if player_id in jugadores:

                    jugador_data = jugadores[
                        player_id
                    ]

                    nombre = jugador_data.get(
                        "nombre",
                        "Jugador"
                    )

                    if codigo in jugador_data.get(
                        "salas",
                        {}
                    ):

                        pos = jugador_data[
                            "salas"
                        ][codigo]

                        x = pos.get(
                            "x",
                            100
                        )

                        y = pos.get(
                            "y",
                            100
                        )

                    else:

                        x = 100
                        y = 100

                else:

                    x = 100
                    y = 100

                    nombre = data.get(
                        "nombre",
                        "Jugador"
                    )

                clientes[ws] = {

                    "sala":
                        codigo,

                    "id":
                        player_id,

                    "nombre":
                        nombre,

                    "x":
                        x,

                    "y":
                        y,

                    "progreso":
                        0,

                    "nivel":
                        0,

                    "flip":
                        False,

                    "hora_conexion":
                        time.time()
                }

                await ws.send(
                    json.dumps(
                        {
                            "tipo":
                                "unido",

                            "codigo":
                                codigo
                        }
                    )
                )

                print(
                    "Jugador unido a",
                    codigo
                )

                await enviar_lista_jugadores(
                    codigo
                )

            # =================================================
            # LISTAR SALAS
            # =================================================

            elif tipo == "listar_salas":

                await ws.send(
                    json.dumps(
                        {
                            "tipo":
                                "salas",

                            "salas":
                                list(
                                    salas.keys()
                                )
                        }
                    )
                )

            # =================================================
            # LISTAR JUGADORES
            # =================================================

            elif tipo == "listar_jugadores":

                codigo = data.get(
                    "codigo",
                    ""
                )

                if codigo in salas:

                    await enviar_lista_jugadores(
                        codigo
                    )

            # =================================================
            # SPAWN NPC
            # =================================================

            elif tipo == "spawn_npc":

                if ws not in clientes:

                    continue

                codigo = clientes[
                    ws
                ]["sala"]

                if codigo not in vacas_por_sala:

                    vacas_por_sala[
                        codigo
                    ] = {}

                vaca_id = data.get(
                    "id"
                )

                vaca = {

                    "x":
                        data.get(
                            "x",
                            100
                        ),

                    "y":
                        data.get(
                            "y",
                            100
                        ),

                    "dir_x":
                        random.uniform(
                            -1,
                            1
                        ),

                    "dir_y":
                        random.uniform(
                            -1,
                            1
                        ),

                    "tiempo":
                        random.uniform(
                            1,
                            3
                        ),

                    "siguiendo":
                        None,

                    "tiempo_seguir":
                        0
                }

                vacas_por_sala[
                    codigo
                ][vaca_id] = vaca

                print(
                    "🐄 Vaca creada:",
                    vaca_id,
                    "en sala",
                    codigo
                )

                await enviar_a_sala(
                    codigo,
                    {
                        "tipo":
                            "npc_movimiento",

                        "id":
                            vaca_id,

                        "x":
                            vaca["x"],

                        "y":
                            vaca["y"],

                        "flip":
                            False
                    }
                )

            # =================================================
            # ALIMENTAR VACA
            # =================================================

            elif tipo == "alimentar_vaca":

                if ws not in clientes:

                    continue

                codigo = clientes[
                    ws
                ]["sala"]

                vaca_id = data.get(
                    "vaca_id"
                )

                player_id = clientes[
                    ws
                ]["id"]

                print(
                    "🐄 Alimentando:",
                    vaca_id,
                    "→ jugador:",
                    player_id
                )

                if (
                    codigo in vacas_por_sala
                    and
                    vaca_id in vacas_por_sala[
                        codigo
                    ]
                ):

                    vaca = vacas_por_sala[
                        codigo
                    ][vaca_id]

                    vaca[
                        "siguiendo"
                    ] = player_id

                    vaca[
                        "tiempo_seguir"
                    ] = 20

                    print(
                        "DEBUG siguiendo guardado:",
                        vaca[
                            "siguiendo"
                        ]
                    )

                    print(
                        "🐄 Ahora sigue por 20 segundos"
                    )

            # =================================================
            # CHAT
            # =================================================

            elif tipo == "chat":

                if ws not in clientes:

                    continue

                codigo = clientes[
                    ws
                ]["sala"]

                nombre = clientes[
                    ws
                ]["nombre"]

                mensaje_chat = str(
                    data.get(
                        "mensaje",
                        ""
                    )
                ).strip()[:120]

                if mensaje_chat == "":

                    continue

                print(
                    f"💬 {nombre}: {mensaje_chat}"
                )

                await enviar_a_sala(
                    codigo,
                    {
                        "tipo":
                            "chat",

                        "nombre":
                            nombre,

                        "mensaje":
                            mensaje_chat
                    }
                )

            # =================================================
            # MOVIMIENTO
            # =================================================

            elif tipo == "movimiento":

                if ws not in clientes:

                    continue

                codigo = clientes[
                    ws
                ]["sala"]

                c = clientes[
                    ws
                ]

                if "x" in data:

                    c["x"] = data[
                        "x"
                    ]

                if "y" in data:

                    c["y"] = data[
                        "y"
                    ]

                if "nombre" in data:

                    c["nombre"] = data[
                        "nombre"
                    ]

                if "progreso" in data:

                    c["progreso"] = data[
                        "progreso"
                    ]

                if "nivel" in data:

                    c["nivel"] = data[
                        "nivel"
                    ]

                if "flip" in data:

                    c["flip"] = data[
                        "flip"
                    ]

                if player_id not in jugadores:

                    jugadores[
                        player_id
                    ] = {

                        "nombre":
                            c["nombre"],

                        "salas":
                            {}
                    }

                jugadores[
                    player_id
                ][
                    "nombre"
                ] = c[
                    "nombre"
                ]

                jugadores[
                    player_id
                ].setdefault(
                    "salas",
                    {}
                )

                jugadores[
                    player_id
                ][
                    "salas"
                ][
                    codigo
                ] = {

                    "x":
                        c["x"],

                    "y":
                        c["y"]
                }

                guardar_jugadores()

                data[
                    "nombre"
                ] = c[
                    "nombre"
                ]

                await enviar_a_sala(
                    codigo,
                    data
                )

                await enviar_lista_jugadores(
                    codigo
                )

            # =================================================
            # ATAQUE
            # =================================================

            elif tipo == "ataque":

                if ws not in clientes:

                    continue

                codigo = clientes[
                    ws
                ]["sala"]

                jugador_id = clientes[
                    ws
                ]["id"]

                print(
                    "⚔️ Ataque de:",
                    jugador_id
                )

                await enviar_a_sala(
                    codigo,
                    {
                        "tipo":
                            "ataque",

                        "id":
                            jugador_id,

                        "x":
                            clientes[
                                ws
                            ]["x"],

                        "y":
                            clientes[
                                ws
                            ]["y"]
                    }
                )

            # =================================================
            # PORTAL
            # =================================================

            elif tipo == "portal":

                if ws not in clientes:

                    continue

                codigo = clientes[
                    ws
                ]["sala"]

                portal_id = int(
                    data.get(
                        "portal",
                        0
                    )
                )

                visible = bool(
                    data.get(
                        "visible",
                        False
                    )
                )

                print(
                    "🌀 Portal cambiado:",
                    portal_id,
                    "visible:",
                    visible,
                    "sala:",
                    codigo
                )

                await enviar_a_sala(
                    codigo,
                    {
                        "tipo":
                            "portal",

                        "portal":
                            portal_id,

                        "visible":
                            visible
                    }
                )

            # =================================================
            # MUERTE
            # =================================================

            elif tipo == "muerte":

                if ws not in clientes:

                    continue

                codigo = clientes[
                    ws
                ]["sala"]

                jugador_id = clientes[
                    ws
                ]["id"]

                print(
                    "💀 Muerte de:",
                    jugador_id
                )

                await enviar_a_sala(
                    codigo,
                    {
                        "tipo":
                            "muerte",

                        "id":
                            jugador_id
                    }
                )

            # =================================================
            # MENSAJE GLOBAL
            # =================================================

            elif tipo == "mensaje_global":

                if ws not in clientes:

                    continue

                codigo = clientes[
                    ws
                ]["sala"]

                mensaje_global = str(
                    data.get(
                        "mensaje",
                        ""
                    )
                ).strip()[:200]

                if mensaje_global == "":

                    continue

                print(
                    f"📢 Mensaje global en {codigo}: {mensaje_global}"
                )

                await enviar_a_sala(
                    codigo,
                    {
                        "tipo":
                            "mensaje_global",

                        "mensaje":
                            mensaje_global
                    }
                )

    # =========================================================
    # ERROR DEL CLIENTE
    # =========================================================

    except Exception as e:

        print(
            "Cliente desconectado:",
            e
        )

    # =========================================================
    # LIMPIEZA AL DESCONECTAR
    # =========================================================

    finally:

        if ws in clientes:

            codigo = clientes[
                ws
            ]["sala"]

            jugador_id = clientes[
                ws
            ].get(
                "id"
            )

            if codigo in salas:

                if ws in salas[
                    codigo
                ]:

                    salas[
                        codigo
                    ].remove(
                        ws
                    )

                await enviar_a_sala(
                    codigo,
                    {
                        "tipo":
                            "jugador_salio",

                        "id":
                            jugador_id
                    }
                )

                await enviar_lista_jugadores(
                    codigo
                )

                # =================================================
                # NO ELIMINAMOS SALAS VACÍAS
                # =================================================
                #
                # Se conserva tu comportamiento anterior.
                #
                # if len(salas[codigo]) == 0:
                #     del salas[codigo]
                #     print("Sala eliminada:", codigo)

            del clientes[
                ws
            ]

            guardar_salas()
            guardar_jugadores()


# =========================================================
# HTTP / HEALTH CHECK PARA RENDER
# =========================================================
#
# IMPORTANTE:
#
# Este servidor también responde peticiones HTTP normales.
#
# Render/Cron puede visitar:
#
# /health
#
# y recibir:
#
# HTTP 200
# Servidor online
#
# Las conexiones WebSocket siguen funcionando normalmente.
# =========================================================

async def responder_http(
    path,
    request_headers
):

    # =====================================================
    # SI ES WEBSOCKET
    # =====================================================

    upgrade = request_headers.get(
        "Upgrade",
        ""
    ).lower()

    if upgrade == "websocket":

        return None

    # =====================================================
    # HEALTH CHECK
    # =====================================================

    if path == "/health":

        body = b"Servidor online"

        return (
            200,
            [
                (
                    "Content-Type",
                    "text/plain; charset=utf-8"
                ),
                (
                    "Content-Length",
                    str(len(body))
                ),
                (
                    "Cache-Control",
                    "no-cache"
                )
            ],
            body
        )

    # =====================================================
    # RUTA PRINCIPAL
    # =====================================================

    if path == "/":

        body = (
            b"Servidor de juego online"
        )

        return (
            200,
            [
                (
                    "Content-Type",
                    "text/plain; charset=utf-8"
                ),
                (
                    "Content-Length",
                    str(len(body))
                ),
                (
                    "Cache-Control",
                    "no-cache"
                )
            ],
            body
        )

    # =====================================================
    # CUALQUIER OTRA RUTA
    # =====================================================

    body = b"OK"

    return (
        200,
        [
            (
                "Content-Type",
                "text/plain; charset=utf-8"
            ),
            (
                "Content-Length",
                str(len(body))
            )
        ],
        body
    )


# =========================================================
# MAIN
# =========================================================

async def main():

    # =====================================================
    # CARGAR DATOS
    # =====================================================

    cargar_salas()

    cargar_jugadores()

    print(
        "Servidor iniciado en puerto",
        PORT
    )

    # =====================================================
    # INICIAR LOOP DE VACAS
    # =====================================================

    asyncio.create_task(
        loop_vacas()
    )

    # =====================================================
    # SERVIDOR WEBSOCKET + HTTP
    # =====================================================
    #
    # Usamos la API legacy porque tu código utiliza:
    #
    # process_request(path, request_headers)
    #
    # Esto mantiene compatible tu servidor actual.
    #
    # =====================================================

    from websockets.legacy.server import serve

    async with serve(
        manejar,
        "0.0.0.0",
        PORT,
        process_request=responder_http
    ):

        print(
            "✅ WebSocket activo"
        )

        print(
            "✅ HTTP /health activo"
        )

        print(
            "🌐 Puerto:",
            PORT
        )

        await asyncio.Future()


# =========================================================
# INICIAR SERVIDOR
# =========================================================

asyncio.run(
    main()
)
