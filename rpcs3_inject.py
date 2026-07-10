# Steuert RPCS3s "Skylanders Manager" per Windows-UI-Automation fern.
# Damit landet eine in BetterPortal gewaehlte Figur direkt in RPCS3 (und im laufenden Spiel),
# ohne dass man dort manuell auf Laden klicken muss.
#
# Funktioniert, weil RPCS3 keine Lade-Schnittstelle bietet: der einzige Weg, eine Figur
# einzuspielen, ist der "Laden"-Knopf im Manager-Dialog - den druecken wir automatisiert.
import ctypes
import time

try:
    from pywinauto import Desktop
    _HAVE_PYWINAUTO = True
except ImportError:
    _HAVE_PYWINAUTO = False

MANAGER_CLASS = "skylander_dialog"
FILE_DIALOG_CLASS = "#32770"
LOAD_LABELS = {"Laden", "Load"}
CLEAR_LABELS = {"Leeren", "Clear"}
FILENAME_EDIT_ID = "1148"   # "Dateiname:"-Feld im Windows-Datei-Dialog
OPEN_BUTTON_ID = "1"        # IDOK ("Oeffnen")
CANCEL_BUTTON_ID = "2"      # IDCANCEL ("Abbrechen")

# Menuepfad zum Manager (mehrsprachig); der Blatt-Eintrag heisst immer "Skylanders Portal"
MANAGE_LABELS = ("Verwalten", "Manage")
SUBMENU_LABELS = ("Portale und Tore", "Portals and Gates")
LEAF_LABEL = "Skylanders Portal"
CONFIRM_LABELS = {"Ja", "Yes", "OK"}


class InjectError(Exception):
    pass


def available():
    return _HAVE_PYWINAUTO


def _desktop():
    return Desktop(backend="uia")


def _main_window():
    for w in _desktop().windows():
        if w.class_name() == "main_window" and "RPCS3" in (w.window_text() or ""):
            return w
    return None


def rpcs3_running():
    return _main_window() is not None


def foreground_window():
    """Handle des aktuellen Vordergrund-Fensters (vor der Automation merken)."""
    try:
        return ctypes.windll.user32.GetForegroundWindow()
    except Exception:
        return 0


def restore_foreground(hwnd):
    """Gemerktes Fenster (Spiel/Browser) nach der Automation wieder nach vorn holen."""
    if not hwnd:
        return
    try:
        if not ctypes.windll.user32.IsWindow(hwnd):
            return  # Fenster existiert nicht mehr (z. B. altes Spiel beendet)
        Desktop(backend="win32").window(handle=hwnd).set_focus()
    except Exception:
        pass  # Fokus-Kosmetik darf nie einen Inject scheitern lassen


def raise_game_window():
    """Das Spielfenster (gs_frame) ueber das RPCS3-Hauptfenster heben, ohne ihm
    den Fokus zu geben - so verdeckt das Hauptfenster nach dem Senden nichts mehr."""
    SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x0001, 0x0002, 0x0010
    try:
        for w in _desktop().windows():
            if w.class_name() == "gs_frame":
                ctypes.windll.user32.SetWindowPos(
                    w.handle, 0, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE)
                return
    except Exception:
        pass


def find_manager(main_win=None):
    mw = main_win or _main_window()
    if not mw:
        return None
    for c in mw.children():
        if c.class_name() == MANAGER_CLASS:
            return c
    return None


def _find_menu_item(parent, wanted):
    """Direkt untergeordneten MenuItem-Eintrag finden (ueber das zwischenliegende Menu)."""
    for c in parent.children():
        for sub in c.children():
            t = sub.window_text() or ""
            if t == wanted or t in (wanted if isinstance(wanted, tuple) else (wanted,)):
                return sub
    return None


def _find_menu_item_any(parent, labels):
    for c in parent.children():
        for sub in c.children():
            if (sub.window_text() or "") in labels:
                return sub
    return None


def open_manager(timeout=10.0):
    """Manager-Dialog holen oder ueber das Menue oeffnen."""
    if not _HAVE_PYWINAUTO:
        raise InjectError("Paket 'pywinauto' fehlt (pip install pywinauto).")
    mw = _main_window()
    if not mw:
        raise InjectError("RPCS3 laeuft nicht (Fenster nicht gefunden).")

    mgr = find_manager(mw)
    if mgr:
        return mgr

    mw.set_focus()
    time.sleep(0.3)

    manage = _find_menu_item_any(mw, MANAGE_LABELS)
    if not manage:
        raise InjectError("Menue 'Verwalten' nicht gefunden.")
    manage.expand()
    time.sleep(0.5)

    submenu = _find_menu_item_any(manage, SUBMENU_LABELS)
    if not submenu:
        raise InjectError("Menue 'Portale und Tore' nicht gefunden.")
    submenu.expand()
    time.sleep(0.6)

    leaf = _find_menu_item_any(submenu, {LEAF_LABEL})
    if not leaf:
        raise InjectError("Menuepunkt 'Skylanders Portal' nicht gefunden.")
    leaf.click_input()

    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(0.25)
        mgr = find_manager(mw)
        if mgr:
            return mgr
    raise InjectError("Manager-Dialog ging nicht auf.")


def _find_desc(win, control_type, auto_id):
    """Erstes passendes Nachfahren-Element (Wrapper) finden."""
    for c in win.descendants(control_type=control_type):
        if (c.element_info.automation_id or "") == auto_id:
            return c
    return None


def _load_buttons(mgr):
    return [b for b in mgr.descendants(control_type="Button")
            if (b.window_text() or "") in LOAD_LABELS]


def _clear_buttons(mgr):
    return [b for b in mgr.descendants(control_type="Button")
            if (b.window_text() or "") in CLEAR_LABELS]


