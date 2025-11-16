# server_flet.py
import flet as ft
import threading
import server as srv


def main(page: ft.Page):
    page.title = "Chat Server - Flet"
    page.vertical_alignment = "start"

    # LISTA MESSAGGI (AUTO-SCROLL)
    log_list = ft.ListView(
        expand=True,
        spacing=5,
        auto_scroll=True   # <<---- AUTO SCROLL ATTIVO
    )

    def on_start_click(_):
        threading.Thread(
            target=srv.start_server,
            args=(log_list, page),
            daemon=True
        ).start()

    def on_stop_click(_):
        srv.stop_server()

    page.add(
        ft.Row([
            ft.ElevatedButton("Avvia Server", on_click=on_start_click),
            ft.ElevatedButton("Ferma Server", on_click=on_stop_click),
        ]),
        log_list
    )


if __name__ == "__main__":
    ft.app(target=main)
