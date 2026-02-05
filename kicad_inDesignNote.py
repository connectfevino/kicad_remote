"""
KiCad InDesignNote Plugin
Professional Design Notes, Kanban Task Manager & Team Link for KiCad.
Version 3.1.0 - Robustness & Multi-Select Update
"""

import pcbnew
import wx
import os
import json
import socket
import threading
import getpass
from datetime import datetime

# =============================================================================
# CONSTANTS
# =============================================================================
PLUGIN_NAME = "InDesignNote"
DIR_NAME = ".inDesignNotes"
FILE_TASKS = "tasks.json"
FILE_NOTES = "item_annotations.json"

PRIORITY_HIGH = "High"
PRIORITY_MED = "Medium"
PRIORITY_LOW = "Low"

DEFAULT_PORT = 5005

# =============================================================================
# DATA MANAGER
# =============================================================================
class DataManager:
    def __init__(self, project_dir):
        self.project_dir = project_dir
        self.data_dir = os.path.join(project_dir, DIR_NAME)
        self.tasks_path = os.path.join(self.data_dir, FILE_TASKS)
        self.notes_path = os.path.join(self.data_dir, FILE_NOTES)
        self.user = getpass.getuser()
        
        if not os.path.exists(self.data_dir):
            try: os.makedirs(self.data_dir)
            except: pass
            
    def load_tasks(self): return self._load_json(self.tasks_path)
    def save_tasks(self, tasks): self._save_json(self.tasks_path, tasks)
    def load_notes(self): return self._load_json(self.notes_path)
    def save_notes(self, notes): self._save_json(self.notes_path, notes)

    def _load_json(self, path):
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f: return json.load(f)
            except: pass
        return []

    def _save_json(self, path, data):
        try:
            with open(path, 'w', encoding='utf-8') as f: json.dump(data, f, indent=2)
        except: pass

# =============================================================================
# TEAM LINK
# =============================================================================
class TeamLinkManager:
    def __init__(self, on_msg_received):
        self.sock = None
        self.running = False
        self.is_server = False
        self.on_msg = on_msg_received
        self.conn = None
        
    def start_host(self, start_port=DEFAULT_PORT):
        if self.running: return False, "Already running."
        for port in range(start_port, start_port + 10):
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.sock.bind(('0.0.0.0', port))
                self.sock.listen(1)
                self.running = True
                self.is_server = True
                t = threading.Thread(target=self._accept_clients)
                t.daemon = True; t.start()
                return True, f"Hosting on Port {port}!"
            except OSError: self.sock.close(); continue
        return False, "All ports busy."

    def connect_to_host(self, ip, port=DEFAULT_PORT):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5); self.sock.connect((ip, port)); self.sock.settimeout(None)
            self.running = True; self.is_server = False
            t = threading.Thread(target=self._listen, args=(self.sock,))
            t.daemon = True; t.start()
            return True, f"Connected to {ip}:{port}"
        except Exception as e: return False, str(e)

    def send(self, data_dict):
        try:
            msg = json.dumps(data_dict) + "\n"; data = msg.encode('utf-8')
            if self.is_server: 
                if self.conn: self.conn.sendall(data)
            else: 
                if self.sock: self.sock.sendall(data)
        except: pass

    def close(self):
        self.running = False
        try: 
            if self.conn: self.conn.shutdown(socket.SHUT_RDWR); self.conn.close()
            if self.sock: self.sock.close()
        except: pass
        self.conn = None; self.sock = None

    def _accept_clients(self):
        while self.running:
            try:
                conn, addr = self.sock.accept(); self.conn = conn
                if self.on_msg: wx.CallAfter(self.on_msg, {"sys": f"Client connected from {addr}"})
                self._listen(conn)
            except: break

    def _listen(self, connection):
        buffer = ""
        while self.running:
            try:
                data = connection.recv(1024)
                if not data: break
                buffer += data.decode('utf-8')
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    try: 
                        if self.on_msg: wx.CallAfter(self.on_msg, json.loads(line))
                    except: pass
            except: break
        if self.running and self.on_msg: wx.CallAfter(self.on_msg, {"sys": "Connection closed"})

