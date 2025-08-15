import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from ctypes import windll, wintypes, Structure, c_long, byref, WINFUNCTYPE
from typing import Optional, Tuple, List
import keyboard


class WindowInfo:
    """Container for window information"""
    def __init__(self, hwnd: int, title: str):
        self.hwnd = hwnd
        self.title = title
    
    def __str__(self) -> str:
        return f"{self.title} ({self.hwnd})"


class ClickPosition:
    """Container for click position coordinates"""
    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y
    
    def __str__(self) -> str:
        return f"({self.x}, {self.y})"


class WindowsAPI:
    WM_LBUTTONDOWN = 0x0201
    WM_LBUTTONUP = 0x0202
    WM_RBUTTONDOWN = 0x0204
    WM_RBUTTONUP = 0x0205
    
    @staticmethod
    def get_cursor_position() -> Tuple[int, int]:
        """Get current mouse cursor position"""
        class POINT(Structure):
            _fields_ = [("x", c_long), ("y", c_long)]
        
        point = POINT()
        windll.user32.GetCursorPos(byref(point))
        return point.x, point.y
    
    @staticmethod
    def screen_to_client(hwnd: int, x: int, y: int) -> Tuple[int, int]:
        """Convert screen coordinates to client window coordinates"""
        class POINT(Structure):
            _fields_ = [("x", c_long), ("y", c_long)]
        
        point = POINT(x, y)
        windll.user32.ScreenToClient(hwnd, byref(point))
        return point.x, point.y
    
    @staticmethod
    def is_window_valid(hwnd: int) -> bool:
        """Check if a window handle is valid"""
        return bool(windll.user32.IsWindow(hwnd))
    
    @staticmethod
    def is_window_visible(hwnd: int) -> bool:
        """Check if a window is visible"""
        return bool(windll.user32.IsWindowVisible(hwnd))
    
    @staticmethod
    def get_window_text(hwnd: int) -> str:
        """Get the title text of a window"""
        length = windll.user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        
        buffer = (wintypes.WCHAR * (length + 1))()
        windll.user32.GetWindowTextW(hwnd, buffer, length + 1)
        return ''.join(buffer).rstrip('\x00')
    
    @staticmethod
    def enumerate_windows() -> List[WindowInfo]:
        """Enumerate all visible windows"""
        windows = []
        
        def enum_callback(hwnd: int, lParam: int) -> bool:
            if WindowsAPI.is_window_visible(hwnd):
                title = WindowsAPI.get_window_text(hwnd)
                if title.strip():  # Only include windows with titles
                    windows.append(WindowInfo(hwnd, title))
            return True  # Continue enumeration
        
        # Define callback function type for EnumWindows
        ENUM_PROC = WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        callback = ENUM_PROC(enum_callback)
        
        windll.user32.EnumWindows(callback, 0)
        return sorted(windows, key=lambda w: w.title.lower())
    
    @staticmethod
    def send_mouse_click(hwnd: int, x: int, y: int, click_type: str) -> None:
        """Send mouse click to specified window at given coordinates"""
        if not WindowsAPI.is_window_valid(hwnd):
            raise ValueError("Invalid window handle")
        
        # Convert to client coordinates
        client_x, client_y = WindowsAPI.screen_to_client(hwnd, x, y)
        
        # Create lParam for the click position
        lParam = (client_y << 16) | (client_x & 0xFFFF)
        
        if click_type == "Left Click":
            windll.user32.PostMessageW(hwnd, WindowsAPI.WM_LBUTTONDOWN, 1, lParam)
            time.sleep(0.01)  # Small delay between down and up
            windll.user32.PostMessageW(hwnd, WindowsAPI.WM_LBUTTONUP, 0, lParam)
            
        elif click_type == "Right Click":
            windll.user32.PostMessageW(hwnd, WindowsAPI.WM_RBUTTONDOWN, 2, lParam)
            time.sleep(0.01)
            windll.user32.PostMessageW(hwnd, WindowsAPI.WM_RBUTTONUP, 0, lParam)
            
        elif click_type == "Double Click":
            # First click
            windll.user32.PostMessageW(hwnd, WindowsAPI.WM_LBUTTONDOWN, 1, lParam)
            windll.user32.PostMessageW(hwnd, WindowsAPI.WM_LBUTTONUP, 0, lParam)
            time.sleep(0.05)  # Delay between clicks
            # Second click
            windll.user32.PostMessageW(hwnd, WindowsAPI.WM_LBUTTONDOWN, 1, lParam)
            windll.user32.PostMessageW(hwnd, WindowsAPI.WM_LBUTTONUP, 0, lParam)


