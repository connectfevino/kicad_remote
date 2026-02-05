"""
KiCad InDesignNote Plugin - Simple Design Notes and Task Management
A minimal plugin for adding design notes and tracking tasks in KiCad PCB projects
"""

import pcbnew
import wx
import os
import json
from datetime import datetime


class InDesignNotePlugin(pcbnew.ActionPlugin):
    """
    Simple KiCad plugin for design notes and task management.
    """
    
    def defaults(self):
        """Set plugin metadata."""
        self.name = "InDesignNote"
        self.category = "Utilities"
        self.description = "Simple design notes and task tracker for your PCB project"
        self.show_toolbar_button = True
        self.icon_file_name = ""  # Optional: add icon path here
    
    def Run(self):
        """Run the plugin - show notes window."""
        # Get the current board
        board = pcbnew.GetBoard()
        
        if not board:
            wx.MessageBox(
                "Please open a PCB layout first.",
                "InDesignNote",
                wx.OK | wx.ICON_WARNING
            )
            return
        
        # Get project directory
        board_file = board.GetFileName()
        if not board_file:
            wx.MessageBox(
                "Please save your PCB file first.",
                "InDesignNote",
                wx.OK | wx.ICON_WARNING
            )
            return
        
        project_dir = os.path.dirname(board_file)
        project_name = os.path.splitext(os.path.basename(board_file))[0]
        
        # Check if any item is selected on the board
        selected_items = self._get_selected_items(board)
        
        # Create and show the appropriate window
        if selected_items:
            # Show item annotation dialog
            frame = ItemAnnotationDialog(None, project_dir, project_name, selected_items)
        else:
            # Show main notes/tasks window
            frame = NotesFrame(None, project_dir, project_name)
        
        frame.Show()
    
    def _get_selected_items(self, board):
        """Get list of selected items on the board."""
        selected = []
        
        # Check footprints
        for footprint in board.GetFootprints():
            if footprint.IsSelected():
                ref = footprint.GetReference()
                value = footprint.GetValue()
                selected.append({
                    'type': 'Footprint',
                    'reference': ref,
                    'value': value,
                    'description': f"{ref} ({value})"
                })
        
        # Check tracks
        for track in board.GetTracks():
            if track.IsSelected():
                net_name = track.GetNetname()
                selected.append({
                    'type': 'Track',
                    'reference': net_name,
                    'value': '',
                    'description': f"Track: {net_name}"
                })
        
        return selected