# =============================================================================
# UI CLASSES
# =============================================================================
class SimpleTaskPanel(wx.Panel):
    def __init__(self, parent, task, on_status, on_delete):
        super().__init__(parent); self.task = task; self.on_status = on_status; self.on_delete = on_delete
        self.SetBackgroundColour(wx.Colour(250, 250, 250))
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Info
        info_sizer = wx.BoxSizer(wx.VERTICAL)
        prio = task.get('priority', 'Medium'); title = task.get('title', 'No Title'); user = task.get('author', 'Unknown')
        
        lbl_h = wx.StaticText(self, label=f"[{prio}] {title}")
        f = lbl_h.GetFont(); f.SetWeight(wx.FONTWEIGHT_BOLD); lbl_h.SetFont(f); lbl_h.Wrap(350); info_sizer.Add(lbl_h, 0, wx.EXPAND|wx.BOTTOM, 2)
        
        desc = task.get('description', '')
        if desc: l_d = wx.StaticText(self, label=desc); l_d.Wrap(350); info_sizer.Add(l_d, 0, wx.EXPAND|wx.BOTTOM, 2)
        
        l_a = wx.StaticText(self, label=f"By: {user}"); l_a.SetForegroundColour(wx.Colour(120, 120, 120)); 
        f2 = l_a.GetFont(); f2.SetPointSize(8); l_a.SetFont(f2); info_sizer.Add(l_a, 0, wx.EXPAND)
        
        sizer.Add(info_sizer, 1, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        
        # Btns
        btns = wx.BoxSizer(wx.VERTICAL)
        lbl_s = "Undo" if task['completed'] else "Done"
        b_s = wx.Button(self, label=lbl_s, size=(50, 22)); b_s.Bind(wx.EVT_BUTTON, lambda e: self.on_status(self.task, not self.task['completed']))
        b_d = wx.Button(self, label="Del", size=(50, 22)); b_d.Bind(wx.EVT_BUTTON, lambda e: self.on_delete(self.task['id']))
        btns.Add(b_s, 0, wx.BOTTOM, 2); btns.Add(b_d, 0)
        
        sizer.Add(btns, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        self.SetSizer(sizer)

class AnnotationDialog(wx.Dialog):
    def __init__(self, parent, count):
        super().__init__(parent, title="Add Note", size=(400, 250))
        pnl = wx.Panel(self); sz = wx.BoxSizer(wx.VERTICAL)
        sz.Add(wx.StaticText(pnl, label=f"Add note for {count} items:"), 0, wx.ALL, 10)
        self.txt = wx.TextCtrl(pnl, style=wx.TE_MULTILINE); sz.Add(self.txt, 1, wx.EXPAND|wx.LEFT|wx.RIGHT, 10)
        btns = wx.StdDialogButtonSizer(); btns.AddButton(wx.Button(pnl, wx.ID_OK)); btns.AddButton(wx.Button(pnl, wx.ID_CANCEL)); btns.Realize()
        sz.Add(btns, 0, wx.ALIGN_RIGHT|wx.ALL, 10); pnl.SetSizer(sz)
    def GetDescription(self): return self.txt.GetValue().strip()

class MainFrame(wx.Frame):
    def __init__(self, parent, data_manager, project_name):
        style = wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP
        super().__init__(parent, title=f"InDesignNote - {project_name}", size=(850, 650), style=style)
        self.dm = data_manager; self.tasks = self.dm.load_tasks(); self.notes = self.dm.load_notes(); self.tl = TeamLinkManager(self._on_tl_message)
        self._init_ui(); self.Centre(); self.Bind(wx.EVT_CLOSE, self._on_close)
        
    def _init_ui(self):
        panel = wx.Panel(self); self.nb = wx.Notebook(panel)
        self.nb.AddPage(self._create_kanban_tab(self.nb), "Tasks")
        self.nb.AddPage(self._create_notes_tab(self.nb), "Design Notes")
        self.nb.AddPage(self._create_team_tab(self.nb), "Team Link")
        sizer = wx.BoxSizer(wx.VERTICAL); sizer.Add(self.nb, 1, wx.EXPAND); panel.SetSizer(sizer)
        self._refresh_kanban(); self._refresh_notes()

    def _on_close(self, event): self.tl.close(); event.Skip()

    # --- TEAM LINK ---
    def _create_team_tab(self, parent):
        panel = wx.Panel(parent); sizer = wx.BoxSizer(wx.VERTICAL)
        # Bar
        bar = wx.BoxSizer(wx.HORIZONTAL)
        self.txt_ip = wx.TextCtrl(panel, value="127.0.0.1", size=(100,-1))
        self.txt_port = wx.TextCtrl(panel, value=str(DEFAULT_PORT), size=(50,-1))
        bar.Add(wx.StaticText(panel, label="IP:"), 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 2); bar.Add(self.txt_ip, 0, wx.RIGHT, 5)
        bar.Add(wx.StaticText(panel, label="Port:"), 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 2); bar.Add(self.txt_port, 0, wx.RIGHT, 5)
        
        self.btn_host = wx.Button(panel, label="Host"); self.btn_host.Bind(wx.EVT_BUTTON, self._tl_host); bar.Add(self.btn_host, 0, wx.RIGHT, 5)
        self.btn_join = wx.Button(panel, label="Join"); self.btn_join.Bind(wx.EVT_BUTTON, self._tl_join); bar.Add(self.btn_join, 0, wx.RIGHT, 5)
        self.btn_end = wx.Button(panel, label="End Session"); self.btn_end.Bind(wx.EVT_BUTTON, self._tl_stop); self.btn_end.Disable(); bar.Add(self.btn_end, 0)
        
        sizer.Add(bar, 0, wx.EXPAND|wx.ALL, 10)
        self.log = wx.TextCtrl(panel, style=wx.TE_MULTILINE|wx.TE_READONLY); sizer.Add(self.log, 1, wx.EXPAND|wx.LEFT|wx.RIGHT, 10)
        
        inp = wx.BoxSizer(wx.HORIZONTAL)
        self.msg = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER); self.msg.Bind(wx.EVT_TEXT_ENTER, self._tl_send); inp.Add(self.msg, 1, wx.RIGHT, 5)
        bs = wx.Button(panel, label="Send"); bs.Bind(wx.EVT_BUTTON, self._tl_send); inp.Add(bs, 0)
        sizer.Add(inp, 0, wx.EXPAND|wx.ALL, 10)
        panel.SetSizer(sizer); return panel

    def _tl_host(self, e):
        try: p=int(self.txt_port.GetValue())
        except: p=DEFAULT_PORT
        ok, m = self.tl.start_host(p)
        self._log(f"[Sys] {m}")
        if ok: self._tl_ui_state(True)

    def _tl_join(self, e):
        try: p=int(self.txt_port.GetValue())
        except: p=DEFAULT_PORT
        ok, m = self.tl.connect_to_host(self.txt_ip.GetValue(), p)
        self._log(f"[Sys] {m}")
        if ok: self._tl_ui_state(True)

    def _tl_stop(self, e):
        self.tl.close()
        self._log("[Sys] Session Ended.")
        self._tl_ui_state(False)

    def _tl_ui_state(self, active):
        self.btn_host.Enable(not active); self.btn_join.Enable(not active)
        self.btn_end.Enable(active); self.txt_ip.Enable(not active); self.txt_port.Enable(not active)

    def _tl_send(self, e):
        m = self.msg.GetValue().strip()
        if m: self.tl.send({"type":"chat", "user":self.dm.user, "msg":m}); self._log(f"Me: {m}"); self.msg.Clear()

    def _on_tl_message(self, d):
        if "sys" in d: self._log(f"[Sys] {d['sys']}")
        elif d.get("type") == "chat": self._log(f"{d['user']}: {d['msg']}")
        elif d.get("type") == "focus":
            self._log(f"[Sys] Remote focus request...")
            # Unpack full items list if available
            self._perform_focus(d.get("items", [])) 

    def _log(self, t): self.log.AppendText(t+"\n")

    # --- KANBAN ---
    def _create_kanban_tab(self, parent):
        panel = wx.Panel(parent); sizer = wx.BoxSizer(wx.VERTICAL)
        # Controls
        controls = wx.BoxSizer(wx.HORIZONTAL)
        controls.Add(wx.StaticText(panel, label="Filter:"), 0, wx.ALIGN_CENTER_VERTICAL, 5)
        self.cb_filt = wx.ComboBox(panel, choices=["All", PRIORITY_HIGH, PRIORITY_MED, PRIORITY_LOW], value="All", style=wx.CB_READONLY)
        self.cb_filt.Bind(wx.EVT_COMBOBOX, self._refresh_kanban); controls.Add(self.cb_filt, 0, wx.RIGHT, 10)
        self.cb_p = wx.ComboBox(panel, choices=[PRIORITY_HIGH, PRIORITY_MED, PRIORITY_LOW], value=PRIORITY_MED, style=wx.CB_READONLY)
        controls.Add(self.cb_p, 0, wx.RIGHT, 5)
        self.t_ti = wx.TextCtrl(panel); self.t_ti.SetHint("Title"); controls.Add(self.t_ti, 1, wx.RIGHT, 5)
        self.t_de = wx.TextCtrl(panel); self.t_de.SetHint("Description"); controls.Add(self.t_de, 1, wx.RIGHT, 5)
        b_add = wx.Button(panel, label="Add"); b_add.Bind(wx.EVT_BUTTON, self._add_task); controls.Add(b_add, 0)
        sizer.Add(controls, 0, wx.EXPAND|wx.ALL, 5)
        # Splitter
        sp = wx.SplitterWindow(panel, style=wx.SP_3D)
        p1 = wx.Panel(sp); sz1 = wx.BoxSizer(wx.VERTICAL); sz1.Add(wx.StaticText(p1, label="--- PENDING ---"),0,wx.ALL|wx.CENTER,5)
        self.sc1 = wx.ScrolledWindow(p1); self.sc1.SetScrollRate(5,5); self.vb1 = wx.BoxSizer(wx.VERTICAL); self.sc1.SetSizer(self.vb1)
        sz1.Add(self.sc1,1,wx.EXPAND); p1.SetSizer(sz1)
        p2 = wx.Panel(sp); sz2 = wx.BoxSizer(wx.VERTICAL); sz2.Add(wx.StaticText(p2, label="--- DONE ---"),0,wx.ALL|wx.CENTER,5)
        self.sc2 = wx.ScrolledWindow(p2); self.sc2.SetScrollRate(5,5); self.vb2 = wx.BoxSizer(wx.VERTICAL); self.sc2.SetSizer(self.vb2)
        sz2.Add(self.sc2,1,wx.EXPAND); p2.SetSizer(sz2)
        sp.SplitHorizontally(p1,p2); sp.SetSashGravity(0.5); sizer.Add(sp,1,wx.EXPAND|wx.ALL,5); panel.SetSizer(sizer)
        return panel

    def _refresh_kanban(self, e=None):
        self.vb1.Clear(True); self.vb2.Clear(True)
        f = self.cb_filt.GetValue()
        for t in self.tasks:
            if f != "All" and t.get('priority') != f: continue
            parent, sizer = (self.sc2, self.vb2) if t['completed'] else (self.sc1, self.vb1)
            sizer.Add(SimpleTaskPanel(parent, t, self._set_t_stat, self._del_t), 0, wx.EXPAND|wx.ALL, 2)
            sizer.Add(wx.StaticLine(parent), 0, wx.EXPAND)
        self.sc1.Layout(); self.sc2.Layout()

    def _add_task(self,e):
        ti = self.t_ti.GetValue().strip()
        if ti:
            t={'id':int(datetime.now().timestamp()*1000),'title':ti,'description':self.t_de.GetValue(),'priority':self.cb_p.GetValue(),'author':self.dm.user,'completed':False}
            self.tasks.append(t); self.dm.save_tasks(self.tasks); self.t_ti.Clear(); self.t_de.Clear(); self._refresh_kanban()
    def _set_t_stat(self,t,s): t['completed']=s; self.dm.save_tasks(self.tasks); self._refresh_kanban()
    def _del_t(self,tid): self.tasks=[x for x in self.tasks if x['id']!=tid]; self.dm.save_tasks(self.tasks); self._refresh_kanban()

    # --- NOTES ---
    def _create_notes_tab(self, parent):
        panel = wx.Panel(parent); sizer = wx.BoxSizer(wx.VERTICAL)
        # Toolbar
        tb = wx.BoxSizer(wx.HORIZONTAL)
        self.cb_ntype = wx.ComboBox(panel, choices=["All", "Footprint", "Track", "Graphic", "Zone"], value="All", style=wx.CB_READONLY)
        self.cb_ntype.Bind(wx.EVT_COMBOBOX, self._refresh_notes); tb.Add(self.cb_ntype, 0, wx.RIGHT, 5)
        
        self.txt_nsearch = wx.TextCtrl(panel); self.txt_nsearch.Bind(wx.EVT_TEXT, self._refresh_notes); tb.Add(self.txt_nsearch, 1, wx.RIGHT, 5)
        
        b_add = wx.Button(panel, label="Add to Sel."); b_add.Bind(wx.EVT_BUTTON, self._add_n_sel); tb.Add(b_add, 0, wx.RIGHT, 5)
        b_del = wx.Button(panel, label="Del Selected"); b_del.Bind(wx.EVT_BUTTON, self._del_note); tb.Add(b_del, 0)
        sizer.Add(tb, 0, wx.EXPAND|wx.ALL, 5)
        
        # List (Multi-Select Enabled by default without LC_SINGLE_SEL)
        self.lst = wx.ListCtrl(panel, style=wx.LC_REPORT|wx.LC_HRULES)
        self.lst.InsertColumn(0, "Date", width=110); self.lst.InsertColumn(1, "Type", width=80)
        self.lst.InsertColumn(2, "Items", width=150); self.lst.InsertColumn(3, "Desc", width=350)
        self.lst.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_note_click)
        sizer.Add(self.lst, 1, wx.EXPAND|wx.ALL, 5); panel.SetSizer(sizer)
        return panel

    def _refresh_notes(self, e=None):
        self.lst.DeleteAllItems(); f = self.cb_ntype.GetValue(); s = self.txt_nsearch.GetValue().lower()
        for i, n in enumerate(self.notes):
            items = n.get('items',[]); itype = items[0]['type'] if items else 'Other'
            if f!="All" and itype!=f: continue
            if s and s not in n['description'].lower(): continue
            idx = self.lst.InsertItem(i, n['timestamp'][:16]); self.lst.SetItem(idx, 1, itype)
            self.lst.SetItem(idx, 2, ", ".join([x.get('description','') for x in items])); self.lst.SetItem(idx, 3, n['description'])
            self.lst.SetItemData(idx, i)

    def _del_note(self, event):
        # Handle MULTI selection cleanup
        idx = self.lst.GetFirstSelected()
        indices_to_del = []
        while idx != -1:
            indices_to_del.append(self.lst.GetItemData(idx))
            idx = self.lst.GetNextSelected(idx)
        
        if not indices_to_del: return
        
        # Sort reverse to delete safely
        indices_to_del.sort(reverse=True)
        for i in indices_to_del:
            if i < len(self.notes): del self.notes[i]
            
        self.dm.save_notes(self.notes); self._refresh_notes()

    def _add_n_sel(self, e):
        try:
            board = pcbnew.GetBoard(); sel = []
            
            def collect(item, itype):
                if item.IsSelected():
                    desc = item.GetReference() if itype=="Footprint" else itype
                    try: uid = item.GetKIID().AsString()
                    except: 
                         try: uid = item.GetUuid().AsString()
                         except: uid = ""
                    # Enhanced Data Capture: Position & Layer
                    pos = x = y = 0
                    try: pos = item.GetPosition(); x = pos.x; y = pos.y
                    except: 
                        try: c = item.GetCenter(); x = c.x; y = c.y
                        except: pass
                    
                    sel.append({'type':itype, 'description':desc, 'uuid':uid, 'x':x, 'y':y, 'layer':item.GetLayer()})

            for x in board.Footprints(): collect(x, "Footprint")
            for x in board.Tracks(): collect(x, "Track")
            for x in board.Drawings(): collect(x, "Graphic")
            for x in board.Zones(): collect(x, "Zone")
            
            if not sel: wx.MessageBox("Select items first."); return
            dlg = AnnotationDialog(self, len(sel))
            if dlg.ShowModal() == wx.ID_OK:
                n={'timestamp':datetime.now().isoformat(), 'items':sel, 'description':dlg.GetDescription()}
                self.notes.append(n); self.dm.save_notes(self.notes); self._refresh_notes()
            dlg.Destroy()
        except Exception as ex: wx.MessageBox(str(ex))

    def _on_note_click(self, event):
        # Consolidate ALL selected notes items (Multi-Select Focus)
        all_items = []
        idx = self.lst.GetFirstSelected()
        while idx != -1:
            real_idx = self.lst.GetItemData(idx)
            all_items.extend(self.notes[real_idx].get('items', []))
            idx = self.lst.GetNextSelected(idx)
            
        if self.tl.running: self.tl.send({"type":"focus", "items": all_items})
        self._perform_focus(all_items)

    def _perform_focus(self, item_dicts):
        try:
            board = pcbnew.GetBoard(); found = False; bbox = None; target_layer = None
            for x in board.Footprints(): x.ClearSelected()
            for x in board.Tracks(): x.ClearSelected()
            for x in board.Drawings(): x.ClearSelected()
            for x in board.Zones(): x.ClearSelected()

            uuids = [x.get('uuid') for x in item_dicts]
            
            def check(obj):
                nonlocal found, bbox, target_layer
                match = False
                # Try UUID
                try: 
                    if obj.GetKIID().AsString() in uuids: match = True
                except: 
                    try: 
                         if obj.GetUuid().AsString() in uuids: match = True
                    except: pass
                
                if match:
                    obj.SetSelected(); found = True
                    if not bbox: bbox = obj.GetBoundingBox()
                    else: bbox.Merge(obj.GetBoundingBox())
                    if target_layer is None: target_layer = obj.GetLayer()

            for x in board.Footprints(): check(x)
            for x in board.Tracks(): check(x)
            for x in board.Drawings(): check(x)
            for x in board.Zones(): check(x)
            
            # Robust Fallback: If no object found by UUID, look for coordinates
            if not found and item_dicts:
                # Use first item coordinate as backup
                i = item_dicts[0]
                if i.get('x') and i.get('y'):
                     # Dummy Zoom to coordinate
                     pcbnew.WindowZoom(i['x'], i['y'], 10000000, 10000000) # Arbitrary small window
                     # Also try to switch layer if saved
                     if i.get('layer') is not None:
                         pcbnew.GetBoard().GetDesignSettings().SetVisibleLayers(i['layer'])
                     return 

            if found:
                pcbnew.Refresh()
                # Auto Layer Switch (Feature!)
                if target_layer is not None:
                     # This command switches the active layer in pcbnew
                     # Note: This API might vary, but standard way is usually via PCB_EDITOR connection
                     # For basic scripting, we can only highlight. 
                     pass 

                if bbox:
                    try: 
                        m = int(max(bbox.GetWidth(), bbox.GetHeight())*0.2); bbox.Inflate(m)
                        pcbnew.WindowZoom(bbox.GetX(), bbox.GetY(), bbox.GetWidth(), bbox.GetHeight())
                    except: pass
        except: pass

# =============================================================================
# ENTRY
# =============================================================================
class InDesignNotePlugin(pcbnew.ActionPlugin):
    def defaults(self): self.name = PLUGIN_NAME; self.category = "Utilities"; self.description = "Team Collab Note Tool"; self.show_toolbar_button = True
    def Run(self):
        try:
            board = pcbnew.GetBoard()
            if not board: 
                wx.MessageBox("Could not access board."); return
            
            fname = board.GetFileName()
            # Handle new/unsaved boards
            if not fname:
                # Try to fallback to CWD or Temp
                p = os.getcwd()
                n = "Unsaved_Board"
            else:
                p = os.path.dirname(fname)
                n = os.path.splitext(os.path.basename(fname))[0]
                
            MainFrame(None, DataManager(p), n).Show()
        except Exception as e: 
            wx.MessageBox(f"Error starting plugin: {e}")

InDesignNotePlugin().register()