def _wait_file_dialog(mgr, timeout=6.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        for c in mgr.children():
            if c.class_name() == FILE_DIALOG_CLASS:
                return c
        time.sleep(0.2)
    return None


def _dismiss_file_dialogs(mgr):
    """Uebrig gebliebene Datei-Dialoge schliessen (Abbrechen)."""
    for _ in range(6):
        fds = [c for c in mgr.children() if c.class_name() == FILE_DIALOG_CLASS]
        if not fds:
            return
        fd = fds[-1]
        btn = _find_desc(fd, "Button", CANCEL_BUTTON_ID)
        try:
            if btn:
                btn.invoke()
            else:
                raise RuntimeError("kein Abbrechen-Button")
        except Exception:
            try:
                fd.set_focus()
                from pywinauto.keyboard import send_keys
                send_keys("{ESC}")
            except Exception:
                pass
        time.sleep(0.4)


def read_slots(mgr=None):
    """Liste der 8 Slot-Namen, wie RPCS3 sie im Manager anzeigt ('None' = leer)."""
    mgr = mgr or find_manager()
    if not mgr:
        return []
    # Nur Edits ausserhalb eines offenen Datei-Dialogs (= die 8 Slot-Zeilen)
    dialog_edits = set()
    for c in mgr.children():
        if c.class_name() == FILE_DIALOG_CLASS:
            for e in c.descendants(control_type="Edit"):
                dialog_edits.add(e.element_info.runtime_id)
    texts = []
    for e in mgr.descendants(control_type="Edit"):
        if e.element_info.runtime_id not in dialog_edits:
            texts.append(e.window_text())
    return texts


def _load_once(mgr, slot_index, filepath, timeout):
    loads = _load_buttons(mgr)
    if slot_index >= len(loads):
        raise InjectError(f"RPCS3 hat nur {len(loads)} Slots (angefragt: {slot_index + 1}).")

    loads[slot_index].invoke()
    fd = _wait_file_dialog(mgr)
    if not fd:
        raise InjectError("Datei-Dialog erschien nicht.")

    edit = _find_desc(fd, "Edit", FILENAME_EDIT_ID)
    if not edit:
        raise InjectError("Dateiname-Feld nicht gefunden.")
    edit.set_edit_text(filepath)

    time.sleep(0.15)
    open_btn = _find_desc(fd, "Button", OPEN_BUTTON_ID)
    if open_btn:
        open_btn.invoke()
    else:
        from pywinauto.keyboard import send_keys
        try:
            fd.set_focus()
        except Exception:
            pass
        send_keys("{ENTER}")

    deadline = time.time() + timeout
    while time.time() < deadline:
        if not any(c.class_name() == FILE_DIALOG_CLASS for c in mgr.children()):
            return True
        time.sleep(0.2)
    return False


def inject_slot(slot_index, filepath, timeout=8.0):
    """Datei in RPCS3-Slot laden. Bei haengendem Dialog einmal sauber wiederholen."""
    mgr = open_manager()
    _dismiss_file_dialogs(mgr)
    if _load_once(mgr, slot_index, filepath, timeout):
        return True
    # Retry: RPCS3 haelt die Datei evtl. noch (gleiche Figur) -> Slot leeren, kurz warten
    _dismiss_file_dialogs(mgr)
    clear_slot(slot_index)
    time.sleep(0.4)
    mgr = open_manager()
    if _load_once(mgr, slot_index, filepath, timeout):
        return True
    _dismiss_file_dialogs(mgr)
    raise InjectError("Laden hat nicht abgeschlossen (Datei-Dialog offen geblieben).")


def clear_slot(slot_index):
    mgr = open_manager()
    clears = _clear_buttons(mgr)
    if slot_index < len(clears):
        clears[slot_index].invoke()
        time.sleep(0.2)
        return True
    return False


def inject_many(assignments, timeout=8.0):
    """assignments: Liste (slot_index, filepath). Gibt {slot: (ok, meldung)} zurueck."""
    open_manager()  # einmal sicherstellen, dass er offen ist
    results = {}
    for slot_index, filepath in assignments:
        try:
            inject_slot(slot_index, filepath, timeout=timeout)
            results[slot_index] = (True, "ok")
        except InjectError as e:
            results[slot_index] = (False, str(e))
    return results


def _confirm_dialogs(mw):
    """Eventuelle Rueckfragen bestaetigen (z. B. 'laufende Emulation beenden?')."""
    try:
        for c in mw.children():
            if "32770" in (c.class_name() or ""):
                continue  # Datei-Dialoge nicht anfassen
            for b in c.descendants(control_type="Button"):
                if (b.window_text() or "").strip("&") in CONFIRM_LABELS:
                    b.invoke()
                    return
    except Exception:
        pass


def _pid_alive(pid):
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return False
    try:
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
        return code.value == STILL_ACTIVE
    finally:
        ctypes.windll.kernel32.CloseHandle(h)


def close_rpcs3(timeout=15.0):
    """RPCS3 sauber beenden (Fenster schliessen) und warten, bis der Prozess weg ist.
    Noetig fuer den Spielwechsel: eine zweite rpcs3.exe-Instanz stuerzt ab."""
    mw = _main_window()
    if not mw:
        return True
    pid = mw.element_info.process_id
    try:
        mw.close()
    except Exception:
        pass
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(0.4)
        if not _pid_alive(pid):
            return True
        m = _main_window()
        if m:
            _confirm_dialogs(m)  # falls doch eine Rueckfrage kommt
    return not _pid_alive(pid)


def wait_for_main_window(timeout=30.0):
    """Nach einem Neustart warten, bis das RPCS3-Hauptfenster wieder da ist."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _main_window():
            return True
        time.sleep(0.8)
    return False
