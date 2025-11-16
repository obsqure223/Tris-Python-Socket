
# server.py
import flet as ft
import socket
import threading

clients = [] 
server_running = False
server_socket = None

external_log = None
external_page = None


def nickformat(msg: str) -> ft.Row:
    if ":" in msg:
        nickname, testo = msg.split(":", 1)
        return ft.Row([
            ft.Text(f"{nickname}:", weight=ft.FontWeight.BOLD),
            ft.Text(testo.strip())
        ])
    else:
        return ft.Text(msg, weight=ft.FontWeight.BOLD)

def log(msg):
    if external_log and external_page:
        widget = nickformat(msg)
        external_log.controls.append(widget)
        external_page.update()
    else:
        print(msg)




def broadcast(messaggio, mittente_socket=None):
    for c, _ in clients:
        if c != mittente_socket:
            try:
                c.sendall(messaggio.encode("utf-8"))
            except:
                pass


def gestisci_client(client_socket, indirizzo):
    nickname = client_socket.recv(1024).decode('utf-8').strip()
    clients.append((client_socket, nickname))

    log(f"[CONNESSO] {nickname} da {indirizzo}")
    broadcast(f"{nickname} si è unito alla chat!", client_socket)

    while True:
        try:
            msg = client_socket.recv(1024).decode('utf-8').strip()
            if not msg:
                break

            if msg.lower() == "exit":
                log(f"[DISCONNESSIONE] {nickname} ha lasciato la chat.")
                broadcast(f"{nickname} ha lasciato la chat.", client_socket)
                break

            log(f"{nickname}: {msg}")
            broadcast(f"{nickname}: {msg}", client_socket)

        except:
            break

    clients.remove((client_socket, nickname))
    client_socket.close()


def start_server(log_widget=None, page=None):
    global server_running, server_socket, external_log, external_page

    external_log = log_widget
    external_page = page

    server_running = True
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(("0.0.0.0", 12345))
    server_socket.listen()

    log("[SERVER] Avviato sulla porta 12345")

    while server_running:
        try:
            client_socket, address = server_socket.accept()
            threading.Thread(
                target=gestisci_client,
                args=(client_socket, address),
                daemon=True
            ).start()
        except:
            break

    log("[SERVER] Fermato")


def stop_server():
    global server_running, server_socket
    server_running = False

    if server_socket:
        try:
            server_socket.close()
        except:
            pass

    log("[SERVER] Arresto in corso...")