class ItemAnnotationDialog(wx.Dialog):
    """Dialog for annotating selected board items."""
    
    def __init__(self, parent, project_dir, project_name, selected_items):
        super().__init__(
            parent,
            title="Add Design Note for Selected Item",
            size=(500, 300)
        )
        
        self.project_dir = project_dir
        self.project_name = project_name
        self.selected_items = selected_items
        self.notes_dir = os.path.join(project_dir, ".inDesignNotes")
        
        # Create notes directory if it doesn't exist
        os.makedirs(self.notes_dir, exist_ok=True)
        
        self._init_ui()
        self.Centre()
    
    def _init_ui(self):
        """Initialize the user interface."""
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Show selected items
        items_text = "Selected Items:\n" + "\n".join([item['description'] for item in self.selected_items])
        items_label = wx.StaticText(panel, label=items_text)
        sizer.Add(items_label, 0, wx.ALL, 10)
        
        # Description/Remark input
        desc_label = wx.StaticText(panel, label="Description/Remark:")
        sizer.Add(desc_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        
        self.desc_ctrl = wx.TextCtrl(
            panel,
            style=wx.TE_MULTILINE | wx.TE_WORDWRAP,
            size=(-1, 100)
        )
        sizer.Add(self.desc_ctrl, 1, wx.EXPAND | wx.ALL, 10)
        
        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        save_btn = wx.Button(panel, label="Save")
        save_btn.Bind(wx.EVT_BUTTON, self._on_save)
        btn_sizer.Add(save_btn, 0, wx.ALL, 5)
        
        cancel_btn = wx.Button(panel, label="Cancel")
        cancel_btn.Bind(wx.EVT_BUTTON, self._on_cancel)
        btn_sizer.Add(cancel_btn, 0, wx.ALL, 5)
        
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
        
        panel.SetSizer(sizer)
    
    def _on_save(self, event):
        """Save the annotation."""
        description = self.desc_ctrl.GetValue().strip()
        
        if not description:
            wx.MessageBox(
                "Please enter a description.",
                "Warning",
                wx.OK | wx.ICON_WARNING
            )
            return
        
        # Create annotation entry
        annotation = {
            'timestamp': datetime.now().isoformat(),
            'items': self.selected_items,
            'description': description
        }
        
        # Load existing annotations
        annotations_file = os.path.join(self.notes_dir, "item_annotations.json")
        annotations = []
        
        if os.path.exists(annotations_file):
            try:
                with open(annotations_file, 'r', encoding='utf-8') as f:
                    annotations = json.load(f)
            except:
                annotations = []
        
        # Add new annotation
        annotations.append(annotation)
        
        # Save annotations
        try:
            with open(annotations_file, 'w', encoding='utf-8') as f:
                json.dump(annotations, f, indent=2)
            
            wx.MessageBox(
                "Design note saved successfully!",
                "Success",
                wx.OK | wx.ICON_INFORMATION
            )
            self.EndModal(wx.ID_OK)
        except Exception as e:
            wx.MessageBox(
                f"Error saving note: {e}",
                "Error",
                wx.OK | wx.ICON_ERROR
            )
    
    def _on_cancel(self, event):
        """Cancel the dialog."""
        self.EndModal(wx.ID_CANCEL)


class NotesFrame(wx.Frame):
    """Main window with tasks and general notes."""
    
    def __init__(self, parent, project_dir, project_name):
        super().__init__(
            parent,
            title=f"Design Notes & Tasks - {project_name}",
            size=(700, 500)
        )
        
        self.project_dir = project_dir
        self.project_name = project_name
        self.notes_dir = os.path.join(project_dir, ".inDesignNotes")
        self.tasks_file = os.path.join(self.notes_dir, "tasks.json")
        self.tasks = []
        
        # Create notes directory if it doesn't exist
        os.makedirs(self.notes_dir, exist_ok=True)
        
        # Create UI
        self._init_ui()
        
        # Load tasks
        self._load_tasks()
        
        # Center window
        self.Centre()
    
    def _init_ui(self):
        """Initialize the user interface."""
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Create notebook for tabs
        notebook = wx.Notebook(panel)
        
        # Tab 1: Tasks
        tasks_panel = self._create_tasks_panel(notebook)
        notebook.AddPage(tasks_panel, "Tasks")
        
        # Tab 2: Item Annotations
        annotations_panel = self._create_annotations_panel(notebook)
        notebook.AddPage(annotations_panel, "Design Notes")
        
        main_sizer.Add(notebook, 1, wx.EXPAND | wx.ALL, 5)
        
        # Close button
        close_btn = wx.Button(panel, label="Close")
        close_btn.Bind(wx.EVT_BUTTON, self._on_close)
        main_sizer.Add(close_btn, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
        
        panel.SetSizer(main_sizer)
        
        # Bind close event
        self.Bind(wx.EVT_CLOSE, self._on_close)
    
    def _create_tasks_panel(self, parent):
        """Create the tasks management panel."""
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Add task section
        add_label = wx.StaticText(panel, label="Add New Task:")
        sizer.Add(add_label, 0, wx.ALL, 5)
        
        # Task description input
        desc_sizer = wx.BoxSizer(wx.HORIZONTAL)
        desc_sizer.Add(wx.StaticText(panel, label="Description:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.task_desc_ctrl = wx.TextCtrl(panel, size=(300, -1))
        desc_sizer.Add(self.task_desc_ctrl, 1, wx.EXPAND)
        sizer.Add(desc_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        # Task remark input
        remark_sizer = wx.BoxSizer(wx.HORIZONTAL)
        remark_sizer.Add(wx.StaticText(panel, label="Remark:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.task_remark_ctrl = wx.TextCtrl(panel, size=(300, -1))
        remark_sizer.Add(self.task_remark_ctrl, 1, wx.EXPAND)
        sizer.Add(remark_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        # Add task button
        add_btn = wx.Button(panel, label="Add Task")
        add_btn.Bind(wx.EVT_BUTTON, self._on_add_task)
        sizer.Add(add_btn, 0, wx.ALL, 5)
        
        # Separator
        sizer.Add(wx.StaticLine(panel), 0, wx.EXPAND | wx.ALL, 5)
        
        # Tasks list
        list_label = wx.StaticText(panel, label="Tasks:")
        sizer.Add(list_label, 0, wx.ALL, 5)
        
        # Scrolled window for tasks
        self.tasks_scroll = wx.ScrolledWindow(panel)
        self.tasks_scroll.SetScrollRate(5, 5)
        self.tasks_sizer = wx.BoxSizer(wx.VERTICAL)
        self.tasks_scroll.SetSizer(self.tasks_sizer)
        
        sizer.Add(self.tasks_scroll, 1, wx.EXPAND | wx.ALL, 5)
        
        panel.SetSizer(sizer)
        return panel
    
    def _create_annotations_panel(self, parent):
        """Create the annotations view panel."""
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        label = wx.StaticText(panel, label="Design Notes for Board Items:")
        sizer.Add(label, 0, wx.ALL, 5)
        
        # Text control to display annotations
        self.annotations_ctrl = wx.TextCtrl(
            panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP
        )
        sizer.Add(self.annotations_ctrl, 1, wx.EXPAND | wx.ALL, 5)
        
        # Refresh button
        refresh_btn = wx.Button(panel, label="Refresh")
        refresh_btn.Bind(wx.EVT_BUTTON, self._on_refresh_annotations)
        sizer.Add(refresh_btn, 0, wx.ALL, 5)
        
        panel.SetSizer(sizer)
        
        # Load annotations initially
        self._load_annotations()
        
        return panel
    
    def _on_add_task(self, event):
        """Add a new task."""
        description = self.task_desc_ctrl.GetValue().strip()
        remark = self.task_remark_ctrl.GetValue().strip()
        
        if not description:
            wx.MessageBox(
                "Please enter a task description.",
                "Warning",
                wx.OK | wx.ICON_WARNING
            )
            return
        
        # Create task
        task = {
            'id': len(self.tasks) + 1,
            'description': description,
            'remark': remark,
            'completed': False,
            'created': datetime.now().isoformat()
        }
        
        self.tasks.append(task)
        self._save_tasks()
        self._refresh_tasks_display()
        
        # Clear inputs
        self.task_desc_ctrl.SetValue("")
        self.task_remark_ctrl.SetValue("")
    
    def _refresh_tasks_display(self):
        """Refresh the tasks display."""
        # Clear existing task widgets
        self.tasks_sizer.Clear(True)
        
        # Add each task
        for task in self.tasks:
            task_panel = self._create_task_widget(task)
            self.tasks_sizer.Add(task_panel, 0, wx.EXPAND | wx.ALL, 5)
        
        self.tasks_scroll.Layout()
        self.tasks_scroll.FitInside()
    
    def _create_task_widget(self, task):
        """Create a widget for displaying a task."""
        panel = wx.Panel(self.tasks_scroll)
        panel.SetBackgroundColour(wx.Colour(240, 240, 240))
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Complete/Incomplete checkbox
        checkbox = wx.CheckBox(panel, label="")
        checkbox.SetValue(task['completed'])
        checkbox.Bind(wx.EVT_CHECKBOX, lambda e: self._on_toggle_task(task['id'], e))
        sizer.Add(checkbox, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        
        # Task info
        info_sizer = wx.BoxSizer(wx.VERTICAL)
        
        desc_text = wx.StaticText(panel, label=f"Description: {task['description']}")
        info_sizer.Add(desc_text, 0, wx.ALL, 2)
        
        if task['remark']:
            remark_text = wx.StaticText(panel, label=f"Remark: {task['remark']}")
            info_sizer.Add(remark_text, 0, wx.ALL, 2)
        
        status = "Completed" if task['completed'] else "Incomplete"
        status_text = wx.StaticText(panel, label=f"Status: {status}")
        info_sizer.Add(status_text, 0, wx.ALL, 2)
        
        sizer.Add(info_sizer, 1, wx.EXPAND | wx.ALL, 5)
        
        # Delete button
        del_btn = wx.Button(panel, label="Delete", size=(60, -1))
        del_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_delete_task(task['id']))
        sizer.Add(del_btn, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        
        panel.SetSizer(sizer)
        return panel
    
    def _on_toggle_task(self, task_id, event):
        """Toggle task completion status."""
        for task in self.tasks:
            if task['id'] == task_id:
                task['completed'] = event.IsChecked()
                break
        
        self._save_tasks()
        self._refresh_tasks_display()
    
    def _on_delete_task(self, task_id):
        """Delete a task."""
        self.tasks = [t for t in self.tasks if t['id'] != task_id]
        self._save_tasks()
        self._refresh_tasks_display()
    
    def _load_tasks(self):
        """Load tasks from file."""
        if os.path.exists(self.tasks_file):
            try:
                with open(self.tasks_file, 'r', encoding='utf-8') as f:
                    self.tasks = json.load(f)
            except:
                self.tasks = []
        
        self._refresh_tasks_display()
    
    def _save_tasks(self):
        """Save tasks to file."""
        try:
            with open(self.tasks_file, 'w', encoding='utf-8') as f:
                json.dump(self.tasks, f, indent=2)
        except Exception as e:
            wx.MessageBox(
                f"Error saving tasks: {e}",
                "Error",
                wx.OK | wx.ICON_ERROR
            )
    
    def _load_annotations(self):
        """Load and display annotations."""
        annotations_file = os.path.join(self.notes_dir, "item_annotations.json")
        
        if not os.path.exists(annotations_file):
            self.annotations_ctrl.SetValue("No design notes yet.\n\nSelect items on the board and open this plugin to add notes.")
            return
        
        try:
            with open(annotations_file, 'r', encoding='utf-8') as f:
                annotations = json.load(f)
            
            # Format annotations for display
            text = ""
            for i, ann in enumerate(annotations, 1):
                text += f"--- Note {i} ---\n"
                text += f"Date: {ann['timestamp'][:19]}\n"
                text += "Items: " + ", ".join([item['description'] for item in ann['items']]) + "\n"
                text += f"Description: {ann['description']}\n\n"
            
            self.annotations_ctrl.SetValue(text)
        except Exception as e:
            self.annotations_ctrl.SetValue(f"Error loading annotations: {e}")
    
    def _on_refresh_annotations(self, event):
        """Refresh annotations display."""
        self._load_annotations()
    
    def _on_close(self, event):
        """Handle window close."""
        self.Destroy()


# Register the plugin
InDesignNotePlugin().register()
