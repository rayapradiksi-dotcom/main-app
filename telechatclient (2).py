# chatclient.py - Telegram Desktop Style
import socket
import threading
import uuid
import datetime
import time
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox

# --- KONFIGURASI TEMA TELEGRAM ---
TG_BG_PRIMARY = "#17212b"
TG_BG_SECONDARY = "#0e1621"
TG_BG_CHAT = "#0e1621"
TG_SIDEBAR_BG = "#17212b"
TG_HEADER_BG = "#17212b"
TG_INPUT_BG = "#2b5278"
TG_ACCENT_BLUE = "#5288c1"
TG_ACCENT_HOVER = "#6da3d5"
TG_MSG_OUT = "#2b5278"
TG_MSG_IN = "#182533"
TG_TEXT_WHITE = "#ffffff"
TG_TEXT_GRAY = "#7e8d9b"
TG_DIVIDER = "#0f1621"
TG_HOVER = "#1c2732"
TG_ONLINE_DOT = "#4dcd5e"

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

print("=== TELEGRAM STYLE CHAT CLIENT ===")
try:
    HOST = input("Server HOST (default: 127.0.0.1): ").strip()
    if not HOST: HOST = "127.0.0.1"
    PORT_INPUT = input("Server PORT (default: 12345): ").strip()
    PORT = int(PORT_INPUT) if PORT_INPUT else 12345
except ValueError:
    PORT = 12345
    
print(f"Connecting to: {HOST}:{PORT}")
print("===================================\n")
RECV_BUF = 4096

