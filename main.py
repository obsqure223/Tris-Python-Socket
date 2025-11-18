import flet as ft
from client import TrisClient
import warnings
import time

# Ignora warning deprecazione
warnings.filterwarnings("ignore")

class TrisFletUI:
    def __init__(self, page: ft.Page):
        self.page = page
        self.client = TrisClient() 
        self.nickname = None
        self.room_id = None
        self.my_symbol = None
        self.opponent = None
        self.board_buttons = []
        self.status_text = None

        self.page.title = "Tris Multiplayer - Ture Pagans"
        self.page.vertical_alignment = ft.MainAxisAlignment.CENTER
        self.page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
        self.page.theme_mode = ft.ThemeMode.DARK 

        self.show_login()

    def show_login(self):
        """Mostra la schermata di login"""
        self.page.controls.clear()
        self.page.dialog = None 
        
        # Se avevamo un nickname salvato, lo rimettiamo nel campo di testo
        default_nick = self.nickname if self.nickname else ""
        self.nickname_input = ft.TextField(
            label="Nickname", 
            width=200, 
            text_align=ft.TextAlign.CENTER,
            value=default_nick
        )
        
        self.page.add(
            ft.Column(
                [
                    ft.Text("Benvenuto a Tris!", size=30, weight=ft.FontWeight.BOLD),
                    ft.Divider(height=20, color="transparent"),
                    self.nickname_input,
                    ft.ElevatedButton("Connetti", on_click=self.on_connect, width=150)
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER
            )
        )
        self.page.update()

    def on_connect(self, e):
        """Gestisce il click sul tasto Connetti"""
        nick_val = self.nickname_input.value.strip()
        if not nick_val:
            return
        self.nickname = nick_val
        
        self._start_matchmaking()

    def _start_matchmaking(self):
        """Avvia la procedura di connessione e attesa (usato sia da Login che da Gioca Ancora)"""
        self.page.controls.clear()
        self.page.add(
            ft.Column(
                [
                    ft.ProgressRing(),
                    ft.Divider(height=10, color="transparent"),
                    ft.Text(f"Bentornato {self.nickname}!", size=20, weight=ft.FontWeight.BOLD),
                    ft.Text("Cerco un avversario...", size=16)
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER
            )
        )
        self.page.update()

        # Assicuriamoci di chiudere eventuali connessioni vecchie prima di riaprire
        if self.client.sock:
            try:
                self.client.sock.close()
            except:
                pass
        self.client.connected = False
        self.client.sock = None

        # Connessione al server
        self.client.connect()
        self.client.register_callback(self.handle_server_message)

        # Invio messaggio di Join
        self.client.send({"action": "join", "player_id": self.nickname})

    def handle_server_message(self, msg):
        """Riceve messaggi dal socket e aggiorna la UI"""
        try:
            self._update_ui(msg)
        except Exception as e:
            print(f"[GUI ERROR] Errore aggiornamento UI: {e}")

    def _update_ui(self, msg):
        msg_type = msg.get("type")
        
        # Se il server ci ha disconnesso (es. timeout matchmaking o errore host)
        # torniamo alla home o riproviamo automaticamente
        if msg_type == "connection_lost":
            print("[GUI] Connessione persa. Torno al login.")
            self.logout(None)
            return
        
        if msg_type == "match_found":
            self.room_id = msg["data"]["game_id"]
            self.my_symbol = msg["data"]["you_are"]
            self.opponent = msg["data"]["opponent"]
            self.show_game_board()

        elif msg_type == "game_state":
            data = msg["data"]
            status = data.get("status")
            
            # Aggiorna la scacchiera
            self.update_board(data["board"], data["turn"], result=data.get("result"))
            
            # Se la partita è finita, mostra la schermata di risultato
            if status == "ended":
                print("[GUI] Partita finita, mostro schermata risultati.")
                self.show_end_dialog(data["result"])

    def show_game_board(self):
        """Costruisce e mostra la griglia di gioco"""
        self.page.controls.clear()
        self.board_buttons = []
        
        self.status_text = ft.Text(
            f"Tu sei: {self.my_symbol} (vs {self.opponent})", 
            size=20, 
            weight=ft.FontWeight.BOLD,
            color="green" if self.my_symbol == "X" else "blue"
        )

        rows = []
        for r in range(3):
            row_controls = []
            for c in range(3):
                idx = r * 3 + c
                # Creazione Bottone
                btn = ft.ElevatedButton(
                    text=" ",
                    width=80,
                    height=80,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=8),
                        text_style=ft.TextStyle(size=40, weight=ft.FontWeight.BOLD),
                    ),
                    on_click=lambda e, i=idx: self.on_cell_click(i)
                )
                self.board_buttons.append(btn)
                row_controls.append(btn)
            rows.append(ft.Row(controls=row_controls, alignment=ft.MainAxisAlignment.CENTER))

        board_container = ft.Column(
            controls=rows,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10
        )

        self.page.add(
            ft.Column(
                controls=[
                    self.status_text,
                    ft.Divider(height=20, color="transparent"),
                    board_container
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                expand=True 
            )
        )
        self.page.update()

    def update_board(self, board, turn, result=None):
        """Aggiorna lo stato dei bottoni e il testo in alto"""
        for i, val in enumerate(board):
            # Testo e colore
            color = "green" if val == "X" else "blue" if val == "O" else "white"
            self.board_buttons[i].content = ft.Text(val if val else " ", color=color, size=30, weight=ft.FontWeight.BOLD)
            self.board_buttons[i].text = val if val else " "
            
            # Abilitazione
            is_my_turn = (turn == self.my_symbol)
            is_empty = (val is None)
            game_running = (turn is not None)
            
            self.board_buttons[i].disabled = not (is_my_turn and is_empty and game_running)
        
        # Aggiorna testo stato
        if self.status_text:
            if turn:
                turn_msg = "Tocca a te!" if turn == self.my_symbol else f"Tocca a {self.opponent}"
                self.status_text.value = f"Tu sei: {self.my_symbol} - {turn_msg}"
                self.status_text.color = "white"
            else:
                self.status_text.value = "Partita Terminata"

        self.page.update()

    def on_cell_click(self, idx):
        """Invia la mossa al server"""
        if not self.room_id: return
        self.client.send({
            "action": "move",
            "player_id": self.nickname,
            "room_id": self.room_id,
            "pos": idx
        })

    def show_end_dialog(self, result):
        """Mostra la schermata finale con opzione 'Gioca di nuovo'"""
        
        title_text = "PARTITA FINITA"
        msg_text = ""
        text_color = "white"

        if "disconnected" in result:
            title_text = "VITTORIA (Ritiro)"
            msg_text = "L'avversario si è disconnesso 🏃"
            text_color = "green"
            
        elif result == "draw":
            title_text = "PAREGGIO"
            msg_text = "Nessun vincitore 🤝"
            text_color = "orange"

        elif result == f"{self.my_symbol}_wins":
            title_text = "HAI VINTO! 🎉"
            msg_text = "Ottima partita!"
            text_color = "green"

        else:
            title_text = "HAI PERSO... 💀"
            msg_text = "Non arrenderti!"
            text_color = "red"

        # Pulisci la pagina
        self.page.controls.clear()
        self.page.dialog = None

        # Nuova schermata Risultati
        end_screen = ft.Column(
            controls=[
                ft.Text(title_text, size=40, weight=ft.FontWeight.BOLD, color=text_color),
                ft.Divider(height=10, color="transparent"),
                ft.Text(msg_text, size=20),
                ft.Divider(height=40, color="transparent"),
                
                # Bottone Principale: GIOCA DI NUOVO
                ft.ElevatedButton(
                    text="Gioca di nuovo",
                    icon="refresh",
                    on_click=self.play_again, # Chiama la funzione di reset automatico
                    width=250,
                    height=50,
                    style=ft.ButtonStyle(
                        bgcolor="green",
                        color="white",
                    )
                ),
                ft.Divider(height=10, color="transparent"),
                
                # Bottone Secondario: CAMBIA NICKNAME
                ft.TextButton(
                    text="Cambia Nickname (Esci)",
                    on_click=self.logout, 
                    style=ft.ButtonStyle(color="grey")
                )
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self.page.add(end_screen)
        self.page.update()

    def play_again(self, e):
        """
        Disconnette, aspetta 2 secondi mostrando un caricamento, e poi riconnette.
        Questo delay è FONDAMENTALE per dare tempo al server di pulire la vecchia sessione.
        """
        # 1. Disconnessione immediata per avvisare il server
        if self.client.sock:
            try:
                self.client.sock.close()
            except:
                pass
        self.client.connected = False
        self.client.sock = None
        self.room_id = None
        self.my_symbol = None
        self.opponent = None

        # 2. Mostra schermata di "Caricamento..."
        self.page.controls.clear()
        self.page.dialog = None
        
        pb = ft.ProgressBar(width=200, color="amber")
        status_txt = ft.Text("Riavvio server in corso...", size=16)
        
        self.page.add(
            ft.Column(
                [
                    ft.Text("Preparazione nuova partita", size=24, weight=ft.FontWeight.BOLD),
                    ft.Divider(height=20, color="transparent"),
                    pb,
                    ft.Divider(height=10, color="transparent"),
                    status_txt
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER
            )
        )
        self.page.update()

        # 3. Aspetta 2 secondi (il server pulisce la vecchia connessione)
        import time
        # Piccolo loop per animare (facoltativo, ma carino)
        for i in range(20):
            time.sleep(0.1) 
            # Se vuoi puoi aggiornare una % ma basta lo sleep
        
        # 4. Ora che il server è pulito, riconnettiti
        status_txt.value = "Connessione in corso..."
        self.page.update()
        
        self._start_matchmaking()

    def logout(self, e):
        """Torna alla schermata di login permettendo di cambiare nick"""
        if self.client.sock:
            try:
                self.client.sock.close()
            except:
                pass
        self.client.connected = False
        self.client.sock = None
        
        self.show_login()

def main(page: ft.Page):
    TrisFletUI(page)

ft.app(target=main)
