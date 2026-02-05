"""
KiCad InDesignNote Plugin
Simpler, safer version with text-based UI to prevent crashes.
"""

import pcbnew
import wx
import os
import json
import traceback
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

# =============================================================================
# DATA MANAGER
# =============================================================================
class DataManager:
    """Handles data persistence."""
    
    def __init__(self, project_dir):
        self.data_dir = os.path.join(project_dir, DIR_NAME)
        self.tasks_path = os.path.join(self.data_dir, FILE_TASKS)
        self.notes_path = os.path.join(self.data_dir, FILE_NOTES)
        
        if not os.path.exists(self.data_dir):
            try: os.makedirs(self.data_dir)
            except: pass
            
    def load_tasks(self):
        return self._load_json(self.tasks_path)

    def save_tasks(self, tasks):
        self._save_json(self.tasks_path, tasks)

    def load_notes(self):
        return self._load_json(self.notes_path)

    def save_notes(self, notes):
        self._save_json(self.notes_path, notes)

    def _load_json(self, path):
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except: pass
        return []

    def _save_json(self, path, data):
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except: pass

# =============================================================================
# UI COMPONENTS
# =============================================================================
class SimpleTaskPanel(wx.Panel):
    """A simplistic text-based task panel."""
    def __init__(self, parent, task, on_status, on_delete):
        super().__init__(parent)
        self.task = task
        self.on_status = on_status
        self.on_delete = on_delete
        
        self.SetBackgroundColour(wx.Colour(250, 250, 250))
        
        # Main Layout: Horizontal [Info ....... Buttons]
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Info Block
        info_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Line 1: [Priority] Title
        prio = task.get('priority', 'Medium')
        title = task.get('title', 'No Title')
        header_txt = f"[{prio.upper()}] {title}"
        lbl_header = wx.StaticText(self, label=header_txt)
        
        # Make title bold
        font = lbl_header.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        lbl_header.SetFont(font)
        lbl_header.Wrap(350)
        info_sizer.Add(lbl_header, 0, wx.EXPAND|wx.BOTTOM, 2)

        # Line 2: Description (Normal Text)
        desc = task.get('description', '')
        if desc:
            lbl_desc = wx.StaticText(self, label=desc)
            lbl_desc.Wrap(350)
            info_sizer.Add(lbl_desc, 0, wx.EXPAND|wx.BOTTOM, 2)
        
        # Line 2: Remark (if any)
        if task.get('remark'):
            lbl_rem = wx.StaticText(self, label=f"Ref: {task['remark']}")
            info_sizer.Add(lbl_rem, 0, wx.EXPAND)
            
        sizer.Add(info_sizer, 1, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        
        # Buttons Block
        btn_sizer = wx.BoxSizer(wx.VERTICAL)
        
        if task['completed']:
            btn_state = wx.Button(self, label="Undo", size=(60, 22))
            btn_state.Bind(wx.EVT_BUTTON, lambda e: self.on_status(self.task, False))
        else:
            btn_state = wx.Button(self, label="Done", size=(60, 22))
            btn_state.Bind(wx.EVT_BUTTON, lambda e: self.on_status(self.task, True))
            
        btn_del = wx.Button(self, label="Del", size=(60, 22))
        btn_del.Bind(wx.EVT_BUTTON, lambda e: self.on_delete(self.task['id']))
        
        btn_sizer.Add(btn_state, 0, wx.BOTTOM, 2)
        btn_sizer.Add(btn_del, 0)
        
        sizer.Add(btn_sizer, 0, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 5)
        
        self.SetSizer(sizer)
        
        # Separator line widget stored in parent
        self.line = wx.StaticLine(self)

    def GetLine(self):
        return self.line


# =============================================================================
# MAIN WINDOW
# =============================================================================
class MainFrame(wx.Frame):
    def __init__(self, parent, data_manager, project_name):
        style = wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP # Keep on top for easier use
        super().__init__(parent, title=f"InDesignNote - {project_name}", size=(800, 600), style=style)
        
        self.dm = data_manager
        self.tasks = self.dm.load_tasks()
        self.notes = self.dm.load_notes()
        
        self._init_ui()
        self.Centre()
        
    def _init_ui(self):
        panel = wx.Panel(self)
        notebook = wx.Notebook(panel)
        
        # Tabs
        self.tab_kanban = self._create_kanban_tab(notebook)
        self.tab_notes = self._create_notes_tab(notebook)
        
        notebook.AddPage(self.tab_kanban, "Tasks")
        notebook.AddPage(self.tab_notes, "Design Notes")
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(notebook, 1, wx.EXPAND)
        panel.SetSizer(sizer)
        
        # Initial Refresh
        self._refresh_kanban()
        self._refresh_notes()

    # --- KANBAN ---
    def _create_kanban_tab(self, parent):
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # 1. Controls
        top_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Filter
        top_sizer.Add(wx.StaticText(panel, label="Filter Level:"), 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 5)
        self.cb_filter_level = wx.ComboBox(panel, choices=["All", PRIORITY_HIGH, PRIORITY_MED, PRIORITY_LOW], 
                                           value="All", style=wx.CB_READONLY)
        self.cb_filter_level.Bind(wx.EVT_COMBOBOX, self._refresh_kanban)
        top_sizer.Add(self.cb_filter_level, 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 15)
        
        # Add Task Inputs
        self.cb_prio = wx.ComboBox(panel, choices=[PRIORITY_HIGH, PRIORITY_MED, PRIORITY_LOW], 
                                   value=PRIORITY_MED, style=wx.CB_READONLY)
        top_sizer.Add(self.cb_prio, 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 5)
        
        # Title Input
        self.txt_title = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.txt_title.SetHint("Title")
        self.txt_title.Bind(wx.EVT_TEXT_ENTER, self._add_task)
        top_sizer.Add(self.txt_title, 1, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 5)

        # Description Input
        self.txt_desc = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.txt_desc.SetHint("Description")
        self.txt_desc.Bind(wx.EVT_TEXT_ENTER, self._add_task)
        top_sizer.Add(self.txt_desc, 1, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 5)
        
        btn_add = wx.Button(panel, label="Add Task")
        btn_add.Bind(wx.EVT_BUTTON, self._add_task)
        top_sizer.Add(btn_add, 0, wx.ALIGN_CENTER_VERTICAL)
        
        sizer.Add(top_sizer, 0, wx.EXPAND|wx.ALL, 8)
        
        # 2. Lists (Using Splitter)
        splitter = wx.SplitterWindow(panel, style=wx.SP_3D)
        
        # Todo
        pnl_todo = wx.Panel(splitter)
        sz_todo = wx.BoxSizer(wx.VERTICAL)
        sz_todo.Add(wx.StaticText(pnl_todo, label="--- PENDING ---"), 0, wx.ALL|wx.ALIGN_CENTER, 5)
        
        self.scroll_todo = wx.ScrolledWindow(pnl_todo)
        self.scroll_todo.SetScrollRate(5, 5)
        self.sizer_todo_items = wx.BoxSizer(wx.VERTICAL)
        self.scroll_todo.SetSizer(self.sizer_todo_items)
        
        sz_todo.Add(self.scroll_todo, 1, wx.EXPAND)
        pnl_todo.SetSizer(sz_todo)
        
        # Done
        pnl_done = wx.Panel(splitter)
        sz_done = wx.BoxSizer(wx.VERTICAL)
        sz_done.Add(wx.StaticText(pnl_done, label="--- DONE ---"), 0, wx.ALL|wx.ALIGN_CENTER, 5)
        
        self.scroll_done = wx.ScrolledWindow(pnl_done)
        self.scroll_done.SetScrollRate(5, 5)
        self.sizer_done_items = wx.BoxSizer(wx.VERTICAL)
        self.scroll_done.SetSizer(self.sizer_done_items)
        
        sz_done.Add(self.scroll_done, 1, wx.EXPAND)
        pnl_done.SetSizer(sz_done)
        
        splitter.SplitHorizontally(pnl_todo, pnl_done)
        splitter.SetSashGravity(0.6)
        
        sizer.Add(splitter, 1, wx.EXPAND|wx.ALL, 5)
        
        panel.SetSizer(sizer)
        return panel

    def _refresh_kanban(self, event=None):
        self.sizer_todo_items.Clear(True)
        self.sizer_done_items.Clear(True)
        
        filter_lvl = self.cb_filter_level.GetValue()
        
        for task in self.tasks:
            # Filter
            if filter_lvl != "All" and task.get('priority', PRIORITY_MED) != filter_lvl:
                continue
                
            if task['completed']:
                item = SimpleTaskPanel(self.scroll_done, task, self._set_task_status, self._del_task)
                self.sizer_done_items.Add(item, 0, wx.EXPAND|wx.ALL, 2)
                self.sizer_done_items.Add(wx.StaticLine(self.scroll_done), 0, wx.EXPAND)
            else:
                item = SimpleTaskPanel(self.scroll_todo, task, self._set_task_status, self._del_task)
                self.sizer_todo_items.Add(item, 0, wx.EXPAND|wx.ALL, 2)
                self.sizer_todo_items.Add(wx.StaticLine(self.scroll_todo), 0, wx.EXPAND)
                
        self.scroll_todo.Layout()
        self.scroll_todo.FitInside()
        self.scroll_done.Layout()
        self.scroll_done.FitInside()

    def _add_task(self, event):
        title = self.txt_title.GetValue().strip()
        if not title: return
        
        t = {
            'id': int(datetime.now().timestamp() * 1000),
            'title': title,
            'description': self.txt_desc.GetValue().strip(),
            'priority': self.cb_prio.GetValue(),
            'remark': "",
            'completed': False
        }
        self.tasks.append(t)
        self.dm.save_tasks(self.tasks)
        self.txt_title.SetValue("")
        self.txt_desc.SetValue("")
        self._refresh_kanban()

    def _set_task_status(self, task, done):
        task['completed'] = done
        self.dm.save_tasks(self.tasks)
        self._refresh_kanban()

    def _del_task(self, tid):
        self.tasks = [t for t in self.tasks if t['id'] != tid]
        self.dm.save_tasks(self.tasks)
        self._refresh_kanban()

    # --- NOTES ---
    def _create_notes_tab(self, parent):
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Toolbar
        tb = wx.BoxSizer(wx.HORIZONTAL)
        
        self.cb_ntype = wx.ComboBox(panel, choices=["All Types", "Footprint", "Graphic", "Track", "Zone"], 
                                    value="All Types", style=wx.CB_READONLY)
        self.cb_ntype.Bind(wx.EVT_COMBOBOX, self._refresh_notes)
        tb.Add(self.cb_ntype, 0, wx.RIGHT, 5)
        
        self.txt_nsearch = wx.TextCtrl(panel)
        self.txt_nsearch.SetHint("Search...")
        self.txt_nsearch.Bind(wx.EVT_TEXT, self._refresh_notes)
        tb.Add(self.txt_nsearch, 1, wx.RIGHT, 5)
        
        btn_del_note = wx.Button(panel, label="Delete Selected")
        btn_del_note.Bind(wx.EVT_BUTTON, self._del_note)
        tb.Add(btn_del_note, 0)
        
        sizer.Add(tb, 0, wx.EXPAND|wx.ALL, 8)
        
        # List
        self.lst = wx.ListCtrl(panel, style=wx.LC_REPORT|wx.LC_SINGLE_SEL|wx.LC_HRULES)
        self.lst.InsertColumn(0, "Date", width=120)
        self.lst.InsertColumn(1, "Type", width=80)
        self.lst.InsertColumn(2, "Items", width=150)
        self.lst.InsertColumn(3, "Description", width=350)
        self.lst.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_note_click)
        
        sizer.Add(self.lst, 1, wx.EXPAND|wx.ALL, 5)
        
        panel.SetSizer(sizer)
        return panel

    def _refresh_notes(self, event=None):
        self.lst.DeleteAllItems()
        target_type = self.cb_ntype.GetValue()
        search = self.txt_nsearch.GetValue().lower()
        
        for i, note in enumerate(self.notes):
            items = note.get('items', [])
            itype = items[0]['type'] if items else 'Other'
            idessc = ", ".join([x.get('description','') for x in items])
            
            # Filter
            if target_type != "All Types" and itype != target_type: continue
            if search and (search not in note['description'].lower() and search not in idessc.lower()): continue
            
            idx = self.lst.InsertItem(i, note.get('timestamp', '')[:16])
            self.lst.SetItem(idx, 1, itype)
            self.lst.SetItem(idx, 2, idessc)
            self.lst.SetItem(idx, 3, note.get('description', ''))
            self.lst.SetItemData(idx, i)

    def _del_note(self, event):
        idx = self.lst.GetFirstSelected()
        if idx == -1: return
        
        real_idx = self.lst.GetItemData(idx)
        del self.notes[real_idx]
        self.dm.save_notes(self.notes)
        self._refresh_notes()

    def _on_note_click(self, event):
        idx = event.GetIndex()
        real_idx = self.lst.GetItemData(idx)
        note = self.notes[real_idx]
        
        # Cross Probe
        board = pcbnew.GetBoard()
        if not board: return
        
        try:
            # Clear all
            for x in board.Footprints(): x.ClearSelected()
            for x in board.Tracks(): x.ClearSelected()
            for x in board.Drawings(): x.ClearSelected()
            for x in board.Zones(): x.ClearSelected()
            
            # Select
            uuids = [x.get('uuid') for x in note.get('items', [])]
            # Fallback data for items without/changed UUIDs
            refs = [x.get('description', '').split(' ')[0] for x in note.get('items', []) if x.get('type') == 'Footprint']
            
            found = False
            bbox = None
            
            def check(item):
                nonlocal found, bbox
                match = False
                
                # Check 1: UUID
                try: 
                    uid = item.GetKIID().AsString() 
                    if uid in uuids: match = True
                except: 
                    try: 
                        if item.GetUuid().AsString() in uuids: match = True
                    except: pass
                
                # Check 2: Reference Fallback (for Footprints)
                if not match and isinstance(item, pcbnew.FOOTPRINT):
                    if item.GetReference() in refs: match = True
                
                if match:
                    item.SetSelected()
                    found = True
                    if not bbox: bbox = item.GetBoundingBox()
                    else: bbox.Merge(item.GetBoundingBox())

            # Specific Iterators for clarity
            for x in board.Footprints(): check(x)
            for x in board.Tracks(): check(x)
            for x in board.Drawings(): check(x)
            for x in board.Zones(): check(x)
            
            if found:
                pcbnew.Refresh()
                # Safe Zoom
                try:
                    margin = int(max(bbox.GetWidth(), bbox.GetHeight()) * 0.2)
                    bbox.Inflate(margin)
                    pcbnew.WindowZoom(bbox.GetX(), bbox.GetY(), bbox.GetWidth(), bbox.GetHeight())
                except: pass
        except: pass


