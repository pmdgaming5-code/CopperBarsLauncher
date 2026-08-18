from __future__ import annotations

import time
import uuid
import zipfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from pathlib import Path

from .core import (
    APP_NAME, APP_VERSION, DEFAULT_VERSION, AppError, Profile,
    VERSION_MANIFEST, MANIFEST_FILE, ROOT,
    ensure_version, import_modpack, launch_game, load_accounts, load_json, load_profiles,
    load_settings, make_offline_account, microsoft_login, recommended_ram_mb,
    request_json, save_accounts, save_profiles, save_settings,
)

BG = "#0a0d12"
PANEL = "#111722"
PANEL2 = "#171e2b"
BORDER = "#252e3e"
TEXT = "#f5f7fb"
MUTED = "#8f9bad"
ACCENT = "#e58516"
ACCENT2 = "#ffb84d"
GREEN = "#32d583"
RED = "#ff5c67"


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
        self._styles()
        self._ui()
        self._refresh()
        self._refresh_manifest_async()

    def _styles(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Copper.TCombobox", fieldbackground=PANEL2, background=PANEL2,
                        foreground=TEXT, arrowcolor=MUTED, bordercolor=BORDER)

    def _label(self, parent: tk.Widget, text: str = "", size: int = 10, color: str = TEXT, bold: bool = False, **kwargs) -> tk.Label:
        return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=color,
                        font=("Segoe UI", size, "bold" if bold else "normal"), **kwargs)

    def _button(self, parent: tk.Widget, text: str, command, primary: bool = False) -> tk.Button:
        return tk.Button(parent, text=text, command=command, bg=ACCENT if primary else PANEL2,
                         fg="white", activebackground=ACCENT2 if primary else "#222c3b",
                         activeforeground="white", bd=0, relief="flat", cursor="hand2",
                         padx=14, pady=10, font=("Segoe UI", 10, "bold"))

    def _card(self, parent: tk.Widget, padx: int = 16, pady: int = 16) -> tk.Frame:
        return tk.Frame(parent, bg=PANEL, highlightbackground=BORDER, highlightthickness=1,
                        padx=padx, pady=pady)

    def _ui(self) -> None:
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=24, pady=(18, 10))
        self._label(header, "COPPERBARS", 23, ACCENT2, True).pack(side="left")
        self._label(header, "Launcher", 15, TEXT, True).pack(side="left", padx=(8, 0), pady=(6, 0))
        self._label(header, f"v{APP_VERSION}", 9, MUTED).pack(side="right", pady=(8, 0))

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=24, pady=(0, 22))
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        side = tk.Frame(body, bg=PANEL, width=205)
        side.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        self._label(side, "WORKSPACE", 9, MUTED, True).pack(anchor="w", padx=18, pady=(18, 10))
        self._button(side, "Play", self._focus_play, True).pack(fill="x", padx=12, pady=4)
        self._button(side, "Profiles", self._profiles).pack(fill="x", padx=12, pady=4)
        self._button(side, "Copper Boost", self._boost).pack(fill="x", padx=12, pady=4)
        self._button(side, "Repair", self._repair).pack(fill="x", padx=12, pady=4)
        self._button(side, "Import Modpack", self._import_modpack).pack(fill="x", padx=12, pady=4)
        self._button(side, "Settings", self._settings).pack(fill="x", padx=12, pady=4)
        self._label(side, "Copper Shield\nPreflight + SHA-1\nSmart Java AutoPilot", 9, MUTED, justify="left").pack(side="bottom", anchor="w", padx=18, pady=18)

        main = tk.Frame(body, bg=BG)
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=2)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(1, weight=1)
        main.rowconfigure(2, weight=1)

        hero = self._card(main, 24, 22)
        hero.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        self._label(hero, "READY WHEN YOU ARE", 9, MUTED, True).pack(anchor="w")
        self._label(hero, "Your Minecraft,\nyour way.", 28, TEXT, True).pack(anchor="w", pady=(4, 8))
        self.status = tk.StringVar(value="Checking launcher health…")
        self._label(hero, "", 10, MUTED, textvariable=self.status).pack(anchor="w")

        launch_card = self._card(main, 20, 18)
        launch_card.grid(row=1, column=0, sticky="nsew", padx=(0, 6))
        self._label(launch_card, "QUICK LAUNCH", 9, MUTED, True).pack(anchor="w")

        self._field_label(launch_card, "Copper Profile")
        self.profile_var = tk.StringVar()
        self.profile_combo = ttk.Combobox(launch_card, textvariable=self.profile_var, state="readonly", style="Copper.TCombobox")
        self.profile_combo.pack(fill="x", pady=(5, 10))
        self.profile_combo.bind("<<ComboboxSelected>>", lambda _e: self._select_profile())

        self._field_label(launch_card, "Minecraft Version")
        self.version_var = tk.StringVar(value=DEFAULT_VERSION)
        self.version_combo = ttk.Combobox(launch_card, textvariable=self.version_var, state="readonly", style="Copper.TCombobox")
        self.version_combo.pack(fill="x", pady=(5, 10))
        self.version_combo.bind("<<ComboboxSelected>>", lambda _e: self._save_profile_state())

        self._field_label(launch_card, "Account")
        self.account_var = tk.StringVar()
        self.account_combo = ttk.Combobox(launch_card, textvariable=self.account_var, state="readonly", style="Copper.TCombobox")
        self.account_combo.pack(fill="x", pady=(5, 14))

        self._button(launch_card, "PLAY NOW", self._launch, True).pack(fill="x", pady=(4, 4))
        self._label(launch_card, "No Java setup required • auto-detected or auto-downloaded", 9, MUTED).pack(pady=(5, 0))

        tools = self._card(main, 18, 18)
        tools.grid(row=1, column=1, sticky="nsew", padx=(6, 0))
        self._label(tools, "COPPER TOOLS", 9, MUTED, True).pack(anchor="w")
        self._metric(tools, "RAM", lambda: f"{self._active_profile().memory_mb} MB")
        self._metric(tools, "Profiles", lambda: str(len(self.profiles)))
        self._metric(tools, "Accounts", lambda: str(len(self.accounts)))
        self._metric(tools, "Recommended", lambda: f"{recommended_ram_mb()} MB")
        self._label(tools, "Highlights", 10, TEXT, True).pack(anchor="w", pady=(12, 7))
        for item in ("• Isolated game folders", "• Official Mojang Java AutoPilot", "• Repair + SHA-1 verification", "• Safe ZIP modpack import", "• One-click performance preset"):
            self._label(tools, item, 9, MUTED).pack(anchor="w", pady=2)

        log_card = self._card(main, 10, 10)
        log_card.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(12, 0))
        self.log = tk.Text(log_card, bg="#080b10", fg="#d7dde7", insertbackground=TEXT,
                           relief="flat", bd=0, font=("Consolas", 9), state="disabled")
        self.log.pack(fill="both", expand=True)
        self._log("CopperBars Launcher started.")

    def _field_label(self, parent: tk.Widget, text: str) -> None:
        self._label(parent, text, 9, MUTED, True).pack(anchor="w")

    def _metric(self, parent: tk.Widget, title: str, value_fn) -> None:
        row = tk.Frame(parent, bg=PANEL2, padx=10, pady=8)
        row.pack(fill="x", pady=4)
        self._label(row, title, 9, MUTED).pack(side="left")
        value = self._label(row, value_fn(), 10, TEXT, True)
        value.pack(side="right")
        def tick() -> None:
            if value.winfo_exists():
                try:
                    value.configure(text=value_fn())
                    value.after(1500, tick)
                except tk.TclError:
                    pass
        value.after(1500, tick)

    def _log(self, text: str) -> None:
        def append() -> None:
            try:
                self.log.configure(state="normal")
                self.log.insert("end", text + "\n")
                self.log.see("end")
                self.log.configure(state="disabled")
            except tk.TclError:
                pass
        self.after(0, append)

    def _status(self, text: str) -> None:
        self.after(0, lambda: self.status.set(text))

    def _active_profile(self) -> Profile:
        wanted = self.profile_var.get()
        for profile in self.profiles:
            if profile.name == wanted:
                return profile
        return self.profiles[0]

    def _refresh(self) -> None:
        self.profile_combo.configure(values=[p.name for p in self.profiles])
        profile = next((p for p in self.profiles if p.id == self.settings.selected_profile), self.profiles[0])
        self.profile_combo.set(profile.name)
        self.version_var.set(profile.version)
        labels = [f"{a.username} · {'Microsoft' if a.type == 'microsoft' else 'Offline'}" for a in self.accounts]
        self.account_combo.configure(values=labels)
        if self.accounts:
            index = next((i for i, a in enumerate(self.accounts) if a.id == self.settings.selected_account), 0)
            self.account_combo.current(index)
        else:
            self.account_combo.set("No account yet")

    def _refresh_manifest_async(self) -> None:
        def worker() -> None:
            try:
                manifest = request_json(VERSION_MANIFEST)
                from .core import save_json
                save_json(MANIFEST_FILE, manifest)
                self.versions = [v["id"] for v in manifest.get("versions", []) if v.get("type") in {"release", "snapshot"}]
                self.after(0, lambda: self.version_combo.configure(values=self.versions[:300]))
                self._status(f"Ready • {len(self.versions)} Minecraft versions")
            except Exception as exc:
                cached = load_json(MANIFEST_FILE, {})
                self.versions = [v["id"] for v in cached.get("versions", []) if v.get("type") in {"release", "snapshot"}]
                self.after(0, lambda: self.version_combo.configure(values=self.versions[:300]))
                self._log(f"Version refresh skipped: {exc}")
                self._status("Ready • using cached version list")
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
        self._log(f"Profile: {profile.name}")

    def _save_profile_state(self) -> None:
        profile = self._active_profile()
        profile.version = self.version_var.get() or DEFAULT_VERSION
        save_profiles(self.profiles)
        self.settings.selected_profile = profile.id
        self.settings.selected_version = profile.version
        self.settings.game_directory = profile.game_directory
        self.settings.memory_mb = profile.memory_mb
        save_settings(self.settings)

    def _focus_play(self) -> None:
        self._status("Ready to launch")

    def _boost(self) -> None:
        profile = self._active_profile()
        profile.memory_mb = recommended_ram_mb()
        profile.extra_jvm_args = "-XX:+UseG1GC -XX:+ParallelRefProcEnabled -XX:MaxGCPauseMillis=75"
        save_profiles(self.profiles)
        self._select_profile()
        self._log(f"Copper Boost applied: {profile.memory_mb} MB")
        self._status("Copper Boost applied")

    def _repair(self) -> None:
        if self.busy:
            return
        profile = self._active_profile()
        self.busy = True
        self._status("Repairing and verifying game files…")
        def worker() -> None:
            try:
                ensure_version(profile.version, self._log)
                self._log(f"Repair complete: {profile.version}")
                self._status("Repair complete")
            except Exception as exc:
                self._log(f"Repair failed: {exc}")
                self._status("Repair failed")
                self.after(0, lambda: messagebox.showerror(APP_NAME, str(exc)))
            finally:
                self.busy = False
        threading.Thread(target=worker, daemon=True).start()

    def _launch(self) -> None:
        if self.busy:
            return
        if not self.accounts:
            self._accounts_dialog()
            return
        index = self.account_combo.current()
        if index < 0 or index >= len(self.accounts):
            messagebox.showerror(APP_NAME, "Bir hesap seçin.")
            return
        self._save_profile_state()
        profile = self._active_profile()
        account = self.accounts[index]
        self.settings.selected_account = account.id
        save_settings(self.settings)
        self.busy = True
        self._status("Copper Shield preflight…")
        def worker() -> None:
            try:
                process = launch_game(profile.version, self.settings, account, self._log)
                self._status(f"Minecraft {profile.version} running")
                self.after(0, lambda: self._watch(process))
            except Exception as exc:
                self._log(f"Launch blocked: {exc}")
                self._status("Launch failed")
                self.after(0, lambda: messagebox.showerror(APP_NAME, str(exc)))
                self.busy = False
        threading.Thread(target=worker, daemon=True).start()

    def _watch(self, process) -> None:
        if process.poll() is None:
            self.after(600, lambda: self._watch(process))
        else:
            self.busy = False
            self._status("Ready")

    def _profiles(self) -> None:
        window = tk.Toplevel(self)
        window.title("Copper Profiles")
        window.geometry("640x430")
        window.configure(bg=BG)
        frame = tk.Frame(window, bg=BG, padx=18, pady=18)
        frame.pack(fill="both", expand=True)
        self._label(frame, "COPPER PROFILES", 18, ACCENT2, True).pack(anchor="w")
        listbox = tk.Listbox(frame, bg=PANEL2, fg=TEXT, selectbackground=ACCENT, relief="flat", font=("Segoe UI", 10))
        listbox.pack(fill="both", expand=True, pady=12)
        for profile in self.profiles:
            listbox.insert("end", f"{profile.name}  •  {profile.version}  •  {profile.memory_mb} MB")
        controls = tk.Frame(frame, bg=BG)
        controls.pack(fill="x")
        self._button(controls, "New Profile", lambda: self._new_profile(window)).pack(side="left")
        self._button(controls, "Accounts", lambda: self._accounts_dialog(window)).pack(side="left", padx=8)
        self._button(controls, "Close", window.destroy).pack(side="right")

    def _new_profile(self, parent: tk.Toplevel) -> None:
        name = simpledialog.askstring("New Copper Profile", "Profile name:", parent=parent)
        if not name:
            return
        clean = name.strip() or f"Profile {len(self.profiles) + 1}"
        profile_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"copperbars:{clean}:{time.time_ns()}"))
        profile = Profile(id=profile_id, name=clean, version=DEFAULT_VERSION, memory_mb=recommended_ram_mb(),
                          game_directory=str(ROOT / "instances" / profile_id), created_at=time.time())
        self.profiles.append(profile)
        save_profiles(self.profiles)
        self._refresh()
        parent.destroy()
        self._profiles()

    def _accounts_dialog(self, parent: tk.Toplevel | None = None) -> None:
        window = tk.Toplevel(self)
        window.title("Copper Account Center")
        window.geometry("520x300")
        window.configure(bg=BG)
        frame = tk.Frame(window, bg=BG, padx=18, pady=18)
        frame.pack(fill="both", expand=True)
        self._label(frame, "ACCOUNT CENTER", 18, ACCENT2, True).pack(anchor="w")
        self._label(frame, "Microsoft device-code login or an offline profile.", 9, MUTED).pack(anchor="w", pady=(5, 18))
        self._button(frame, "Add Microsoft", lambda: self._login_microsoft(window), True).pack(fill="x", pady=5)
        self._button(frame, "Add Offline", lambda: self._add_offline(window)).pack(fill="x", pady=5)
        self._button(frame, "Close", window.destroy).pack(fill="x", pady=5)

    def _login_microsoft(self, window: tk.Toplevel) -> None:
        if self.busy:
            return
        self.busy = True
        self._status("Waiting for Microsoft login…")
        def worker() -> None:
            try:
                account = microsoft_login(self.settings.client_id, self._log)
                self.accounts.append(account)
                self.settings.selected_account = account.id
                save_accounts(self.accounts)
                save_settings(self.settings)
                self.after(0, self._refresh)
                self._status(f"Signed in as {account.username}")
                self.after(0, window.destroy)
            except Exception as exc:
                self._log(f"Microsoft login error: {exc}")
                self._status("Microsoft login failed")
                self.after(0, lambda: messagebox.showerror(APP_NAME, str(exc), parent=window))
            finally:
                self.busy = False
        threading.Thread(target=worker, daemon=True).start()

    def _add_offline(self, window: tk.Toplevel) -> None:
        name = simpledialog.askstring("Offline profile", "Username (3–16 chars):", parent=window)
        if not name:
            return
        try:
            account = make_offline_account(name)
            self.accounts.append(account)
            self.settings.selected_account = account.id
            save_accounts(self.accounts)
            save_settings(self.settings)
            self._refresh()
            self._log(f"Offline profile added: {account.username}")
        except AppError as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=window)

    def _import_modpack(self) -> None:
        profile = self._active_profile()
        path = filedialog.askopenfilename(filetypes=[("Minecraft modpack ZIP", "*.zip"), ("All files", "*.*")])
        if not path:
            return
        try:
            count = import_modpack(path, profile)
            messagebox.showinfo(APP_NAME, f"{count} files imported into {profile.name}.")
            self._log(f"Modpack imported: {count} files")
        except (OSError, zipfile.BadZipFile, AppError) as exc:
            messagebox.showerror(APP_NAME, str(exc))

    def _settings(self) -> None:
        window = tk.Toplevel(self)
        window.title("CopperBars Settings")
        window.geometry("580x430")
        window.configure(bg=BG)
        frame = tk.Frame(window, bg=BG, padx=18, pady=18)
        frame.pack(fill="both", expand=True)
        self._label(frame, "SETTINGS", 18, ACCENT2, True).pack(anchor="w")
        self._label(frame, "Java path is optional; AutoPilot handles it automatically.", 9, MUTED).pack(anchor="w", pady=(5, 14))
        java = tk.StringVar(value=self.settings.java_path)
        self._label(frame, "Optional Java path", 9, MUTED).pack(anchor="w")
        row = tk.Frame(frame, bg=BG)
        row.pack(fill="x", pady=5)
        entry = tk.Entry(row, textvariable=java, bg=PANEL2, fg=TEXT, insertbackground=TEXT, relief="flat")
        entry.pack(side="left", fill="x", expand=True)
        self._button(row, "Browse", lambda: java.set(filedialog.askopenfilename(filetypes=[("Java", "java.exe"), ("All files", "*.*")]))).pack(side="right", padx=(8, 0))
        self._label(frame, "Extra JVM arguments", 9, MUTED).pack(anchor="w", pady=(12, 0))
        extra = tk.StringVar(value=self.settings.extra_jvm_args)
        tk.Entry(frame, textvariable=extra, bg=PANEL2, fg=TEXT, insertbackground=TEXT, relief="flat").pack(fill="x", pady=5)
        width = tk.IntVar(value=self.settings.width)
        height = tk.IntVar(value=self.settings.height)
        self._label(frame, "Resolution", 9, MUTED).pack(anchor="w", pady=(12, 0))
        size = tk.Frame(frame, bg=BG)
        size.pack(anchor="w", pady=5)
        tk.Spinbox(size, from_=800, to=3840, textvariable=width, width=8).pack(side="left")
        self._label(size, " × ", 10, MUTED).pack(side="left")
        tk.Spinbox(size, from_=600, to=2160, textvariable=height, width=8).pack(side="left")
        def save() -> None:
            self.settings.java_path = java.get().strip()
            self.settings.extra_jvm_args = extra.get().strip()
            self.settings.width = max(800, min(3840, int(width.get())))
            self.settings.height = max(600, min(2160, int(height.get())))
            save_settings(self.settings)
            self._log("Settings saved.")
            window.destroy()
        self._button(frame, "Save", save, True).pack(fill="x", pady=(22, 6))
        self._button(frame, "Close", window.destroy).pack(fill="x")


if __name__ == "__main__":
    LauncherApp().mainloop()
