import socket
import threading
import time
from protocollo import recv_msg, send_msg
from gameroom import GameRoom, GameRoomError

rooms = {}              
waiting_room = None     
rooms_lock = threading.Lock()
waiting_lock = threading.Lock()

def broadcast_game_state(room, data):
    disconnected = []
    with room.lock:
        for pid, p_conn in room.connections.items():
            try:
                send_msg(p_conn, {"type": "game_state", "data": data})
            except:
                disconnected.append(pid)
    return disconnected

def client_handler(conn, addr):
    global waiting_room
    player_id = None
    current_room = None
    
    print(f"[Server] Connessione da {addr}")
    
    try:
        msg = recv_msg(conn)
        if not msg: return
        player_id = msg.get("player_id")
        if not player_id: return

        print(f"[Server] Login: {player_id}")

        # ---------------- Matchmaking ----------------
        with waiting_lock:
            # 1. Se non c'è stanza d'attesa, creala
            if waiting_room is None:
                room = GameRoom(player_id)
                room.connections[player_id] = conn
                rooms[room.id] = room
                waiting_room = room
                current_room = room
                send_msg(conn, {"ok": True, "status": "waiting"})
                print(f"[Server] {player_id} ha creato stanza {room.id}")
            
            else:
                # 2. C'è una stanza. Unisciti.
                room = waiting_room
                host_id = list(room.players.keys())[0]
                host_conn = room.connections.get(host_id)
                
                try:
                    room.add_player(player_id, conn)
                    waiting_room = None # Stanza piena
                    current_room = room
                    
                    # --- TENTATIVO AVVIO PARTITA ---
                    match_started = True
                    
                    # Notifica Host (Chi era in attesa)
                    try:
                        send_msg(host_conn, {
                            "type": "match_found",
                            "data": {"game_id": room.id, "you_are": "X", "opponent": player_id}
                        })
                    except Exception as e:
                        print(f"[Server] ERRORE critico invio a Host {host_id}: {e}")
                        match_started = False
                        # ### FIX CRITICO: CHIUDI IL SOCKET DELL'HOST MORTO ###
                        # Se non lo chiudiamo, il client dell'host resta in attesa per sempre
                        try: host_conn.close()
                        except: pass
                        if room.id in rooms: del rooms[room.id]

                    # Se l'host era vivo, notifica il Joiner (Tu)
                    if match_started:
                        try:
                            send_msg(conn, {
                                "type": "match_found",
                                "data": {"game_id": room.id, "you_are": "O", "opponent": host_id}
                            })
                        except Exception as e:
                            print(f"[Server] Errore invio a Joiner {player_id}: {e}")
                            match_started = False
                    
                    # Se qualcosa è andato storto nell'handshake
                    if not match_started:
                        print(f"[Server] Match fallito. Sposto {player_id} in nuova stanza.")
                        # Crea una nuova stanza pulita per il giocatore corrente
                        new_room = GameRoom(player_id)
                        new_room.connections[player_id] = conn
                        rooms[new_room.id] = new_room
                        waiting_room = new_room
                        current_room = new_room
                        send_msg(conn, {"ok": True, "status": "waiting"})

                except GameRoomError as e:
                    send_msg(conn, {"ok": False, "reason": str(e)})
                    return

        # ---------------- Loop Gioco ----------------
        while True:
            msg = recv_msg(conn)
            if msg is None: break
            
            action = msg.get("action")
            if action == "move":
                pos = msg.get("pos")
                if current_room:
                    res = current_room.apply_move(player_id, pos)
                    broadcast_game_state(current_room, res)

    except Exception as e:
        if "10054" not in str(e):
            print(f"[Server] Errore {player_id}: {e}")
    finally:
        print(f"[Server] Disconnessione {player_id}")
        conn.close()
        
        # Pulizia Waiting Room se era la mia
        with waiting_lock:
            if waiting_room and current_room and waiting_room.id == current_room.id:
                waiting_room = None
        
        # Pulizia Partita in Corso
        if player_id and current_room:
            with current_room.lock:
                if player_id in current_room.connections:
                    del current_room.connections[player_id]
                
                if current_room.status == "running":
                    current_room.status = "ended"
                    for other_conn in current_room.connections.values():
                        try:
                            send_msg(other_conn, {
                                "type": "game_state",
                                "data": {
                                    "status": "ended",
                                    "result": f"{current_room.players[player_id]}_disconnected",
                                    "board": current_room.board,
                                    "turn": None
                                }
                            })
                        except: pass

def start_server(host="0.0.0.0", port=5000):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((host, port))
    s.listen()
    print(f"[Server] Avviato su {host}:{port}")
    while True:
        try:
            conn, addr = s.accept()
            threading.Thread(target=client_handler, args=(conn, addr), daemon=True).start()
        except: pass

if __name__ == "__main__":
    start_server()
