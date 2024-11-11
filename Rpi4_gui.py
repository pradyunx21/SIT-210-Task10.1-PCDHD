#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from PIL import Image, ImageTk
import serial
import datetime
import os
import subprocess
import threading
import json
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np

class TollBoothGUI:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("Smart Toll Booth Management System")
        self.root.geometry("1024x600")
        
        # Theme settings
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # Initialize serial connection
        try:
            self.ser = serial.Serial('/dev/ttyACM0', 9600)
        except:
            print("Serial connection failed - running in demo mode")
            self.ser = None

        # Load transaction history
        self.transaction_history = self.load_transaction_history()
        
        self.setup_gui()
        self.start_serial_thread()

    def setup_gui(self):
        # Create main container
        self.main_container = ctk.CTkTabview(self.root)
        self.main_container.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Add tabs
        self.main_container.add("Live Monitor")
        self.main_container.add("Statistics")
        self.main_container.add("Transaction History")
        
        # Setup Live Monitor tab
        self.setup_live_monitor()
        
        # Setup Statistics tab
        self.setup_statistics()
        
        # Setup Transaction History tab
        self.setup_transaction_history()

    def setup_live_monitor(self):
        live_frame = self.main_container.tab("Live Monitor")
        
        # Status indicators
        status_frame = ctk.CTkFrame(live_frame)
        status_frame.pack(fill="x", padx=10, pady=5)
        
        self.barrier_status = ctk.CTkLabel(status_frame, text="Barrier Status: Closed")
        self.barrier_status.pack(side="left", padx=10)
        
        self.vehicle_status = ctk.CTkLabel(status_frame, text="Vehicle Detection: None")
        self.vehicle_status.pack(side="left", padx=10)
        
        # Latest transaction frame
        transaction_frame = ctk.CTkFrame(live_frame)
        transaction_frame.pack(fill="x", padx=10, pady=5)
        
        self.latest_transaction = ctk.CTkLabel(
            transaction_frame,
            text="Latest Transaction: None",
            font=("Helvetica", 16)
        )
        self.latest_transaction.pack(pady=10)
        
        # Camera feed placeholder
        camera_frame = ctk.CTkFrame(live_frame)
        camera_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.camera_label = ctk.CTkLabel(
            camera_frame,
            text="Camera Feed\n(Live feed will appear here)",
            font=("Helvetica", 20)
        )
        self.camera_label.pack(fill="both", expand=True)

    def setup_statistics(self):
        stats_frame = self.main_container.tab("Statistics")
        
        # Create figure for matplotlib
        fig = Figure(figsize=(6, 4), dpi=100)
        self.plot = fig.add_subplot(111)
        
        # Create some sample data
        dates = [datetime.datetime.now() - datetime.timedelta(days=x) for x in range(7)]
        vehicles = [len([t for t in self.transaction_history 
                        if datetime.datetime.strptime(t['timestamp'], 
                        '%Y-%m-%d %H:%M:%S').date() == date.date()]) 
                   for date in dates]
        
        # Plot the data
        self.plot.clear()
        self.plot.plot(dates, vehicles)
        self.plot.set_title('Daily Vehicle Count')
        self.plot.set_xlabel('Date')
        self.plot.set_ylabel('Number of Vehicles')
        fig.autofmt_xdate()
        
        # Create canvas
        canvas = FigureCanvasTkAgg(fig, master=stats_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        
        # Statistics summary
        stats_summary = ctk.CTkFrame(stats_frame)
        stats_summary.pack(fill="x", padx=10, pady=5)
        
        total_vehicles = len(self.transaction_history)
        total_revenue = sum(t['amount'] for t in self.transaction_history)
        
        ctk.CTkLabel(stats_summary, 
                    text=f"Total Vehicles: {total_vehicles}").pack(side="left", padx=10)
        ctk.CTkLabel(stats_summary, 
                    text=f"Total Revenue: GBP {total_revenue}").pack(side="left", padx=10)

    def setup_transaction_history(self):
        history_frame = self.main_container.tab("Transaction History")
        
        # Create Treeview
        columns = ('timestamp', 'card_id', 'amount', 'balance')
        self.tree = ttk.Treeview(history_frame, columns=columns, show='headings')
        
        # Define headings
        self.tree.heading('timestamp', text='Time')
        self.tree.heading('card_id', text='Card ID')
        self.tree.heading('amount', text='Amount')
        self.tree.heading('balance', text='Balance')
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(history_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack elements
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Populate with existing data
        self.update_transaction_history()

    def load_transaction_history(self):
        try:
            with open('transaction_history.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return []

    def save_transaction_history(self):
        with open('transaction_history.json', 'w', encoding='utf-8') as f:
            json.dump(self.transaction_history, f, ensure_ascii=False)

    def update_transaction_history(self):
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Add all transactions
        for transaction in reversed(self.transaction_history):
            self.tree.insert('', 'end', values=(
                transaction['timestamp'],
                transaction['card_id'],
                f"GBP {transaction['amount']}",
                f"GBP {transaction['balance']}"
            ))

    def process_serial_data(self):
        while True:
            if self.ser and self.ser.in_waiting > 0:
                try:
                    data = self.ser.readline().decode('utf-8').strip()
                    parts = data.split(',')
                    
                    if len(parts) >= 1:
                        event = parts[0]
                        
                        if event == "CAPTURE":
                            self.capture_image()
                        elif event == "TRANSACTION":
                            if len(parts) == 4:
                                card_id = parts[1]
                                amount = int(parts[2])
                                balance = int(parts[3])
                                
                                # Add transaction to history
                                transaction = {
                                    'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    'card_id': card_id,
                                    'amount': amount,
                                    'balance': balance
                                }
                                self.transaction_history.append(transaction)
                                self.save_transaction_history()
                                self.update_transaction_history()
                                
                                # Update latest transaction display
                                self.latest_transaction.configure(
                                    text=f"Latest Transaction: Card {card_id} - Amount: GBP {amount}"
                                )
                                
                                # Update barrier status
                                self.barrier_status.configure(text="Barrier Status: Open")
                        elif event == "INSUFFICIENT":
                            if len(parts) == 4:
                                card_id = parts[1]
                                balance = int(parts[3])
                                self.latest_transaction.configure(
                                    text=f"Insufficient Balance: Card {card_id} - Balance: GBP {balance}"
                                )
                                
                except Exception as e:
                    print(f"Error processing serial data: {e}")

    def capture_image(self):
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        image_path = f"/home/university/toll_images/vehicle_{timestamp}.jpg"
        
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(image_path), exist_ok=True)
            
            subprocess.run(["libcamera-still", "-o", image_path, "-t", "1"], check=True)
            # Update GUI with new image
            self.display_camera_image(image_path)
            # Update barrier status
            self.barrier_status.configure(text="Barrier Status: Closed")
        except subprocess.CalledProcessError as e:
            print(f"Error capturing image: {e}")

    def display_camera_image(self, image_path):
        try:
            image = Image.open(image_path)
            image = image.resize((640, 480))
            photo = ImageTk.PhotoImage(image)
            self.camera_label.configure(image=photo)
            self.camera_label.image = photo
        except Exception as e:
            print(f"Error displaying image: {e}")

    def start_serial_thread(self):
        serial_thread = threading.Thread(target=self.process_serial_data, daemon=True)
        serial_thread.start()

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = TollBoothGUI()
    app.run()
