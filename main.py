# client/main.py

import flet as ft
from client import TrisClient
import warnings
import time
import random
import threading
import math # Serve per le onde

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
        
        self.board_items = [] 
        
        self.status_text = None
        self.login_button = None
        self.nickname_input = None
        self.error_text = None
        self.current_dialog = None

        # Variabili per l'animazione background
        self.anim_running = False
        self.background_objs = [] 

        self.page.title = "Tris Multiplayer"
        self.page.vertical_alignment = ft.MainAxisAlignment.CENTER
        self.page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
        self.page.theme_mode = ft.ThemeMode.DARK 
        self.page.bgcolor = "blueGrey900" 

        # --- NAVBAR ---
        self.theme_icon = ft.IconButton(
            icon="wb_sunny_outlined", 
            tooltip="Cambia Tema",
            on_click=self.toggle_theme
        )

        self.exit_button = ft.IconButton(
            icon="exit_to_app", 
            tooltip="Esci dalla partita",
            visible=False, 
            on_click=self.request_exit_dialog
        )

        self.page.appbar = ft.AppBar(
            leading=self.exit_button, 
            leading_width=40,
            title=ft.Text("Tris Multiplayer", weight=ft.FontWeight.BOLD),
            center_title=True,        
            bgcolor="blueGrey900", 
            actions=[self.theme_icon, ft.Container(width=10)]
        )

        self.show_login()

    def toggle_theme(self, e):
        if self.page.theme_mode == ft.ThemeMode.DARK:
            self.page.theme_mode = ft.ThemeMode.LIGHT
            self.theme_icon.icon = "dark_mode_outlined" 
            self.page.bgcolor = "blueGrey50"
            self.page.appbar.bgcolor = "blueGrey200"
        else:
            self.page.theme_mode = ft.ThemeMode.DARK
            self.theme_icon.icon = "wb_sunny_outlined" 
            self.page.bgcolor = "blueGrey900"
            self.page.appbar.bgcolor = "blueGrey900"
        self.page.update()

    # --- ANIMAZIONE BACKGROUND A ONDE ---
    def _animation_loop(self):
        """Thread che muove le icone a onde"""
        t = 0 # Tempo per la funzione seno
        
        while self.anim_running:
            try:
                # Dimensioni schermo (fallback se non ancora caricato)
                h = self.page.height if self.page.height else 800
                w = self.page.width if self.page.width else 600
                
                t += 0.05
                
                for i, obj in enumerate(self.background_objs):
                    # obj = {'control': Image, 'speed': float, 'y': float, 'base_x': float, 'amplitude': float}
                    
                    # 1. Movimento Verticale (Caduta)
                    obj['y'] += obj['speed']
                    
                    # 2. Movimento Orizzontale (Onda)
                    # x = posizione_iniziale + ampiezza * sin(tempo + offset_diverso_per_ogni_icona)
                    wave_offset = obj['amplitude'] * math.sin(t + i)
                    current_x = obj['base_x'] + wave_offset
                    
                    # 3. Reset se esce dal basso
                    if obj['y'] > h:
                        obj['y'] = -50 # Riparte da sopra
                        obj['base_x'] = random.randint(0, int(w)) # Nuova colonna casuale
                    
                    # Applica posizione
                    obj['control'].top = obj['y']
                    obj['control'].left = current_x

                self.page.update()
                time.sleep(0.02) # ~50 FPS per fluidità
            except Exception as e:
                # Se la pagina viene chiusa o c'è un errore, ferma il loop
                print(f"Animation stopping: {e}")
                break

    def start_background_animation(self):
        """Crea le icone e avvia il thread"""
        self.anim_running = True
        self.background_objs = []
        
        # Creiamo 30 icone piccole
        for _ in range(30):
            symbol = random.choice(["x.png", "o.png"])
            size = random.randint(20, 40) # Piccole
            
            start_x = random.randint(0, 1000)
            start_y = random.randint(-800, 0) # Partono fuori schermo o sparse
            
            speed = random.uniform(1, 3) # Velocità caduta
            amplitude = random.randint(20, 60) # Quanto è larga l'onda
            
            img = ft.Image(
                src=symbol,
                width=size,
                height=size,
                opacity=0.3, # Semi-trasparenti
                fit=ft.ImageFit.CONTAIN,
                left=start_x,
                top=start_y,
                # IMPORTANTE: animate_position=None qui perché gestiamo noi ogni frame
            )
            
            self.background_objs.append({
                'control': img,
                'speed': speed,
                'y': float(start_y),
                'base_x': float(start_x),
                'amplitude': amplitude
            })
            
        # Avvia il thread
        threading.Thread(target=self._animation_loop, daemon=True).start()

    def stop_animation(self):
        self.anim_running = False

    # --- DIALOGHI ---
    def request_exit_dialog(self, e):
        self.current_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Vuoi uscire?"),
            content=ft.Text("Perderai la connessione e tornerai al login."),
            actions=[
                ft.TextButton("Annulla", on_click=self.close_dialog),
                ft.TextButton("Esci", on_click=self.confirm_exit_and_logout, style=ft.ButtonStyle(color="red")),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.open(self.current_dialog)

    def close_dialog(self, e):
        if self.current_dialog:
            self.page.close(self.current_dialog)
            self.current_dialog = None

    def confirm_exit_and_logout(self, e):
        self.close_dialog(e)
        self.logout(None)

    # --- LOGIN SCREEN ---
    def show_login(self):
        # 1. Pulizia e Stop vecchie animazioni
        self.stop_animation()
        time.sleep(0.1) # Breve pausa per essere sicuri che il thread si fermi
        
        self.page.controls.clear()
        if self.exit_button:
            self.exit_button.visible = False 
            self.page.update() 

        # 2. Setup Form Login
        default_nick = self.nickname if self.nickname else ""
        self.nickname_input = ft.TextField(
            label="Nickname", width=200, text_align=ft.TextAlign.CENTER,
            value=default_nick, on_submit=self.on_connect, max_length=15,
            #bgcolor="#CC37474F", # Input scuro leggibile
            border_color="white"
        )
        self.error_text = ft.Text(value="", color="red", size=14, weight=ft.FontWeight.BOLD, visible=False, text_align=ft.TextAlign.CENTER)
        self.login_button = ft.ElevatedButton("Connetti", on_click=self.on_connect, width=150)
        
        # Contenitore "Vetro" per il login
        login_container = ft.Container(
            content=ft.Column(
                [
                    ft.Text("Benvenuto a Tris!", size=30, weight=ft.FontWeight.BOLD),
                    ft.Divider(height=20, color="transparent"),
                    self.nickname_input, self.error_text, 
                    ft.Container(height=10), self.login_button
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER
            ),
            padding=40,
            border_radius=20,
            width=350,
            # Sfondo nero al 70% di opacità per far risaltare il testo sopra le animazioni
            #bgcolor="#B3000000", 
            #border=ft.border.all(1, ft.Colors.WHITE24),
            #shadow=ft.BoxShadow(
                #spread_radius=1,
                #blur_radius=15,
               # color=ft.Colors.BLACK54,
          #  )
        )

        # 3. Preparazione Animazione
        self.start_background_animation()
        
        # Estrai i controlli immagine dalla lista oggetti
        background_controls = [obj['control'] for obj in self.background_objs]

        # 4. Stack Principale: Sfondo Animato SOTTO, Login SOPRA
        login_stack = ft.Stack(
            controls=background_controls + [
                ft.Container(
                    content=login_container,
                    alignment=ft.alignment.center, # Centra il form
                    expand=True
                )
            ],
            expand=True 
        )

        self.page.add(login_stack)
        self.page.update()

    def on_connect(self, e):
        self.error_text.visible = False
        self.page.update()
        nick_val = self.nickname_input.value.strip()
        
        error_msg = None
        if not nick_val: error_msg = "Il nickname non può essere vuoto."
        elif len(nick_val) < 3: error_msg = "Nickname troppo corto (min 3)."
        elif len(nick_val) > 15: error_msg = "Nickname troppo lungo (max 15)."
        elif not nick_val.isalnum(): error_msg = "Usa solo lettere e numeri."
            
        if error_msg:
            self.error_text.value = error_msg
            self.error_text.visible = True 
            self.page.update()
            return

        self.nickname = nick_val
        self.login_button.disabled = True
        self.login_button.text = "Connessione..."
        self.nickname_input.disabled = True
        self.page.update()
        self._perform_connection()

    def _perform_connection(self):
        if self.client.sock:
            try: self.client.sock.close()
            except: pass
        self.client.connected = False
        self.client.sock = None

        try:
            self.client.connect()
            self.client.register_callback(self.handle_server_message)
            self.client.send({"action": "join", "player_id": self.nickname})
        except Exception as e:
            self._handle_login_error(f"Impossibile connettersi al server: {e}")

    def _handle_login_error(self, reason):
        print(f"[GUI] Errore Login: {reason}")
        self.error_text.value = reason
        self.error_text.visible = True 
        if self.login_button:
            self.login_button.disabled = False
            self.login_button.text = "Connetti"
        if self.nickname_input:
            self.nickname_input.disabled = False
            self.nickname_input.focus()
        self.page.update()

    def show_waiting_screen(self):
        # FERMA L'ANIMAZIONE QUANDO CAMBI SCHERMATA
        self.stop_animation()
        
        self.exit_button.visible = True 
        self.page.update()
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

    def handle_server_message(self, msg):
        try: self._update_ui(msg)
        except Exception as e: print(f"[GUI ERROR] Errore aggiornamento UI: {e}")

    def _update_ui(self, msg):
        if msg.get("ok") is False:
            self._handle_login_error(msg.get("reason", "Errore"))
            if self.client.sock: self.client.sock.close()
            return
        if msg.get("ok") is True and msg.get("status") == "waiting":
            self.show_waiting_screen()
            return

        msg_type = msg.get("type")
        if msg_type == "connection_lost":
            self.logout(None)
            return
        if msg_type == "match_found":
            self.stop_animation()
            self.room_id = msg["data"]["game_id"]
            self.my_symbol = msg["data"]["you_are"]
            self.opponent = msg["data"]["opponent"]
            self.show_game_board()
        elif msg_type == "game_state":
            data = msg["data"]
            status = data.get("status")
            self.update_board(data["board"], data["turn"], result=data.get("result"))
            if status == "ended":
                self.show_end_dialog(data["result"])

    # --- BOARD A BOTTONI CON IMMAGINI ---
    def show_game_board(self):
        self.stop_animation() # Assicurati che sia ferma
        self.exit_button.visible = True 
        self.page.update()
        
        self.page.controls.clear()
        self.board_items = [] 
        
        self.status_text = ft.Text(
            f"Tu sei: {self.my_symbol} (vs {self.opponent})", 
            size=20, weight=ft.FontWeight.BOLD,
            color="green" if self.my_symbol == "X" else "blue"
        )

        rows = []
        for r in range(3):
            row_controls = []
            for c in range(3):
                idx = r * 3 + c
                
                img = ft.Image(
                    src="x.png",     
                    opacity=0,       
                    width=60, 
                    height=60,
                    fit=ft.ImageFit.CONTAIN
                )
                
                btn = ft.ElevatedButton(
                    content=img,     
                    width=90,        
                    height=90,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=8),
                        padding=0,   
                    ),
                    on_click=lambda e, i=idx: self.on_cell_click(i)
                )
                
                self.board_items.append((btn, img))
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
        for i, val in enumerate(board):
            btn, img = self.board_items[i]
            
            if val == "X":
                img.src = "x.png"
                img.opacity = 1
            elif val == "O":
                img.src = "o.png"
                img.opacity = 1
            else:
                img.src = "x.png" 
                img.opacity = 0   
            
            img.update()

            is_my_turn = (turn == self.my_symbol)
            is_empty = (val is None)
            game_running = (turn is not None)
            
            btn.disabled = not (is_my_turn and is_empty and game_running)
            btn.update()
        
        if self.status_text:
            if turn:
                turn_msg = "Tocca a te!" if turn == self.my_symbol else f"Tocca a {self.opponent}"
                self.status_text.value = f"Tu sei: {self.my_symbol} - {turn_msg}"
                self.status_text.color = "white"
            else:
                self.status_text.value = "Partita Terminata"

        self.page.update()

    def on_cell_click(self, idx):
        if not self.room_id: return
        self.client.send({
            "action": "move", "player_id": self.nickname,
            "room_id": self.room_id, "pos": idx
        })

    def show_end_dialog(self, result):
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

        self.page.controls.clear()
        
        end_screen = ft.Column(
            controls=[
                ft.Text(title_text, size=40, weight=ft.FontWeight.BOLD, color=text_color),
                ft.Divider(height=10, color="transparent"),
                ft.Text(msg_text, size=20),
                ft.Divider(height=40, color="transparent"),
                
                ft.ElevatedButton(
                    text="Gioca di nuovo", icon="refresh",
                    on_click=self.play_again, width=250, height=50,
                    style=ft.ButtonStyle(bgcolor="green", color="white")
                ),
                ft.Divider(height=10, color="transparent"),
                
                ft.TextButton(
                    text="Cambia Nickname (Esci)",
                    on_click=self.logout, style=ft.ButtonStyle(color="grey")
                )
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self.page.add(end_screen)
        self.page.update()

    def play_again(self, e):
        if self.client.sock:
            try: self.client.sock.close()
            except: pass
        self.client.connected = False
        self.client.sock = None
        self.room_id = None
        self.my_symbol = None
        self.opponent = None

        self.page.controls.clear()
        pb = ft.ProgressBar(width=200, color="amber")
        status_txt = ft.Text("Riavvio server in corso...", size=16)
        
        self.page.add(
            ft.Column(
                [
                    ft.Text("Preparazione nuova partita", size=24, weight=ft.FontWeight.BOLD),
                    ft.Divider(height=20, color="transparent"),
                    pb, ft.Divider(height=10, color="transparent"), status_txt
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER
            )
        )
        self.page.update()

        import time
        for i in range(15):
            time.sleep(0.1)
        
        status_txt.value = "Connessione in corso..."
        self.page.update()
        self._perform_connection()

    def logout(self, e):
        if self.client.sock:
            try: self.client.sock.close()
            except: pass
        self.client.connected = False
        self.client.sock = None
        self.show_login()

def main(page: ft.Page):
    TrisFletUI(page)

ft.app(target=main, assets_dir="assets")
