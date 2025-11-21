# server/main.py

import socket
import threading
import time
from protocollo import recv_msg, send_msg
from gameroom import GameRoom, GameRoomError

# --- STRUTTURE DATI GLOBALI ---
rooms = {}              
waiting_room = None     

# Tracking univocità nickname
connected_players = set()       
players_lock = threading.Lock() 

# Lock per la gestione delle stanze
rooms_lock = threading.Lock()
waiting_lock = threading.Lock()

def broadcast_game_state(room, data):
    """Invia lo stato del gioco a tutti i giocatori nella stanza."""
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
    player_id = None     # Il nickname confermato
    current_room = None  # La stanza attuale
    
    print(f"[Server] Connessione da {addr}")
    
    try:
        # 1. RICEZIONE PRIMO MESSAGGIO (LOGIN)
        msg = recv_msg(conn)
        if not msg: return
        
        requested_id = msg.get("player_id")
        if not requested_id: return

        # 2. CONTROLLO UNIVOCITÀ NICKNAME
        with players_lock:
            if requested_id in connected_players:
                print(f"[Server] Login rifiutato: '{requested_id}' è già connesso.")
                try:
                    send_msg(conn, {"ok": False, "reason": "Nickname già in uso!"})
                except: pass
                return # Chiude la connessione ed esce
            else:
                # Nickname valido: lo registriamo
                connected_players.add(requested_id)
                player_id = requested_id

        print(f"[Server] Login effettuato: {player_id}")

        # 3. MATCHMAKING
        with waiting_lock:
            # CASO A: Nessuna stanza in attesa -> Crea nuova stanza
            if waiting_room is None:
                room = GameRoom(player_id)
                room.connections[player_id] = conn
                rooms[room.id] = room
                waiting_room = room
                current_room = room
                
                send_msg(conn, {"ok": True, "status": "waiting"})
                print(f"[Server] {player_id} ha creato stanza {room.id} in attesa...")
            
            # CASO B: C'è una stanza in attesa -> Unisciti
            else:
                room = waiting_room
                host_id = list(room.players.keys())[0]
                host_conn = room.connections.get(host_id)
                
                try:
                    # Tenta di aggiungere il secondo giocatore
                    room.add_player(player_id, conn)
                    waiting_room = None # La stanza ora è piena
                    current_room = room
                    
                    # --- AVVIO PARTITA ---
                    match_started = True
                    
                    # Notifica Host (Chi era in attesa, gioca come X)
                    try:
                        send_msg(host_conn, {
                            "type": "match_found",
                            "data": {"game_id": room.id, "you_are": "X", "opponent": player_id}
                        })
                    except Exception as e:
                        print(f"[Server] ERRORE critico invio a Host {host_id}: {e}")
                        match_started = False
                        # L'host è probabilmente disconnesso/morto -> chiudiamo il suo socket
                        try: host_conn.close()
                        except: pass
                        if room.id in rooms: del rooms[room.id]

                    # Se l'host era vivo, notifica il Joiner (Tu, gioca come O)
                    if match_started:
                        try:
                            send_msg(conn, {
                                "type": "match_found",
                                "data": {"game_id": room.id, "you_are": "O", "opponent": host_id}
                            })
                        except Exception as e:
                            print(f"[Server] Errore invio a Joiner {player_id}: {e}")
                            match_started = False
                    
                    # FALLBACK: Se qualcosa è andato storto nell'handshake
                    if not match_started:
                        print(f"[Server] Match fallito. Sposto {player_id} in nuova stanza pulita.")
                        new_room = GameRoom(player_id)
                        new_room.connections[player_id] = conn
                        rooms[new_room.id] = new_room
                        waiting_room = new_room
                        current_room = new_room
                        send_msg(conn, {"ok": True, "status": "waiting"})

                except GameRoomError as e:
                    send_msg(conn, {"ok": False, "reason": str(e)})
                    return

        # 4. LOOP DI GIOCO
        while True:
            msg = recv_msg(conn)
            if msg is None: break # Client disconnesso
            
            action = msg.get("action")
            
            if action == "move":
                pos = msg.get("pos")
                if current_room:
                    res = current_room.apply_move(player_id, pos)
                    broadcast_game_state(current_room, res)

    except Exception as e:
        # Ignora errori di reset connessione standard
        if "10054" not in str(e):
            print(f"[Server] Errore imprevisto per {player_id}: {e}")

    finally:
        print(f"[Server] Disconnessione {player_id}")
        
        # A. Rilascia il nickname
        if player_id:
            with players_lock:
                if player_id in connected_players:
                    connected_players.remove(player_id)
                    print(f"[Server] Nickname '{player_id}' liberato.")

        # B. Chiudi socket
        try: conn.close()
        except: pass
        
        # C. Pulizia Waiting Room (se il giocatore era in attesa da solo)
        with waiting_lock:
            if waiting_room and current_room and waiting_room.id == current_room.id:
                waiting_room = None
                print("[Server] Waiting room rimossa (host disconnesso).")
        
        # D. Pulizia Partita in Corso (notifica avversario)
        if player_id and current_room:
            with current_room.lock:
                # Rimuovi la connessione del giocatore uscente
                if player_id in current_room.connections:
                    del current_room.connections[player_id]
                
                # Se la partita era in corso, termina per abbandono
                if current_room.status == "running":
                    current_room.status = "ended"
                    for other_pid, other_conn in current_room.connections.items():
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
                            print(f"[Server] Notificato avversario {other_pid} dell'abbandono.")
                        except: pass

def start_server(host="0.0.0.0", port=5000):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Permette di riavviare il server subito senza errore "Address already in use"
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        s.bind((host, port))
        s.listen()
        print(f"[Server] Avviato su {host}:{port}")
        print("[Server] In attesa di connessioni...")
        
        while True:
            conn, addr = s.accept()
            # Avvia un thread per ogni client
            threading.Thread(target=client_handler, args=(conn, addr), daemon=True).start()
            
    except Exception as e:
        print(f"[Server] Errore avvio: {e}")
    finally:
        s.close()

if __name__ == "__main__":
    start_server()
