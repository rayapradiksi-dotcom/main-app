# chat_server_customtk_plot.py
import socket
import threading
import datetime
import time
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import collections
import datetime
import re

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 12345
RECV_BUF = 4096

class ChatServer:
    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False

        # clients: client_id -> socket (DICTIONARY untuk O(1) lookup)
        self.clients = {}
        self.client_lock = threading.Lock()
        self.history = []   # list of messages (dictionary)

        # message map: uuid -> (from_id, to_id, timestamp, message)
        self.message_map = {}
        self.message_lock = threading.Lock()

        self.stats_lock = threading.Lock()
        self.time_series = collections.deque(maxlen=200)  # (timestamp, connected_count)

    def start(self):
        if self.running:
            return True, None
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(10)
            self.running = True
            threading.Thread(target=self._accept_loop, daemon=True).start()
            return True, None
        except Exception as e:
            return False, str(e)

    def stop(self):
        self.running = False
        try:
            if self.server_socket:
                self.server_socket.close()
        except:
            pass
        with self.client_lock:
            for cs in list(self.clients.values()):
                try:
                    cs.close()
                except:
                    pass
            self.clients.clear()

    def now_iso():
        return datetime.datetime.now().isoformat(timespec="seconds")

    def _accept_loop(self):
        while self.running:
            try:
                client_sock, client_addr = self.server_socket.accept()
                # Expect the first message to be the ID: format "ID:<client_id>"
                try:
                    data = client_sock.recv(RECV_BUF).decode('utf-8', errors='replace').strip()
                except:
                    client_sock.close()
                    continue
                if not data:
                    client_sock.close()
                    continue

                # Accept "ID:clientid" or raw client id (backward compatibility)
                if data.startswith("ID:"):
                    client_id = data.split(":",1)[1].strip()
                else:
                    client_id = data.strip()

                # Register client
                with self.client_lock:
                    # if client_id exists, close old socket
                    if client_id in self.clients:
                        try:
                            client_sock.sendall(b"ERR:ID_IN_USE")
                        except:
                            pass
                        client_sock.close() 
                        self.log(f"ID {client_id} sudah digunakan, Login ditolak.")
                        continue
                    
                    self.clients[client_id] = client_sock
                    client_count = len(self.clients)
                
                # Record stats OUTSIDE the client_lock
                self._record_stats_with_count(client_count)

                # Start handler thread
                threading.Thread(target=self._handle_client, args=(client_sock, client_addr, client_id), daemon=True).start()
            except OSError:
                break
            except Exception as e:
                self.log(f"Error in accept loop: {e}")
                continue

    def _handle_client(self, client_sock, client_addr, client_id):
        self.log(f"Koneksi dari {client_addr} (ID: {client_id})")
        # notify all that online list changed
        self.broadcast_online()

        try:
            while self.running:
                data = client_sock.recv(RECV_BUF)
                if not data:
                    break
                text = data.decode('utf-8', errors='replace').strip()
                # support multiple lines
                for line in text.splitlines():
                    self._process_line(line.strip(), client_id)
        except Exception as e:
            self.log(f"Error pada client {client_id}: {e}")
        finally:
            # remove client
            with self.client_lock:
                try:
                    if client_id in self.clients:
                        del self.clients[client_id]
                except:
                    pass
                client_count = len(self.clients)
            
            # Record stats OUTSIDE the client_lock
            self._record_stats_with_count(client_count)
            
            self.log(f"Client {client_id} disconnected")
            try:
                client_sock.close()
            except:
                pass
            # broadcast updated online list
            self.broadcast_online()

    # -------------------------------
    # Protocol processing
    # -------------------------------
    def _process_line(self, line, from_id):
        if not line:
            return
        
        # REQ:ONLINE
        if line.startswith("REQ:ONLINE"):
            self._send_online_to(from_id)
            return
        
        # ===== FITUR BROADCAST =====
        # ALL:<message>
        if line.startswith("ALL:"):
            parts = line.split(":", 1)
            if len(parts) >= 2:
                broadcast_msg = parts[1]
                ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._broadcast_message(from_id, broadcast_msg, ts)
                self.log(f"Broadcast dari {from_id}: {broadcast_msg}")
                return
        # ================================

        # MSG:<toID>:<uuid>:<timestamp>:<message>
        if line.startswith("MSG:"):
            parts = line.split(":", 4)
            if len(parts) >= 5:
                _, to_id, mid, ts, msg = parts
                # store mapping
                with self.message_lock:
                    self.message_map[mid] = (from_id, to_id, ts, msg)
                # inform sender that server received -> SENT
                self._send_to_client(from_id, f"STATUS:{mid}:SENT")
                # forward to recipient if online
                sent_ok = self._forward_message(from_id, to_id, mid, ts, msg)
                # if forwarded, optionally send DELIVERED to sender (server-side delivered)
                if sent_ok:
                    # Server indicates delivered (not necessarily read)
                    self._send_to_client(from_id, f"STATUS:{mid}:DELIVERED")
                else:
                    # recipient offline -> inform sender (still keep as SENT but recipient not available)
                    self._send_to_client(from_id, f"STATUS:{mid}:SENT")
                return
            else:
                self._send_to_client(from_id, f"ERR:BadMSGFormat:{line}")
                return

        # MSGFROM:... unlikely to be sent to server by client; ignore or log
        if line.startswith("MSGFROM:"):
            self.log(f"Unhandled MSGFROM from client {from_id}: {line}")
            return

        # STATUS:<uuid>:SENT|DELIVERED|READ
        if line.startswith("STATUS:"):
            parts = line.split(":", 2)
            if len(parts) == 3:
                _, mid, status = parts
                # Forward status to original sender if known
                with self.message_lock:
                    info = self.message_map.get(mid)
                if info:
                    orig_from, orig_to, ts, message = info
                    # The status submission should come from recipient side (orig_to)
                    # Forward status to original sender if it's not the original sender (avoid loops)
                    if from_id != orig_from:
                        self._send_to_client(orig_from, f"STATUS:{mid}:{status}")
                return

        # a fallback - broadcast or log
        self.log(f"Unknown command from {from_id}: {line}")

    # ===== METHOD BROADCAST =====
    def _broadcast_message(self, from_id, message, timestamp):
        """
        Mengirim pesan broadcast ke semua client kecuali pengirim.
        Format: BROADCAST:<from_id>:<timestamp>:<message>
        Kompleksitas: O(n) untuk iterasi, tapi lookup client O(1) karena pakai dictionary
        """
        with self.client_lock:
            recipients = [(cid, sock) for cid, sock in self.clients.items() if cid != from_id]
        
        payload = f"BROADCAST:{from_id}:{timestamp}:{message}"
        success_count = 0
        
        for client_id, client_sock in recipients:
            try:
                client_sock.sendall(payload.encode('utf-8'))
                success_count += 1
            except Exception as e:
                self.log(f"Error broadcasting to {client_id}: {e}")
        
        self.log(f"Broadcast terkirim ke {success_count}/{len(recipients)} client")
        
        # Konfirmasi ke pengirim
        self._send_to_client(from_id, f"BROADCAST:OK:{success_count} clients")

    def _forward_message(self, from_id, to_id, mid, ts, msg):
        with self.client_lock:
            sock = self.clients.get(to_id)

        if not sock:
            return False
        try:
            payload = f"MSGFROM:{from_id}:{mid}:{ts}:{msg}"
            sock.sendall(payload.encode("utf-8"))
            return True
        except Exception as e:
            self.log(f"Error forwarding to {to_id}: {e}")
        return False

    def _send_online_to(self, client_id):
        # Compose online list excluding the recipient
        with self.client_lock:
            ids = [i for i in self.clients.keys() if i != client_id]
        payload = "ONLINE:" + ",".join(ids)
        self._send_to_client(client_id, payload)

    def broadcast_online(self):
        # Get snapshot of clients ONCE
        with self.client_lock:
            ids = list(self.clients.keys())
            clients_snapshot = list(self.clients.items())
        
        payload = "ONLINE:" + ",".join(ids)
        
        # Send outside of lock
        for cid, csock in clients_snapshot:
            try:
                csock.sendall(payload.encode('utf-8'))
            except:
                pass
        
        # Record stats with count we already have
        self._record_stats_with_count(len(ids))
        self.log(f"Online list broadcast ({len(ids)} users)")

    def _send_to_client(self, client_id, message):
        # O(1) lookup menggunakan dictionary
        with self.client_lock:
            sock = self.clients.get(client_id)
        if not sock:
            return False
        try:
            sock.sendall(message.encode('utf-8'))
            return True
        except Exception as e:
            self.log(f"Error send to {client_id}: {e}")
            return False

    # -------------------------------
    # Logging & stats
    # -------------------------------
    def log(self, text):
        # This will be replaced / set by GUI to reflect in UI; here just print
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now}] {text}")

    def _record_stats_with_count(self, count):
        """Record stats with pre-calculated count (avoids nested lock)"""
        with self.stats_lock:
            ts = time.time()
            self.time_series.append((ts, count))

    def _record_stats(self):
        """Legacy method - gets count itself"""
        with self.client_lock:
            cnt = len(self.clients)
        self._record_stats_with_count(cnt)

    def get_stats_series(self):
        with self.stats_lock:
            return list(self.time_series)

    def get_online_ids(self):
        with self.client_lock:
            return list(self.clients.keys())