class AutoClickerApp:
    """
    Main application class for the Auto Clicker
    Handles GUI, user interactions, and clicking automation
    """
    
    def __init__(self):
        """Initialize the application"""
        # Application state
        self.is_running = False
        self.click_position: Optional[ClickPosition] = None
        self.selected_window: Optional[WindowInfo] = None
        self.position_selection_active = False
        
        # Create and configure main window
        self.root = self._create_main_window()
        self._setup_styles()
        self._create_gui()
        self._bind_hotkeys()
        
        # Initial window refresh
        self.refresh_window_list()
    
    def _create_main_window(self) -> tk.Tk:
        """Create and configure the main application window"""
        root = tk.Tk()
        root.title("Finger of God")
        root.geometry("650x600")
        root.resizable(False, False)
        root.configure(bg='#f0f0f0')
        
        # Center the window on screen
        root.update_idletasks()
        x = (root.winfo_screenwidth() // 2) - (root.winfo_width() // 2)
        y = (root.winfo_screenheight() // 2) - (root.winfo_height() // 2)
        root.geometry(f"+{x}+{y}")
        
        # Handle window closing
        root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        return root
    
    def _setup_styles(self) -> None:
        """Configure ttk styles for consistent appearance"""
        style = ttk.Style()
        
        # Configure styles
        style.configure('Title.TLabel', font=('Segoe UI', 14, 'bold'), foreground='#2c3e50')
        style.configure('Subtitle.TLabel', font=('Segoe UI', 9), foreground='#7f8c8d')
        style.configure('Status.TLabel', font=('Segoe UI', 10), foreground='#34495e')
        style.configure('Success.TLabel', font=('Segoe UI', 10), foreground='#27ae60')
        style.configure('Error.TLabel', font=('Segoe UI', 10), foreground='#e74c3c')
        
        style.configure('Main.TLabelframe', padding=15)
        style.configure('Action.TButton', font=('Segoe UI', 11, 'bold'), padding=(10, 8))
    
    def _create_gui(self) -> None:
        """Create the main GUI interface"""
        # Main container with padding
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Create sections
        self._create_header(main_frame)
        self._create_window_selection_section(main_frame)
        self._create_click_settings_section(main_frame)
        self._create_control_section(main_frame)
    
    def _create_header(self, parent: ttk.Frame) -> None:
        """Create the application header"""
        header_frame = ttk.Frame(parent)
        header_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Label(
            header_frame,
            text="Finger of God",
            style='Title.TLabel'
        ).pack()
        
        ttk.Label(
            header_frame,
            text="A background auto-clicker by Steins",
            style='Subtitle.TLabel'
        ).pack(pady=(5, 0))
    
    def _create_window_selection_section(self, parent: ttk.Frame) -> None:
        """Create the window selection section"""
        window_frame = ttk.LabelFrame(parent, text="Target Window", style='Main.TLabelframe')
        window_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Window list with scrollbar
        list_frame = ttk.Frame(window_frame)
        list_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.window_listbox = tk.Listbox(
            list_frame,
            height=6,
            font=('Segoe UI', 9),
            selectmode=tk.SINGLE,
            relief=tk.FLAT,
            bd=1,
            highlightthickness=1,
            highlightcolor='#3498db'
        )
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        self.window_listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.window_listbox.yview)
        
        self.window_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Refresh button
        refresh_btn = ttk.Button(
            window_frame,
            text="Refresh Window List",
            command=self.refresh_window_list
        )
        refresh_btn.pack()
        
        # Bind selection event
        self.window_listbox.bind('<<ListboxSelect>>', self._on_window_select)
    
    def _create_click_settings_section(self, parent: ttk.Frame) -> None:
        """Create the click settings section"""
        settings_frame = ttk.LabelFrame(parent, text="Click Settings", style='Main.TLabelframe')
        settings_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Position selection
        pos_frame = ttk.Frame(settings_frame)
        pos_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.position_label = ttk.Label(
            pos_frame,
            text="Position: Not selected",
            style='Status.TLabel'
        )
        self.position_label.pack(side=tk.LEFT)
        
        self.select_position_btn = ttk.Button(
            pos_frame,
            text="Select Position (F8)",
            command=self.start_position_selection
        )
        self.select_position_btn.pack(side=tk.RIGHT)
        
        # Click type selection
        type_frame = ttk.Frame(settings_frame)
        type_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(type_frame, text="Click Type:", style='Status.TLabel').pack(side=tk.LEFT)
        
        self.click_type_var = tk.StringVar(value="Left Click")
        self.click_type_combo = ttk.Combobox(
            type_frame,
            textvariable=self.click_type_var,
            values=["Left Click", "Right Click", "Double Click"],
            state='readonly',
            width=15
        )
        self.click_type_combo.pack(side=tk.RIGHT)
        
        # Delay settings
        delay_frame = ttk.Frame(settings_frame)
        delay_frame.pack(fill=tk.X)
        
        ttk.Label(delay_frame, text="Delay (milliseconds):", style='Status.TLabel').pack(side=tk.LEFT)
        
        # Validate delay input
        vcmd = (self.root.register(self._validate_delay), '%P')
        self.delay_var = tk.StringVar(value="100")
        self.delay_spinbox = ttk.Spinbox(
            delay_frame,
            textvariable=self.delay_var,
            from_=1,
            to=999999,
            increment=1,
            width=10,
            validate='key',
            validatecommand=vcmd
        )
        self.delay_spinbox.pack(side=tk.RIGHT)
    
    def _create_control_section(self, parent: ttk.Frame) -> None:
        """Create the control section"""
        control_frame = ttk.LabelFrame(parent, text="Controls", style='Main.TLabelframe')
        control_frame.pack(fill=tk.X)
        
        # Start/Stop button
        self.toggle_btn = ttk.Button(
            control_frame,
            text="Start Auto Clicking (F6)",
            command=self.toggle_clicking,
            style='Action.TButton'
        )
        self.toggle_btn.pack(fill=tk.X, pady=(0, 15))
        
        # Status label
        self.status_label = ttk.Label(
            control_frame,
            text="Ready - Select a window and position to begin",
            style='Status.TLabel'
        )
        self.status_label.pack()
        
        # Instructions
        instructions = (
            "Instructions:\n"
            "1. Select a target window from the list above\n"
            "2. Click 'Select Position' and press F8 where you want to click\n"
            "3. Choose your click type and delay\n"
            "4. Press F6 or click Start to begin auto-clicking"
        )
        
        instruction_label = ttk.Label(
            control_frame,
            text=instructions,
            style='Subtitle.TLabel',
            justify=tk.LEFT
        )
        instruction_label.pack(pady=(15, 0), anchor=tk.W)
    
    def _bind_hotkeys(self) -> None:
        """Bind keyboard shortcuts"""
        # Make sure the main window can receive focus
        self.root.focus_set()
        
        # Bind F6 for start/stop
        self.root.bind('<F6>', lambda e: self.toggle_clicking())
        self.root.bind('<KeyPress-F6>', lambda e: self.toggle_clicking())
        
        # Bind F8 for position selection
        self.root.bind('<F8>', lambda e: self._handle_position_hotkey())
        self.root.bind('<KeyPress-F8>', lambda e: self._handle_position_hotkey())
        
        # Allow the window to receive key events
        self.root.bind('<FocusIn>', lambda e: None)
    
    def _validate_delay(self, value: str) -> bool:
        """Validate delay input"""
        if not value:
            return True
        try:
            delay = int(value)
            return 1 <= delay <= 999999
        except ValueError:
            return False
    
    def _on_window_select(self, event) -> None:
        """Handle window selection from listbox"""
        selection = self.window_listbox.curselection()
        if selection:
            index = selection[0]
            window_text = self.window_listbox.get(index)
            # Extract window handle from the text
            hwnd = int(window_text.split('(')[-1].rstrip(')'))
            title = window_text.split(' (')[0]
            self.selected_window = WindowInfo(hwnd, title)
            self._update_status(f"Selected window: {title}")
    
    def refresh_window_list(self) -> None:
        """Refresh the list of available windows"""
        try:
            self.window_listbox.delete(0, tk.END)
            windows = WindowsAPI.enumerate_windows()
            
            for window in windows:
                self.window_listbox.insert(tk.END, str(window))
            
            self._update_status(f"Found {len(windows)} windows")
            
        except Exception as e:
            self._update_status(f"Error refreshing windows: {str(e)}", is_error=True)
    
    def start_position_selection(self) -> None:
        if self.position_selection_active:
            return
        
        self.position_selection_active = True
        self.select_position_btn.config(state='disabled', text="Move mouse and press F8")
        self._update_status("Move your mouse to the desired position and press F8")

        # Minimize the window
        self.root.iconify()

        # Listen for F8 globally
        keyboard.add_hotkey('F8', self._handle_position_hotkey)

    
    def _check_position_selection(self) -> None:
        """Check if position selection is complete"""
        if self.position_selection_active:
            # Schedule next check
            self.root.after(50, self._check_position_selection)
    
    def _handle_position_hotkey(self) -> None:
        if self.position_selection_active:
            x, y = WindowsAPI.get_cursor_position()
            self.click_position = ClickPosition(x, y)

            self.position_label.config(text=f"Position: {self.click_position}")
            self.select_position_btn.config(state='normal', text="Select Position (F8)")

            self.position_selection_active = False

            # Remove hotkey listener
            keyboard.remove_hotkey('F8')

            # Restore window
            self.root.deiconify()
            self.root.lift()
            self.root.focus_set()

            self._update_status("Position selected successfully!", is_success=True)
    
    def toggle_clicking(self) -> None:
        """Start or stop the auto-clicking"""
        if self.is_running:
            self._stop_clicking()
        else:
            self._start_clicking()
    
    def _start_clicking(self) -> None:
        """Start the auto-clicking process"""
        # Validation
        if not self.selected_window:
            messagebox.showwarning("No Window Selected", "Please select a target window first!")
            return
        
        if not self.click_position:
            messagebox.showwarning("No Position Selected", "Please select a click position first!")
            return
        
        if not WindowsAPI.is_window_valid(self.selected_window.hwnd):
            messagebox.showerror("Invalid Window", "The selected window is no longer valid. Please refresh the window list.")
            return
        
        # Start clicking
        self.is_running = True
        self.toggle_btn.config(text="Stop Auto Clicking (F6)")
        self._update_status("Auto-clicking started...")
        
        # Start clicking thread
        self.click_thread = threading.Thread(target=self._clicking_loop, daemon=True)
        self.click_thread.start()
    
    def _stop_clicking(self) -> None:
        """Stop the auto-clicking process"""
        self.is_running = False
        self.toggle_btn.config(text="Start Auto Clicking (F6)")
        self._update_status("Auto-clicking stopped")
    
    def _clicking_loop(self) -> None:
        """Main clicking loop (runs in separate thread)"""
        try:
            while self.is_running:
                # Check if window is still valid
                if not WindowsAPI.is_window_valid(self.selected_window.hwnd):
                    self.root.after(0, lambda: self._handle_clicking_error("Target window closed"))
                    break
                
                # Send click
                WindowsAPI.send_mouse_click(
                    self.selected_window.hwnd,
                    self.click_position.x,
                    self.click_position.y,
                    self.click_type_var.get()
                )
                
                # Wait for specified delay
                delay_ms = int(self.delay_var.get())
                time.sleep(delay_ms / 1000.0)
                
        except Exception as e:
            self.root.after(0, lambda: self._handle_clicking_error(f"Clicking error: {str(e)}"))
    
    def _handle_clicking_error(self, error_message: str) -> None:
        """Handle errors that occur during clicking"""
        self.is_running = False
        self.toggle_btn.config(text="Start Auto Clicking (F6)")
        self._update_status(error_message, is_error=True)
        messagebox.showerror("Auto-Clicking Error", error_message)
    
    def _update_status(self, message: str, is_error: bool = False, is_success: bool = False) -> None:
        """Update the status label"""
        if is_error:
            icon = "ERROR"
            style = 'Error.TLabel'
        elif is_success:
            icon = "SUCCESS"
            style = 'Success.TLabel'
        else:
            icon = "INFO"
            style = 'Status.TLabel'
        
        self.status_label.config(text=f"{icon}: {message}", style=style)
    
    def _on_closing(self) -> None:
        """Handle application closing"""
        try:
            # Stop any running processes
            self.is_running = False
            self.position_selection_active = False
            
            # Small delay to let threads finish
            time.sleep(0.1)
            
            # Destroy the window
            self.root.destroy()
            
        except Exception as e:
            print(f"Error during cleanup: {e}")
            # Force close if there's an error
            self.root.destroy()
    
    def run(self) -> None:
        """Start the application"""
        try:
            self.root.mainloop()
        except Exception as e:
            messagebox.showerror("Fatal Error", f"Application error: {str(e)}")


def main():
    """Main entry point"""
    try:
        app = AutoClickerApp()
        app.run()
    except Exception as e:
        messagebox.showerror("Startup Error", f"Failed to start application: {str(e)}")


if __name__ == "__main__":
    main()