class TelegramChatClient(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Chat Client - Inspirasi UI dari Telegram Desktop")
        self.geometry("1200x700")
        self.minsize(800, 600)
        self.configure(fg_color=TG_BG_PRIMARY)

        # Network state
        self.client_socket = None
        self.running = False
        self.client_id = None

        # App state
        self.online_users = []
        self.chat_conversations = {}
        self.current_target = None
        self.messages = {}
        self.reply_to_message = None
        self.is_closing = False
        self.conversations = {}
        self.messages_by_user = {}

        self._build_ui()

    def _build_ui(self):
        # === SIDEBAR (LEFT) ===
        self.sidebar = ctk.CTkFrame(self, width=380, corner_radius=0, fg_color=TG_SIDEBAR_BG)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Sidebar Header
        sidebar_header = ctk.CTkFrame(self.sidebar, height=70, corner_radius=0, fg_color=TG_HEADER_BG)
        sidebar_header.pack(fill="x")

        # Menu button (hamburger)
        menu_btn = ctk.CTkButton(
            sidebar_header, text="☰", width=40, height=40,
            fg_color="transparent", hover_color=TG_HOVER,
            font=("Arial", 20), corner_radius=20
        )
        menu_btn.pack(side="left", padx=10, pady=15)

        # Search bar in header
        self.search_var = tk.StringVar()
        self.entry_search = ctk.CTkEntry(
            sidebar_header, textvariable=self.search_var, 
            placeholder_text="Search",
            fg_color=TG_INPUT_BG, border_width=0, 
            text_color=TG_TEXT_WHITE, corner_radius=20, height=40
        )
        self.entry_search.pack(side="left", fill="x", expand=True, padx=(0, 10), pady=15)
        self.entry_search.bind("<KeyRelease>", self._on_search)

        # Divider
        ctk.CTkFrame(self.sidebar, height=1, fg_color=TG_DIVIDER).pack(fill="x")

        # Tabs (All Chats, Contacts, etc)
        tabs_frame = ctk.CTkFrame(self.sidebar, height=45, fg_color="transparent")
        tabs_frame.pack(fill="x", padx=5)

        self.btn_all_chats = ctk.CTkButton(
            tabs_frame, text="All Chats", height=35,
            fg_color=TG_ACCENT_BLUE, hover_color=TG_ACCENT_HOVER,
            corner_radius=15, font=("Segoe UI", 13, "bold")
        )
        self.btn_all_chats.pack(side="left", padx=5, pady=5, fill="x", expand=True)

        self.btn_contacts = ctk.CTkButton(
            tabs_frame, text="Contacts", height=35,
            fg_color="transparent", hover_color=TG_HOVER,
            text_color=TG_TEXT_GRAY, corner_radius=15,
            font=("Segoe UI", 13)
        )
        self.btn_contacts.pack(side="left", padx=5, pady=5, fill="x", expand=True)

        # Chat list
        self.chat_list_frame = ctk.CTkScrollableFrame(
            self.sidebar, fg_color="transparent"
        )
        self.chat_list_frame.pack(fill="both", expand=True)

        # === MAIN CHAT AREA (RIGHT) ===
        main_area = ctk.CTkFrame(self, fg_color=TG_BG_CHAT, corner_radius=0)
        main_area.pack(side="right", fill="both", expand=True)

        # Chat Header
        self.header_frame = ctk.CTkFrame(
            main_area, height=70, corner_radius=0, fg_color=TG_HEADER_BG
        )
        self.header_frame.pack(fill="x")

        # Profile avatar
        avatar_frame = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        avatar_frame.pack(side="left", padx=15, pady=12)

        self.profile_avatar = ctk.CTkLabel(
            avatar_frame, text="TG", 
            font=("Arial", 18, "bold"),
            text_color="white",
            fg_color=TG_ACCENT_BLUE,
            width=45, height=45,
            corner_radius=22
        )
        self.profile_avatar.pack()

        # Chat info
        chat_info_frame = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        chat_info_frame.pack(side="left", fill="y", pady=12)

        self.label_chat_with = ctk.CTkLabel(
            chat_info_frame, text="Select a chat to start messaging",
            font=("Segoe UI", 15, "bold"),
            text_color=TG_TEXT_WHITE
        )
        self.label_chat_with.pack(anchor="w")

        self.label_chat_status = ctk.CTkLabel(
            chat_info_frame, text="",
            font=("Segoe UI", 12),
            text_color=TG_TEXT_GRAY
        )
        self.label_chat_status.pack(anchor="w")

        # Header actions
        actions_frame = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        actions_frame.pack(side="right", padx=10)

        # Login/Logout button
        self.btn_auth = ctk.CTkButton(
            actions_frame, text="🔑 Login", width=100, height=35,
            fg_color=TG_ACCENT_BLUE, hover_color=TG_ACCENT_HOVER,
            corner_radius=18, command=self.show_login_dialog
        )
        self.btn_auth.pack(side="right", padx=5)

        # Refresh button
        self.btn_refresh = ctk.CTkButton(
            actions_frame, text="🔄", width=35, height=35,
            fg_color="transparent", hover_color=TG_HOVER,
            corner_radius=18, font=("Arial", 16),
            command=self.request_online
        )
        self.btn_refresh.pack(side="right", padx=5)

        # Chat messages area
        self.chat_canvas_frame = ctk.CTkFrame(main_area, fg_color=TG_BG_CHAT)
        self.chat_canvas_frame.pack(fill="both", expand=True)

        self.chat_canvas = tk.Canvas(
            self.chat_canvas_frame, bg=TG_BG_CHAT, highlightthickness=0
        )
        self.chat_scrollbar = ctk.CTkScrollbar(
            self.chat_canvas_frame, command=self.chat_canvas.yview,
            fg_color="transparent", button_color=TG_INPUT_BG
        )

        self.chat_area = ctk.CTkFrame(self.chat_canvas, fg_color=TG_BG_CHAT)
        self.chat_canvas.configure(yscrollcommand=self.chat_scrollbar.set)
        self.chat_scrollbar.pack(side="right", fill="y", padx=2)
        self.chat_canvas.pack(side="left", fill="both", expand=True)
        self.canvas_window = self.chat_canvas.create_window(
            (0, 0), window=self.chat_area, anchor="nw"
        )

        self.chat_area.bind("<Configure>", self._on_chat_configure)
        self.chat_canvas.bind("<Configure>", self._on_canvas_configure)

        # Reply bar (hidden by default)
        self.reply_bar = ctk.CTkFrame(main_area, fg_color=TG_MSG_IN, corner_radius=0)
        
        reply_accent = ctk.CTkFrame(self.reply_bar, width=3, fg_color=TG_ACCENT_BLUE)
        reply_accent.pack(side="left", fill="y", pady=8, padx=(10, 8))
        
        self.reply_label = ctk.CTkLabel(
            self.reply_bar, text="", anchor="w", justify="left", 
            text_color=TG_TEXT_GRAY, font=("Segoe UI", 11)
        )
        self.reply_label.pack(side="left", padx=5, pady=8, fill="x", expand=True)

        cancel_reply_btn = ctk.CTkButton(
            self.reply_bar, text="✕", width=30, height=30,
            command=self.cancel_reply, fg_color="transparent", 
            hover_color=TG_HOVER, corner_radius=15
        )
        cancel_reply_btn.pack(side="right", padx=8)

        # Input area
        input_area = ctk.CTkFrame(main_area, fg_color=TG_HEADER_BG, corner_radius=0)
        input_area.pack(fill="x")

        input_container = ctk.CTkFrame(input_area, fg_color="transparent")
        input_container.pack(fill="x", padx=15, pady=12)

        # Attachment button
        self.btn_attach = ctk.CTkButton(
            input_container, text="📎", width=40, height=40,
            fg_color="transparent", hover_color=TG_HOVER,
            font=("Arial", 18), corner_radius=20
        )
        self.btn_attach.pack(side="left", padx=(0, 8))

        # Message input
        self.entry_message = ctk.CTkTextbox(
            input_container, height=45, wrap="word",
            fg_color=TG_INPUT_BG, text_color=TG_TEXT_WHITE, 
            corner_radius=22, border_width=0, 
            font=("Segoe UI", 14)
        )
        self.entry_message.pack(side="left", fill="both", expand=True)
        self.entry_message.bind("<Return>", self._on_enter_key)

        # Action buttons
        btn_container = ctk.CTkFrame(input_container, fg_color="transparent")
        btn_container.pack(side="right", padx=(8, 0))

        self.btn_broadcast = ctk.CTkButton(
            btn_container, text="📢", width=40, height=40,
            fg_color=TG_ACCENT_BLUE, hover_color=TG_ACCENT_HOVER,
            font=("Arial", 18), corner_radius=20,
            command=self.send_broadcast
        )
        self.btn_broadcast.pack(side="left", padx=2)

        self.btn_send = ctk.CTkButton(
            btn_container, text="➤", width=40, height=40,
            fg_color=TG_ACCENT_BLUE, hover_color=TG_ACCENT_HOVER,
            font=("Arial", 18, "bold"), corner_radius=20,
            command=self.send_message
        )
        self.btn_send.pack(side="left", padx=2)

    # === UI HELPERS ===
    def _on_chat_configure(self, event):
        self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.chat_canvas.itemconfig(self.canvas_window, width=event.width)

    def _scroll_to_bottom(self):
        self.chat_area.update_idletasks()
        self.chat_canvas.update_idletasks()
        self.chat_canvas.yview_moveto(1.0)

    def _on_enter_key(self, event):
        if event.state & 0x1:  # Shift+Enter
            return
        else:
            self.send_message()
            return "break"

    def _on_search(self, event=None):
        self._refresh_chat_list_ui()

    # === LOGIN DIALOG ===
    def show_login_dialog(self):
        if self.client_socket:
            self.disconnect()
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Login")
        dialog.geometry("400x250")
        dialog.configure(fg_color=TG_BG_PRIMARY)
        dialog.resizable(False, False)
        dialog.grab_set()

        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (400 // 2)
        y = (dialog.winfo_screenheight() // 2) - (250 // 2)
        dialog.geometry(f"400x250+{x}+{y}")

        ctk.CTkLabel(
            dialog, text="🔐 Login to Chat",
            font=("Segoe UI", 20, "bold"),
            text_color=TG_TEXT_WHITE
        ).pack(pady=(30, 10))

        ctk.CTkLabel(
            dialog, text="Enter your username to continue",
            font=("Segoe UI", 12),
            text_color=TG_TEXT_GRAY
        ).pack(pady=(0, 20))

        entry_id = ctk.CTkEntry(
            dialog, placeholder_text="Username",
            fg_color=TG_INPUT_BG, border_width=0,
            text_color=TG_TEXT_WHITE, height=45,
            corner_radius=22, font=("Segoe UI", 14)
        )
        entry_id.pack(padx=40, pady=10, fill="x")
        entry_id.focus()

        def do_login():
            cid = entry_id.get().strip()
            if not cid:
                messagebox.showwarning("Required", "Please enter a username")
                return
            
            self.client_id = cid
            try:
                self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_socket.connect((HOST, PORT))
                self.client_socket.sendall(f"ID:{self.client_id}".encode('utf-8'))
                self.running = True
                threading.Thread(target=self.receive_loop, daemon=True).start()

                self.btn_auth.configure(text="🚪 Logout", fg_color="#e74c3c")
                self.request_online()
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Connection Failed", f"Cannot connect to server.\n{e}")
                self.client_socket = None
                dialog.destroy()

        btn_login = ctk.CTkButton(
            dialog, text="Login", height=45,
            fg_color=TG_ACCENT_BLUE, hover_color=TG_ACCENT_HOVER,
            corner_radius=22, font=("Segoe UI", 14, "bold"),
            command=do_login
        )
        btn_login.pack(padx=40, pady=10, fill="x")

        entry_id.bind("<Return>", lambda e: do_login())

    # === NETWORKING ===
    def disconnect(self):
        try:
            self.running = False
            if self.client_socket:
                try:
                    self.client_socket.shutdown(socket.SHUT_RDWR)
                except:
                    pass
                self.client_socket.close()
        except:
            pass
        self.client_socket = None
        self.btn_auth.configure(text="🔑 Login", fg_color=TG_ACCENT_BLUE)
        self.online_users = []
        self._refresh_chat_list_ui()

    def request_online(self):
        if not self.client_socket:
            return
        try:
            self.client_socket.sendall(b"REQ:ONLINE")
        except:
            pass

    def receive_loop(self):
        while self.running:
            try:
                data = self.client_socket.recv(RECV_BUF)
                if not data:
                    self.running = False
                    break
                text = data.decode('utf-8', errors='replace').strip()
                for line in text.splitlines():
                    self._handle_server_line(line.strip())
            except:
                self.running = False
                break

        if self.client_socket:
            self.disconnect()

    def _handle_server_line(self, line):
        if not line:
            return

        if line == "ERR:ID_IN_USE":
            messagebox.showerror("Login Failed", "Username already in use.\nPlease choose another.")
            self.disconnect()
            
        elif line.startswith("ONLINE:"):
            rest = line[len("ONLINE:"):].strip()
            ids = [x for x in rest.split(",") if x and x != self.client_id]
            self.update_online_list(ids)

        elif line.startswith("BROADCAST:OK:"):
            try:
                _, _, count = line.split(":", 2)
                print(f"[INFO] Broadcast sent to {count} users")
            except:
                print("[INFO] Broadcast sent")

        elif line.startswith("BROADCAST:"):
            try:
                prefix = "BROADCAST:"
                rest = line[len(prefix):]
                from_id, rest = rest.split(":", 1)
                ts = rest[:19]
                message = rest[20:]
                self._display_broadcast_in(from_id, message, ts)
            except Exception as e:
                print(f"[ERROR PROCESSING BROADCAST]: {e}")

        elif line.startswith("MSGFROM:"):
            parts = line.split(":", 3)
            if len(parts) >= 4:
                _, from_id, mid, rest = parts
                ts = rest
                message = ""
                try:
                    if len(rest) >= 20 and rest[4] == "-" and rest[19] == ":":
                        ts = rest[:19]
                        message = rest[20:]
                    else:
                        if ":" in rest:
                            ts, message = rest.split(":", 1)
                        else:
                            ts = rest
                except:
                    if ":" in rest:
                        ts, message = rest.split(":", 1)
                    else:
                        ts = rest

                display_msg = message
                reply_info = None

                if message.startswith("REPLY:"):
                    reply_parts = message.split(":", 2)
                    if len(reply_parts) == 3:
                        original_mid = reply_parts[1]
                        display_msg = reply_parts[2]
                        if original_mid in self.messages:
                            orig = self.messages[original_mid]
                            reply_info = {
                                'from': orig.get('from') or 'You',
                                'text': orig.get('text', ''),
                                'mid': original_mid
                            }

                if from_id not in self.conversations:
                    self.conversations[from_id] = []

                if not any(m.get("mid") == mid for m in self.conversations[from_id]):
                    self.conversations[from_id].append({
                        'mid': mid,
                        'message': display_msg,
                        'timestamp': ts,
                        'direction': 'incoming',
                        'sender': from_id
                    })

                if from_id == self.current_target:
                    self._display_incoming(from_id, mid, display_msg, ts, reply_info)
                    try:
                        self.client_socket.sendall(f"STATUS:{mid}:READ".encode('utf-8'))
                    except:
                        pass

                self._update_chat_list(from_id, display_msg, ts, is_outgoing=False)

                try:
                    self.client_socket.sendall(f"STATUS:{mid}:DELIVERED".encode('utf-8'))
                except:
                    pass

        elif line.startswith("STATUS:"):
            parts = line.split(":", 2)
            if len(parts) == 3:
                _, mid, status = parts
                self._update_message_status(mid, status)

    # === CHAT LIST ===
    def update_online_list(self, ids):
        self.online_users = ids
        self._refresh_chat_list_ui()

    def format_time(self, ts: str) -> str:
        if not ts:
            return ""
        try:
            if " " in ts:
                time_part = ts.split(" ")[1]
            else:
                time_part = ts
            parts = time_part.split(":")
            if len(parts) >= 2:
                return f"{parts[0]}:{parts[1]}"
        except:
            pass
        return ts

    def _update_chat_list(self, user_id, message, timestamp, is_outgoing=False):
        try:
            short_time = timestamp.split()[1][:5]
        except:
            short_time = timestamp

        if user_id not in self.chat_conversations:
            self.chat_conversations[user_id] = {
                'last_message': message,
                'last_time': short_time,
                'unread_count': 0
            }
        else:
            conv = self.chat_conversations[user_id]
            conv['last_message'] = message
            conv['last_time'] = short_time
            if not is_outgoing and user_id != self.current_target:
                conv['unread_count'] = conv.get('unread_count', 0) + 1

        self._refresh_chat_list_ui()

    def _refresh_chat_list_ui(self):
        if self.is_closing:
            return
        
        for widget in self.chat_list_frame.winfo_children():
            try:
                widget.destroy()
            except:
                pass

        query = self.search_var.get().lower().strip()
        sorted_convs = sorted(
            self.chat_conversations.items(),
            key=lambda x: x[1]['last_time'], 
            reverse=True
        )

        displayed_users = set()

        def render_row(uid, info=None, is_online=False):
            if query and query not in uid.lower():
                return
            displayed_users.add(uid)

            is_selected = (uid == self.current_target)
            bg_color = TG_HOVER if is_selected else "transparent"

            row = ctk.CTkFrame(
                self.chat_list_frame, 
                fg_color=bg_color, 
                corner_radius=8
            )
            row.pack(fill="x", padx=8, pady=2)

            # Avatar
            avatar_container = ctk.CTkFrame(row, fg_color="transparent")
            avatar_container.pack(side="left", padx=10, pady=10)

            avatar_bg = TG_ACCENT_BLUE if is_online else "#4a5568"
            avatar = ctk.CTkLabel(
                avatar_container,
                text=uid[0].upper(),
                font=("Arial", 18, "bold"),
                text_color="white",
                fg_color=avatar_bg,
                width=50, height=50,
                corner_radius=25
            )
            avatar.pack()

            # Online indicator
            if is_online:
                online_dot = ctk.CTkLabel(
                    avatar_container,
                    text="",
                    width=14, height=14,
                    fg_color=TG_ONLINE_DOT,
                    corner_radius=7
                )
                online_dot.place(x=36, y=36)

            # Content
            content = ctk.CTkFrame(row, fg_color="transparent")
            content.pack(side="left", fill="both", expand=True, padx=8, pady=10)

            # Top line (name + time)
            top = ctk.CTkFrame(content, fg_color="transparent")
            top.pack(fill="x")

            name = ctk.CTkLabel(
                top, text=uid,
                font=("Segoe UI", 14, "bold"),
                text_color=TG_TEXT_WHITE
            )
            name.pack(side="left")

            if info:
                time_lbl = ctk.CTkLabel(
                    top, text=info['last_time'],
                    font=("Segoe UI", 11),
                    text_color=TG_TEXT_GRAY
                )
                time_lbl.pack(side="right")

            # Message preview
            if info:
                preview = info['last_message'][:35] + "..." if len(info['last_message']) > 35 else info['last_message']
                msg_lbl = ctk.CTkLabel(
                    content, text=preview,
                    font=("Segoe UI", 12),
                    text_color=TG_TEXT_GRAY,
                    anchor="w"
                )
                msg_lbl.pack(fill="x")
            else:
                status = "online" if is_online else "last seen recently"
                status_lbl = ctk.CTkLabel(
                    content, text=status,
                    font=("Segoe UI", 12, "italic"),
                    text_color=TG_ACCENT_BLUE if is_online else TG_TEXT_GRAY,
                    anchor="w"
                )
                status_lbl.pack(fill="x")

            # Unread badge
            if info and info.get('unread_count', 0) > 0:
                badge = ctk.CTkLabel(
                    row, 
                    text=str(info['unread_count']),
                    fg_color=TG_ACCENT_BLUE,
                    text_color="white",
                    width=24, height=24,
                    corner_radius=12,
                    font=("Segoe UI", 11, "bold")
                )
                badge.pack(side="right", padx=12)

            # Click handler
            row.bind("<Button-1>", lambda e, u=uid: self.select_user(u))
            for child in row.winfo_children():
                child.bind("<Button-1>", lambda e, u=uid: self.select_user(u))
                for subchild in child.winfo_children():
                    subchild.bind("<Button-1>", lambda e, u=uid: self.select_user(u))

        # Render conversations
        for uid, info in sorted_convs:
            render_row(uid, info=info, is_online=(uid in self.online_users))

        # Render online users without conversations
        for uid in self.online_users:
            if uid not in displayed_users:
                render_row(uid, info=None, is_online=True)

    def select_user(self, uid):
        self.current_target = uid
        self.label_chat_with.configure(text=uid)
        
        # Update status
        if uid in self.online_users:
            self.label_chat_status.configure(text="online", text_color=TG_ACCENT_BLUE)
        else:
            self.label_chat_status.configure(text="last seen recently", text_color=TG_TEXT_GRAY)

        # Update avatar
        self.profile_avatar.configure(text=uid[0].upper())

        if uid in self.chat_conversations:
            self.chat_conversations[uid]['unread_count'] = 0

        self._refresh_chat_list_ui()
        self._load_conversation(uid)

    def _load_conversation(self, user_id):
        for widget in self.chat_area.winfo_children():
            widget.destroy()

        if user_id in self.conversations:
            for msg_data in self.conversations[user_id]:
                if msg_data['direction'] == 'outgoing':
                    self._display_message_from_history(
                        msg_data['message'],
                        msg_data['timestamp'],
                        'outgoing',
                        msg_data.get('status', 'SENT')
                    )
                else:
                    self._display_message_from_history(
                        msg_data['message'],
                        msg_data['timestamp'],
                        'incoming',
                        None,
                        msg_data['sender']
                    )

        self._scroll_to_bottom()

    def _display_message_from_history(self, message, timestamp, direction, status=None, sender=None):
        if direction == 'outgoing':
            frame = ctk.CTkFrame(self.chat_area, fg_color="transparent")
            frame.pack(anchor="e", padx=20, pady=6, fill="x")

            bubble = ctk.CTkFrame(frame, fg_color=TG_MSG_OUT, corner_radius=18)
            bubble.pack(anchor="e")

            msg_lbl = ctk.CTkLabel(
                bubble, text=message, wraplength=500,
                anchor="e", justify="left",
                text_color=TG_TEXT_WHITE,
                font=("Segoe UI", 14)
            )
            msg_lbl.pack(padx=15, pady=(10, 5), anchor="e")

            meta = ctk.CTkFrame(bubble, fg_color="transparent")
            meta.pack(anchor="e", padx=12, pady=(0, 8))

            time_lbl = ctk.CTkLabel(
                meta, text=self.format_time(timestamp),
                font=("Segoe UI", 11),
                text_color="#b3b9bd"
            )
            time_lbl.pack(side="left", padx=(0, 4))

            status_lbl = ctk.CTkLabel(
                meta, text="✓",
                font=("Arial", 12),
                text_color="#b3b9bd"
            )
            status_lbl.pack(side="left")

            if status == "DELIVERED":
                status_lbl.configure(text="✓✓")
            elif status == "READ":
                status_lbl.configure(text="✓✓", text_color="#4dcd5e")

        else:  # incoming
            frame = ctk.CTkFrame(self.chat_area, fg_color="transparent")
            frame.pack(anchor="w", padx=20, pady=6, fill="x")

            bubble = ctk.CTkFrame(frame, fg_color=TG_MSG_IN, corner_radius=18)
            bubble.pack(anchor="w")

            msg_lbl = ctk.CTkLabel(
                bubble, text=message, wraplength=500,
                anchor="w", justify="left",
                text_color=TG_TEXT_WHITE,
                font=("Segoe UI", 14)
            )
            msg_lbl.pack(padx=15, pady=(10, 5), anchor="w")

            time_lbl = ctk.CTkLabel(
                bubble, text=self.format_time(timestamp),
                font=("Segoe UI", 11),
                text_color=TG_TEXT_GRAY
            )
            time_lbl.pack(anchor="e", padx=12, pady=(0, 8))

    # === MESSAGE RENDERING ===
    def _display_broadcast_out(self, message, ts):
        frame = ctk.CTkFrame(self.chat_area, fg_color="transparent")
        frame.pack(anchor="center", padx=20, pady=10, fill="x")

        bubble = ctk.CTkFrame(frame, fg_color="#2c3e50", corner_radius=18)
        bubble.pack(anchor="center")

        header = ctk.CTkLabel(
            bubble, text="📢 BROADCAST MESSAGE",
            font=("Segoe UI", 11, "bold"),
            text_color="#3498db"
        )
        header.pack(padx=15, pady=(10, 5))

        msg_lbl = ctk.CTkLabel(
            bubble, text=message, wraplength=500,
            anchor="center", justify="left",
            text_color=TG_TEXT_WHITE,
            font=("Segoe UI", 14)
        )
        msg_lbl.pack(padx=15, pady=(5, 5))

        time_lbl = ctk.CTkLabel(
            bubble, text=self.format_time(ts),
            font=("Segoe UI", 11),
            text_color=TG_TEXT_GRAY
        )
        time_lbl.pack(anchor="center", padx=12, pady=(0, 10))

        self._scroll_to_bottom()

    def _display_broadcast_in(self, from_id, message, ts):
        frame = ctk.CTkFrame(self.chat_area, fg_color="transparent")
        frame.pack(anchor="w", padx=20, pady=10, fill="x")

        bubble = ctk.CTkFrame(frame, fg_color="#1e3a5f", corner_radius=18)
        bubble.pack(anchor="w")

        header = ctk.CTkLabel(
            bubble, text=f"📢 {from_id} (Broadcast)",
            font=("Segoe UI", 11, "bold"),
            text_color="#5dade2"
        )
        header.pack(padx=15, pady=(10, 5), anchor="w")

        msg_lbl = ctk.CTkLabel(
            bubble, text=message, wraplength=500,
            anchor="w", justify="left",
            text_color=TG_TEXT_WHITE,
            font=("Segoe UI", 14)
        )
        msg_lbl.pack(padx=15, pady=(5, 5), anchor="w")

        time_lbl = ctk.CTkLabel(
            bubble, text=self.format_time(ts),
            font=("Segoe UI", 11),
            text_color=TG_TEXT_GRAY
        )
        time_lbl.pack(anchor="e", padx=12, pady=(0, 10))

        self._scroll_to_bottom()

    def _display_incoming(self, from_id, mid, message, ts, reply_info=None):
        frame = ctk.CTkFrame(self.chat_area, fg_color="transparent")
        frame.pack(anchor="w", padx=20, pady=6, fill="x")

        bubble = ctk.CTkFrame(frame, fg_color=TG_MSG_IN, corner_radius=18)
        bubble.pack(anchor="w")

        if reply_info:
            reply_frame = ctk.CTkFrame(
                bubble, fg_color="#0d1921",
                corner_radius=12, border_width=0
            )
            reply_frame.pack(padx=10, pady=(10, 5), fill="x")

            accent = ctk.CTkFrame(reply_frame, width=3, fg_color=TG_ACCENT_BLUE)
            accent.pack(side="left", fill="y", pady=5)

            reply_content = ctk.CTkFrame(reply_frame, fg_color="transparent")
            reply_content.pack(side="left", padx=8, pady=5, fill="x", expand=True)

            ctk.CTkLabel(
                reply_content, text=reply_info['from'],
                font=("Segoe UI", 11, "bold"),
                text_color=TG_ACCENT_BLUE
            ).pack(anchor="w")

            ctk.CTkLabel(
                reply_content, text=reply_info['text'][:50],
                font=("Segoe UI", 11),
                text_color=TG_TEXT_GRAY
            ).pack(anchor="w")

        msg_lbl = ctk.CTkLabel(
            bubble, text=message, wraplength=500,
            anchor="w", justify="left",
            text_color=TG_TEXT_WHITE,
            font=("Segoe UI", 14)
        )
        msg_lbl.pack(padx=15, pady=(10, 5), anchor="w")

        meta = ctk.CTkFrame(bubble, fg_color="transparent")
        meta.pack(anchor="e", padx=12, pady=(0, 8))

        time_lbl = ctk.CTkLabel(
            meta, text=self.format_time(ts),
            font=("Segoe UI", 11),
            text_color=TG_TEXT_GRAY
        )
        time_lbl.pack(side="left")

        reply_btn = ctk.CTkButton(
            frame, text="↩", width=32, height=32,
            fg_color="transparent", hover_color=TG_HOVER,
            text_color=TG_TEXT_GRAY, corner_radius=16,
            command=lambda: self.set_reply(from_id, message, mid)
        )
        reply_btn.pack(side="left", padx=(8, 0))

        if from_id not in self.conversations:
            self.conversations[from_id] = []

        self.conversations[from_id].append({
            'mid': mid,
            'message': message,
            'timestamp': ts,
            'direction': 'incoming',
            'sender': from_id
        })

        self.messages[mid] = {
            "widget": frame,
            "status": "READ",
            "from": from_id,
            "text": message,
            "time": ts
        }
        self._scroll_to_bottom()

    def _display_outgoing(self, mid, target, message, ts, reply_info=None):
        frame = ctk.CTkFrame(self.chat_area, fg_color="transparent")
        frame.pack(anchor="e", padx=20, pady=6, fill="x")

        bubble = ctk.CTkFrame(frame, fg_color=TG_MSG_OUT, corner_radius=18)
        bubble.pack(anchor="e")

        if reply_info:
            reply_frame = ctk.CTkFrame(
                bubble, fg_color="#1e3d5c",
                corner_radius=12, border_width=0
            )
            reply_frame.pack(padx=10, pady=(10, 5), fill="x")

            accent = ctk.CTkFrame(reply_frame, width=3, fg_color="#5dade2")
            accent.pack(side="left", fill="y", pady=5)

            reply_content = ctk.CTkFrame(reply_frame, fg_color="transparent")
            reply_content.pack(side="left", padx=8, pady=5, fill="x", expand=True)

            name = "You" if reply_info['from'] == self.client_id else reply_info['from']
            ctk.CTkLabel(
                reply_content, text=name,
                font=("Segoe UI", 11, "bold"),
                text_color="#5dade2"
            ).pack(anchor="w")

            ctk.CTkLabel(
                reply_content, text=reply_info['text'][:50],
                font=("Segoe UI", 11),
                text_color="#b3b9bd"
            ).pack(anchor="w")

        msg_lbl = ctk.CTkLabel(
            bubble, text=message, wraplength=500,
            anchor="e", justify="left",
            text_color=TG_TEXT_WHITE,
            font=("Segoe UI", 14)
        )
        msg_lbl.pack(padx=15, pady=(10, 5), anchor="e")

        meta = ctk.CTkFrame(bubble, fg_color="transparent")
        meta.pack(anchor="e", padx=12, pady=(0, 8))

        time_lbl = ctk.CTkLabel(
            meta, text=self.format_time(ts),
            font=("Segoe UI", 11),
            text_color="#b3b9bd"
        )
        time_lbl.pack(side="left", padx=(0, 4))

        status_label = ctk.CTkLabel(
            meta, text="✓",
            font=("Arial", 12),
            text_color="#b3b9bd"
        )
        status_label.pack(side="left")

        if target not in self.conversations:
            self.conversations[target] = []

        self.conversations[target].append({
            'mid': mid,
            'message': message,
            'timestamp': ts,
            'direction': 'outgoing',
            'status': 'SENT'
        })

        self.messages[mid] = {
            "widget": frame,
            "status": "SENT",
            "to": target,
            "status_label": status_label,
            "text": message,
            "time": ts,
            "reply_info": reply_info
        }
        self._scroll_to_bottom()

    def _update_message_status(self, mid, status):
        if mid not in self.messages:
            return
        
        self.messages[mid]["status"] = status
        info = self.messages[mid]
        lbl = info.get("status_label")
        
        if lbl:
            if status == "SENT":
                lbl.configure(text="✓", text_color="#b3b9bd")
            elif status == "DELIVERED":
                lbl.configure(text="✓✓", text_color="#b3b9bd")
            elif status == "READ":
                lbl.configure(text="✓✓", text_color="#4dcd5e")

    # === REPLY FEATURE ===
    def set_reply(self, from_user, message, mid):
        self.reply_to_message = {'from': from_user, 'text': message, 'mid': mid}
        preview = message[:60] + "..." if len(message) > 60 else message
        self.reply_label.configure(text=f"Replying to {from_user}\n{preview}")
        self.reply_bar.pack(fill="x", before=self.footer_area.winfo_children()[0])
        self.entry_message.focus()

    def cancel_reply(self):
        self.reply_to_message = None
        self.reply_bar.pack_forget()

    # === SENDING MESSAGES ===
    def send_message(self):
        if not self.client_socket:
            messagebox.showinfo("Not Connected", "Please login first")
            return

        msg = self.entry_message.get("1.0", "end-1c").strip()
        if not msg:
            return

        if not self.current_target:
            if messagebox.askyesno("Broadcast?", "Send to all online users?"):
                self.send_broadcast()
                return
            else:
                messagebox.showinfo("Info", "Select a chat to send message")
                return

        target = self.current_target
        mid = str(uuid.uuid4())
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        full_msg = msg
        reply_info = None

        if self.reply_to_message:
            reply_info = self.reply_to_message.copy()
            full_msg = f"REPLY:{reply_info['mid']}:{msg}"

        payload = f"MSG:{target}:{mid}:{ts}:{full_msg}"
        try:
            self.client_socket.sendall(payload.encode('utf-8'))
            self._display_outgoing(mid, target, msg, ts, reply_info)
            self.entry_message.delete("1.0", tk.END)
            self.cancel_reply()
            self._update_chat_list(target, msg, ts, is_outgoing=True)
        except Exception as e:
            print(f"Error sending: {e}")

    def send_broadcast(self):
        if not self.client_socket:
            messagebox.showinfo("Not Connected", "Please login first")
            return

        msg = self.entry_message.get("1.0", "end-1c").strip()
        if not msg:
            return

        payload = f"ALL:{msg}"
        try:
            self.client_socket.sendall(payload.encode('utf-8'))
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._display_broadcast_out(msg, ts)
            self.entry_message.delete("1.0", tk.END)
        except Exception as e:
            print(f"Error sending broadcast: {e}")

    def on_closing(self):
        self.is_closing = True
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
        self.destroy()

if __name__ == "__main__":
    app = TelegramChatClient()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()