# -------------------------------
# GUI wrapper with customtkinter and matplotlib
# -------------------------------
class ServerGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Chat Server - Komunikasi Data")
        self.geometry("1100x700")
        self.minsize(1000, 650)

        # server instance
        self.server = ChatServer()

        # Main container with padding
        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.pack(fill="both", expand=True, padx=20, pady=20)

        # Top section - Server Controls
        top_frame = ctk.CTkFrame(main_container, corner_radius=15)
        top_frame.pack(fill="x", pady=(0, 15))
        
        self._build_top_controls(top_frame)

        # Bottom section - split into left and right
        bottom_frame = ctk.CTkFrame(main_container, fg_color="transparent")
        bottom_frame.pack(fill="both", expand=True)

        # Left side - Online Users and Server Log
        left_section = ctk.CTkFrame(bottom_frame, corner_radius=15, width=340)
        left_section.pack(side="left", fill="both", padx=(0, 10), expand=False)
        left_section.pack_propagate(False)
        
        self._build_left_section(left_section)

        # Right side - Statistics Graph
        right_section = ctk.CTkFrame(bottom_frame, corner_radius=15)
        right_section.pack(side="right", fill="both", expand=True)
        
        self._build_right_section(right_section)

        # update loop for UI (online list, stats)
        self.after(1000, self._periodic_update)

        # hook logger
        self.server.log = self._server_log

    def _build_top_controls(self, parent):
        # Title
        title_label = ctk.CTkLabel(
            parent, 
            text="🖥️ Server Controls", 
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title_label.pack(padx=20, pady=(15, 10), anchor="w")

        # Connection settings frame
        settings_frame = ctk.CTkFrame(parent, fg_color="transparent")
        settings_frame.pack(padx=20, pady=(0, 10), fill="x")

        # Host input
        host_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        host_frame.pack(side="left", padx=(0, 15))
        
        ctk.CTkLabel(host_frame, text="Host Address", font=ctk.CTkFont(size=12)).pack(anchor="w")
        self.entry_host = ctk.CTkEntry(host_frame, width=160, height=35)
        self.entry_host.pack(pady=(5, 0))
        self.entry_host.insert(0, DEFAULT_HOST)

        # Port input
        port_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        port_frame.pack(side="left", padx=(0, 15))
        
        ctk.CTkLabel(port_frame, text="Port Number", font=ctk.CTkFont(size=12)).pack(anchor="w")
        self.entry_port = ctk.CTkEntry(port_frame, width=120, height=35)
        self.entry_port.pack(pady=(5, 0))
        self.entry_port.insert(0, str(DEFAULT_PORT))

        # Buttons
        button_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        button_frame.pack(side="left", fill="x", expand=True, padx=(20, 0))

        self.btn_start = ctk.CTkButton(
            button_frame, 
            text="▶ Start Server", 
            command=self._on_start,
            height=35,
            font=ctk.CTkFont(size=14, weight="bold"),
            corner_radius=8
        )
        self.btn_start.pack(side="left", padx=(0, 10), expand=True, fill="x")

        self.btn_stop = ctk.CTkButton(
            button_frame, 
            text="⏹ Stop Server", 
            command=self._on_stop,
            height=35,
            fg_color="#e74c3c",
            hover_color="#c0392b",
            font=ctk.CTkFont(size=14, weight="bold"),
            corner_radius=8
        )
        self.btn_stop.pack(side="left", expand=True, fill="x")
        self.btn_stop.configure(state="disabled")

        # Server status indicator
        self.status_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.status_frame.pack(padx=20, pady=(0, 15), fill="x")
        
        self.status_indicator = ctk.CTkLabel(
            self.status_frame,
            text="● Server Offline",
            font=ctk.CTkFont(size=13),
            text_color="#95a5a6"
        )
        self.status_indicator.pack(side="left")

    def _build_left_section(self, parent):
        # Online Users Section
        users_container = ctk.CTkFrame(parent, fg_color="transparent")
        users_container.pack(fill="both", expand=True, padx=15, pady=(15, 10))
        
        # Title with icon
        title_frame = ctk.CTkFrame(users_container, fg_color="transparent")
        title_frame.pack(fill="x", pady=(0, 5))
        
        ctk.CTkLabel(
            title_frame,
            text="👥 Online Users",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w")

        # User count badge
        self.user_count_label = ctk.CTkLabel(
            title_frame,
            text="0 users",
            font=ctk.CTkFont(size=11),
            text_color="#7f8c8d"
        )
        self.user_count_label.pack(anchor="w", pady=(3, 0))

        # Users listbox with custom styling
        listbox_frame = ctk.CTkFrame(users_container, fg_color="#2b2b2b", corner_radius=8)
        listbox_frame.pack(fill="both", expand=True, pady=(8, 0))

        self.users_listbox = tk.Listbox(
            listbox_frame,
            bg="#2b2b2b",
            fg="#ecf0f1",
            selectbackground="#3498db",
            selectforeground="white",
            font=("Segoe UI", 10),
            borderwidth=0,
            highlightthickness=0,
            height=8
        )
        self.users_listbox.pack(fill="both", expand=True, padx=2, pady=2)

        # Server Log Section
        log_container = ctk.CTkFrame(parent, fg_color="transparent")
        log_container.pack(fill="both", expand=True, padx=15, pady=(10, 15))
        
        ctk.CTkLabel(
            log_container,
            text="📋 Server Log (recent)",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", pady=(0, 8))

        # Log text area
        log_frame = ctk.CTkFrame(log_container, fg_color="#2b2b2b", corner_radius=8)
        log_frame.pack(fill="both", expand=True)

        self.log_small = tk.Text(
            log_frame,
            bg="#2b2b2b",
            fg="#ecf0f1",
            font=("Consolas", 9),
            borderwidth=0,
            highlightthickness=0,
            height=10,
            wrap=tk.WORD
        )
        self.log_small.pack(fill="both", expand=True, padx=2, pady=2)

    def _build_right_section(self, parent):
        # Title
        title_frame = ctk.CTkFrame(parent, fg_color="transparent")
        title_frame.pack(fill="x", padx=20, pady=(15, 10))
        
        ctk.CTkLabel(
            title_frame,
            text="📊 Connection Statistics",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(anchor="w")

        # Plot area
        plot_frame = ctk.CTkFrame(parent, fg_color="#2b2b2b", corner_radius=10)
        plot_frame.pack(fill="both", expand=True, padx=20, pady=(10, 20))

        self.fig = Figure(figsize=(8, 5), dpi=100, facecolor='#2b2b2b')
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor('#2b2b2b')
        self.ax.set_title("Connected Users Over Time", color='#ecf0f1', fontsize=14, pad=15)
        self.ax.set_xlabel("Time", color='#bdc3c7', fontsize=11)
        self.ax.set_ylabel("Users Connected", color='#bdc3c7', fontsize=11)
        self.ax.tick_params(colors='#7f8c8d', labelsize=9)
        self.ax.spines['bottom'].set_color('#34495e')
        self.ax.spines['top'].set_color('#34495e')
        self.ax.spines['left'].set_color('#34495e')
        self.ax.spines['right'].set_color('#34495e')
        self.ax.grid(True, alpha=0.2, color='#7f8c8d', linestyle='--')
        self.line, = self.ax.plot([], [], linewidth=2.5, color='#3498db', marker='o', markersize=4)

        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

    # -----------------------
    # UI callbacks
    # -----------------------
    def _on_start(self):
        host = self.entry_host.get().strip()
        try:
            port = int(self.entry_port.get().strip())
        except:
            messagebox.showerror("Port invalid", "Masukkan port yang valid (angka).")
            return
        # configure server
        self.server.host = host
        self.server.port = port
        ok, err = self.server.start()
        if ok:
            self._append_log(f"Server berjalan di {host}:{port}")
            self.btn_start.configure(state="disabled")
            self.btn_stop.configure(state="normal")
            self.status_indicator.configure(
                text=f"● Server Running on {host}:{port}",
                text_color="#27ae60"
            )
        else:
            messagebox.showerror("Gagal start", f"Gagal memulai server: {err}")

    def _on_stop(self):
        self.server.stop()
        self._append_log("Server dihentikan.")
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.status_indicator.configure(
            text="● Server Offline",
            text_color="#95a5a6"
        )
        # clear online list
        self.users_listbox.delete(0, tk.END)
        self.user_count_label.configure(text="0 users")
        self._update_plot()

    # -----------------------
    # Logging helpers
    # -----------------------
    def _server_log(self, txt):
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] {txt}\n"
        def ui_update():
            self.log_small.insert(tk.END, line)
            self.log_small.see(tk.END)
        try:
            self.after(1, ui_update)
        except:
            pass

    def _append_log(self, text):
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_small.insert(tk.END, f"[{ts}] {text}\n")
        self.log_small.see(tk.END)

    # -----------------------
    # Periodic UI update (users list, plot)
    # -----------------------
    def _periodic_update(self):
        # update online users list
        ids = self.server.get_online_ids()
        self.users_listbox.delete(0, tk.END)
        for i in ids:
            self.users_listbox.insert(tk.END, f"  {i}")
        
        # Update user count
        count = len(ids)
        self.user_count_label.configure(text=f"{count} user{'s' if count != 1 else ''} connected")

        self._update_plot()

        self.after(1500, self._periodic_update)

    def _update_plot(self):
        series = self.server.get_stats_series()
        if not series:
            # clear
            self.ax.cla()
            self.ax.set_facecolor('#2b2b2b')
            self.ax.set_title("Connected Users Over Time", color='#ecf0f1', fontsize=14, pad=15)
            self.ax.set_xlabel("Time", color='#bdc3c7', fontsize=11)
            self.ax.set_ylabel("Users Connected", color='#bdc3c7', fontsize=11)
            self.ax.tick_params(colors='#7f8c8d', labelsize=9)
            self.ax.spines['bottom'].set_color('#34495e')
            self.ax.spines['top'].set_color('#34495e')
            self.ax.spines['left'].set_color('#34495e')
            self.ax.spines['right'].set_color('#34495e')
            self.ax.grid(True, alpha=0.2, color='#7f8c8d', linestyle='--')
            self.canvas.draw()
            return
        # series: list of (ts, count)
        xs = [datetime.datetime.fromtimestamp(t[0]) for t in series]
        ys = [t[1] for t in series]
        self.ax.cla()
        self.ax.set_facecolor('#2b2b2b')
        self.ax.plot(xs, ys, linewidth=2.5, color='#3498db', marker='o', markersize=4)
        self.ax.fill_between(xs, ys, alpha=0.3, color='#3498db')
        self.ax.set_title("Connected Users Over Time", color='#ecf0f1', fontsize=14, pad=15)
        self.ax.set_xlabel("Time", color='#bdc3c7', fontsize=11)
        self.ax.set_ylabel("Users Connected", color='#bdc3c7', fontsize=11)
        self.ax.tick_params(colors='#7f8c8d', labelsize=9)
        self.ax.spines['bottom'].set_color('#34495e')
        self.ax.spines['top'].set_color('#34495e')
        self.ax.spines['left'].set_color('#34495e')
        self.ax.spines['right'].set_color('#34495e')
        self.ax.grid(True, alpha=0.2, color='#7f8c8d', linestyle='--')
        # beautify x ticks
        self.fig.autofmt_xdate()
        self.canvas.draw()

    def on_closing(self):
        if messagebox.askokcancel("Quit", "Keluar dan hentikan server?"):
            try:
                self.server.stop()
            except:
                pass
            self.destroy()

if __name__ == "__main__":
    app = ServerGUI()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()