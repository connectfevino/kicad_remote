"""
KiCad InDesignNote Plugin - Simple Design Notes Tool
A minimal plugin for adding design notes to KiCad PCB projects
"""

import pcbnew
import wx
import os


class InDesignNotePlugin(pcbnew.ActionPlugin):
    """
    Simple KiCad plugin for design notes.
    """
    
    def defaults(self):
        """Set plugin metadata."""
        self.name = "InDesignNote"
        self.category = "Utilities"
        self.description = "Simple design notes for your PCB project"
        self.show_toolbar_button = True
        self.icon_file_name = ""  # Optional: add icon path here
    
    def Run(self):
        """Run the plugin - show a simple notes window."""
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
        
        # Create and show the notes window
        frame = NotesFrame(None, project_dir, project_name)
        frame.Show()


class NotesFrame(wx.Frame):
    """Simple notes window with basic text editor."""
    
    def __init__(self, parent, project_dir, project_name):
        super().__init__(
            parent,
            title=f"Design Notes - {project_name}",
            size=(600, 400)
        )
        
        self.project_dir = project_dir
        self.project_name = project_name
        self.notes_file = os.path.join(project_dir, f"{project_name}_notes.txt")
        
        # Create UI
        self._init_ui()
        
        # Load existing notes
        self._load_notes()
        
        # Center window
        self.Centre()
    
    def _init_ui(self):
        """Initialize the user interface."""
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Title label
        title = wx.StaticText(panel, label="Design Notes:")
        sizer.Add(title, 0, wx.ALL, 5)
        
        # Text editor
        self.text_ctrl = wx.TextCtrl(
            panel,
            style=wx.TE_MULTILINE | wx.TE_WORDWRAP
        )
        sizer.Add(self.text_ctrl, 1, wx.EXPAND | wx.ALL, 5)
        
        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        save_btn = wx.Button(panel, label="Save")
        save_btn.Bind(wx.EVT_BUTTON, self._on_save)
        btn_sizer.Add(save_btn, 0, wx.ALL, 5)
        
        close_btn = wx.Button(panel, label="Close")
        close_btn.Bind(wx.EVT_BUTTON, self._on_close)
        btn_sizer.Add(close_btn, 0, wx.ALL, 5)
        
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT)
        
        panel.SetSizer(sizer)
        
        # Bind close event
        self.Bind(wx.EVT_CLOSE, self._on_close)
    
    def _load_notes(self):
        """Load notes from file if it exists."""
        if os.path.exists(self.notes_file):
            try:
                with open(self.notes_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    self.text_ctrl.SetValue(content)
            except Exception as e:
                wx.MessageBox(
                    f"Error loading notes: {e}",
                    "Error",
                    wx.OK | wx.ICON_ERROR
                )
        else:
            # Set default template
            template = f"""# {self.project_name} - Design Notes

## Overview
[Brief description of the PCB project]

## Schematic Notes
[Key circuit blocks, design rationale]

## Layout Considerations
[Layer stackup, impedance, keep-outs]

## Component Notes
[Important component selections and specifications]

## References
[Datasheets, application notes, calculations]
"""
            self.text_ctrl.SetValue(template)
    
    def _on_save(self, event):
        """Save notes to file."""
        try:
            content = self.text_ctrl.GetValue()
            with open(self.notes_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            wx.MessageBox(
                "Notes saved successfully!",
                "Success",
                wx.OK | wx.ICON_INFORMATION
            )
        except Exception as e:
            wx.MessageBox(
                f"Error saving notes: {e}",
                "Error",
                wx.OK | wx.ICON_ERROR
            )
    
    def _on_close(self, event):
        """Handle window close - ask to save if modified."""
        # Simple close without checking for modifications
        # You can add modification tracking if needed
        self.Destroy()


# Register the plugin
InDesignNotePlugin().register()
