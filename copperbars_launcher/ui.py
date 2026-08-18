from __future__ import annotations

import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

from .core import (
    APP_NAME, APP_VERSION, DEFAULT_VERSION, Account, AppError, Profile, Settings,
    ensure_version, import_modpack, launch_game, load_accounts, load_profiles, load_settings,
    microsoft_login, recommended_ram_mb, save_accounts, save_profiles, save_settings,
    make_offline_account,
)

BG = "#0b0e13"
PANEL = "#121722"
PANEL_2 = "#171d2a"
TEXT = "#f5f7fb"
MUTED = "#98a2b3"
ACCENT = "#d97706"
ACCENT_2 = "#f59e0b"
SUCCESS = "#22c55e"
DANGER = "#ef4444"


class LauncherApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME} {APP_VERSION}")
        self.geometry("1180x760")
        self.minsize(1000, 680)
        self.configure(bg=BG)
        self.settings = load_settings()
        self.profiles = load_profiles()
        self.accounts = load_accounts()
        self.versions: list[str] = []
        self.busy = False
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self._build_styles()
        self._build_ui()
        self._refresh_all()
        self._load_versions()

    def _build_styles(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Dark.TCombobox", fieldbackground=PANEL_2, background=PANEL_2, foreground=TEXT, arrowcolor=MUTED)
        style.configure("Tree.TButton", font=("Segoe UI", 10, "bold"), padding=(12, 9))

    def _card(self, parent: tk.Widget, padx: int = 16, pady: int = 16) -> tk.Frame:
        return tk.Frame(parent, bg=PANEL, highlightbackground="#202938", highlightthickness=1, padx=padx, pady=pady)

    def _label(self, parent: tk.Widget, text: str, size: int = 10, color: str = TEXT, bold: bool = False) -> tk.Label:
        return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=color, font=("Segoe UI", size, "bold" if bold else "normal"))

    def _button(self, parent: tk.Widget, text: str, command, primary: bool = False) -> tk.Button:
        return tk.Button(parent, text=text, command=command, bg=ACCENT if primary else PANEL_2,
                         fg="white", activebackground=ACCENT_2 if primary else "#232c3d",
                         activeforeground="white", bd=0, relief="flat", cursor="hand2",
                         padx=14, pady=10, font=("Segoe UI", 10, "bold"))

    def _build_ui(self) -> None:
        top = tk.Frame(self, bg=BG, height=70)
        top.pack(fill="x", padx=22, pady=(18, 8))
        self._label(top, "COPPERBARS", 23, ACCENT_2, True).pack(side="left")
        self._label(top, "Launcher", 15, TEXT, True).pack(side="left", padx=(8, 0), pady=(6, 0))
        self._label(top, f"v{APP_VERSION}", 9, MUTED).pack(side="right", pady=(8, 0))

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=22, pady=(0, 20))
        body.columnconfigure(0, weight=0, minsize=200)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        side = tk.Frame(body, bg=PANEL, width=200)
        side.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self._label(side, "WORKSPACE", 9, MUTED, True).pack(anchor="w", padx=18, pady=(18, 10))
        self._button(side, "⌂  Play", self._focus_play, primary=True).pack(fill="x", padx=12, pady=4)
        self._button(side, "▣  Profiles", self._profiles_dialog).pack(fill="x", padx=12, pady=4)
        self._button(side, "⚡  Copper Boost", self._boost).pack(fill="x", padx=12, pady=4)
        self._button(side, "🛠  Repair", self._repair).pack(fill="x", padx=12, pady=4)
        self._button(side, "📦  Import Modpack", self._import_modpack).pack(fill="x", padx=12, pady=4)
        self._button(side, "⚙  Settings", self._settings_dialog).pack(fill="x", padx=12, pady=4)
        self._label(side, "\nCopper Shield\nPreflight + SHA-1\n+ automatic Java", 9, MUTED).pack(side="bottom", anchor="w", padx=18, pady=18)

        self.main = tk.Frame(body, bg=BG)
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.columnconfigure(0, weight=2)
        self.main.columnconfigure(1, weight=1)
        self.main.rowconfigure(1, weight=1)

        hero = self._card(self.main, 24, 22)
        hero.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        self._label(hero, "READY WHEN YOU ARE", 9, MUTED, True).pack(anchor="w")
        self._label(hero, "Your Minecraft,\nyour way.", 27, TEXT, True).pack(anchor="w", pady=(5, 10))
        self.status = tk.StringVar(value="Checking launcher health…")
        self._label(hero, textvariable=self.status, 10, MUTED).pack(anchor="w")

        play = self._card(self.main, 20, 18)
        play.grid(row=1, column=0, sticky="nsew", padx=(0, 6))
        self._label(play, "QUICK LAUNCH", 9, MUTED, True).pack(anchor="w")
        row = tk.Frame(play, bg=PANEL)
        row.pack(fill="x", pady=(12, 8))
        self._label(row, "Profile", 10, MUTED).pack(side="left")
        self.profile_var = tk.StringVar()
        self.profile_combo = ttk.Combobox(row, textvariable=self.profile_var, state="readonly", style="Dark.TCombobox")
        self.profile_combo.pack(side="right", fill="x", expand=True, padx=(20, 0))
        self.profile_combo.bind("<<ComboboxSelected>>", lambda _e: self._select_profile())

        row2 = tk.Frame(play, bg=PANEL)
        row2.pack(fill="x", pady=8)
        self._label(row2, "Version", 10, MUTED).pack(side="left")
        self.version_var = tk.StringVar(value=self.settings.selected_version)
        self.version_combo = ttk.Combobox(row2, textvariable=self.version_var, state="readonly", style="Dark.TCombobox")
        self.version_combo.pack(side="right", fill="x", expand=True, padx=(20, 0))
        self.version_combo.bind("<<ComboboxSelected>>", lambda _e: self._save_profile_state())

        row3 = tk.Frame(play, bg=PANEL)
        row3.pack(fill="x", pady=8)
        self.account_var = tk.StringVar()
        self.account_combo = ttk.Combobox(row3, textvariable=self.account_var, state="readonly", style="Dark.TCombobox")
        self.account_combo.pack(fill="x", expand=True)
        self._button(play, "PLAY NOW", self._launch, primary=True).pack(fill="x", pady=(18, 4))
        self._label(play, "Java is detected/downloaded automatically.", 9, MUTED).pack(anchor="center", pady=(6, 0))

        tools = self._card(self.main, 18, 18)
        tools.grid(row=1, column=1, sticky="nsew", padx=(6, 0))
        self._label(tools, "COPPER TOOLS", 9, MUTED, True).pack(anchor="w")
        self._stat(tools, "Memory", lambda: f"{self._active_profile().memory_mb} MB")
        self._stat(tools, "Profiles", lambda: str(len(self.profiles)))
        self._stat(tools, "Accounts", lambda: str(len(self.accounts)))
        self._stat(tools, "Recommended RAM", lambda: f"{self._recommended()} MB")
        self._label(tools, "\nHighlights", 10, TEXT, True).pack(anchor="w")
        for text in ("• Isolated Copper Profiles", "• Smart Java AutoPilot", "• Repair + integrity checks", "• Safe modpack import", "• Performance preset"):
            self._label(tools, text, 9, MUTED).pack(anchor="w", pady=2)

        log_card = self._card(self.main, 12, 12)
        log_card.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(12, 0))
        self.main.rowconfigure(2, weight=1)
        self.log = tk.Text(log_card, bg="#090c11", fg="#d5dae3", insertbackground=TEXT, relief="flat",
                           font=("Consolas", 9), state="disabled", height=7, wrap="word")
        self.log.pack(fill="both", expand=True)
        self._log("CopperBars Launcher booted.\n")

        for widget in (self.version_combo, self.account_combo, self.profile_combo):
            try:
                widget.option_add("*TCombobox*Listbox.background", PANEL_2)
                widget.option_add("*TCombobox*Listbox.foreground", TEXT)
            except Exception:
                pass

    def _stat(self, parent: tk.Widget, title: str, fn) -> None:
        frame = tk.Frame(parent, bg=PANEL_2, padx=10, pady=8)
        frame.pack(fill="x", pady=5)
        self._label(frame, title, 9, MUTED).pack(side="left")
        value = self._label(frame, fn(), 10, TEXT, True)
        value.pack(side="right")
        value.after(1200, lambda: self._refresh_stat(value, fn))

    def _refresh_stat(self, label: tk.Label, fn) -> None:
        if not label.winfo_exists():
            return
        try:
            label.configure(text=fn())
            label.after(1200, lambda: self._refresh_stat(label, fn))
        except tk.TclError:
            return

    def _recommended(self) -> int:
        try:
            return recommended_ram_mb()
        except Exception:
            return 4096

    def _log(self, text: str) -> None:
        def append() -> None:
            self.log.configure(state="normal")
            self.log.insert("end", text.rstrip() + "\n")
            self.log.see("end")
            self.log.configure(state="disabled")
        self.after(0, append)

    def _set_status(self, text: str) -> None:
        self.after(0, lambda: self.status.set(text))

    def _active_profile(self) -> Profile:
        if not self.profiles:
            self.profiles = load_profiles()
        name = self.profile_var.get()
        for profile in self.profiles:
            if profile.name == name:
                return profile
        return self.profiles[0]

    def _refresh_all(self) -> None:
        labels = [profile.name for profile in self.profiles]
        self.profile_combo.configure(values=labels)
        profile = next((p for p in self.profiles if p.id == self.settings.selected_profile), self.profiles[0])
        self.profile_combo.set(profile.name)
        self.version_var.set(profile.version)
        accounts = [f"{a.username} · {'Microsoft' if a.type == 'microsoft' else 'Offline'}" for a in self.accounts]
        self.account_combo.configure(values=accounts)
        if self.accounts:
            idx = next((i for i, a in enumerate(self.accounts) if a.id == self.settings.selected_account), 0)
            self.account_combo.current(idx)
        else:
            self.account_combo.set("Add a Microsoft or Offline profile via Profiles")

    def _load_versions(self) -> None:
        def worker() -> None:
            try:
                manifest = ensure_version(DEFAULT_VERSION, lambda s: self._log(s)).get("id")
                _ = manifest
                data = ensure_version(DEFAULT_VERSION)
                # The manifest is cached by ensure_version; read it directly for the complete list.
                from .core import load_json, MANIFEST_FILE
                cached = load_json(MANIFEST_FILE, {})
                self.versions = [v["id"] for v in cached.get("versions", []) if v.get("type") in {"release", "snapshot"}]
                self.versions = self.versions[:300]
                self.after(0, lambda: self.version_combo.configure(values=self.versions))
                self._set_status(f"Launcher ready • {len(self.versions)} versions indexed")
            except Exception as exc:
                self._log(f"Version index unavailable: {exc}")
                self._set_status("Offline mode • version list will refresh when you connect")
        threading.Thread(target=worker, daemon=True).start()

    def _select_profile(self) -> None:
        profile = self._active_profile()
        self.settings.selected_profile = profile.id
        self.settings.selected_version = profile.version
        self.settings.memory_mb = profile.memory_mb
        self.settings.game_directory = profile.game_directory
        self.settings.extra_jvm_args = profile.extra_jvm_args
        save_settings(self.settings)
        self.version_var.set(profile.version)
        self._log(f"Profile selected: {profile.name}")

    def _save_profile_state(self) -> None:
        profile = self._active_profile()
        profile.version = self.version_var.get() or DEFAULT_VERSION
        profile.memory_mb = max(1024, min(65536, profile.memory_mb))
        save_profiles(self.profiles)
        self.settings.selected_profile = profile.id
        self.settings.selected_version = profile.version
        self.settings.memory_mb = profile.memory_mb
        self.settings.game_directory = profile.game_directory
        save_settings(self.settings)

    def _focus_play(self) -> None:
        self._log("Play workspace is ready.")

    def _boost(self) -> None:
        profile = self._active_profile()
        profile.memory_mb = self._recommended()
        profile.extra_jvm_args = "-XX:+UseG1GC -XX:+ParallelRefProcEnabled -XX:MaxGCPauseMillis=75"
        save_profiles(self.profiles)
        self._select_profile()
        self._log(f"Copper Boost applied • {profile.memory_mb} MB + tuned JVM")
        self._set_status("Copper Boost applied")

    def _repair(self) -> None:
        if self.busy:
            return
        profile = self._active_profile()
        self.busy = True
        self._set_status("Running Copper Shield repair…")
        def worker() -> None:
            try:
                version = profile.version
                ensure_version(version, self._log)
                self._log(f"Repair complete: {version}")
                self._set_status("Repair complete • files verified")
            except Exception as exc:
                self._log(f"Repair failed: {exc}")
                self._set_status("Repair failed")
                self.after(0, lambda: messagebox.showerror(APP_NAME, str(exc)))
            finally:
                self.busy = False
        threading.Thread(target=worker, daemon=True).start()

    def _launch(self) -> None:
        if self.busy:
            return
        profile = self._active_profile()
        if not self.accounts:
            self._profiles_dialog()
            messagebox.showinfo(APP_NAME, "Önce bir Microsoft veya Offline profil ekleyin.")
            return
        index = self.account_combo.current()
        if index < 0 or index >= len(self.accounts):
            raise_account = True
        else:
            raise_account = False
        if raise_account:
            messagebox.showerror(APP_NAME, "Bir hesap seçin.")
            return
        account = self.accounts[index]
        self._save_profile_state()
        self.busy = True
        self._set_status("Copper Shield preflight running…")
        def worker() -> None:
            try:
                process = launch_game(profile.version, self.settings, account, self._log)
                self._set_status(f"Running Minecraft {profile.version} • Java handled automatically")
                self.after(0, lambda: self._watch(process))
            except Exception as exc:
                self._set_status("Launch blocked by Copper Shield")
                self._log(f"LAUNCH ERROR: {exc}")
                self.after(0, lambda: messagebox.showerror(APP_NAME, str(exc)))
                self.busy = False
        threading.Thread(target=worker, daemon=True).start()

    def _watch(self, process) -> None:
        if process.poll() is None:
            self.after(600, lambda: self._watch(process))
        else:
            self.busy = False
            self._set_status("Ready")

    def _profiles_dialog(self) -> None:
        window = tk.Toplevel(self)
        window.title("Copper Profiles")
        window.geometry("640x430")
        window.configure(bg=BG)
        frame = tk.Frame(window, bg=BG, padx=18, pady=18)
        frame.pack(fill="both", expand=True)
        self._label(frame, "COPPER PROFILES", 18, ACCENT_2, True).pack(anchor="w")
        listbox = tk.Listbox(frame, bg=PANEL_2, fg=TEXT, selectbackground=ACCENT, relief="flat", font=("Segoe UI", 10))
        listbox.pack(fill="both", expand=True, pady=12)
        for profile in self.profiles:
            listbox.insert("end", f"{profile.name}  •  {profile.version}  •  {profile.memory_mb} MB")
        controls = tk.Frame(frame, bg=BG)
        controls.pack(fill="x")
        self._button(controls, "New Profile", lambda: self._create_profile(window)).pack(side="left")
        self._button(controls, "Microsoft / Offline", lambda: self._account_dialog(window)).pack(side="left", padx=8)
        self._button(controls, "Close", window.destroy).pack(side="right")

    def _create_profile(self, parent: tk.Toplevel) -> None:
        dialog = tk.Toplevel(parent)
        dialog.title("New Copper Profile")
        dialog.geometry("420x230")
        dialog.configure(bg=BG)
        frame = tk.Frame(dialog, bg=BG, padx=18, pady=18)
        frame.pack(fill="both", expand=True)
        self._label(frame, "Profile name", 10, MUTED).pack(anchor="w")
        name = tk.StringVar(value=f"Profile {len(self.profiles) + 1}")
        tk.Entry(frame, textvariable=name, bg=PANEL_2, fg=TEXT, insertbackground=TEXT, relief="flat").pack(fill="x", pady=8)
        def create() -> None:
            clean = name.get().strip() or f"Profile {len(self.profiles) + 1}"
            ident = uuid4_text(clean)
            profile = Profile(id=ident, name=clean, game_directory=str(Path(__import__('copperbars_launcher.core', fromlist=['ROOT']).ROOT) / "instances" / ident), created_at=__import__('time').time())
            self.profiles.append(profile)
            save_profiles(self.profiles)
            self._refresh_all()
            dialog.destroy()
            parent.destroy()
            self._profiles_dialog()
        self._button(frame, "Create", create, primary=True).pack(fill="x", pady=10)

    def _account_dialog(self, parent: tk.Toplevel | None = None) -> None:
        window = tk.Toplevel(self) if parent is None else tk.Toplevel(parent)
        window.title("Accounts")
        window.geometry("500x340")
        window.configure(bg=BG)
        frame = tk.Frame(window, bg=BG, padx=18, pady=18)
        frame.pack(fill="both", expand=True)
        self._label(frame, "ACCOUNT CENTER", 18, ACCENT_2, True).pack(anchor="w")
        self._label(frame, "Microsoft login uses the official device-code flow.", 9, MUTED).pack(anchor="w", pady=(4, 14))
        self._button(frame, "Add Microsoft account", lambda: self._login_microsoft(window), primary=True).pack(fill="x", pady=5)
        self._button(frame, "Add Offline profile", lambda: self._add_offline(window)).pack(fill="x", pady=5)
        self._button(frame, "Close", window.destroy).pack(fill="x", pady=5)

    def _login_microsoft(self, window) -> None:
        if self.busy:
            return
        self.busy = True
        self._set_status("Waiting for Microsoft login…")
        def worker() -> None:
            try:
                account = microsoft_login(self.settings.client_id, self._log)
                self.accounts.append(account)
                self.settings.selected_account = account.id
                save_accounts(self.accounts)
                save_settings(self.settings)
                self.after(0, self._refresh_all)
                self._log(f"Microsoft account added: {account.username}")
                self._set_status(f"Signed in as {account.username}")
                self.after(0, window.destroy)
            except Exception as exc:
                self._log(f"Microsoft login error: {exc}")
                self._set_status("Microsoft login failed")
                self.after(0, lambda: messagebox.showerror(APP_NAME, str(exc), parent=window))
            finally:
                self.busy = False
        threading.Thread(target=worker, daemon=True).start()

    def _add_offline(self, window) -> None:
        name = tk.simpledialog.askstring("Offline profile", "Username (3–16 chars):", parent=window)
        if not name:
            return
        try:
            account = make_offline_account(name)
            self.accounts.append(account)
            self.settings.selected_account = account.id
            save_accounts(self.accounts)
            save_settings(self.settings)
            self._refresh_all()
            self._log(f"Offline profile added: {account.username}")
        except AppError as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=window)

    def _import_modpack(self) -> None:
        profile = self._active_profile()
        path = filedialog.askopenfilename(filetypes=[("Modpack ZIP", "*.zip"), ("All files", "*.*")])
        if not path:
            return
        try:
            count = import_modpack(path, profile)
            self._log(f"Imported modpack: {count} files • {profile.name}")
            messagebox.showinfo(APP_NAME, f"{count} dosya profile içine aktarıldı.")
        except (OSError, AppError, zipfile.BadZipFile) as exc:
            messagebox.showerror(APP_NAME, str(exc))

    def _settings_dialog(self) -> None:
        window = tk.Toplevel(self)
        window.title("CopperBars Settings")
        window.geometry("580x480")
        window.configure(bg=BG)
        frame = tk.Frame(window, bg=BG, padx=18, pady=18)
        frame.pack(fill="both", expand=True)
        self._label(frame, "SETTINGS", 18, ACCENT_2, True).pack(anchor="w")
        self._label(frame, "Java path is optional. Copper AutoPilot will handle it.", 9, MUTED).pack(anchor="w", pady=(4, 14))
        self._label(frame, "Optional Java path", 9, MUTED).pack(anchor="w")
        java = tk.StringVar(value=self.settings.java_path)
        row = tk.Frame(frame, bg=BG)
        row.pack(fill="x", pady=6)
        tk.Entry(row, textvariable=java, bg=PANEL_2, fg=TEXT, insertbackground=TEXT, relief="flat").pack(side="left", fill="x", expand=True)
        self._button(row, "Browse", lambda: java.set(filedialog.askopenfilename(filetypes=[("Java", "java.exe"), ("All files", "*.*")] ))).pack(side="right", padx=(8, 0))
        self._label(frame, "Resolution", 9, MUTED).pack(anchor="w", pady=(12, 0))
        width = tk.IntVar(value=self.settings.width)
        height = tk.IntVar(value=self.settings.height)
        r = tk.Frame(frame, bg=BG)
        r.pack(fill="x", pady=6)
        tk.Spinbox(r, from_=800, to=3840, textvariable=width, width=8).pack(side="left")
        self._label(r, " × ", 10, MUTED).pack(side="left")
        tk.Spinbox(r, from_=600, to=2160, textvariable=height, width=8).pack(side="left")
        self._label(frame, "Extra JVM args", 9, MUTED).pack(anchor="w", pady=(12, 0))
        extra = tk.StringVar(value=self.settings.extra_jvm_args)
        tk.Entry(frame, textvariable=extra, bg=PANEL_2, fg=TEXT, insertbackground=TEXT, relief="flat").pack(fill="x", pady=6)
        def save() -> None:
            self.settings.java_path = java.get().strip()
            self.settings.width = max(800, min(3840, int(width.get())))
            self.settings.height = max(600, min(2160, int(height.get())))
            self.settings.extra_jvm_args = extra.get().strip()
            save_settings(self.settings)
            window.destroy()
        self._button(frame, "Save", save, primary=True).pack(fill="x", pady=(22, 6))
        self._button(frame, "Close", window.destroy).pack(fill="x")


def uuid4_text(seed: str) -> str:
    import hashlib
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"copperbars:{seed}"))


if __name__ == "__main__":
    LauncherApp().mainloop()