class AnnotationDialog(wx.Dialog):
    def __init__(self, parent, count):
        super().__init__(parent, title="Add Note", size=(400, 250))
        self.description = ""
        
        pnl = wx.Panel(self)
        sz = wx.BoxSizer(wx.VERTICAL)
        
        sz.Add(wx.StaticText(pnl, label=f"Add note for {count} selected items:"), 0, wx.ALL, 10)
        self.txt = wx.TextCtrl(pnl, style=wx.TE_MULTILINE)
        sz.Add(self.txt, 1, wx.EXPAND|wx.LEFT|wx.RIGHT, 10)
        
        btns = wx.BoxSizer(wx.HORIZONTAL)
        b_ok = wx.Button(pnl, wx.ID_OK, label="Save")
        b_cn = wx.Button(pnl, wx.ID_CANCEL, label="Cancel")
        btns.Add(b_ok, 0, wx.RIGHT, 5)
        btns.Add(b_cn, 0)
        
        sz.Add(btns, 0, wx.ALIGN_RIGHT|wx.ALL, 10)
        pnl.SetSizer(sz)

    def GetDescription(self):
        return self.txt.GetValue().strip()

# =============================================================================
# PLUGIN ENTRY
# =============================================================================
class InDesignNotePlugin(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = PLUGIN_NAME
        self.category = "Utilities"
        self.description = "Simple Task and Note Manager"
        self.show_toolbar_button = True

    def Run(self):
        try:
            board = pcbnew.GetBoard()
            if not board: return
            
            fname = board.GetFileName()
            if not fname: return
            
            project_dir = os.path.dirname(fname)
            project_name = os.path.splitext(os.path.basename(fname))[0]
            
            dm = DataManager(project_dir)
            
            # Check selection
            sel_count = 0
            sel_items = []
            
            def collect(item, itype):
                try:
                    if item.IsSelected():
                        desc = "Item"
                        if itype == "Footprint": desc = f"{item.GetReference()}"
                        elif itype == "Graphic": 
                            try: desc = f"Shape on {board.GetLayerName(item.GetLayer())}"
                            except: pass
                        
                        try: uid = item.GetKIID().AsString() 
                        except: 
                            try: uid = item.GetUuid().AsString() 
                            except: uid = ""
                        
                        sel_items.append({
                            'type': itype,
                            'description': desc,
                            'uuid': uid
                        })
                except: pass

            try:
                for x in board.Footprints(): collect(x, "Footprint")
                for x in board.Tracks(): collect(x, "Track")
                for x in board.Drawings(): collect(x, "Graphic")
                for x in board.Zones(): collect(x, "Zone")
            except: pass
            
            if sel_items:
                # Dialog
                dlg = AnnotationDialog(None, len(sel_items))
                if dlg.ShowModal() == wx.ID_OK:
                    desc = dlg.GetDescription()
                    if desc:
                        note = {
                            'timestamp': datetime.now().isoformat(),
                            'items': sel_items,
                            'description': desc
                        }
                        notes = dm.load_notes()
                        notes.append(note)
                        dm.save_notes(notes)
                        
                        # Show main after add
                        MainFrame(None, dm, project_name).Show()
                dlg.Destroy()
            else:
                MainFrame(None, dm, project_name).Show()
                
        except Exception as e:
            wx.MessageBox(f"Error: {e}")

InDesignNotePlugin().register()
